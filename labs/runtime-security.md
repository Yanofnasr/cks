# Monitoring and runtime security

Use the [lab environment guide](../preparation/LAB-SAFETY.md), run commands from the repository root and keep evidence in ignored `work/`. Use only dummy data and owned test processes. Record the distinction between an observed event, a policy decision and a conclusion in the [progress log](../preparation/PROGRESS.md).

## RT01 Falco and syscall investigation

**Environment:** a disposable node with working Falco event collection and a writable custom-rule configuration. The optional syscall comparison also needs `strace`. If Falco cannot collect the required events on this kernel/runtime, record the prerequisite as pending; a YAML rule file is not a functioning detector.

**Start:** apply the shared workload fixture, wait for the `cks-lab/client` Pod to run, and locate the effective Falco rule configuration and output. Create two harmless files inside that Pod:

```bash
kubectl -n cks-lab exec client -- sh -c \
  'printf "probe\n" >/tmp/cks-runtime-probe; printf "ordinary\n" >/tmp/cks-ordinary'
```

**Task:** write a custom rule named `CKS practice file read` for successful read-opens of the named probe file by `cat` in a container. Constrain the event types and use fields supported by the installed Falco engine. Include event time, container identity, process command and user identity in its output. The [worked rule](../solutions/falco-file-read.yaml) uses explicit syscall fields and no externally defined macros; inspect it after attempting your own rule.

Copy the attempted rule to `work/RT01/falco-file-read.yaml`, then validate it with the same Falco version that will load it. On a node installation where the CLI is available, the command is:

```bash
falco --version
falco --validate work/RT01/falco-file-read.yaml
```

For containerized Falco, validate the copied file using the installed deployment's supported method. A local CLI from another version does not establish compatibility. Add only this file through the active installation's custom-rule mechanism, reload/restart that owned lab detector as documented, and inspect startup output for loading errors. Do not replace its full ruleset or disable unrelated rules. Record which detector instance on the client's node actually loaded the rule.

**Prove it:** execute both operations against the known client container:

```bash
kubectl -n cks-lab exec client -c client -- cat /tmp/cks-runtime-probe
kubectl -n cks-lab exec client -c client -- cat /tmp/cks-ordinary
```

The first produces a real matching event; the second must not match **this rule**, although other installed rules may emit events. Correlate the reported container ID with the actual Pod and node rather than assuming Kubernetes metadata fields are available. Confirm collection is healthy and repeat the positive probe before accepting the negative control. A successful read-open describes the open operation, not the exact bytes later consumed or a malicious intent. Rule validation without an observed event is only a syntax/compatibility check.

**Syscall comparison:** in the disposable node's private working directory, trace a harmless child process reading a file you created, using `strace -f` with selected file/read/write syscalls. Compare the raw calls with the higher-level Falco event. Trace only your own child; do not attach to unrelated host processes or weaken global ptrace controls to complete the exercise.

```bash
mkdir -p work/RT01
printf 'trace-practice\n' > work/RT01/trace-input
strace -f -o work/RT01/read.trace -e trace=openat,read,write,close \
  cat work/RT01/trace-input
strace -f -o work/RT01/missing.trace -e trace=openat,read,write,close \
  cat work/RT01/file-that-does-not-exist
```

Confirm the second path does not exist before using it. In the first trace, follow the descriptor returned by opening the owned file through its read and close. In the second, locate `ENOENT`; a requested file operation is not proof that data was read. Record these separately from the Falco event and remove only these task-owned trace files afterward.

**Reset:** remove only the named custom rule and the two fixture files, then reload and confirm normal Falco operation. Stop only your own trace process. Keep a small non-secret event sample and the rule used.

References: [Falco rule structure](https://falco.org/docs/concepts/rules/basic-elements/), [supported fields](https://falco.org/docs/rules/supported-fields/), [CLI validation](https://falco.org/docs/reference/daemon/cli-arguments/).

## RT02 Audit policy and investigation

**Environment:** the first part is offline. Live audit configuration needs a disposable kubeadm control plane with root access and snapshot recovery. Audit policies are API-server configuration files, not resources to apply with `kubectl`.

**Start offline:** inspect [audit-events.jsonl](fixtures/audit-events.jsonl), which contains explicitly synthetic training events. Identify the two forbidden Secret reads and the successful Pod-list request. For each, record actor, verb, namespace/resource, response status and timestamp. Separate the response outcome from the request intent; a denied read is not evidence that a Secret was disclosed.

**Task A:** use JSON-aware filtering to produce a timeline of the denied Secret requests. Verify it against the original records. Explain what these metadata-only records cannot tell you about a request body, credential theft or later actions. This exercise measures log interpretation, not a live audit pipeline.

**Start live:** snapshot the control plane, save its current API-server manifest and policy outside the watched manifests directory, and inspect [audit-policy.yaml](fixtures/audit-policy.yaml). Its purpose is metadata capture without logging Secret bodies.

**Task B:** copy the policy to an owned location on the control plane, mount it read-only into the existing API-server Pod and add the audit-policy flag. Configure a separate writable audit-log directory and bounded retention/rotation. Preserve the current API-server image, addresses, credentials and unrelated flags. Make equivalent changes on every API server if your lab has more than one. Wait for API health before generating test requests.

Create a drill-owned `audit-reader` ServiceAccount in `cks-lab`, with a Role/RoleBinding permitting Pod listing and no Secret reads. As the lab administrator, impersonate that identity for one actual Pod-list request and one actual Secret-read request. Do not substitute `kubectl auth can-i` for the requests: it tests authorization through a different API operation.

**Prove B:** the Pod list succeeds, the Secret request is forbidden, and the response-complete audit events identify the correct actor, verb, resource, namespace and status. There must be no Secret request/response body in those records. Confirm the correct policy rule matched and that API/node health remains good. If you add an exclusion, place it before broader matching rules and test both an excluded and a retained event.

**Reset:** remove only `audit-reader` and its Role/RoleBinding. Restore the control-plane snapshot, or carefully restore the saved manifest/policy and remove only the drill's mounts/files after API health is verified. Keep logs protected and remove them when the exercise's retention period ends.

Reference: [Kubernetes auditing](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/).

## RT03 Runtime immutability

**Environment:** ordinary disposable cluster. Start from your successful MW02 manifest, copy it to `work/immutable.yaml` and name the new Pod `immutable-demo`. The task's static page must remain available on port 8080.

**Task:** serve the page from a read-only volume mounted at `/www`, backed by a drill-owned ConfigMap named `immutable-page` with `immutable: true`. Change the HTTP command to serve `/www` without rewriting its contents at startup. Keep `/tmp` as an explicitly writable temporary volume, the root filesystem read-only, and the other MW02 restrictions in place.

**Prove it:**

1. The Pod becomes Ready and returns the expected page to the healthy client.
2. The runtime root mount is read-only, and a root-filesystem write fails.
3. Changing `/www/index.html` from the container fails, while creating `/tmp/cks-proof` succeeds.
4. An API attempt to change the immutable ConfigMap's data is rejected; an unrelated mutable ConfigMap in the same namespace still behaves normally.
5. The page remains available after the probes and a Pod restart.

Explain the separate controls: a read-only root filesystem does not make writable volumes immutable, and a read-only ConfigMap mount alone does not prevent an authorized API user from changing a mutable source ConfigMap. Keep the scope of each conclusion explicit.

**Reset:** delete only `immutable-demo`, `immutable-page` and your mutable comparison ConfigMap. Do not delete shared application configuration or change unrelated namespace policies.

## RT04 Incident response

**Environment:** ordinary disposable cluster with an enforcing CNI. Use a fresh shared baseline with no earlier NetworkPolicies. This is a benign containment exercise, not a malware exercise.

**Start:** copy the hardened workload manifest into `work/incident.yaml`. Name the Pod `incident-probe`, add the label `exercise: incident`, and replace its command with a harmless long-running process that writes a timestamp to `/tmp/cks-heartbeat` every few seconds. Remove the inherited HTTP readiness probe and container port because this process does not serve HTTP. Keep its writable `/tmp` volume and restricted security settings. Wait for it to run and confirm that the heartbeat advances.

**Task:** identify the Pod UID, node, container identity, process and start time. Save the relevant events and a short heartbeat sample. Capture the healthy destination Pod's IP **before** quarantine and use it for the primary connection comparison:

```bash
API_IP=$(kubectl -n cks-lab get pod api -o jsonpath='{.status.podIP}')
API_URL="http://$API_IP:8080/"
kubectl -n cks-lab exec incident-probe -- wget -qO- -T 3 "$API_URL"
kubectl -n cks-lab exec client -- wget -qO- -T 3 "$API_URL"
```

For an IPv6 Pod address, set `API_URL="http://[$API_IP]:8080/"` before the probes. Both direct-IP requests must succeed initially. Also record a successful DNS-based request before containment, but do not use name-resolution failure as proof that the destination connection was blocked.

Create a NetworkPolicy named `incident-quarantine` in `cks-lab` selecting only `exercise: incident`, with both ingress and egress isolated and no allow rules. Inspect all policies selecting that Pod: NetworkPolicies are additive, so another allow can defeat the intended quarantine.

**Prove it:** rerun the same two direct-IP commands using the captured `API_URL`. The still-running probe loses the connection while the unchanged healthy client retains it. Confirm the destination is still Ready at that IP; if it was recreated with a different IP, repeat the baseline comparison before drawing a conclusion. Verify the failed request ran the working utility in the intended Pod, and check that its heartbeat still advances. DNS is intentionally blocked by this all-egress quarantine too, but that separate effect is not the evidence for direct-IP containment. Record what quarantine does not prevent, such as the process using its local filesystem.

Identify which controller, if any, owns the probe before removing it; deleting a managed Pod may cause immediate replacement. Remove only this drill's Pod or owning workload after preserving the observations, then verify that the expected process/workload is gone and the healthy application remains available.

**Reset:** delete only `incident-quarantine` and any remaining owned probe resource. Never delete an executable obtained from an arbitrary `/proc/PID/exe` path, kill an unknown port owner, or remove unrelated binaries as a cleanup method.
