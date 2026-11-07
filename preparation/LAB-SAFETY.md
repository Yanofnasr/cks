# Lab setup

Use a disposable cluster you own. The namespace fixtures below are enough to start ordinary Kubernetes drills. Host and control-plane tasks need dedicated VMs with snapshots and console/SSH recovery access.

## Environments

| Level | What you need | Suitable work |
|---|---|---|
| Local | Private working directory, shell and named tools | Binary checks, audit-log reading, Dockerfile edits, image/SBOM work |
| Cluster | Healthy Kubernetes 1.37 cluster, kubectl, CNI that enforces NetworkPolicy | Networking, RBAC, PSA, Secrets, security contexts and CEL policies |
| Nodes | Disposable Linux control plane and worker, kubeadm/containerd, root access and snapshots | API/kubelet configuration, upgrades, audit mounts, AppArmor, seccomp and runtime handlers |
| Add-ons | Actual working Ingress, Falco, mesh or sandbox components required by the drill | Component-specific enforcement and investigation |

A manifest or CRD alone does not establish a working controller. Check the named prerequisite before starting. Use current official installation instructions for the chosen Kubernetes/runtime combination. Keep AppArmor enabled on nodes used for its drill.

Command examples assume a Linux shell with standard GNU utilities; node commands require the stated disposable Linux VM. On macOS or Windows, use a suitable Linux VM/terminal or adapt local-only commands such as `sha256sum` deliberately. Python 3.11+ is needed only for repository checks. Each build, scanner, mesh, firewall and kernel drill names its additional tools.

Pods use the cluster-provided DNS search configuration. The examples use names such as `api.cks-lab.svc`, avoiding a fixed cluster-domain suffix. Inspect the client's `/etc/resolv.conf` and use the actual full domain if its DNS policy/search configuration differs. Keep namespaces, label selectors, CNI enforcement, IP family and image architecture consistent with the task.

## Select the cluster deliberately

Run commands from this repository root. Create a private working directory and put a kubeconfig containing only the lab identity at `work/kubeconfig`:

```bash
umask 077
mkdir -p work
export KUBECONFIG="$PWD/work/kubeconfig"
kubectl config current-context
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'
kubectl get nodes -o wide
kubectl version
```

Populate the kubeconfig before running these commands. Confirm its endpoint and node names belong to the disposable environment. Keep generated keys, Secret values, scans and edited manifests in `work/`, which Git ignores. A lab kubeconfig does not protect the local machine from node-level shell commands: check which host your terminal is on.

## Shared starting state

The shared fixtures own **`cks-lab` and `cks-other`**. If either namespace already contains unrelated work, use a fresh cluster. CS06 separately creates `cks-tiers` and `cks-data`. Follow CS06's preflight and cleanup for its extra namespaces. Admission policies/bindings, CSRs and RuntimeClasses are explicitly introduced only by their corresponding drills.

```bash
kubectl apply -f labs/fixtures/workloads.yaml
kubectl wait -n cks-lab --for=condition=Ready pod --all --timeout=120s
kubectl wait -n cks-other --for=condition=Ready pod --all --timeout=120s
```

| Namespace | Workloads | Purpose |
|---|---|---|
| `cks-lab` | `api`, `client`, `intruder` | HTTP service, permitted caller and forbidden caller |
| `cks-other` | `api`, `client` | Cross-namespace positive/negative witnesses |

Both Services are named `api` and listen on **8080**. Server Pods have `app=api`; permitted clients have `role=client`; the intruder has `role=intruder`. Images are explicitly named `docker.io/library/busybox:1.37`. Tags make initial setup convenient; pin the digest in SC03 when practicing reproducibility.

Before adding policy, prove connectivity from each witness:

```bash
kubectl exec -n cks-lab client -- wget -qO- -T 3 http://api.cks-lab.svc:8080
kubectl exec -n cks-lab intruder -- wget -qO- -T 3 http://api.cks-lab.svc:8080
kubectl exec -n cks-other client -- wget -qO- -T 3 http://api.cks-lab.svc:8080
kubectl exec -n cks-lab client -- wget -qO- -T 3 http://api.cks-other.svc:8080
```

All four should succeed initially. The clients sleep for 24 hours; recreate the baseline for a later session. Diagnose image pulls, application readiness and DNS before treating a failed request as evidence of a policy boundary.

## Working with fixtures

| File | Use |
|---|---|
| [workloads.yaml](../labs/fixtures/workloads.yaml) | Small, restricted-compatible network witnesses |
| [workload.yaml](../labs/fixtures/workload.yaml) | Deliberately unhardened `demo` Pod for MW02/RT03; copy before editing |
| [image/Dockerfile](../labs/fixtures/image/Dockerfile) | Deliberately root-running HTTP image for SC01 |
| [seccomp-deny-chmod.json](../labs/fixtures/seccomp-deny-chmod.json) | SH04 demonstration, permits other syscalls and rejects the chmod family |
| [apparmor-deny-write](../labs/fixtures/apparmor-deny-write) | SH03 demonstration, permits other operations and denies writing `/tmp/blocked.txt` |
| [registry-policy.yaml](../labs/fixtures/registry-policy.yaml) | SC06 allowlist, applies only to namespaces labeled `cks-practice=admission` |
| [audit-policy.yaml](../labs/fixtures/audit-policy.yaml) | RT02 Metadata policy that avoids request/response Secret bodies |
| [audit-events.jsonl](../labs/fixtures/audit-events.jsonl) | Four synthetic events for local investigation, never evidence of a real incident |
| [three-tier.yaml](../labs/fixtures/three-tier.yaml) | CS06 cross-namespace traffic witnesses, with scoped [policy reference](../solutions/three-tier-policy.yaml) |

The AppArmor and seccomp demonstrations isolate one behavior; they are not general production profiles. No profile becomes effective until it is installed on the selected node and a workload actually uses it.

The [static-analysis directory](../labs/fixtures/static-analysis/README.md) contains deliberately flawed files for offline inspection only. Do not recursively apply or build the whole fixtures directory. Use only the specific manifest or build context named by a drill. Worked answers live separately under [solutions](../solutions/README.md).

## Reset and recovery

For a fresh namespaced attempt, finish each drill's separately named cluster/node cleanup, then remove only the resources owned here. This deletes your practice objects and edits in the two namespaces:

```bash
kubectl delete -f labs/fixtures/registry-policy.yaml --ignore-not-found
kubectl delete namespace cks-lab cks-other --ignore-not-found --wait=true
kubectl apply -f labs/fixtures/workloads.yaml
kubectl wait -n cks-lab --for=condition=Ready pod --all --timeout=120s
kubectl wait -n cks-other --for=condition=Ready pod --all --timeout=120s
```

Deleting namespaces does not restore node files, encryption keys, mesh installations, CSRs, RuntimeClasses or other cluster-scoped objects. Each corresponding drill names its cleanup. Use a consistent VM snapshot for host/control-plane recovery when needed. Keep static-Pod backups outside `/etc/kubernetes/manifests` and preserve the current API-server image and unrelated flags.

The shared reset does not delete CS06's extra namespaces. Follow that drill's scoped cleanup before another attempt.

For encryption changes, retain old decryption keys until data has been rewritten and verified under the replacement key. Restoring only an old configuration can strand data encrypted with a newer key. Do not delete a system executable merely because it owns a listening port; stop the specific task-owned service instead.
