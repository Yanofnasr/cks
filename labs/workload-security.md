# Workload security

Use a disposable cluster and the [lab environment guide](../preparation/LAB-SAFETY.md). Run commands from the repository root. Keep edited manifests in `work/`; leave the starter fixtures unchanged. Record measured results in the [progress log](../preparation/PROGRESS.md).

## MW01 Pod Security Admission

**Environment:** Kubernetes with Pod Security Admission enabled. Start with a fresh shared lab baseline:

```bash
kubectl apply -f labs/fixtures/workloads.yaml
mkdir -p work
cp labs/fixtures/workload.yaml work/psa-probe.yaml
```

Change the copied Pod's name to `psa-probe`. In this owned namespace, first set the enforcement level to `baseline` and confirm the starter passes a server-side dry run. Do not deploy the probe yet.

**Task:** enforce the Restricted standard in `cks-lab`, pinning its version to the lab's Kubernetes minor version. Set audit and warn labels deliberately too. Keep `cks-other` unaffected. Modify a second copy of the probe until it complies, without using privileged mode, host namespaces or host mounts.

**Prove it:**

1. `kubectl create --dry-run=server -f work/psa-probe.yaml` rejects the original with a Pod Security explanation, not an existing-name or schema error.
2. The compliant copy is accepted by the same server-side check and can run.
3. The original is still accepted by a dry run targeting `cks-other` after changing its manifest namespace.
4. Existing Pods are not retroactively evicted just because the namespace policy changed. Verify new admissions separately.

**Reset:** delete the probe you actually created and remove only the Pod Security labels you added, or restore the shared baseline as described in the environment guide. Preserve any original labels if this was not a fresh namespace.

## MW02 Workload hardening

**Environment:** ordinary disposable cluster. Start from a fresh baseline without MW01's Restricted enforcement, then apply the intentionally incomplete [workload starter](fixtures/workload.yaml):

```bash
kubectl apply -f labs/fixtures/workload.yaml
kubectl -n cks-lab wait --for=condition=Ready pod/demo --timeout=90s
kubectl -n cks-lab exec demo -- id
mkdir -p work
cp labs/fixtures/workload.yaml work/demo.yaml
```

**Task:** keep the HTTP service working on port 8080 while running as UID/GID 1000. Set `runAsNonRoot`, `allowPrivilegeEscalation: false`, drop all Linux capabilities, use `RuntimeDefault` seccomp, disable automatic ServiceAccount token mounting and make the root filesystem read-only. Retain the intended writable `/tmp` volume; use an appropriate `fsGroup` for its ownership. A read-only root filesystem is a runtime setting, not a Dockerfile permission change.

Pod security fields usually require replacement. Delete only `cks-lab/demo`, wait for deletion, then create your edited Pod. Do not force-delete unrelated workloads.

**Prove it:** the Pod becomes Ready; `id` reports the expected identity; `/proc/1/status` shows no effective capabilities and `NoNewPrivs: 1`; the root mount is read-only; a write to `/tmp` succeeds. The existing healthy `client` can still fetch the Pod's IP on port 8080. A root-filesystem write must fail, and the usual ServiceAccount token path must be absent.

Run the independent verifier before cleanup, using the lab context selected during setup:

```bash
python3 scripts/lab.py --context "$LAB_CONTEXT" verify MW02
```

Keep this proof from the deliberately incomplete starter as the hardening prerequisite for CAP01. The capstone begins with already-hardened shared witnesses and checks that their controls survive the combined changes.

**Reset:** delete `cks-lab/demo`. Keep your answer in `work/demo.yaml` for RT03, or reapply the original starter for a fresh attempt.

## MW03 Secrets and encryption rotation

**Environment:** the first task needs an ordinary cluster. Storage-encryption work needs a disposable kubeadm control plane, root access, an etcd client compatible with that installation, and a VM snapshot. Use dummy values throughout.

**Start:** apply the shared baseline, then create a Secret owned by this drill:

```bash
kubectl -n cks-lab create secret generic training-secret \
  --from-literal=message=practice-only
```

**Task A:** mount only its `message` key read-only into a new non-root Pod named `secret-reader`. Do not place the value directly in its manifest. Keep token automount disabled. Separately create a ServiceAccount named `secret-reader` and a namespaced Role/RoleBinding named `training-secret-reader` permitting only `get` on `training-secret`; test authorization through impersonation. Mounting a Secret through a Pod does not require granting that Pod's ServiceAccount API access to Secrets.

**Prove A:** the mounted dummy value is correct and not writable; the named `get` is allowed; list, unrelated Secret access and another namespace are denied. Check the exact identity, verb, namespace and resource name in each authorization query.

**Task B:** inspect the active API-server manifest and any existing encryption configuration. Save protected backups outside the watched manifests directory. If encryption is absent, generate a fresh lab-only key and mount the configuration into every API server that serves this cluster. First keep `identity` as the write provider and add the encryption provider/key afterward so every server can decrypt the new format before any server writes it. Activate and verify that configuration everywhere, then move encryption first for writes on every server. Keep the appropriate existing decrypt providers, including identity when plaintext records still exist. Never replace existing keys with freshly generated values under the same name.

Create another dummy Secret after configuration is active. Inspect its raw etcd record using the endpoints and TLS credentials from this control plane, without copying credentials into the repository. Rewrite only the drill-owned pre-existing Secret through the API and inspect its stored representation too.

For a standard kubeadm control plane with local etcd, first verify the endpoint and certificate paths against the active API-server arguments. Then inspect **only the owned dummy Secret**, before and after enabling encryption:

```bash
sudo etcdctl --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/apiserver-etcd-client.crt \
  --key=/etc/kubernetes/pki/apiserver-etcd-client.key \
  get /registry/secrets/cks-lab/training-secret --print-value-only | hexdump -C
```

These paths are an example for that topology, not values to guess on another installation. Use the node's existing client credentials in place; do not copy private keys into `work/`. Once encrypted writes are enabled consistently, create the fresh control and rewrite the old dummy record:

```bash
kubectl -n cks-lab create secret generic training-secret-next \
  --from-literal=message=practice-next
kubectl -n cks-lab get secret training-secret -o json | kubectl replace -f -
```

Read both exact etcd keys. For an AES-CBC lab provider, encrypted records begin with `k8s:enc:aescbc:v1:<key-name>:`; other providers have their own prefix. Do not confuse the serialized plaintext record, API base64 encoding, or an empty/failed read with encrypted data. Keep the plaintext-before, encrypted-after and still-readable-through-API observations together.

**Task C:** practice rotation with distinct key names. Retain the old key first for writes and add the new key as a non-primary decryption key. Activate and verify that configuration on **every API server** before promoting the new key to first for writes. Activate the new write order everywhere, rewrite the drill-owned Secrets and verify their new stored representation. Do not remove the old key while any retained data or required backup still needs it. A real cluster requires a complete resource migration, beyond this small drill.

**Prove B/C:** API reads return the original dummy values before and after rotation; fresh and rewritten etcd records use encryption and the expected key identity; API-server health remains good. Base64 data in an API Secret is not proof of encryption at rest. As a negative control, the authorized drill ServiceAccount still cannot list all Secrets after encryption is enabled.

**Reset:** delete only the drill-owned Pods, Role, RoleBinding, ServiceAccount and Secrets. Restore the entire disposable VM snapshot for encryption work. Do not restore an old configuration file over data that now requires a newer key.

Reference: [encrypt data at rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/).

## MW04 Runtime isolation

**Environment:** disposable node VMs with a working, compatible sandbox runtime such as gVisor already installed. A RuntimeClass object alone does not install a runtime. If the handler is unavailable, record the prerequisite as pending.

**Start:** snapshot the node, inspect its container runtime version and existing configuration, and confirm the selected sandbox handler works. Preserve all unrelated runtime configuration. Copy the workload starter to `work/sandbox.yaml`, name the Pod `sandbox`, and harden it as in MW02.

**Task:** create a RuntimeClass named `cks-sandbox` using the actual configured handler. If only one node supports it, constrain scheduling to that node using the RuntimeClass scheduling settings or the Pod's node selector. Assign the RuntimeClass to the copied workload.

**Prove it:** the Pod is Running and Ready, serves HTTP, and its sandbox/runtime metadata confirms the selected handler. Compare with an ordinary-runtime witness on the same node. Create a second probe that references a nonexistent RuntimeClass and verify that it cannot run; do not interpret Pending as successful isolation.

**Reset:** delete the two drill Pods and `cks-sandbox`. Restore the node snapshot if you changed runtime configuration. Do not uninstall a runtime used by another workload.

References: [RuntimeClass](https://kubernetes.io/docs/concepts/containers/runtime-class/), [gVisor containerd guide](https://gvisor.dev/docs/user_guide/containerd/quick_start/).

## MW05 Pod-to-pod encryption

**Environment:** a working **sidecar-mode** Istio installation on a disposable cluster, with a compatible `istioctl`. For the restricted-compatible application fixtures, use functioning Istio CNI traffic redirection. Do not remove the fixture's security settings or grant its application `NET_ADMIN` to work around a failed injection/init step. An ambient-only installation or an unconfigured RuntimeClass/CRD is not this exercise's environment.

**Preflight:** record the Istio version, available injection revision/tag, namespace labels and existing mesh policies:

```bash
istioctl version
kubectl get namespace cks-lab cks-other --show-labels
kubectl get peerauthentication,authorizationpolicy -A
```

Use a fresh shared baseline without restrictive NetworkPolicies. A global or namespace STRICT policy, authorization rule, ambient enrollment or explicit client TLS override can invalidate the starting comparison. Resolve that by choosing the appropriate disposable environment, not weakening someone else's mesh policy. Confirm `mw05-api-strict` is unused in `cks-lab`.

**Start:** enable the installation's actual sidecar injector for `cks-lab`: use `istio-injection=enabled` only when a default injector exists, or `istio.io/rev=<installed-revision-or-tag>` for a revisioned installation. Use one mechanism, record the label you add, and leave `cks-other` unmeshed. Recreate only the owned API and client Pods:

```bash
kubectl delete pod -n cks-lab api client --wait=true
kubectl apply -f labs/fixtures/workloads.yaml
kubectl wait -n cks-lab --for=condition=Ready pod/api pod/client --timeout=180s
istioctl proxy-status
```

Inspect both Pods for the running `istio-proxy` container, which may be a restartable init container in native-sidecar mode. Verify the CNI's traffic-redirection/validation step succeeded and both proxies have synchronized configuration. For example, inspect the API proxy's listeners using `istioctl proxy-config listeners api -n cks-lab`. Sidecar presence by itself is not proof that application traffic is captured. Keep the application UID distinct from the proxy UID.

Both requests must succeed **before** the exercise's policy is installed:

```bash
kubectl -n cks-lab exec client -c client -- wget -qO- -T 3 http://api.cks-lab.svc:8080/
kubectl -n cks-other exec client -c client -- wget -qO- -T 3 http://api.cks-lab.svc:8080/
```

**Task:** create `PeerAuthentication` named `mw05-api-strict` in `cks-lab`, with selector `app=api` and `mtls.mode: STRICT`. Keep the legitimate meshed client's access working. The [worked policy](../solutions/istio-strict.yaml) is available after attempting your own manifest; it is limited to this namespace and workload selector.

**Prove it:** repeat the two requests. The meshed client succeeds and the healthy plain client fails. Correlate the successful connection with workload proxy configuration and mesh telemetry showing mutual TLS; the negative request alone does not prove encryption. Keep both clients and the destination Ready and rule out unrelated network/authorization failures. The plain client's request to its own `cks-other/api:8080` must remain successful, demonstrating unaffected traffic outside the policy scope.

**Cilium variation:** with a real Cilium installation, distinguish mutual authentication from traffic encryption. Enable and validate the required encryption mechanism on the nodes, then enforce the requested identity policy and test the actual traffic path. Authentication policy presence is not proof that application traffic is encrypted.

**Reset:** delete only `mw05-api-strict` and the injection label added for this drill, then recreate the owned `cks-lab/api` and `cks-lab/client` from the original fixture. Verify they have no proxy and the starting traffic comparison succeeds again. Restore a dedicated cluster snapshot if mesh configuration was changed. Do not purge the cluster's mesh as a per-exercise cleanup step.

References: [Istio mutual TLS](https://istio.io/latest/docs/tasks/security/authentication/mtls-migration/), [Istio CNI](https://istio.io/latest/docs/setup/additional-setup/cni/), [Cilium authentication](https://docs.cilium.io/en/stable/network/servicemesh/mutual-authentication/mutual-authentication/), [Cilium encryption](https://docs.cilium.io/en/stable/security/network/encryption/).

## MW06 Container namespaces

**Environment:** an ordinary Linux container runtime in a disposable cluster. Start from the fresh shared baseline with `cks-lab` available, no mesh injection, and no exercise policies affecting these Pods. A sandbox runtime can virtualize `/proc` differently and should be a separate MW04 comparison. Confirm that neither `namespace-pair` nor `namespace-shared` already exists in `cks-lab` before using those names.

The [two-container fixture](fixtures/namespace-pair.yaml) runs an HTTP server and a sleeping observer as UID 1000. Each has a separate writable `/tmp` volume. It uses no host namespaces, privileged containers, host mounts or extra capabilities.

```bash
kubectl -n cks-lab get pod namespace-pair namespace-shared --ignore-not-found
```

Proceed only if the command succeeds without returning Pods, then create the first witness:

```bash
mkdir -p work/MW06
kubectl create -f labs/fixtures/namespace-pair.yaml
kubectl -n cks-lab wait --for=condition=Ready pod/namespace-pair --timeout=120s
kubectl -n cks-lab exec namespace-pair -c observer -- wget -qO- -T 3 http://127.0.0.1:8080/
kubectl -n cks-lab exec namespace-pair -c server -- readlink /proc/self/ns/net
kubectl -n cks-lab exec namespace-pair -c observer -- readlink /proc/self/ns/net
kubectl -n cks-lab exec namespace-pair -c server -- readlink /proc/self/ns/pid
kubectl -n cks-lab exec namespace-pair -c observer -- readlink /proc/self/ns/pid
kubectl -n cks-lab exec namespace-pair -c server -- ps
kubectl -n cks-lab exec namespace-pair -c observer -- ps
```

**Prove the default:** both containers report the same network namespace identifier, and the observer reaches the server through localhost. Their PID namespace identifiers differ; the observer's process listing does not show the server's `httpd`. Check the actual identifiers rather than expecting a particular numeric value.

Create a file in only the server's writable volume, then check the observer's independent path:

```bash
kubectl -n cks-lab exec namespace-pair -c server -- sh -c 'printf "server-only\n" > /tmp/mw06-marker; cat /tmp/mw06-marker'
kubectl -n cks-lab exec namespace-pair -c observer -- sh -c 'test ! -e /tmp/mw06-marker && echo "marker absent from observer /tmp"'
```

Sharing the Pod network does not share the containers' root filesystems or these separate `emptyDir` volumes. Explicitly mounting the same volume into both containers would share that volume.

**Task:** copy the fixture to `work/MW06/shared.yaml`, change its Pod name to `namespace-shared`, and set `spec.shareProcessNamespace: true`. Keep all other fields, including the distinct volumes and security settings. Create the new Pod while leaving `namespace-pair` unchanged; do not try to patch this immutable setting on a running Pod.

```bash
cp labs/fixtures/namespace-pair.yaml work/MW06/shared.yaml
# Edit the copied Pod name and spec.shareProcessNamespace before creating it.
kubectl create -f work/MW06/shared.yaml
kubectl -n cks-lab wait --for=condition=Ready pod/namespace-shared --timeout=120s
kubectl -n cks-lab exec namespace-shared -c server -- readlink /proc/self/ns/pid
kubectl -n cks-lab exec namespace-shared -c observer -- readlink /proc/self/ns/pid
kubectl -n cks-lab exec namespace-shared -c observer -- ps
kubectl -n cks-lab exec namespace-shared -c observer -- wget -qO- -T 3 http://127.0.0.1:8080/
kubectl -n cks-lab exec namespace-shared -c server -- sh -c 'printf "shared-pid-only\n" > /tmp/mw06-marker; cat /tmp/mw06-marker'
kubectl -n cks-lab exec namespace-shared -c observer -- sh -c 'test ! -e /tmp/mw06-marker && echo "marker absent from observer /tmp"'
```

**Prove the change:** the new Pod's two containers report the same PID namespace identifier, the observer sees `httpd` as well as its own sleeper, and localhost still serves HTTP. The application process is no longer necessarily PID 1. The observer's `/tmp` still has no marker. Repeat the original Pod's PID and process checks to show that its isolation did not change.

Process sharing exposes process metadata and can expose another container's filesystem through `/proc/<pid>/root`, subject to Linux access controls. Separate mount paths do not establish a confidentiality boundary between containers sharing a process namespace. Do not add `SYS_PTRACE` or weaken the fixture to force inspection. Explain why a Pod is a shared trust boundary and how this differs from `hostPID` or `hostNetwork`.

**Optional engine repeat:** on a disposable Linux host with Docker or Podman already installed, compare two ordinary standalone containers. Set `ENGINE=docker` or `ENGINE=podman`; use an isolated lab engine, not a shared or remote production daemon. Confirm both `mw06-a` and `mw06-b` are unused with `$ENGINE ps -a --filter name=mw06`. The names must belong to this drill before cleanup.

```bash
ENGINE=podman
for name in mw06-a mw06-b; do
  "$ENGINE" run -d --name "$name" --network none --user 1000:1000 \
    --cap-drop ALL --security-opt no-new-privileges --read-only \
    --tmpfs /tmp:rw,nosuid,nodev,noexec,mode=1777 \
    docker.io/library/busybox:1.37 sleep 86400
done
for name in mw06-a mw06-b; do
  "$ENGINE" exec "$name" readlink /proc/self/ns/net
  "$ENGINE" exec "$name" readlink /proc/self/ns/pid
done
"$ENGINE" rm -f mw06-a mw06-b
```

The two standalone containers should have different network and PID namespace identifiers. `--network none` still supplies each container's own loopback interface. This comparison does not make either container share the host's namespaces.

**Reset:** delete only `cks-lab/namespace-pair` and `cks-lab/namespace-shared`. Delete the optional engine containers only if this drill created them. Keep the shared namespace and other exercises intact.

Reference: [share a process namespace between containers](https://kubernetes.io/docs/tasks/configure-pod-container/share-process-namespace/).
