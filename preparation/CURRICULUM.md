# Curriculum coverage

This map uses the [CNCF CKS 1.37 curriculum](https://github.com/cncf/curriculum/blob/main/CKS_Curriculum%20v1.37.pdf) and [Linux Foundation exam page](https://training.linuxfoundation.org/certification/certified-kubernetes-security-specialist/), checked in **November 2026**. Objective descriptions are summarized below. They establish scope, not the frequency, wording or selection of real exam tasks.

## Cluster setup, 15%

| Published objective | Drills | Observable result |
|---|---|---|
| Network isolation | CS01, CS06, CAP01 | Intended traffic and DNS work; healthy unauthorized peers are blocked |
| CIS component checks | CS03 | Version-matched control fails before remediation and passes afterward |
| Ingress TLS | CS04 | Correct hostname/backend and verified certificate trust |
| Metadata and endpoint protection | CS02 | Selective access to a controlled external endpoint, with ordinary traffic preserved |
| Platform binary verification | CS05 | Trusted expected digest matches; changed artifact fails |

## Cluster hardening, 15%

| Published objective | Drills | Observable result |
|---|---|---|
| Least-privilege RBAC | CH01, CAP01 | Authorized operation works; forbidden scope and escalation requests fail |
| Careful ServiceAccount use | CH02 | Token mounting and API permissions are verified independently |
| Kubernetes API access | CH03, CH04, CH06, CH07 | Protected endpoints reject anonymous access while required probes and operations work |
| Kubernetes upgrades | CH05 | Supported version transition, recovered workload, Ready and schedulable nodes |

## System hardening, 10%

| Published objective | Drills | Observable result |
|---|---|---|
| Reduce OS attack surface | SH01 | Task-owned service/port removed without breaking required software |
| Least-privilege OS access | SH02 | Intended reader succeeds; unrelated reader and forbidden writes fail |
| Limit external network access | SH05 | One controlled client succeeds and another is rejected by the host rule |
| Kernel restrictions | SH03, SH04 | AppArmor/seccomp enforce the intended restriction, with a working witness |

## Minimize microservice vulnerabilities, 20%

| Published objective | Drills | Observable result |
|---|---|---|
| Pod security standards | MW01, MW02, CAP01 | Valid workload admitted; prohibited configuration rejected; app remains healthy |
| Secret management | MW03 | Scoped access and actual encrypted storage survive staged key rotation |
| Workload isolation | MW04, MW06, CS01, CS06, CAP01 | Selected sandbox actually runs; tenant/network boundaries behave as intended |
| Pod-to-pod encryption | MW05 | Protected connection is observed, permitted client works, plain client fails |

## Supply chain security, 20%

| Published objective | Drills | Observable result |
|---|---|---|
| Minimal functional images | SC01 | Non-root image serves the app with constrained runtime settings |
| SBOMs, build and artifact understanding | SC05, SC07 | Real component inventory and traceable artifact/build identities |
| Registry and artifact trust | SC03, SC04, SC06, SC09 | Correct digest/publisher accepted; wrong identity, image field or registry rejected |
| Static workload/image analysis | SC08, SC02 | Actual misconfiguration findings are repaired; vulnerability scans are distinguished from configuration analysis |

## Monitoring, logging and runtime security, 20%

| Published objective | Drills | Observable result |
|---|---|---|
| Behavioral detection | RT01 | A real event matches a scoped rule; a healthy negative control does not |
| Threat detection across components | RT01, RT04 | Process, workload and network evidence identify the controlled activity |
| Investigate actors and attack progression | RT02, RT04 | Timeline and identity claims are supported by recorded evidence |
| Runtime immutability | RT03, MW02 | Required writable paths work while protected image/data paths reject writes |
| Kubernetes audit logging | RT02 | Actual requests produce correctly scoped, ordered audit records |

## Practice emphasis and limits

Start with networking, RBAC/ServiceAccounts, PSA/security contexts, audit interpretation, image analysis and runtime detection. This is a learning sequence chosen for transferable skills, not an estimate of exam-question probability. Then complete the node, encryption, signing, mesh and sandbox work before mixed timed practice.

The 37 drills plus CAP01 provide written coverage of all listed objective groups. That is different from runtime coverage: controllers, CNIs, runtimes, kernels and tool versions affect outcomes. Local repository checks do not prove every lab works on every environment. Use the evidence requirements in [Contributing](../CONTRIBUTING.md) for runtime claims and a local [progress log](PROGRESS.md) for measured attempts.

This workbook is independent of CNCF, the Linux Foundation and training providers. It contains no recalled exam content. The [allowed-resource rules](REFERENCES.md) govern exam use; the wider study bibliography does not expand them.

## Killer Shell practice coverage

Use this table to practice the topics in Killer Shell's [public scenario index](https://github.com/killer-sh/cks-course-environment/blob/f10551265c2eb04c12a443afaa8500eb824530de/Scenarios.md) and [course resources](https://github.com/killer-sh/cks-course-environment/blob/f10551265c2eb04c12a443afaa8500eb824530de/Resources.md) within this workbook. The index groups 38 hosted scenarios into 21 topics. The local exercises below implement those skills; they are not copies of the hosted questions or validators.

| Course practice topic | Local exercise | What to do and prove |
|---|---|---|
| Container internals | MW06 | Compare network/PID namespaces, localhost access, separate volumes and shared-process mode; repeat with Docker or Podman if available |
| Network policies | CS01, CS06, CAP01 | Apply default deny, restore intended flows, and demonstrate namespace/Pod selector AND versus OR and additive policies |
| Ingress and TLS | CS04 | Create routing and a fresh TLS identity; prove trusted access and certificate rejection |
| Metadata protection | CS02 | Restrict a controlled external endpoint while keeping DNS and intended cluster traffic working |
| CIS benchmarks | CS03 | Match the benchmark to the installation, repair actual failures and keep the cluster healthy |
| Platform binaries | CS05 | Compare an actual artifact with a trusted digest and reject an altered copy |
| RBAC and certificate signing | CH01 | Issue a client certificate through Kubernetes and manually, then test actual authentication and permission scope |
| ServiceAccount token mounting | CH02 | Compare automatic/explicit token mounting and prove that Pod-creation authority can expose a dummy Secret |
| API access, crashes and node restrictions | CH03, CH04, CH06, CH07 | Harden protected endpoints, recover an unavailable API and distinguish node authorization from admission restrictions |
| Secrets and etcd | MW03, CH02 | Mount a dummy Secret, verify limited API access, inspect encrypted storage, rewrite existing values and rotate keys safely |
| Runtime sandboxes | MW04 | Run a real workload with the installed sandbox handler and compare runtime evidence |
| OS security domains | MW01, MW02, SH03, SH04 | Exercise security contexts, admission rejection and kernel enforcement with healthy witnesses |
| Image footprint | SC01 | Harden a static image, then remove an actual compiler/source tree with a multi-stage build |
| Manual static analysis | SC08 | Identify manifest and Dockerfile defects before scanning; repair, rescan and prove the app still runs |
| Vulnerability scanning | SC02 | Use actual scanner findings and image identity, including a failing severity gate |
| Image-policy webhook and digests | SC03, SC09 | Pin runtime identity; connect an actual mTLS backend and test policy rejection, TLS failure, outage and recovery |
| Syscalls and Falco | RT01 | Trace an owned process and observe real matching/nonmatching detector events |
| Runtime immutability | RT03, MW02 | Prove read-only image/data boundaries while required writable paths and the app still work |
| Audit logging | RT02 | Configure a real audit pipeline and interpret actor/resource/status evidence separately from synthetic examples |
| AppArmor | SH03 | Load a profile on the selected node and observe an audited denial with a working comparison |
| Packages, services and ports | SH01, SH05 | Remove task-owned exposure/software and prove source-specific host filtering |

The resource collection also includes Gatekeeper/Rego and multi-stage build examples; SC06's Gatekeeper variation and SC01's compiled-image variation practice those actual operations. CH01 compares a RoleBinding to a ClusterRole with a cluster-wide binding, rather than treating the two scopes as interchangeable. CH05 covers the separate upgrade resource section.

Some source-specific products remain optional: the historical Dashboard installation is not supplied here, and custom Conftest policy development is not the same operation as SC08's Trivy/KubeLinter analysis. Use an already-installed management UI to practice its exposure and ServiceAccount permissions if needed; do not count those product-specific paths as locally executed. Runtime/add-on prerequisites remain explicit in each drill. The workbook also retains mesh encryption, signing, SBOM, provenance, PSA and seccomp practice beyond the scenario index.
