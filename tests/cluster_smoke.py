# SPDX-License-Identifier: MIT
"""Behavioral checks for an otherwise empty, disposable kind cluster."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import lab


def require_result(result, expected=0, reason=""):
    if result.returncode != expected or (reason and reason not in result.stdout + result.stderr):
        raise RuntimeError(f"Expected exit {expected} with {reason!r}; got "
                           f"{result.returncode}: {result.stdout}{result.stderr}")


def wait_for_denial(request, reason):
    for attempt in range(20):
        result = request()
        if result.returncode != 0 or attempt == 19:
            require_result(result, 1, reason)
            return
        time.sleep(0.5)


class ResultChecks(unittest.TestCase):
    def test_smoke_rejects_unknown_identity_before_any_cluster_command(self):
        with patch.object(lab, "verify_identity", side_effect=lab.Blocked("identity not acknowledged")), \
                patch("subprocess.run") as command:
            with self.assertRaisesRegex(RuntimeError, "identity not acknowledged"):
                smoke("kind-cks-test")
            command.assert_not_called()

    def test_expected_denial_requires_its_reason(self):
        require_result(subprocess.CompletedProcess([], 1, "FAIL: intended denial", ""), 1, "intended denial")
        with self.assertRaises(RuntimeError):
            require_result(subprocess.CompletedProcess([], 1, "FAIL: unrelated failure", ""), 1, "intended denial")

    def test_blocked_or_success_cannot_count_as_expected_failure(self):
        for code in (0, 2):
            with self.subTest(code=code), self.assertRaises(RuntimeError):
                require_result(subprocess.CompletedProcess([], code, "intended denial", ""), 1, "intended denial")

    def test_admission_waits_for_the_named_policy(self):
        results = iter([subprocess.CompletedProcess([], 0, "accepted", ""),
                        subprocess.CompletedProcess([], 1, "", "named policy denial")])
        wait_for_denial(lambda: next(results), "named policy denial")
        with self.assertRaises(RuntimeError):
            wait_for_denial(lambda: subprocess.CompletedProcess([], 1, "", "unrelated error"), "named policy denial")


def smoke(context, external_lab_uid=None):
    try:
        lab.verify_identity(lab.Kubectl(context), external_lab_uid)
    except lab.Blocked as error:
        raise RuntimeError(str(error)) from None

    def request(*args, document=None):
        return subprocess.run(
            ["kubectl", "--context", context, "--request-timeout=30s", *args],
            input=json.dumps(document) if document is not None else None,
            text=True, capture_output=True, timeout=180, cwd=ROOT,
        )
    def kubectl(*args, document=None, expected=0, reason=""):
        result = request(*args, document=document)
        require_result(result, expected, reason)
        return result.stdout

    def verify(drill, expected=0, reason=""):
        deadline = time.monotonic() + 90
        while True:
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/lab.py"), "--context", context,
                 "verify", drill, *(["--external-lab-uid", external_lab_uid] if external_lab_uid else [])],
                text=True, capture_output=True, timeout=180,
            )
            if result.returncode == expected:
                require_result(result, expected, reason)
                print(result.stdout, end="")
                return
            if result.returncode == 2 or time.monotonic() >= deadline:
                require_result(result, expected, reason)
            time.sleep(2)

    # Refuse existing work before creating any fixture or policy.
    for resource, names in [("namespace", ["cks-lab", "cks-other"]),
                            ("validatingadmissionpolicy", ["cks-allowed-registries"]),
                            ("validatingadmissionpolicybinding", ["cks-allowed-registries"])]:
        if kubectl("get", resource, *names, "--ignore-not-found", "-o", "name").strip():
            raise RuntimeError("Smoke checks require an empty disposable cluster.")

    try:
        kubectl("apply", "-f", "labs/fixtures/workloads.yaml")
        for namespace in ("cks-lab", "cks-other"):
            kubectl("wait", "-n", namespace, "--for=condition=Ready", "pod", "--all", "--timeout=120s")
        verify("CS01", 1, "FAIL: intruder is blocked before the independent ingress check")
        kubectl("apply", "-f", "solutions/network-policy.yaml")
        verify("CS01")
        kubectl("patch", "networkpolicy", "cs01-api-ingress", "-n", "cks-lab", "--type=json",
                "-p", json.dumps([{"op": "replace", "path": "/spec/ingress/0/from/0/podSelector", "value": {}}]))
        verify("CS01", 1, "FAIL: API ingress independently denies the intruder")
        kubectl("apply", "-f", "solutions/network-policy.yaml")
        verify("CS01")
        kubectl("delete", "-f", "solutions/network-policy.yaml")

        kubectl("apply", "-f", "solutions/serviceaccount.yaml")
        kubectl("wait", "-n", "cks-lab", "--for=condition=Ready", "pod/ch02-client", "--timeout=120s")
        verify("CH02")
        role = json.loads(kubectl("get", "role", "ch02-pod-reader", "-n", "cks-lab", "-o", "json"))
        wrong_rules = role["rules"] + [{"apiGroups": [""], "resources": ["secrets"], "verbs": ["list"]}]
        kubectl("patch", "role", "ch02-pod-reader", "-n", "cks-lab", "--type=merge",
                "-p", json.dumps({"rules": wrong_rules}))
        verify("CH02", 1, "FAIL: ServiceAccount cannot list cks-lab/secrets")
        kubectl("patch", "role", "ch02-pod-reader", "-n", "cks-lab", "--type=merge",
                "-p", json.dumps({"rules": role["rules"]}))
        verify("CH02")
        named_rules = role["rules"] + [{"apiGroups": [""], "resources": ["secrets"],
                                       "verbs": ["get"], "resourceNames": ["training-secret"]}]
        kubectl("patch", "role", "ch02-pod-reader", "-n", "cks-lab", "--type=merge",
                "-p", json.dumps({"rules": named_rules}))
        verify("CH02", 1, "FAIL: no extra resource grants in cks-lab, including named-resource grants")
        kubectl("patch", "role", "ch02-pod-reader", "-n", "cks-lab", "--type=merge",
                "-p", json.dumps({"rules": role["rules"]}))
        verify("CH02")

        kubectl("apply", "-f", "solutions/workload.yaml")
        kubectl("wait", "-n", "cks-lab", "--for=condition=Ready", "pod/demo", "--timeout=120s")
        verify("MW02")
        pod = json.loads(kubectl("create", "--dry-run=client", "-f", "solutions/workload.yaml", "-o", "json"))
        wrong = copy.deepcopy(pod)
        wrong["spec"]["containers"][0]["securityContext"]["readOnlyRootFilesystem"] = False
        kubectl("delete", "pod", "demo", "-n", "cks-lab", "--wait=true")
        kubectl("create", "-f", "-", document=wrong)
        kubectl("wait", "-n", "cks-lab", "--for=condition=Ready", "pod/demo", "--timeout=120s")
        verify("MW02", 1, "FAIL: requested workload restrictions are configured")
        kubectl("delete", "pod", "demo", "-n", "cks-lab", "--wait=true")
        kubectl("create", "-f", "-", document=pod)
        kubectl("wait", "-n", "cks-lab", "--for=condition=Ready", "pod/demo", "--timeout=120s")
        verify("MW02")

        kubectl("apply", "-f", "labs/fixtures/registry-policy.yaml")
        kubectl("label", "namespace", "cks-lab", "cks-practice=admission")
        generation = json.loads(kubectl("get", "validatingadmissionpolicy", "cks-allowed-registries", "-o", "json"))["metadata"]["generation"]
        kubectl("wait", "validatingadmissionpolicy/cks-allowed-registries",
                f"--for=jsonpath={{.status.observedGeneration}}={generation}", "--timeout=60s")
        status = json.loads(kubectl("get", "validatingadmissionpolicy", "cks-allowed-registries", "-o", "json"))["status"]
        if status.get("typeChecking", {}).get("expressionWarnings"):
            raise RuntimeError("Admission policy has CEL type-checking warnings.")

        def admission(document, reason=""):
            kubectl("create", "--dry-run=server", "-f", "-", document=document,
                    expected=1 if reason else 0, reason=reason)

        ordinary = copy.deepcopy(pod)
        ordinary["metadata"]["name"] = "admission-probe"
        wrong_main = copy.deepcopy(ordinary)
        wrong_main["spec"]["containers"][0]["image"] = "example.invalid/artifact:v1"
        wait_for_denial(lambda: request("create", "--dry-run=server", "-f", "-", document=wrong_main),
                        "Ordinary container images must use an allowed registry prefix.")
        admission(ordinary)
        minimal = copy.deepcopy(ordinary)
        del minimal["spec"]["volumes"]
        del minimal["spec"]["containers"][0]["volumeMounts"]
        admission(minimal)
        admission(wrong_main, "Ordinary container images must use an allowed registry prefix.")
        wrong_main["metadata"]["namespace"] = "cks-other"
        admission(wrong_main)
        init_pod = copy.deepcopy(ordinary)
        init_pod["spec"]["initContainers"] = [{
            "name": "prepare", "image": "docker.io/library/busybox:1.37", "command": ["true"],
            "securityContext": copy.deepcopy(pod["spec"]["containers"][0]["securityContext"]),
        }]
        admission(init_pod)
        init_pod["spec"]["initContainers"][0]["image"] = "example.invalid/artifact:v1"
        admission(init_pod, "Init container images must use an allowed registry prefix.")
        for allowed in (True, False):
            volume_pod = copy.deepcopy(ordinary)
            volume_pod["metadata"]["name"] = "volume-probe"
            volume_pod["spec"]["volumes"].append({"name": "artifact", "image": {
                "reference": "docker.io/library/busybox:1.37" if allowed else "example.invalid/artifact:v1"}})
            volume_pod["spec"]["containers"][0]["volumeMounts"].append({"name": "artifact", "mountPath": "/artifact"})
            admission(volume_pod, "" if allowed else "Image volume references must use an allowed registry prefix.")

        live = json.loads(kubectl("get", "pod", "demo", "-n", "cks-lab", "-o", "json"))
        for allowed in (True, False):
            live["spec"]["ephemeralContainers"] = [{
                "name": "inspect", "image": "docker.io/library/busybox:1.37" if allowed else "example.invalid/artifact:v1",
                "command": ["true"], "securityContext": {"runAsNonRoot": True, "runAsUser": 1000,
                    "allowPrivilegeEscalation": False, "capabilities": {"drop": ["ALL"]},
                    "seccompProfile": {"type": "RuntimeDefault"}},
            }]
            kubectl("replace", "--raw", "/api/v1/namespaces/cks-lab/pods/demo/ephemeralcontainers?dryRun=All", "-f", "-",
                    document=live, expected=0 if allowed else 1,
                    reason="" if allowed else "Ephemeral container images must use an allowed registry prefix.")
        print("PASS: correct answers, deliberately incorrect answers and image-volume admission.")
    finally:
        active_error = sys.exc_info()[1]
        cleanup_errors = []
        for command in [("delete", "-f", "labs/fixtures/registry-policy.yaml", "--ignore-not-found"),
                        ("delete", "namespace", "cks-lab", "cks-other", "--ignore-not-found", "--wait=true", "--timeout=120s")]:
            try:
                kubectl(*command)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                cleanup_errors.append(str(error))
        if cleanup_errors:
            raise RuntimeError(f"{active_error or 'Checks completed'}; cleanup failed: {'; '.join(cleanup_errors)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True, help="Explicit context of an empty disposable kind cluster")
    parser.add_argument("--external-lab-uid", help="Explicitly acknowledge an externally created lab's kube-system UID")
    args = parser.parse_args()
    if not args.context.startswith("kind-cks-"):
        parser.error("Use a dedicated kind cluster whose name starts with cks-.")
    try:
        smoke(args.context, args.external_lab_uid)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        sys.exit(f"FAIL: {error}")
