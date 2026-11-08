# Cluster setup

Use a disposable cluster and the [environment guide](../preparation/LAB-SAFETY.md). Commands start at the repository root. Save your own manifests under `work/CSxx/` and record results in the [progress log](../preparation/PROGRESS.md).

The [shared workloads](fixtures/workloads.yaml) provide two HTTP servers and three clients. They need a CNI that enforces NetworkPolicy. For drills using this baseline, use the shared reset procedure first, apply the fixture, and wait for all Pods in both namespaces to become Ready. A failed probe counts only after its client, destination and test command are known to work. The `.svc` names below use the Pod's configured DNS search path; if that path is customized, inspect `/etc/resolv.conf` and use the actual cluster-domain suffix.

## CS01 Network isolation

**Start:** apply `labs/fixtures/workloads.yaml`. With no exercise policies installed, prove that `client`, `intruder`, and the client in `cks-other` can reach the API in `cks-lab`:

```bash
kubectl -n cks-lab exec client -- wget -qO- -T 3 http://api:8080/
kubectl -n cks-lab exec intruder -- wget -qO- -T 3 http://api:8080/
kubectl -n cks-other exec client -- wget -qO- -T 3 http://api.cks-lab.svc:8080/
```

**Task:** create policies named `cs01-deny-all`, `cs01-dns`, `cs01-client-egress`, and `cs01-api-ingress` in `cks-lab`:

1. Isolate every Pod for ingress and egress by default.
2. Allow only Pods labelled `role=client` in `cks-lab` to reach Pods labelled `app=api` in that namespace on TCP 8080.
3. Allow DNS for the namespace using the actual resolver destinations and both UDP/TCP 53. Inspect the cluster DNS Service, endpoint Pods and client `/etc/resolv.conf`; do not assume a selector fits NodeLocal DNS.
4. Leave `cks-other` unchanged. Do not add a broad all-destinations or all-namespaces application allow rule.

**Prove:** the first probe above succeeds, while the other two fail. The local client's request to `api.cks-other.svc:8080` also fails, while the `cks-other` client still reaches its own API. Verify name resolution separately:

```bash
kubectl -n cks-lab exec client -- cat /etc/resolv.conf
DNS_SUFFIX=cluster.local # Use the suffix after cks-lab.svc. in the search line.
kubectl -n cks-lab exec client -- nslookup "api.cks-lab.svc.$DNS_SUFFIX."
kubectl -n cks-other exec client -- wget -qO- -T 3 http://api:8080/
kubectl -n cks-lab get networkpolicy
```

Use the actual DNS suffix: BusyBox `nslookup` does not expand dotted `.svc` names in the same way as the HTTP client's resolver. A partial-name lookup can return NXDOMAIN even when HTTP name resolution works.

Repeat a denied probe against the server's current Pod IP to distinguish a connection denial from a DNS error. Confirm the server is still Ready and the permitted probe still succeeds. Explain why NetworkPolicies are additive and why both the source's egress and destination's ingress must allow this flow.

### Independent ingress check

The intruder's own egress denial can hide an API ingress rule that admits every local Pod. Test ingress separately by briefly allowing only the intruder's egress to the two fixture APIs on TCP 8080. The unaffected `cks-other/api` is the positive control proving that this temporary allowance is active. First check that the temporary policy name is unused:

```bash
kubectl -n cks-lab get networkpolicy cs01-ingress-probe --ignore-not-found
```

Proceed only if the command succeeds without returning a policy. Do not adopt or remove an existing policy with that name. Create the temporary allowance:

```bash
kubectl -n cks-lab create -f - <<'YAML'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: cs01-ingress-probe
spec:
  podSelector:
    matchLabels:
      role: intruder
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: cks-lab
      podSelector:
        matchLabels:
          app: api
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: cks-other
      podSelector:
        matchLabels:
          app: api
    ports:
    - protocol: TCP
      port: 8080
YAML
```

Continue only after creation succeeds. Verify both APIs and the intruder are Ready, then capture the current addresses. Run the requests individually:

```bash
kubectl -n cks-lab wait --for=condition=Ready pod/api pod/intruder --timeout=120s
kubectl -n cks-other wait --for=condition=Ready pod/api --timeout=120s
CS01_API_IP=$(kubectl -n cks-lab get pod api -o jsonpath='{.status.podIP}')
case "$CS01_API_IP" in
  *:*) CS01_API_URL="http://[$CS01_API_IP]:8080/" ;;
  *) CS01_API_URL="http://$CS01_API_IP:8080/" ;;
esac
CS01_OTHER_IP=$(kubectl -n cks-other get pod api -o jsonpath='{.status.podIP}')
case "$CS01_OTHER_IP" in
  *:*) CS01_OTHER_URL="http://[$CS01_OTHER_IP]:8080/" ;;
  *) CS01_OTHER_URL="http://$CS01_OTHER_IP:8080/" ;;
esac
kubectl -n cks-lab exec intruder -- wget -qO- -T 3 "$CS01_OTHER_URL"
kubectl -n cks-lab exec client -- wget -qO- -T 3 "$CS01_API_URL"
kubectl -n cks-lab exec intruder -- wget -qO- -T 3 "$CS01_API_URL"
kubectl -n cks-lab exec intruder -- wget -qO- -T 3 "$CS01_OTHER_URL"
kubectl -n cks-lab exec client -- wget -qO- -T 3 "$CS01_API_URL"
```

Expect success, success, a connection denial, success, then success. Do not interpret the internal denial until the intruder's request to `cks-other/api` succeeds: if the temporary egress rule has not converged, both requests can still fail. If that positive control remains blocked, diagnose it or record a blocked check. The intruder and both APIs must remain Ready. Direct IPs avoid DNS, and the working request to the other namespace establishes the intruder's egress allowance before testing the local API's ingress restriction. An unexpected intruder success against `cks-lab/api` means its ingress boundary is too broad even if the earlier combined checks passed.

Remove the temporary policy immediately, including after an unexpected result or an interrupted proof, but only if this attempt created it:

```bash
kubectl -n cks-lab delete networkpolicy cs01-ingress-probe --wait=true
kubectl -n cks-lab get networkpolicy cs01-ingress-probe --ignore-not-found
```

The final query must succeed without returning a policy. Repeat the original allowed and denied checks after cleanup.

You can also run the independent verifier using the lab context selected during setup:

```bash
python3 scripts/lab.py --context "$LAB_CONTEXT" verify CS01
```

It briefly creates its own scoped `cs01-ingress-probe` policy and cleans it up. Resolve an existing probe policy from an interrupted attempt before retrying. A blocked check is not a passing result.

**Reset:** remove any temporary `cs01-ingress-probe` owned by this attempt, then delete only the four task policies you created, or use the shared namespace reset. Repeat the original successful probes before the next drill.

After attempting the task, compare the selectors and proof strategy with the optional [worked references](../solutions/README.md).

## CS02 Metadata protection

**Start:** use a fresh fixture plus a disposable **non-cluster VM** reachable on a private lab address. This extra machine is required for a portable external-IP test; a Service's translated address is unsuitable. On that VM, set `MOCK_BIND` to its private lab address and run this server in a dedicated terminal. Restrict its firewall to the lab sources. Do not use a real metadata service or real credentials.

```bash
mkdir -p work/CS02/mock
printf 'training-only\n' > work/CS02/mock/metadata.txt
python3 -m http.server 8081 --bind "$MOCK_BIND" --directory work/CS02/mock
```

Set `META_IP` to that VM's IPv4 address in your shell. Both clients must successfully read the dummy file before applying policy:

```bash
kubectl -n cks-lab exec client -- wget -qO- -T 3 "http://$META_IP:8081/metadata.txt"
kubectl -n cks-lab exec intruder -- wget -qO- -T 3 "http://$META_IP:8081/metadata.txt"
```

**Task:** label `client` with `metadata-access=true`. Create the following egress policies in `cks-lab`:

1. `cs02-restrict-metadata`: select all Pods and allow external IPv4 destinations through `ipBlock: 0.0.0.0/0`, except `META_IP/32`.
2. `cs02-cluster-peers`: explicitly allow the shared API Pods on TCP 8080, using `app=api` together with namespace selectors for `cks-lab` and `cks-other`. Keep each namespace selector and Pod selector in the same peer entry so their conditions are combined.
3. `cs02-dns`: permit the cluster's actual DNS destinations on UDP/TCP 53. Inspect the resolver and use the appropriate Pod/namespace selectors or NodeLocal DNS rules for that environment.
4. `cs02-reader`: allow only Pods with `metadata-access=true` to reach `META_IP/32` on TCP 8081.

Broad `ipBlock` ranges do not select Pod traffic consistently across implementations. The explicit peer and DNS rules make the required application checks independent of that behavior. Inspect other policies so none reopens the excluded external address. See the [official implementation comparison](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/network-policy#inclusion_of_pod_ip_ranges_in_ipblock_rules).

This example targets IPv4. For an IPv6 variation, use the equivalent `::/0` exception with a `/128` host address and bracket the literal in URLs, such as `http://[${META_IP}]:8081/metadata.txt`. On a dual-stack lab, specify which address family each test covers; one IPv4 rule does not establish IPv6 protection.

**Prove:** the labelled client reads the dummy file, `intruder` cannot, and both still resolve DNS and reach the ordinary in-cluster API. Keep the mock server running during both tests. Explain how the policy would target an actual provider endpoint, and why host-network workloads, node access, provider controls and CNI behavior need separate consideration. This mock test does not prove protection of a cloud metadata deployment.

**Reset:** remove only the four named `cs02-*` policies and the `metadata-access` label. Stop the foreground mock server with Ctrl+C in its own terminal, then remove its dummy directory and task-specific firewall rule. Restore ordinary egress checks. If the extra VM is unavailable, mark this drill blocked rather than counting an unreachable address as protected.

## CS03 CIS remediation

**Start:** use a snapshot of a dedicated kubeadm VM cluster with a reviewed kube-bench version and benchmark compatible with its Kubernetes version. No scanner is installed by this repository. Record `kubectl version`, `kube-bench version`, the selected benchmark and the exact command used to produce the baseline report under `work/CS03/`.

**Task:** choose one applicable failing control concerning static-Pod manifest permissions and one concerning a component setting. Read each control's audit and remediation text before changing anything. Correct only the relevant file or setting. Keep a backup of modified node files outside watched configuration directories.

If the chosen permission control is already satisfied, a controlled before/after exercise may temporarily make the API-server manifest mode `0644` **only if that selected benchmark requires a stricter mode**. Do this only on the isolated snapshot and record the original mode. Do not weaken authentication, authorization or etcd protection merely to manufacture a failure.

**Prove:** rerun the exact selected checks, not just a whole-report summary. Show the effective file ownership/mode and component setting. Confirm the API server is ready, nodes are Ready, and the fixture API remains available. A changed control ID, unsupported benchmark, scanner failure or skipped check is not a pass. The intentionally weakened permission control must fail before correction and pass afterward.

**Reset:** retain the hardened lab state if continuing from it, or restore the VM snapshot. Restore any test-only change that was not part of the intended remediation. Keep the baseline and final reports together so that their tool and benchmark identities can be compared.

## CS04 Ingress TLS

**Start:** use the shared workloads and an installed, maintained Ingress controller with a known IngressClass and reachable HTTPS address. Confirm its controller Pods are Ready. It must be able to route an Ingress to `cks-lab/api:8080`. Installation and external address allocation are environment prerequisites.

Generate a new one-day **lab-only** identity:

```bash
mkdir -p work/CS04
umask 077
openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
  -subj '/CN=cks.test' -addext 'subjectAltName=DNS:cks.test' \
  -keyout work/CS04/tls.key -out work/CS04/tls.crt
kubectl -n cks-lab create secret tls cs04-tls \
  --cert=work/CS04/tls.crt --key=work/CS04/tls.key
```

**Task:** write a `networking.k8s.io/v1` Ingress named `cs04-api`, using your controller's IngressClass, host `cks.test`, Prefix path `/`, backend `api:8080`, and TLS Secret `cs04-tls`. Avoid controller-specific snippets. Set `INGRESS_IP` to the lab controller's reachable address, then test:

```bash
curl --cacert work/CS04/tls.crt \
  --resolve "cks.test:443:$INGRESS_IP" https://cks.test/
```

**Prove:** the expected application response arrives and the certificate covers `cks.test`. Repeat using an unrelated CA and confirm certificate validation fails while the trusted-CA request still succeeds. Inspect the failure reason: connection refusal or a missing route does not prove TLS validation. Do not use `-k` as the success test. If the task also requires HTTP redirection, configure it using your controller's documented mechanism and inspect its response status and destination.

**Reset:** delete only `cs04-api` and `cs04-tls`, then remove the generated private key and certificate. Leave the shared controller and other namespaces intact.

## CS05 Binary integrity

**Start:** this drill runs locally and does not need a cluster. Use a private `work/CS05/` directory and copy your existing `kubectl` there. Never alter or execute the modified copy:

```bash
mkdir -p work/CS05
cp "$(command -v kubectl)" work/CS05/kubectl
(cd work/CS05 && sha256sum kubectl > kubectl.sha256)
(cd work/CS05 && sha256sum -c kubectl.sha256)
printf '\n' >> work/CS05/kubectl
(cd work/CS05 && sha256sum -c kubectl.sha256)
```

**Task:** explain why the first check succeeds and the second fails. Then select a real Kubernetes binary release for your OS and architecture, obtain its expected digest from the official release channel, and verify a downloaded artifact without installing it. Record the version, architecture, artifact URL and expected digest. Use the [official references](../preparation/REFERENCES.md) to locate the release instructions.

**Prove:** the untouched official artifact matches and an altered disposable copy does not. Distinguish integrity from authenticity: a checksum you generated yourself proves later corruption, not publisher identity; a checksum supplied by an attacker alongside a binary does not establish trust. If testing signatures, identify the trusted signer and the exact signed artifact.

**Reset:** remove only the copies and digest files under `work/CS05/`. The installed `kubectl` must remain unchanged and usable.

## CS06 Three-tier traffic and policy composition

**Environment:** an ordinary cluster with a CNI that enforces NetworkPolicy. This drill uses fresh `cks-tiers` and `cks-data` namespaces, separately from CS01. Confirm both names are absent before creating anything:

```bash
kubectl get namespace cks-tiers cks-data --ignore-not-found
```

Proceed only if that command succeeds with no namespaces returned. Existing namespaces must not be adopted or deleted. Check for cluster-wide CNI policies and automatic mesh injection that would change this baseline. The [three-tier fixture](fixtures/three-tier.yaml) uses small HTTP servers to represent the backend and database, plus four clients. It does not run a real database or application chain.

```bash
mkdir -p work/CS06
kubectl create -f labs/fixtures/three-tier.yaml
kubectl -n cks-tiers wait --for=condition=Ready pod --all --timeout=120s
kubectl -n cks-data wait --for=condition=Ready pod --all --timeout=120s
kubectl -n cks-tiers get pods --show-labels
kubectl -n cks-data get pods --show-labels
```

**Baseline:** all seven probes below must succeed before installing policy. Capture both server Pod addresses after readiness so negative tests can avoid DNS entirely. Refresh an address if you replace its Pod. The case statements also bracket IPv6 addresses correctly.

```bash
DB_IP=$(kubectl -n cks-data get pod database -o jsonpath='{.status.podIP}')
case "$DB_IP" in
  *:*) DB_URL="http://[$DB_IP]:8080/" ;;
  *) DB_URL="http://$DB_IP:8080/" ;;
esac
BACKEND_IP=$(kubectl -n cks-tiers get pod backend -o jsonpath='{.status.podIP}')
case "$BACKEND_IP" in
  *:*) BACKEND_URL="http://[$BACKEND_IP]:8080/" ;;
  *) BACKEND_URL="http://$BACKEND_IP:8080/" ;;
esac
kubectl -n cks-tiers exec frontend -- wget -qO- -T 3 http://backend:8080/
kubectl -n cks-tiers exec intruder -- wget -qO- -T 3 "$BACKEND_URL"
kubectl -n cks-data exec frontend-witness -- wget -qO- -T 3 "$BACKEND_URL"
kubectl -n cks-tiers exec backend -- wget -qO- -T 3 http://database.cks-data.svc:8080/
kubectl -n cks-tiers exec frontend -- wget -qO- -T 3 "$DB_URL"
kubectl -n cks-tiers exec intruder -- wget -qO- -T 3 "$DB_URL"
kubectl -n cks-data exec backend-witness -- wget -qO- -T 3 "$DB_URL"
```

**Task:** write `work/CS06/policies.yaml` with ingress default-deny policies named `cs06-deny-ingress` in both namespaces, `cs06-backend` in `cks-tiers`, and `cs06-database` in `cks-data`. Allow only frontend Pods in `cks-tiers` to reach backend Pods on TCP 8080. Allow only backend Pods in `cks-tiers` to reach database Pods in `cks-data` on TCP 8080. Combine each namespace selector and Pod selector in the **same peer entry**. Apply your file and repeat the exact seven probes.

Keep egress unrestricted in this drill. This makes each denial evidence about its destination's ingress selector, rather than a source-egress rule masking a broken ingress policy. CS01 exercises both directions and DNS restrictions.

| Source | Destination | Before policy | Correct policy |
| --- | --- | --- | --- |
| `cks-tiers/frontend` | backend | succeeds | succeeds |
| `cks-tiers/intruder` (right namespace, wrong label) | backend | succeeds | denied |
| `cks-data/frontend-witness` (right label, wrong namespace) | backend | succeeds | denied |
| `cks-tiers/backend` | database | succeeds | succeeds |
| `cks-tiers/frontend` | database | succeeds | denied |
| `cks-tiers/intruder` (right namespace, wrong label) | database | succeeds | denied |
| `cks-data/backend-witness` (right label, wrong namespace) | database | succeeds | denied |

**Prove the selector distinction:** copy your answer to `work/CS06/policies-or.yaml`. In only `cs06-database`, split the single peer into these two entries:

```yaml
from:
- namespaceSelector:
    matchLabels:
      kubernetes.io/metadata.name: cks-tiers
- podSelector:
    matchLabels:
      tier: backend
```

```bash
kubectl apply -f work/CS06/policies-or.yaml
kubectl -n cks-tiers exec intruder -- wget -qO- -T 3 "$DB_URL"
kubectl -n cks-data exec backend-witness -- wget -qO- -T 3 "$DB_URL"
kubectl apply -f work/CS06/policies.yaml
```

Both witness requests now succeed: the namespace-only peer admits every Pod in `cks-tiers`, while the Pod-only peer selects matching Pods in the policy's own `cks-data` namespace. Separate entries are OR; selectors inside one entry are AND. After restoring your answer, both requests must fail again and the legitimate backend request must still succeed. Wait for policy convergence before recording results.

**Prove additive behavior:** temporarily add a second policy selecting the database:

```bash
kubectl -n cks-data create -f - <<'YAML'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: cs06-database-reopen
spec:
  podSelector:
    matchLabels:
      tier: database
  policyTypes:
  - Ingress
  ingress:
  - ports:
    - protocol: TCP
      port: 8080
YAML
kubectl -n cks-data get networkpolicy
kubectl -n cks-tiers exec frontend -- wget -qO- -T 3 "$DB_URL"
kubectl apply -f work/CS06/policies.yaml
kubectl -n cks-tiers exec frontend -- wget -qO- -T 3 "$DB_URL"
kubectl -n cks-data delete networkpolicy cs06-database-reopen
```

Both frontend requests succeed while the extra allow policy exists, even after reapplying the original default-deny and narrow allow rules. Allowed traffic is the union of applicable policies; a default-deny policy does not override another allowance. After deleting `cs06-database-reopen`, rerun all seven probes and verify the correct-policy column. Confirm all Pods remain Ready. Compare your answer with the [worked policy](../solutions/three-tier-policy.yaml) after attempting it.

Run the independent seven-path check before cleanup, using the [lab identity selected during setup](../preparation/LAB-SAFETY.md#select-the-cluster-deliberately):

```bash
python3 scripts/lab.py --context "$LAB_CONTEXT" verify CS06
```

The verifier checks the restored traffic matrix. Keep the selector and additive-policy experiments above as separate evidence of why the rules behave that way.

**Reset:** delete only the two namespaces created for this drill:

```bash
kubectl delete namespace cks-tiers cks-data --wait=true
```

Reference: [NetworkPolicy selectors and behavior](https://kubernetes.io/docs/concepts/services-networking/network-policies/).
