# S12 relation trigger contract v1

The next server-owned relation-evidence candidate must receive a
predicate-specific `triggerQuote` in a new versioned relation-evidence
envelope. The released m3.v2 envelope is not mutated; the next execution
package must bind the new envelope explicitly. The candidate materializer
treats the field as required for every allowlisted predicate and fails closed
when it is absent, empty, or outside the selected clause/sentence.

This is an offline contract decision. It does not authorize a provider call or
reopen S12-f-09.
