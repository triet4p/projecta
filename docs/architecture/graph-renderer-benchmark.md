# Web Graph Renderer Benchmark — Sprint 8

**Status:** `PROPOSAL_ONLY` — renderer choice pending S8-11 approval
**Task:** S8-08
**Benchmark date:** 2026-08-09
**Current web stack:** React 19.1.1, TypeScript 5.9.2, Vite 7.1.5; no graph
renderer dependency is currently installed.

## Decision summary

Select **`@xyflow/react` (React Flow 12)** as the Sprint 8 Graph screen
renderer candidate. It fits the existing React/TypeScript SPA, exposes DOM/SVG
nodes and edges with built-in keyboard/screen-reader affordances, supports
controlled incremental node/edge state, and allows custom semantic node/edge
components. It still requires the mandatory accessible companion table from
S8-07/S8-48; the renderer is not the only navigation surface.

This is an implementation choice proposal, not permission to install a
dependency before G1. Layout selection remains a separate bounded concern: the
first implementation should use a deterministic layout for the finite
projection and add an external layout engine only if S8-49 performance
evidence requires it.

## Candidates and evidence

Versions and package metadata were read from the npm registry on 2026-08-09:

| Candidate | Registry version | License | Registry unpacked size | Rendering model |
| --- | ---: | --- | ---: | --- |
| `@xyflow/react` | 12.11.2 | MIT | 1,208,222 bytes | React/DOM/SVG |
| `cytoscape` | 3.34.0 | MIT | 5,696,647 bytes | Canvas |
| `sigma` + `graphology` | 3.0.3 + 0.26.0 | MIT | 970,733 + 2,729,833 bytes | WebGL + graphology model |

The unpacked sizes are registry package sizes, not final Vite bundle sizes;
S8-49 must measure the production bundle and runtime behavior with the actual
projection fixture before release.

## Criteria matrix

| Criterion | `@xyflow/react` | Cytoscape.js | Sigma.js + Graphology |
| --- | --- | --- | --- |
| React readiness | Native React component and TypeScript types; controlled `nodes`/`edges` props fit the current SPA. | Core is framework-neutral; React integration needs an adapter/wrapper and imperative lifecycle management. | React demo exists, but the core renderer remains imperative and WebGL-oriented; React state bridge is application-owned. |
| Accessibility | Strongest fit: built-in focusable nodes/edges, Tab/Enter/Space/arrow-key behavior, ARIA roles/descriptions, and live guidance. | Canvas rendering does not provide equivalent semantic DOM nodes; accessibility must be supplied by the companion table and custom controls. | WebGL rendering is not a semantic DOM graph; accessibility must be supplied by the companion table and separate focus model. |
| Directed edges | SVG edge paths and configurable edge markers support directed semantic relations. | Edge arrow types and styling/extensions are mature. | Possible through renderer/edge programs, but more custom work is required for semantic arrows and accessible labels. |
| Incremental updates | Controlled state, `applyNodeChanges`/`applyEdgeChanges`, hooks, and instance APIs support bounded expansion and selection updates. | Mutable graph model, JSON serialization, events, filtering, and layout extensions support updates. | Graphology is mutable and Sigma reads it, but update/render coordination and higher-level selection/expansion stay application-owned. |
| Bounded expansion | Natural mapping: replace/append finite React arrays and retain projection revision/handles in application state. | Natural graph subset operations, but the mutable model needs strict adapter guards to prevent accidental broad traversal. | Graphology adjacency is capable; application must prevent unrestricted traversal and coordinate layout after expansion. |
| Layout | External layout engines are documented options; renderer itself does not own layout. | Many first-party/officially linked layouts and extensions; broad choice increases bundle/behavior surface. | Layout packages are separate and hierarchy support is less turnkey; more custom integration. |
| Testability | DOM/React Testing Library can assert labels, focus, ARIA, node/edge selection, and table parity; layout can be tested separately. | Headless Node testing and browser tests are strong, but canvas semantics need pixel/event or adapter tests. | Renderer behavior is more visual/WebGL-oriented; semantic assertions belong outside the renderer. |
| Performance fit | Suitable for Sprint 8 bounded graphs; official docs warn that large controlled updates need memoization and selective rendering. | Strong graph analysis/performance story and no external core dependencies; 5.7 MB unpacked before adapters/extensions. | Best candidate for thousands of nodes/WebGL, but Sprint 8 deliberately uses finite small projections and values accessibility/semantic DOM more. |
| License/operational risk | MIT; package is maintained by xyflow; commercial attribution/support expectations must be reviewed before release. | MIT core and first-party extensions; mature project with no external core dependencies. | MIT; maintained open source, but more low-level renderer integration. |
| Overall fit | **Recommended**: best match for React, accessibility, typed domain nodes, and bounded interaction. | Viable fallback if S8-49 proves React Flow insufficient on measured graph size. | Not selected for S8; reserve for a measured large-graph requirement. |

## Recommended implementation constraints

If G1 approves the choice, S8-42 should use React Flow as a read-only
projection renderer with:

- controlled `nodes`/`edges` derived from `s8.graph.v1` DTOs;
- custom node and edge components that show semantic labels and state text;
- built-in keyboard focus and ARIA configuration enabled for nodes and edges;
- `onlyRenderVisibleElements` and explicit viewport limits where appropriate;
- edge markers for direction, supplemented by text/legend so direction is not
  encoded by color alone;
- no connect/create/delete behavior in this read-only graph slice;
- node selection opening the typed detail panel, not exposing a raw handle;
- the same DTO projected to the accessible companion table;
- memoized custom components and bounded state updates;
- renderer errors mapped to the S8-03 finite problem contract.

## Performance benchmark to run during implementation

The selected renderer is not considered production-ready until S8-49 measures
the following with representative generated fixtures:

| Fixture | Required measurement |
| --- | --- |
| 25 nodes / 50 edges | Initial render, keyboard traversal, selection/detail latency. |
| 100 nodes / 200 edges | Initial render and filter/viewport latency under the proposed limit. |
| 150 nodes / 300 edges | Oversized/continuation behavior and no silent truncation. |
| 50-node one-hop expansion | Append/update latency, repeated expansion, stale revision handling. |
| Cyclic and multi-edge relations | Layout completion, directed marker truthfulness, cancellation. |
| Narrow viewport | Focus visibility, overflow, companion table parity, responsive panel behavior. |

Record production bundle size, cold render, update latency, memory/console
errors, keyboard traversal, screen-reader labels, and test flakiness. The
benchmark must not use a graph larger than the bounded API contract to justify
removing the finite limits.

## Sources

- React Flow accessibility: https://reactflow.dev/learn/advanced-use/accessibility
- React Flow layouting: https://reactflow.dev/learn/layouting/layouting
- React Flow controlled interactivity: https://reactflow.dev/learn/concepts/adding-interactivity
- React Flow performance: https://reactflow.dev/learn/advanced-use/performance
- React Flow API and markers: https://reactflow.dev/api-reference/react-flow
- React Flow repository/license: https://github.com/xyflow/xyflow
- Cytoscape.js factsheet and canvas/layout support: https://js.cytoscape.org/
- Sigma.js renderer model: https://www.sigmajs.org/docs/advanced/renderers/
- Sigma.js repository/license: https://github.com/jacomyal/sigma.js

## Review status

The renderer selection is the S8-08 proposal input to S8-10. No dependency is
installed and no UI code is changed by this task. G1 must approve the choice;
S8-49 must then provide measured acceptance evidence.
