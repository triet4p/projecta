# Task Summary: S3-07 — Build the multi-stage image

**Sprint:** Sprint 3
**Task:** S3-07

## Summary of Work

Added a multi-stage Dockerfile with development, test, build, and non-root
runtime targets. The image pins Java 21/Maven and Java 21 JRE base-image
digests, executes tests in the test stage, and carries only compiled classes and
runtime dependencies into the runtime stage.

## Files Modified

- [services/semantic-core/Dockerfile](../../../../services/semantic-core/Dockerfile) - pinned multi-stage service image.
- [services/semantic-core/.dockerignore](../../../../services/semantic-core/.dockerignore) - minimal build context.
- [services/semantic-core/pom.xml](../../../../services/semantic-core/pom.xml) - copies runtime dependencies during package.
- [services/semantic-core/src/main/java/org/projecta/semanticcore/SemanticCoreApplication.java](../../../../services/semantic-core/src/main/java/org/projecta/semanticcore/SemanticCoreApplication.java) - container smoke-test server lifecycle without application endpoints.
- [services/semantic-core/README.md](../../../../services/semantic-core/README.md) - container-only workflow note.
- [docs/sprint-plans/sprint-3.md](../../../../docs/sprint-plans/sprint-3.md) - records task completion.

## Testing

- **Test Image:** `projecta-semantic-core:test`
- **Status:** Passed.
- **Execution Commands:**

  - `docker build --target test --tag projecta-semantic-core:test services/semantic-core`
  - `docker build --target runtime --tag projecta-semantic-core:local services/semantic-core`
  - `docker run --rm --entrypoint java projecta-semantic-core:local -version`

## Additional Notes

- The runtime target runs as the dedicated non-root `semantic` user. Canonical
  Compose integration is added by S3-08.
