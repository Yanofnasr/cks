# Contributing

Contributions should make a published CKS objective easier to practice and verify. Use [the curriculum map](preparation/CURRICULUM.md) to place an exercise before adding one. Do not submit recalled exam questions, exam dumps, private course material or unsupported predictions about the exam.

## A useful lab change

- Preserve existing drill IDs and links. Add a new ID only for a distinct skill.
- State the environment, versions, required tools and whether setup is supplied here.
- Give an achievable starting state, a concrete task, positive and negative proof, and cleanup limited to named lab resources.
- Distinguish admission rejection, authentication failure, network denial, DNS failure and an unavailable tool. A broken witness is not proof of security.
- Keep examples portable where possible. Explain CNI, DNS, runtime, architecture or controller assumptions where they affect results.
- Use dummy data. Keep kubeconfigs, keys, tokens, scan outputs and personal progress in ignored `work/`.
- Link the primary documentation supporting version-sensitive behavior. General study links are not automatically exam-allowed resources.
- Add the drill to the study path with difficulty, estimated active minutes (excluding setup), and direct links; update the capability matrix and progress ranges when IDs change.
- Mark core work, extensions and partial-platform coverage explicitly. Update runtime validation records only after performing the actual run.

Keep starter fixtures reproducible; place proposed answers in `solutions/` and label incomplete or environment-specific parts. Avoid broad host resets, installers, global policy deletion and automatic success fallbacks.

Use this small outline inside the appropriate existing domain file. Keep metadata in the [study path](preparation/STUDY-PATH.md), not duplicated in a new registry:

```markdown
## XX01 Concrete skill

**Environment:** named capabilities, exact relevant versions and prerequisites.

**Start:** owned resources and a working baseline, with any deliberate defect explained.

**Task:** observable outcome; distinguish required core work from optional extensions.

**Prove:** intended behaviour succeeds, prohibited behaviour fails for the expected reason,
and the application remains healthy. State which evidence does not prove the control.

**Reset:** remove only owned resources, restore the baseline and verify recovery.

Reference: primary documentation for version-sensitive behaviour.
```

## Validate a contribution

Run these from the repository root with Python 3.11 or newer:

```bash
python3 scripts/check.py
python3 -m unittest discover -s tests -v
git diff --check
```

The documentation checker uses only the Python standard library. Its scope is local Markdown links/anchors, drill consistency and JSON/JSONL syntax. It is not a Markdown renderer or Kubernetes grader. The Python test suite also exercises the lab verifier and image-policy fixture: its TLS tests need OpenSSL and a temporary loopback listener. Missing OpenSSL produces explicitly skipped TLS tests, which must not be reported as TLS validation. Describe additional tools and skips rather than implying these commands cover them.

When changing the compiled image example, run its standard-library-only Go test with Go already installed:

```bash
GOTOOLCHAIN=local GOPROXY=off go test labs/fixtures/image-go/main.go labs/fixtures/image-go/main_test.go
```

That test exercises the handler without network access; it does not build the Docker image or prove its runtime constraints.

For a runtime claim, use disposable infrastructure and report the Kubernetes version, OS, architecture, runtime, CNI and relevant tool/controller versions. Include the starting-state result, successful intended operation, rejected prohibited operation, reason for rejection and verified cleanup. Remove credentials and unrelated data from evidence. State which steps were not run. Do not label a lab validated on a new environment solely because its manifest was accepted.

Use the [runtime evidence record](preparation/VALIDATION.md) and [capability matrix](preparation/COMPATIBILITY.md) consistently. A verifier change needs tests showing both a correct solution and a plausible incorrect solution; a missing Pod, denied exec, unavailable tool or broken DNS must not become a security pass. Keep the verifier independent of worked-reference file contents. Test cleanup on failures as well as success when a check creates temporary resources.

The basic checks above need no cluster access or registry publication. TLS tests contact only their own loopback server. Gatekeeper decision tests use the real OPA engine and PyYAML when installed; otherwise they explicitly skip. Run them with `python3 -m unittest discover -s tests -p test_rego.py -v`, and report skipped cases accurately.

CI also runs pinned YAML, Kubernetes schema and secret validators, builds and exercises the compiled images, and creates an isolated kind/Calico cluster. Binary downloads are checksum-verified. Schema checks cover the named Kubernetes resource files; kubeconfig, node configuration, Falco rules and controller-specific custom resources are handled separately. Deliberately insecure training fixtures still require valid syntax and schemas.

Infrastructure changes also run formatting, provider-schema validation and mock-provider plans with both Terraform and OpenTofu. Keep both engine lockfiles with each profile and test changes without cloud credentials using the [infrastructure contributor checks](infrastructure/README.md#check-changes-without-creating-cloud-resources). Test lifecycle ownership and bootstrap credential handling at their command boundaries. Render changed Mermaid diagrams and keep their accompanying text useful without the diagram.

To repeat the cluster checks, create a **separate empty** kind cluster named `cks-ci` using the environment guide, then run `python3 tests/cluster_smoke.py --context kind-cks-ci`. This creates and deletes its own practice namespaces and admission policy. It refuses existing practice resources, verifies correct answers and deliberately incorrect answers, and checks native admission. Do not run it in a learner's active session. The CI workflow uses a read-only repository token and does not publish images or provision cloud resources.

## Licensing and attribution

Contribute only material you are authorized to share under the applicable [repository license](LICENSE): CC BY 4.0 for learning material, MIT for original fixtures and validation code. Identify copied/adapted material, its exact source and license, and what changed. Keep attribution specific to the affected content. A reference link by itself does not make another project's implementation reusable.

Report ordinary errors through an issue with the drill ID, expected result, observed result and environment. Never put a real credential in a public issue; revoke an exposed credential with its provider before sharing a sanitized description.
