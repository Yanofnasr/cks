# CAP01: Isolate a small application

Allow **45 minutes**. Use the [shared starting state](../preparation/LAB-SAFETY.md) on an otherwise disposable cluster. Keep all five witness Pods healthy. The two namespaces and their Services already belong to this exercise.

This combines CS01, CH01/CH02, MW01/MW02, SC03 and RT03. Complete MW02 independently from its deliberately incomplete starter before this timed attempt. The shared API is already hardened, so this capstone tests whether you preserve and verify those controls while changing identity, admission, networking and image identity. Use documentation when needed, but start without previous solutions. Save edited manifests and evidence in `work/capstone/`.

## Task

1. Enforce the Restricted Pod Security Standard for new workloads in `cks-lab`, using the cluster's supported policy version. Leave `cks-other` unchanged.
2. Create ServiceAccount `app-reader` in `cks-lab`. It may only `get` and `list` Pods in that namespace. It must not read Secrets, mutate Pods or list Pods in another namespace.
3. Recreate `cks-lab/api` with that ServiceAccount, without an automatically mounted API token. Keep Service `api` working on port 8080.
4. Preserve and verify UID/GID 1000, non-root enforcement, disabled privilege escalation, dropped capabilities, RuntimeDefault seccomp and a read-only root filesystem. Preserve the explicitly writable `/tmp` volume and its group ownership needed by the HTTP server.
5. Default-deny ingress and egress in `cks-lab`. Permit only `role=client` Pods in that same namespace to reach `app=api` on TCP/8080, plus the DNS traffic required by the lab. `intruder` and `cks-other/client` must not reach the lab API; the lab client must not reach `cks-other/api`.
6. Replace the API image tag with the verified digest for the same working image. Record the declared and running image identities, accounting for an image-index digest versus a platform-manifest digest where relevant.

Use only task-owned objects. Do not delete witness Pods to make blocked-traffic tests pass, install an unrelated policy globally, or weaken the cluster's existing controls.

## Proof

Keep one concrete observation for each requirement:

| Requirement | Positive control | Negative control |
|---|---|---|
| Admission | Compliant new Pod is accepted by server-side dry run | A valid Pod manifest violating Restricted is rejected; equivalent request in `cks-other` remains unaffected by this namespace label |
| Identity | `get pods` and `list pods` authorization queries say yes for `system:serviceaccount:cks-lab:app-reader` in `cks-lab` | Secret `get/list/watch`, Pod `watch/create/update/patch/delete/deletecollection`, and Pod listing in `cks-other` say no for that identity |
| Application | API Pod Ready, HTTP response through its Service | ServiceAccount token is absent from the running container |
| Runtime | Writing `/tmp/allowed.txt` succeeds; app stays Ready; `/proc/1/status` confirms UID/GID 1000, zero effective capabilities and `NoNewPrivs: 1` | The root mount is read-only and writing `/should-not-write` fails; a file-permission error alone is insufficient |
| Network | `cks-lab/client` reaches `api.cks-lab.svc:8080`; DNS works; `cks-other/client` still reaches its own API | Healthy forbidden clients fail; the intruder still fails with only its egress temporarily allowed to the API; lab client cannot reach the other namespace API |
| Image | Declared digest is the intended image and runtime identity is explained | A mutable tag alone is not accepted as completion |

For every failed connection, first verify that the caller exists, is Ready, can execute commands and resolves the target. Preserve the successful permitted request as a witness. A failed command caused by a missing Pod, broken DNS or missing utility is not policy evidence.

Use [CS01's independent ingress check](cluster-setup.md#independent-ingress-check), including the temporary policy's collision check and cleanup. Otherwise an intruder blocked by source egress can conceal overly broad API ingress. Use [CH02's authorization matrix](cluster-hardening.md#ch02-serviceaccounts) with `app-reader` substituted for `ch02-client`; inspect all contributing grants rather than treating a denied Secret `get` as proof that Secret `list` is also denied. Finish with the temporary network allowance absent and all original traffic checks repeated.

If an API Pod field is immutable, recreate only that Pod from your edited manifest. Do not replace a working control-plane manifest or reset a node for this exercise.

## Finish

Record completed requirements, incomplete requirements, elapsed time and one diagnostic lesson in [Progress](../preparation/PROGRESS.md). This is a practice checklist, not an exam-grade calculation. Repeat with different names/ports when all six requirements work.

Use the [shared reset](../preparation/LAB-SAFETY.md) to remove the namespace-scoped Role, RoleBinding, ServiceAccount, policies and workloads, and to clear the namespace labels. Verify the fresh witnesses all communicate again before the next drill.
