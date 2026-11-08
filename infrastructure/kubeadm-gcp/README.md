# Two-VM kubeadm practice on GCP

This profile creates a dedicated network, two Ubuntu 24.04 VMs, reserved addresses and a lab service account with no project roles. It prepares matching Kubernetes/containerd packages, then a separate SSH bootstrap command initializes the control plane, joins the worker and installs Calico. Use this environment for node, kernel, control-plane and recovery exercises.

The API is reachable only from your administrator `/32` and the lab nodes. SSH uses your public key and previously checked host keys. Internal rules allow Kubernetes node traffic, Calico BGP/VXLAN and ICMP between the two tagged nodes. etcd is not exposed through an ingress rule. Workloads do not receive a default Compute Engine service account with project privileges.

## Prepare

Use a dedicated training project with the Compute Engine API enabled and sufficient Compute, network and IAM permissions. Organization policy must permit metadata SSH keys on these lab VMs; the profile disables OS Login for its explicit `cks` key path. If your organization requires OS Login, use its approved access process rather than changing that policy.

Install Terraform or OpenTofu 1.7+, gcloud, OpenSSH, kubectl 1.37 and Python 3.11+. Authenticate using the provider's [Application Default Credentials](https://registry.terraform.io/providers/hashicorp/google/latest/docs/guides/provider_reference#authentication), without downloading a service-account key. The selected `project_id` is explicit in every resource.

The VMs are billable, each with 2 vCPUs, 8 GiB RAM and a 30 GiB disk. Reserved external IPv4 addresses also incur charges. Set a budget alert and cleanup date. The `expires_on` label is a reminder, not an automatic shutdown. The profile needs a stable administrator public IPv4 address with `/32` and nonoverlapping ranges `10.92.0.0/24` and `192.168.0.0/16`.

Run from the repository root. Choose a new directory and preserve the provider lockfile:

```bash
export LAB_DIRECTORY="$PWD/work/kubeadm-gcp"
export TF=terraform # Use tofu if that is your installed engine.
(
set -euo pipefail
umask 077
test ! -e "$LAB_DIRECTORY"
mkdir -p "$PWD/work"
mkdir -m 0700 "$LAB_DIRECTORY"
cp infrastructure/kubeadm-gcp/*.tf infrastructure/kubeadm-gcp/*.tftpl "$LAB_DIRECTORY/"
if [ "$TF" = tofu ]; then
  cp infrastructure/kubeadm-gcp/.tofu.lock.hcl "$LAB_DIRECTORY/.terraform.lock.hcl"
else
  cp infrastructure/kubeadm-gcp/.terraform.lock.hcl "$LAB_DIRECTORY/"
fi
cp infrastructure/kubeadm-gcp/terraform.tfvars.example "$LAB_DIRECTORY/terraform.tfvars"
)
```

Edit `terraform.tfvars` with your project, zone, unique `cks-` name, actual public `/32` and real cleanup date. Generate a new SSH key only if its filename is unused; use a passphrase and load it into your agent before bootstrap:

```bash
mkdir -p work/keys
ssh-keygen -t ed25519 -f work/keys/cks-kubeadm
ssh-add work/keys/cks-kubeadm
export TF_VAR_ssh_public_key="$(cat work/keys/cks-kubeadm.pub)"
```

Only the public key belongs in Terraform input. Keep the private key, state, plans, kubeconfig and logs in ignored `work/`. The pinned package defaults are Kubernetes `1.37.0-1.1` and containerd `2.3.4-2~ubuntu.24.04~noble`. A saved plan also records the exact maintained Ubuntu image selected from Google's official `ubuntu-2404-lts-amd64` family. Package versions can be deliberately changed through their validated inputs; use matching versions on both nodes.

## Plan and create

```bash
"$TF" -chdir="$LAB_DIRECTORY" init -lockfile=readonly
"$TF" -chdir="$LAB_DIRECTORY" validate
"$TF" -chdir="$LAB_DIRECTORY" plan -out=create.tfplan
"$TF" -chdir="$LAB_DIRECTORY" show create.tfplan
"$TF" -chdir="$LAB_DIRECTORY" apply create.tfplan
"$TF" -chdir="$LAB_DIRECTORY" output -json bootstrap
```

Review the plan's project, region, exact image, administrator range and resource names before applying. It should create two VMs and no project IAM role bindings. Creation does not write Kubernetes credentials into Terraform state. The startup script prepares packages and records readiness at `/var/lib/cks/prepared`; it preserves AppArmor and never resets an existing cluster.

## Verify SSH identity and bootstrap

For each node, obtain its public Ed25519 host-key fingerprint through the trusted Google Cloud serial console. The startup script prints the fingerprint after package preparation. Use the project, zone and node names from `output bootstrap`:

```bash
gcloud compute instances get-serial-port-output NODE_NAME \
  --project PROJECT_ID --zone ZONE
ssh -i work/keys/cks-kubeadm cks@NODE_PUBLIC_IP true
```

Replace the uppercase placeholders with the recorded values. Compare the SSH prompt's fingerprint with the console fingerprint before accepting the first connection. Repeat for both nodes. This establishes the entries that the bootstrap helper requires in your normal OpenSSH `known_hosts`. Do not disable host-key checking or copy an unchecked `ssh-keyscan` result into that file.

```bash
python3 scripts/bootstrap_kubeadm.py --directory "$LAB_DIRECTORY" \
  --identity-file work/keys/cks-kubeadm --engine "$TF"
```

The helper checks both fresh node identities and package readiness before changing cluster state. It initializes the API on the private address, adds the restricted public address to the serving certificate, transfers a short-lived join credential only through SSH stdin, revokes that credential after joining, verifies the downloaded Calico checksum and switches the pool to VXLAN. It waits for networking, DNS and nodes, then runs preflight.

Use the exact `export KUBECONFIG=...` and `export LAB_CONTEXT=...` commands printed after completion. Confirm the [lab identity and record its UID](../../preparation/LAB-SAFETY.md#select-the-cluster-deliberately), then follow the [shared baseline and first session](../../preparation/LAB-SAFETY.md#first-session). The kubeconfig is written with owner-only permissions. Take coordinated VM recovery snapshots before starting disruptive host/control-plane exercises; snapshots are separate billable resources that must be removed later.

## Diagnose and recover

Package preparation can take several minutes. Inspect `/var/log/cks/prepare.log` over trusted SSH if its readiness marker does not appear. Initialization details are in `/var/log/cks/init.log`, readable only by root. Keep these logs private. No command here removes AppArmor, disables package authentication or resets an existing node.

The helper refuses an existing local kubeconfig or existing cluster configuration on either VM. If bootstrap stops after initialization or joining, inspect the actual state before deciding how to recover. A fresh training environment can be recreated with the reviewed destroy/create sequence below; the helper never performs an implicit `kubeadm reset` or VM deletion. The join credential expires after ten minutes even if its cleanup request cannot reach the API.

## Teardown

Save non-secret study results. Remove exercise-created cloud resources and VM snapshots separately, then review the destruction plan using the same directory and input values:

```bash
"$TF" -chdir="$LAB_DIRECTORY" plan -destroy -out=destroy.tfplan
"$TF" -chdir="$LAB_DIRECTORY" show destroy.tfplan
"$TF" -chdir="$LAB_DIRECTORY" apply destroy.tfplan
"$TF" -chdir="$LAB_DIRECTORY" state list
```

The final state should contain no managed resources. Check the project's inventory for snapshots, detached disks or resources created manually during drills before treating cleanup as complete. Remove private local kubeconfig/key files only after they are no longer needed. Never remove the state directory to simulate infrastructure deletion.

## Contributor checks

These commands use provider mocks and do not create cloud resources:

```bash
terraform -chdir=infrastructure/kubeadm-gcp init -backend=false -lockfile=readonly
terraform -chdir=infrastructure/kubeadm-gcp fmt -check -recursive
terraform -chdir=infrastructure/kubeadm-gcp validate
terraform -chdir=infrastructure/kubeadm-gcp test
python3 -m unittest discover -s tests -p test_bootstrap_kubeadm.py -v
```

The provider schema and mock tests check configuration contracts. Bootstrap unit tests check input validation, SSH host-key requirements, credential handling and checksum failures. A runtime record belongs in [Validation](../../preparation/VALIDATION.md) after exercising the complete environment.

References: [Compute Engine instance metadata and SSH keys](https://docs.cloud.google.com/compute/docs/connect/add-ssh-keys), [Google provider instance schema](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_instance), [kubeadm initialization](https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-init/), [short-lived bootstrap tokens](https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-token/), [Calico encapsulation](https://docs.tigera.io/calico/latest/networking/configuring/vxlan-ipip).
