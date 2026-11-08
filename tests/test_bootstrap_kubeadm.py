# SPDX-License-Identifier: MIT
import hashlib
import contextlib
import io
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import bootstrap_kubeadm as bootstrap


def inventory():
    return {"project_id": "practice-project", "zone": "europe-west1-b", "name": "cks-practice",
            "ssh_user": "cks", "kubernetes_version": "1.37.0",
            "control": {"name": "cks-practice-control", "private_ip": "10.92.0.10", "public_ip": "203.0.113.10"},
            "worker": {"name": "cks-practice-worker", "private_ip": "10.92.0.11", "public_ip": "203.0.113.11"}}


class BootstrapTests(unittest.TestCase):
    def test_inventory_rejects_shell_content_and_shared_addresses(self):
        self.assertEqual(bootstrap.validate_inventory(inventory())["name"], "cks-practice")
        for key, value in [("name", "cks-test;echo wrong"), ("ssh_user", "root"),
                           ("kubernetes_version", "1.37.0;true")]:
            data = inventory(); data[key] = value
            with self.subTest(key=key), self.assertRaises(bootstrap.BootstrapError):
                bootstrap.validate_inventory(data)
        data = inventory(); data["worker"]["public_ip"] = data["control"]["public_ip"]
        with self.assertRaises(bootstrap.BootstrapError):
            bootstrap.validate_inventory(data)

    def test_join_config_preserves_ca_pin_and_keeps_token_out_of_argv(self):
        token = "abcdef.0000000000000000"
        line = f"kubeadm join 10.92.0.10:6443 --token {token} --discovery-token-ca-cert-hash sha256:" + "a" * 64
        config, token_id = bootstrap.join_configuration(line, inventory())
        self.assertEqual(config["discovery"]["bootstrapToken"]["token"], token)
        self.assertEqual(config["discovery"]["bootstrapToken"]["caCertHashes"], ["sha256:" + "a" * 64])
        self.assertEqual(config["discovery"]["bootstrapToken"]["apiServerEndpoint"], "10.92.0.10:6443")
        self.assertEqual(token_id, "abcdef")
        for bad in [line.replace("10.92.0.10", "10.92.0.12"), line + " --discovery-token-unsafe-skip-ca-verification", "echo " + line]:
            with self.subTest(bad=bad), self.assertRaises(bootstrap.BootstrapError):
                bootstrap.join_configuration(bad, inventory())

    def test_calico_requires_exact_download_before_switching_encapsulation(self):
        manifest = b'- name: CALICO_IPV4POOL_IPIP\n  value: "Always"\n- name: CALICO_IPV4POOL_VXLAN\n  value: "Never"\n'
        with patch.object(bootstrap, "CALICO_SHA256", hashlib.sha256(manifest).hexdigest()):
            changed = bootstrap.calico_vxlan(manifest)
            self.assertIn('IPIP\n  value: "Never"', changed)
            self.assertIn('VXLAN\n  value: "Always"', changed)
            with self.assertRaises(bootstrap.BootstrapError):
                bootstrap.calico_vxlan(manifest + b'changed')

    def test_ssh_always_requires_known_host_and_uses_stdin(self):
        runner = bootstrap.Runner(Path('/tmp/private-key'))
        with patch('scripts.bootstrap_kubeadm.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'ok', '')) as run:
            runner.remote(inventory()['worker'], ['kubeadm', 'join', '--config=/dev/stdin'], 'private-token', 'join')
        command = run.call_args.args[0]
        self.assertIn('StrictHostKeyChecking=yes', command)
        self.assertIn('BatchMode=yes', command)
        self.assertIn('ForwardAgent=no', command)
        self.assertNotIn('private-token', ' '.join(command))
        self.assertEqual(run.call_args.kwargs['input'], 'private-token')

    def test_errors_never_echo_sensitive_stdout_or_stderr(self):
        with patch('scripts.bootstrap_kubeadm.subprocess.run', return_value=subprocess.CompletedProcess([], 1, 'secret-token', 'private-key')):
            with self.assertRaises(bootstrap.BootstrapError) as raised:
                bootstrap.run(['ssh'], 'connection')
        self.assertNotIn('secret-token', str(raised.exception))
        self.assertNotIn('private-key', str(raised.exception))

    def test_kubeconfig_copies_only_embedded_credentials(self):
        remote = {"clusters": [{"cluster": {"server": "https://unexpected.invalid", "certificate-authority-data": "Y2E="}}],
                  "users": [{"user": {"client-certificate-data": "Y2VydA==", "client-key-data": "a2V5",
                                       "exec": {"command": "must-never-run"}, "tokenFile": "/private/file"}}]}
        local = bootstrap.local_kubeconfig(json.dumps(remote), inventory())
        self.assertEqual(local["clusters"][0]["cluster"]["server"], "https://203.0.113.10:6443")
        self.assertNotIn("exec", local["users"][0]["user"])
        self.assertNotIn("tokenFile", local["users"][0]["user"])
        del remote["users"][0]["user"]["client-key-data"]
        with self.assertRaises(bootstrap.BootstrapError):
            bootstrap.local_kubeconfig(json.dumps(remote), inventory())

    def test_private_file_is_exclusive_and_mode_600(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'kubeconfig'
            bootstrap.private_write(path, 'credential')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(bootstrap.BootstrapError):
                bootstrap.private_write(path, 'replacement')
            self.assertEqual(path.read_text(), 'credential')


class BootstrapFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / "work/vms"
        self.directory.mkdir(parents=True)
        self.identity = self.root / "key"
        self.identity.write_text("private-key-fixture")
        self.identity.chmod(0o600)
        self.calls = []
        self.join_fails = False
        self.existing_cluster = False
        self.token = "abcdef.0000000000000000"
        self.manifest = b'- name: CALICO_IPV4POOL_IPIP\n  value: "Always"\n- name: CALICO_IPV4POOL_VXLAN\n  value: "Never"\n'

    def execute(self, command, **options):
        self.calls.append((command, options))
        output, code = "", 0
        if command[0] == "terraform":
            output = json.dumps(inventory())
        elif command[0] == "ssh":
            script = options.get("input") or ""
            if "/var/lib/cks/prepared" in script:
                output = "1.37.0\n"
            elif "test ! -f /etc/kubernetes/admin.conf" in script:
                code = 1 if self.existing_cluster else 0
            elif "--print-join-command" in command:
                output = f"kubeadm join 10.92.0.10:6443 --token {self.token} --discovery-token-ca-cert-hash sha256:" + "a" * 64
            elif "join" in command:
                code = 1 if self.join_fails else 0
            elif "view" in command:
                output = json.dumps({"clusters": [{"cluster": {"certificate-authority-data": "Y2E="}}],
                                     "users": [{"user": {"client-certificate-data": "Y2VydA==", "client-key-data": "a2V5"}}]})
        return subprocess.CompletedProcess(command, code, output, self.token if code else "")

    def invoke(self):
        with patch.object(bootstrap, "ROOT", self.root), patch.object(bootstrap, "CALICO_SHA256", hashlib.sha256(self.manifest).hexdigest()), \
                patch("scripts.bootstrap_kubeadm.shutil.which", return_value="/tool"), \
                patch("scripts.bootstrap_kubeadm.urlopen", return_value=io.BytesIO(self.manifest)), \
                patch("scripts.bootstrap_kubeadm.subprocess.run", side_effect=self.execute), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            bootstrap.bootstrap(self.directory, self.identity, "terraform")
        return output.getvalue()

    def test_complete_flow_keeps_token_in_stdin_and_writes_private_config(self):
        output = self.invoke()
        self.assertNotIn(self.token, output)
        self.assertTrue(all(self.token not in " ".join(command) for command, _ in self.calls))
        join = [(command, opts) for command, opts in self.calls if "join" in command]
        self.assertEqual(len(join), 1)
        self.assertEqual(json.loads(join[0][1]["input"])["discovery"]["bootstrapToken"]["token"], self.token)
        self.assertTrue(any("delete" in command and "abcdef" in command for command, _ in self.calls))
        path = self.directory / "kubeconfig"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(json.loads(path.read_text())["current-context"], "kubeadm-cks-practice")

    def test_failed_join_still_revokes_token_and_does_not_write_config(self):
        self.join_fails = True
        with self.assertRaises(bootstrap.BootstrapError) as raised:
            self.invoke()
        self.assertNotIn(self.token, str(raised.exception))
        self.assertTrue(any("delete" in command and "abcdef" in command for command, _ in self.calls))
        self.assertFalse((self.directory / "kubeconfig").exists())

    def test_readiness_requests_allow_the_documented_wait_duration(self):
        self.invoke()
        rollouts = [(cmd, options) for cmd, options in self.calls if "rollout" in cmd]
        self.assertEqual(len(rollouts), 3)
        for command, options in rollouts:
            self.assertIn("--request-timeout=300s", command)
            self.assertIn("--timeout=300s", command)
            self.assertEqual(options["timeout"], 330)
        waits = [(cmd, options) for cmd, options in self.calls if "wait" in cmd and "nodes" in cmd]
        self.assertEqual(len(waits), 1)
        self.assertIn("--request-timeout=180s", waits[0][0])
        self.assertIn("--timeout=180s", waits[0][0])
        self.assertEqual(waits[0][1]["timeout"], 210)

    def test_existing_cluster_is_never_reset_or_initialized(self):
        self.existing_cluster = True
        with self.assertRaises(bootstrap.BootstrapError):
            self.invoke()
        self.assertFalse(any("kubeadm init" in (options.get("input") or "") for _, options in self.calls))
        self.assertFalse(any("reset" in command for command, _ in self.calls))

    def test_existing_kubeconfig_is_preserved_before_any_subprocess(self):
        path = self.directory / "kubeconfig"
        path.write_text("existing")
        with self.assertRaises(bootstrap.BootstrapError):
            self.invoke()
        self.assertEqual(path.read_text(), "existing")
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
