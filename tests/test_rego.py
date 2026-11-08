# SPDX-License-Identifier: MIT
"""Evaluate the shipped registry policy; no cluster or image pulls are needed."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

try:
    import yaml
except ImportError:
    yaml = None


OPA = shutil.which("opa")
ROOT = Path(__file__).resolve().parents[1]
ALLOWED_IMAGE = "docker.io/library/busybox:1.37"
DENIED_IMAGE = "example.invalid/lab/artifact:v1"


@unittest.skipUnless(OPA and yaml is not None, "Rego tests require opa and PyYAML")
class RegistryRegoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        template = yaml.safe_load((ROOT / "solutions/gatekeeper-template.yaml").read_text())
        constraint = yaml.safe_load((ROOT / "solutions/gatekeeper-constraint.yaml").read_text())
        cls.policy = cls.directory / "registry.rego"
        cls.policy.write_text(template["spec"]["targets"][0]["rego"])
        cls.parameters = constraint["spec"]["parameters"]

    def setUp(self):
        self.spec = {"containers": [{"name": "main", "image": ALLOWED_IMAGE}]}

    def assert_policy(self, rejected_image=None):
        document = {"review": {"object": {"spec": self.spec}}, "parameters": self.parameters}
        input_file = self.directory / "input.json"
        input_file.write_text(json.dumps(document))
        result = subprocess.run(
            [OPA, "eval", "--v0-compatible", "--format=json", "--data", str(self.policy),
             "--input", str(input_file), "data.k8spracticeimages.violation"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        violations = json.loads(result.stdout)["result"][0]["expressions"][0]["value"]
        expected = [] if rejected_image is None else [
            {"msg": f"CKS registry policy rejects {rejected_image}"},
        ]
        self.assertEqual(violations, expected)

    def test_allowed_regular_image_without_optional_fields(self):
        self.assert_policy()

    def test_ordinary_volume_is_allowed(self):
        self.spec["volumes"] = [{"name": "scratch", "emptyDir": {}}]
        self.assert_policy()

    def test_allowed_image_volume(self):
        self.spec["volumes"] = [{"name": "artifact", "image": {"reference": ALLOWED_IMAGE}}]
        self.assert_policy()

    def test_forbidden_image_volume_with_allowed_container(self):
        self.spec["volumes"] = [{"name": "artifact", "image": {"reference": DENIED_IMAGE}}]
        self.assert_policy(DENIED_IMAGE)

    def test_empty_or_missing_image_volume_reference_is_denied(self):
        for source in [{"reference": ""}, {}]:
            with self.subTest(source=source):
                self.spec["volumes"] = [{"name": "artifact", "image": source}]
                self.assert_policy("")

    def test_forbidden_main_image(self):
        self.spec["containers"][0]["image"] = DENIED_IMAGE
        self.assert_policy(DENIED_IMAGE)

    def test_forbidden_init_image_with_allowed_container(self):
        self.spec["initContainers"] = [{"name": "init", "image": DENIED_IMAGE}]
        self.assert_policy(DENIED_IMAGE)

    def test_forbidden_ephemeral_image_with_allowed_container(self):
        self.spec["ephemeralContainers"] = [{"name": "inspect", "image": DENIED_IMAGE}]
        self.assert_policy(DENIED_IMAGE)


if __name__ == "__main__":
    unittest.main()
