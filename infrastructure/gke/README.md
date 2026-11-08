# GKE practice infrastructure

This profile creates a dedicated VPC, subnet, Cloud NAT, node service account and a **zonal GKE Standard cluster with two private Linux nodes**. Dataplane V2 provides network-policy enforcement. The public Kubernetes API is restricted to one administrator IPv4 `/32`; nodes use the private control-plane endpoint. Workload Identity separates workload access from the node identity.

Use the [compatibility map](../../preparation/COMPATIBILITY.md) to choose exercises. Node and control-plane administration tasks use the separate kubeadm profile. Review the resources and cost before applying: the cluster, nodes, disks, NAT and network traffic are billable. `expires_on` is a teardown reminder, not an automatic shutdown.

## Prepare

Use Terraform or OpenTofu **1.7 or newer**, gcloud, `gke-gcloud-auth-plugin`, kubectl matching the selected cluster version, and Python 3.11+. The examples use `terraform`; substitute `tofu` consistently when using OpenTofu. Choose one engine for the lab and use its supplied dependency lockfile throughout creation, updates and teardown.

Choose an existing dedicated, billing-enabled training project with `compute.googleapis.com`, `container.googleapis.com`, `iam.googleapis.com` and `cloudresourcemanager.googleapis.com` enabled. Its organization policies must allow this profile's public API endpoint and private nodes. The operator needs permission to manage GKE, the dedicated network/NAT and service account, its project IAM grant, and to use that service account. Use a training administrator identity with the Kubernetes administration and impersonation permissions checked by preflight. Terraform uses Application Default Credentials; it does not accept credentials in variables.

Authenticate with the intended training identity. Confirm the CLI account and project, and select an exact Kubernetes 1.37 or newer version offered in the zone's REGULAR release channel:

```bash
gcloud auth login
gcloud auth application-default login
gcloud auth list --filter=status:ACTIVE
gcloud projects describe YOUR_PROJECT_ID --format='value(projectId,projectNumber)'
gcloud services list --enabled --project YOUR_PROJECT_ID
gcloud container get-server-config --project YOUR_PROJECT_ID --zone europe-west1-b
```

Choose the same identity in both authentication flows. Replace the project and zone above. Select an unused `cks-` name. The dedicated address ranges are `10.50.0.0/20` for nodes, `10.60.0.0/16` for Pods, `10.70.0.0/20` for Services and `172.16.0.0/28` for the control plane. Keep this network separate from connected networks with overlapping ranges.

From the repository root, prepare a new private working directory. Stop if it already exists; reuse its existing state for an existing lab rather than overwriting it:

```bash
(
set -eu
umask 077
mkdir -p work
mkdir work/gke
cp infrastructure/gke/*.tf infrastructure/gke/.terraform.lock.hcl work/gke/
cp infrastructure/gke/terraform.tfvars.example work/gke/terraform.tfvars
)
```

The block above selects the Terraform lockfile. For **OpenTofu**, replace only the new working copy's lockfile before initialization:

```bash
cp infrastructure/gke/.tofu.lock.hcl work/gke/.terraform.lock.hcl
```

OpenTofu also reads `.terraform.lock.hcl` in the working directory; `.tofu.lock.hcl` is the supplied OpenTofu-specific source. Keep the selected lockfile and use `init -lockfile=readonly`; no `-upgrade` is needed.

Edit `work/gke/terraform.tfvars`: set the exact project, zone, offered version, unique name, your actual public IPv4 `/32`, and planned teardown date. The example address is documentation-only. A changed VPN/public address requires a reviewed change to `admin_cidr`. Keep state, saved plans and variables private under `work/`.

## Plan and create

```bash
(
set -eu
terraform -chdir=work/gke init -lockfile=readonly
terraform -chdir=work/gke fmt -check
terraform -chdir=work/gke validate
terraform -chdir=work/gke plan -out=create.tfplan
terraform -chdir=work/gke show create.tfplan
)
```

Inspect the selected project, names, administrator address, node count and billable resources. The plan must create a new lab without replacing unrelated resources. Apply that saved plan only after reviewing it:

```bash
terraform -chdir=work/gke apply create.tfplan
```

The cluster is created without a default node pool; the separate managed pool supplies the two private nodes. GKE's REGULAR channel can subsequently upgrade the control plane and nodes; record the versions used for each practice session. Auto-repair remains enabled.

## Connect and practice

Keep the kubeconfig beside this lab's state. These commands refuse an existing kubeconfig so an earlier cluster identity is not silently replaced. On a later visit, export the same existing file instead of regenerating it:

```bash
umask 077
export KUBECONFIG="$PWD/work/gke/kubeconfig"
test ! -e "$KUBECONFIG" && terraform -chdir=work/gke output -raw connect_command
```

Run the displayed `gcloud container clusters get-credentials` command after checking its project, zone and cluster name. It writes only the selected kubeconfig. Then:

```bash
export LAB_CONTEXT="$(terraform -chdir=work/gke output -raw context)"
kubectl --context "$LAB_CONTEXT" get nodes -o wide
kubectl --context "$LAB_CONTEXT" wait nodes --all --for=condition=Ready --timeout=300s
python3 scripts/lab.py --context "$LAB_CONTEXT" preflight
```

Continue with the [shared baseline and first session](../../preparation/LAB-SAFETY.md#first-session). Inspect the actual DNS resolver when writing NetworkPolicies. The dedicated node identity receives `roles/container.defaultNodeServiceAccount`, not Editor; workload permissions still need their own explicit configuration.

## Finish and destroy

Complete each drill's cleanup first. Delete exercise-created Ingresses, LoadBalancer Services and persistent-volume claims while their controllers are still running, then verify that their provider resources have been removed. Preserve the state directory until teardown is complete.

```bash
terraform -chdir=work/gke plan -destroy -out=destroy.tfplan
terraform -chdir=work/gke show destroy.tfplan
```

Confirm that only this lab's cluster, node pool, dedicated network/NAT and node identity/grant are being removed. Deletion protection is disabled deliberately for this disposable profile. Apply the reviewed destroy plan:

```bash
terraform -chdir=work/gke apply destroy.tfplan
terraform -chdir=work/gke state list
```

The final state list should be empty. Check the project's cluster, disk, load-balancer and network inventory for exercise-created leftovers before removing local credentials or state. Project APIs remain enabled because this profile does not manage them.

## Configuration checks

These checks validate the configuration and security assertions without cloud credentials or resource creation. The test provider is mocked and each test uses a plan. Mock testing requires Terraform 1.7+ or OpenTofu 1.8+:

```bash
terraform -chdir=infrastructure/gke fmt -check -recursive
terraform -chdir=infrastructure/gke init -backend=false -lockfile=readonly
terraform -chdir=infrastructure/gke validate
terraform -chdir=infrastructure/gke test
```

For OpenTofu checks, use a separate copy of the `.tf` files and `tests/` directory, copy `.tofu.lock.hcl` into that directory as `.terraform.lock.hcl`, then run the same commands with `tofu`. Preserve both source lockfiles.

Primary references: [Google provider](https://registry.terraform.io/providers/hashicorp/google/8.10.0/docs), [GKE cluster resource](https://registry.terraform.io/providers/hashicorp/google/8.10.0/docs/resources/container_cluster), [Dataplane V2](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/dataplane-v2), [node service accounts](https://docs.cloud.google.com/kubernetes-engine/security/configure-node-service-accounts), [private clusters and authorized networks](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/latest/network-isolation).
