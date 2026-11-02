# Study path

Work through one skill at a time, then combine them. Every drill has a starting state, task, proof and reset. Copy editable material into `work/`; keep the supplied fixtures as a repeatable starting point.

The domain weights below follow the [official curriculum](REFERENCES.md). The baseline is Kubernetes 1.37. First establish [your lab environment](LAB-SAFETY.md); an unavailable optional component means **blocked by environment**, not a failed skill or a simulated pass.

## Cluster setup, 15%

Read [Cluster setup](../labs/cluster-setup.md).

| ID | Practice | Environment |
|---|---|---|
| CS01 | Default deny, allowed traffic, namespace selectors and DNS | Cluster with enforcing CNI |
| CS02 | Block a controlled metadata-like endpoint selectively | Cluster plus isolated private test endpoint |
| CS03 | Find and remediate an actual CIS benchmark failure | kubeadm VMs and matching kube-bench |
| CS04 | Serve the intended hostname with a verifiable TLS certificate | Cluster with Ingress controller |
| CS05 | Verify exact platform binary identity | Local files and trusted release metadata |


## Practice rhythm

Work through the available drills, record positive and negative checks, and verify cleanup. Repeat weak skills from a fresh starting state. Keep a local copy of [Progress](PROGRESS.md) under `work/` and consult the [worked references](../solutions/README.md) after attempting a task.
