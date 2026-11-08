# SPDX-License-Identifier: MIT
mock_provider "google" {}

variables {
  project_id     = "cks-training-project"
  zone           = "europe-west1-b"
  admin_cidr     = "203.0.113.10/32"
  ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA test-only"
  expires_on     = "2030-01-01"
}

run "restricted_two_node_profile" {
  command = plan

  assert {
    condition     = length(google_compute_instance.node) == 2
    error_message = "The profile must create exactly a control plane and worker."
  }
  assert {
    condition     = google_compute_firewall.ssh.source_ranges == toset([var.admin_cidr]) && google_compute_firewall.api.source_ranges == toset([var.admin_cidr])
    error_message = "SSH and the public API must be restricted to the administrator's /32."
  }
  assert {
    condition     = google_compute_firewall.api.target_tags == toset(["${var.name}-control"])
    error_message = "The API firewall rule must target only the control plane."
  }
  assert {
    condition     = google_compute_firewall.nodes.source_tags == toset(["${var.name}-node"]) && google_compute_firewall.nodes.target_tags == toset(["${var.name}-node"])
    error_message = "Internal ports must be restricted to the dedicated lab node tag."
  }
  assert {
    condition     = alltrue([for node in google_compute_instance.node : node.metadata["block-project-ssh-keys"] == "TRUE" && node.metadata["enable-oslogin"] == "FALSE"])
    error_message = "Only the explicit lab SSH key may authorize the metadata-key access path."
  }
  assert {
    condition     = alltrue([for node in google_compute_instance.node : length(node.service_account[0].scopes) == 0 && node.shielded_instance_config[0].enable_secure_boot])
    error_message = "VMs must have no OAuth scopes and retain secure boot."
  }
  assert {
    condition     = alltrue([for node in google_compute_instance.node : node.labels["expires_on"] == var.expires_on])
    error_message = "Every VM must carry the explicit cleanup date."
  }
  assert {
    condition     = !strcontains(google_compute_instance.node["control"].metadata_startup_script, "kubeadm init") && !strcontains(google_compute_instance.node["worker"].metadata_startup_script, "kubeadm join")
    error_message = "Terraform metadata must not initialize the cluster or carry join credentials."
  }
}

run "reject_open_administrator_access" {
  command = plan
  variables {
    admin_cidr = "0.0.0.0/0"
  }
  expect_failures = [var.admin_cidr]
}

run "reject_private_key_input" {
  command = plan
  variables {
    ssh_public_key = "-----BEGIN OPENSSH PRIVATE KEY-----"
  }
  expect_failures = [var.ssh_public_key]
}
