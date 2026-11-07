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

### Compiler-to-runtime variation

The [Go starter](fixtures/image-go/README.md) makes multi-stage reduction a concrete operation, following the course's image-footprint practice. It has a real compilation step and no external Go dependencies. With an installed builder, use a fresh working directory:

```bash
mkdir -p work/SC01-go
cp labs/fixtures/image-go/main.go labs/fixtures/image-go/Dockerfile work/SC01-go/
docker build -t cks-go:single work/SC01-go
```

The first image deliberately keeps the Go toolchain and source. Rewrite the copied Dockerfile to compile a static binary in a named build stage, copy only that binary into a runtime stage, and run as UID/GID 65532 on port 8080. Choose a verified builder-image digest. The [multi-stage reference](../solutions/Dockerfile.multistage) is available after attempting the edit; use `work/SC01-go` as its build context, not the repository root.

Build the result as `cks-go:multi`. Run each image in turn as a named probe with the port published only to `127.0.0.1`, and confirm that both return `cks-practice`. Compare image sizes/history and verify that the final image has no compiler, source tree or shell. Repeat the final image with a read-only root, all capabilities dropped and no-new-privileges. A missing shell must not be confused with a failed application: HTTP must still work.

For example, after building the final image:

```bash
docker run -d --name cks-go-probe --read-only --cap-drop ALL \
  --security-opt no-new-privileges -p 127.0.0.1:18080:8080 cks-go:multi
curl --fail http://127.0.0.1:18080/
docker inspect --format '{{.Config.User}} {{.State.Running}}' cks-go-probe
docker exec cks-go-probe /bin/sh -c true
```

Check that the name and local port are unused before starting. Expect a working page, configured non-root identity, and an explicit missing-executable failure for the shell probe. Inspect the effective runtime settings too. Remove only `cks-go-probe` and the two task-owned image tags when finished. `scratch` works for this static application; other applications may require CA certificates, libraries or timezone data.

Reference: [multi-stage builds](https://docs.docker.com/build/building/multi-stage/).

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

## SC04 Signatures

**Environment:** a compatible Cosign installation and a private lab registry where you are authorized to push images and signatures. Use dummy artifacts and an explicitly chosen transparency-log policy. Signing can contact a transparency service and publish signature metadata; use the current tool documentation before choosing an offline or private-log mode.

**Start:** push the SC01 image to the owned registry, resolve its digest, and create a lab-only signing key pair under `work/`. Keep the private key and password out of Git. Set `SIGNED_IMAGE` to the fully qualified digest reference you actually pushed.

**Task:** sign that digest with the lab key and verify it using only the expected public key:

```bash
cosign verify --key work/cks-signing.pub "$SIGNED_IMAGE"
```

Use the real public-key filename you generated. For a keyless variation, bind verification to both the expected signing identity and OIDC issuer. A valid signature from an arbitrary identity is not the requested publisher policy.

**Prove it:** the expected key/identity accepts the intended digest; an unrelated public key fails; an unsigned different digest fails. Record the digest and verifier identity constraints. Changing a tag must not silently change which artifact you trust. Manual verification does not itself stop Kubernetes from admitting another image.

**Reset:** remove only the lab tags/signatures through the owned registry's supported interface if they are no longer needed. Remove private key material when finished; retain non-secret evidence of the policy tested.

Reference: [Cosign verification](https://docs.sigstore.dev/cosign/verifying/verify/).

## SC05 SBOMs

**Environment:** Trivy or another real SBOM generator. Reuse the digest from SC03; set `IMAGE` to that actual image reference.

```bash
trivy image --format spdx-json --output work/sbom.spdx.json "$IMAGE"
trivy image --format cyclonedx --output work/sbom.cdx.json "$IMAGE"
```

**Task:** identify the artifact described, its packages/components, versions and available license information. Select one component and trace it to the image layer or dependency that introduced it. Compare the SBOM with the scanner report from SC02 and explain the difference between an inventory and a vulnerability result.

**Prove it:** the files are valid documents in the claimed formats and contain actual component data for the selected image. Generate an SBOM for a second, different image and show that its identity and inventory are distinguishable. A file containing a format header, or an empty fallback after a failed tool invocation, is not evidence of a generated SBOM. State any missing package or license information rather than inventing it.

**Reset:** retain only the reports and comparison notes you need in `work/`; no cluster resources are required for this drill.

References: [BOM CLI](https://kubernetes-sigs.github.io/bom/cli-reference/), [Trivy SBOM documentation](https://trivy.dev/docs/latest/supply-chain/sbom/).

## SC06 Admission policies

**Environment:** a disposable Kubernetes cluster with the stable ValidatingAdmissionPolicy API available. Start with a fresh shared baseline so another exercise's policy cannot explain a rejection. Confirm that the `cks-allowed-registries` policy and binding names are available for this drill.

**Start:** inspect [registry-policy.yaml](fixtures/registry-policy.yaml). It contains a policy and binding for Pods in namespaces labelled `cks-practice=admission`; only explicitly qualified `docker.io/` and `registry.k8s.io/` image references are allowed. Regular, init and ephemeral containers are considered.

```bash
kubectl apply -f labs/fixtures/registry-policy.yaml
kubectl label namespace cks-lab cks-practice=admission --overwrite
```

**Task:** explain the CEL expressions, the binding's scope and the difference between `failurePolicy: Fail` and the binding's `Deny` action. Prepare uniquely named compliant Pod manifests with one image field changed at a time. Use an `example.invalid/lab/image:v1` reference as the prohibited input; server-side dry runs need not pull it.

**Prove it:**

1. A compliant Pod using an allowed explicit registry is accepted.
2. An unapproved regular-container image is rejected with this policy's message.
3. An unapproved init-container image is rejected even when the main image is allowed.
4. An ephemeral-container update using an unapproved image is rejected. Test the actual subresource update against a drill-owned running Pod; a CREATE-only test does not cover it.
5. An otherwise valid unapproved-image Pod in unlabelled `cks-other` passes server-side dry run. Do not deploy or pull that image.

For all probes, distinguish an admission-policy rejection from malformed YAML, PSA rejection, authorization failure or an existing Pod name. This registry policy does not verify signatures, image contents or ownership of every image in an allowed registry.

**Extension:** on a cluster with a real image-verification webhook, separately test allowed, unsigned/wrong-identity and unavailable-backend outcomes. Confirm the configured fail-open/fail-closed behavior. Do not create fake webhook CRDs or replace the API-server manifest to simulate this extension.

**Reset:** remove the `cks-practice` label you added and delete only the `cks-allowed-registries` binding and policy. Delete the drill's probe Pods. Do not delete all admission policies.

### Gatekeeper variation

Use a disposable cluster with a compatible, healthy Gatekeeper installation. This variation practices the course's actual ConstraintTemplate/Constraint/Rego workflow, rather than treating native CEL as the same tool. Finish the native-policy cleanup first so another policy cannot explain the rejection. Confirm the names below are unused.

Inspect the original [template](../solutions/gatekeeper-template.yaml) and [constraint](../solutions/gatekeeper-constraint.yaml). They use a structural parameter schema, explicit registry prefixes ending in `/`, and all three container-image fields. Apply the template first, wait for its generated CRD, then apply the constraint:

```bash
kubectl apply -f solutions/gatekeeper-template.yaml
kubectl wait --for=create \
  crd/k8spracticeimages.constraints.gatekeeper.sh --timeout=60s
kubectl wait --for=condition=Established \
  crd/k8spracticeimages.constraints.gatekeeper.sh --timeout=60s
kubectl get constrainttemplate k8spracticeimages -o yaml
kubectl apply -f solutions/gatekeeper-constraint.yaml
```

Inspect template/constraint status for ingestion or Rego errors. The `spec.targets[].rego` example uses Gatekeeper's legacy Rego syntax; confirm support in the installed version. Repeat the allowed-image, rejected-main-image and rejected-init-image server-side dry runs in `cks-lab`, then prove that the same otherwise-valid request in `cks-other` is unaffected. The constraint's named rejection must be the reason for denial.

In a working copy, restrict the permitted prefixes further and show the changed result; restore the intended list afterward. Inspect the installed validating webhook's subresource rules before testing ephemeral-container updates. A template can inspect that field only when the controller actually receives the request. Record a routing gap instead of claiming enforcement from Rego text alone.

Delete only `cks-gatekeeper-images` first, verify the previously rejected dry run is accepted again, then delete `k8spracticeimages`. Do not remove the Gatekeeper installation or other constraints. These examples check registry prefixes, not image signatures or contents.

References: [ConstraintTemplates](https://open-policy-agent.github.io/gatekeeper/website/docs/constrainttemplates/), [Killer Shell admission-policy practice](https://github.com/killer-sh/cks-course-environment/tree/f10551265c2eb04c12a443afaa8500eb824530de/course-content/opa).

## SC07 Build provenance

**Environment:** the local Git checkout, SC01 build outputs and a JSON/text editor. A real attestation-verification extension also needs an artifact with published provenance and a trusted verifier already installed.

**Start:** record the current commit, the hash of the actual Dockerfile used, its base digest, the build command, and the resulting image identity in `work/build-record.txt`. Note explicitly if the build context differs from the committed starter. This handwritten trace is not a signed attestation.

**Task:** trace source, resolved dependencies, builder, artifact, test result, signature and publication as separate handoffs. Identify which values are immutable and who could replace each mutable tag or output. For a proposed CI flow, state which job may build, which may sign and which may publish; untrusted contributions must not receive publishing/signing authority.

**Prove it:** build a changed copy of the page and demonstrate that its artifact identity differs, so the original digest/signature does not identify it. Explain why a successful build, repository name, or signing-workflow filename alone does not prove every provenance claim. Where an actual attestation is available, verify the subject digest, expected repository/workflow identity and expected release ref/commit; reject a wrong subject or wrong trusted identity. Without that artifact, record the attestation part as not measured.

**Reset:** remove only the alternate lab image/tag. Keep the non-secret handoff notes and genuine verification output. Never replace a missing attestation with a locally fabricated success file.

## SC08 Static analysis

**Environment:** the static-analysis stage needs an installed Trivy version with its misconfiguration checks available. It scans local files without a cluster or execution of the deliberately flawed inputs. Initial check-bundle retrieval may need network access. Full completion also requires a working image builder/runtime and a disposable cluster able to pull the repaired image, for the separate functional proof below. KubeLinter is an optional Kubernetes-only comparison, not a replacement for Dockerfile analysis. Record the tool version and the check configuration/bundle used, then keep them consistent for the comparison.

**Start:** inspect the warnings in the [static-analysis fixtures](fixtures/static-analysis/README.md). Copy them into an isolated working directory. **Do not apply or build the original inputs.**

```bash
mkdir -p work/SC08/before work/SC08/after
cp labs/fixtures/static-analysis/deployment.yaml labs/fixtures/static-analysis/Dockerfile work/SC08/before/
cp work/SC08/before/deployment.yaml work/SC08/before/Dockerfile work/SC08/after/
trivy --version > work/SC08/tool-version.txt
trivy config --exit-code 1 --format json \
  --output work/SC08/before.json work/SC08/before
```

A nonzero result is expected when checks find problems, but inspect the report and diagnostics: a failed download, parse error or missing tool is not a successful detection. Reports stay outside the scanned directories so they cannot become accidental build inputs.

**Task:** explain the actual reported findings and the relevant source fields. Assess image identity, container user, privilege escalation, writable filesystem, token mounting, resources and build-context scope. Repair only the `after` copies while retaining an HTTP application on port 8080. Use a verified image digest; retain required writable paths explicitly. Copy [the sample page](fixtures/image/index.html) into the repaired image context and narrow `COPY` to that required file. Do not suppress a relevant rule simply to obtain a green report.

Rerun the same check policy and inspect the before/after differences:

```bash
trivy config --exit-code 1 --format json \
  --output work/SC08/after.json work/SC08/after
```

If the scanner or checks changed during the exercise, rerun both inputs with the same versions. Finding identifiers, counts and severities can change; the task is to explain and repair observed categories, not match a hardcoded count. As an optional Kubernetes-only comparison, run an installed KubeLinter against the repaired Deployment and explain any differences in its checks.

**Prove it:** the deliberately flawed input still triggers relevant findings, and the repaired input satisfies the chosen checks without broad exclusions. Separately build and run only the repaired image using SC01's loopback-only probe, then validate the repaired Deployment on the disposable cluster. Ensure it references the repaired image available to that cluster, becomes Ready, and serves the page with the intended runtime restrictions. Static analysis, vulnerability scanning and runtime enforcement are different forms of evidence. If a builder/runtime or cluster is unavailable, record the static stage's result and the functional stage as not measured; do not mark the full drill passed.

**Reset:** remove only the repaired `static-analysis-demo` Deployment and any specifically named probe container/image created for this drill. Preserve reports needed for comparison in `work/`. The scanner-only stage creates no cluster resources.

References: [Trivy misconfiguration scanning](https://trivy.dev/docs/latest/scanner/misconfiguration/), [KubeLinter usage](https://github.com/stackrox/kube-linter/blob/main/README.md#using-kubelinter).
