# Practice sessions

The [first session](LAB-SAFETY.md#first-session) is guided. Repeat its drills independently before attempting the sessions below. Estimated times in the [study path](STUDY-PATH.md) exclude provisioning, downloads, vulnerability-database updates and recovery snapshots. Stop the timer when the environment fails; record that as a blocker separately from solving time.

## Three practice modes

| Mode | Use | Completion evidence |
|---|---|---|
| Guided | Read the task, use documentation and compare a worked reference after an attempt | Understand and explain each control, run positive/negative proof and reset |
| Independent | Start clean and avoid previous answers; change one name, port or identity deliberately | Solve and prove the behaviour with no answer lookup; note any hints used |
| Timed | Prepare the environment first, then use only the currently permitted documentation | Record completed/incomplete requirements, minutes, evidence and cleanup |

Keep `pass`, `retry`, `blocked by environment` and `not measured` separate. A guided pass is useful learning, but does not establish an independent pass. Name completed parts of mixed drills explicitly, for example `MW03 A` or `RT02 offline`.

Before advancing, answer the [five reflection questions](CONCEPTS.md#turn-an-attempt-into-understanding): boundary, evidence, counterexample, recovery and transfer. Keep the explanation short enough to repeat without your previous answer.

## After the first session

1. Repeat CS01, CH02 core and MW02 independently, resetting between them. Then complete MW01 and RT03 to distinguish admission, runtime root settings and data immutability.
2. Extend networking with CS06, identities with CH01 then CH02's binding/Secret extensions, and container internals with MW06.
3. Complete the artifact sequence SC01 → SC02 → SC03 → SC04/SC05/SC07. Keep the final published digest together across deployment, scans, signatures, SBOM and provenance. Add SC06/SC08 admission and static analysis.
4. Reserve a separate VM session for CH03/CH04, SH01-SH05, live RT02 and runtime tooling. CH05 needs its own older-version snapshot. Practice CH06 recovery before SC09 changes admission.
5. Attempt [CAP01](../labs/capstone.md), then use the mixed session below. Finish the remaining curriculum tasks, including actual mesh, sandbox and signing proof, on suitable environments.

## Two-hour mixed session

This recipe samples **all six domains** using existing exercises. It is a training session, not a reconstruction of an exam or a weighted passing-score estimate. Use a disposable kubeadm VM pair for the full profile. A kind/managed-cloud learner can do the cluster/local portions, but must record the host segment as blocked rather than substituting a written answer.

**Before the timer:** prepare trusted kubectl, the shared baseline, clean namespaces, a separate dummy `/srv/cks-private` starting state for SH02, and copies of the binary-integrity artifact and synthetic audit fixture. Keep the VM snapshot and console recovery ready. Download required artifacts beforehand. Choose new task-owned names in your working copies and write down their mapping. Do not pre-apply policies, RBAC answers or hardening changes.

| Minutes | Domain | Exercise slice | Required observation |
|---|---|---|---|
| 0-20 | Cluster setup | [CS01](../labs/cluster-setup.md#cs01-network-isolation) | Intended traffic and DNS pass; healthy forbidden peers fail |
| 20-25 | Transition | Reset CS01 policies and repeat unrestricted probes | Original connectivity restored before later work |
| 25-40 | Cluster hardening | [CH02 core](../labs/cluster-hardening.md#ch02-serviceaccounts) | Correct token mounting and narrow authorization; no extension grants |
| 40-45 | Transition | Reset CH02 owned objects | No exercise RoleBindings remain |
| 45-60 | System hardening | [SH02](../labs/system-hardening.md#sh02-os-permissions) | Intended read works; outsider read and reader write fail |
| 60-65 | Transition | Reset SH02 users/groups/files | Remove only this session's host resources |
| 65-85 | Workload security | [MW02](../labs/workload-security.md#mw02-workload-hardening) | Healthy app, non-root identity, effective restrictions, writable exception |
| 85-90 | Transition | Reset MW02 Pod | Shared witnesses remain healthy |
| 90-105 | Supply chain | [SC02](../labs/supply-chain.md#sc02-vulnerability-scanning) | Scan the preselected actual image and demonstrate the severity gate with real findings |
| 105-115 | Runtime/auditing | [RT02 offline](../labs/runtime-security.md#rt02-audit-policy-and-investigation) | Accurate actor/resource/status timeline and explicit evidence limits |
| 115-120 | Review | Update the attempt log and verify cleanup | Incomplete steps and next retries named honestly |

For SC02, pre-pull a deliberately chosen training image with findings and prepare the scanner/database before timing; record its exact digest and database version. A clean image is not a failed security outcome, but cannot demonstrate a failing severity gate. Do not fabricate findings or treat scanner errors as vulnerability detection. CS05's binary comparison can be used as an explicitly logged alternative if the scanner/database is unavailable; this does not complete SC02.

The host segment uses the separate VM shell. Before returning to cluster work, verify the workstation context again. The offline RT02 segment measures investigation, not live audit configuration. In a later session replace it with live RT02 or RT01 after provisioning their prerequisites outside the timer.

If a segment overruns, record where you stopped and move on after safe cleanup. A broken reset blocks dependent segments. Repeat the weak segment separately before repeating the whole session.
