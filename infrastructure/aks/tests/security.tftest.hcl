# SPDX-License-Identifier: MIT
mock_provider "azurerm" {}

variables {
  subscription_id        = "11111111-1111-1111-1111-111111111111"
  tenant_id              = "22222222-2222-2222-2222-222222222222"
  name                   = "cks-test"
  location               = "westeurope"
  kubernetes_version     = "1.37.0"
  admin_cidr             = "203.0.113.10/32"
  admin_group_object_ids = ["33333333-3333-3333-3333-333333333333"]
  expires_on             = "2026-12-01"
}

run "restricted_training_cluster" {
  command = plan

  assert {
    condition     = azurerm_kubernetes_cluster.practice.api_server_access_profile[0].authorized_ip_ranges == toset([var.admin_cidr])
    error_message = "The API must be restricted to the administrator's exact /32."
  }
  assert {
    condition     = azurerm_kubernetes_cluster.practice.local_account_disabled && azurerm_kubernetes_cluster.practice.role_based_access_control_enabled
    error_message = "Use Entra authentication and RBAC, without local administrator credentials."
  }
  assert {
    condition     = azurerm_kubernetes_cluster.practice.azure_active_directory_role_based_access_control[0].tenant_id == var.tenant_id && toset(azurerm_kubernetes_cluster.practice.azure_active_directory_role_based_access_control[0].admin_group_object_ids) == toset(var.admin_group_object_ids) && !azurerm_kubernetes_cluster.practice.azure_active_directory_role_based_access_control[0].azure_rbac_enabled
    error_message = "Only the supplied Entra groups should receive native Kubernetes administrator access."
  }
  assert {
    condition     = azurerm_kubernetes_cluster.practice.network_profile[0].network_plugin == "azure" && azurerm_kubernetes_cluster.practice.network_profile[0].network_plugin_mode == "overlay" && azurerm_kubernetes_cluster.practice.network_profile[0].network_data_plane == "cilium"
    error_message = "The profile needs Azure CNI Overlay with Cilium enforcement."
  }
  assert {
    condition     = azurerm_kubernetes_cluster.practice.default_node_pool[0].node_count == 2 && !azurerm_kubernetes_cluster.practice.default_node_pool[0].node_public_ip_enabled && azurerm_kubernetes_cluster.practice.node_provisioning_profile[0].mode == "Manual"
    error_message = "Create two Linux nodes without individual public IP addresses."
  }
  assert {
    condition     = azurerm_kubernetes_cluster.practice.default_node_pool[0].vm_size == "Standard_D4s_v5"
    error_message = "The system pool must meet AKS's four-vCPU minimum."
  }
  assert {
    condition     = azurerm_kubernetes_cluster.practice.identity[0].type == "SystemAssigned" && azurerm_resource_group.practice.tags["expires-on"] == var.expires_on
    error_message = "Use a system identity and retain the planned cleanup date on the dedicated group."
  }
}

run "reject_public_api" {
  command = plan
  variables {
    admin_cidr = "0.0.0.0/0"
  }
  expect_failures = [var.admin_cidr]
}

run "reject_network_range" {
  command = plan
  variables {
    admin_cidr = "203.0.113.0/24"
  }
  expect_failures = [var.admin_cidr]
}

run "require_admin_group" {
  command = plan
  variables {
    admin_group_object_ids = []
  }
  expect_failures = [var.admin_group_object_ids]
}
