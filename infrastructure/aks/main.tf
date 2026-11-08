# SPDX-License-Identifier: MIT
locals {
  tags = {
    purpose      = "cks-practice"
    "expires-on" = var.expires_on
  }
}

resource "azurerm_resource_group" "practice" {
  name     = "${var.name}-rg"
  location = var.location
  tags     = local.tags
}

resource "azurerm_kubernetes_cluster" "practice" {
  name                              = var.name
  location                          = azurerm_resource_group.practice.location
  resource_group_name               = azurerm_resource_group.practice.name
  node_resource_group               = "${var.name}-nodes"
  dns_prefix                        = var.name
  kubernetes_version                = var.kubernetes_version
  sku_tier                          = "Free"
  role_based_access_control_enabled = true
  local_account_disabled            = true
  node_os_upgrade_channel           = "NodeImage"
  tags                              = local.tags

  default_node_pool {
    name                   = "system"
    node_count             = 2
    vm_size                = "Standard_D4s_v5"
    os_sku                 = "Ubuntu"
    os_disk_size_gb        = 30
    node_public_ip_enabled = false
    tags                   = local.tags
  }

  node_provisioning_profile {
    mode = "Manual"
  }

  identity {
    type = "SystemAssigned"
  }

  azure_active_directory_role_based_access_control {
    tenant_id              = var.tenant_id
    admin_group_object_ids = var.admin_group_object_ids
    azure_rbac_enabled     = false
  }

  api_server_access_profile {
    authorized_ip_ranges = [var.admin_cidr]
  }

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    network_data_plane  = "cilium"
    network_policy      = "cilium"
    pod_cidr            = "10.244.0.0/16"
    service_cidr        = "10.96.0.0/16"
    dns_service_ip      = "10.96.0.10"
    load_balancer_sku   = "standard"
    outbound_type       = "loadBalancer"
  }
}
