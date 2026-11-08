# SPDX-License-Identifier: MIT
terraform {
  required_version = ">= 1.7.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.72.0"
    }
  }
}

locals {
  tags = {
    Project   = var.name
    Purpose   = "cks-practice"
    ExpiresOn = var.expires_on
  }
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.account_id]
  default_tags {
    tags = local.tags
  }
}
