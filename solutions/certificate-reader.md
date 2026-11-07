# CH01: Certificate identities and RBAC scope

Attempt [CH01](../labs/cluster-hardening.md#ch01-rbac-and-csrs) first. Use a disposable cluster and the [shared baseline](../preparation/LAB-SAFETY.md). Commands run individually from the repository root with the administrator's lab kubeconfig unless `--kubeconfig` selects the new client identity. Inspect each result before continuing; negative authorization probes intentionally exit nonzero.

## Issue a client certificate through a CSR

**Start:** require OpenSSL, kubectl, a working client-certificate signer and an administrator allowed to create and approve the named CSR. The user `cks-reader` must have no existing user or group grants. Use a fresh `work/CH01` directory; if it already exists, complete the prior attempt's cleanup before reusing it. Do not overwrite another attempt's key or kubeconfig.

```bash
umask 077
mkdir -p work
mkdir -m 700 work/CH01
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 \
  -out work/CH01/reader.key
openssl req -new -key work/CH01/reader.key \
  -subj '/CN=cks-reader' -out work/CH01/reader.csr
openssl req -in work/CH01/reader.csr -noout -subject -verify
```

**Task:** submit the public request with a one-hour requested lifetime. No organization is specified in the subject, so the certificate does not request membership in a privileged group.

```bash
CH01_REQUEST=$(base64 -w 0 < work/CH01/reader.csr)
cat > work/CH01/csr.yaml <<EOF
apiVersion: certificates.k8s.io/v1
kind: CertificateSigningRequest
metadata:
  name: ch01-reader
spec:
  request: $CH01_REQUEST
  signerName: kubernetes.io/kube-apiserver-client
  expirationSeconds: 3600
  usages:
  - client auth
EOF
kubectl create -f work/CH01/csr.yaml
kubectl get csr ch01-reader -o yaml
kubectl get csr ch01-reader -o jsonpath='{.spec.request}' \
  | base64 --decode > work/CH01/submitted.csr
cmp work/CH01/reader.csr work/CH01/submitted.csr
openssl req -in work/CH01/submitted.csr -noout -subject -text -verify
```

Check the subject, signer, usage and exact request bytes before approving **only** `ch01-reader`. Approval and issuance are separate events:

```bash
kubectl certificate approve ch01-reader
kubectl wait --for=jsonpath='{.status.certificate}' \
  csr/ch01-reader --timeout=60s
kubectl get csr ch01-reader -o jsonpath='{.status.certificate}' \
  | base64 --decode > work/CH01/reader.crt
openssl x509 -in work/CH01/reader.crt -noout -subject -issuer -dates
```

If the certificate wait times out, inspect the CSR conditions and signer/controller configuration. An `Approved` condition without `status.certificate` is not a usable credential. Inspect the issued validity period instead of assuming the requested duration was granted. See [Kubernetes CSR signers](https://kubernetes.io/docs/reference/access-authn-authz/certificate-signing-requests/#kubernetes-signers).

Extract only the selected cluster's endpoint and **public server CA**. `--flatten` resolves a referenced CA file; `--raw` prevents encoded data from being redacted; the JSONPath limits output to the public CA field. Do not save or print the administrator's complete raw kubeconfig.

```bash
CH01_SERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
kubectl config view --minify --flatten --raw \
  -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' \
  | base64 --decode > work/CH01/server-ca.crt
test -s work/CH01/server-ca.crt
openssl x509 -in work/CH01/server-ca.crt -noout -subject -issuer
kubectl --kubeconfig work/CH01/reader.conf config set-cluster ch01-lab \
  --server="$CH01_SERVER" --certificate-authority=work/CH01/server-ca.crt \
  --embed-certs=true
kubectl --kubeconfig work/CH01/reader.conf config set-credentials cks-reader \
  --client-certificate=work/CH01/reader.crt --client-key=work/CH01/reader.key \
  --embed-certs=true
kubectl --kubeconfig work/CH01/reader.conf config set-context ch01-reader \
  --cluster=ch01-lab --user=cks-reader --namespace=cks-lab
kubectl --kubeconfig work/CH01/reader.conf config use-context ch01-reader
```

This reference assumes a normal kubeadm endpoint whose TLS identity matches its URL and whose public CA is configured. Stop if the CA extraction is empty; obtain the lab's trusted CA instead of disabling verification. If the administrator's cluster entry uses `tls-server-name`, preserve that verified name in the new cluster entry too. The API serving CA and the CA used to sign client certificates need not be identical.

As administrator, create only a namespace Pod-reader grant:

```bash
kubectl -n cks-lab create role ch01-pod-reader --verb=get,list --resource=pods
kubectl -n cks-lab create rolebinding ch01-reader \
  --role=ch01-pod-reader --user=cks-reader
```

**Prove:** use the new credential for every request below, with no impersonation:

```bash
kubectl --kubeconfig work/CH01/reader.conf auth whoami
kubectl --kubeconfig work/CH01/reader.conf get pods -n cks-lab
kubectl --kubeconfig work/CH01/reader.conf get secrets -n cks-lab
kubectl --kubeconfig work/CH01/reader.conf get pods -n cks-other
kubectl --kubeconfig work/CH01/reader.conf run ch01-denied -n cks-lab \
  --image=docker.io/library/busybox:1.37 --restart=Never --dry-run=server \
  --command -- sleep 60
kubectl --kubeconfig work/CH01/reader.conf delete pod client -n cks-lab --dry-run=server
```

Expect the `cks-reader` identity and a local Pod list, followed by four `Forbidden` responses. The final two are server-side dry runs and must not create or delete a Pod. A TLS handshake failure, expired certificate or unavailable API is not an RBAC-denial result. Complete the Role-escalation check in CH01 before resetting, if practicing it in this attempt.

## Compare namespaced and cluster-wide bindings

**Start:** retain the valid `cks-reader` credential from the previous section. The temporary ClusterRole below permits only reading Pod objects. It grants no Secrets, logs, exec or writes. Removing the original binding isolates the scope comparison; leave the original Role for the later reset.

```bash
kubectl -n cks-lab delete rolebinding ch01-reader
kubectl create clusterrole ch01-shared-pod-reader --verb=get,list --resource=pods
kubectl -n cks-lab create rolebinding ch01-scoped-reader \
  --clusterrole=ch01-shared-pod-reader --user=cks-reader
```

**Task and prove:** with a RoleBinding, the ClusterRole's Pod permissions apply only in that binding's namespace:

```bash
kubectl --kubeconfig work/CH01/reader.conf get pods -n cks-lab
kubectl --kubeconfig work/CH01/reader.conf get pods -n cks-other
kubectl --kubeconfig work/CH01/reader.conf get pods --all-namespaces
```

Expect success, denial and denial. Replace only that task-owned binding with a ClusterRoleBinding:

```bash
kubectl -n cks-lab delete rolebinding ch01-scoped-reader
kubectl create clusterrolebinding ch01-wide-reader \
  --clusterrole=ch01-shared-pod-reader --user=cks-reader
kubectl --kubeconfig work/CH01/reader.conf get pods -n cks-lab
kubectl --kubeconfig work/CH01/reader.conf get pods -n cks-other
kubectl --kubeconfig work/CH01/reader.conf get pods --all-namespaces
kubectl --kubeconfig work/CH01/reader.conf get secrets -n cks-lab
```

The three Pod lists now succeed; the Secret list remains forbidden. The [binding type determines the grant's scope](https://kubernetes.io/docs/reference/access-authn-authz/rbac/#rolebinding-and-clusterrolebinding), while the rules still limit which resources and verbs it covers.

**Reset:** remove the broader binding and check that neither namespace can be read before restoring the original narrow grant:

```bash
kubectl delete clusterrolebinding ch01-wide-reader
kubectl --kubeconfig work/CH01/reader.conf get pods -n cks-lab
kubectl --kubeconfig work/CH01/reader.conf get pods -n cks-other
kubectl delete clusterrole ch01-shared-pod-reader
kubectl -n cks-lab create rolebinding ch01-reader \
  --role=ch01-pod-reader --user=cks-reader
```

Both reads during the unbound interval must be forbidden. An unexpected success means another binding is contributing permissions; inspect that lab state before continuing.

## Reset the CSR exercise

Remove any remaining `ch01-role-author`, `ch01-scoped-reader` and `ch01-wide-reader` exercise bindings first, along with their corresponding temporary Roles or ClusterRole. Remove only objects created for this attempt.

```bash
kubectl -n cks-lab delete rolebinding ch01-reader
kubectl --kubeconfig work/CH01/reader.conf get pods -n cks-lab
kubectl -n cks-lab delete role ch01-pod-reader
kubectl delete csr ch01-reader
rm -f work/CH01/reader.key work/CH01/reader.csr work/CH01/submitted.csr \
  work/CH01/reader.crt work/CH01/reader.conf work/CH01/server-ca.crt work/CH01/csr.yaml
rmdir work/CH01
```

The Pod list after binding removal must be forbidden while the certificate is still valid. Deleting the CSR does **not** revoke an issued certificate. Removing the binding withdraws this authorization grant, while the credential can still authenticate until expiry and may have permissions from other bindings. The kubeconfig embeds the private key, so remove it as well as the separate key file. `rmdir` deliberately refuses to remove a nonempty directory; preserve or relocate any additional evidence before starting another fresh attempt.

## Manual signing on a disposable control plane

**Start:** this separate variation requires a snapshotted kubeadm control-plane VM, root access and the actual lab client-signing CA key. It is unsuitable for a managed cluster or an external-CA installation where that key is unavailable. Never copy, display or commit the CA private key. Keep it at its original node path and pass that path directly to OpenSSL.

Run these commands **on the disposable control-plane VM in a root shell**, not on the workstation. Prepare the shared `cks-lab` and `cks-other` namespaces and workloads on this cluster first. Verify `/etc/kubernetes/admin.conf` addresses this lab and the API server's `--client-ca-file` trusts the selected signing CA. The variables below use ordinary kubeadm defaults; resolve the manifest's volume mappings if this installation uses different host paths. The `cks-manual-reader` user must be fresh and have no existing bindings.

```bash
sudo -i
umask 077
mkdir -m 700 /root/ch01-manual
cd /root/ch01-manual
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}{"\n"}'
CH01_CA_CERT=/etc/kubernetes/pki/ca.crt
CH01_CA_KEY=/etc/kubernetes/pki/ca.key
test -r "$CH01_CA_CERT" && test -r "$CH01_CA_KEY"
openssl x509 -in "$CH01_CA_CERT" -noout -subject -issuer -fingerprint -sha256
```

**Task:** generate a fresh client key and request. The extensions make this a client-authentication certificate rather than a CA. A random serial avoids modifying the CA directory or reusing a fixed serial. This portable `openssl x509` example issues a one-day certificate; inspect its actual expiry and remove the authorization grant immediately after practicing.

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out manual.key
openssl req -new -key manual.key -subj '/CN=cks-manual-reader' -out manual.csr
cat > client.ext <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=clientAuth
EOF
openssl req -in manual.csr -noout -subject -verify
CH01_SERIAL="0x$(openssl rand -hex 16)"
openssl x509 -req -in manual.csr -CA "$CH01_CA_CERT" -CAkey "$CH01_CA_KEY" \
  -set_serial "$CH01_SERIAL" -days 1 -sha256 -extfile client.ext -out manual.crt
openssl verify -purpose sslclient -CAfile "$CH01_CA_CERT" manual.crt
openssl x509 -in manual.crt -noout -subject -issuer -serial -dates -text
```

Do not use `-CAcreateserial` here, which would create or update a serial file beside the CA. Do not create a replacement CA, sign an administrator subject, or request `system:masters`. See [manual certificate generation](https://kubernetes.io/docs/tasks/administer-cluster/certificates/) for the underlying PKI operations.

Construct a new kubeconfig using only this fresh client credential and the public serving CA from the lab's admin context. Do not reuse or modify `admin.conf`:

```bash
CH01_SERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
kubectl config view --minify --flatten --raw \
  -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' \
  | base64 --decode > server-ca.crt
test -s server-ca.crt
kubectl --kubeconfig manual.conf config set-cluster ch01-lab \
  --server="$CH01_SERVER" --certificate-authority=server-ca.crt --embed-certs=true
kubectl --kubeconfig manual.conf config set-credentials cks-manual-reader \
  --client-certificate=manual.crt --client-key=manual.key --embed-certs=true
kubectl --kubeconfig manual.conf config set-context ch01-manual \
  --cluster=ch01-lab --user=cks-manual-reader --namespace=cks-lab
kubectl --kubeconfig manual.conf config use-context ch01-manual
kubectl -n cks-lab create role ch01-manual-pod-reader --verb=get,list --resource=pods
kubectl -n cks-lab create rolebinding ch01-manual-reader \
  --role=ch01-manual-pod-reader --user=cks-manual-reader
```

The same CA and TLS-name checks from the CSR example apply here.

**Prove:** the manually signed credential must actually authenticate and obey the namespace boundary:

```bash
kubectl --kubeconfig manual.conf auth whoami
kubectl --kubeconfig manual.conf get pods -n cks-lab
kubectl --kubeconfig manual.conf get secrets -n cks-lab
kubectl --kubeconfig manual.conf get pods -n cks-other
```

Expect `cks-manual-reader`, a local Pod list, and two authorization denials. This identity has no Kubernetes CSR object because signing occurred outside the CSR API.

**Reset:** while the certificate is valid, remove its binding and prove Pod access is withdrawn, then remove only the exercise Role and generated client artifacts:

```bash
kubectl -n cks-lab delete rolebinding ch01-manual-reader
kubectl --kubeconfig manual.conf get pods -n cks-lab
kubectl -n cks-lab delete role ch01-manual-pod-reader
rm -f manual.key manual.csr manual.crt manual.conf server-ca.crt client.ext
cd /root
rmdir /root/ch01-manual
exit
```

Leave the lab CA certificate and private key untouched. Removing RBAC withdraws the grant; it does not cryptographically invalidate the certificate. Finish with the disposable environment's normal snapshot/reset procedure.
