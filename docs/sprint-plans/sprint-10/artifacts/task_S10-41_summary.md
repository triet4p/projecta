# Task Summary: S10-41 — Preserve candidate and assertion separation

Connector-generated candidate triples retain source/provenance derivation and
use the connector generator marker; they do not write asserted or inferred
facts. The change reuses released semantics and adds no ontology vocabulary.

Testing: `QuickNoteCaptureServiceTest` candidate separation regression passed.
