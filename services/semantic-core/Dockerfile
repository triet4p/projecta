# syntax=docker/dockerfile:1

FROM maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e AS development
WORKDIR /workspace

COPY pom.xml ./
RUN mvn --batch-mode dependency:go-offline

COPY src ./src
CMD ["mvn", "--batch-mode", "test"]

FROM development AS test
RUN mvn --batch-mode verify

FROM development AS build
RUN mvn --batch-mode --offline package -DskipTests

FROM eclipse-temurin:21-jre-jammy@sha256:d63bd8d9b171999cbed8576f2c76e874dd4856791a358536e5c4d407e77edc13 AS runtime
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends wget ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --system semantic && useradd --system --gid semantic --home-dir /app semantic

COPY --from=build --chown=semantic:semantic /workspace/target/classes /app/classes
COPY --from=build --chown=semantic:semantic /workspace/target/lib /app/lib

USER semantic
EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=3s --retries=12 CMD wget -q --spider http://127.0.0.1:8080/health/ready
ENTRYPOINT ["java", "-cp", "/app/classes:/app/lib/*", "org.projecta.semanticcore.SemanticCoreApplication"]
