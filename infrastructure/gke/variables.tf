# SPDX-License-Identifier: MIT
variable "project_id" {
  description = "Existing billing-enabled training project with Compute, GKE, IAM and Cloud Resource Manager APIs enabled."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Use the exact Google Cloud project ID, not its display name or number."
  }
}

variable "zone" {
  description = "One GKE-supported zone, for example europe-west1-b."
  type        = string
  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+-[a-z]$", var.zone))
    error_message = "Select one zone, such as europe-west1-b, rather than a region."
  }
}

variable "name" {
  description = "Unique name for this disposable lab and its dedicated resources."
  type        = string
  default     = "cks-practice"
  validation {
    condition     = can(regex("^cks-[a-z0-9][a-z0-9-]{0,18}[a-z0-9]$", var.name))
    error_message = "Use a cks- prefixed lowercase name, 6-24 characters, ending in a letter or digit."
  }
}

variable "kubernetes_version" {
  description = "Exact 1.37+ version offered in the selected zone's REGULAR channel. GKE maintains it afterward."
  type        = string
  validation {
    condition     = can(regex("^1\\.[0-9]+\\.[0-9]+-gke\\.[0-9]+$", var.kubernetes_version)) && try(tonumber(split(".", var.kubernetes_version)[1]), 0) >= 37
    error_message = "Select an offered exact GKE 1.37 or newer version (1.MINOR.PATCH-gke.BUILD)."
  }
}

variable "admin_cidr" {
  description = "Administrator's actual public IPv4 address with /32 for Kubernetes API access."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.admin_cidr)) && can(regex("/32$", var.admin_cidr))
    error_message = "Supply one actual administrator IPv4 /32; broader or IPv6 ranges are not accepted."
  }
}

variable "expires_on" {
  description = "Planned teardown date (YYYY-MM-DD). The label is a reminder, not an automatic deletion job."
  type        = string
  validation {
    condition     = can(formatdate("YYYY-MM-DD", "${var.expires_on}T00:00:00Z"))
    error_message = "Set a valid planned teardown date in YYYY-MM-DD format."
  }
}
