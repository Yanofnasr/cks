# Supply chain security

Use only lab artifacts and a registry you control for publishing exercises. Run commands from the repository root, save answers and outputs in ignored `work/`, and record actual tool versions and results in the [progress log](../preparation/PROGRESS.md). Optional build, scan and signing tools must already be installed; these exercises do not install them.

## SC01 Image footprint

**Environment:** a working Docker or compatible image builder. The [image starter](fixtures/image/Dockerfile) serves a static page with BusyBox and deliberately leaves the default root identity.

```bash
mkdir -p work/image
cp labs/fixtures/image/Dockerfile labs/fixtures/image/index.html work/image/
docker build -t cks-image:practice work/image
```

**Task:** inspect the image's layers, base and startup command. Make the copied image run as a non-root UID/GID on port 8080, with only the files needed to serve the page. Select and record a verified base-image digest. Explain which build inputs are needed at runtime; introduce a separate build stage only if an actual build step produces artifacts to copy.

**Prove it:** build the edited context and start one named container, binding its HTTP port only to `127.0.0.1`. Fetch the page, inspect its runtime identity and compare image size/history with the starter. Repeat with a read-only filesystem, all capabilities dropped and no-new-privileges enabled. The page must still work, and a write into the image filesystem must fail. A successful build alone is insufficient.

**Reset:** stop and remove only your named probe container. Remove the `cks-image:practice` tag if no subsequent drill needs it. Do not prune the shared image store.

## SC02 Vulnerability scanning

**Environment:** Trivy with a usable vulnerability database, plus the image built in SC01. Database downloads may require network access. Record scanner/database versions and update times.

```bash
mkdir -p work
trivy --version
trivy image --severity HIGH,CRITICAL --format json \
  --output work/scan.json cks-image:practice
```

**Task:** identify the scanned artifact, affected packages, severity and any fixed versions. Distinguish OS packages from application dependencies. Choose a replacement base or dependency based on the actual findings, rebuild and rescan it. Do not infer safety from a tag's age or a historical statement that it had no vulnerabilities.

**Prove it:** retain the real before/after reports with image identity and database metadata. Configure a nonzero exit status when the chosen severity threshold is present. Exercise that failure path using a deliberately outdated lab image with an actual matching finding, without running the image. A scan with no matching findings should pass the same gate. If the required finding or database is unavailable, mark that control as not measured rather than manufacturing output.

**Reset:** remove only the probe image/tag and reports you no longer need. Preserve your comparison notes; do not change shared scanner policy or registry contents.

## SC03 Image digests

**Environment:** ordinary disposable cluster and an available registry/image-inspection tool. Apply the shared baseline, then copy the [workload starter](fixtures/workload.yaml) into `work/digest.yaml` and name its Pod `digest-demo`.

**Task:** resolve the exact image reference to a digest from the intended registry, record the node architecture, and replace the manifest's tag with an `image@sha256:...` reference. Deploy the copied manifest. Keep a note of how you obtained the expected digest.

**Prove it:** the declared image uses the recorded digest, the Pod is Ready, and the running image identity matches the expected artifact for that node. An image-index digest, platform-manifest digest and local image/config ID are different identifiers; explain the relationship instead of comparing unrelated strings. In a separate probe, use a nonexistent digest and verify that it cannot start. A typo causing ImagePullBackOff is not a completed secure deployment.

**Reset:** delete only the two probe Pods. Keep the real resolved digest for SC04 and SC05.
