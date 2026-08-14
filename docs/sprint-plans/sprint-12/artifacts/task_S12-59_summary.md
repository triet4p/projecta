# S12-59 — Dataset integrity checks

Manifest IDs, content digests, canonical case digests, duplicate IDs,
cross-split content leakage, offsets through metric inputs, and cross-file
scenario references are checked deterministically.

## Testing

Phase E self-tests cover duplicate manifest IDs, digest leakage, tampering and
invalid scenario references.
