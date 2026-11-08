# SPDX-License-Identifier: MIT
locals {
  region             = substr(var.zone, 0, length(var.zone) - 2)
  kubernetes_version = split("-", var.kubernetes_package)[0]
  nodes = {
    control = "10.92.0.10"
    worker  = "10.92.0.11"
  }
  labels = {
    purpose    = "cks-practice"
    lab        = var.name
    expires_on = var.expires_on
  }
}

# Resolve the maintained official image during plan; the saved plan fixes its exact identity.
data "google_compute_image" "ubuntu" {
  project = "ubuntu-os-cloud"
  family  = "ubuntu-2404-lts-amd64"
}

resource "google_compute_network" "lab" {
  name                    = var.name
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "lab" {
  name          = var.name
  region        = local.region
  network       = google_compute_network.lab.id
  ip_cidr_range = "10.92.0.0/24"
}

resource "google_service_account" "nodes" {
  account_id   = "${var.name}-nodes"
  display_name = "${var.name} VMs, no project roles"
}

resource "google_compute_address" "node" {
  for_each = local.nodes
  name     = "${var.name}-${each.key}"
  region   = local.region
}

resource "google_compute_firewall" "ssh" {
  name          = "${var.name}-ssh"
  network       = google_compute_network.lab.name
  source_ranges = [var.admin_cidr]
  target_tags   = ["${var.name}-node"]
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_compute_firewall" "api" {
  name          = "${var.name}-api"
  network       = google_compute_network.lab.name
  source_ranges = [var.admin_cidr]
  target_tags   = ["${var.name}-control"]
  allow {
    protocol = "tcp"
    ports    = ["6443"]
  }
}

resource "google_compute_firewall" "nodes" {
  name        = "${var.name}-nodes"
  network     = google_compute_network.lab.name
  source_tags = ["${var.name}-node"]
  target_tags = ["${var.name}-node"]
  allow {
    protocol = "tcp"
    ports    = ["179", "6443", "10250"]
  }
  allow {
    protocol = "udp"
    ports    = ["4789"]
  }
  allow {
    protocol = "icmp"
  }
}

resource "google_compute_instance" "node" {
  for_each     = local.nodes
  name         = "${var.name}-${each.key}"
  zone         = var.zone
  machine_type = "e2-standard-2"
  labels       = merge(local.labels, { role = each.key })
  tags         = ["${var.name}-node", "${var.name}-${each.key}"]

  boot_disk {
    auto_delete = true
    initialize_params {
      image = data.google_compute_image.ubuntu.self_link
      size  = 30
      type  = "pd-balanced"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.lab.id
    network_ip = each.value
    access_config {
      nat_ip = google_compute_address.node[each.key].address
    }
  }

  service_account {
    email  = google_service_account.nodes.email
    scopes = []
  }

  metadata = {
    block-project-ssh-keys   = "TRUE"
    enable-oslogin           = "FALSE"
    ssh-keys                 = "cks:${var.ssh_public_key}"
    disable-legacy-endpoints = "true"
  }
  metadata_startup_script = templatefile("${path.module}/prepare-node.sh.tftpl", {
    kubernetes_package = var.kubernetes_package
    kubernetes_version = local.kubernetes_version
    containerd_package = var.containerd_package
  })

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  depends_on = [google_compute_firewall.ssh, google_compute_firewall.api, google_compute_firewall.nodes]
}
