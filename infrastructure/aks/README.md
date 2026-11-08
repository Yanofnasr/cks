# AKS practice environment

This profile creates a dedicated resource group and a two-node AKS cluster in Standard mode. It uses the Free control-plane SKU, Azure CNI Overlay with Cilium, an API endpoint restricted to your public IPv4 `/32`, and Entra authentication with native Kubernetes RBAC. Worker nodes have no individual public IP addresses. Azure manages their network and load balancer in the separate node resource group.

The supplied Entra groups administer this disposable cluster so members can practice namespaces, admission and impersonation. Local administrator credentials are disabled. The module creates no Entra groups, service-principal secrets or private SSH keys, and exports no kubeconfig or tokens.

## Prepare

Run commands from the repository root. Install Terraform or OpenTofu 1.7+, Azure CLI, kubelogin, kubectl and Python 3.11+. Use an existing training subscription and Entra security group whose members may administer the lab. The signed-in user must belong to that group and have permission to create AKS and a dedicated resource group, and to retrieve the cluster's user credentials. Cluster creation does not add your user to the Entra group.

Set `LAB_SUBSCRIPTION`, `LAB_TENANT` and `LAB_LOCATION` to the intended subscription, tenant and Azure region. Authenticate to that tenant and inspect the exact account/version availability:

```bash
az login --tenant "$LAB_TENANT"
az account show --subscription "$LAB_SUBSCRIPTION" --query '{subscription:id,tenant:tenantId,name:name}'
az aks get-versions --subscription "$LAB_SUBSCRIPTION" --location "$LAB_LOCATION" --output table
```

The subscription needs the `Microsoft.ContainerService`, `Microsoft.Compute`, `Microsoft.Network` and `Microsoft.ManagedIdentity` resource providers registered. This configuration does not change subscription-wide registrations automatically. Check each using `az provider show --subscription "$LAB_SUBSCRIPTION" --namespace PROVIDER --query registrationState -o tsv`; arrange registration with the subscription administrator if needed. Confirm quota and availability for two `Standard_D4s_v5` nodes (eight vCPUs total). This meets the [four-vCPU system-pool minimum](https://learn.microsoft.com/en-us/azure/aks/use-system-pools); include that size in the cost review.

Choose a unique `cks-` name. Both `<name>-rg` and `<name>-nodes` must be absent before creation. Confirm with `az group exists --subscription "$LAB_SUBSCRIPTION" --name GROUP`; a successful result must say `false`. Never import existing shared resources into this lab's state.

Nodes, disks, load balancers and outbound traffic are billable. Set a budget alert and choose a deletion date. The `expires-on` tag records that date; it does not stop billing or delete resources. The Pod range `10.244.0.0/16` and Service range `10.96.0.0/16` must not overlap networks you intend to connect.

## Plan and create

Keep state, plans, variable files and kubeconfig under ignored `work/`. Use a fresh directory for each environment. The `&&` chain preserves an existing directory instead of overwriting it:

```bash
umask 077
export TF=terraform # Use tofu here for OpenTofu.
LOCKFILE=.terraform.lock.hcl
if [ "$TF" = tofu ]; then LOCKFILE=.tofu.lock.hcl; fi
export LAB_DIR="$PWD/work/aks"
mkdir -p work && mkdir -m 700 "$LAB_DIR" && \
  cp infrastructure/aks/*.tf "$LAB_DIR/" && \
  cp "infrastructure/aks/$LOCKFILE" "$LAB_DIR/.terraform.lock.hcl" && \
  cp infrastructure/aks/terraform.tfvars.example "$LAB_DIR/terraform.tfvars"
```

Edit `work/aks/terraform.tfvars`: replace the example subscription/tenant/group IDs, name, region, version, address and date. `kubernetes_version` must be an exact patch offered in the chosen region. `admin_cidr` is your workstation or VPN's current public IPv4 address with `/32`. Group IDs identify existing Entra security groups, not users or applications. Keep credentials out of this file and use the Azure CLI's normal authentication.

```bash
"$TF" -chdir="$LAB_DIR" init -lockfile=readonly
"$TF" -chdir="$LAB_DIR" validate
"$TF" -chdir="$LAB_DIR" plan -out=create.tfplan
```

Read the plan, including subscription, names, location, administrator groups and API address restriction. Apply only that reviewed plan:

```bash
"$TF" -chdir="$LAB_DIR" apply create.tfplan
```

Use the same engine, directory and selected lockfile for the environment's full lifetime. Both engines read the copied file as `.terraform.lock.hcl`. Protect state and plan files as private data. Azure can rotate the node OS image; record the actual Kubernetes, OS and runtime versions in your practice log.

## Connect and practice

Choose a new kubeconfig filename. If the file already exists, select another name rather than overwriting it. Read the non-secret connection command, then run it exactly as shown:

```bash
export KUBECONFIG="$LAB_DIR/kubeconfig"
test ! -e "$KUBECONFIG" && "$TF" -chdir="$LAB_DIR" output -raw connect_command
```

After running that command:

```bash
kubelogin convert-kubeconfig -l azurecli --kubeconfig "$KUBECONFIG"
export LAB_CONTEXT="$("$TF" -chdir="$LAB_DIR" output -raw context_name)"
kubectl --context "$LAB_CONTEXT" get nodes -o wide
kubectl --context "$LAB_CONTEXT" wait nodes --all --for=condition=Ready --timeout=300s
python3 scripts/lab.py --context "$LAB_CONTEXT" preflight
```

If Entra access is denied, verify group membership, tenant and the current Azure CLI login. Preserve local-account disabling; do not switch to `--admin` credentials. A changed workstation/VPN address requires a reviewed `admin_cidr` update in the same Terraform state.

Continue with the [shared baseline and first session](../../preparation/LAB-SAFETY.md#first-session), using this exact kubeconfig and context. Consult the [drill matrix](../../preparation/COMPATIBILITY.md) for host/control-plane exercises. Network-policy drills use the cluster's actual DNS resolver; Cilium and Calico need not interpret every IP-based policy identically.

## Finish and delete

Finish the active drill's cleanup. Remove any practice Ingress or LoadBalancer resources while their controllers still run. Review the dedicated groups before deletion:

```bash
LAB_GROUP="$("$TF" -chdir="$LAB_DIR" output -raw resource_group_name)"
LAB_NODE_GROUP="$("$TF" -chdir="$LAB_DIR" output -raw node_resource_group_name)"
az resource list --subscription "$LAB_SUBSCRIPTION" --resource-group "$LAB_GROUP" --output table
az resource list --subscription "$LAB_SUBSCRIPTION" --resource-group "$LAB_NODE_GROUP" --output table
"$TF" -chdir="$LAB_DIR" plan -destroy -out=destroy.tfplan
```

Confirm every planned deletion belongs to this session. Keep these group names available for the final check, then apply the reviewed destruction plan:

```bash
"$TF" -chdir="$LAB_DIR" apply destroy.tfplan
az group exists --subscription "$LAB_SUBSCRIPTION" --name "$LAB_GROUP"
az group exists --subscription "$LAB_SUBSCRIPTION" --name "$LAB_NODE_GROUP"
"$TF" -chdir="$LAB_DIR" state list
```

Both group-existence results must be `false`, and state should contain no managed resources. Check any separately created disks, public addresses or external resources as well. If resource-group deletion is blocked by unexpected contents, inspect them; do not disable the provider's protection to force deletion. Retain the state until cleanup is confirmed, then remove only this lab's local credentials and files.

## Configuration checks

The provider is pinned in `versions.tf` and the engine-specific lockfiles. Use the `TF` and `LOCKFILE` selection above. These checks run in a temporary copy, validating configuration and using mock providers for the security assertions:

```bash
(
set -eu
CHECK_DIR=$(mktemp -d)
trap 'rm -r "$CHECK_DIR"' EXIT
cp infrastructure/aks/*.tf "$CHECK_DIR/"
cp -R infrastructure/aks/tests "$CHECK_DIR/"
cp "infrastructure/aks/$LOCKFILE" "$CHECK_DIR/.terraform.lock.hcl"
"$TF" -chdir="$CHECK_DIR" init -backend=false -lockfile=readonly
"$TF" -chdir="$CHECK_DIR" fmt -check -recursive
"$TF" -chdir="$CHECK_DIR" validate
"$TF" -chdir="$CHECK_DIR" test
)
```

References: [AzureRM AKS resource](https://registry.terraform.io/providers/hashicorp/azurerm/5.13.0/docs/resources/kubernetes_cluster), [managed Entra integration](https://learn.microsoft.com/en-us/azure/aks/enable-authentication-microsoft-entra-id), [Azure CLI login with kubelogin](https://learn.microsoft.com/en-us/azure/aks/kubelogin-authentication), [Azure CNI powered by Cilium](https://learn.microsoft.com/en-us/azure/aks/azure-cni-powered-by-cilium), [API authorized ranges](https://learn.microsoft.com/en-us/azure/aks/api-server-authorized-ip-ranges).
