# SPDX-License-Identifier: MIT
import contextlib
import copy
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import lab


def pod(name, namespace="cks-lab"):
    return {"metadata": {"name": name, "namespace": namespace, "labels": {
                "app": "api" if name == "api" else name,
                "role": "intruder" if name == "intruder" else "client"}},
            "spec": {"serviceAccountName": "ch02-client", "automountServiceAccountToken": False,
                     "containers": [{"name": "app", "securityContext": {
                         "runAsNonRoot": True, "allowPrivilegeEscalation": False,
                         "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]},
                         "seccompProfile": {"type": "RuntimeDefault"}}}], "volumes": []},
            "status": {"phase": "Running", "podIP": "10.0.0.2" if namespace == "cks-lab" else "10.0.1.2",
                       "conditions": [{"type": "Ready", "status": "True"}]}}


class Cluster:
    """A kubectl boundary fake: no cluster commands run in these tests."""
    def __init__(self):
        self.calls = []
        self.uid = "cluster-uid"
        self.owner = None
        self.policy = None
        self.enforced = True
        self.ingress = True
        self.cleanup_fails = False
        self.exec_error = False
        self.wget_broken = False
        self.secret_watch = False
        self.pod_watch = False
        self.temporary_egress = True
        self.stale_egress = False
        self.deleted_probe = False
        self.denied_permission = None
        self.extra_rules = []
        self.incomplete_rules = False
        self.resolver = "search cks-lab.svc.example.test svc.example.test example.test\nnameserver 10.96.0.10\n"
        self.token_volume = False
        self.root_mount = "rw"
        self.runtime = "Uid:\t1000\t1000\t1000\t1000\nGid:\t1000\t1000\t1000\t1000\nCapEff:\t0000000000000000\nNoNewPrivs:\t1\nSeccomp:\t2\n"

    def run(self, command, **options):
        self.calls.append((command, options))
        args = command[4:]
        out, err, code = "", "", 0
        if args[:1] == ["version"]:
            out = {"clientVersion": {"gitVersion": "v1.37.1"}, "serverVersion": {"gitVersion": "v1.37.1"}}
        elif args[:2] == ["get", "namespace"]:
            out = {"metadata": {"name": args[2], "uid": self.uid,
                                "annotations": {"cks-practice/environment-id": self.owner} if self.owner else {}}}
        elif args[:2] == ["get", "nodes"]:
            out = {"items": [{"metadata": {"name": "worker"}, "spec": {}, "status": {
                "conditions": [{"type": "Ready", "status": "True"}],
                "nodeInfo": {"operatingSystem": "linux", "kernelVersion": "6.8", "containerRuntimeVersion": "containerd://2.0"}}}]}
        elif args[:2] == ["get", "daemonsets"] or args[:2] == ["get", "runtimeclasses"]:
            out = {"items": []}
        elif args[:2] == ["auth", "can-i"]:
            verb, resource = args[2:4]
            impersonating = any(a.startswith("--as=") for a in args)
            allowed = not impersonating or (resource == "pods" and verb in {"get", "list"} and "cks-other" not in args)
            allowed |= impersonating and resource == "secrets" and verb == "watch" and self.secret_watch
            allowed |= impersonating and resource == "pods" and verb == "watch" and self.pod_watch
            if not impersonating and (verb, resource) == self.denied_permission:
                allowed = False
            out, code = ("yes\n", 0) if allowed else ("no\n", 1)
        elif args[:2] == ["get", "pod"]:
            out = pod(args[2], args[args.index("-n") + 1])
            if self.token_volume and args[2] == "ch02-client":
                out["spec"]["volumes"] = [{"projected": {"sources": [{"serviceAccountToken": {"path": "token"}}]}}]
        elif args[:2] == ["get", "serviceaccount"]:
            out = {"automountServiceAccountToken": False}
        elif args[:2] == ["get", "networkpolicy"]:
            out = copy.deepcopy(self.policy) if self.policy else ""
        elif args[:1] == ["create"]:
            document = json.loads(options["input"])
            if document["kind"] == "SelfSubjectRulesReview":
                rules = [{"apiGroups": ["authorization.k8s.io"], "resources": ["selfsubjectaccessreviews", "selfsubjectrulesreviews"], "verbs": ["create"]}]
                rules += [{"apiGroups": ["certificates.k8s.io"], "resources": ["clustertrustbundles"],
                           "verbs": ["get", "list", "watch"]}]
                if document["spec"]["namespace"] == "cks-lab":
                    rules += [{"apiGroups": [""], "resources": ["pods"], "verbs": ["get", "list"]}] + self.extra_rules
                out = {"status": {"incomplete": self.incomplete_rules, "resourceRules": rules}}
            else:
                self.policy = document
                self.policy["metadata"]["uid"] = "owned-policy-uid"
                out = copy.deepcopy(self.policy)
        elif args[:1] == ["delete"]:
            if self.cleanup_fails:
                code, err = 1, "cleanup forbidden"
            else:
                self.policy = None
                self.deleted_probe = True
                out = {"status": "Success"}
        elif args[:1] == ["exec"]:
            if self.exec_error:
                return subprocess.CompletedProcess(command, 1, "", "unable to upgrade connection")
            name, namespace = args[1], args[args.index("-n") + 1]
            script = args[args.index("-c") + 1]
            if "wget" in script:
                if self.wget_broken:
                    out = "LAB_BROKEN\n"
                else:
                    target = args[-1]
                    probe_egress = ((bool(self.policy) and self.temporary_egress)
                                    or (self.deleted_probe and self.stale_egress)) and name == "intruder"
                    denied = self.enforced and ((namespace == "cks-other" and "10.0.0.2" in target)
                        or (namespace == "cks-lab" and "10.0.1.2" in target and not probe_egress)
                        or (name == "intruder" and "10.0.0.2" in target and (not probe_egress or self.ingress)))
                    out = "LAB_DENIED\nwget: download timed out\n" if denied else "LAB_OK\ncks-practice\n"
            elif "nslookup" in script:
                out = "LAB_DNS_OK\n"
            elif "/etc/resolv.conf" in script:
                out = self.resolver
            elif "/proc/1/status" in script:
                out = self.runtime
            elif "/proc/mounts" in script:
                out = f"overlay / overlay {self.root_mount},relatime 0 0\n"
            elif "LAB_TMP" in script:
                out = "LAB_TMP_OK\n"
            elif "LAB_ROOT" in script:
                out = "LAB_ROOT_DENIED\n" if self.root_mount == "ro" else "LAB_ROOT_WRITABLE\n"
            elif "LAB_TOKEN" in script:
                out = "LAB_TOKEN_ABSENT\n"
            else:
                raise AssertionError(f"unexpected exec script: {script}")
        else:
            raise AssertionError(f"unexpected kubectl command: {args}")
        if isinstance(out, (dict, list)):
            out = json.dumps(out)
        return subprocess.CompletedProcess(command, code, out, err)


class LabTests(unittest.TestCase):
    def invoke(self, cluster, *args, context="practice", external=True):
        output = io.StringIO()
        arguments = ["--context", context, *args]
        if args[0] == "verify" and external:
            arguments += ["--external-lab-uid", cluster.uid]
        with patch("scripts.lab.subprocess.run", side_effect=cluster.run), contextlib.redirect_stdout(output):
            code = lab.main(arguments)
        return code, output.getvalue()

    def test_unknown_cluster_is_blocked_before_any_pod_probe_or_write(self):
        cluster = Cluster()
        code, output = self.invoke(cluster, "verify", "CS01", external=False)
        self.assertEqual(code, 2, output)
        self.assertTrue(all(cmd[4:6] == ["get", "namespace"] for cmd, _ in cluster.calls))

    def test_wrong_external_uid_is_blocked_without_mutation(self):
        cluster = Cluster()
        code, output = self.invoke(cluster, "verify", "CS01", "--external-lab-uid", "another-cluster", external=False)
        self.assertEqual(code, 2, output)
        self.assertFalse(any(cmd[4] in {"create", "delete", "exec"} for cmd, _ in cluster.calls))

    def test_registered_identity_must_match_even_with_external_acknowledgement(self):
        for broken in (None, "uid", "owner", "json", "symlink"):
            with self.subTest(broken=broken), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                record = root / "work/environments/cks-test/environment.json"
                record.parent.mkdir(parents=True)
                cluster = Cluster()
                cluster.owner = "00000000-0000-4000-8000-000000000001"
                state = {"name": "cks-test", "owner": cluster.owner, "namespace_uid": cluster.uid, "phase": "ready"}
                if broken == "uid": state["namespace_uid"] = "other-uid"
                if broken == "owner": state["owner"] = "00000000-0000-4000-8000-000000000002"
                record.write_text("broken" if broken == "json" else json.dumps(state))
                if broken == "symlink":
                    target = root / "record.json"
                    record.rename(target)
                    record.symlink_to(target)
                with patch.object(lab, "ROOT", root):
                    code, output = self.invoke(cluster, "verify", "CH02", context="kind-cks-test", external=broken is not None)
                self.assertEqual(code, 0 if broken is None else 2, output)
                if broken:
                    self.assertFalse(any(cmd[4] in {"create", "delete", "exec"} for cmd, _ in cluster.calls))

    def test_context_is_mandatory(self):
        with patch("scripts.lab.subprocess.run") as run, contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            lab.main(["preflight"])
        run.assert_not_called()

    def test_preflight_is_read_only_and_cannot_claim_enforcement(self):
        cluster = Cluster()
        code, output = self.invoke(cluster, "preflight")
        self.assertEqual(code, 0, output)
        self.assertIn("UNKNOWN", output)
        for command, options in cluster.calls:
            self.assertEqual(command[:4], ["kubectl", "--context", "practice", "--request-timeout=10s"])
            self.assertIn(command[4], {"get", "version", "auth"})
            self.assertLessEqual(options["timeout"], 20)

    def test_named_and_subresource_permission_checks_use_kubectl_syntax(self):
        cluster = Cluster()
        self.invoke(cluster, "preflight")
        commands = [cmd for cmd, _ in cluster.calls]
        self.assertTrue(any("serviceaccounts/ch02-client" in cmd for cmd in commands))
        self.assertTrue(any("--subresource=exec" in cmd and "pods" in cmd for cmd in commands))
        self.assertFalse(any("--resource-name" in cmd or "pods/exec" in cmd for cmd in commands))

    def test_preflight_requires_cleanup_permissions(self):
        cluster = Cluster()
        cluster.denied_permission = ("delete", "rolebindings")
        code, output = self.invoke(cluster, "preflight")
        self.assertEqual(code, 2)
        self.assertIn("delete cks-lab/rolebindings", output)

    def test_cs01_verifies_and_removes_owned_probe_with_uid_precondition(self):
        cluster = Cluster()
        code, output = self.invoke(cluster, "verify", "CS01")
        self.assertEqual(code, 0, output)
        self.assertIsNone(cluster.policy)
        deletes = [(cmd, opts) for cmd, opts in cluster.calls if cmd[4] == "delete"]
        self.assertEqual(len(deletes), 1)
        self.assertEqual(json.loads(deletes[0][1]["input"])["preconditions"]["uid"], "owned-policy-uid")

    def test_cs01_detects_missing_ingress_even_when_egress_masks_it(self):
        cluster = Cluster()
        cluster.ingress = False
        code, output = self.invoke(cluster, "verify", "CS01")
        self.assertEqual(code, 1, output)
        self.assertIsNone(cluster.policy)

    def test_cs01_non_enforcing_cni_fails(self):
        cluster = Cluster()
        cluster.enforced = False
        self.assertEqual(self.invoke(cluster, "verify", "CS01")[0], 1)

    def test_inactive_temporary_egress_cannot_prove_ingress(self):
        cluster = Cluster()
        cluster.temporary_egress = False
        with patch("scripts.lab.time.sleep"):
            self.assertEqual(self.invoke(cluster, "verify", "CS01")[0], 2)
        self.assertIsNone(cluster.policy)

    def test_cs01_cannot_pass_before_probe_egress_is_withdrawn(self):
        cluster = Cluster()
        cluster.stale_egress = True
        with patch("scripts.lab.time.sleep"):
            self.assertEqual(self.invoke(cluster, "verify", "CS01")[0], 2)
        self.assertIsNone(cluster.policy)

    def test_cs01_preserves_existing_probe(self):
        cluster = Cluster()
        cluster.policy = {"metadata": {"uid": "someone-elses"}}
        self.assertEqual(self.invoke(cluster, "verify", "CS01")[0], 2)
        self.assertEqual(cluster.policy["metadata"]["uid"], "someone-elses")
        self.assertFalse(any(cmd[4] in {"create", "delete"} for cmd, _ in cluster.calls))

    def test_cleanup_failure_is_never_pass(self):
        cluster = Cluster()
        cluster.cleanup_fails = True
        code, output = self.invoke(cluster, "verify", "CS01")
        self.assertEqual(code, 2, output)
        self.assertIn("cleanup", output.lower())

    def test_broken_exec_and_missing_wget_are_blocked(self):
        for setting in ["exec_error", "wget_broken"]:
            cluster = Cluster()
            setattr(cluster, setting, True)
            self.assertEqual(self.invoke(cluster, "verify", "CS01")[0], 2)

    def test_ch02_checks_group_grants_and_secret_watch(self):
        cluster = Cluster()
        self.assertEqual(self.invoke(cluster, "verify", "CH02")[0], 0)
        impersonated = [cmd for cmd, _ in cluster.calls if any(a.startswith("--as=") for a in cmd)]
        self.assertTrue(impersonated)
        self.assertTrue(all("--as-group=system:serviceaccounts:cks-lab" in cmd for cmd in impersonated))
        cluster.secret_watch = True
        self.assertEqual(self.invoke(cluster, "verify", "CH02")[0], 1)

    def test_ch02_rejects_projected_token_despite_absent_default_path(self):
        cluster = Cluster()
        cluster.token_volume = True
        self.assertEqual(self.invoke(cluster, "verify", "CH02")[0], 1)

    def test_ch02_rejects_extra_pod_watch_permission(self):
        cluster = Cluster()
        cluster.pod_watch = True
        self.assertEqual(self.invoke(cluster, "verify", "CH02")[0], 1)

    def test_ch02_rejects_named_secret_and_pod_mutation_grants(self):
        for resource, verb in [("secrets", "get"), ("pods", "patch")]:
            cluster = Cluster()
            cluster.extra_rules = [{"apiGroups": [""], "resources": [resource],
                                    "verbs": [verb], "resourceNames": ["training-secret"]}]
            self.assertEqual(self.invoke(cluster, "verify", "CH02")[0], 1)

    def test_ch02_incomplete_rule_inventory_is_blocked(self):
        cluster = Cluster()
        cluster.incomplete_rules = True
        self.assertEqual(self.invoke(cluster, "verify", "CH02")[0], 2)

    def test_rule_review_does_not_require_crd_discovery_permissions(self):
        cluster = Cluster()
        self.invoke(cluster, "verify", "CH02")
        reviews = [cmd for cmd, opts in cluster.calls
                   if opts.get("input") and json.loads(opts["input"]).get("kind") == "SelfSubjectRulesReview"]
        self.assertEqual(len(reviews), 2)
        self.assertTrue(all("--raw" in cmd and
                            "/apis/authorization.k8s.io/v1/selfsubjectrulesreviews" in cmd for cmd in reviews))

    def test_dns_uses_cluster_suffix_from_resolver_search_path(self):
        cluster = Cluster()
        self.invoke(cluster, "verify", "CS01")
        self.assertTrue(any(cmd[-1] == "api.cks-lab.svc.example.test." for cmd, _ in cluster.calls))

    def test_mw02_requires_actual_read_only_mount(self):
        cluster = Cluster()
        self.assertEqual(self.invoke(cluster, "verify", "MW02")[0], 1)
        cluster.root_mount = "ro"
        self.assertEqual(self.invoke(cluster, "verify", "MW02")[0], 0)

    def test_mw02_rejects_runtime_capabilities_and_unfiltered_seccomp(self):
        for old, new in [("0000000000000000", "0000000000000001"), ("Seccomp:\t2", "Seccomp:\t0")]:
            cluster = Cluster()
            cluster.root_mount = "ro"
            cluster.runtime = cluster.runtime.replace(old, new)
            self.assertEqual(self.invoke(cluster, "verify", "MW02")[0], 1)

    def test_timeout_and_api_error_do_not_expose_output(self):
        for failure in [subprocess.TimeoutExpired("kubectl", 20, output="secret-token"),
                        subprocess.CompletedProcess([], 1, "secret-token", "secret-token")]:
            with patch("scripts.lab.subprocess.run", side_effect=failure if isinstance(failure, Exception) else None,
                       return_value=failure), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(lab.main(["--context", "practice", "preflight"]), 2)
            self.assertNotIn("secret-token", output.getvalue())

    def test_ipv6_http_addresses_are_bracketed(self):
        self.assertEqual(lab.http_url("fd00::1"), "http://[fd00::1]:8080/")


if __name__ == "__main__":
    unittest.main()
