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
