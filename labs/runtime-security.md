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
