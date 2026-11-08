# SPDX-License-Identifier: MIT
import contextlib
import copy
import io
import json
import subprocess
import unittest
from unittest.mock import patch

from scripts import lab


class DrillCluster:
    """Recorded kubectl responses, without evaluating the learner's policy."""
    def __init__(self):
        self.calls = []
        self.labels = {"pod-security.kubernetes.io/" + key: value for key, value in {
            "enforce": "restricted", "enforce-version": "v1.37", "audit": "baseline", "warn": "restricted"}.items()}
        self.version = "v1.37.1"
        self.denial = ('Error from server (Forbidden): violates PodSecurity "restricted:v1.37": '
                       'allowPrivilegeEscalation != false (container "probe" must set '
                       'securityContext.allowPrivilegeEscalation=false)')
        self.admissions = [(0, ""), (1, self.denial), (0, "")]
        self.pods = {}
        for namespace, name, tier, address in [
            ("cks-tiers", "frontend", "frontend", "10.0.0.1"),
            ("cks-tiers", "backend", "backend", "10.0.0.2"),
            ("cks-tiers", "intruder", "intruder", "10.0.0.3"),
            ("cks-data", "database", "database", "10.0.1.1"),
            ("cks-data", "frontend-witness", "frontend", "10.0.1.2"),
            ("cks-data", "backend-witness", "backend", "10.0.1.3"),
        ]:
            self.pods[namespace, name] = {
                "metadata": {"name": name, "namespace": namespace, "labels": {"tier": tier}},
                "spec": {"containers": [{"name": "app"}]},
                "status": {"phase": "Running", "podIP": address,
                           "conditions": [{"type": "Ready", "status": "True"}]},
            }
        self.responses = {
            ("cks-tiers", "frontend", "backend"): "LAB_OK\nbackend-witness\n",
            ("cks-tiers", "intruder", "backend"): "LAB_DENIED\nwget: download timed out\n",
            ("cks-data", "frontend-witness", "backend"): "LAB_DENIED\nwget: download timed out\n",
            ("cks-tiers", "backend", "database"): "LAB_OK\ndatabase-witness\n",
            ("cks-tiers", "frontend", "database"): "LAB_DENIED\nwget: download timed out\n",
            ("cks-tiers", "intruder", "database"): "LAB_DENIED\nwget: download timed out\n",
            ("cks-data", "backend-witness", "database"): "LAB_DENIED\nwget: download timed out\n",
        }
        self.policies = []
        self.get_count = 0
        self.lose_health = False

    def run(self, command, **options):
        self.calls.append((command, options))
        args, code, error = command[4:], 0, ""
        if args[0] == "version":
            output = {"serverVersion": {"gitVersion": self.version}}
        elif args[:2] == ["get", "namespace"]:
            output = {"metadata": {"labels": self.labels}}
        elif args[0] == "create":
            code, error = self.admissions.pop(0)
            output = json.loads(options["input"])
        elif args[:2] == ["get", "networkpolicies"]:
            output = {"items": self.policies}
        elif args[:2] == ["get", "pod"]:
            self.get_count += 1
            output = copy.deepcopy(self.pods[args[args.index("-n") + 1], args[2]])
            if self.lose_health and self.get_count > 6:
                output["status"]["conditions"][0]["status"] = "False"
        elif args[0] == "exec":
            destination = next(name for (namespace, name), pod in self.pods.items()
                               if name in {"backend", "database"} and pod["status"]["podIP"] in args[-1])
            output = self.responses[args[args.index("-n") + 1], args[1], destination]
        else:
            raise AssertionError(f"Unexpected command: {args}")
        return subprocess.CompletedProcess(command, code, output if isinstance(output, str) else json.dumps(output), error)


class DrillChecks(unittest.TestCase):
    def run_check(self, function, cluster):
        with patch("scripts.lab.subprocess.run", side_effect=cluster.run), contextlib.redirect_stdout(io.StringIO()):
            function(lab.Kubectl("kind-cks-test"))

    def test_mw01_uses_three_unique_server_dry_runs_and_one_field_negative(self):
        cluster = DrillCluster()
        self.run_check(lab.mw01, cluster)
        calls = [(command, json.loads(options["input"])) for command, options in cluster.calls if command[4] == "create"]
        self.assertEqual(len(calls), 3)
        self.assertTrue(all("--dry-run=server" in command for command, _ in calls))
        good, bad, other = [document for _, document in calls]
        self.assertEqual(len({doc["metadata"]["name"] for _, doc in calls}), 3)
        self.assertEqual([doc["metadata"]["namespace"] for _, doc in calls], ["cks-lab", "cks-lab", "cks-other"])
        self.assertIs(good["spec"]["containers"][0]["securityContext"]["allowPrivilegeEscalation"], False)
        self.assertIs(bad["spec"]["containers"][0]["securityContext"]["allowPrivilegeEscalation"], True)
        bad["spec"]["containers"][0]["securityContext"]["allowPrivilegeEscalation"] = False
        self.assertEqual(good["spec"], bad["spec"])
        self.assertIs(other["spec"]["containers"][0]["securityContext"]["allowPrivilegeEscalation"], True)

    def test_mw01_requires_restricted_pin_and_deliberate_audit_warn_modes(self):
        for key, value in [("enforce", "baseline"), ("enforce-version", "latest"),
                           ("enforce-version", "v1.36"), ("audit", ""), ("warn", "invalid")]:
            with self.subTest(key=key, value=value):
                cluster = DrillCluster()
                cluster.labels["pod-security.kubernetes.io/" + key] = value
                with self.assertRaises(lab.Failed):
                    self.run_check(lab.mw01, cluster)
                self.assertFalse(any(command[4] == "create" for command, _ in cluster.calls))

    def test_mw01_requires_a_parseable_server_version(self):
        cluster = DrillCluster()
        cluster.version = "unknown"
        with self.assertRaises(lab.Blocked):
            self.run_check(lab.mw01, cluster)

    def test_mw01_accepts_deliberate_alternative_audit_and_warn_levels(self):
        cluster = DrillCluster()
        cluster.labels["pod-security.kubernetes.io/warn"] = "privileged"
        self.run_check(lab.mw01, cluster)

    def test_mw01_cannot_pass_without_actual_restricted_enforcement(self):
        cluster = DrillCluster()
        cluster.admissions[1] = (0, "")
        with self.assertRaisesRegex(lab.Failed, "noncompliant Pod is denied"):
            self.run_check(lab.mw01, cluster)

    def test_mw01_rejects_unrelated_denials_and_unavailable_control(self):
        for index, reason in [(0, "Forbidden: cannot create pods"), (1, "Forbidden: cannot create pods"),
                              (1, "Invalid: unknown field"), (1, 'violates PodSecurity "restricted:v1.37": hostNetwork'),
                              (2, "admission webhook unavailable")]:
            with self.subTest(index=index, reason=reason):
                cluster = DrillCluster()
                cluster.admissions[index] = (1, reason)
                with self.assertRaises(lab.Blocked):
                    self.run_check(lab.mw01, cluster)

    def test_mw01_detects_restrictions_leaking_into_other_namespace(self):
        cluster = DrillCluster()
        cluster.admissions[2] = (1, cluster.denial)
        with self.assertRaisesRegex(lab.Failed, "cks-other"):
            self.run_check(lab.mw01, cluster)

    def test_cs06_checks_all_seven_paths_and_refreshes_positive_witnesses(self):
        cluster = DrillCluster()
        self.run_check(lab.cs06, cluster)
        self.assertEqual(cluster.get_count, 12)
        calls = [command for command, _ in cluster.calls if command[4] == "exec"]
        self.assertEqual(len(calls), 9)
        self.assertEqual({(cmd[cmd.index("-n") + 1], cmd[5]) for cmd in calls},
                         {("cks-tiers", "frontend"), ("cks-tiers", "intruder"), ("cks-tiers", "backend"),
                          ("cks-data", "frontend-witness"), ("cks-data", "backend-witness")})
        self.assertTrue(all(command[4] in {"get", "exec"} for command, _ in cluster.calls))

    def test_cs06_detects_broad_ingress_and_wrong_namespace_peers(self):
        for flow in [("cks-tiers", "intruder", "backend"), ("cks-data", "frontend-witness", "backend"),
                     ("cks-tiers", "frontend", "database"), ("cks-tiers", "intruder", "database"),
                     ("cks-data", "backend-witness", "database")]:
            with self.subTest(flow=flow):
                cluster = DrillCluster()
                cluster.responses[flow] = "LAB_OK\n" + flow[2] + "-witness\n"
                with self.assertRaises(lab.Failed):
                    self.run_check(lab.cs06, cluster)

    def test_cs06_broken_http_and_readiness_cannot_prove_denial(self):
        for response, exception in [("LAB_BROKEN\n", lab.Blocked),
                                    ("LAB_DENIED\nwget: server returned error: HTTP/1.1 403 Forbidden\n", lab.Failed),
                                    ("LAB_OK\nunexpected-page\n", lab.Failed)]:
            with self.subTest(response=response):
                cluster = DrillCluster()
                cluster.responses["cks-tiers", "intruder", "backend"] = response
                with self.assertRaises(exception):
                    self.run_check(lab.cs06, cluster)
        for after in (False, True):
            with self.subTest(after=after):
                cluster = DrillCluster()
                if after:
                    cluster.lose_health = True
                else:
                    cluster.pods["cks-data", "database"]["status"]["phase"] = "Pending"
                with self.assertRaises(lab.Blocked):
                    self.run_check(lab.cs06, cluster)

    def test_cs06_requires_working_positive_witnesses(self):
        cluster = DrillCluster()
        cluster.responses["cks-tiers", "frontend", "backend"] = "LAB_DENIED\nwget: connection refused\n"
        with self.assertRaises(lab.Failed):
            self.run_check(lab.cs06, cluster)

    def test_cs06_supports_ipv6_direct_addresses(self):
        cluster = DrillCluster()
        cluster.pods["cks-tiers", "backend"]["status"]["podIP"] = "fd00::2"
        cluster.pods["cks-data", "database"]["status"]["podIP"] = "fd00::3"
        self.run_check(lab.cs06, cluster)
        calls = [command for command, _ in cluster.calls if command[4] == "exec"]
        self.assertTrue(all(command[-1] in {"http://[fd00::2]:8080/", "http://[fd00::3]:8080/"} for command in calls))

    def test_cs06_rejects_egress_rules_that_could_mask_ingress(self):
        cluster = DrillCluster()
        cluster.policies = [{"spec": {"policyTypes": ["Egress"], "egress": []}}]
        with self.assertRaisesRegex(lab.Failed, "egress unrestricted"):
            self.run_check(lab.cs06, cluster)


if __name__ == "__main__":
    unittest.main()
