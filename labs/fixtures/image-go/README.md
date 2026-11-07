# Compiler-to-runtime image practice

Use this small HTTP application for the [SC01 multi-stage build](../../supply-chain.md#sc01-image-footprint) variation. It uses only the Go standard library and serves `cks-practice` on port 8080. The starting Dockerfile deliberately retains the compiler and source in the runtime image.

With Go already installed, the handler can be checked without opening a socket:

```bash
go test labs/fixtures/image-go/main.go labs/fixtures/image-go/main_test.go
```

That unit test does not build the image or verify container restrictions. Follow SC01 for the actual before/after image build, HTTP request and runtime proof. The [multi-stage reference](../../../solutions/Dockerfile.multistage) retains only a static binary and uses a non-root UID. Select and record an appropriate builder-image digest for reproducible practice.

This application makes no outgoing TLS requests and does not look up OS users. Other applications may need CA certificates, timezone data, shared libraries or other files in their final stage; `scratch` is not a universal replacement for a runtime base image.
