# SPDX-License-Identifier: MIT
mock_provider "google" {
  mock_resource "google_service_account" {
    defaults = {
      email = "cks-practice-nodes@cks-training-example.iam.gserviceaccount.com"
    }
  }
}

variables {
  project_id         = "cks-training-example"
  zone               = "europe-west1-b"
  name               = "cks-practice"
  kubernetes_version = "1.37.0-gke.1000000"
  admin_cidr         = "203.0.113.10/32"
  expires_on         = "2026-11-15"
}

run "private_nodes_and_scoped_control_plane" {
  command = plan

  assert {
    condition = (
      google_container_cluster.lab.private_cluster_config[0].enable_private_nodes &&
      !google_container_cluster.lab.private_cluster_config[0].enable_private_endpoint &&
      !google_container_cluster.lab.master_authorized_networks_config[0].gcp_public_cidrs_access_enabled &&
      length(google_container_cluster.lab.master_authorized_networks_config[0].cidr_blocks) == 1 &&
      one(google_container_cluster.lab.master_authorized_networks_config[0].cidr_blocks).cidr_block == var.admin_cidr
    )
    error_message = "Nodes must be private and the public API must accept only the administrator's /32."
  }

  assert {
    condition = (
      !google_compute_network.lab.auto_create_subnetworks &&
      google_compute_subnetwork.lab.private_ip_google_access &&
      length(google_compute_subnetwork.lab.secondary_ip_range) == 2 &&
      google_compute_router_nat.lab.source_subnetwork_ip_ranges_to_nat == "LIST_OF_SUBNETWORKS"
    )
    error_message = "Use one dedicated VPC-native subnet and scope NAT to that subnet."
  }

  assert {
    condition = (
      google_container_cluster.lab.location == var.zone &&
      google_container_cluster.lab.min_master_version == var.kubernetes_version &&
      google_container_cluster.lab.datapath_provider == "ADVANCED_DATAPATH" &&
      google_container_cluster.lab.initial_node_count == 0 &&
      google_container_node_pool.lab.node_count == 2 &&
      google_container_node_pool.lab.location == var.zone
    )
    error_message = "The profile must remain zonal with two permanent nodes and Dataplane V2."
  }

  assert {
    condition = (
      google_service_account.nodes.account_id == "${var.name}-nodes" &&
      google_project_iam_member.nodes.role == "roles/container.defaultNodeServiceAccount" &&
      google_project_iam_member.nodes.project == var.project_id &&
      google_container_cluster.lab.workload_identity_config[0].workload_pool == "${var.project_id}.svc.id.goog" &&
      google_container_node_pool.lab.node_config[0].workload_metadata_config[0].mode == "GKE_METADATA" &&
      google_container_node_pool.lab.node_config[0].shielded_instance_config[0].enable_secure_boot &&
      google_container_node_pool.lab.node_config[0].shielded_instance_config[0].enable_integrity_monitoring &&
      !google_container_cluster.lab.enable_legacy_abac &&
      !google_container_cluster.lab.master_auth[0].client_certificate_config[0].issue_client_certificate
    )
    error_message = "Keep workload identity, minimal node IAM and modern node/authentication controls."
  }

  assert {
    condition = (
      google_container_cluster.lab.resource_labels["expires-on"] == var.expires_on &&
      !google_container_cluster.lab.deletion_protection &&
      output.context == "gke_${var.project_id}_${var.zone}_${var.name}"
    )
    error_message = "Keep the teardown reminder, disposable lifecycle and explicit connection scope."
  }
}

run "reject_open_api" {
  command = plan
  variables {
    admin_cidr = "0.0.0.0/0"
  }
  expect_failures = [var.admin_cidr]
}

run "reject_shared_admin_network" {
  command = plan
  variables {
    admin_cidr = "203.0.113.0/24"
  }
  expect_failures = [var.admin_cidr]
}

run "reject_ipv6_admin_network" {
  command = plan
  variables {
    admin_cidr = "2001:db8::1/128"
  }
  expect_failures = [var.admin_cidr]
}

run "reject_regional_node_multiplication" {
  command = plan
  variables {
    zone = "europe-west1"
  }
  expect_failures = [var.zone]
}
