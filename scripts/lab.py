# SPDX-License-Identifier: MIT
"""Bounded checks for a disposable lab; never uses the implicit kubeconfig context."""
import argparse
from contextlib import contextmanager
import ipaddress
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]

IDENTITY = ["--as=system:serviceaccount:cks-lab:ch02-client",
            "--as-group=system:serviceaccounts", "--as-group=system:serviceaccounts:cks-lab",
            "--as-group=system:authenticated"]


class Failed(Exception):
    pass


class Blocked(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Failed(message)
    print(f"PASS: {message}")


class Kubectl:
    def __init__(self, context):
        self.context = context
        self.prefix = ["kubectl", "--context", context, "--request-timeout=10s"]

    def run(self, *args, document=None, check=True):
        try:
            result = subprocess.run(self.prefix + list(args), input=json.dumps(document) if document is not None else None,
                                    text=True, capture_output=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            raise Blocked(f"kubectl {args[0]} unavailable or timed out; inspect the selected lab context") from None
        if check and result.returncode:
            # API responses can include submitted objects; never print their bodies or credentials.
            raise Blocked(f"kubectl {args[0]} failed; check API access, permissions and fixture readiness")
        return result

    def get(self, resource, name=None, namespace=None, optional=False):
        args = ["get", resource]
        if name:
            args.append(name)
        if namespace:
            args += ["-n", namespace]
        if optional:
            args.append("--ignore-not-found")
        result = self.run(*args, "-o", "json")
        if optional and not result.stdout.strip():
            return None
        return self.decode(result.stdout)

    @staticmethod
    def decode(text):
        try:
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except ValueError:
            raise Blocked("kubectl returned an unexpected JSON response") from None

    def exec(self, pod, script, *args):
        meta = pod["metadata"]
        return self.run("exec", meta["name"], "-n", meta["namespace"], "--", "sh", "-c", script, "sh", *args).stdout

    def can(self, verb, resource, namespace=None, identity=False, name=None):
        subresource = None
        if "/" in resource:
            resource, subresource = resource.split("/", 1)
        if name:
            resource += "/" + name
        args = ["auth", "can-i", verb, resource]
        if namespace:
            args += ["-n", namespace]
        if subresource:
            args.append("--subresource=" + subresource)
        if identity:
            args += IDENTITY
        result = self.run(*args, check=False)
        answer = result.stdout.strip()
        if (answer, result.returncode) not in {("yes", 0), ("no", 1)}:
            raise Blocked("authorization query failed; impersonation or API errors are not security denials")
        return answer == "yes"


def cluster_identity(kube):
    metadata = kube.get("namespace", "kube-system").get("metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("uid"), str) or not metadata["uid"]:
        raise Blocked("could not read the selected cluster's kube-system UID")
    return metadata


def verify_identity(kube, external_uid=None):
    metadata = cluster_identity(kube)
    uid = metadata["uid"]
    if external_uid is not None and external_uid != uid:
        raise Blocked("external lab UID does not match the selected cluster; no verification was started")
    match = re.fullmatch(r"kind-(cks-[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)", kube.context)
    if match and len(match[1]) <= 63:
        directory = ROOT / "work" / "environments" / match[1]
        record = directory / "environment.json"
        if any(p.is_symlink() for p in (ROOT / "work", directory.parent, directory, record)):
            raise Blocked("local environment record uses a symbolic link; no verification was started")
        if directory.exists():
            try:
                state = json.loads(record.read_text())
                uuid.UUID(state["owner"])
                valid = (state["name"] == match[1] and state["namespace_uid"] == uid
                         and state["phase"] in {"created", "owned", "ready"}
                         and metadata.get("annotations", {}).get("cks-practice/environment-id") == state["owner"])
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                raise Blocked("local environment record is incomplete or invalid; inspect it before verification") from None
            if not valid:
                raise Blocked("selected cluster differs from its local ownership record; external acknowledgement cannot override it")
            print("PASS: selected cluster matches the local environment UID and ownership marker")
            return
    if external_uid is None:
        raise Blocked("no local ownership record; inspect preflight and acknowledge your disposable lab with --external-lab-uid UID")
    print("PASS: selected cluster matches the explicitly acknowledged external lab UID")


def ready(pod):
    return pod.get("status", {}).get("phase") == "Running" and any(
        c.get("type") == "Ready" and c.get("status") == "True" for c in pod["status"].get("conditions", []))


def workload(kube, name, namespace="cks-lab", label=None):
    pod = kube.get("pod", name, namespace, optional=True)
    if not pod or not ready(pod) or pod.get("metadata", {}).get("deletionTimestamp"):
        raise Blocked(f"{namespace}/{name} must exist and be Running/Ready")
    if len(pod.get("spec", {}).get("containers", [])) != 1:
        raise Blocked(f"{namespace}/{name} must use the single-container practice fixture")
    if label and pod["metadata"].get("labels", {}).get(label[0]) != label[1]:
        raise Blocked(f"{namespace}/{name} does not have the expected fixture label")
    return pod


def baseline(kube):
    return {(ns, name): workload(kube, name, ns, ("app", "api") if name == "api" else ("role", name))
            for ns, names in [("cks-lab", ["api", "client", "intruder"]), ("cks-other", ["api", "client"])]
            for name in names}


def http_url(address):
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        raise Blocked("fixture has no valid Pod IP") from None
    return f"http://{'[' + str(ip) + ']' if ip.version == 6 else ip}:8080/"


HTTP_PROBE = '''command -v wget >/dev/null || { echo LAB_BROKEN; exit 0; }
output=$(wget -qO- -T 3 "$1" 2>&1)
if [ "$?" -eq 0 ]; then printf 'LAB_OK\\n%s\\n' "$output"; else printf 'LAB_DENIED\\n%s\\n' "$output"; fi'''


def http(kube, pod, url, expected_body="cks-practice"):
    output = kube.exec(pod, HTTP_PROBE, url)
    if output.startswith("LAB_OK\n"):
        return "ok" if output.split("\n", 1)[1].strip() == expected_body else "wrong-page"
    if output.startswith("LAB_DENIED\n"):
        if "server returned error: HTTP" in output:
            return "http-error"
        if any(reason in output.lower() for reason in ("timed out", "connection refused")):
            return "denied"
    raise Blocked("HTTP witness failed without a recognized connection result; check wget and networking")


def traffic(kube, pod, url, allowed, label, expected_body="cks-practice"):
    result = http(kube, pod, url, expected_body)
    require(result == ("ok" if allowed else "denied"), label)


def dns(kube, pod, hostname):
    resolver = kube.exec(pod, "cat /etc/resolv.conf")
    prefix = pod["metadata"]["namespace"] + ".svc."
    suffixes = [entry[len(prefix):] for line in resolver.splitlines() if line.split()[:1] == ["search"]
                for entry in line.split()[1:] if entry.startswith(prefix)]
    if not suffixes:
        raise Blocked("cannot determine cluster DNS suffix from the witness search path")
    # BusyBox nslookup does not expand dotted .svc names like the HTTP client's resolver does.
    hostname = hostname + "." + suffixes[0].rstrip(".") + "."
    output = kube.exec(pod, 'command -v nslookup >/dev/null || { echo LAB_BROKEN; exit 0; }; '
                       'if nslookup "$1" >/dev/null 2>&1; then echo LAB_DNS_OK; else echo LAB_DNS_FAILED; fi', hostname)
    if output.strip() not in {"LAB_DNS_OK", "LAB_DNS_FAILED"}:
        raise Blocked("DNS witness unavailable")
    require(output.strip() == "LAB_DNS_OK", f"{pod['metadata']['name']} resolves {hostname}")


@contextmanager
def ingress_probe(kube):
    name, owner = "cs01-ingress-probe", str(uuid.uuid4())
    if kube.get("networkpolicy", name, "cks-lab", optional=True):
        raise Blocked(f"cks-lab/{name} already exists; inspect it before retrying")
    policy = {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
              "metadata": {"name": name, "namespace": "cks-lab", "annotations": {"cks-practice/owner": owner}},
              "spec": {"podSelector": {"matchLabels": {"role": "intruder"}}, "policyTypes": ["Egress"],
                       "egress": [{"to": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": ns}},
                                           "podSelector": {"matchLabels": {"app": "api"}}}
                                          for ns in ("cks-lab", "cks-other")], "ports": [{"protocol": "TCP", "port": 8080}]}]}}
    try:
        kube.run("create", "-f", "-", "-o", "json", document=policy)
        yield
    finally:
        # A lost create response can still leave our object behind. Recover ownership before deleting.
        handlers = {sig: signal.signal(sig, signal.SIG_IGN) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            current = kube.get("networkpolicy", name, "cks-lab", optional=True)
            if current:
                meta = current.get("metadata", {})
                if meta.get("annotations", {}).get("cks-practice/owner") != owner or not meta.get("uid"):
                    raise Blocked(f"cleanup: {name} ownership changed; left untouched")
                path = f"/apis/networking.k8s.io/v1/namespaces/cks-lab/networkpolicies/{name}"
                kube.run("delete", "--raw", path, "-f", "-", document={"apiVersion": "v1", "kind": "DeleteOptions",
                         "preconditions": {"uid": meta["uid"]}})
                if kube.get("networkpolicy", name, "cks-lab", optional=True):
                    raise Blocked(f"cleanup: {name} still exists; inspect it before retrying")
                print(f"PASS: removed owned {name}")
        except Blocked:
            raise Blocked(f"cleanup incomplete for cks-lab/{name}; inspect and remove only your verifier's policy") from None
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)


def cs01(kube, pods):
    client, intruder = pods["cks-lab", "client"], pods["cks-lab", "intruder"]
    other = pods["cks-other", "client"]
    local_url = http_url(pods["cks-lab", "api"]["status"].get("podIP", ""))
    other_url = http_url(pods["cks-other", "api"]["status"].get("podIP", ""))
    for witness in (client, intruder):
        dns(kube, witness, "api.cks-lab.svc")
    traffic(kube, client, "http://api.cks-lab.svc:8080/", True, "permitted service request succeeds")
    traffic(kube, client, local_url, True, "permitted direct-IP request succeeds")
    traffic(kube, other, "http://api.cks-other.svc:8080/", True, "other namespace remains functional")
    traffic(kube, intruder, local_url, False, "intruder is blocked before the independent ingress check")
    traffic(kube, other, local_url, False, "cross-namespace ingress is denied")
    traffic(kube, client, other_url, False, "client cross-namespace egress is denied")
    with ingress_probe(kube):
        for attempt in range(4):
            if http(kube, intruder, other_url) == "ok":
                break
            if attempt == 3:
                raise Blocked("temporary egress witness never became functional; ingress cannot be assessed")
            time.sleep(0.5)
        print("PASS: temporary intruder egress is demonstrably active")
        traffic(kube, intruder, local_url, False, "API ingress independently denies the intruder")
        traffic(kube, client, local_url, True, "permitted application remains healthy")
    for attempt in range(4):
        if http(kube, intruder, other_url) == "denied":
            break
        if attempt == 3:
            raise Blocked("temporary egress has not been withdrawn; check CNI convergence before retrying")
        time.sleep(0.5)
    baseline(kube)
    traffic(kube, client, local_url, True, "permitted application remains healthy after cleanup")
    traffic(kube, other, other_url, True, "other namespace remains healthy after cleanup")
    print("PASS: original intruder isolation restored after cleanup")


def token_absent(kube, pod):
    volumes = pod["spec"].get("volumes", [])
    projected = any("serviceAccountToken" in source for volume in volumes
                    for source in volume.get("projected", {}).get("sources", []))
    require(not projected, "no projected ServiceAccount token volume")
    output = kube.exec(pod, 'if [ -e /var/run/secrets/kubernetes.io/serviceaccount/token ]; '
                       'then echo LAB_TOKEN_PRESENT; else echo LAB_TOKEN_ABSENT; fi')
    if output.strip() not in {"LAB_TOKEN_PRESENT", "LAB_TOKEN_ABSENT"}:
        raise Blocked("token-presence witness returned an unexpected result")
    require(output.strip() == "LAB_TOKEN_ABSENT", "usual ServiceAccount token path is absent")


def ch02(kube, pods):
    pod = workload(kube, "ch02-client")
    account = kube.get("serviceaccount", "ch02-client", "cks-lab")
    require(pod["spec"].get("serviceAccountName") == "ch02-client", "Pod uses ch02-client identity")
    require(account.get("automountServiceAccountToken") is False and pod["spec"].get("automountServiceAccountToken") is not True,
            "ServiceAccount automount is disabled without a Pod override")
    token_absent(kube, pod)
    for verb in ("get", "list"):
        require(kube.can(verb, "pods", "cks-lab", identity=True), f"ServiceAccount may {verb} local Pods")
    for namespace, resource, verbs in [("cks-lab", "secrets", ("get", "list", "watch")),
                                      ("cks-lab", "pods", ("watch", "create", "update", "patch", "delete", "deletecollection")),
                                      ("cks-other", "pods", ("get", "list"))]:
        for verb in verbs:
            require(not kube.can(verb, resource, namespace, identity=True), f"ServiceAccount cannot {verb} {namespace}/{resource}")
    for namespace in ("cks-lab", "cks-other"):
        review = {"apiVersion": "authorization.k8s.io/v1", "kind": "SelfSubjectRulesReview",
                  "spec": {"namespace": namespace}}
        status = kube.decode(kube.run("create", "--raw", "/apis/authorization.k8s.io/v1/selfsubjectrulesreviews",
                                      "-f", "-", *IDENTITY, document=review).stdout).get("status", {})
        if status.get("incomplete") is not False or not isinstance(status.get("resourceRules"), list):
            raise Blocked("effective permission rules are incomplete; inspect authorization before assessing CH02")
        for rule in status["resourceRules"]:
            verbs, groups, resources = (set(rule.get(field, [])) for field in ("verbs", "apiGroups", "resources"))
            if not verbs or not groups or not resources:
                raise Blocked("effective permission rules are malformed")
            pod_reader = namespace == "cks-lab" and groups == {""} and resources == {"pods"} and verbs <= {"get", "list"}
            self_review = verbs == {"create"} and (
                (groups == {"authorization.k8s.io"} and resources <= {"selfsubjectaccessreviews", "selfsubjectrulesreviews"})
                or (groups == {"authentication.k8s.io"} and resources == {"selfsubjectreviews"}))
            public_trust = groups == {"certificates.k8s.io"} and resources == {"clustertrustbundles"} and verbs <= {"get", "list", "watch"}
            if not (pod_reader or self_review or public_trust):
                raise Failed(f"no extra resource grants in {namespace}, including named-resource grants")
        print(f"PASS: only intended resource permissions in {namespace}")


def mw02(kube, pods):
    pod = workload(kube, "demo")
    spec = pod["spec"]
    settings = {**spec.get("securityContext", {}), **spec["containers"][0].get("securityContext", {})}
    require(settings.get("runAsNonRoot") is True and settings.get("allowPrivilegeEscalation") is False
            and "ALL" in settings.get("capabilities", {}).get("drop", [])
            and not settings.get("capabilities", {}).get("add")
            and settings.get("readOnlyRootFilesystem") is True
            and settings.get("seccompProfile", {}).get("type") == "RuntimeDefault"
            and spec.get("automountServiceAccountToken") is False, "requested workload restrictions are configured")
    output = kube.exec(pod, "cat /proc/1/status")
    status = dict(line.split(":", 1) for line in output.splitlines() if ":" in line)
    if not all(field in status for field in ("Uid", "Gid", "CapEff", "NoNewPrivs", "Seccomp")):
        raise Blocked("runtime process status is unavailable")
    require(status["Uid"].split() == ["1000"] * 4 and status["Gid"].split() == ["1000"] * 4,
            "application UID/GID are 1000")
    try:
        empty_caps = int(status["CapEff"].strip(), 16) == 0
    except ValueError:
        raise Blocked("runtime capabilities are not readable") from None
    require(empty_caps and status["NoNewPrivs"].strip() == "1" and status["Seccomp"].strip() == "2",
            "application has no effective capabilities, cannot gain privileges and uses seccomp filtering")
    mounts = [line.split() for line in kube.exec(pod, "cat /proc/mounts").splitlines()]
    roots = [fields for fields in mounts if len(fields) >= 4 and fields[1] == "/"]
    if len(roots) != 1:
        raise Blocked("cannot identify the container root mount")
    require("ro" in roots[0][3].split(","), "root mount is actually read-only")
    output = kube.exec(pod, 'path=$(mktemp /tmp/cks-mw02.XXXXXX) || exit 1; '
                       'trap \'rm -f "$path"\' EXIT; printf practice > "$path" && '
                       '[ "$(cat "$path")" = practice ] && rm "$path" && echo LAB_TMP_OK')
    require(output.strip() == "LAB_TMP_OK", "temporary file can be written, read and removed")
    output = kube.exec(pod, 'path=$(mktemp /cks-mw02.XXXXXX 2>/dev/null); '
                       'if [ -n "$path" ]; then rm -f "$path"; echo LAB_ROOT_WRITABLE; else echo LAB_ROOT_DENIED; fi')
    require(output.strip() == "LAB_ROOT_DENIED", "root-filesystem write is denied on the verified read-only mount")
    token_absent(kube, pod)
    traffic(kube, pods["cks-lab", "client"], http_url(pod["status"].get("podIP", "")), True,
            "hardened application still serves the expected page")


def mw01(kube, pods=None):
    version = kube.decode(kube.run("version", "-o", "json").stdout).get("serverVersion", {}).get("gitVersion", "")
    parts = version.removeprefix("v").split(".")
    if not version.startswith("v") or len(parts) < 3 or not all(part.isdigit() for part in parts[:2]):
        raise Blocked("server minor version could not be detected for the Pod Security pin")
    pin = "v" + ".".join(parts[:2])
    labels = kube.get("namespace", "cks-lab").get("metadata", {}).get("labels", {})
    prefix = "pod-security.kubernetes.io/"
    require(labels.get(prefix + "enforce") == "restricted" and labels.get(prefix + "enforce-version") == pin,
            f"cks-lab enforces Restricted pinned to server minor {pin}")
    require(all(labels.get(prefix + mode) in {"privileged", "baseline", "restricted"} for mode in ("audit", "warn")),
            "audit and warn modes are deliberately configured")
    probe = {"apiVersion": "v1", "kind": "Pod", "metadata": {"namespace": "cks-lab"},
             "spec": {"automountServiceAccountToken": False, "restartPolicy": "Never",
                      "securityContext": {"runAsNonRoot": True, "runAsUser": 1000,
                                          "seccompProfile": {"type": "RuntimeDefault"}},
                      "containers": [{"name": "probe", "image": "docker.io/library/busybox:1.37",
                                      "command": ["sleep", "60"], "securityContext": {
                                          "allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                                          "capabilities": {"drop": ["ALL"]}}}]}}
    for phase in ("compliant", "noncompliant", "other namespace"):
        probe["metadata"]["name"] = "mw01-" + uuid.uuid4().hex[:12]
        probe["metadata"]["namespace"] = "cks-other" if phase == "other namespace" else "cks-lab"
        probe["spec"]["containers"][0]["securityContext"]["allowPrivilegeEscalation"] = phase != "compliant"
        result = kube.run("create", "--dry-run=server", "-f", "-", "-o", "json", document=probe, check=False)
        if phase == "noncompliant":
            if result.returncode == 0:
                raise Failed("noncompliant Pod is denied in cks-lab")
            if (f'violates PodSecurity "restricted:{pin}"' not in result.stderr
                    or "allowPrivilegeEscalation != false" not in result.stderr):
                raise Blocked("rejection was not the expected Restricted privilege-escalation denial")
            print("PASS: Restricted admission rejects the single-field privilege-escalation violation")
        elif result.returncode:
            if phase == "other namespace" and "violates PodSecurity" in result.stderr:
                raise Failed("cks-other must still admit the same noncompliant Pod")
            raise Blocked(f"{phase} admission control failed; check API access, permissions and other admission policies")
        else:
            print(f"PASS: {phase} Pod passes server admission without being persisted")


def cs06(kube, pods=None):
    fixtures = [("cks-tiers", "frontend", "frontend"), ("cks-tiers", "backend", "backend"),
                ("cks-tiers", "intruder", "intruder"), ("cks-data", "database", "database"),
                ("cks-data", "frontend-witness", "frontend"), ("cks-data", "backend-witness", "backend")]

    def refresh():
        return {(ns, name): workload(kube, name, ns, ("tier", tier)) for ns, name, tier in fixtures}

    pods = refresh()
    for namespace in ("cks-tiers", "cks-data"):
        policies = kube.get("networkpolicies", namespace=namespace).get("items", [])
        require(not any("Egress" in p.get("spec", {}).get("policyTypes", ["Egress"] if "egress" in p.get("spec", {}) else [])
                        for p in policies), f"{namespace} policies keep egress unrestricted for independent ingress checks")
    flows = [("cks-tiers", "frontend", "cks-tiers", "backend", True),
             ("cks-tiers", "backend", "cks-data", "database", True),
             ("cks-tiers", "intruder", "cks-tiers", "backend", False),
             ("cks-data", "frontend-witness", "cks-tiers", "backend", False),
             ("cks-tiers", "frontend", "cks-data", "database", False),
             ("cks-tiers", "intruder", "cks-data", "database", False),
             ("cks-data", "backend-witness", "cks-data", "database", False)]
    for ns, source, target_ns, target, allowed in flows:
        traffic(kube, pods[ns, source], http_url(pods[target_ns, target]["status"].get("podIP", "")), allowed,
                f"{ns}/{source} to {target_ns}/{target} is {'allowed' if allowed else 'denied'}", target + "-witness")
    pods = refresh()
    for ns, source, target_ns, target, allowed in flows[:2]:
        traffic(kube, pods[ns, source], http_url(pods[target_ns, target]["status"].get("podIP", "")), allowed,
                f"{target_ns}/{target} remains healthy after the denied requests", target + "-witness")


def preflight(kube):
    metadata = cluster_identity(kube)
    print(f"INFO: context={kube.context} cluster UID={metadata['uid']}")
    versions = kube.decode(kube.run("version", "-o", "json").stdout)
    for key in ("clientVersion", "serverVersion"):
        version = versions.get(key, {}).get("gitVersion")
        if not version:
            raise Blocked("client/server version could not be detected")
        print(f"INFO: {key}={version}")
    nodes = kube.get("nodes").get("items", [])
    if not nodes:
        raise Blocked("no accessible nodes")
    usable = False
    for node in nodes:
        info = node.get("status", {}).get("nodeInfo", {})
        node_ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in node.get("status", {}).get("conditions", []))
        print(f"INFO: node={node['metadata']['name']} Ready={node_ready} OS={info.get('operatingSystem', 'unknown')} "
              f"runtime={info.get('containerRuntimeVersion', 'unknown')} kernel={info.get('kernelVersion', 'unknown')}")
        if not node_ready:
            raise Blocked("restore node readiness before practice")
        usable |= info.get("operatingSystem") == "linux" and not node.get("spec", {}).get("unschedulable", False) and not any(
            t.get("effect") in {"NoSchedule", "NoExecute"} for t in node.get("spec", {}).get("taints", []))
    if not usable:
        raise Blocked("a schedulable Linux node is required for the supplied fixtures")
    permissions = [(verb, "namespaces", None) for verb in ("get", "create", "patch", "delete")]
    for namespace in ("cks-lab", "cks-other"):
        for resource in ("pods", "services"):
            permissions.extend((verb, resource, namespace) for verb in ("get", "list", "watch", "create", "patch", "delete"))
        permissions.extend((verb, "pods/exec", namespace) for verb in ("get", "create"))
    for resource in ("networkpolicies", "serviceaccounts", "roles", "rolebindings"):
        permissions.extend((verb, resource, "cks-lab") for verb in ("get", "create", "patch", "delete"))
    missing = [f"{verb} {namespace or 'cluster'}/{resource}" for verb, resource, namespace in permissions
               if not kube.can(verb, resource, namespace)]
    if not kube.can("impersonate", "serviceaccounts", "cks-lab", name="ch02-client"):
        missing.append("impersonate cks-lab/ch02-client ServiceAccount")
    for group in ("system:serviceaccounts", "system:serviceaccounts:cks-lab", "system:authenticated"):
        if not kube.can("impersonate", "groups", name=group):
            missing.append(f"impersonate group {group}")
    if missing:
        raise Blocked("required permissions missing: " + "; ".join(missing))
    print("PASS: checked setup/verification permissions for the first three drills")
    try:
        items = kube.decode(kube.run("get", "daemonsets", "-A", "-o", "json").stdout).get("items", [])
        names = [item["metadata"]["name"] for item in items]
        candidates = [name for name in names if any(part in name.lower() for part in ("calico", "cilium", "antrea", "kindnet", "flannel", "weave", "aws-node", "azure", "kube-router"))]
        print("INFO: CNI candidates=" + (", ".join(candidates) or "not identified"))
    except Blocked:
        print("INFO: CNI discovery UNKNOWN (daemonsets unavailable to this identity)")
    print("INFO: NetworkPolicy enforcement UNKNOWN until CS01's behavioral checks pass")
    try:
        classes = kube.get("runtimeclasses").get("items", [])
        print("INFO: RuntimeClasses=" + (", ".join(item["metadata"]["name"] for item in classes) or "none"))
    except Blocked:
        print("INFO: RuntimeClass discovery UNKNOWN")
    print("INFO: sandbox runtime/AppArmor capability UNKNOWN; a RuntimeClass object is not runtime proof")
    print("INFO: optional local tools " + ", ".join(f"{name}={'found' if shutil.which(name) else 'missing'}"
          for name in ("kind", "docker", "openssl", "curl", "trivy", "cosign", "helm")))


def main(argv=None):
    checks = {"CS01": cs01, "CS06": cs06, "CH02": ch02, "MW01": mw01, "MW02": mw02}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True, help="explicit disposable-cluster context")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight", help="read-only environment inventory and prerequisite checks")
    verify = commands.add_parser("verify", help="verify a completed drill; CS01 temporarily creates a scoped egress policy")
    verify.add_argument("drill", choices=checks)
    verify.add_argument("--external-lab-uid", help="explicitly acknowledge this disposable external cluster's kube-system UID")
    args = parser.parse_args(argv)
    if not args.context.strip():
        parser.error("--context must not be empty")
    def interrupted(signum, frame):
        raise Blocked("interrupted; temporary policy cleanup was attempted if needed")
    handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        kube = Kubectl(args.context)
        if args.command == "preflight":
            preflight(kube)
        else:
            verify_identity(kube, args.external_lab_uid)
            pods = baseline(kube) if args.drill in {"CS01", "CH02", "MW02"} else None
            checks[args.drill](kube, pods)
        print("PASS: " + ("preflight inventory; next run the drill's behavioral checks" if args.command == "preflight" else args.drill))
        return 0
    except Failed as error:
        print(f"FAIL: {error}")
        return 1
    except (Blocked, KeyboardInterrupt) as error:
        print(f"BLOCKED: {error or 'interrupted'}")
        return 2
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
