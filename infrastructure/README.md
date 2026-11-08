# Provision a practice environment

For the first session, [create the local kind environment](../preparation/ENVIRONMENTS.md#kind-with-calico). Use the cloud profiles below when you want provider experience or dedicated VMs for host and control-plane practice. Each profile owns a separate set of resources and has its own plan, state and teardown.

| Profile | Creates | Connection and learning path |
|---|---|---|
| [EKS](eks/README.md) | Dedicated VPC, private managed Linux nodes and an EKS control plane | AWS identity, isolated kubeconfig; check the network-policy fixture restrictions |
| [AKS](aks/README.md) | Dedicated resource group, Linux nodes and Azure CNI powered by Cilium | Entra group access and isolated kubeconfig |
| [GKE](gke/README.md) | Dedicated VPC, private nodes, Cloud NAT and Dataplane V2 | Google identity and isolated kubeconfig |
| [kubeadm on GCP](kubeadm-gcp/README.md) | Two dedicated Ubuntu VMs and restricted networking | SSH bootstrap, then full control-plane and host practice |

Choose using the [drill compatibility map](../preparation/COMPATIBILITY.md). A managed control plane and a kubeadm VM offer different administrative capabilities; the exercises make that boundary part of the learning.

## The same lifecycle for each cloud

1. Read the profile's prerequisites and verify the intended account, subscription or project.
2. Copy its Terraform files and lockfile into a new directory under ignored `work/`. Keep separate state for each environment.
3. Fill in local variables using the example. Supply your actual administrator IPv4 `/32`, supported Kubernetes version and identity. Never put a private key, password or cloud token in the variables.
4. Initialize and validate, then create a saved plan. Read the resources, access rules and estimated operating costs before applying that exact plan.
5. Follow the profile's connection step, run preflight, and continue with the [first session](../preparation/LAB-SAFETY.md#first-session).
6. Finish drill cleanup, review a destroy plan, apply it, and confirm the provider resources are gone before removing the local state.

Use either Terraform or OpenTofu consistently for an environment. Provider versions and checksums are locked for each engine. The profile READMEs show how to select the corresponding lockfile: for OpenTofu, copy `.tofu.lock.hcl` to `.terraform.lock.hcl` in the private working directory before initialization, then use `tofu` for the remaining commands. Keep the source lockfiles unchanged. Do not alternate engines against the same active state without following their documented migration procedure.

## Keep access and state private

Cloud profiles create billable nodes and networking. An expiry tag is a reminder, not automatic deletion. Set a budget alert and schedule the teardown before starting. Stopping VMs or deleting Kubernetes namespaces does not remove the whole environment.

The profiles restrict the public API or SSH entry point to the administrator's `/32`; do not widen it to work around a changed VPN address. Update the input and review the resulting plan. Internal node communication stays within the dedicated network. Use a dedicated training account or project with only the permissions required by the selected profile.

Terraform state and saved plans can contain sensitive data, including provider-returned connection details even when outputs are marked sensitive. Keep the working directory private (`umask 077`), never commit it, and do not upload plans or state as CI artifacts. For a shared environment, configure an encrypted access-controlled remote backend with locking before the first apply. These profiles use individual local state by default and do not provision a backend or share credentials.

Resource ownership comes from the selected state, not just a name or tag. Do not import unrelated resources into these practice states. Keep provider-managed LoadBalancers, disks and external add-ons in your cleanup inventory. Remove exercise-created load balancers while their controllers still run, then destroy the infrastructure.

## Check changes without creating cloud resources

Every root includes mock-provider tests. They exercise planned network, identity and configuration contracts without cloud credentials or resource creation:

```bash
terraform -chdir=infrastructure/eks init -backend=false
terraform -chdir=infrastructure/eks validate
terraform -chdir=infrastructure/eks test
```

Repeat for the other roots, using the same engine throughout. The CI workflow runs these checks and formatting alongside the workbook tests. Mock plans test the declared configuration; regional availability, quotas and organization policies are evaluated by the real plan and apply in your chosen account.
