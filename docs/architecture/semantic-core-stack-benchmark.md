# Semantic Core Service-Stack Benchmark — S3-04

**Status:** Decision input only; no stack is selected by this document.

## 1. Decision Scope

The Semantic Core is a small, internal HTTP service around Apache Jena 6.1.0
and remote Fuseki/TDB2. Its critical characteristics are deterministic RDF
transactions, SHACL validation, typed API errors, project-scoped graph routing,
and reliable integration testing—not high request volume or serverless cold
starts.

The comparison covers Java versus Kotlin and Spring Boot, Javalin, and Quarkus.
It deliberately excludes Kotlin-native frameworks without an established Java
Jena integration path and excludes Spring WebFlux because the first slice uses
blocking Jena and HTTP client operations.

## 2. Constraints and Evidence

- Jena 6 requires Java 21+, and Jena publishes Maven artifacts including ARQ,
  TDB, SHACL, and Fuseki. This makes Java the lowest-friction integration
  language. [Apache Jena releases](https://jena.apache.org/download/index.html)
  and [Maven guidance](https://jena.apache.org/download/maven.html)
- Javalin 7 is a Java/Kotlin framework running on embedded Jetty 12; it has a
  small core artifact and explicit lifecycle hooks. [Javalin documentation](https://javalin.io/documentation)
- Spring Boot supports Kotlin but adds Kotlin-specific build and reflection
  requirements; its current baseline supports Java 17+, which is compatible
  with Jena's Java 21 requirement. [Spring Kotlin support](https://docs.spring.io/spring-boot/reference/features/kotlin.html)
  and [system requirements](https://docs.spring.io/spring-boot/system-requirements.html)
- Quarkus has first-class Kotlin support and JVM/native container paths. Native
  builds use GraalVM/Mandrel and have substantial build-tooling requirements.
  [Quarkus Kotlin](https://quarkus.io/guides/kotlin) and
  [native executable guidance](https://quarkus.io/guides/building-native-image)

No performance number is asserted here: no service exists yet, and published
microbenchmarks would not represent Jena/Fuseki latency, the required container
image lineage, or this workstation. S3-06/S3-07 will measure the selected
baseline using the protocol in section 6.

## 3. Language Assessment

| Criterion | Java | Kotlin | Result |
|---|---:|---:|---|
| Jena API fit and examples | 5 | 4 | Jena is Java-first; Kotlin interoperability is good but adds interop conventions. |
| Null-safety and request-model ergonomics | 3 | 5 | Kotlin reduces nullable DTO boilerplate. |
| Build and toolchain simplicity | 5 | 3 | Java uses one compiler/toolchain; Kotlin adds compiler and annotation/reflection considerations. |
| Native-image risk | 4 | 3 | Kotlin JSON/reflection metadata needs explicit verification. |
| Team maintenance and hiring surface | 5 | 4 | Java has the widest Jena ecosystem. |
| **Weighted result** | **4.5 / 5** | **3.9 / 5** | **Prefer Java for the first semantic-core slice.** |

Kotlin remains viable if the team explicitly values Kotlin as the long-term
service language and accepts native-image compatibility testing as a mandatory
gate. It is not needed to meet the S3 contract.

## 4. Framework Assessment (Java Baseline)

Scores use a 1–5 scale (5 = best fit) and these weights: Jena integration 25%,
startup/image path 15%, tests 20%, maintenance 20%, developer workflow 20%.

| Criterion | Spring Boot | Javalin | Quarkus |
|---|---:|---:|---:|
| Jena/Fuseki integration | 5 | 5 | 4 |
| Startup and runtime-image path | 2 | 4 | 4 |
| Unit/HTTP/integration test support | 5 | 4 | 4 |
| Maintenance, diagnostics, conventions | 5 | 4 | 4 |
| Small-service developer workflow | 3 | 5 | 3 |
| **Weighted total** | **4.1 / 5** | **4.4 / 5** | **3.8 / 5** |

### Interpretation

- **Javalin + Java** is the leading fit for Sprint 3: it keeps the thin,
  explicit HTTP boundary small, uses a Java 21/Jena toolchain directly, and
  does not introduce build-time augmentation or a larger application platform.
  Add explicit dependencies for JSON, validation, logging, and metrics rather
  than relying on a starter bundle.
- **Spring Boot + Java** is the low-risk alternative if the team values its
  richer conventions, test support, configuration binding, and operations
  ecosystem more than a small initial footprint. It has the highest framework
  surface for this narrow service.
- **Quarkus + Java** is attractive only if measured startup/RSS or native-image
  delivery is a real requirement. Jena's ServiceLoader use and the RDF/SHACL
  dependency graph make native compatibility an evidence gate, not an
  assumption. A JVM image remains viable, but then Quarkus' main differentiator
  is reduced.

## 5. Recommendation for S3-05

Approve **Java 21 + Javalin 7.x + Maven** as the Sprint 3 baseline, with
Jena 6.1.0 pinned as already decided. Use a JVM runtime image first; native
compilation is out of scope. The service keeps its own typed domain layer, so a
future framework migration does not alter the API, graph routing, or ontology
contract.

The human decision should also explicitly accept these trade-offs:

- add and maintain the few Javalin-adjacent libraries explicitly;
- use JUnit 5 plus an HTTP test client and Testcontainers/Compose for
  integration tests;
- defer native image work until a measured deployment requirement warrants it.

## 6. Required Empirical Follow-up

After S3-06/S3-07, record these measurements for the selected stack in the
Sprint 3 review packet. Run each cold-start test five times on the same
machine, with a cold image cache noted separately.

| Measurement | Method | Acceptance use |
|---|---|---|
| Startup-to-ready | container start to a healthy `/health/ready` response | verifies Compose dependency timing |
| Image size | `docker image inspect` image size | documents production footprint |
| Idle and validation RSS | container statistics after warmup and one validation request | establishes resource baseline |
| Build and test time | clean container build and unit/integration suite | validates developer workflow |
| Jena behavior | validate fixture, confirm, reject, and rollback against ephemeral Fuseki | proves framework does not weaken semantic guarantees |

These are baseline observations, not release thresholds. Thresholds require a
future workload/SLO decision.
