#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Loopback-only, mutually authenticated ImageReview backend for SC09."""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import ssl


MAX_BODY = 64 * 1024
READ_TIMEOUT = 3


def response(allowed, reason):
    return {"apiVersion": "imagepolicy.k8s.io/v1alpha1", "kind": "ImageReview",
            "status": {"allowed": allowed, "reason": reason}}


def review_images(document):
    if (not isinstance(document, dict) or document.get("apiVersion") != "imagepolicy.k8s.io/v1alpha1"
            or document.get("kind") != "ImageReview"):
        raise ValueError("expected imagepolicy.k8s.io/v1alpha1 ImageReview")
    spec = document.get("spec")
    if not isinstance(spec, dict) or not isinstance(spec.get("containers"), list) or not spec["containers"]:
        raise ValueError("spec.containers must be a nonempty list")
    if "namespace" in spec and not isinstance(spec["namespace"], str):
        raise ValueError("spec.namespace must be a string")
    annotations = spec.get("annotations", {})
    if not isinstance(annotations, dict) or any(not isinstance(value, str) for value in annotations.values()):
        raise ValueError("spec.annotations must map strings to strings")
    images = []
    for container in spec["containers"]:
        image = container.get("image") if isinstance(container, dict) else None
        if (not isinstance(image, str) or not image or image.endswith("/")
                or any(character.isspace() or not character.isprintable() for character in image) or "\\" in image):
            raise ValueError("each container must have a nonempty image without whitespace, control characters or backslashes")
        images.append(image)
    allowed = all(image.startswith(("docker.io/", "registry.k8s.io/")) for image in images)
    return response(allowed, "SC09: registry allowed" if allowed else "SC09: registry must be docker.io or registry.k8s.io")


def unique_object(pairs):
    document = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("duplicate JSON field")
        document[key] = value
    return document


def invalid_constant(value):
    raise ValueError("nonstandard JSON constant")


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, document):
        body = json.dumps(document).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_POST(self):
        if self.path != "/":
            self.reply(404, response(False, "unknown endpoint"))
            return
        if self.headers.get_content_type() != "application/json":
            self.reply(415, response(False, "expected application/json"))
            return
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
            self.reply(400, response(False, "one positive Content-Length is required; chunked requests are unsupported"))
            return
        if len(lengths[0]) > len(str(MAX_BODY)):
            self.reply(413, response(False, "review exceeds 64 KiB"))
            return
        length = int(lengths[0])
        if length > MAX_BODY:
            self.reply(413, response(False, "review exceeds 64 KiB"))
            return
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("incomplete request body")
            document = json.loads(body, object_pairs_hook=unique_object, parse_constant=invalid_constant)
            result = review_images(document)
        except TimeoutError:
            self.reply(408, response(False, "request body timed out"))
            return
        except (ValueError, RecursionError) as error:
            self.reply(400, response(False, str(error)))
            return
        self.reply(200, result)


class TLSServer(HTTPServer):
    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(READ_TIMEOUT)
        try:
            return self.context.wrap_socket(connection, server_side=True), address
        except OSError:
            connection.close()
            raise


def make_server(cert, key, client_ca, port=8443):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert, key)
    context.load_verify_locations(cafile=client_ca)
    context.verify_mode = ssl.CERT_REQUIRED
    server = TLSServer(("127.0.0.1", port), Handler)
    server.context = context
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--client-ca", required=True)
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()
    with make_server(args.cert, args.key, args.client_ca, args.port) as server:
        print(f"SC09 listening at https://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
