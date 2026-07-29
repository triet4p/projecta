# Semantic Core

The Semantic Core is the Java 21/Javalin service that executes Projecta's
domain-safe RDF lifecycle against Fuseki/TDB2.

## Local workflow

Java and Maven run inside containers. A host Java installation is not required.
S3-08 introduces the canonical Compose commands for building and running the
service; direct Docker build commands are limited to image-stage verification.

The S3-06 scaffold intentionally exposes no HTTP endpoints. Endpoint work must
follow the approved [API contract](../../docs/architecture/semantic-core-api.md).

## System test

Run the isolated Compose entry point from the repository root:

```powershell
.\scripts\run_system_tests.ps1
```

It uses a unique Compose project and removes its containers and volumes on exit.
