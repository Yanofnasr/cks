mock_provider "aws" {
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/mock-role" }
  }
  mock_resource "aws_eks_cluster" {
    defaults = {
      identity = [{ oidc = [{ issuer = "https://oidc.eks.eu-west-1.amazonaws.com/id/EXAMPLE" }] }]
    }
  }
  mock_resource "aws_launch_template" {
    defaults = {
      id             = "lt-0123456789abcdef0"
      latest_version = 1
    }
  }
}

variables {
  account_id           = "123456789012"
  region               = "eu-west-1"
  availability_zones   = ["eu-west-1a", "eu-west-1b"]
  name                 = "cks-test"
  admin_cidr           = "203.0.113.10/32"
  admin_principal_arn  = "arn:aws:iam::123456789012:role/training-admin"
  kubernetes_version   = "1.37"
  node_release_version = "1.37.0-20261001"
  expires_on           = "2026-12-01"
}

run "private_nodes_and_explicit_access" {
  command = plan

  assert {
    condition     = alltrue([for subnet in aws_subnet.private : !subnet.map_public_ip_on_launch])
    error_message = "Worker subnets must not assign public IPs."
  }
  assert {
    condition     = aws_eks_cluster.lab.vpc_config[0].endpoint_private_access && aws_eks_cluster.lab.vpc_config[0].endpoint_public_access && aws_eks_cluster.lab.vpc_config[0].public_access_cidrs == toset([var.admin_cidr])
    error_message = "API access must retain the private endpoint and restrict public access to the selected administrator."
  }
  assert {
    condition     = aws_eks_cluster.lab.access_config[0].authentication_mode == "API" && !aws_eks_cluster.lab.access_config[0].bootstrap_cluster_creator_admin_permissions
    error_message = "Cluster access must use the explicit access entry, not an implicit creator grant."
  }
  assert {
    condition     = aws_eks_access_entry.administrator.principal_arn == var.admin_principal_arn && aws_eks_access_policy_association.administrator.access_scope[0].type == "cluster"
    error_message = "The named training identity needs explicit administrator access."
  }
  assert {
    condition     = aws_launch_template.nodes.metadata_options[0].http_tokens == "required" && aws_launch_template.nodes.metadata_options[0].http_put_response_hop_limit == 1
    error_message = "Worker metadata must require IMDSv2 and prevent ordinary Pod hops."
  }
  assert {
    condition     = aws_launch_template.nodes.block_device_mappings[0].ebs[0].encrypted && aws_eks_node_group.lab.scaling_config[0].desired_size == 2
    error_message = "The profile must use two workers with encrypted root disks."
  }
  assert {
    condition     = alltrue([for spec in aws_launch_template.nodes.tag_specifications : spec.tags["ExpiresOn"] == var.expires_on])
    error_message = "The cleanup reminder must reach worker instances and their volumes."
  }
  assert {
    condition     = !contains([for attachment in aws_iam_role_policy_attachment.nodes : attachment.policy_arn], "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy")
    error_message = "The CNI must use its own role, not the node role."
  }
  assert {
    condition     = aws_eks_cluster.lab.enabled_cluster_log_types == toset(["api", "audit", "authenticator", "controllerManager", "scheduler"]) && aws_cloudwatch_log_group.control_plane.retention_in_days == 7
    error_message = "Control-plane logs must be enabled with bounded retention."
  }
}

run "reject_world_access" {
  command = plan
  variables { admin_cidr = "0.0.0.0/0" }
  expect_failures = [var.admin_cidr]
}

run "reject_foreign_administrator" {
  command = plan
  variables { admin_principal_arn = "arn:aws:iam::999999999999:role/other-admin" }
  expect_failures = [aws_eks_access_entry.administrator]
}

run "reject_missing_expiry" {
  command = plan
  variables { expires_on = "" }
  expect_failures = [var.expires_on]
}
