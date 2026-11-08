# Study path

Work through one skill at a time, then combine them. Every drill has a starting state, task, proof and reset. Copy editable material into `work/`; keep the supplied fixtures as a repeatable starting point. Use the [concept maps](CONCEPTS.md) to connect each exercise to its trust boundary and explain your result before moving on.

The domain weights below follow the [official curriculum](REFERENCES.md). The baseline is Kubernetes 1.37. The [objective map](CURRICULUM.md) explains coverage and practice emphasis. First establish [your lab environment](LAB-SAFETY.md); an unavailable optional component means **blocked by environment**, not a failed skill or a simulated pass.

Difficulty describes the task for a CKA-level learner: **Core** establishes one main control, **Intermediate** combines controls, and **Advanced** needs deeper diagnosis or host/control-plane recovery. Minutes are estimated active practice time, excluding provisioning, downloads and snapshots. Optional variations take additional time. Check the [platform matrix](COMPATIBILITY.md) and [recorded runtime evidence](VALIDATION.md) separately.

## Cluster setup, 15%

Read [Cluster setup](../labs/cluster-setup.md).

| ID | Practice | Environment | Difficulty | Minutes |
|---|---|---|---|---|
| [CS01](../labs/cluster-setup.md#cs01-network-isolation) | Default deny, allowed traffic, namespace selectors and DNS | Cluster with enforcing CNI | Core | 25-35 |
| [CS02](../labs/cluster-setup.md#cs02-metadata-protection) | Block a controlled metadata-like endpoint selectively | Cluster plus isolated private test endpoint | Intermediate | 25-40 |
| [CS03](../labs/cluster-setup.md#cs03-cis-remediation) | Find and remediate an actual CIS benchmark failure | kubeadm VMs and matching kube-bench | Advanced | 30-45 |
| [CS04](../labs/cluster-setup.md#cs04-ingress-tls) | Serve the intended hostname with a verifiable TLS certificate | Cluster with Ingress controller | Intermediate | 20-30 |
| [CS05](../labs/cluster-setup.md#cs05-binary-integrity) | Verify exact platform binary identity | Local files and trusted release metadata | Core | 15-20 |
| [CS06](../labs/cluster-setup.md#cs06-three-tier-traffic-and-policy-composition) | Three-tier traffic, selector AND/OR and additive policies | Cluster with enforcing CNI; supplied witnesses and policy reference | Intermediate | 25-40 |

## Cluster hardening, 15%

Read [Cluster hardening](../labs/cluster-hardening.md).

| ID | Practice | Environment | Difficulty | Minutes |
|---|---|---|---|---|
| [CH01](../labs/cluster-hardening.md#ch01-rbac-and-csrs) | RBAC scope, client certificates and CSRs | Cluster with administrator access | Intermediate | 30-45 |
| [CH02](../labs/cluster-hardening.md#ch02-serviceaccounts) | ServiceAccount permissions, mounting and projected tokens | Cluster | Core | 20-30 core |
| [CH03](../labs/cluster-hardening.md#ch03-api-server) | API authentication, authorization, admission and TLS | kubeadm VM with recovery access | Advanced | 30-45 |
| [CH04](../labs/cluster-hardening.md#ch04-kubelet) | Kubelet authentication and authorization | Disposable worker VM | Advanced | 25-40 |
| [CH05](../labs/cluster-hardening.md#ch05-upgrade) | One-minor-version upgrade with drain and recovery | Snapshot of older kubeadm VM pair | Advanced | 45-60 |
| [CH06](../labs/cluster-hardening.md#ch06-recover-an-unavailable-api-server) | Break, diagnose and recover the API server | Dedicated single-control-plane VM with snapshot and console | Advanced | 25-40 |
| [CH07](../labs/cluster-hardening.md#ch07-node-authorization-and-noderestriction) | Prove node-identity authorization and NodeRestriction admission | Disposable cluster with two nodes and administrator impersonation | Advanced | 20-30 |

## System hardening, 10%

Read [System hardening](../labs/system-hardening.md).

| ID | Practice | Environment | Difficulty | Minutes |
|---|---|---|---|---|
| [SH01](../labs/system-hardening.md#sh01-services-and-ports) | Attribute and remove a task-owned listener/service | Disposable Linux VM | Intermediate | 20-30 |
| [SH02](../labs/system-hardening.md#sh02-os-permissions) | Least-privilege users, groups and filesystem access | Disposable Linux VM | Core | 15-25 |
| [SH03](../labs/system-hardening.md#sh03-apparmor) | AppArmor profile, node placement and enforced denial | AppArmor-enabled node | Advanced | 25-40 |
| [SH04](../labs/system-hardening.md#sh04-seccomp) | seccomp profile with working and denied operations | Linux node and compatible runtime | Advanced | 25-40 |
| [SH05](../labs/system-hardening.md#sh05-host-firewall-rules) | Restrict a private host listener to the intended client source | Disposable Linux VM, nftables and two controlled clients | Advanced | 25-40 |

## Minimize microservice vulnerabilities, 20%

Read [Workload security](../labs/workload-security.md).

| ID | Practice | Environment | Difficulty | Minutes |
|---|---|---|---|---|
| [MW01](../labs/workload-security.md#mw01-pod-security-admission) | Pod Security Admission, valid/invalid Pods and namespace scope | Cluster | Core | 20-30 |
| [MW02](../labs/workload-security.md#mw02-workload-hardening) | Non-root, capabilities, escalation and writable paths | Cluster | Core | 25-35 |
| [MW03](../labs/workload-security.md#mw03-secrets-and-encryption-rotation) | Secrets, encryption at rest, rewrite and key rotation | Cluster; kubeadm/etcd access for encryption | Advanced | 20 A; 45-60 B/C |
| [MW04](../labs/workload-security.md#mw04-runtime-isolation) | Actual sandboxed workload using RuntimeClass | Node with compatible sandbox runtime | Advanced | 20-30 |
| [MW05](../labs/workload-security.md#mw05-pod-to-pod-encryption) | mTLS and encryption with real allowed/denied traffic | Cluster with a working mesh | Advanced | 30-45 |
| [MW06](../labs/workload-security.md#mw06-container-namespaces) | Compare network, PID and filesystem isolation | Supplied two-container Pod; optional Docker/Podman repeat | Intermediate | 20-30 |

## Supply chain security, 20%

Read [Supply chain](../labs/supply-chain.md).

| ID | Practice | Environment | Difficulty | Minutes |
|---|---|---|---|---|
| [SC01](../labs/supply-chain.md#sc01-image-footprint) | Smaller, non-root images that still serve the app | Local container builder/runtime | Intermediate | 30-45 |
| [SC02](../labs/supply-chain.md#sc02-vulnerability-scanning) | Scan and compare real findings | Trivy and available vulnerability database | Core | 15-25 |
| [SC03](../labs/supply-chain.md#sc03-image-digests) | Publish the final build and bind desired/running identity to its digest | SC01 build, owned registry with push/pull access and cluster | Intermediate | 25-40 |
| [SC04](../labs/supply-chain.md#sc04-signatures) | Signature verification and rejected wrong identity/key | SC03 published digest, Cosign and owned test registry | Intermediate | 20-30 |
| [SC05](../labs/supply-chain.md#sc05-sboms) | Generate and inspect a real SBOM | SC03 published digest; Trivy, BOM or Syft | Core | 15-20 |
| [SC06](../labs/supply-chain.md#sc06-admission-policies) | Registry admission across regular, init and ephemeral containers | Cluster with ValidatingAdmissionPolicy | Advanced | 25-40 |
| [SC07](../labs/supply-chain.md#sc07-build-provenance) | Trace source, build identity, digest and provenance | SC03 published digest/build evidence; trusted attestation for signed-provenance variant | Advanced | 20-30 |
| [SC08](../labs/supply-chain.md#sc08-static-analysis) | Find and fix workload/Dockerfile misconfigurations | Trivy; builder/runtime and cluster for full proof; KubeLinter optional | Intermediate | 25-40 |
| [SC09](../labs/supply-chain.md#sc09-imagepolicywebhook-integration) | Configure, test and recover an external image-policy webhook | Single-control-plane VM, Python/OpenSSL and supplied TLS backend | Advanced | 45-60 |

## Monitoring, logging and runtime security, 20%

Read [Runtime security](../labs/runtime-security.md).

| ID | Practice | Environment | Difficulty | Minutes |
|---|---|---|---|---|
| [RT01](../labs/runtime-security.md#rt01-falco-and-syscall-investigation) | Falco rules, real events and syscall attribution | Falco-equipped disposable node | Advanced | 25-40 |
| [RT02](../labs/runtime-security.md#rt02-audit-policy-and-investigation) | Audit policy ordering, mounts and event investigation | Local JSONL; kubeadm VM for live auditing | Intermediate | 15 offline; 30-45 live |
| [RT03](../labs/runtime-security.md#rt03-runtime-immutability) | Read-only root with required writable volumes | Cluster | Intermediate | 20-30 |
| [RT04](../labs/runtime-security.md#rt04-incident-response) | Attribute, contain and verify a controlled incident | Disposable cluster or VM | Intermediate | 20-30 |

## Practice rhythm

1. Follow the [guided first session](LAB-SAFETY.md#first-session): [CS01](../labs/cluster-setup.md#cs01-network-isolation), [CH02 core](../labs/cluster-hardening.md#ch02-serviceaccounts) and [MW02](../labs/workload-security.md#mw02-workload-hardening). Defer CH02's binding and Secret-via-Pod extensions until after the first independent core pass.
2. Use the [progression and session recipes](SESSIONS.md#after-the-first-session) for the next independent exercises. Complete MW01, SC03 and RT03 before CAP01, and CH06 recovery before SC09 modifies admission configuration. Keep the same final published image digest through SC03, SC04, SC05 and SC07.
3. Repeat each weak skill from a clean starting state, without looking at the previous solution. Change names, ports or identities on the second attempt.
4. Attempt [CAP01](../labs/capstone.md) in 45 minutes. Complete every requirement and record evidence, rather than inventing an exam score.
5. Follow the [two-hour mixed session](SESSIONS.md#two-hour-mixed-session) across all six domains. Prepare its environment outside the timer, use only currently permitted documentation and practice returning to the designated base/SSH host.

Keep a local copy of [Progress](PROGRESS.md) under `work/`: elapsed time, positive check, negative check, recovery result and next retry. Two independent successful attempts are a useful study milestone, not a guarantee of passing. Consult the [worked references](../solutions/README.md) after an attempt, then repeat without them.
