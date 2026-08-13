# Production-shaped Keycloak image. The production compose override replaces
# the local image with the CI-built immutable digest.
FROM quay.io/keycloak/keycloak:26.7.0 AS builder

ENV KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=true \
    KC_DB=postgres
RUN /opt/keycloak/bin/kc.sh build

FROM quay.io/keycloak/keycloak:26.7.0
COPY --from=builder /opt/keycloak/ /opt/keycloak/
USER 1000
ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
