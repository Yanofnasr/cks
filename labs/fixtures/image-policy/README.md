# ImagePolicyWebhook practice backend

Use this fixture for [SC09](../../supply-chain.md#sc09-imagepolicywebhook-integration). It supplies a small HTTPS backend so the exercise includes a real external admission decision, TLS configuration and outage test. Python 3, OpenSSL, curl and kubectl must already be installed.

The backend accepts Kubernetes `imagepolicy.k8s.io/v1alpha1` `ImageReview` requests, not `AdmissionReview` requests. Every supplied image must begin with `docker.io/` or `registry.k8s.io/`. Unqualified names and other registries are denied. User annotations never override the decision. This is a registry exercise, not signature verification, a vulnerability scanner or a complete image-reference parser. An allowed registry can contain untrusted images.

Run only on a **disposable, single-control-plane kubeadm VM**, with a current snapshot and working console access. The API server must use the host network to reach this loopback listener. The plugin applies cluster-wide, including system workloads; this fixture is deliberately unsuitable for shared clusters. Complete [API-server recovery practice](../../cluster-hardening.md) first. Use a fresh lab without SC06's CEL policy or other exercise policies that could explain a denial.

## Create separate lab certificates

Run from the repository root on the control-plane VM. Stop if `work/SC09` already exists; select or reset your own previous exercise directory explicitly. Keep this shell open for the later commands.

```bash
umask 077
mkdir -p work
mkdir -m 700 work/SC09
LAB_DIR="$PWD/work/SC09"

openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 2 \
  -subj '/CN=SC09 lab CA' \
  -addext 'basicConstraints=critical,CA:TRUE' \
  -addext 'keyUsage=critical,keyCertSign,cRLSign' \
  -keyout "$LAB_DIR/ca.key" -out "$LAB_DIR/ca.crt"

openssl req -new -newkey rsa:2048 -nodes -sha256 \
  -subj '/CN=SC09 loopback server' \
  -keyout "$LAB_DIR/server.key" -out "$LAB_DIR/server.csr"
cat > "$LAB_DIR/server.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:127.0.0.1
EOF
openssl x509 -req -sha256 -days 2 -in "$LAB_DIR/server.csr" \
  -CA "$LAB_DIR/ca.crt" -CAkey "$LAB_DIR/ca.key" -CAcreateserial \
  -extfile "$LAB_DIR/server.ext" -out "$LAB_DIR/server.crt"

openssl req -new -newkey rsa:2048 -nodes -sha256 \
  -subj '/CN=SC09 webhook client' \
  -keyout "$LAB_DIR/client.key" -out "$LAB_DIR/client.csr"
cat > "$LAB_DIR/client.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=clientAuth
EOF
openssl x509 -req -sha256 -days 2 -in "$LAB_DIR/client.csr" \
  -CA "$LAB_DIR/ca.crt" -CAkey "$LAB_DIR/ca.key" -CAcreateserial \
  -extfile "$LAB_DIR/client.ext" -out "$LAB_DIR/client.crt"

openssl verify -CAfile "$LAB_DIR/ca.crt" -purpose sslserver \
  -verify_ip 127.0.0.1 "$LAB_DIR/server.crt"
openssl verify -CAfile "$LAB_DIR/ca.crt" -purpose sslclient "$LAB_DIR/client.crt"
```

This CA is used only for this webhook. Never use or copy the Kubernetes cluster CA private key. Its client certificate is for the webhook connection and grants no Kubernetes API identity. Keep all keys under the private directory, out of Git, image builds and screenshots.

## Run and probe the backend

In a second terminal on the same VM, from the repository root:

```bash
python3 labs/fixtures/image-policy/webhook.py \
  --cert work/SC09/server.crt --key work/SC09/server.key \
  --client-ca work/SC09/ca.crt
```

Leave it running while configuring the API server. It binds only `127.0.0.1:8443`, requires TLS 1.2 or newer and a client certificate from the lab CA, and serves `POST /`. Bodies are limited to 64 KiB and stalled TLS/HTTP reads time out after three seconds. It handles requests sequentially for a small lab; it is not a production webhook service.

Back in the first terminal, send the actual ImageReview payloads:

```bash
curl --fail-with-body --cacert "$LAB_DIR/ca.crt" \
  --cert "$LAB_DIR/client.crt" --key "$LAB_DIR/client.key" \
  -H 'Content-Type: application/json' \
  --data-binary @labs/fixtures/image-policy/allowed-review.json \
  https://127.0.0.1:8443/

curl --fail-with-body --cacert "$LAB_DIR/ca.crt" \
  --cert "$LAB_DIR/client.crt" --key "$LAB_DIR/client.key" \
  -H 'Content-Type: application/json' \
  --data-binary @labs/fixtures/image-policy/denied-review.json \
  https://127.0.0.1:8443/

# Must fail TLS authentication, without bypassing server verification.
curl --cacert "$LAB_DIR/ca.crt" \
  -H 'Content-Type: application/json' \
  --data-binary @labs/fixtures/image-policy/allowed-review.json \
  https://127.0.0.1:8443/
```

Expect HTTP 200 with `status.allowed: true`, then HTTP 200 with `status.allowed: false`. A policy denial is a valid webhook response, so curl's exit code alone does not prove an allow. The third command must fail before any policy decision. A malformed review receives a 4xx response with `allowed: false`.

## Connect the API server

Inspect the existing static-Pod manifest, Kubernetes version, container UID, enabled/disabled admission plugins, `--admission-control-config-file`, `--runtime-config`, volumes and mounts. Confirm console recovery and a healthy `kubectl get --raw=/readyz` before proceeding. The following host paths must be unused by anything else. These file modes assume the default kubeadm API server runs as root; determine appropriate restricted access first if yours runs under another UID.

```bash
sudo cp -a /etc/kubernetes/manifests/kube-apiserver.yaml "$LAB_DIR/kube-apiserver.before.yaml"
sudo mkdir -m 700 /etc/kubernetes/cks-image-policy
sudo install -m 644 "$LAB_DIR/ca.crt" "$LAB_DIR/client.crt" /etc/kubernetes/cks-image-policy/
sudo install -m 600 "$LAB_DIR/client.key" /etc/kubernetes/cks-image-policy/
sudo install -m 600 labs/fixtures/image-policy/kubeconfig.yaml /etc/kubernetes/cks-image-policy/
cp labs/fixtures/image-policy/admission-config.yaml "$LAB_DIR/admission-config.yaml"
```

Keep backups and edited manifests **outside** `/etc/kubernetes/manifests`; the kubelet reads that directory. If there is an existing admission configuration, back it up too and merge the `ImagePolicyWebhook` plugin entry from the fixture into a working copy. Preserve every other plugin configuration and resolve any relative paths against the new location. Never replace existing admission configuration with this single-plugin example. Install the resulting combined file:

```bash
sudo install -m 600 "$LAB_DIR/admission-config.yaml" /etc/kubernetes/cks-image-policy/admission-config.yaml
sudo cp -a "$LAB_DIR/kube-apiserver.before.yaml" "$LAB_DIR/kube-apiserver.edited.yaml"
```

Edit only the working manifest. Add `ImagePolicyWebhook` to the existing `--enable-admission-plugins` list and ensure it is not explicitly disabled. Point `--admission-control-config-file` at `/etc/kubernetes/cks-image-policy/admission-config.yaml`. Merge `imagepolicy.k8s.io/v1alpha1=true` into `--runtime-config`, preserving existing settings. Do not add duplicate command flags. Keep the existing API-server image, other arguments, probes, security context, volumes and mounts.

Add this mount to the API-server container and this volume to the Pod, merging with their existing lists:

```yaml
# Under the API-server container's volumeMounts:
- name: cks-image-policy
  mountPath: /etc/kubernetes/cks-image-policy
  readOnly: true

# Under spec.volumes:
- name: cks-image-policy
  hostPath:
    path: /etc/kubernetes/cks-image-policy
    type: Directory
```

Only the CA public certificate, client certificate/key and configuration files belong in that mounted directory. The CA private key and webhook server private key remain outside it. Review the diff and check YAML structure with your available tooling. With the backend still running, stage the manifest outside the watched directory and rename it into place. Confirm the temporary host path below is unused before proceeding.

```bash
sudo diff -u "$LAB_DIR/kube-apiserver.before.yaml" "$LAB_DIR/kube-apiserver.edited.yaml"
sudo install -m 600 "$LAB_DIR/kube-apiserver.edited.yaml" /etc/kubernetes/kube-apiserver.sc09.yaml
sudo mv /etc/kubernetes/kube-apiserver.sc09.yaml /etc/kubernetes/manifests/kube-apiserver.yaml
kubectl get --raw=/readyz
```

Wait for readiness after the restart and inspect kubelet/container logs if startup fails. Restore the saved manifest from the console if necessary; a failed API-server restart is not a policy test.

The fixture sets `defaultAllow: false` and disables both caches with `allowTTL: -1` and `denyTTL: -1`. In the referenced Kubernetes implementation, **zero selects default TTLs**, not disabled caches. Confirm these semantics against your installed version. The cache key contains the images, namespace and forwarded image-policy annotations, not the Pod name. With caching enabled in a separate variation, use a new `lab.image-policy.k8s.io/probe` value and wait past the configured TTL before testing an outage.

## Prove Kubernetes admission behavior

Use a fresh namespace and an explicit allowed image. These probes pass restricted Pod Security requirements and disable token mounting. Check for other admission policies first and keep them out of this exercise's namespace. The external image policy itself is cluster-wide.

```bash
kubectl create namespace cks-image-policy
cat > "$LAB_DIR/allowed-pod.yaml" <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: image-policy-probe
  namespace: cks-image-policy
spec:
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: main
      image: docker.io/library/busybox:1.37
      command: ["sleep", "3600"]
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: ["ALL"]
EOF
kubectl create --dry-run=server -f "$LAB_DIR/allowed-pod.yaml"
```

1. The allowed Pod must pass server-side dry run. Copy the file, change only the main image to `example.invalid/lab/image:v1`, and confirm rejection contains `SC09: registry must be docker.io or registry.k8s.io`.
2. In another copy keep the allowed main container and add an init container with the prohibited image, `command: ["true"]` and the same container security context. Its dry run must be rejected with the same backend reason. Replace only that init image with `docker.io/library/busybox:1.37` and confirm admission succeeds.
3. Add `lab.image-policy.k8s.io/allow: "true"` under metadata annotations to a prohibited-image probe. It must still be rejected.
4. Create only the allowed Pod, wait for it to run, then test an actual ephemeral-container subresource update. Existing allowed images must not hide a forbidden ephemeral image.

```bash
kubectl create -f "$LAB_DIR/allowed-pod.yaml"
kubectl -n cks-image-policy wait pod/image-policy-probe --for=condition=Ready --timeout=120s
kubectl -n cks-image-policy get pod image-policy-probe -o json > "$LAB_DIR/live-pod.json"
python3 - "$LAB_DIR" <<'PY'
import json
from pathlib import Path
import sys

directory = Path(sys.argv[1])
pod = json.loads((directory / "live-pod.json").read_text())
for name, image in [("allowed", "docker.io/library/busybox:1.37"),
                    ("denied", "example.invalid/lab/image:v1")]:
    pod["spec"]["ephemeralContainers"] = [{
        "name": "inspect", "image": image, "command": ["true"],
        "securityContext": {"runAsNonRoot": True, "runAsUser": 1000,
                            "allowPrivilegeEscalation": False,
                            "capabilities": {"drop": ["ALL"]},
                            "seccompProfile": {"type": "RuntimeDefault"}},
    }]
    (directory / f"ephemeral-{name}.json").write_text(json.dumps(pod))
PY
kubectl replace --raw '/api/v1/namespaces/cks-image-policy/pods/image-policy-probe/ephemeralcontainers?dryRun=All' \
  -f "$LAB_DIR/ephemeral-allowed.json"
kubectl replace --raw '/api/v1/namespaces/cks-image-policy/pods/image-policy-probe/ephemeralcontainers?dryRun=All' \
  -f "$LAB_DIR/ephemeral-denied.json"
```

The first subresource request must succeed and the second must carry the backend's denial. Neither dry run starts an ephemeral container or pulls the prohibited image. If the running Pod changes meanwhile, retrieve its current resource version and rebuild both probe files. An authorization, conflict, schema or PSA error does not prove this webhook works. Regular and init containers are reviewed on normal Pod requests; ephemeral containers use their subresource. Image-backed volumes are outside this plugin's coverage.

For the outage test, first delete only `image-policy-probe` so its name is available again. Confirm the allowed Pod's dry run still passes. Stop the backend with Ctrl-C in its terminal, repeat the **same allowed-image** dry run, and require a webhook connection failure and denied admission. Caches are disabled, so a previous approval cannot mask this failure. The API server can retry, so allow time for the response. Restart the backend immediately and prove that the same request succeeds again. Record both the policy denial and the unavailable-backend denial separately; do not enable `defaultAllow` to make the test pass.

## Reset

With the backend running, restore the original API-server manifest and its original admission-configuration reference. Restore any original configuration you deliberately edited first:

```bash
sudo cp -a "$LAB_DIR/kube-apiserver.before.yaml" /etc/kubernetes/kube-apiserver.sc09.yaml
sudo mv /etc/kubernetes/kube-apiserver.sc09.yaml /etc/kubernetes/manifests/kube-apiserver.yaml
kubectl get --raw=/readyz
```

Wait for readiness and repeat a known working request. **Remove the API-server dependency before stopping the backend.** Then stop the backend, delete the drill-owned namespace, and remove only `/etc/kubernetes/cks-image-policy` and the lab key material you created. Retain non-secret results if useful. Never remove cluster PKI, other admission configuration, or all namespaces. If recovery fails, use the VM snapshot and console.

## Sources and local checks

Practice topic: [Killer Shell's ImagePolicyWebhook scenario](https://killercoda.com/killer-shell-cks/scenario/image-policy-webhook-setup), linked from its [course environment](https://github.com/killer-sh/cks-course-environment). This backend and its fixtures are original workbook code; no upstream certificates or installer are needed.

Primary references: [Kubernetes ImagePolicyWebhook configuration and protocol](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/#imagepolicywebhook), [versioned cache normalization](https://github.com/kubernetes/kubernetes/blob/v1.37.1/plugin/pkg/admission/imagepolicy/config.go), and [versioned request construction and cache key](https://github.com/kubernetes/kubernetes/blob/v1.37.1/plugin/pkg/admission/imagepolicy/admission.go).

From the repository root, `python3 -m unittest discover -s tests -p test_image_policy.py -v` checks decisions, malformed requests, client/server certificate trust, body limits and stalled reads. Its TLS tests generate temporary certificates and open an ephemeral loopback port. These checks do not replace the disposable-VM admission and recovery tests above.
