terraform {
  required_version = ">= 1.5.0"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
  }
}

# Kubernetes provider configuration
provider "kubernetes" {
  config_path = "${path.module}/kubeconfig.yaml"
}

locals {
  master_nodes = { for name, node in var.nodes : name => node if node.role == "master" }
  worker_nodes = { for name, node in var.nodes : name => node if node.role == "worker" }
  master_ip    = values(local.master_nodes)[0].ip
  master_user  = values(local.master_nodes)[0].user
}

# ----------------------------------------------------------
# Install RKE2 Server (Control Plane)
# ----------------------------------------------------------
resource "null_resource" "install_rke2_master" {
  for_each = local.master_nodes

  provisioner "remote-exec" {
    inline = [
      "set -e",
      "echo 'Installing RKE2 server...'",
      "curl -sfL https://get.rke2.io | sudo INSTALL_RKE2_TYPE=server sh -",
      "sudo systemctl enable rke2-server.service",
      "sudo systemctl start rke2-server.service",
      "echo 'Waiting for RKE2 server to be ready...'",
      "timeout 300 bash -c 'until sudo test -f /var/lib/rancher/rke2/server/node-token; do sleep 5; done'",
      "echo 'RKE2 server installation complete!'"
    ]

    connection {
      type        = "ssh"
      host        = each.value.ip
      user        = each.value.user
      private_key = file(var.ssh_private_key_path)
    }
  }

  triggers = {
    node_ip = each.value.ip
  }
}

# ----------------------------------------------------------
# Get Node Token from Master
# ----------------------------------------------------------
data "external" "get_token" {
  depends_on = [null_resource.install_rke2_master]

  program = ["bash", "-c", <<-EOT
    TOKEN=$(ssh -o StrictHostKeyChecking=no -i ${var.ssh_private_key_path} ${local.master_user}@${local.master_ip} 'sudo cat /var/lib/rancher/rke2/server/node-token' 2>/dev/null)
    if [ -z "$TOKEN" ]; then
      echo '{"error": "Failed to retrieve token"}' >&2
      exit 1
    fi
    echo "$TOKEN" | jq -R '{token: .}'
  EOT
  ]
}

# ----------------------------------------------------------
# Install RKE2 Agents (Workers)
# ----------------------------------------------------------
resource "null_resource" "install_rke2_worker" {
  for_each   = local.worker_nodes
  depends_on = [data.external.get_token]

  provisioner "remote-exec" {
    inline = [
      "set -e",
      "echo 'Installing RKE2 agent...'",
      "curl -sfL https://get.rke2.io | sudo INSTALL_RKE2_TYPE=agent sh -",
      "sudo mkdir -p /etc/rancher/rke2",
      "echo 'server: https://${local.master_ip}:9345' | sudo tee /etc/rancher/rke2/config.yaml",
      "echo 'token: ${data.external.get_token.result.token}' | sudo tee -a /etc/rancher/rke2/config.yaml",
      "sudo systemctl enable rke2-agent.service",
      "sudo systemctl start rke2-agent.service",
      "echo 'RKE2 agent installation complete!'"
    ]

    connection {
      type        = "ssh"
      host        = each.value.ip
      user        = each.value.user
      private_key = file(var.ssh_private_key_path)
    }
  }

  triggers = {
    node_ip      = each.value.ip
    master_token = data.external.get_token.result.token
  }
}

# ----------------------------------------------------------
# Retrieve and Save kubeconfig
# ----------------------------------------------------------
resource "null_resource" "get_kubeconfig" {
  depends_on = [null_resource.install_rke2_worker]

  provisioner "local-exec" {
    command = <<-EOT
      ssh -o StrictHostKeyChecking=no -i ${var.ssh_private_key_path} ${local.master_user}@${local.master_ip} 'sudo cat /etc/rancher/rke2/rke2.yaml' | \
      sed 's/127.0.0.1/${local.master_ip}/g' > ${path.module}/kubeconfig.yaml
      chmod 600 ${path.module}/kubeconfig.yaml
      echo "Kubeconfig saved to: ${path.module}/kubeconfig.yaml"
    EOT
  }

  triggers = {
    always_run = timestamp()
  }
}
