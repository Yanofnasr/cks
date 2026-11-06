# Study path

Work through one skill at a time, then combine them. Every drill has a starting state, task, proof and reset. Copy editable material into `work/`; keep the supplied fixtures as a repeatable starting point.

The domain weights below follow the [official curriculum](REFERENCES.md). The baseline is Kubernetes 1.37. First establish [your lab environment](LAB-SAFETY.md); an unavailable optional component means **blocked by environment**, not a failed skill or a simulated pass.

## Cluster setup, 15%

Read [Cluster setup](../labs/cluster-setup.md).

| ID | Practice | Environment |
|---|---|---|
| CS01 | Default deny, allowed traffic, namespace selectors and DNS | Cluster with enforcing CNI |
| CS02 | Block a controlled metadata-like endpoint selectively | Cluster plus isolated private test endpoint |
| CS03 | Find and remediate an actual CIS benchmark failure | kubeadm VMs and matching kube-bench |
| CS04 | Serve the intended hostname with a verifiable TLS certificate | Cluster with Ingress controller |
| CS05 | Verify exact platform binary identity | Local files and trusted release metadata |


## Cluster hardening, 15%

Read [Cluster hardening](../labs/cluster-hardening.md).

| ID | Practice | Environment |
|---|---|---|
| CH01 | RBAC scope, client certificates and CSRs | Cluster with administrator access |
| CH02 | ServiceAccount permissions, mounting and projected tokens | Cluster |
| CH03 | API authentication, authorization, admission and TLS | kubeadm VM with recovery access |
| CH04 | Kubelet authentication and authorization | Disposable worker VM |
| CH05 | One-minor-version upgrade with drain and recovery | Snapshot of older kubeadm VM pair |


## System hardening, 10%

Read [System hardening](../labs/system-hardening.md).

| ID | Practice | Environment |
|---|---|---|
| SH01 | Attribute and remove a task-owned listener/service | Disposable Linux VM |
| SH02 | Least-privilege users, groups and filesystem access | Disposable Linux VM |
| SH03 | AppArmor profile, node placement and enforced denial | AppArmor-enabled node |
| SH04 | seccomp profile with working and denied operations | Linux node and compatible runtime |
| SH05 | Restrict a private host listener to the intended client source | Disposable Linux VM, nftables and two controlled clients |


## Minimize microservice vulnerabilities, 20%

Read [Workload security](../labs/workload-security.md).

| ID | Practice | Environment |
|---|---|---|
| MW01 | Pod Security Admission, valid/invalid Pods and namespace scope | Cluster |
| MW02 | Non-root, capabilities, escalation and writable paths | Cluster |
| MW03 | Secrets, encryption at rest, rewrite and key rotation | Cluster; kubeadm/etcd access for encryption |
| MW04 | Actual sandboxed workload using RuntimeClass | Node with compatible sandbox runtime |
| MW05 | mTLS and encryption with real allowed/denied traffic | Cluster with a working mesh |


## Supply chain security, 20%

Read [Supply chain](../labs/supply-chain.md).

| ID | Practice | Environment |
|---|---|---|
| SC01 | Smaller, non-root images that still serve the app | Local container builder/runtime |
| SC02 | Scan and compare real findings | Trivy and available vulnerability database |
| SC03 | Bind desired and running image identities to a digest | Cluster and registry access |
| SC04 | Signature verification and rejected wrong identity/key | Cosign and an owned test registry |
| SC05 | Generate and inspect a real SBOM | Trivy, BOM or Syft |
| SC06 | Registry admission across regular, init and ephemeral containers | Cluster with ValidatingAdmissionPolicy |
| SC07 | Trace source, build identity, digest and provenance | Public artifact and its attestation |
| SC08 | Find and fix workload/Dockerfile misconfigurations | Trivy; builder/runtime and cluster for full proof; KubeLinter optional |


## Monitoring, logging and runtime security, 20%

Read [Runtime security](../labs/runtime-security.md).

| ID | Practice | Environment |
|---|---|---|
| RT01 | Falco rules, real events and syscall attribution | Falco-equipped disposable node |
| RT02 | Audit policy ordering, mounts and event investigation | Local JSONL; kubeadm VM for live auditing |
| RT03 | Read-only root with required writable volumes | Cluster |
| RT04 | Attribute, contain and verify a controlled incident | Disposable cluster or VM |


## Practice rhythm

Work through the available drills, record positive and negative checks, and verify cleanup. Repeat weak skills from a fresh starting state. Keep a local copy of [Progress](PROGRESS.md) under `work/` and consult the [worked references](../solutions/README.md) after attempting a task.
