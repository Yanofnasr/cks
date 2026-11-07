# SPDX-License-Identifier: MIT
import http.client
import importlib.util
import json
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest


FIXTURE = Path(__file__).resolve().parents[1] / "labs/fixtures/image-policy"
SPEC = importlib.util.spec_from_file_location("image_policy", FIXTURE / "webhook.py")
webhook = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(webhook)


def review(*images):
    return {
        "apiVersion": "imagepolicy.k8s.io/v1alpha1",
        "kind": "ImageReview",
        "spec": {"containers": [{"image": image} for image in images]},
    }


class PolicyTests(unittest.TestCase):
    def test_explicit_allowed_registries(self):
        response = webhook.review_images(review("docker.io/library/busybox:1.37", "registry.k8s.io/pause:3.10"))
        self.assertEqual(response["apiVersion"], "imagepolicy.k8s.io/v1alpha1")
        self.assertEqual(response["kind"], "ImageReview")
        self.assertIs(response["status"]["allowed"], True)

    def test_other_registries_and_implicit_names_are_denied(self):
        for image in ["example.invalid/a:v1", "busybox:1.37", "docker.io.evil/a", "docker.io:443/a"]:
            with self.subTest(image=image):
                self.assertIs(webhook.review_images(review(image))["status"]["allowed"], False)

    def test_one_denied_image_rejects_whole_review(self):
        result = webhook.review_images(review("docker.io/library/busybox:1.37", "example.invalid/init:v1"))
        self.assertIs(result["status"]["allowed"], False)

    def test_user_annotations_cannot_bypass_registry_policy(self):
        document = review("example.invalid/a:v1")
        document["spec"]["annotations"] = {"lab.image-policy.k8s.io/allow": "true"}
        self.assertIs(webhook.review_images(document)["status"]["allowed"], False)

    def test_malformed_contract_is_rejected(self):
        malformed = [None, [], {}, review(), review(""), review(None), review("docker.io/"),
                     review("docker.io/a b"), review("docker.io/a\\b"), review("docker.io/a\x00")]
        for key, value in [("apiVersion", "admission.k8s.io/v1"), ("kind", "AdmissionReview"), ("spec", [])]:
            document = review("docker.io/library/busybox:1.37")
            document[key] = value
            malformed.append(document)
        for containers in [{"image": "docker.io/a"}, [None], ["docker.io/a"], [{"image": 42}]]:
            document = review()
            document["spec"]["containers"] = containers
            malformed.append(document)
        for key, value in [("namespace", 42), ("annotations", []), ("annotations", {"key": True})]:
            document = review("docker.io/a")
            document["spec"][key] = value
            malformed.append(document)
        for document in malformed:
            with self.subTest(document=document), self.assertRaises(ValueError):
                webhook.review_images(document)

    def test_shipped_payloads(self):
        for name, allowed in [("allowed-review.json", True), ("denied-review.json", False)]:
            self.assertIs(webhook.review_images(json.loads((FIXTURE / name).read_text()))["status"]["allowed"], allowed)


@unittest.skipUnless(shutil.which("openssl"), "openssl is required for the local TLS tests")
class TLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)

        def openssl(*args):
            subprocess.run(["openssl", *args], cwd=cls.directory, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        for name in ["ca", "other-ca"]:
            openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", f"/CN={name}", "-addext", "basicConstraints=critical,CA:TRUE",
                    "-addext", "keyUsage=critical,keyCertSign,cRLSign",
                    "-keyout", f"{name}.key", "-out", f"{name}.crt")
        for name, issuer, usage in [("server", "ca", "serverAuth"), ("client", "ca", "clientAuth"),
                                    ("other-client", "other-ca", "clientAuth")]:
            openssl("req", "-new", "-newkey", "rsa:2048", "-nodes", "-subj", f"/CN={name}",
                    "-keyout", f"{name}.key", "-out", f"{name}.csr")
            extensions = "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n"
            extensions += f"extendedKeyUsage={usage}\nsubjectAltName=IP:127.0.0.1\n"
            (cls.directory / f"{name}.ext").write_text(extensions)
            openssl("x509", "-req", "-days", "1", "-in", f"{name}.csr", "-CA", f"{issuer}.crt",
                    "-CAkey", f"{issuer}.key", "-CAcreateserial", "-extfile", f"{name}.ext", "-out", f"{name}.crt")
        cls.server = webhook.make_server(cls.directory / "server.crt", cls.directory / "server.key",
                                         cls.directory / "ca.crt", port=0)
        cls.addClassCleanup(cls.server.server_close)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.thread.join, 5)
        cls.addClassCleanup(cls.server.shutdown)

    def context(self, identity="client", ca="ca"):
        context = ssl.create_default_context(cafile=self.directory / f"{ca}.crt")
        if identity:
            context.load_cert_chain(self.directory / f"{identity}.crt", self.directory / f"{identity}.key")
        return context

    def request(self, body, *, identity="client", ca="ca", headers=None, path="/"):
        connection = http.client.HTTPSConnection("127.0.0.1", self.server.server_port,
                                               context=self.context(identity, ca), timeout=5)
        self.addCleanup(connection.close)
        connection.request("POST", path, body, headers or {"Content-Type": "application/json"})
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def test_valid_client_receives_allow_and_deny(self):
        for image, allowed in [("docker.io/library/busybox:1.37", True), ("example.invalid/a:v1", False)]:
            status, result = self.request(json.dumps(review(image)))
            self.assertEqual(status, 200)
            self.assertIs(result["status"]["allowed"], allowed)
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertEqual(self.server.context.minimum_version, ssl.TLSVersion.TLSv1_2)

    def test_missing_and_untrusted_client_certificates_fail(self):
        for identity in [None, "other-client", "server"]:
            with self.subTest(identity=identity), self.assertRaises((ssl.SSLError, OSError)):
                self.request(json.dumps(review("docker.io/a")), identity=identity)

    def test_wrong_server_ca_fails(self):
        with self.assertRaises(ssl.SSLError):
            self.request(json.dumps(review("docker.io/a")), ca="other-ca")

    def test_invalid_json_contract_and_nonstandard_json_fail_closed(self):
        for body in ["{", "null", json.dumps(review()), '{"kind":"ImageReview","kind":"Other"}',
                     '{"number":NaN}', json.dumps({**review("docker.io/a"), "apiVersion": "unknown"})]:
            with self.subTest(body=body):
                status, result = self.request(body)
                self.assertEqual(status, 400)
                self.assertIs(result["status"]["allowed"], False)

    def test_oversized_body_bad_route_and_content_type_fail_closed(self):
        for body, options, expected in [("x" * (webhook.MAX_BODY + 1), {}, 413),
                                        ("{}", {"path": "/other"}, 404),
                                        ("{}", {"headers": {"Content-Type": "text/plain"}}, 415)]:
            status, result = self.request(body, **options)
            self.assertEqual(status, expected)
            self.assertIs(result["status"]["allowed"], False)

    def test_body_read_times_out(self):
        with socket.create_connection(self.server.server_address, timeout=5) as raw:
            with self.context().wrap_socket(raw, server_hostname="127.0.0.1") as connection:
                connection.sendall(b"POST / HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: 5\r\n\r\n{")
                response = http.client.HTTPResponse(connection)
                response.begin()
                self.assertEqual(response.status, 408)
                self.assertIs(json.loads(response.read())["status"]["allowed"], False)

    def test_invalid_http_framing_fails_closed(self):
        for headers, expected in [(b"", 400), (b"Content-Length: -1\r\n", 400),
                                  (b"Content-Length: 2\r\nContent-Length: 2\r\n", 400),
                                  (b"Transfer-Encoding: chunked\r\nContent-Length: 2\r\n", 400),
                                  (b"Content-Length: " + b"9" * 5000 + b"\r\n", 413)]:
            with self.subTest(headers=headers[:80]), socket.create_connection(self.server.server_address, timeout=5) as raw:
                with self.context().wrap_socket(raw, server_hostname="127.0.0.1") as connection:
                    connection.sendall(b"POST / HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\n" + headers + b"\r\n{}")
                    response = http.client.HTTPResponse(connection)
                    response.begin()
                    self.assertEqual(response.status, expected)
                    self.assertIs(json.loads(response.read())["status"]["allowed"], False)


if __name__ == "__main__":
    unittest.main()
