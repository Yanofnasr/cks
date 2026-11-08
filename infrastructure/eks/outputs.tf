# SPDX-License-Identifier: MIT
output "cluster_name" {
  description = "The dedicated EKS cluster name."
  value       = aws_eks_cluster.lab.name
}

output "region" {
  value = var.region
}

output "context" {
  value = var.name
}

output "kubeconfig_command" {
  description = "Run with the selected AWS profile after exporting a fresh private KUBECONFIG path."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${var.name} --alias ${var.name} --kubeconfig \"$KUBECONFIG\""
}
