output "node_token" {
  description = "RKE2 node token for joining workers"
  value       = data.external.get_token.result.token
  sensitive   = true
}

output "master_node_ip" {
  description = "IP address of the master node"
  value       = local.master_ip
}

output "worker_node_ips" {
  description = "IP addresses of worker nodes"
  value       = [for node in local.worker_nodes : node.ip]
}

output "kubeconfig_path" {
  description = "Path to the kubeconfig file"
  value       = "${path.module}/kubeconfig.yaml"
}

output "cluster_info" {
  description = "RKE2 cluster information"
  value = {
    master_ip      = local.master_ip
    worker_count   = length(local.worker_nodes)
    kubeconfig_cmd = "export KUBECONFIG=${path.module}/kubeconfig.yaml"
  }
}
