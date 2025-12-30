# terraform-on-premise-rke2

## Run on each server (master and workers)

### 1. Update system
sudo apt-get update && sudo apt-get upgrade -y

### 2. Install required packages
sudo apt-get install -y curl jq

### 3. Disable swap (required for Kubernetes)
sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab

### 4. Configure firewall (if UFW is enabled)
### On master node:
sudo ufw allow 6443/tcp  # Kubernetes API
sudo ufw allow 9345/tcp  # RKE2 supervisor API
sudo ufw allow 10250/tcp # Kubelet
sudo ufw allow 2379:2380/tcp # etcd

### On worker nodes:
sudo ufw allow 10250/tcp # Kubelet
sudo ufw allow 30000:32767/tcp # NodePort services


### On your local machine where you run Terraform

### 1. Generate SSH key if you don't have one
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""

### 2. Copy SSH key to all nodes
ssh-copy-id hkn@10.211.55.28
ssh-copy-id hkn@10.211.55.29
ssh-copy-id hkn@10.211.55.30

### 3. Test SSH connection (should not ask for password)
ssh hkn@10.211.55.28 "echo 'Connection successful'"


### Initialize Terraform
terraform init

### Validate configuration
terraform validate

### Preview changes
terraform plan

### Apply configuration
terraform apply -auto-approve

### Export kubeconfig
export KUBECONFIG=$(pwd)/kubeconfig.yaml

### Check nodes
kubectl get nodes

### Check pods
kubectl get pods -A

### Check cluster info
kubectl cluster-info

### Check RKE2 server status on master
sudo systemctl status rke2-server

### SSH to master node
ssh hkn@10.211.55.28

### Check RKE2 agent status on workers
ssh hkn@10.211.55.29 "sudo systemctl status rke2-agent"

### View RKE2 server logs
ssh hkn@10.211.55.28 "sudo journalctl -u rke2-server -f"

### Destroy cluster when done
terraform destroy -auto-approve

=========================================================

### SSH to each server
ssh hkn@10.211.55.28

### Add user to sudoers with NOPASSWD
echo "hkn ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/hkn
sudo chmod 0440 /etc/sudoers.d/hkn

### Verify it works
sudo ls /root
### Should not ask for password

