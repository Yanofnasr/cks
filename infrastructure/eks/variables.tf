# SPDX-License-Identifier: MIT
variable "account_id" {
  type        = string
  description = "The dedicated training AWS account. The provider refuses another account."
  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "Use a 12-digit training account ID."
  }
}

variable "region" {
  type        = string
  description = "Commercial AWS region selected for this lab."
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]+$", var.region))
    error_message = "Use a commercial AWS region such as eu-west-1."
  }
}

variable "availability_zones" {
  type        = list(string)
  description = "Two different available zones in the selected region."
  validation {
    condition     = length(var.availability_zones) == 2 && length(distinct(var.availability_zones)) == 2
    error_message = "Choose exactly two distinct availability zones."
  }
}

variable "name" {
  type        = string
  default     = "cks-practice"
  description = "Unique lab name, also used to identify resources for teardown."
  validation {
    condition     = can(regex("^cks-[a-z0-9][a-z0-9-]{0,25}$", var.name))
    error_message = "Use a unique cks- name containing lowercase letters, digits and hyphens, at most 30 characters."
  }
}

variable "admin_cidr" {
  type        = string
  description = "Your workstation or VPN's stable public IPv4 address with /32."
  validation {
    condition     = can(cidrnetmask(var.admin_cidr)) && can(regex("/32$", var.admin_cidr))
    error_message = "Public API access must be one IPv4 /32, not a network or 0.0.0.0/0."
  }
}

variable "admin_principal_arn" {
  type        = string
  description = "Existing IAM role or user ARN that will administer the disposable cluster; not an STS session ARN."
  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:(role|user)/[A-Za-z0-9_+=,.@/-]+$", var.admin_principal_arn))
    error_message = "Use an IAM role/user ARN in the training account, not a temporary session ARN."
  }
}

variable "kubernetes_version" {
  type        = string
  description = "Exact EKS-supported Kubernetes minor selected from the regional version list, for example 1.37."
  validation {
    condition     = can(regex("^1\\.[0-9]+$", var.kubernetes_version))
    error_message = "EKS accepts a Kubernetes minor such as 1.37; query regional availability first."
  }
}

variable "node_release_version" {
  type        = string
  description = "Exact matching EKS AL2023 x86_64 standard AMI release, selected before planning."
  validation {
    condition     = can(regex("^1\\.[0-9]+\\.[0-9]+-[0-9]{8}$", var.node_release_version))
    error_message = "Use the matching EKS AMI release value, such as 1.37.0-YYYYMMDD, from the official SSM parameter."
  }
}

variable "expires_on" {
  type        = string
  description = "Planned removal date YYYY-MM-DD. This tag is a reminder, not automatic deletion."
  validation {
    condition     = can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", var.expires_on)) && can(formatdate("YYYY-MM-DD", "${var.expires_on}T00:00:00Z"))
    error_message = "Set a real planned removal date in YYYY-MM-DD format."
  }
}
