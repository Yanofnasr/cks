# SPDX-License-Identifier: MIT
"""Initialize the two fresh VMs provisioned by infrastructure/kubeadm-gcp."""
import argparse
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CALICO_URL = "https://raw.githubusercontent.com/projectcalico/calico/v3.33.0/manifests/calico.yaml"
CALICO_SHA256 = "2de8f47595fb9c41b3f47d7b767a1f8e72ecf84057af834738ff12689a234da5"


class BootstrapError(Exception):
    pass


def run(command, label, input=None, timeout=60, env=None):
    try:
        result = subprocess.run(command, input=input, text=True, capture_output=True,
                                timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired):
        raise BootstrapError(f"{label} could not complete; check the selected tools and connection") from None
    if result.returncode:
        # SSH and kubeadm output may contain credentials; keep it out of terminal/error logs.
        raise BootstrapError(f"{label} failed; inspect the lab's private logs or repeat the documented diagnostic command")
    return result.stdout


def validate_inventory(value):
    try:
        if not (isinstance(value, dict)
                and re.fullmatch(r"cks-[a-z0-9][a-z0-9-]{0,15}[a-z0-9]", value["name"])
                and re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", value["project_id"])
                and re.fullmatch(r"[a-z]+-[a-z]+[0-9]+-[a-z]", value["zone"])
                and value["ssh_user"] == "cks"
                and re.fullmatch(r"1\.37\.[0-9]+", value["kubernetes_version"])):
            raise ValueError()
        addresses = []
        for role in ("control", "worker"):
            node = value[role]
            if node["name"] != value["name"] + "-" + role:
                raise ValueError()
            for field in ("private_ip", "public_ip"):
                if not isinstance(node[field], str):
                    raise ValueError()
                address = ipaddress.IPv4Address(node[field])
                if address.is_unspecified or address.is_multicast or address.is_loopback:
                    raise ValueError()
                addresses.append(str(address))
        if (len(set(addresses)) != 4 or value["control"]["private_ip"] != "10.92.0.10"
                or value["worker"]["private_ip"] != "10.92.0.11"):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise BootstrapError("Terraform output does not match the dedicated two-VM profile") from None
    return value


def join_configuration(command, inventory):
    try:
        words = shlex.split(command)
        if not (len(words) == 7 and words[:2] == ["kubeadm", "join"]
                and words[2] == inventory["control"]["private_ip"] + ":6443"
                and words[3] == "--token" and re.fullmatch(r"[a-z0-9]{6}\.[a-z0-9]{16}", words[4])
                and words[5] == "--discovery-token-ca-cert-hash" and re.fullmatch(r"sha256:[a-f0-9]{64}", words[6])):
            raise ValueError()
    except (TypeError, ValueError):
        raise BootstrapError("The control plane returned an unexpected join command; nothing was sent to the worker") from None
    return {"apiVersion": "kubeadm.k8s.io/v1beta4", "kind": "JoinConfiguration",
            "discovery": {"bootstrapToken": {"token": words[4], "apiServerEndpoint": words[2],
                                             "caCertHashes": [words[6]]}},
            "nodeRegistration": {"name": inventory["worker"]["name"],
                                 "criSocket": "unix:///run/containerd/containerd.sock"}}, words[4].split(".")[0]


def calico_vxlan(content):
    if hashlib.sha256(content).hexdigest() != CALICO_SHA256:
        raise BootstrapError("Calico checksum mismatch; no manifest was applied")
    text = content.decode("utf-8")
    for name, old, new in [("IPIP", "Always", "Never"), ("VXLAN", "Never", "Always")]:
        pattern = rf'(name: CALICO_IPV4POOL_{name}\n\s+value: )"{old}"'
        text, count = re.subn(pattern, rf'\g<1>"{new}"', text)
        if count != 1:
            raise BootstrapError("The pinned Calico manifest has an unexpected pool configuration")
    return text


def private_write(path, content):
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
    except FileExistsError:
        raise BootstrapError(f"Refusing to replace existing {path.name}") from None


def local_kubeconfig(content, inventory):
    try:
        remote = json.loads(content)
        if len(remote["clusters"]) != 1 or len(remote["users"]) != 1:
            raise ValueError()
        ca = remote["clusters"][0]["cluster"]["certificate-authority-data"]
        credentials = {field: remote["users"][0]["user"][field]
                       for field in ("client-certificate-data", "client-key-data")}
        for value in (ca, *credentials.values()):
            if not isinstance(value, str) or not base64.b64decode(value, validate=True):
                raise ValueError()
    except (KeyError, IndexError, TypeError, ValueError):
        raise BootstrapError("The control plane did not return embedded kubeadm credentials") from None
    name = inventory["name"]
    context = "kubeadm-" + name
    # Reconstruct the file so remote exec plugins and local file paths never reach the workstation.
    return {"apiVersion": "v1", "kind": "Config", "current-context": context,
            "clusters": [{"name": name, "cluster": {"server": "https://" + inventory["control"]["public_ip"] + ":6443",
                                                      "certificate-authority-data": ca}}],
            "users": [{"name": "lab-admin", "user": credentials}],
            "contexts": [{"name": context, "context": {"cluster": name, "user": "lab-admin"}}]}


class Runner:
    def __init__(self, identity):
        self.identity = identity

    def remote(self, node, command, input, label, timeout=60):
        return run(["ssh", "-i", str(self.identity), "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
                    "-o", "StrictHostKeyChecking=yes", "-o", "ForwardAgent=no", "-o", "ConnectTimeout=10",
                    "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3",
                    "cks@" + node["public_ip"], "sudo", "-n", *command], label, input, timeout)

    def script(self, node, script, label, timeout=60):
        return self.remote(node, ["bash", "-s"], "set -euo pipefail\numask 077\n" + script,
                           label, timeout)

    def prepared(self, node, version):
        for attempt in range(60):
            result = self.script(node, 'if test -f /var/lib/cks/prepared; then cat /var/lib/cks/prepared; else echo pending; fi',
                                 "SSH readiness check (verify host keys and ssh-agent first)").strip()
            if result == version:
                return
            if result != "pending":
                raise BootstrapError("VM package version differs from the selected Terraform profile")
            if attempt == 59:
                raise BootstrapError("VM package preparation did not finish; inspect /var/log/cks/prepare.log")
            time.sleep(5)


def bootstrap(directory, identity, engine):
    directory = directory.resolve(strict=True)
    if not directory.is_relative_to((ROOT / "work").resolve()) or directory == (ROOT / "work").resolve():
        raise BootstrapError("Use a dedicated Terraform directory beneath this repository's ignored work/")
    identity = identity.expanduser().resolve(strict=True)
    if not identity.is_file() or stat.S_IMODE(identity.stat().st_mode) & 0o077:
        raise BootstrapError("The SSH identity must be a private file readable only by its owner (chmod 600)")
    for tool in (engine, "ssh", "kubectl"):
        if not shutil.which(tool):
            raise BootstrapError(f"Install {tool} before bootstrapping")
    kubeconfig = directory / "kubeconfig"
    if kubeconfig.exists() or kubeconfig.is_symlink():
        raise BootstrapError("A kubeconfig already exists here; use the existing environment or a fresh Terraform directory")
    try:
        inventory = validate_inventory(json.loads(run([engine, f"-chdir={directory}", "output", "-json", "bootstrap"],
                                                       "Read Terraform output")))
        with urlopen(CALICO_URL, timeout=30) as response:
            manifest = calico_vxlan(response.read(4 * 1024 * 1024))
    except (OSError, ValueError):
        raise BootstrapError("Could not read the non-secret inventory or pinned CNI download") from None
    runner = Runner(identity)
    control, worker = inventory["control"], inventory["worker"]
    directory.chmod(0o700)
    print(f"Preparing {inventory['name']} in {inventory['project_id']} / {inventory['zone']}")
    for node in (control, worker):
        runner.prepared(node, inventory["kubernetes_version"])
        runner.script(node, f"test \"$(hostname -s)\" = {shlex.quote(node['name'])}\n"
                      "test ! -f /etc/kubernetes/admin.conf\ntest ! -f /etc/kubernetes/kubelet.conf\n",
                      "Check fresh VM identity and empty cluster state")
    print("Initializing the control plane")
    init = ["kubeadm", "init", "--kubernetes-version=" + inventory["kubernetes_version"],
            "--apiserver-advertise-address=" + control["private_ip"],
            "--control-plane-endpoint=" + control["private_ip"] + ":6443",
            "--apiserver-cert-extra-sans=" + control["public_ip"], "--node-name=" + control["name"],
            "--pod-network-cidr=192.168.0.0/16", "--cri-socket=unix:///run/containerd/containerd.sock",
            "--token-ttl=10m", "--skip-token-print"]
    runner.script(control, "install -d -m 0700 /var/log/cks\n" + shlex.join(init) +
                  " > /var/log/cks/init.log 2>&1\n", "Control-plane initialization", timeout=600)
    command = runner.remote(control, ["kubeadm", "token", "create", "--ttl=10m", "--print-join-command"],
                            None, "Create short-lived join credential")
    configuration, token_id = join_configuration(command, inventory)
    print("Joining the worker with a short-lived credential")
    try:
        runner.remote(worker, ["kubeadm", "join", "--config=/dev/stdin"], json.dumps(configuration),
                      "Worker join", timeout=300)
    finally:
        runner.remote(control, ["kubeadm", "token", "delete", token_id], None, "Revoke join credential")
    print("Installing checksum-verified Calico with VXLAN")
    runner.remote(control, ["env", "KUBECONFIG=/etc/kubernetes/admin.conf", "kubectl", "apply", "-f", "-"],
                  manifest, "Install Calico", timeout=180)
    content = runner.remote(control, ["kubectl", "config", "view", "--raw", "--minify", "-o", "json",
                                      "--kubeconfig=/etc/kubernetes/admin.conf"], None, "Retrieve private lab credentials")
    config = local_kubeconfig(content, inventory)
    private_write(kubeconfig, json.dumps(config))
    context = config["current-context"]
    kube = ["kubectl", "--kubeconfig", str(kubeconfig), "--context", context]
    for resource in ("daemonset/calico-node", "deployment/calico-kube-controllers", "deployment/coredns"):
        run(kube + ["--request-timeout=300s", "-n", "kube-system", "rollout", "status", resource, "--timeout=300s"],
            "Wait for " + resource, timeout=330)
    run(kube + ["--request-timeout=180s", "wait", "nodes", "--all", "--for=condition=Ready", "--timeout=180s"],
        "Wait for Ready nodes", timeout=210)
    env = dict(os.environ, KUBECONFIG=str(kubeconfig))
    run([sys.executable, str(ROOT / "scripts/lab.py"), "--context", context, "preflight"], "Lab preflight", timeout=180, env=env)
    print("Ready. Keep this kubeconfig private; continue with the shared baseline and first session.")
    print("export KUBECONFIG=" + shlex.quote(str(kubeconfig)))
    print("export LAB_CONTEXT=" + shlex.quote(context))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "work/kubeadm-gcp")
    parser.add_argument("--identity-file", type=Path, required=True)
    parser.add_argument("--engine", choices=("terraform", "tofu"), default="terraform")
    args = parser.parse_args(argv)
    try:
        bootstrap(args.directory, args.identity_file, args.engine)
        return 0
    except (BootstrapError, OSError, KeyboardInterrupt) as error:
        print(f"STOP: {error or 'interrupted'}")
        print("No reset or VM deletion was attempted. Inspect the private logs and use the documented recovery path.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
