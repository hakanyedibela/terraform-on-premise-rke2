
#!/usr/bin/env python3
"""
RKE2 Cluster Setup Automation Script
This script automates the setup and deployment of an RKE2 cluster using Terraform.
"""

import subprocess
import sys
import os
import time
import argparse
from pathlib import Path
from typing import List, Tuple


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class ClusterSetup:
    def __init__(self, master_ip: str, worker_ips: List[str], ssh_user: str, ssh_key_path: str):
        self.master_ip = master_ip
        self.worker_ips = worker_ips
        self.ssh_user = ssh_user
        self.ssh_key_path = Path(ssh_key_path).expanduser()
        self.all_nodes = [master_ip] + worker_ips

    def print_step(self, message: str):
        """Print a formatted step message"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

    def print_success(self, message: str):
        """Print a success message"""
        print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")

    def print_error(self, message: str):
        """Print an error message"""
        print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")

    def print_warning(self, message: str):
        """Print a warning message"""
        print(f"{Colors.WARNING}⚠ {message}{Colors.ENDC}")

    def run_command(self, command: str, check: bool = True, capture_output: bool = False) -> Tuple[int, str, str]:
        """Run a shell command and return the result"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=check,
                capture_output=capture_output,
                text=True
            )
            return result.returncode, result.stdout if capture_output else "", result.stderr if capture_output else ""
        except subprocess.CalledProcessError as e:
            if check:
                self.print_error(f"Command failed: {command}")
                self.print_error(f"Error: {e.stderr if capture_output else str(e)}")
            return e.returncode, e.stdout if capture_output else "", e.stderr if capture_output else ""

    def ssh_command(self, host: str, command: str, check: bool = True) -> Tuple[int, str, str]:
        """Execute a command on a remote host via SSH"""
        ssh_cmd = f"ssh -o StrictHostKeyChecking=no -i {self.ssh_key_path} {self.ssh_user}@{host} '{command}'"
        return self.run_command(ssh_cmd, check=check, capture_output=True)

    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met"""
        self.print_step("Checking Prerequisites")

        all_ok = True

        # Check if terraform is installed
        returncode, _, _ = self.run_command("terraform version", check=False, capture_output=True)
        if returncode == 0:
            self.print_success("Terraform is installed")
        else:
            self.print_error("Terraform is not installed")
            all_ok = False

        # Check if kubectl is installed
        returncode, _, _ = self.run_command("kubectl version --client", check=False, capture_output=True)
        if returncode == 0:
            self.print_success("kubectl is installed")
        else:
            self.print_warning("kubectl is not installed (optional, but recommended)")

        # Check if SSH key exists
        if self.ssh_key_path.exists():
            self.print_success(f"SSH key found at {self.ssh_key_path}")
        else:
            self.print_error(f"SSH key not found at {self.ssh_key_path}")
            all_ok = False

        return all_ok

    def generate_ssh_key(self):
        """Generate SSH key if it doesn't exist"""
        self.print_step("Generating SSH Key")

        if self.ssh_key_path.exists():
            self.print_warning(f"SSH key already exists at {self.ssh_key_path}")
            return

        self.ssh_key_path.parent.mkdir(parents=True, exist_ok=True)
        returncode, _, _ = self.run_command(
            f'ssh-keygen -t rsa -b 4096 -f {self.ssh_key_path} -N ""',
            check=False
        )

        if returncode == 0:
            self.print_success("SSH key generated successfully")
        else:
            self.print_error("Failed to generate SSH key")
            sys.exit(1)

    def copy_ssh_keys(self):
        """Copy SSH keys to all nodes"""
        self.print_step("Copying SSH Keys to Nodes")

        for node in self.all_nodes:
            print(f"\nCopying SSH key to {node}...")
            returncode, _, _ = self.run_command(
                f"ssh-copy-id -i {self.ssh_key_path} {self.ssh_user}@{node}",
                check=False
            )

            if returncode == 0:
                self.print_success(f"SSH key copied to {node}")
            else:
                self.print_error(f"Failed to copy SSH key to {node}")

    def test_ssh_connections(self) -> bool:
        """Test SSH connections to all nodes"""
        self.print_step("Testing SSH Connections")

        all_ok = True
        for node in self.all_nodes:
            returncode, stdout, _ = self.ssh_command(node, "echo 'Connection successful'", check=False)

            if returncode == 0 and "Connection successful" in stdout:
                self.print_success(f"SSH connection to {node} successful")
            else:
                self.print_error(f"SSH connection to {node} failed")
                all_ok = False

        return all_ok

    def setup_sudoers(self):
        """Setup passwordless sudo on all nodes"""
        self.print_step("Setting up Passwordless Sudo")

        for node in self.all_nodes:
            print(f"\nConfiguring sudo on {node}...")

            # Create sudoers file
            cmd = f'echo "{self.ssh_user} ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/{self.ssh_user}'
            returncode, _, _ = self.ssh_command(node, cmd, check=False)

            if returncode == 0:
                # Set correct permissions
                self.ssh_command(node, f"sudo chmod 0440 /etc/sudoers.d/{self.ssh_user}", check=False)

                # Test sudo
                test_returncode, _, _ = self.ssh_command(node, "sudo ls /root", check=False)
                if test_returncode == 0:
                    self.print_success(f"Passwordless sudo configured on {node}")
                else:
                    self.print_error(f"Sudo test failed on {node}")
            else:
                self.print_error(f"Failed to configure sudo on {node}")

    def prepare_nodes(self):
        """Prepare all nodes with required packages and configurations"""
        self.print_step("Preparing Nodes")

        for node in self.all_nodes:
            print(f"\n{Colors.OKCYAN}Preparing {node}...{Colors.ENDC}")

            # Update system
            print("  - Updating system...")
            self.ssh_command(node, "sudo apt-get update -qq", check=False)

            # Install required packages
            print("  - Installing required packages...")
            self.ssh_command(node, "sudo apt-get install -y curl jq", check=False)

            # Disable swap
            print("  - Disabling swap...")
            self.ssh_command(node, "sudo swapoff -a", check=False)
            self.ssh_command(node, "sudo sed -i '/ swap / s/^/#/' /etc/fstab", check=False)

            self.print_success(f"Node {node} prepared")

    def configure_firewall(self):
        """Configure firewall rules on nodes"""
        self.print_step("Configuring Firewall")

        # Check if UFW is active
        returncode, stdout, _ = self.ssh_command(self.master_ip, "sudo ufw status", check=False)

        if "inactive" in stdout.lower():
            self.print_warning("UFW is not active, skipping firewall configuration")
            return

        # Configure master node
        print(f"\n{Colors.OKCYAN}Configuring firewall on master node...{Colors.ENDC}")
        master_ports = [
            ("6443/tcp", "Kubernetes API"),
            ("9345/tcp", "RKE2 supervisor API"),
            ("10250/tcp", "Kubelet"),
            ("2379:2380/tcp", "etcd")
        ]

        for port, description in master_ports:
            print(f"  - Allowing {port} ({description})")
            self.ssh_command(self.master_ip, f"sudo ufw allow {port}", check=False)

        self.print_success("Master node firewall configured")

        # Configure worker nodes
        for worker in self.worker_ips:
            print(f"\n{Colors.OKCYAN}Configuring firewall on {worker}...{Colors.ENDC}")
            worker_ports = [
                ("10250/tcp", "Kubelet"),
                ("30000:32767/tcp", "NodePort services")
            ]

            for port, description in worker_ports:
                print(f"  - Allowing {port} ({description})")
                self.ssh_command(worker, f"sudo ufw allow {port}", check=False)

            self.print_success(f"Worker node {worker} firewall configured")

    def terraform_init(self):
        """Initialize Terraform"""
        self.print_step("Initializing Terraform")

        os.chdir("cluster")
        returncode, _, _ = self.run_command("terraform init")

        if returncode == 0:
            self.print_success("Terraform initialized")
        else:
            self.print_error("Terraform initialization failed")
            sys.exit(1)

    def terraform_validate(self):
        """Validate Terraform configuration"""
        self.print_step("Validating Terraform Configuration")

        returncode, _, _ = self.run_command("terraform validate")

        if returncode == 0:
            self.print_success("Terraform configuration is valid")
        else:
            self.print_error("Terraform configuration is invalid")
            sys.exit(1)

    def terraform_plan(self):
        """Run Terraform plan"""
        self.print_step("Running Terraform Plan")

        returncode, _, _ = self.run_command("terraform plan")

        if returncode == 0:
            self.print_success("Terraform plan completed")
        else:
            self.print_error("Terraform plan failed")
            sys.exit(1)

    def terraform_apply(self):
        """Apply Terraform configuration"""
        self.print_step("Applying Terraform Configuration")

        returncode, _, _ = self.run_command("terraform apply -auto-approve")

        if returncode == 0:
            self.print_success("Terraform apply completed")
        else:
            self.print_error("Terraform apply failed")
            sys.exit(1)

    def verify_cluster(self):
        """Verify the cluster is working"""
        self.print_step("Verifying Cluster")

        # Export kubeconfig
        kubeconfig_path = Path.cwd() / "kubeconfig.yaml"
        os.environ["KUBECONFIG"] = str(kubeconfig_path)

        # Wait for cluster to be ready
        print("Waiting for cluster to be ready...")
        time.sleep(30)

        # Check nodes
        print("\nChecking nodes...")
        returncode, stdout, _ = self.run_command("kubectl get nodes", check=False, capture_output=True)
        if returncode == 0:
            print(stdout)
            self.print_success("Nodes are accessible")
        else:
            self.print_error("Failed to get nodes")

        # Check pods
        print("\nChecking pods...")
        returncode, stdout, _ = self.run_command("kubectl get pods -A", check=False, capture_output=True)
        if returncode == 0:
            print(stdout)
            self.print_success("Pods are accessible")
        else:
            self.print_error("Failed to get pods")

        # Cluster info
        print("\nCluster info:")
        self.run_command("kubectl cluster-info", check=False)

    def terraform_destroy(self):
        """Destroy the Terraform-managed infrastructure"""
        self.print_step("Destroying Cluster")

        returncode, _, _ = self.run_command("terraform destroy -auto-approve")

        if returncode == 0:
            self.print_success("Cluster destroyed")
        else:
            self.print_error("Failed to destroy cluster")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="RKE2 Cluster Setup Automation")
    parser.add_argument("--master-ip", default="10.211.55.28", help="Master node IP address")
    parser.add_argument("--worker-ips", nargs="+", default=["10.211.55.29", "10.211.55.30"],
                       help="Worker node IP addresses")
    parser.add_argument("--ssh-user", default="hkn", help="SSH user")
    parser.add_argument("--ssh-key", default="~/.ssh/id_rsa", help="SSH private key path")
    parser.add_argument("--skip-prep", action="store_true", help="Skip node preparation")
    parser.add_argument("--skip-firewall", action="store_true", help="Skip firewall configuration")
    parser.add_argument("--destroy", action="store_true", help="Destroy the cluster")
    parser.add_argument("--verify-only", action="store_true", help="Only verify the cluster")

    args = parser.parse_args()

    setup = ClusterSetup(
        master_ip=args.master_ip,
        worker_ips=args.worker_ips,
        ssh_user=args.ssh_user,
        ssh_key_path=args.ssh_key
    )

    if args.destroy:
        setup.terraform_destroy()
        return

    if args.verify_only:
        setup.verify_cluster()
        return

    if not setup.check_prerequisites():
        sys.exit(1)

    setup.generate_ssh_key()
    setup.copy_ssh_keys()

    if not setup.test_ssh_connections():
        sys.exit(1)

    setup.setup_sudoers()

    if not args.skip_prep:
        setup.prepare_nodes()

    if not args.skip_firewall:
        setup.configure_firewall()

    setup.terraform_init()
    setup.terraform_validate()
    setup.terraform_plan()
    setup.terraform_apply()
    setup.verify_cluster()


if __name__ == "__main__":
    main()
