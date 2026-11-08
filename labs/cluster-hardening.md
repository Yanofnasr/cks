# Cluster hardening

Use the [environment guide](../preparation/LAB-SAFETY.md) and a fresh shared workload fixture unless a drill requires a separate VM snapshot. Commands start at the repository root unless a step explicitly belongs on a lab node. Save local artifacts under `work/CHxx/`, keep credentials private, and record evidence in the [progress log](../preparation/PROGRESS.md).

## CH01 RBAC and CSRs

**Start:** use the shared namespaces and cluster-admin access to the disposable cluster. Create a unique lab user identity `cks-reader`; it must have no existing group or user binding. Under `work/CH01/`, generate a private key and CSR with subject `/CN=cks-reader` and no privileged organization. Use `umask 077` before creating private files.

**Task:** submit a `certificates.k8s.io/v1` CertificateSigningRequest named `ch01-reader`, with signer `kubernetes.io/kube-apiserver-client`, usage `client auth`, and a short requested lifetime such as 3600 seconds. Inspect the request before approving only that named CSR. Save the issued certificate and construct a separate kubeconfig using the lab API address and CA, this key and certificate, and namespace `cks-lab`.

Create a Role `ch01-pod-reader` allowing only `get` and `list` on core-group Pods in `cks-lab`. Bind it to the user with a RoleBinding `ch01-reader`. Do not grant a ClusterRoleBinding or Secret access.

**Prove:** first test the intended permissions using administrator impersonation, then repeat with the separate credential to prove authentication as well as authorization:

```bash
kubectl auth can-i list pods -n cks-lab --as=cks-reader
kubectl auth can-i get secrets -n cks-lab --as=cks-reader
kubectl auth can-i list pods -n cks-other --as=cks-reader
kubectl --kubeconfig work/CH01/reader.conf auth whoami
kubectl --kubeconfig work/CH01/reader.conf get pods -n cks-lab
kubectl --kubeconfig work/CH01/reader.conf get secrets -n cks-lab
```

Expect `yes`, `no`, `no`, the intended user identity, a Pod list, and an authorization denial respectively. Inspect the certificate subject and actual validity dates; requested lifetime is not proof of issued lifetime. Confirm create/delete operations are also denied.

The [certificate-reader reference](../solutions/certificate-reader.md) gives the full CSR, approval, certificate retrieval and isolated kubeconfig sequence. After the basic proof, compare a read-only ClusterRole bound through a namespaced RoleBinding with the same ClusterRole bound through a ClusterRoleBinding. Test both namespaces using the actual client certificate, then remove the broader binding. Its separate manual-signing variation uses a fresh identity and the disposable control plane's client CA key in place, with a unique serial, client-authentication extensions and a short lifetime.

**Role-escalation check:** as the administrator, create a temporary Role named `ch01-role-author` allowing only `create` on `roles` in `rbac.authorization.k8s.io`, and bind it to `cks-reader` through a RoleBinding with the same name. Do not grant `escalate`, `bind`, updates or wildcard permissions. The user can now submit a Role, but Kubernetes must still reject permissions it does not hold:

```bash
kubectl --kubeconfig work/CH01/reader.conf create role ch01-equivalent \
  -n cks-lab --verb=get,list --resource=pods --dry-run=server -o yaml
kubectl --kubeconfig work/CH01/reader.conf create role ch01-forbidden \
  -n cks-lab --verb=get --resource=secrets --resource-name=training-secret \
  --dry-run=server -o yaml
```

The equivalent Pod-reader Role should pass the server-side dry run; the Secret-reader Role should be forbidden because it would grant an unheld permission. A denial of the ordinary `create roles` operation does not demonstrate the escalation guard, which is why the positive control is required. Neither probe persists a Role. Remove the temporary RoleBinding and Role afterward. See [RBAC privilege-escalation prevention](https://kubernetes.io/docs/reference/access-authn-authz/rbac/#restrictions-on-role-creation-or-update).

**Reset:** remove any remaining `ch01-role-author` RoleBinding and Role, then remove `ch01-reader` and verify that the existing certificate can no longer list Pods. Remove `ch01-pod-reader`, the named CSR and local key/kubeconfig files. Deleting a CSR alone does **not** revoke an already-issued client certificate. Restore the snapshot if you accidentally granted broader permissions.

## CH02 ServiceAccounts

**Start:** create a ServiceAccount named `ch02-client` in `cks-lab`, initially without a RoleBinding. Create a new Pod `ch02-client` from the client stanza in [workloads.yaml](fixtures/workloads.yaml), selecting this ServiceAccount. Omit the Pod's `automountServiceAccountToken` field for the first test so that you can observe the ServiceAccount default.

**Task:** disable token automounting on the ServiceAccount and recreate the Pod. Grant the identity only `get` and `list` on Pods in `cks-lab`, through a Role and RoleBinding both named `ch02-pod-reader`. Keep the workload's token unmounted despite granting those API permissions.

**Prove:** compare the projected volumes/mounts and the token-file presence before and after recreation. Inspect presence only, never print a token. Prove that mounting and authorization are distinct:

```bash
for verb in get list; do
  kubectl auth can-i "$verb" pods -n cks-lab \
    --as=system:serviceaccount:cks-lab:ch02-client
done
for verb in get list watch; do
  kubectl auth can-i "$verb" secrets -n cks-lab \
    --as=system:serviceaccount:cks-lab:ch02-client
done
for verb in watch create update patch delete deletecollection; do
  kubectl auth can-i "$verb" pods -n cks-lab \
    --as=system:serviceaccount:cks-lab:ch02-client
done
kubectl auth can-i list pods -n cks-other \
  --as=system:serviceaccount:cks-lab:ch02-client
```

Only the first two queries must say `yes`; all others must say `no`, while the Pod still has no automatically mounted token. A failed request or impersonation error is not the expected authorization answer. Secret `list` and `watch` permission can reveal values even when `get` is denied. Inspect the Role and every binding contributing to this identity so that the intended grant contains only `get` and `list` on Pods.

Run the independent verifier before cleanup, using the lab context selected during setup:

The drill's Role adds only Pod reads. Kubernetes also provides standard self-review APIs and, on the current baseline, read access to public [ClusterTrustBundles](https://kubernetes.io/docs/reference/access-authn-authz/certificate-signing-requests/#cluster-trust-bundles). These public certificates are separate from Secrets. Preserve those built-in grants; the verifier permits them while rejecting additional workload permissions, including grants restricted to named resources.

```bash
python3 scripts/lab.py --context "$LAB_CONTEXT" verify CH02
```

**Core complete:** record the authorization and token-mounting results. For a first session, finish here and clean up the four core resources:

```bash
kubectl -n cks-lab delete pod ch02-client --wait=true
kubectl -n cks-lab delete rolebinding ch02-pod-reader
kubectl -n cks-lab delete role ch02-pod-reader
kubectl -n cks-lab delete serviceaccount ch02-client
kubectl -n cks-lab get pod/ch02-client rolebinding/ch02-pod-reader \
  role/ch02-pod-reader serviceaccount/ch02-client --ignore-not-found
```

The final query must succeed without returning resources. The optional sections below begin from the proved Pod-reader state; retain it if continuing now, or recreate and verify it before a later attempt. Run the final reset after any extension.

### Optional token projection

Create a separate Pod named `ch02-projected` using `ch02-client`, with automatic token mounting still disabled and an explicit projected ServiceAccount token with a short lifetime and intended audience. Inspect the volume/mount specification and file presence without printing token contents. This proves explicit projection is separate from automatic mounting; it does not prove the audience is accepted by a particular API, actual expiry, or credential rotation. Delete `ch02-projected` afterward and keep the core Pod unchanged.

### Optional binding and indirect Secret access

**Binding check:** as the administrator, create an unbound Role `ch02-secret-probe` allowing only `get` on the dummy Secret name `training-secret`. A Role alone grants nobody access. Temporarily grant `ch02-client` only `create` on namespaced `rolebindings` through a Role and RoleBinding named `ch02-binding-author`. Do not grant `bind`, `escalate` or access to Secrets. Run these server-side dry runs as that limited identity:

```bash
kubectl --as=system:serviceaccount:cks-lab:ch02-client create rolebinding ch02-equivalent \
  -n cks-lab --role=ch02-pod-reader --serviceaccount=cks-lab:ch02-client \
  --dry-run=server -o yaml
kubectl --as=system:serviceaccount:cks-lab:ch02-client create rolebinding ch02-forbidden \
  -n cks-lab --role=ch02-secret-probe --serviceaccount=cks-lab:ch02-client \
  --dry-run=server -o yaml
```

The first should be accepted; the second should be forbidden because the identity cannot bind a Role containing an unheld permission. Neither binding is stored. Remove the temporary `ch02-binding-author` RoleBinding and Role, then the unbound `ch02-secret-probe` Role. Confirm the ServiceAccount returns to its original Pod-reader-only permissions. See [restrictions on RoleBinding creation](https://kubernetes.io/docs/reference/access-authn-authz/rbac/#restrictions-on-role-binding-creation-or-update).

**Secret-via-Pod extension:** start with the original Pod-reader-only ServiceAccount and no other exercise grants. Use this synthetic value only. As the administrator, create the dummy Secret and prepare a restricted-compatible Pod:

```bash
umask 077
mkdir -p work/CH02
kubectl -n cks-lab create secret generic ch02-dummy-secret \
  --from-literal=marker=ch02-dummy-value
cat > work/CH02/secret-mount.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: ch02-secret-mount
  namespace: cks-lab
spec:
  serviceAccountName: ch02-client
  automountServiceAccountToken: false
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: probe
    image: docker.io/library/busybox:1.37
    command:
    - sh
    - -c
    - 'test "$(cat /dummy/marker)" = ch02-dummy-value && echo "mounted dummy Secret matched"'
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: [ALL]
    resources:
      requests:
        cpu: 10m
        memory: 16Mi
      limits:
        cpu: 100m
        memory: 64Mi
    volumeMounts:
    - name: dummy
      mountPath: /dummy
      readOnly: true
  volumes:
  - name: dummy
    secret:
      secretName: ch02-dummy-secret
      defaultMode: 0440
EOF
kubectl --as=system:serviceaccount:cks-lab:ch02-client \
  -n cks-lab get secret ch02-dummy-secret
kubectl --as=system:serviceaccount:cks-lab:ch02-client \
  create -f work/CH02/secret-mount.yaml --dry-run=server
```

Both requests must initially be forbidden. Temporarily grant only Pod creation in this lab namespace, then submit the Pod **as the limited identity**:

```bash
kubectl -n cks-lab create role ch02-pod-creator --verb=create --resource=pods
kubectl -n cks-lab create rolebinding ch02-pod-creator \
  --role=ch02-pod-creator --serviceaccount=cks-lab:ch02-client
kubectl --as=system:serviceaccount:cks-lab:ch02-client \
  create -f work/CH02/secret-mount.yaml
kubectl -n cks-lab wait --for=jsonpath='{.status.phase}'=Succeeded \
  pod/ch02-secret-mount --timeout=120s
kubectl --as=system:serviceaccount:cks-lab:ch02-client \
  -n cks-lab get pod ch02-secret-mount -o jsonpath='{.status.phase}{"\n"}'
kubectl -n cks-lab logs ch02-secret-mount
kubectl --as=system:serviceaccount:cks-lab:ch02-client \
  -n cks-lab get secret ch02-dummy-secret
```

Expect `Succeeded`, the fixed success message, and another direct Secret-read denial. The administrator reads the diagnostic log; the limited identity can already see the successful exit through its ordinary Pod-read permission. A Pod that cannot start or mount the Secret is not a successful proof. The kubelet supplied the mounted Secret without requiring the Pod creator to hold `get secrets`. Disabling ServiceAccount token mounting did not stop this filesystem access. This is why namespace workload creation can confer [indirect access to Secrets](https://kubernetes.io/docs/concepts/security/rbac-good-practices/#workload-creation).

Remove the extra grant and the already-created workload separately:

```bash
kubectl -n cks-lab delete rolebinding ch02-pod-creator
kubectl -n cks-lab delete role ch02-pod-creator
kubectl --as=system:serviceaccount:cks-lab:ch02-client \
  auth can-i create pods -n cks-lab
kubectl -n cks-lab delete pod ch02-secret-mount --wait=true
kubectl -n cks-lab delete secret ch02-dummy-secret
```

The authorization answer must return to `no`. Removing the creation grant does not terminate an existing Pod or remove its mounted data. RBAC cannot constrain a `create pods` grant to a preselected Pod name; keep this brief grant confined to the disposable namespace.

**Reset:** remove any remaining `ch02-binding-author` and `ch02-pod-creator` RoleBindings and Roles and the unbound `ch02-secret-probe` Role. Delete `ch02-client`, `ch02-projected` and `ch02-secret-mount` Pods, `ch02-pod-reader` RoleBinding and Role, `ch02-client` ServiceAccount and `ch02-dummy-secret` Secret. Remove the local extension manifest when finished. Confirm no exercise binding remains and do not change the `default` ServiceAccount or another task's identity.

The optional [worked references](../solutions/README.md) cover the ordinary Pod-reader identity and token-mounting setup.

## CH03 API server

**Start:** use a dedicated kubeadm control-plane VM with console/SSH recovery access and a snapshot. Record the current API-server manifest, authentication configuration, admission configuration and readiness. Back up files into a private directory **outside** `/etc/kubernetes/manifests`; extra manifests in that watched directory can be executed too.

**Task:** inspect the effective configuration and enforce the following while preserving the cluster's existing required settings:

- Anonymous access rejected for protected API resources, with only the required health-probe paths reachable without credentials.
- Node and RBAC authorization retained.
- NodeRestriction admission enabled alongside required existing plugins.
- Profiling disabled.
- Minimum TLS version set to at least TLS 1.2, using the actual supported version value.

Inspect the **actual** startup, liveness and readiness probes in the current manifest first. Kubeadm normally uses HTTPS `/livez` and `/readyz` probes without client credentials. Setting `--anonymous-auth=false` blindly can make those probes fail and repeatedly restart the API server.

For the 1.37 baseline, use the stable `AuthenticationConfiguration` mechanism to limit anonymous authentication to the required health paths. This is the shape of its anonymous section, not a replacement for an existing authentication configuration:

```yaml
apiVersion: apiserver.config.k8s.io/v1
kind: AuthenticationConfiguration
anonymous:
  enabled: true
  conditions:
    - path: /livez
    - path: /readyz
    - path: /healthz
```

Keep only health paths needed by this lab's probes or monitoring. Merge the section into an existing authentication configuration without dropping JWT settings. If creating a new configuration file, mount it read-only and reference its in-container path with `--authentication-config`. Do not also set `--anonymous-auth`; the two anonymous-configuration mechanisms conflict. If existing `--oidc-*` flags are in use, follow the documented authentication-configuration migration before combining settings.

Edit the existing manifest or referenced configuration; do not replace it with a generic static-Pod file. Preserve the current image, certificate authentication, ServiceAccount authentication, mounts, authorization, required admission plugins and provider settings. See [anonymous authenticator configuration](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#anonymous-authenticator-configuration) and [API health endpoints](https://kubernetes.io/docs/reference/using-api/health-checks/).

For a controlled failing baseline, you may enable profiling on the isolated snapshot before disabling it again. Do not grant anonymous administrator access as a setup shortcut.

**Prove:** the API becomes ready again and the shared workloads remain healthy:

```bash
kubectl get --raw='/readyz'
kubectl get nodes
kubectl -n cks-lab get pods
kubectl get --raw='/debug/pprof/'
```

An authenticated profiling request should no longer expose the profiler. Set `API_SERVER` to the lab API URL without a trailing slash and `CA_FILE` to its trusted CA bundle. These requests disable curl's default configuration and send no client credential:

```bash
curl -q --noproxy '*' --cacert "$CA_FILE" -sS -o /dev/null -w '%{http_code}\n' \
  "$API_SERVER/livez"
curl -q --noproxy '*' --cacert "$CA_FILE" -sS -o /dev/null -w '%{http_code}\n' \
  "$API_SERVER/readyz"
curl -q --noproxy '*' --cacert "$CA_FILE" -sS -o /dev/null -w '%{http_code}\n' \
  "$API_SERVER/api/v1/namespaces"
```

Expect `200`, `200`, and `401` once the API is healthy. Check the actual kubeadm probes stay successful and the restart count remains stable. A certificate or connection error is not an authentication rejection. Verify both the configured TLS value and an appropriate handshake rejection below the minimum. A TLS client refusing an old protocol before it connects is not server-side proof; mark that check unmeasured if the client cannot exercise it.

**Reset:** restore the backed-up configuration or VM snapshot if needed, then wait for API readiness and node recovery. Keep intentional hardening only when it is your chosen new baseline. Do not perform repeated speculative edits while the API is down; use node logs and the saved configuration.

## CH04 Kubelet

**Start:** use a dedicated worker VM with SSH recovery and a snapshot. Find the kubelet's active config and command-line overrides from its systemd unit/process, rather than assuming the first YAML file is authoritative. Back up the active files and record a working Pod log/exec request through the API server. The log and exec probes must target Pods on this worker: inspect their node placement, and on a multi-worker cluster create task-owned probes on the chosen worker and substitute their names below.

**Task:** enforce anonymous authentication disabled, webhook token authentication enabled, and Webhook authorization. Preserve the existing client CA, bootstrap settings, runtime endpoint, root directory and server certificate configuration. Disable an unauthenticated read-only endpoint if the environment exposes one. Change only the intended settings, then restart the kubelet when required.

**Prove:** the node returns to Ready and authorized API-server-mediated operations still work:

```bash
kubectl get nodes
kubectl -n cks-lab logs api
kubectl -n cks-lab exec client -- id
```

From the lab network, inspect a credential-free request to the chosen node's HTTPS `/pods` endpoint on port 10250. Use the appropriate trusted node certificate chain and confirm an HTTP authentication/authorization rejection, not a connection or certificate error. If the node uses a self-signed or incorrectly named serving certificate, record that trust problem separately; it must not masquerade as authentication success. Confirm an intended authorized kubelet operation remains permitted.

Inspect the effective configuration after restart, including any flags that override the file. Readiness by itself does not prove anonymous access is denied.

**Reset:** restore only the backed-up files if rolling back, restart kubelet, and verify node readiness and the original log/exec operations. Keep access to the VM independent of the kubelet until recovery is complete.

## CH05 Upgrade

**Start:** use a disposable two-node kubeadm cluster on Kubernetes 1.36 and prepare a supported 1.37 patch target. A cluster already on the target version is not an upgrade exercise. Check container-runtime and OS compatibility, package availability, version-skew rules, and the [official upgrade instructions](../preparation/REFERENCES.md). Save an etcd backup and coordinated VM recovery point using the installed tools appropriate to that cluster.

Do not apply the shared bare-Pod fixture in this separate upgrade environment. Create the task-owned `cks-lab` namespace and a small Deployment for observing rescheduling and recovery. If the fixture was already applied here, delete only its task-owned bare Pods before the drain exercise. Note available capacity and PodDisruptionBudgets before deciding whether uninterrupted service is feasible.

**Task:** write and carry out the version-specific sequence:

1. Select the correct Kubernetes package repository and exact package versions. Upgrade and re-hold kubeadm on the control plane.
2. Inspect `kubeadm upgrade plan`, then apply the selected target on the control plane.
3. Drain the control-plane node as required, upgrade kubelet/kubectl, restart kubelet, verify health and uncordon.
4. On the worker, upgrade kubeadm and run the node upgrade step. Drain it before upgrading/restarting kubelet, then verify and uncordon.

Use only the documented steps for the starting and target versions. Resolve drain blockers deliberately. Do not add blanket `--force` or delete-local-data flags to make an unexplained failure disappear.

**Prove:** collect the API-server, kubeadm and kubelet versions, node Ready/schedulable state, DNS resolution and application response after each node. The workload must recover. Check that no node remains cordoned and the actual configuration still satisfies the hardening from earlier drills. A successful package install alone is insufficient.

**Reset:** delete the exercise Deployment and use the saved recovery procedure if returning to the old version. Do not attempt a package-only downgrade of a changed control plane or discard the recovery data before validating the upgraded cluster.

## CH06 Recover an unavailable API server

**Start:** use a dedicated kubeadm cluster with one control-plane VM, a worker and the healthy shared workloads. Take a coordinated recovery snapshot and verify console/SSH access that does not depend on Kubernetes. This drill deliberately stops the only API server. Reserve this disposable cluster for the exercise and plan for API downtime; running Pods may continue, but scheduling and cluster administration will be unavailable.

Before the fault, record `kubectl get --raw='/readyz'`, `kubectl get nodes -o wide` and Pod readiness in both fixture namespaces. On the **control-plane VM**, inspect the active kubelet configuration and verify its static-Pod directory is `/etc/kubernetes/manifests`. Verify `sudo crictl ps -a --name kube-apiserver` works with the node's configured CRI endpoint before you need it for recovery. If this node uses different paths, resolve them before proceeding.

Save the existing manifest outside the watched directory, with its permissions, and keep this shell open:

```bash
CH06_MANIFEST=/etc/kubernetes/manifests/kube-apiserver.yaml
CH06_BACKUP=$(sudo mktemp -d /root/ch06-recovery.XXXXXX)
sudo cp --preserve=all "$CH06_MANIFEST" "$CH06_BACKUP/original.yaml"
sudo cmp "$CH06_MANIFEST" "$CH06_BACKUP/original.yaml"
printf '%s\n' "$CH06_BACKUP"
sudo cp --preserve=all "$CH06_BACKUP/original.yaml" "$CH06_BACKUP/fault.yaml"
sudoedit "$CH06_BACKUP/fault.yaml"
```

Record the printed backup directory in your private notes so that a replacement console shell can recover it. In `fault.yaml`, add exactly one argument to the existing `kube-apiserver` command list, using the same indentation as its other arguments:

```yaml
    - --ch06-deliberate-unknown-flag=true
```

**Task:** inspect the diff. It must contain only the added unknown flag, with the current image, mounts and all existing arguments preserved. A diff exit status of 1 means the expected difference exists. Then copy that edited manifest over the active file:

```bash
sudo diff -u "$CH06_BACKUP/original.yaml" "$CH06_BACKUP/fault.yaml"
sudo cp --preserve=all "$CH06_BACKUP/fault.yaml" "$CH06_MANIFEST"
```

Wait for the kubelet to observe the change. From the normal lab terminal, `kubectl --request-timeout=5s get --raw='/readyz'` should become unavailable. On the VM, diagnose without relying on `kubectl`:

```bash
sudo crictl ps -a --name kube-apiserver
sudo journalctl -u kubelet --since='5 minutes ago' --no-pager -n 80
```

Select the newest **failed** API-server container ID from that list and inspect its log:

```bash
CH06_FAILED_CONTAINER='replace-with-the-failed-container-id'
sudo crictl logs "$CH06_FAILED_CONTAINER"
sudo diff -u "$CH06_BACKUP/original.yaml" "$CH06_MANIFEST"
```

Identify the unknown-flag error and tie it to the single changed line. A connection timeout alone is not a diagnosis. Restore the exact saved manifest on the VM, even if the API is completely unreachable:

```bash
sudo cp --preserve=all "$CH06_BACKUP/original.yaml" "$CH06_MANIFEST"
sudo cmp "$CH06_BACKUP/original.yaml" "$CH06_MANIFEST"
sudo crictl ps -a --name kube-apiserver
```

The kubelet recreates the [static Pod](https://kubernetes.io/docs/tasks/configure-pod-container/static-pod/) from the restored file. Do not use `kubeadm reset`, regenerate certificates, replace the manifest with a sample, or delete the cluster. If recovery stalls, inspect the current container log and kubelet journal before making another change.

**Prove:** once the API responds again, run these from the ordinary lab terminal:

```bash
kubectl get --raw='/readyz?verbose'
kubectl wait --for=condition=Ready nodes --all --timeout=180s
kubectl -n cks-lab wait --for=condition=Ready pod --all --timeout=120s
kubectl -n cks-other wait --for=condition=Ready pod --all --timeout=120s
kubectl -n cks-lab exec client -- wget -qO- -T 3 http://api.cks-lab.svc:8080/
kubectl -n cks-other exec client -- wget -qO- -T 3 http://api.cks-other.svc:8080/
```

Confirm API-server restart counts stop increasing and readiness stays healthy across several probe intervals. Record the failure signature, the node-side tools that worked during the outage, and the recovery checks.

**Reset:** the byte-for-byte restored manifest is the intended reset. Retain the backup until the recovery proof passes. Then remove only `original.yaml` and `fault.yaml` from the recorded `CH06_BACKUP` directory and remove that empty directory. If restoring the VM snapshot instead, use the coordinated recovery point and repeat the health checks.

## CH07 Node authorization and NodeRestriction

**Start:** use a healthy disposable cluster with an actual worker and a second Node. Inspect the API server's effective authorization configuration: it must retain both `Node` and `RBAC`, with the `NodeRestriction` admission plugin enabled. Do not add permissive bindings to `system:nodes` or disable admission to make a probe pass. Run the following as a cluster administrator allowed to impersonate users and groups.

Set the variables to the exact Node names shown by the cluster, with the worker as the impersonated identity:

```bash
kubectl get nodes -o wide
CH07_WORKER='replace-with-actual-worker-name'
CH07_OTHER='replace-with-a-different-node-name'
test "$CH07_WORKER" != "$CH07_OTHER"
umask 077
mkdir -p work/CH07
kubectl get node "$CH07_WORKER" -o yaml > work/CH07/own-node.yaml
kubectl get node "$CH07_OTHER" -o yaml > work/CH07/other-node.yaml
CH07_AS=(--as="system:node:$CH07_WORKER" \
  --as-group=system:nodes --as-group=system:authenticated)
```

**Task:** run these three mutation probes individually. Each uses a saved object to identify the Node and a server-side dry run, so the API performs authorization and admission without persisting labels:

```bash
kubectl "${CH07_AS[@]}" patch -f work/CH07/own-node.yaml --type=merge \
  --patch '{"metadata":{"labels":{"practice.example.com/ch07":"probe"}}}' \
  --dry-run=server -o yaml
kubectl "${CH07_AS[@]}" patch -f work/CH07/own-node.yaml --type=merge \
  --patch '{"metadata":{"labels":{"node-restriction.kubernetes.io/ch07":"probe"}}}' \
  --dry-run=server -o yaml
kubectl "${CH07_AS[@]}" patch -f work/CH07/other-node.yaml --type=merge \
  --patch '{"metadata":{"labels":{"practice.example.com/ch07":"probe"}}}' \
  --dry-run=server -o yaml
```

**Prove:** expect the ordinary label on the worker's own Node to pass. The protected label on its own Node must be rejected by NodeRestriction, and the other-Node mutation must also be rejected. Read the returned reason; an impersonation-permission error or malformed manifest does not demonstrate the intended control.

Compare authorization alone with the admission results:

```bash
kubectl "${CH07_AS[@]}" auth can-i patch nodes/"$CH07_OTHER"
kubectl "${CH07_AS[@]}" get node "$CH07_OTHER"
```

On the 1.37 baseline, the Node authorizer allows Node patch operations and leaves the own-Node write restriction to admission, so `can-i patch` can return `yes` even though the dry-run patch is forbidden. Reading the other Node is denied by authorization. A name-based `kubectl patch node OTHER` can fail its preliminary GET at authorization before sending a patch; using `-f` above avoids confusing that failure with an admission decision. See [Node authorization](https://kubernetes.io/docs/reference/access-authn-authz/node/) and [NodeRestriction](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/#noderestriction).

These requests exercise authorization and admission for the impersonated identity. The administrator's credential authenticates the connection, so this does not prove the kubelet possesses a working client certificate. Certificate authentication is a separate check, as practiced in CH01. Keep both impersonated groups explicit; do not use `system:masters`.

**Reset:** no Node should have changed. As administrator, inspect both Nodes and confirm the probe labels were not stored. Remove only `work/CH07/own-node.yaml` and `work/CH07/other-node.yaml` when finished. If a dry-run flag was accidentally omitted, compare with the saved labels and restore only that task's change.
