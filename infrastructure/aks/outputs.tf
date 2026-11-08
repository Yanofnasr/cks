# SPDX-License-Identifier: MIT
output "cluster_name" {
  description = "Name of the owned training cluster."
  value       = azurerm_kubernetes_cluster.practice.name
}

output "resource_group_name" {
  description = "Dedicated resource group containing the cluster resource."
  value       = azurerm_resource_group.practice.name
}

output "node_resource_group_name" {
  description = "AKS-managed resource group removed with the cluster."
  value       = azurerm_kubernetes_cluster.practice.node_resource_group
}

output "context_name" {
  description = "Kubeconfig alias for this cluster."
  value       = "aks-${var.name}"
}

output "connect_command" {
  description = "Run after exporting a fresh private KUBECONFIG path, then use kubelogin."
  value       = "az aks get-credentials --subscription '${var.subscription_id}' --resource-group '${azurerm_resource_group.practice.name}' --name '${azurerm_kubernetes_cluster.practice.name}' --file \"$KUBECONFIG\" --context 'aks-${var.name}'"
}
