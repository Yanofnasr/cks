# SPDX-License-Identifier: MIT
variable "subscription_id" {
  description = "Dedicated training subscription ID."
  type        = string
  validation {
    condition     = can(regex("(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.subscription_id))
    error_message = "Set the training subscription UUID explicitly."
  }
}

variable "tenant_id" {
  description = "Entra tenant ID for both provisioning and cluster authentication."
  type        = string
  validation {
    condition     = can(regex("(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.tenant_id))
    error_message = "Set the Entra tenant UUID explicitly."
  }
}

variable "name" {
  description = "Unique name for this disposable cluster and its dedicated resource groups."
  type        = string
  default     = "cks-practice"
  validation {
    condition     = can(regex("^cks-[a-z0-9]([a-z0-9-]{0,34}[a-z0-9])?$", var.name))
    error_message = "Use a 5-40 character cks- name with lowercase letters, digits or internal hyphens."
  }
}

variable "location" {
  description = "Azure region with the requested Kubernetes version and VM quota."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9]+$", var.location))
    error_message = "Use the Azure region name, such as westeurope."
  }
}

variable "kubernetes_version" {
  description = "Exact offered Kubernetes patch version, selected with az aks get-versions."
  type        = string
  validation {
    condition     = can(regex("^1\\.[0-9]+\\.[0-9]+$", var.kubernetes_version))
    error_message = "Select an offered exact 1.x.y version, not an automatic latest version."
  }
}

variable "admin_cidr" {
  description = "Administrator workstation or VPN's public IPv4 address with /32."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.admin_cidr)) && can(cidrhost(var.admin_cidr, 0)) && endswith(var.admin_cidr, "/32")
    error_message = "Use exactly one administrator IPv4 /32; broad and IPv6 ranges are not accepted."
  }
}

variable "admin_group_object_ids" {
  description = "Existing Entra security groups whose members administer this training cluster."
  type        = set(string)
  validation {
    condition = length(var.admin_group_object_ids) > 0 && alltrue([
      for id in var.admin_group_object_ids : can(regex("(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", id))
    ])
    error_message = "Supply at least one existing Entra security-group UUID, not a user or application ID."
  }
}

variable "expires_on" {
  description = "Planned deletion date, YYYY-MM-DD. This tag is a reminder, not automatic deletion."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", var.expires_on)) && can(formatdate("YYYY-MM-DD", "${var.expires_on}T00:00:00Z"))
    error_message = "Use a real calendar date in YYYY-MM-DD format."
  }
}
