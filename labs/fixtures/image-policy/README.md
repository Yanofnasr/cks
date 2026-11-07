# ImagePolicyWebhook practice backend

A small loopback-only HTTPS fixture for image-policy decisions and mutual TLS. Python 3, OpenSSL and curl must already be installed.

The backend accepts Kubernetes `imagepolicy.k8s.io/v1alpha1` `ImageReview` requests, not `AdmissionReview` requests. Every supplied image must begin with `docker.io/` or `registry.k8s.io/`. Unqualified names and other registries are denied. User annotations never override the decision. This is a registry exercise, not signature verification, a vulnerability scanner or a complete image-reference parser. An allowed registry can contain untrusted images.

## Create separate lab certificates

Run from the repository root on a disposable lab machine. Stop if `work/SC09` already exists; select or reset your own previous exercise directory explicitly. Keep this shell open for the later commands.

```bash
umask 077
mkdir -p work
mkdir -m 700 work/SC09
LAB_DIR="$PWD/work/SC09"

openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 2 \
  -subj '/CN=SC09 lab CA' \
  -addext 'basicConstraints=critical,CA:TRUE' \
  -addext 'keyUsage=critical,keyCertSign,cRLSign' \
  -keyout "$LAB_DIR/ca.key" -out "$LAB_DIR/ca.crt"

openssl req -new -newkey rsa:2048 -nodes -sha256 \
  -subj '/CN=SC09 loopback server' \
  -keyout "$LAB_DIR/server.key" -out "$LAB_DIR/server.csr"
cat > "$LAB_DIR/server.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:127.0.0.1
EOF
openssl x509 -req -sha256 -days 2 -in "$LAB_DIR/server.csr" \
  -CA "$LAB_DIR/ca.crt" -CAkey "$LAB_DIR/ca.key" -CAcreateserial \
  -extfile "$LAB_DIR/server.ext" -out "$LAB_DIR/server.crt"

openssl req -new -newkey rsa:2048 -nodes -sha256 \
  -subj '/CN=SC09 webhook client' \
  -keyout "$LAB_DIR/client.key" -out "$LAB_DIR/client.csr"
cat > "$LAB_DIR/client.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=clientAuth
EOF
openssl x509 -req -sha256 -days 2 -in "$LAB_DIR/client.csr" \
  -CA "$LAB_DIR/ca.crt" -CAkey "$LAB_DIR/ca.key" -CAcreateserial \
  -extfile "$LAB_DIR/client.ext" -out "$LAB_DIR/client.crt"

openssl verify -CAfile "$LAB_DIR/ca.crt" -purpose sslserver \
  -verify_ip 127.0.0.1 "$LAB_DIR/server.crt"
openssl verify -CAfile "$LAB_DIR/ca.crt" -purpose sslclient "$LAB_DIR/client.crt"
```

This CA is used only for this webhook. Never use or copy the Kubernetes cluster CA private key. Its client certificate is for the webhook connection and grants no Kubernetes API identity. Keep all keys under the private directory, out of Git, image builds and screenshots.

## Run and probe the backend

In a second terminal on the same lab machine, from the repository root:

```bash
python3 labs/fixtures/image-policy/webhook.py \
  --cert work/SC09/server.crt --key work/SC09/server.key \
  --client-ca work/SC09/ca.crt
```

Keep this terminal open during the direct probes. It binds only `127.0.0.1:8443`, requires TLS 1.2 or newer and a client certificate from the lab CA, and serves `POST /`. Bodies are limited to 64 KiB and stalled TLS/HTTP reads time out after three seconds. It handles requests sequentially for a small lab; it is not a production webhook service.

Back in the first terminal, send the actual ImageReview payloads:

```bash
curl --fail-with-body --cacert "$LAB_DIR/ca.crt" \
  --cert "$LAB_DIR/client.crt" --key "$LAB_DIR/client.key" \
  -H 'Content-Type: application/json' \
  --data-binary @labs/fixtures/image-policy/allowed-review.json \
  https://127.0.0.1:8443/

curl --fail-with-body --cacert "$LAB_DIR/ca.crt" \
  --cert "$LAB_DIR/client.crt" --key "$LAB_DIR/client.key" \
  -H 'Content-Type: application/json' \
  --data-binary @labs/fixtures/image-policy/denied-review.json \
  https://127.0.0.1:8443/

# Must fail TLS authentication, without bypassing server verification.
curl --cacert "$LAB_DIR/ca.crt" \
  -H 'Content-Type: application/json' \
  --data-binary @labs/fixtures/image-policy/allowed-review.json \
  https://127.0.0.1:8443/
```

Expect HTTP 200 with `status.allowed: true`, then HTTP 200 with `status.allowed: false`. A policy denial is a valid webhook response, so curl's exit code alone does not prove an allow. The third command must fail before any policy decision. A malformed review receives a 4xx response with `allowed: false`.

## Local checks and cleanup

Run `python3 -m unittest discover -s tests -p test_image_policy.py -v` from the repository root. The TLS tests use temporary certificates and an ephemeral loopback listener; they do not contact a cluster.

After the direct probes, stop this foreground server with Ctrl+C and remove only the private `work/SC09` certificate directory created for this attempt. Preserve any non-secret evidence separately.
