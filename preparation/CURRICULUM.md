# Curriculum coverage

This map uses the [CNCF CKS 1.37 curriculum](https://github.com/cncf/curriculum/blob/main/CKS_Curriculum%20v1.37.pdf) and [Linux Foundation exam page](https://training.linuxfoundation.org/certification/certified-kubernetes-security-specialist/), checked in **November 2026**. Objective descriptions are summarized below. They establish scope, not the frequency, wording or selection of real exam tasks.

## Cluster setup, 15%

| Published objective | Drills | Observable result |
|---|---|---|
| Network isolation | CS01, CAP01 | Intended traffic and DNS work; healthy unauthorized peers are blocked |
| CIS component checks | CS03 | Version-matched control fails before remediation and passes afterward |
| Ingress TLS | CS04 | Correct hostname/backend and verified certificate trust |
| Metadata and endpoint protection | CS02 | Selective access to a controlled external endpoint, with ordinary traffic preserved |
| Platform binary verification | CS05 | Trusted expected digest matches; changed artifact fails |

## Cluster hardening, 15%

| Published objective | Drills | Observable result |
|---|---|---|
| Least-privilege RBAC | CH01, CAP01 | Authorized operation works; forbidden scope and escalation requests fail |
| Careful ServiceAccount use | CH02 | Token mounting and API permissions are verified independently |
| Kubernetes API access | CH03, CH04 | Protected endpoints reject anonymous access while required probes and operations work |
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
| Workload isolation | MW04, CS01, CAP01 | Selected sandbox actually runs; tenant/network boundaries behave as intended |
| Pod-to-pod encryption | MW05 | Protected connection is observed, permitted client works, plain client fails |

## Supply chain security, 20%

| Published objective | Drills | Observable result |
|---|---|---|
| Minimal functional images | SC01 | Non-root image serves the app with constrained runtime settings |
| SBOMs, build and artifact understanding | SC05, SC07 | Real component inventory and traceable artifact/build identities |
| Registry and artifact trust | SC03, SC04, SC06 | Correct digest/publisher accepted; wrong identity, image field or registry rejected |
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

The 32 drills plus CAP01 provide written coverage of all listed objective groups. That is different from runtime coverage: controllers, CNIs, runtimes, kernels and tool versions affect outcomes. Local repository checks do not prove every lab works on every environment. Use the evidence requirements in [Contributing](../CONTRIBUTING.md) for runtime claims and a local [progress log](PROGRESS.md) for measured attempts.

This workbook is independent of CNCF, the Linux Foundation and training providers. It contains no recalled exam content. The [allowed-resource rules](REFERENCES.md) govern exam use; the wider study bibliography does not expand them.
