# CKS practice

Hands-on preparation for the Certified Kubernetes Security Specialist exam: **36 focused drills, one capstone, and reusable practice fixtures**. Exercises map to the published CKS objectives, with explicit starting states, positive and negative checks, and scoped cleanup.

Intended for learners who already administer Kubernetes at CKA level. There are no recalled exam questions, predictions of particular tasks, or passing-score guarantees.

## Start here

1. Prepare a disposable environment using [Lab setup](preparation/LAB-SAFETY.md).
2. Follow the [study path](preparation/STUDY-PATH.md), beginning with network isolation and ServiceAccounts.
3. Copy starter files into `work/`, solve the task, and prove both allowed and denied behavior.
4. Copy [the progress template](preparation/PROGRESS.md) into `work/PROGRESS.md` and record results there.

| Domain | Exercises |
|---|---|
| Cluster setup | [Networking, metadata, CIS, TLS and binary integrity](labs/cluster-setup.md) |
| Cluster hardening | [RBAC, identities, API server, kubelet and upgrades](labs/cluster-hardening.md) |
| System hardening | [Services, firewall rules, OS permissions, AppArmor and seccomp](labs/system-hardening.md) |
| Workload security | [PSA, security contexts, Secrets, isolation and mTLS](labs/workload-security.md) |
| Supply chain | [Images, static analysis, scanning, digests, signatures, SBOMs and admission](labs/supply-chain.md) |
| Runtime security | [Falco, auditing, immutability and incident response](labs/runtime-security.md) |
| Mixed practice | [45-minute capstone](labs/capstone.md) |

The target baseline is **Kubernetes 1.37**. See the [curriculum map](preparation/CURRICULUM.md) for objective coverage and [References](preparation/REFERENCES.md) for current exam rules, authoritative technical guidance and optional practice environments.

Commands assume the repository root and a lab-only kubeconfig. Node exercises require disposable VMs; mesh, runtime and scanner exercises state their additional prerequisites. This repository does not provision those components or award automatic passing scores. A working application and meaningful negative checks are part of every result.

## Check, learn and contribute

After attempting the core drills, compare with the [worked references](solutions/README.md). Adapt environment-specific assumptions and run the proof steps; a reference manifest alone is not a passing result.

Run the repository checks with Python 3.11 or newer:

```bash
python3 scripts/check.py
python3 -m unittest discover -s tests -v
```

These offline checks cover documentation consistency and JSON fixtures. They do not validate Kubernetes schemas, CEL execution, external URL availability, controller compatibility or live lab behavior. No complete runtime validation matrix is published yet. See [Contributing](CONTRIBUTING.md) for the evidence expected when adding or validating a lab.

Learning material is **CC BY 4.0**; original fixtures and validation code are **MIT**. See [LICENSE](LICENSE) for the boundaries and [Acknowledgements](ACKNOWLEDGEMENTS.md) for the three adapted exercises. Keep credentials and generated results under ignored `work/`.
