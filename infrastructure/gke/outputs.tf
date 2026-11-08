# SPDX-License-Identifier: MIT
output "cluster_name" {
  value = google_container_cluster.lab.name
}

output "project_id" {
  value = var.project_id
}

output "zone" {
  value = var.zone
}

output "context" {
  value = "gke_${var.project_id}_${var.zone}_${var.name}"
}

output "connect_command" {
  description = "Run only after exporting an isolated lab KUBECONFIG. No credentials are stored in this output."
  value       = "gcloud container clusters get-credentials ${var.name} --project ${var.project_id} --zone ${var.zone}"
}
