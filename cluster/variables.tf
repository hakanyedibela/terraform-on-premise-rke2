variable "nodes" {
  description = "Map of RKE2 nodes with IP, SSH user, and role"
  type = map(object({
    ip   = string
    user = string
    role = string
  }))
}

variable "ssh_private_key_path" {
  description = "Path to SSH private key for connecting to nodes"
  type        = string
  default     = "~/.ssh/id_rsa"
}
