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

Keep starter fixtures reproducible; place proposed answers in `solutions/` and label incomplete or environment-specific parts. Avoid broad host resets, installers, global policy deletion and automatic success fallbacks.

## Validate a contribution

Run these from the repository root with Python 3.11 or newer:

```bash
python3 scripts/check.py
python3 -m unittest discover -s tests -v
git diff --check
```

The checker uses only the Python standard library. Its scope is local Markdown links/anchors, drill consistency and JSON/JSONL syntax. It is not a Markdown renderer, YAML/schema validator, security scanner or Kubernetes grader. Describe additional static tools you ran, including versions, instead of implying these commands cover them.

For a runtime claim, use disposable infrastructure and report the Kubernetes version, OS, architecture, runtime, CNI and relevant tool/controller versions. Include the starting-state result, successful intended operation, rejected prohibited operation, reason for rejection and verified cleanup. Remove credentials and unrelated data from evidence. State which steps were not run. Do not label a lab validated on a new environment solely because its manifest was accepted.

No cluster access, registry publication or remote installation is needed to run the repository checks. The CI workflow runs the same offline checks with a read-only repository token.

## Licensing and attribution

Contribute only material you are authorized to share under the applicable [repository license](LICENSE): CC BY 4.0 for learning material, MIT for original fixtures and validation code. Identify copied/adapted material, its exact source and license, and what changed. Keep attribution specific to the affected content. A reference link by itself does not make another project's implementation reusable.

Report ordinary errors through an issue with the drill ID, expected result, observed result and environment. Never put a real credential in a public issue; revoke an exposed credential with its provider before sharing a sanitized description.
