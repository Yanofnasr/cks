# EKS practice infrastructure

This profile creates a dedicated VPC, two private Linux workers, an EKS control plane, one NAT gateway, scoped IAM roles and seven-day control-plane logs. The API has a private endpoint for nodes and a public endpoint restricted to one administrator IPv4 `/32`. It adds an explicit administrator access entry; the identity that provisions the cluster receives no implicit Kubernetes administrator grant.

Use this route for the [EKS-compatible exercises](../../preparation/COMPATIBILITY.md). Amazon VPC CNI has a documented standalone-Pod NetworkPolicy restriction, so use the local kind route for CS01/CS06 and the networking capstone with the supplied fixtures. Use kubeadm VMs for control-plane file, etcd and host configuration practice.

## Prepare

Install Terraform or OpenTofu 1.7+ and AWS CLI v2. Use a dedicated training account, an existing provisioning profile with permission to create the listed resources, and an existing IAM role or user for lab administration. This root targets the commercial AWS partition. Verify quota for two `t3.medium` workers and check that `10.80.0.0/16` does not overlap networks you need to reach.

The control plane, workers, NAT gateway, public IPv4 address, storage and logs incur charges. The `ExpiresOn` tag records your removal date; it does not stop billing or delete resources. Set a budget alert independently.

From the repository root, reserve a new private state directory. If `work/eks` already exists, reuse its existing state intentionally or choose a different directory; do not overwrite it:

```bash
(
set -eu
umask 077
mkdir -p work
mkdir work/eks
cp infrastructure/eks/*.tf infrastructure/eks/.terraform.lock.hcl work/eks/
cp infrastructure/eks/terraform.tfvars.example work/eks/terraform.tfvars
)
```

After creating the directory, select the training profile and inspect the account and available versions:

```bash
export AWS_PROFILE=training
aws sts get-caller-identity
aws eks describe-cluster-versions --region eu-west-1
aws ec2 describe-availability-zones --region eu-west-1 \
  --query 'AvailabilityZones[?State==`available`].ZoneName' --output text
```

Replace `eu-west-1` with your chosen region in the discovery commands. Edit **every placeholder** in `work/eks/terraform.tfvars`: account, region, two zones, unique `cks-` name, your actual public IPv4 `/32`, existing administrator IAM ARN, an offered Kubernetes minor and removal date. EKS takes a minor such as `1.37`; select its exact worker AMI release separately. Query the matching Amazon Linux 2023 x86_64 release before planning:

```bash
aws ssm get-parameter --region eu-west-1 \
  --name /aws/service/eks/optimized-ami/1.37/amazon-linux-2023/x86_64/standard/recommended/release_version \
  --query Parameter.Value --output text
```

Use the selected region/minor in that command and copy its returned release into `node_release_version`. The AMI is pinned to that value. The managed VPC CNI add-on selects an AWS-compatible initial version; record its deployed version alongside your Kubernetes/runtime versions before practice. Keep the dependency lockfile with the configuration.

The administrator input is an IAM `role/...` or `user/...` ARN in the training account. A temporary `arn:aws:sts::...:assumed-role/...` session ARN is not an access-entry principal. If provisioning and practice use different profiles, retain both identities in your session notes and switch to the administrator profile before connecting.

## Review and create

Choose the engine before the first initialization. The setup above copies the Terraform lockfile. For OpenTofu, replace that copy with the supplied OpenTofu lockfile, which records the provider package checksums accepted by that engine:

```bash
cp infrastructure/eks/.tofu.lock.hcl work/eks/.terraform.lock.hcl
```

The remaining commands use Terraform; replace `terraform` with `tofu` when using OpenTofu. Keep the chosen engine and its lockfile together for this state directory. `-chdir` keeps state and plans inside the private working directory:

```bash
terraform -chdir=work/eks init -lockfile=readonly
terraform -chdir=work/eks fmt -check
terraform -chdir=work/eks validate
terraform -chdir=work/eks plan -out=create.tfplan
terraform -chdir=work/eks show create.tfplan
```

Review the account, region, CIDR, resource names, IAM grants and resource count. Continue only with the intended creation plan:

```bash
terraform -chdir=work/eks apply create.tfplan
terraform -chdir=work/eks output
```

The state manages this dedicated stack only. Do not import shared resources into it. Keep state, plans, `.terraform/`, variable files and kubeconfigs in ignored `work/`; state can contain infrastructure identifiers and sensitive provider data even when outputs omit credentials.

## Connect and practice

Select the AWS profile for `admin_principal_arn`; it also needs the AWS `eks:DescribeCluster` permission to retrieve connection details. The EKS access policy grants Kubernetes permissions separately. Query the outputs instead of guessing cluster names:

```bash
aws sts get-caller-identity
LAB_REGION=$(terraform -chdir=work/eks output -raw region)
LAB_CLUSTER=$(terraform -chdir=work/eks output -raw cluster_name)
export KUBECONFIG="$PWD/work/eks/kubeconfig"
export LAB_CONTEXT="$LAB_CLUSTER"
(
set -eu
umask 077
test ! -e "$KUBECONFIG"
aws eks update-kubeconfig --region "$LAB_REGION" --name "$LAB_CLUSTER" \
  --alias "$LAB_CONTEXT" --kubeconfig "$KUBECONFIG"
)
kubectl --context "$LAB_CONTEXT" wait nodes --all --for=condition=Ready --timeout=300s
python3 scripts/lab.py --context "$LAB_CONTEXT" preflight
```

The kubeconfig uses AWS CLI authentication; keep the selected `AWS_PROFILE` in each practice shell. If the administrator's egress address changes, update `admin_cidr`, review a new plan and apply it from the recorded state. Do not open the API to all addresses to bypass a connectivity problem.

Continue with the [shared baseline](../../preparation/LAB-SAFETY.md#shared-starting-state), then CH02 and MW02. Nodes use IMDSv2 with a response hop limit of one; the VPC CNI receives its own IRSA role rather than network-management permissions on the worker role. This separates node infrastructure authority from workload credentials. The single NAT is an explicit lab cost/availability choice, not a production architecture.

## Destroy

Finish the drill-specific cleanup. Delete any lab-created Ingress, LoadBalancer Service or persistent-volume claims while their controllers are still running, and wait for provider resources to disappear. Terraform does not own resources created by Kubernetes controllers.

Use the same state directory and provisioning profile. Review a destruction plan before applying it:

```bash
aws sts get-caller-identity
terraform -chdir=work/eks plan -destroy -out=destroy.tfplan
terraform -chdir=work/eks show destroy.tfplan
terraform -chdir=work/eks apply destroy.tfplan
terraform -chdir=work/eks state list
```

The final state list should be empty. Check the recorded cluster, NAT, public IP, volumes and load balancers in the selected account/region before deleting local state or credentials. If creation failed partway through, retain the state and use a reviewed destroy plan for what Terraform created.

## Configuration checks

These commands download the pinned provider schema and execute mock-provider assertions without AWS credentials or cloud resources:

```bash
terraform -chdir=infrastructure/eks init -backend=false
terraform -chdir=infrastructure/eks validate
terraform -chdir=infrastructure/eks test
```

The tests assert private worker placement, restricted API access, explicit administrator grants, IMDSv2 settings, encrypted root disks, separate CNI authority, log retention and rejected unsafe inputs. Provider APIs still determine regional version/AMI availability and account quotas when you create the stack.

Primary references: [EKS cluster resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eks_cluster), [node IAM role](https://docs.aws.amazon.com/eks/latest/userguide/create-node-role.html), [VPC CNI role](https://docs.aws.amazon.com/eks/latest/userguide/cni-iam-role.html), [EKS API access](https://docs.aws.amazon.com/eks/latest/userguide/access-entries.html), [NetworkPolicy restrictions](https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy.html).
