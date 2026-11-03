# System hardening

These drills need dedicated Linux lab VMs, not the workstation or a shared node. Read the [environment guide](../preparation/LAB-SAFETY.md), keep console/SSH recovery available, and record results in the [progress log](../preparation/PROGRESS.md). Run node commands on the named lab VM; transfer only the required local fixture to that node.

## SH01 Services and ports

**Start:** on a disposable VM with Python 3 and systemd, confirm TCP 8088 and the unit name `cks-demo.service` are unused. Create a new `/var/lib/cks-demo` directory containing a dummy `index.html`. Make it readable by the unprivileged service user. Do not serve a home directory, repository or credential directory.

Create this task-owned unit, adjusting the Python path only after checking `command -v python3`:

```ini
[Unit]
Description=CKS disposable HTTP exercise

[Service]
User=nobody
WorkingDirectory=/var/lib/cks-demo
ExecStart=/usr/bin/python3 -m http.server 8088 --bind 127.0.0.1

[Install]
WantedBy=multi-user.target
```

Install it as `/etc/systemd/system/cks-demo.service`, reload systemd and enable/start only that unit. Prove a local request to `http://127.0.0.1:8088/` succeeds. Its loopback bind is intentional: no external listener is needed to learn process and service ownership.

**Task:** identify the listener, process identity, executable path, owning unit and package supplying the executable. Stop and disable the unnecessary **unit**, keeping Python and unrelated services intact. Explain how the bind address in `ExecStart` restricts its network exposure and how a lab firewall could restrict an intentionally external service separately. Inventory installed packages and identify one unnecessary package for removal only if it is isolated to this disposable exercise; do not remove a shared runtime to stop one service.

**Prove:** the dummy response succeeds before the change; afterward, no task listener exists and a new connection to 8088 fails. The unit is inactive and disabled. An unrelated required service and the Kubernetes node, if present, remain healthy. Do not count a failed request caused by the wrong address as evidence. Never delete the executable found through `/proc/PID/exe`.

**Reset:** ensure the unit is stopped, remove only `/etc/systemd/system/cks-demo.service` and the task's dummy directory, then reload systemd. Do not kill arbitrary processes using a port or uninstall Python. Restore the snapshot if unrelated host state changed.

## SH02 OS permissions

**Start:** use a disposable VM and confirm the names `cks-reader`, `cks-outsider`, and `/srv/cks-private` do not already exist. Create two dedicated system users with their own groups, no home directories and no login shell. Create the new directory and a `note.txt` containing only a dummy phrase. Initially make the directory traversable and file readable by both users, and demonstrate that baseline.

**Task:** give `cks-reader` permission to read the file while keeping ownership with root. Deny access to `cks-outsider`. Use a dedicated group, directory mode `0750`, and file mode `0640`; keep the group consistent on the directory and file. Do not grant sudo or change a real user's memberships.

**Prove:** run the same operation as each identity:

```bash
sudo -u cks-reader cat /srv/cks-private/note.txt
sudo -u cks-outsider cat /srv/cks-private/note.txt
sudo -u cks-reader sh -c 'printf changed >> /srv/cks-private/note.txt'
```

The reader succeeds, the outsider is denied, and the reader cannot modify the root-owned file. Check all parent-directory traversal permissions as well as the leaf file. Explain why read permission on a file cannot compensate for missing directory search permission, and why a read-only group should not own writable parent directories.

**Reset:** remove the dummy file/directory and only the two users/groups created by this drill. If any name already belonged to something else, do not change it: choose distinct task-owned names instead and record them.

## SH03 AppArmor

**Start:** apply the shared workload fixture to a fresh lab namespace. Its `client` is your unchanged witness. Identify its Linux node, confirm AppArmor is enabled and `apparmor_parser` is available there, and choose a node label that identifies it. Run both sides of this comparison on that same prepared node.

Use [apparmor-deny-write](fixtures/apparmor-deny-write), a narrow teaching profile named `cks-deny-write`. It allows normal operations and denies writes specifically to `/tmp/blocked.txt`. It is not a general workload-hardening policy. Confirm that profile name is unused before installing it on the selected node as `/etc/apparmor.d/cks-deny-write`, then load it in enforce mode using `apparmor_parser`.

**Task:** copy the client Pod stanza from [workloads.yaml](fixtures/workloads.yaml) into your own `work/SH03/pod.yaml`, rename it `sh03-confined`, and select the prepared node. Add this Pod-level field while retaining the other security settings and writable `/tmp` volume:

```yaml
securityContext:
  appArmorProfile:
    type: Localhost
    localhostProfile: cks-deny-write
```

Create the new Pod and wait for Ready. Do not edit a running Pod's immutable profile settings or substitute the deprecated annotation form.

**Prove:** on `sh03-confined`, writing `/tmp/allowed.txt` succeeds while writing `/tmp/blocked.txt` fails with an access denial. On the unchanged witness, both operations succeed. Inspect `/proc/self/attr/current` in the confined container and the relevant node audit message to establish that the expected profile is in enforce mode. A read-only volume, missing directory, failed exec or wrong node must not count as AppArmor enforcement.

```bash
kubectl -n cks-lab exec sh03-confined -- cat /proc/self/attr/current
kubectl -n cks-lab exec sh03-confined -- sh -c 'printf ok > /tmp/allowed.txt'
kubectl -n cks-lab exec sh03-confined -- sh -c 'printf blocked > /tmp/blocked.txt'
```

**Reset:** delete `sh03-confined` and wait for it to terminate. Unload only this task-owned profile using `apparmor_parser -R` on its file, then remove that file. Do not disable AppArmor globally. Reset the shared namespace to remove the witness's dummy files.

## SH04 Seccomp

**Start:** apply the shared workload fixture and identify the Linux node hosting its `client` witness. Confirm that node's kernel and container runtime support seccomp. Identify the kubelet root directory. On a default kubeadm node it is `/var/lib/kubelet`; Localhost profiles are resolved below its `seccomp/` directory. Check the actual setting before copying anything and run the confined Pod on this same node.

Copy [seccomp-deny-chmod.json](fixtures/seccomp-deny-chmod.json) to `seccomp/profiles/cks-deny-chmod.json` beneath that root on the selected worker, with root ownership and no unprivileged write access. This teaching profile allows other syscalls and rejects the chmod family with EPERM. It is not a production allowlist. The runtime must understand all included syscall names; a profile-load failure is an environment issue, not successful restriction.

**Task:** create a new Pod `sh04-confined` from the client stanza in the shared fixture, selecting that worker and retaining the writable `/tmp` volume. Replace the Pod's RuntimeDefault seccomp setting with:

```yaml
securityContext:
  seccompProfile:
    type: Localhost
    localhostProfile: profiles/cks-deny-chmod.json
```

Keep its other security-context fields and ensure no container-level seccomp setting overrides the Pod profile. Leave the ordinary `client` witness unchanged.

**Prove:** the new Pod becomes Ready; creating and reading a file in `/tmp` works, but changing its mode fails with EPERM. The unchanged witness must successfully create and chmod its own file. Inspect the declared profile, selected node and runtime events. A container that never starts, a read-only filesystem or a nonexistent target file is not proof of syscall filtering.

```bash
kubectl -n cks-lab exec sh04-confined -- sh -c 'printf ok > /tmp/seccomp-demo; cat /tmp/seccomp-demo'
kubectl -n cks-lab exec sh04-confined -- chmod 600 /tmp/seccomp-demo
kubectl -n cks-lab exec client -- sh -c 'printf ok > /tmp/seccomp-demo; chmod 600 /tmp/seccomp-demo'
```

Explain why filtering only `chmod` may miss another syscall in the same family and why denying all syscalls by default without a complete allowlist can prevent startup.

**Reset:** delete `sh04-confined` and wait for termination before removing only `profiles/cks-deny-chmod.json` from that worker. Do not remove the kubelet's seccomp directory or another workload's profile. Reset the shared namespace to clear witness files.

## SH05 Host firewall rules

**Environment:** a dedicated disposable Linux VM with a working nftables kernel/userspace (`nft`), sudo, Python 3, private networking and console access. Use two controlled clients with curl and **distinct source IPv4 addresses as seen by the VM**. Do not use this drill on the workstation, a shared node, or a VM whose SSH service uses port 8088. Keep the current SSH session and a separate recovery path open.

**Start:** inspect `sudo nft list ruleset` and `ss -ltnp`. Confirm that TCP 8088 and the nftables table name `cks_practice` are unused. Save the existing ruleset privately for comparison; do not load or flush it as part of the exercise. Set `SERVER_IP` to the VM's private IPv4 address. As the ordinary lab user, start a foreground server serving only a new dummy directory:

```bash
umask 077
mkdir -p work/SH05/www
printf 'firewall-practice\n' > work/SH05/www/index.html
sudo nft list ruleset > work/SH05/before.nft
python3 -m http.server 8088 --bind "$SERVER_IP" --directory work/SH05/www
```

On **both clients**, set `SERVER_IP` to the same address and prove this request succeeds before installing any rule:

```bash
curl --noproxy '*' --connect-timeout 3 --max-time 5 "http://$SERVER_IP:8088/"
```

Use the server's request log to identify each client's actual source address. If NAT makes them indistinguishable, change the isolated test topology; do not infer source filtering from two clients that share one visible address.

**Task:** permit one client and block the other on TCP 8088, without changing SSH or unrelated traffic. On the server, save the following as `work/SH05/firewall.nft`. Replace `192.0.2.10` with the **observed allowed-client address** before loading it; that value is a documentation placeholder.

```nft
define allowed_client = 192.0.2.10

table inet cks_practice {
  chain input {
    type filter hook input priority 10; policy accept;
    ip saddr $allowed_client tcp dport 8088 counter accept
    tcp dport 8088 counter drop
  }
}
```

Check the file, then load it once from a second server terminal:

```bash
sudo nft --check --file work/SH05/firewall.nft
sudo nft --file work/SH05/firewall.nft
sudo nft list table inet cks_practice
```

This adds a task-owned `inet` table and an input chain whose drop rule matches **only TCP 8088**. The chain's default policy accepts other traffic for further processing; it does not override another chain's drop. Do not flush an existing ruleset, change another chain's default policy, add a blanket drop, or edit the persistent system firewall configuration. See [nftables base chains and priorities](https://wiki.nftables.org/wiki-nftables/index.php/Configuring_chains).

**Prove:** the allowed client's new request still returns the page; the other client's new request times out. Confirm the corresponding rule counters increase, the server is still running, and SSH plus an unrelated required service remain available. A stopped server or wrong destination address is not firewall proof. Use the same numeric server address before and after, so DNS cannot explain the difference.

**Reset:** from the server's recovery terminal, run `sudo nft delete table inet cks_practice`. Both client requests must work again while the server is still running. Confirm other tables and policies match the saved baseline. Stop only this foreground server with Ctrl+C, then remove its dummy files. Do not kill an arbitrary port owner or restore the whole firewall configuration over unrelated changes.
