# Task Summary: S3-04 — Benchmark the service baseline

**Sprint:** Sprint 3
**Task:** S3-04

## Summary of Work

Compared Java and Kotlin plus Spring Boot, Javalin, and Quarkus against the
Semantic Core's Jena/Fuseki integration, startup/image path, testing,
maintenance, and developer-workflow needs. The benchmark recommends Java 21,
Javalin 7.x, and Maven but does not enact that choice.

## Files Modified

- [docs/architecture/semantic-core-stack-benchmark.md](../../../../docs/architecture/semantic-core-stack-benchmark.md) - evidence, scored comparison, recommendation, and empirical measurement protocol.
- [docs/sprint-plans/sprint-3.md](../../../../docs/sprint-plans/sprint-3.md) - records task completion.

## Testing

- **Test Type:** Documentation and source review; no service exists yet for representative runtime measurement.
- **Validation Performed:** Used primary framework and Jena documentation, and specified the repeatable empirical benchmark required after scaffolding.
- **Status:** Ready for S3-05 human stack-selection decision.

## Additional Notes

- Performance figures are intentionally not fabricated from unrelated published
  microbenchmarks. The selected stack's actual image and runtime measurements
  are deferred to S3-06/S3-07.
