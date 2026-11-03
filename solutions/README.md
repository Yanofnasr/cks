# Worked references

Attempt the [drills](../preparation/STUDY-PATH.md) first. These are selected reference implementations and explanations, not an answer bank for every environment or an automatic grader. Run commands individually and inspect results, including expected nonzero exits from negative probes.

Start each independent example from the [shared lab baseline](../preparation/LAB-SAFETY.md). All commands run from the repository root with the intended lab kubeconfig. Keep edits and evidence under `work/`. Reference manifests have not been validated end-to-end on every supported environment; the proof and recovery steps remain required.

## CS01: Network isolation

Inspect the resolver before using [network-policy.yaml](network-policy.yaml):

```bash
kubectl -n cks-lab exec client -- cat /etc/resolv.conf
kubectl -n kube-system get pods -l k8s-app=kube-dns --show-labels
```

The reference DNS rule assumes DNS traffic is enforced against CoreDNS Pods with `k8s-app=kube-dns` in `kube-system`. For NodeLocal DNS or another resolver, copy the manifest into `work/` and adapt that rule to the actual destination and CNI behavior. Do not open unrestricted application egress merely to make DNS pass.

Apply the reference when its assumptions match:

```bash
kubectl apply -f solutions/network-policy.yaml
kubectl -n cks-lab exec client -- wget -qO- -T 3 http://api.cks-lab.svc:8080/
kubectl -n cks-lab exec intruder -- wget -qO- -T 3 http://api.cks-lab.svc:8080/
kubectl -n cks-other exec client -- wget -qO- -T 3 http://api.cks-lab.svc:8080/
kubectl -n cks-lab exec client -- wget -qO- -T 3 http://api.cks-other.svc:8080/
kubectl -n cks-lab exec client -- nslookup api.cks-lab.svc
kubectl -n cks-other exec client -- wget -qO- -T 3 http://api:8080/
```

Expect the first HTTP request, DNS lookup and last HTTP request to succeed. The other three HTTP requests must fail while their callers and destinations remain healthy. Repeat direct-Pod-IP probes if needed to separate transport denial from name-resolution failure.

Why it works:

- The default policy selects every lab Pod and isolates both directions.
- The client egress and API ingress policies allow the same local Pod-to-Pod flow. Both sides must permit it.
- A Pod selector without a namespace selector selects peers in the policy's namespace. An identically labeled client in another namespace does not qualify.
- The DNS namespace and Pod selectors occupy the same peer entry, so they intersect. Separate peer entries would allow their union.
- Policies are additive; a separate broad allow can undo the intended restriction.

Clean up with `kubectl delete -f solutions/network-policy.yaml`, then repeat the initial unrestricted checks. Do not delete other policies.

## CH02: ServiceAccount authority and token mounting

[serviceaccount.yaml](serviceaccount.yaml) contains a ServiceAccount, a narrow Role, its RoleBinding and a Pod that relies on the ServiceAccount's automount default. The Role allows only `get` and `list` on Pods in `cks-lab`.

If CH02 left a Pod named `ch02-client`, delete only that owned Pod and wait for it to terminate before applying this reference:

```bash
kubectl -n cks-lab delete pod ch02-client --ignore-not-found --wait=true
kubectl apply -f solutions/serviceaccount.yaml
kubectl -n cks-lab wait --for=condition=Ready pod/ch02-client --timeout=120s
kubectl auth can-i list pods -n cks-lab --as=system:serviceaccount:cks-lab:ch02-client
kubectl auth can-i get secrets -n cks-lab --as=system:serviceaccount:cks-lab:ch02-client
kubectl auth can-i create pods -n cks-lab --as=system:serviceaccount:cks-lab:ch02-client
kubectl auth can-i list pods -n cks-other --as=system:serviceaccount:cks-lab:ch02-client
kubectl -n cks-lab exec ch02-client -- test ! -e /var/run/secrets/kubernetes.io/serviceaccount/token
```

Expect `yes`, `no`, `no`, `no`, then a successful absence check. Inspect the running Pod's volume/mount specification too. Permissions do not require mounting a token; a Pod-level `automountServiceAccountToken: true` could override the ServiceAccount default, and an explicit projected token is a separate choice.

Administrator impersonation tests authorization, not possession of credentials. CH01's client-certificate exercise verifies authentication separately. CH02's extension demonstrates why permission to create Pods can expose namespace Secrets even without direct Secret-read permission; do it only with dummy data and scoped temporary grants.

Clean up with `kubectl delete -f solutions/serviceaccount.yaml`, plus any separately named extension resources created during the drill.

## MW02: Harden a working workload

[workload.yaml](workload.yaml) preserves the starter's HTTP server while setting non-root UID/GID 1000, `fsGroup`, disabled privilege escalation, dropped capabilities, RuntimeDefault seccomp, no automatic API token and a read-only root filesystem. The `/tmp` emptyDir is the deliberate writable exception.

```bash
kubectl -n cks-lab delete pod demo --ignore-not-found --wait=true
kubectl apply -f solutions/workload.yaml
kubectl -n cks-lab wait --for=condition=Ready pod/demo --timeout=120s
kubectl -n cks-lab exec demo -- id
kubectl -n cks-lab exec demo -- grep -E 'CapEff|NoNewPrivs' /proc/1/status
kubectl -n cks-lab exec demo -- sh -c 'printf ok > /tmp/allowed.txt; cat /tmp/allowed.txt'
kubectl -n cks-lab exec demo -- test ! -e /var/run/secrets/kubernetes.io/serviceaccount/token
```

The UID/GID should be 1000, effective capabilities zero and `NoNewPrivs` one. Verify the root mount is read-only by inspecting `/proc/mounts`, then confirm a root-filesystem write is rejected. An ordinary file-permission denial alone is not proof of a read-only mount.

Capture the running Pod IP and fetch its page from the healthy client. For an IPv6 address, use brackets in the HTTP URL:

```bash
DEMO_IP=$(kubectl -n cks-lab get pod demo -o jsonpath='{.status.podIP}')
kubectl -n cks-lab exec client -- wget -qO- -T 3 "http://$DEMO_IP:8080/"
```

The command above is the IPv4 form. Confirm the app remains healthy after the negative probes. The writable volume does not make the root writable, and root immutability does not make that volume immutable. RT03 explores the separate data-volume controls.

Clean up with `kubectl -n cks-lab delete pod demo`. Keep a copy in `work/` if continuing to RT03.

## MW05: Mesh encryption

[istio-strict.yaml](istio-strict.yaml) restricts peer authentication to `app=api` in `cks-lab`. Use it only after MW05's injection, CNI, proxy-readiness and permissive-baseline checks. A running application container does not prove its traffic is intercepted by a healthy proxy.

Apply the file, retain the successful meshed-client request, and verify the healthy plain client is rejected. Check proxy configuration/telemetry for mutual TLS on the accepted connection. Remove only this policy with `kubectl delete -f solutions/istio-strict.yaml`, then complete MW05's injection cleanup.
