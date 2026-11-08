# Completed checks and reproducibility

This page records completed checks, the environment used, and the observed outcomes. Use the [compatibility map](COMPATIBILITY.md) to choose an environment and the drill's proof steps to record your own results.

## Environment records

| Profile | Kubernetes / CNI / runtime | Recorded run | Host |
|---|---|---|---|
| kind default | 1.37.0 / Calico 3.33.0 / containerd 2.3.4 | November 2026 | kind 0.33.0; Linux amd64; Debian 13 nodes; WSL2 kernel 6.18.54.1-microsoft-standard-WSL2 |

Add environment records from completed runs. Include exact component versions, the source revision, date, architecture, OS/kernel, image identities and the exercise parts completed.

The recorded local run used the exact node image digest in [kind.yaml](../labs/environments/kind.yaml) and the checksum-verified Calico manifest from the environment guide:

| Check | Observed scope |
|---|---|
| Preflight and shared baseline | Ready nodes, required permissions, all five working witnesses |
| Local environment lifecycle | Automated create, ownership-aware status, baseline checks, learner acceptance sequence and deletion of the owned cluster and credentials |
| CS01 | Correct policy passes; absent policy and overly broad ingress fail; independent ingress witness and restored isolation after temporary-policy cleanup |
| CH02 core | Correct Pod-reader identity passes; added Secret-list and named-Secret-read grants fail; token absence and effective permission rules checked |
| MW02 | Correct configuration and actual runtime restrictions pass; a writable-root variant fails; HTTP and the writable exception remain functional |
| CS06 traffic matrix | All seven baseline paths work; intended policies reject all five forbidden paths; the new witness detects overly broad backend ingress; baseline and namespace cleanup verified |
| SC06 native admission | Allowed and forbidden ordinary, init, ephemeral and image-volume references; absent optional fields, ordinary volumes and unaffected namespace; named rejection required after propagation |
| SC01 compiled variation | Both Dockerfiles build and serve HTTP; multi-stage image runs as 65532:65532 with a read-only root, dropped capabilities and no-new-privileges; shell absent |
| Gatekeeper decision logic | Eight OPA 1.22.2 tests evaluate the shipped Rego decisions against allowed and prohibited inputs |

The native cluster checks are reproducible with [cluster_smoke.py](../tests/cluster_smoke.py) on a separate empty kind cluster. They clean up their namespaces and admission policy. CS06 additionally used the written seven-path matrix and broadened-backend counterexample. The compiled-image checks follow the [CI workflow](../.github/workflows/check.yml), using Go builder digest `sha256:87c65a688975c0b1d4585d204874c45ca78354670e3a5f11368c5a492303d696` for the recorded run. The source used for the automated run is identified by SHA-256:

| File | SHA-256 |
|---|---|
| `scripts/lab.py` | `c910eece491339e5b9533bafb46f4b7e5e5e08b02932fd823cdd02454552e494` |
| `scripts/environment.py` | `9a0af8795eb78c858da7420915da4aab3f75ffb7159449e7b2021152a353a98d` |
| `tests/cluster_smoke.py` | `82549a203aeddb559764f3314556100ba0627408077eecc34c2e056896bc38c7` |
| `labs/environments/kind.yaml` | `88f5fab0531db4521576c54bb0cc8061f19c5aff4e944386371e083266ca2d3a` |

Re-run the relevant checks whenever the implementation, profile or component versions change. The table names the specific operations demonstrated by each result.

## Infrastructure configuration checks

The four [cloud profiles](../infrastructure/README.md) passed formatting, provider-schema validation and mock-provider plan assertions with Terraform 1.16.1 and OpenTofu 1.13.9. Each engine initializes against its own supplied lockfile. Mock plans evaluate declared configuration without creating cloud resources.

| Profile | Provider version | Mock plans per engine | Checked contracts |
|---|---|---:|---|
| EKS | AWS 6.72.0 | 4 | Private workers, administrator API range, explicit access entry, separate CNI identity, metadata protection and encrypted disks |
| AKS | AzureRM 5.13.0 | 4 | Administrator API range, Entra groups, disabled local accounts, Cilium and the four-vCPU system-pool size |
| GKE | Google 8.10.0 | 5 | Private nodes, dedicated node identity, Dataplane V2, scoped API access and zonal node count |
| kubeadm VMs | Google 8.10.0 | 3 | Two dedicated VMs, SSH/API ranges, node identity, host security and public-key-only inputs |

The SSH bootstrap helper passed twelve unit tests for inventory checks, strict host-key handling, disabled agent forwarding, credential transport and revocation, private kubeconfig construction, and failure handling. Its startup template passed rendered Bash syntax checks. Four Mermaid diagrams were rendered and inspected alongside the documentation checks.

## First-session verifier

With Python 3.11+, kubectl and the isolated lab kubeconfig:

```bash
python3 scripts/lab.py --context "$LAB_CONTEXT" preflight
python3 scripts/lab.py --context "$LAB_CONTEXT" verify CS01
python3 scripts/lab.py --context "$LAB_CONTEXT" verify CH02
python3 scripts/lab.py --context "$LAB_CONTEXT" verify MW02
```

Run each verifier after solving that drill and before its reset. Preflight inventories the selected environment and checks permissions. CS01 tests traffic and temporarily creates a narrowly scoped NetworkPolicy, then removes it and confirms restored isolation. Use it on the owned lab baseline with policy-create/delete permissions. CH02 and MW02 inspect your prepared resources and run bounded in-container checks; the learner remains responsible for configuring the solution.

| Result | Exit code | What to do |
|---|---|---|
| PASS | 0 | Record the tested scope and complete the drill's manual proof and reset |
| FAIL | 1 | A requirement failed; inspect the reported observation, fix the solution and retry |
| BLOCKED | 2 | A prerequisite, access check or trustworthy witness is missing; fix the environment before interpreting the result |

The automated checker evaluates CS01, CH02 core and MW02 using the standard fixture names, labels and port. Use the written manual proof for independently renamed or ported variations. CH02 checks effective resource permissions in the two practice namespaces, including grants restricted to named resources; standard self-review APIs and public ClusterTrustBundle reads remain permitted. An authorizer that cannot return complete rules produces BLOCKED. Record the exercise part and the observed denial reason, then complete its cleanup. If interrupted, inspect the reported temporary resources and remove only those created by the verifier after confirming ownership.

## Record a reproducible attempt

Keep detailed output in ignored `work/`, sanitized before sharing. A useful record includes:

1. Repository revision, timestamp, platform and exact component versions.
2. Drill and part, such as `CH02 core` or `RT02 offline`; guided, independent or timed mode.
3. Working starting state, plus intended operation, prohibited operation and the observed reason for denial.
4. Application/node health after the probes, cleanup commands and the successful reset check.
5. Skips, unresolved environment assumptions and the next retry.

Use [Progress](PROGRESS.md) for personal records. Contributors should submit a concise sanitized summary and reproducible steps, not credentials, full kubeconfigs or unfiltered node logs. Add separate rows for materially different CNIs, kernels, runtimes or provider modes. Record each CNI and provider mode separately, with its own traffic observations.

## Repository checks

Run the checks in [Contributing](../CONTRIBUTING.md#validate-a-contribution). Syntax and schema checks validate file and resource structure; unit tests exercise program behaviour; cluster checks observe actual admission, traffic and runtime outcomes. Keep these evidence types distinct when recording a result. Intentionally insecure fixtures are training inputs and remain clearly identified when interpreting scanner findings.
