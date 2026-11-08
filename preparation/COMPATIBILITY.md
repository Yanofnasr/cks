# Drill compatibility

This is a **capability map**, not a test-results table. Every platform cell describes the expected scope of the [documented profiles](ENVIRONMENTS.md). Consult [Validation](VALIDATION.md) for actual runtime evidence and record your own exact versions. An accepted manifest does not establish enforcement.

- **R**: the profile provides the capabilities needed for the written drill, subject to its preflight and proof.
- **A**: additional named tooling, controller, registry or machine must be prepared first.
- **P**: only the stated part is available; record that part separately and do the remainder on a suitable profile.
- **N**: unavailable as written on this profile. Use the suggested alternative.
- **L**: runs on the learner's workstation with the named tools; the cluster platform is irrelevant.

Columns mean: **kind** v0.33.0/Kubernetes 1.37.0/Calico 3.33.0; **EKS** managed Linux nodes with Amazon VPC CNI; **AKS** Standard with Azure CNI powered by Cilium; **GKE** Standard with Dataplane V2; **VMs** self-managed kubeadm/containerd on dedicated Linux VMs. Windows nodes, EKS Fargate, AKS Automatic and GKE Autopilot are outside these profiles. Cloud minor versions depend on regional availability.

| ID | Drill | kind | EKS | AKS | GKE | VMs | Restriction or additional prerequisite |
|---|---|---|---|---|---|---|---|
| CS01 | Network isolation | R | N | R | R | R | EKS native policy has a standalone-Pod limitation; inspect actual DNS on every CNI |
| CS02 | Metadata-like endpoint | A | N | A | A | A | Separate private non-cluster VM and reachable test endpoint; IPv4 example |
| CS03 | CIS remediation | N | N | N | N | A | Matching kube-bench plus direct kubeadm configuration and recovery access |
| CS04 | Ingress TLS | A | A | A | A | A | Working maintained Ingress controller, IngressClass and reachable HTTPS address |
| CS05 | Binary integrity | L | L | L | L | L | Trusted release digest and platform-matching binary; never run altered copy |
| CS06 | Three-tier policies | R | N | R | R | R | Enforcing CNI and fresh extra namespaces; EKS standalone-Pod restriction |
| CH01 | RBAC and certificates | P | P | P | P | R | kind: API CSR/RBAC; manual CA-key variation requires VMs; managed profiles: RBAC, provider-dependent client signing |
| CH02 | ServiceAccounts | R | R | R | R | R | Administrator impersonation and scoped Role/RoleBinding permissions; core and extensions logged separately |
| CH03 | API-server configuration | N | N | N | N | R | Written task edits a kubeadm control-plane VM, with snapshot and console recovery |
| CH04 | Kubelet hardening | N | N | N | N | R | Written task changes the worker's effective config and requires independent recovery |
| CH05 | kubeadm upgrade | N | N | N | N | A | Separate 1.36 VM starting snapshot; provider upgrade is a different exercise |
| CH06 | API-server recovery | N | N | N | N | R | Deliberate control-plane outage; dedicated VM pair and verified recovery |
| CH07 | Node authorization | R | P | P | P | R | Two nodes and user/group impersonation; managed control-plane config inspection is unavailable |
| SH01 | Services and packages | N | N | N | N | R | Dedicated Linux VM; package variation assumes Debian/Ubuntu |
| SH02 | OS permissions | N | N | N | N | R | Root-owned files and disposable system users on a VM |
| SH03 | AppArmor | N | N | N | N | A | AppArmor-enabled kernel, parser, node profile installation and audit access |
| SH04 | Local seccomp profile | N | N | N | N | A | Compatible runtime plus writable selected node's kubelet profile directory |
| SH05 | Host firewall | N | N | N | N | A | Dedicated VM, nftables, two clients with distinct observed source addresses |
| MW01 | Pod Security Admission | R | R | R | R | R | Namespace-label permission; distinguish provider/global admission from the intended PSA denial |
| MW02 | Workload hardening | R | R | R | R | R | Linux workload and no leftover CS01 policies or MW01 labels |
| MW03 | Secrets and encryption | P | P | P | P | R | Secret mount/RBAC everywhere; full etcd encryption/rotation task requires VMs |
| MW04 | Runtime isolation | N | N | N | N | A | Installed and proven sandbox handler on a disposable VM; RuntimeClass alone is insufficient |
| MW05 | Pod encryption | A | A | A | A | A | Compatible sidecar Istio plus functioning Istio CNI; plain and meshed controls |
| MW06 | Container namespaces | R | R | R | R | R | Linux Pods; optional Docker/Podman comparison is local |
| SC01 | Functional minimal images | L | L | L | L | L | Docker/Podman builder/runtime; compiled variation uses supplied Go build context |
| SC02 | Vulnerability scanning | L | L | L | L | L | Trivy and its database; scan the actual recorded artifact |
| SC03 | Publish and pin images | A | A | A | A | A | SC01 output, owned registry, push/pull access and final digest; no default registry supplied |
| SC04 | Artifact signatures | A | A | A | A | A | SC03 published digest, Cosign and registry signing/push permissions |
| SC05 | SBOM | L | L | L | L | L | SC03 published digest and Trivy/BOM/Syft with registry access |
| SC06 | Registry admission | R | R | R | R | R | ValidatingAdmissionPolicy API; Gatekeeper variation additionally needs its real controller |
| SC07 | Build provenance | L | L | L | L | L | Actual artifact/build evidence; signed-attestation verification needs a trusted attestation |
| SC08 | Static analysis | A | A | A | A | A | Trivy plus local image build/run and cluster proof; optional KubeLinter |
| SC09 | ImagePolicyWebhook | N | N | N | N | A | Dedicated control-plane VM, CH06 recovery, Python/OpenSSL, backend and API configuration |
| RT01 | Falco and syscall tracing | N | N | N | N | A | Compatible Falco event source on disposable VM, rule loading and node tracing tools |
| RT02 | Audit interpretation/config | P | P | P | P | R | Offline synthetic interpretation everywhere; full audit configuration requires kubeadm VMs |
| RT03 | Runtime immutability | R | R | R | R | R | Successful MW02 manifest, immutable ConfigMap and fresh networking baseline |
| RT04 | Incident containment | R | N | R | R | R | EKS standalone-Pod restriction; healthy witnesses and no earlier allow policies |
| CAP01 | Application integration | R | N | R | R | R | First-session core, MW01 and public-image digest lookup; no owned registry required; EKS network restriction applies |

For MW03, `P` covers Task A only. A provider's built-in encryption, logging or upgrade feature does not complete the different low-level kubeadm task. Likewise, a containerized kind node is not a replacement for the VM host exercises as written.

The EKS restriction follows [AWS's owner-reference warning](https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy.html). Changing to controller-backed witnesses or a different supported policy engine needs a documented adaptation and new runtime evidence. Do not manufacture owner references on standalone Pods. [AKS control-plane ownership](https://learn.microsoft.com/en-us/azure/aks/core-aks-concepts) and [GKE cluster architecture](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/cluster-architecture) explain why managed control planes cannot follow the VM mutation tasks.

Missing capability means **blocked by environment**. Complete local/available parts, name them in the [progress log](PROGRESS.md), and return to the remaining parts on VMs. Do not mark an entire drill passed after completing only an offline or managed-cloud subset.
