package org.projecta.semanticcore;

/** Contract-safe problem response; never exposes RDF graph or Fuseki implementation details. */
public record ApiProblem(String type, String title, int status, String code, String detail, String requestId) {}
