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
kubectl auth can-i list pods -n cks-lab \
  --as=system:serviceaccount:cks-lab:ch02-client
kubectl auth can-i get secrets -n cks-lab \
  --as=system:serviceaccount:cks-lab:ch02-client
kubectl auth can-i list pods -n cks-other \
  --as=system:serviceaccount:cks-lab:ch02-client
```

The results must be `yes`, `no`, `no`, while the Pod still has no automatically mounted token. In a separate Pod variant, use an explicit projected ServiceAccount token with a short lifetime and intended audience; observe the volume specification without logging its contents. An explicit projection is separate from automatic mounting.

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

**Extension:** with a dummy Secret only, explain and demonstrate how adding `create pods` can allow an identity to create a Pod that mounts a namespace Secret even when direct Secret reads are forbidden. Grant that permission only in a temporary exercise Role, create the test workload as that identity, and remove the extra permission afterward. Namespace workload creation is a significant authority boundary.

**Reset:** remove any remaining `ch02-binding-author` RoleBinding and Role and the unbound `ch02-secret-probe` Role. Delete the exercise Pods, `ch02-pod-reader` RoleBinding and Role, ServiceAccount and dummy Secret, including any temporary Role from the workload-creation extension. Confirm no exercise binding remains and do not change the `default` ServiceAccount or another task's identity.

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
