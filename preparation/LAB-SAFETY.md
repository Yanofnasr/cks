# Lab setup

Use a disposable cluster you own. First follow [environment creation](ENVIRONMENTS.md), which sets `KUBECONFIG` and `LAB_CONTEXT`; then prepare the baseline below. Host and control-plane tasks need dedicated VMs with snapshots and console/SSH recovery access. Check the [compatibility map](COMPATIBILITY.md) before starting a drill.

## Environments

| Level | What you need | Suitable work |
|---|---|---|
| Local | Private working directory, shell and named tools | Binary checks, audit-log reading, Dockerfile edits, image/SBOM work |
| Cluster | Healthy Kubernetes 1.37 cluster, kubectl, CNI that enforces NetworkPolicy | Networking, RBAC, PSA, Secrets, security contexts and CEL policies |
| Nodes | Disposable Linux control plane and worker, kubeadm/containerd, root access and snapshots | API/kubelet configuration, upgrades, audit mounts, AppArmor, seccomp and runtime handlers |
| Add-ons | Actual working Ingress, Falco, mesh or sandbox components required by the drill | Component-specific enforcement and investigation |

A manifest or CRD alone does not establish a working controller. Check the named prerequisite before starting. Use current official installation instructions for the chosen Kubernetes/runtime combination. Keep AppArmor enabled on nodes used for its drill.

Command examples assume a Linux shell with standard GNU utilities; node commands require the stated disposable Linux VM. On macOS or Windows, use a suitable Linux VM/terminal or adapt local-only commands such as `sha256sum` deliberately. Python 3.11+ is needed for preflight, the independent verifier and repository checks. Each build, scanner, mesh, firewall and kernel drill names its additional tools.

Pods use the cluster-provided DNS search configuration. The examples use names such as `api.cks-lab.svc`, avoiding a fixed cluster-domain suffix. Inspect the client's `/etc/resolv.conf` and use the actual full domain if its DNS policy/search configuration differs. Keep namespaces, label selectors, CNI enforcement, IP family and image architecture consistent with the task.

## Select the cluster deliberately

Run commands from this repository root. The environment guide creates a private working directory and kubeconfig containing only the lab identity. In a new terminal, export `KUBECONFIG` with the exact filename you chose and `LAB_CONTEXT` with that environment's context. The checks below preserve those selections, including an alternate kubeconfig filename:

```bash
umask 077
mkdir -p work
: "${KUBECONFIG:?Export the exact lab kubeconfig filename chosen during setup}"
: "${LAB_CONTEXT:?Export the context chosen during setup}"
test -f "$KUBECONFIG"
kubectl config use-context "$LAB_CONTEXT"
kubectl config current-context
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'
kubectl get nodes -o wide
kubectl version
python3 scripts/lab.py --context "$LAB_CONTEXT" preflight
```

Populate the kubeconfig and set `LAB_CONTEXT` before running these commands. Confirm its endpoint and node names belong to the disposable environment. Preflight reads metadata and permissions; it cannot prove policy enforcement or every host capability. Resolve BLOCKED results before dependent work. Keep generated keys, Secret values, scans and edited manifests in `work/`, which Git ignores. A lab kubeconfig does not protect the local machine from node-level shell commands: check which host your terminal is on.

Every `verify` command checks the cluster identity before running a drill. For a cluster created with `scripts/environment.py`, the live `kube-system` UID and ownership marker must match its saved environment record. Keep `work/environments/<name>/environment.json` with its kubeconfig until teardown. No extra verification flag is needed for this route.

For manual kind, cloud or other externally created labs, first confirm the endpoint and nodes against your own provisioning records. Copy the `kube-system` UID reported by preflight once into a session variable, then append the acknowledgement to each `verify` command shown in this workbook. After solving CH02, for example:

```bash
export LAB_CLUSTER_UID='replace-with-the-confirmed-lab-cluster-uid'
python3 scripts/lab.py --context "$LAB_CONTEXT" verify CH02 \
  --external-lab-uid "$LAB_CLUSTER_UID"
```

Use the same recorded UID throughout that session. A recreated cluster requires a fresh identity check. The flag acknowledges your choice of lab; it cannot establish that the cluster is disposable. It does not override a mismatched or damaged local ownership record. If verification reports an identity mismatch, check the selected kubeconfig and saved environment before retrying.

## Shared starting state

The shared fixtures own **`cks-lab` and `cks-other`**. If either namespace already contains unrelated work, use a fresh cluster. CS06 separately creates `cks-tiers` and `cks-data`; SC09 creates `cks-image-policy`. Follow those drills' preflight and cleanup for their extra namespaces. Admission policies/bindings, Gatekeeper templates/constraints, CSRs and RuntimeClasses are explicitly introduced only by their corresponding drills.

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

## First session

Allow approximately 75-110 minutes of active practice after environment setup. This is guided practice for someone comfortable with CKA-level administration, not a timed examination. Start with the kind profile; the documented EKS profile must skip the network drill because of its [fixture restriction](COMPATIBILITY.md).

Copy the progress template once, preserving an existing personal log:

```bash
test -e work/PROGRESS.md || cp preparation/PROGRESS.md work/PROGRESS.md
mkdir -p work/CS01 work/CH02
```

| Step | Do | Prove and finish |
|---|---|---|
| 1 | Run preflight and establish all four baseline connections above | Correct context, healthy Pods and working DNS/application before adding controls |
| 2 | Attempt [CS01](../labs/cluster-setup.md#cs01-network-isolation) in `work/CS01/` | Run its manual proof, then `python3 scripts/lab.py --context "$LAB_CONTEXT" verify CS01`; delete only its four named policies and repeat the baseline connections |
| 3 | Attempt [CH02 core](../labs/cluster-hardening.md#ch02-serviceaccounts), through the token/Pod-reader proof | Run `python3 scripts/lab.py --context "$LAB_CONTEXT" verify CH02`; defer the binding and Secret-via-Pod extensions, then delete the core Pod, RoleBinding, Role and ServiceAccount |
| 4 | Attempt [MW02](../labs/workload-security.md#mw02-workload-hardening) using `work/demo.yaml` | Run `python3 scripts/lab.py --context "$LAB_CONTEXT" verify MW02`; retain your manifest for RT03, delete only `cks-lab/demo`, and confirm the shared witnesses remain healthy |
| 5 | Record guided results and reset evidence in `work/PROGRESS.md` | Repeat independently in a later session, then choose the [next exercises](SESSIONS.md#after-the-first-session) |

Attempt the solution before opening [worked references](../solutions/README.md). The verifier checks the prepared exercise; it does not solve it. CS01 verification briefly creates a narrowly scoped policy and removes it, so it needs create/delete permissions on lab NetworkPolicies. For FAIL, compare the reported observation to the task. For BLOCKED, repair the stated environment or witness before judging the solution. [Result codes and limits](VALIDATION.md#first-session-verifier).

For the first CH02 core reset, these names must be objects you created for that drill:

```bash
kubectl -n cks-lab delete pod ch02-client --wait=true
kubectl -n cks-lab delete rolebinding ch02-pod-reader
kubectl -n cks-lab delete role ch02-pod-reader
kubectl -n cks-lab delete serviceaccount ch02-client
```

Use the full drill reset if you attempted extensions. In every drill, a nonzero negative probe is expected only when its error explains the intended denial. Do not run every command under a blanket `set -e`, and do not hide failures with `|| true`.

## Diagnose a blocked start

| Symptom | Check before changing the solution |
|---|---|
| API unreachable or wrong context | Selected kubeconfig, endpoint, VPN/authorized IP and provider login; use `kubectl --request-timeout=10s get nodes` |
| Pod Pending or ImagePullBackOff | `kubectl -n cks-lab describe pod POD`; inspect scheduling, image architecture, registry access and recent events |
| Pod starts but is not Ready | `kubectl -n cks-lab logs POD` and `describe pod`; confirm the application command, port and writable directory |
| DNS fails | `kubectl -n cks-lab exec client -- cat /etc/resolv.conf`, resolver readiness and the exercise's DNS egress rule |
| Every HTTP probe fails | First restore the clean baseline; prove the server and a healthy witness work before interpreting policy denial |
| Forbidden API operation | Confirm which identity and verb were rejected; an administrator lacking impersonation is an environment blocker |
| A later exercise behaves differently | Check leftover NetworkPolicies, namespace PSA/mesh labels and earlier admission configuration; complete the owning drill's reset |

Substitute the named Pod for `POD`. Keep diagnostic output private when it includes cluster details. A shared namespace reset clears practice state; it does not repair a missing CNI, provider restriction or failed node. Use the [environment teardown](ENVIRONMENTS.md) when finished paying for or running a cluster.

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
| [namespace-pair.yaml](../labs/fixtures/namespace-pair.yaml) | MW06 two-container network/PID/filesystem comparison |
| [image-go](../labs/fixtures/image-go/README.md) | SC01 real compilation and multi-stage runtime reduction |
| [image-policy](../labs/fixtures/image-policy/README.md) | SC09 mutually authenticated HTTPS backend and actual API-server integration |

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

The shared reset does not delete CS06's extra namespaces or undo SC09's host configuration. Restore the API server's original admission configuration before stopping the webhook backend. Use CH06's verified console recovery procedure rather than depending on a healthy API during a control-plane failure.

For encryption changes, retain old decryption keys until data has been rewritten and verified under the replacement key. Restoring only an old configuration can strand data encrypted with a newer key. Do not delete a system executable merely because it owns a listening port; stop the specific task-owned service instead.
