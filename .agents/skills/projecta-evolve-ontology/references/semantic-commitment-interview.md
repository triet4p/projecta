# Semantic Commitment Interview

Run this interview before introducing or materially changing a class or property. Record the answers in the human review packet.

This interview complements competency questions:

- Competency questions define what the ontology must answer.
- Semantic commitment questions determine what kinds of entities and relations the ontology must assert to answer correctly.

Do not create a term when its only justification is that a noun or verb appeared in source text.

## Questions for every proposed term

Answer all:

1. What does the term mean in one sentence without using the term itself?
2. Which competency question or governance rule requires it?
3. Give at least two positive examples and two counterexamples.
4. Does an existing Projecta or reused vocabulary term already express the meaning?
5. Is this domain truth, source evidence, candidate knowledge, inferred knowledge, operational state, retrieval metadata, or a UI projection?
6. What changes if the term is not added? Identify the query, validation, inference, or governance gap.
7. Is the meaning stable across projects and connectors, or is it channel/application-specific?
8. What provenance, verification state, project scope, tenant scope, and temporal metadata apply?

If the meaning cannot be defined independently of a UI screen, connector payload, or current workflow implementation, do not put it in the domain ontology without a stronger domain justification.

## Additional questions for a class

Answer all:

1. What kind of real-world or project-domain things are its instances?
2. What makes two observations refer to the same instance? State the identity criterion.
3. Can an instance exist independently, or does it exist only as part of, a role toward, or a relation between other entities?
4. Can the same entity enter or leave this class while retaining its identity?
   - If yes, evaluate a role, phase, state, assignment, membership, or time-qualified relation.
   - If no, explain why membership is essential to the entity's identity.
5. What is the nearest justified superclass already present?
6. Is the proposed term actually:
   - A subclass?
   - An individual or controlled vocabulary value?
   - A state/status?
   - A role?
   - A relationship?
   - An event/activity?
   - A literal value?
7. Are proposed subclasses exhaustive or merely known examples?
8. Are any disjointness claims true in the domain, not just in current data?
9. Which conditions are necessary for membership? Are any truly sufficient?
10. What is the instance lifecycle: creation, effective period, change, supersession, retraction, and deletion?
11. Does a wording or status change create a new instance, a new version, or only a new assertion?
12. Must instances have independent provenance and be referenced by multiple relations?

Do not infer that a class is correct merely because instances may be long-lived. Vocabulary stability and instance lifetime are different concerns.

## Additional questions for an object property

Answer all:

1. State the relation as a plain sentence: “subject relation object.”
2. What are the intended subject and object kinds?
3. Would OWL domain/range entail unintended types for valid data?
4. Is the relation genuinely binary?
   - If it needs its own actor, evidence, status, confidence, validity interval, quantity, or repeated occurrences, evaluate a relation/assertion/activity node.
5. Can the relation change while both endpoint entities retain their identities?
6. Does the relation need `validFrom`, `validTo`, supersession, retraction, or assertion provenance?
7. Is an inverse useful and semantically exact, or only convenient for queries?
8. Are functional, inverse-functional, symmetric, asymmetric, transitive, irreflexive, or other characteristics universally true? Give counterexample attempts.
9. What cardinalities are domain truths, and which are only application validation rules?
10. May it cross project or tenant boundaries? If so, under what explicit policy?
11. Is the relation asserted by a human/external authority or derived by a rule?
12. Could an existing property plus a more specific subproperty express the meaning with less commitment?

Prefer SHACL for closed-world application constraints. Do not use OWL property characteristics to encode what is merely typical.

## Additional questions for a datatype property

Answer all:

1. Why is the value a literal rather than a resource with identity and provenance?
2. What datatype, language, unit, normalization, and precision apply?
3. Is the value immutable, versioned, temporal, or replaceable?
4. Are cardinalities domain truths or SHACL/application constraints?
5. Could multiple sources disagree, and if so where is assertion-level provenance stored?
6. Will consumers need to relate other entities to this value? If yes, evaluate an identity-bearing resource.

## Decision outcomes

Choose and justify exactly one primary outcome:

- Reuse existing term.
- Add class.
- Add subclass.
- Add individual/controlled value.
- Add object property.
- Add datatype property.
- Add relation/assertion/activity node.
- Add SHACL constraint only.
- Add deterministic inference rule only.
- Keep in operational storage.
- Keep in evidence/retrieval/projection data.
- Defer pending human domain decision.

When more than one artifact is needed, state which is the primary domain commitment and which artifacts only validate, derive, or operationalize it.
