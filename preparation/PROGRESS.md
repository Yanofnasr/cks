# Progress

Copy this template to `work/PROGRESS.md` for a local study log. Keep this shared copy blank so other learners start from the same template.

Record a result only after completing the drill's proof. `pass` requires the intended action to work, the prohibited action to fail for the expected reason, and the workload/cluster to remain healthy. Record cleanup separately; a failed reset blocks dependent work.

| Domain | First pass | Independent retry | Next weak skill |
|---|---|---|---|
| CS01-CS06, cluster setup | Not measured | Not measured | |
| CH01-CH07, cluster hardening | Not measured | Not measured | |
| SH01-SH05, system hardening | Not measured | Not measured | |
| MW01-MW06, workload security | Not measured | Not measured | |
| SC01-SC09, supply chain | Not measured | Not measured | |
| RT01-RT04, runtime security | Not measured | Not measured | |
| CAP01, capstone | Not measured | Not measured | |

## Attempt log

Use `pass`, `retry`, `blocked by environment`, or `not measured`. Keep missing tool/controller problems separate from knowledge gaps. Use `guided`, `independent`, or `timed` for practice mode. Name the completed part, such as `CH02 core`, `MW03 A`, or `RT02 offline`; a partial result is not a whole-drill pass. Put detailed outputs in ignored `work/`; record only non-secret summaries here.

| Date | Drill / part | Mode | Environment / versions | Minutes | Result | Positive / negative proof; hints used | Reset verified / retry date |
|---|---|---|---|---:|---|---|---|
| | | | | | | | |

For example, an offline audit attempt should name `RT02 offline`, with `RT02 live: blocked by environment` recorded separately if no control-plane VM is available. A guided pass followed by an independent retry gives more useful evidence than a single domain checkmark.

Add one sentence explaining the boundary and one plausible wrong answer your checks would catch. The [concept questions](../preparation/CONCEPTS.md#turn-an-attempt-into-understanding) help turn an attempt into reusable understanding.

Record the repository revision and complete environment identity once per session, then refer to that session in the table. Include Kubernetes, CNI, runtime, OS/kernel, architecture and relevant tool versions. See [validation evidence](../preparation/VALIDATION.md#record-a-reproducible-attempt).

## Next session

1. Prepare the [shared starting state](../preparation/LAB-SAFETY.md#shared-starting-state) and confirm the intended lab context.
2. Follow the [first session](../preparation/LAB-SAFETY.md#first-session), or pick an independent/timed [session](../preparation/SESSIONS.md).
3. Record observed results and choose the next session from the weakest skill. Keep environment blockers and unattempted parts visible.
