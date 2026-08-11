FROM eclipse-temurin:21-jre-jammy

ARG JENA_VERSION=6.2.0
WORKDIR /opt

COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /uvx /bin/

RUN apt-get update && \
    apt-get install -y --no-install-recommends wget ca-certificates && \
    rm -rf /var/lib/apt/lists/*

ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python
ENV UV_PYTHON=3.12
ENV UV_PYTHON_PREFERENCE=only-managed
ENV UV_NO_PROGRESS=1

# Cache the managed Python and pinned validation dependency in the image.
RUN uv python install 3.12 && \
    uv run --with rdflib==7.6.0 python -c "import rdflib"

# Full Jena distro: contains riot, sparql, tdb2.tdbloader, shacl, etc.
RUN wget -q https://dlcdn.apache.org/jena/binaries/apache-jena-${JENA_VERSION}.tar.gz && \
    tar xzf apache-jena-${JENA_VERSION}.tar.gz && \
    mv apache-jena-${JENA_VERSION} jena && \
    rm apache-jena-${JENA_VERSION}.tar.gz

# Fuseki server distro
RUN wget -q https://dlcdn.apache.org/jena/binaries/apache-jena-fuseki-${JENA_VERSION}.tar.gz && \
    tar xzf apache-jena-fuseki-${JENA_VERSION}.tar.gz && \
    mv apache-jena-fuseki-${JENA_VERSION} fuseki && \
    rm apache-jena-fuseki-${JENA_VERSION}.tar.gz

ENV PATH="/opt/jena/bin:/opt/fuseki:${PATH}"
ENV FUSEKI_BASE=/var/lib/fuseki

WORKDIR /opt/fuseki
COPY log4j2.properties /opt/fuseki/log4j2.properties
RUN mkdir -p /var/lib/fuseki
EXPOSE 3030
CMD ["./fuseki-server"]
