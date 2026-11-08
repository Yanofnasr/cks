# SPDX-License-Identifier: MIT
variable "project_id" {
  description = "Dedicated training project with Compute Engine API already enabled."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Use an explicit Google Cloud project ID."
  }
}

variable "zone" {
  description = "One zone for the two lab VMs."
  type        = string
  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+-[a-z]$", var.zone))
    error_message = "Use a zone such as europe-west1-b."
  }
}

variable "name" {
  description = "Unique lab resource prefix, not an existing environment."
  type        = string
  default     = "cks-kubeadm"
  validation {
    condition     = can(regex("^cks-[a-z0-9][a-z0-9-]{0,15}[a-z0-9]$", var.name))
    error_message = "Use a cks- prefix and 2-17 lowercase letters/digits after it; end with a letter or digit."
  }
}

variable "admin_cidr" {
  description = "Your stable public IPv4 address with /32; permits SSH and the control-plane API."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.admin_cidr)) && can(regex("/32$", var.admin_cidr))
    error_message = "Administrator access must be one explicit IPv4 /32, never an open network."
  }
}

variable "ssh_public_key" {
  description = "One public SSH key for the cks user. Never supply a private key."
  type        = string
  validation {
    condition     = can(regex("^(ssh-ed25519|ssh-rsa) [A-Za-z0-9+/=]+( [^\n\r]+)?$", var.ssh_public_key))
    error_message = "Supply one OpenSSH public-key line (Ed25519 or RSA), without newlines."
  }
}

variable "expires_on" {
  description = "Calendar date used as a cleanup reminder label; it does not delete resources automatically."
  type        = string
  validation {
    condition     = can(formatdate("YYYY-MM-DD", "${var.expires_on}T00:00:00Z"))
    error_message = "Use a real calendar date in YYYY-MM-DD format."
  }
}

variable "kubernetes_package" {
  description = "Exact common kubeadm/kubelet/kubectl package version from the 1.37 repository."
  type        = string
  default     = "1.37.0-1.1"
  validation {
    condition     = can(regex("^1\\.37\\.[0-9]+-[0-9.]+$", var.kubernetes_package))
    error_message = "Use an exact 1.37 package revision, such as 1.37.0-1.1."
  }
}

variable "containerd_package" {
  description = "Exact containerd.io 2.x package from Docker's Ubuntu 24.04 repository."
  type        = string
  default     = "2.3.4-2~ubuntu.24.04~noble"
  validation {
    condition     = can(regex("^2\\.[0-9]+\\.[0-9]+-[0-9]+~ubuntu\\.24\\.04~noble$", var.containerd_package))
    error_message = "Use an exact containerd.io 2.x Ubuntu 24.04 noble package revision."
  }
}
