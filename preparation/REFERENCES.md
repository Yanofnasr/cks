# References

## Exam baseline

Target **Kubernetes 1.37**, **two hours**, **67% passing score**, with a **prior CKA pass** required. Version and rules were checked against the live Linux Foundation pages in **November 2026**; confirm them again before the exam.

- [CKS technical instructions](https://docs.linuxfoundation.org/tc-docs/certification/important-instructions-cks)
- [CKS candidate FAQ](https://docs.linuxfoundation.org/tc-docs/certification/faq-cka-ckad-cks)
- [Resources allowed during the exam](https://docs.linuxfoundation.org/tc-docs/certification/certification-resources-allowed#certified-kubernetes-security-specialist-cks)
- [CNCF CKS 1.37 curriculum](https://github.com/cncf/curriculum/blob/main/CKS_Curriculum%20v1.37.pdf)
- [Linux Foundation CKS exam page](https://training.linuxfoundation.org/certification/certified-kubernetes-security-specialist/)

Use the versioned curriculum PDF and exam page for the 15/15/10/20/20/20 domain weights. This workbook is a study resource; do not assume personal notes or third-party repositories are allowed during the exam. Simulator availability depends on the exam product purchased.

## Exam documentation versus study resources

The current LF CKS list permits Kubernetes documentation/blog, Falco, BOM, etcd, the specified ingress-nginx configuration documentation, Cilium and Istio, plus task-specific Quick Reference links and the listed local system resources. Follow its browser/search restrictions. Trivy, Sigstore, gVisor, KubeLinter, arbitrary GitHub pages and this workbook are **general study references**, not automatically allowed exam resources. Consult the [actual allowed-resource page](https://docs.linuxfoundation.org/tc-docs/certification/certification-resources-allowed#certified-kubernetes-security-specialist-cks) for the full current rules.

The exam's documentation list is not a recommendation to deploy an old controller. [Ingress NGINX was retired](https://kubernetes.io/blog/2026/03/30/kubernetes-v1-36-sneak-peek/); keep practicing the published Ingress-with-TLS objective using the controller supplied by the lab/exam or an appropriately maintained controller in a fresh environment.

## Technical study references

Use LF/CNCF for exam scope and the component maintainers for implementation details. Match documentation to the installed version and environment, especially containerd configuration, admission/authentication APIs, CNI address handling and runtime event fields. The collection below is a selected primary-source bibliography, not a claim to exhaust all preparation material.

| Topic | Documentation |
|---|---|
| Network isolation | [NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/) |
| Identity and authorization | [RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/), [ServiceAccounts](https://kubernetes.io/docs/concepts/security/service-accounts/), [CSRs](https://kubernetes.io/docs/reference/access-authn-authz/certificate-signing-requests/) |
| Nodes and upgrades | [Kubelet authentication](https://kubernetes.io/docs/reference/access-authn-authz/kubelet-authn-authz/), [kubeadm upgrade](https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-upgrade/), [kube-bench](https://github.com/aquasecurity/kube-bench) |
| API access and authority | [Authentication configuration](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#anonymous-authenticator-configuration), [RBAC escalation restrictions](https://kubernetes.io/docs/reference/access-authn-authz/rbac/#privilege-escalation-prevention-and-bootstrapping), [RBAC good practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/) |
| Kernel controls | [AppArmor](https://kubernetes.io/docs/tutorials/security/apparmor/), [seccomp](https://kubernetes.io/docs/tutorials/security/seccomp/) |
| Host network filtering | [nftables manual](https://netfilter.org/projects/nftables/manpage.html) |
| CNI portability | [Cilium Layer 3 policy](https://docs.cilium.io/en/stable/security/policy/layer3/), [GKE ipBlock behavior](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/network-policy#inclusion_of_pod_ip_ranges_in_ipblock_rules) |
| Workload security | [Security contexts](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/), [Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/), [RuntimeClass](https://kubernetes.io/docs/concepts/containers/runtime-class/) |
| Secrets and encryption | [Encryption at rest and key rotation](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/), [etcd](https://etcd.io/docs/) |
| Sandbox | [gVisor containerd guide](https://gvisor.dev/docs/user_guide/containerd/quick_start/) |
| Pod-to-pod protection | [Istio mTLS](https://istio.io/latest/docs/tasks/security/authentication/mtls-migration/), [Cilium mutual authentication](https://docs.cilium.io/en/stable/network/servicemesh/mutual-authentication/mutual-authentication/), [Cilium encryption](https://docs.cilium.io/en/stable/security/network/encryption/) |
| Images and signatures | [Trivy](https://trivy.dev/docs/latest/), [Cosign verification](https://docs.sigstore.dev/cosign/verifying/verify/), [BOM CLI](https://kubernetes-sigs.github.io/bom/cli-reference/), [Syft](https://github.com/anchore/syft) |
| Static configuration analysis | [Trivy misconfiguration scanning](https://trivy.dev/docs/latest/scanner/misconfiguration/), [KubeLinter](https://github.com/stackrox/kube-linter), [Kubesec](https://kubesec.io/) |
| Admission | [ValidatingAdmissionPolicy](https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/), [admission controllers](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/) |
| Runtime detection | [Falco rule structure](https://falco.org/docs/concepts/rules/basic-elements/), [supported event fields](https://falco.org/docs/rules/supported-fields/), [Kubernetes auditing](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/) |
| Provenance | [GitHub artifact attestations](https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations), [SLSA specification](https://slsa.dev/spec/) |

## Optional browser practice

Use these when you want a temporary environment for repetition. The local drills remain the workbook's primary path; hosted scenarios have their own versions, prerequisites and scoring.

| Skill | Killer Shell / Killercoda scenario |
|---|---|
| Network policy | [Default deny](https://killercoda.com/killer-shell-cks/scenario/networkpolicy-create-default-deny), [namespace communication](https://killercoda.com/killer-shell-cks/scenario/networkpolicy-namespace-communication) |
| Cluster configuration | [CIS remediation](https://killercoda.com/killer-shell-cks/scenario/cis-benchmarks-kube-bench-fix-controlplane), [binary verification](https://killercoda.com/killer-shell-cks/scenario/verify-platform-binaries-kubelet) |
| Identity | [RBAC ServiceAccounts](https://killercoda.com/killer-shell-cks/scenario/rbac-serviceaccount-permissions), [token mounting](https://killercoda.com/killer-shell-cks/scenario/serviceaccount-token-mounting) |
| Secrets and isolation | [etcd encryption](https://killercoda.com/killer-shell-cks/scenario/secret-etcd-encryption), [gVisor](https://killercoda.com/killer-shell-cks/scenario/sandbox-gvisor) |
| Kernel and host | [AppArmor](https://killercoda.com/killer-shell-cks/scenario/apparmor), [open ports](https://killercoda.com/killer-shell-cks/scenario/system-hardening-close-open-ports) |
| Supply chain | [Trivy](https://killercoda.com/killer-shell-cks/scenario/image-vulnerability-scanning-trivy), [image digests](https://killercoda.com/killer-shell-cks/scenario/image-use-digest) |
| Detection and auditing | [Falco rule](https://killercoda.com/killer-shell-cks/scenario/falco-change-rule), [audit logs](https://killercoda.com/killer-shell-cks/scenario/auditing-enable-audit-logs) |

Source credits and adapted-material licensing are in [Acknowledgements](../ACKNOWLEDGEMENTS.md).
