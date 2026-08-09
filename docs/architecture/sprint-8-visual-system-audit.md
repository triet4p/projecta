# Sprint 8 visual system audit

Audit date: 2026-08-10. Target viewports: 1440×900 desktop and approximately
390×844 narrow viewport. The screen taxonomy follows the
`build-databricks-ui` skill and describes gaps before implementation.

| Screen | Classification | Hierarchy/density gaps | Interaction/responsive/a11y gaps |
| --- | --- | --- | --- |
| Global shell | Shell | Top bar is taller than 48px; sidebar is flat and loose; project context is absent. | Navigation has no grouped sections or responsive rail/drawer; selected state is present but visual focus/overflow are inconsistent. |
| Overview | Overview | Marketing hero, oversized heading, gradient, and floating shadows compete with operational collections. | No selected-project recovery state; collections are not navigable; narrow layout spends too much vertical space on hero copy. |
| Extract/Capture | Editor/form | Controls and cards use large radii, padding, and a one-off teal palette. | Forms need dense 32–36px controls, stable loading/error regions, and stacked narrow layout. |
| Review | Review queue | Candidate list/detail hierarchy is not expressed as a bounded dense queue. | Long labels need truncation and keyboard-visible selection; split view must collapse at narrow widths. |
| Knowledge/Q&A | Explorer/editor | Read-only collections lack consistent toolbar, breadcrumbs, table/list row geometry, and freshness context. | Internal IDs must remain hidden; table overflow needs an owned scroll region. |
| Settings | Configuration form | Two-column form is visually loose and uses oversized controls. | Field labels, disabled/error reasons, and destructive separation need consistent states. |
| Diagnostics | Diagnostics | Health information is card-heavy and not grouped by dependency/state. | Async status should use live regions and preserve readable failure/request-ID evidence. |
| Projects | Explorer/list (new) | No finite catalog screen, search, labeled status/count/activity summary, or explicit empty/error state. | Selection must be card action only; no editable ID input; cards must collapse to one column around 520px. |

## Target tokens and behavior

The implementation uses semantic `--dws-*` light/dark tokens, a 4px base grid,
13px/18px body text, 22px/28px page titles, 48px top bar, approximately 200px
desktop sidebar, 32px controls, 4px control radius, and 8px panel radius.
Borders and surface steps carry hierarchy; color is never the only state cue.

Desktop owns the main scroll region and keeps navigation stable. At narrow
width the sidebar becomes a horizontal/drawer-like navigation region before
text or controls shrink. Skip link, landmarks, visible focus, `aria-current`,
and live status messages remain part of the shell contract.
