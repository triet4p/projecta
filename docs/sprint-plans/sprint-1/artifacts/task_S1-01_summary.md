# Task Summary: S1-01 — Fix the Slice Boundary

**Sprint:** Sprint 1 — Ontology Kernel
**Task:** S1-01 — Fix the Slice Boundary

## Summary of Work

Defined the precise boundary of the Quick Note use case as the foundation for Sprint 1's ontology kernel work. The document specifies the standard use case with actor (BrSE), trigger, preconditions, main flow, and postconditions. It includes a concrete positive example — a realistic multi-type capture scenario from an "Ecommerce Checkout Redesign" sprint review meeting, demonstrating Requirement, Risk, Decision, Task, Question, and Assumption capture in a single note. Four counterexamples clarify what Quick Note is NOT: meeting transcripts, direct Jira task creation, AI-generated summaries without human input, and free-form personal notes without project scope. Ten non-goals are explicitly listed with rationale and target sprint assignments. The document also identifies the minimum ontology kernel terms that Sprint 1 must define to support this use case.

## Files Modified

- [docs/use-cases/quick-note.md](../../../../docs/use-cases/quick-note.md) — New file: authoritative Quick Note use case definition with positive example, counterexamples, non-goals, and ontology kernel requirements.

## Testing

- **Test Type:** Documentation review (no automated test — this is a specification artifact).
- **Validation Performed:**
  - Cross-referenced against [Project Overview](../../../../docs/initialization/01-Project-Overview.md) §6.1 (Quick Note and knowledge capture) and §7 (architectural principles).
  - Cross-referenced against [Project Scope](../../../../docs/initialization/02-Project-Scope.md) §2.3 (Quick Note workflow), §3 (out of scope), and §5 (delivery scope strategy).
  - Cross-referenced against [Ontology Design](../../../../docs/initialization/05-Ontology-Design.md) §3.5 (Communication Ontology: Note, NoteItem) and §8 (named graph model).
  - Verified the use case covers all entity types listed in the project overview: Requirement, Decision, Question, Task, Risk, Assumption, Constraint, Progress Update, Research Need.
  - Verified the counterexamples address the four main boundary risks: transcript dependency, bypassing semantic core, AI-without-human, and missing project scope.
- **Status:** Awaiting human review (see acceptance criteria in the document).

## Additional Notes

- This is a pure documentation task. The acceptance criteria include a human review gate — the use case boundary must be confirmed before S1-02 (competency questions) proceeds.
- The positive example ("Ecommerce Checkout Redesign") should be reused as the demo project for the TriG fixture in S1-10 and competency queries in S1-11.
- The non-goals table explicitly defers LLM extraction (S2+), entity linking (S3+), and connector integration (S3+) to keep Sprint 1 focused on the ontology kernel.
