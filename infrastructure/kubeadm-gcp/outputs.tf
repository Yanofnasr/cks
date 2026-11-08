# SPDX-License-Identifier: MIT
output "bootstrap" {
  description = "Non-secret inventory consumed by scripts/bootstrap_kubeadm.py."
  value = {
    project_id         = var.project_id
    zone               = var.zone
    name               = var.name
    ssh_user           = "cks"
    kubernetes_version = local.kubernetes_version
    control = {
      name       = google_compute_instance.node["control"].name
      private_ip = local.nodes.control
      public_ip  = google_compute_address.node["control"].address
    }
    worker = {
      name       = google_compute_instance.node["worker"].name
      private_ip = local.nodes.worker
      public_ip  = google_compute_address.node["worker"].address
    }
  }
}

output "ubuntu_image" {
  description = "Exact official Ubuntu image selected by this saved plan."
  value       = data.google_compute_image.ubuntu.self_link
}
