# BrSE Project Intelligence Platform — Documentation Index

Bộ tài liệu kiến trúc ban đầu cho một ontology-driven, connector-agnostic project intelligence platform dành cho BrSE.

## Documents

1. [Project Overview](01-Project-Overview.md)
2. [Project Scope](02-Project-Scope.md)
3. [Project Architecture Overview](03-Project-Architecture-Overview.md)
4. [Memory Layer](04-Memory-Layer.md)
5. [Ontology Design](05-Ontology-Design.md)
6. [Tech Stack](06-Tech-Stack.md)
7. [Learning Path Index](07-Learning-Path-Index.md)
8. [Deployment Choice](08-Deployment-Choice.md)

## Core Principle

Không thành phần nào sau đây được coi là “MVP optional”:

- Ontology.
- RDF knowledge graph.
- Candidate/asserted/inferred separation.
- SHACL validation.
- Provenance.
- Connector abstraction.
- Project/tenant isolation.
- Semantic lifecycle.
- Policy-controlled action.
- Operational persistence.

Việc triển khai tăng dần chỉ áp dụng cho connector, permission, external integration và deployment scale.
