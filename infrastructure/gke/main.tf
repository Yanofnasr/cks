# SPDX-License-Identifier: MIT
locals {
  region = join("-", slice(split("-", var.zone), 0, length(split("-", var.zone)) - 1))
  labels = {
    purpose    = "cks-practice"
    expires-on = var.expires_on
  }
}

resource "google_compute_network" "lab" {
  project                 = var.project_id
  name                    = "${var.name}-net"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "lab" {
  project                  = var.project_id
  name                     = "${var.name}-subnet"
  region                   = local.region
  network                  = google_compute_network.lab.id
  ip_cidr_range            = "10.50.0.0/20"
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "cks-pods"
    ip_cidr_range = "10.60.0.0/16"
  }
  secondary_ip_range {
    range_name    = "cks-services"
    ip_cidr_range = "10.70.0.0/20"
  }
}

resource "google_compute_router" "lab" {
  project = var.project_id
  name    = "${var.name}-router"
  region  = local.region
  network = google_compute_network.lab.id
}

resource "google_compute_router_nat" "lab" {
  project                            = var.project_id
  name                               = "${var.name}-nat"
  region                             = local.region
  router                             = google_compute_router.lab.name
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = google_compute_subnetwork.lab.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
}

resource "google_service_account" "nodes" {
  project      = var.project_id
  account_id   = "${var.name}-nodes"
  display_name = "${var.name} GKE nodes"
}

resource "google_project_iam_member" "nodes" {
  project = var.project_id
  role    = "roles/container.defaultNodeServiceAccount"
  member  = "serviceAccount:${google_service_account.nodes.email}"
}

resource "google_container_cluster" "lab" {
  project               = var.project_id
  name                  = var.name
  location              = var.zone
  min_master_version    = var.kubernetes_version
  network               = google_compute_network.lab.id
  subnetwork            = google_compute_subnetwork.lab.id
  networking_mode       = "VPC_NATIVE"
  datapath_provider     = "ADVANCED_DATAPATH"
  initial_node_count    = 0
  deletion_protection   = false
  enable_legacy_abac    = false
  enable_shielded_nodes = true
  resource_labels       = local.labels

  release_channel {
    channel = "REGULAR"
  }
  ip_allocation_policy {
    cluster_secondary_range_name  = "cks-pods"
    services_secondary_range_name = "cks-services"
  }
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }
  master_authorized_networks_config {
    gcp_public_cidrs_access_enabled = false
    cidr_blocks {
      cidr_block   = var.admin_cidr
      display_name = "lab-administrator"
    }
  }
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
  master_auth {
    client_certificate_config {
      issue_client_certificate = false
    }
  }

  depends_on = [google_project_iam_member.nodes, google_compute_router_nat.lab]
}

resource "google_container_node_pool" "lab" {
  project    = var.project_id
  name       = "practice"
  location   = var.zone
  cluster    = google_container_cluster.lab.id
  version    = var.kubernetes_version
  node_count = 2

  # GKE-maintained upgrades must not become downgrade plans.
  lifecycle {
    ignore_changes = [version]
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
  node_config {
    machine_type    = "e2-standard-2"
    disk_size_gb    = 30
    disk_type       = "pd-balanced"
    image_type      = "COS_CONTAINERD"
    service_account = google_service_account.nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = local.labels
    metadata = {
      disable-legacy-endpoints = "true"
    }
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
}
