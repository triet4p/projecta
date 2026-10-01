# Sprint 14 User Journeys and Acceptance Scenarios

**Status:** implementation input for S14-02–06 and the selected user trials in S14-12–13. This is not a claim that the current UI passes these scenarios or that the owner trial has occurred.

Requirement §3 is the priority: a user should understand the current screen, the next useful action, and how a source-backed task reaches a reviewable result. Requirement §1 says not to add standalone capabilities just to fill screens. The journeys below reuse existing Projects, Project Overview, Notes, Review Queue, and Graph contracts. They keep source capture, candidate review, and graph materialization distinct.

The current-product observations below come from reading the linked application and API contracts. No browser run or direct user trial was performed for this documentation task. “Acceptance target” is the observable behavior later tasks must deliver; it is not a statement that the current surface already delivers it.

## Shared entry, navigation, and state contract

| Screen or shell state | Purpose and primary action | Transition and observable result | Failure, stale, and return path |
| --- | --- | --- | --- |
| Session shell | Establish whether the user is signed in; keep sign-out available. | An authenticated user enters the app shell; the current session state is visible across workspace screens. | While checking, show a loading state. If unauthenticated, show the sign-in gate rather than project data. Sign-out returns to the sign-in entry. Session status is not the active-project label. |
| Projects | Select or change the authorized project, not navigate among project work screens. | Open one listed project; the result is Project Overview with that project’s name/context. | Distinguish a healthy empty catalog from catalog/API failure. Retry a failed catalog. Search with no match gives a clear empty state. Stale selection or failed selection must not restore a prior project or fall back to a default. |
| Project Overview | Orient in the selected project using its counts, freshness, and current collections. | Choose a recent Note to open Notes with that exact source record resolved, a pending candidate to open Review Queue, or a project knowledge item to open Graph. | Keep loading and errors distinct from valid empty collections. A missing or unavailable selected record must stay explicit without substitution and offer a retry/return path. Return to Overview through project navigation; use the explicit Change project action to leave the current project. |
| Notes | Create or inspect source Notes. Make the three existing paths understandable: Note Composer, Assisted import, and exact-span capture. | A saved/committed Note is browsable with source/evidence detail; exact-span capture produces a candidate entry point to Review Queue. | Keep draft, committed Note, candidate, and review receipt states distinct. Show operation errors in place and do not imply persistence or approval on a failed request. |
| Review Queue | Decide about a candidate only after showing its source/evidence and current review state. | Select a candidate to open its source-first detail; validate, then record an explicit supported outcome. | Stale queue/source, missing source, unavailable evidence, validation failure, and operation failure must be visible and must not be presented as an approval. Refresh or return to the queue/workspace without an implicit decision. |
| Graph | Read and investigate a finite project projection; it is not a capture or review form. | Filter, select a node, inspect type/state/provenance/evidence/freshness, and optionally expand one hop. | Explain empty-filter results; expose stale projection and refresh; show API failure instead of an empty graph. Close detail or return to Overview through project navigation. |

Project scope is server-owned. Changing projects is explicit; no project-scoped screen may silently retain the previous project’s content while another project is loading. The UI uses returned labels and opaque handles, not user-entered internal IDs. The manual Quick Note endpoint is top-level rather than project-path-addressed; its server request context must still resolve the same active project. This follows the [project-context contract](../../architecture/project-context-selection.md).

## Journey 1 — Capture one exact source span and review it

**User goal:** record a requirement from a source note, then make an explicit source-bound review decision without an automatic model call or hidden graph write.

| Step | Screen and purpose | User action and next screen | Observable result and state | Failure and return path |
| --- | --- | --- | --- | --- |
| 1 | **Projects** — choose the workspace. | Open a listed, authorized project. | Project Overview and the workspace header identify the same active project. | Catalog loading, healthy-empty, API error, and selection error are distinct. Retry the catalog or remain at Projects; never use a default project. |
| 2 | **Project Overview** — orient and enter source work. | Open Notes from project navigation or the New Note action. | Notes opens under the same active-project context. | If the project is stale/unavailable, show recovery rather than old Notes data. Change project returns explicitly to Projects. |
| 3 | **Notes** — choose the capture method that matches the source. | Choose **Capture exact spans** for a specific passage that must remain anchored; do not confuse it with composing typed items or asking Assisted import for editable proposals. | The exact-span action opens the existing Manual Quick Note capture form, whose purpose and next action are clear. | If the Notes screen is still ambiguous about the three methods, this scenario fails even if the capture endpoint works. Back to Notes is available before submission. |
| 4 | **Manual Quick Note capture** — bind a human-selected passage to its source. | Enter the disposable test sentence “The project owner will review the export before it is shared.” Select the full sentence, choose `requirement`, and add the selected span. | The selected quote, type, and server-relevant range are visible; no user-entered offset is needed. The span is ordered and non-overlapping. | No selection, empty span, overlap, or invalid selection produces an actionable error and no captured candidate. Editing the source clears previously selected segments; reselect before capture. A capture API error stays on this screen and does not produce a success result. |
| 5 | **Capture result** — confirm that a candidate exists and continue to review. | Select the candidate’s **Open review queue** action. | The selected candidate handle reaches Review Queue, which selects that exact candidate and loads its matching source detail before decisions. | If the handle is no longer in the pending queue, show an explicit missing state and keep it through refresh; selecting a listed candidate is the recovery action. A failed capture has no candidate action. |
| 6 | **Review Queue** — inspect source before deciding. | Open the matching candidate, inspect source text, source revision, quote/highlight and displayed offsets, then validate. | Candidate, validation, evidence, and receipt states are visibly separate. Validation failure does not offer an approval as if it passed. | Stale queue/source requires refresh before a decision. Missing source or highlight is explicit and blocks an unsupported approval. Operation errors remain visible and leave the item undecided. |
| 7 | **Review outcome** — record the person’s decision. | For this positive scenario, after successful validation choose **Record manual approval**. Rejection or abstention are legitimate alternate outcomes, not failure states. | A durable receipt/outcome is shown. Manual approval/rejection/abstention does not itself create an asserted or inferred graph write; the RM-63 authorization lock remains in force. No local suggestion is requested in this scenario. | A failed receipt write is reported and is not described as recorded. If the user is not ready to decide, leave the item in the queue without implying a decision; use the explicit abstention action only when they intend to abstain. |
| 8 | **Return to work** — continue in the same project. | Use project navigation to return to Notes or Project Overview. | The active project remains identifiable; the recorded review state is not confused with a committed Note or an asserted Graph node. | Returning from an unfinished capture preserves its source and spans in session memory with explicit Continue or Discard actions; it does not imply that the capture was saved. |

### Journey 1 acceptance checks

- In Notes, the exact-span route is visible and explains when to use it; Composer and Assisted import remain available as different choices.
- The test passage is the exact human-selected evidence; a successful capture shows a candidate and an unambiguous next step into Review Queue.
- Review presents the source and its current evidence/revision before the decision; success is an explicit receipt, not a silent state change.
- An accepted, rejected, or abstained manual candidate is not described as already asserted or inferred. No model/provider call is required for this scenario.
- The return, stale, validation-error, and request-error paths leave the active project and recorded decision state understandable.

## Journey 2 — Compose or assist a Note, then inspect its source record

**User goal:** create a usable project Note from typed source items, with optional assistance that never saves or commits on the user’s behalf.

| Step | Screen and purpose | User action and next screen | Observable result and state | Failure and return path |
| --- | --- | --- | --- | --- |
| 1 | **Projects → Project Overview** — enter the selected project. | Select the project, then open Notes. | The same project is named in the workspace while Notes loads. | Use the shared catalog, selection, and stale-context recovery paths above. |
| 2a | **Notes / Note Composer** — author typed source items directly. | Enter a human title, add at least one typed item, choose its type, and enter the source content. | A canonical preview shows the source body that the server will derive offsets from; offsets are not user input. | Empty drafts may be saved while editing, but cannot be committed without an item. A blank title disables save. Errors do not show a saved/committed result. |
| 2b | **Notes / Assisted import** — request editable proposals from pasted text. | Paste the source text and choose **Propose items**. If proposals arrive, edit or remove them in the Composer; if the operation abstains, read the explicit abstention and continue manually in the Composer if useful. | Proposals remain editable and unsaved. The original text is not silently turned into a committed Note. | An abstention is a visible outcome, not a success claim; request failure remains an error. Do not require a model to complete the direct Composer path or this sprint’s manual exact-span trial. |
| 3 | **Notes / Note Composer** — persist the user’s authored draft, then commit deliberately. | Choose **Save draft**, review the returned draft revision/status, then choose **Commit Note** as a separate action. | Only explicit save persists the draft; only explicit commit changes it to committed. After a successful commit, the Notes list can be refreshed and the Note can be opened. | Save/commit errors remain visible and do not advance the displayed state. Keep the current editable content available in place where possible; do not claim commit until the API confirms it. |
| 4 | **Notes / Project Notes** — inspect the committed source record. | Open the committed Note by title. | Detail shows the committed item content/type, source offsets, author/time, and evidence coverage. Close detail to return to the list. | An empty list is distinct from a failed list request. A failed detail read shows an error; refresh or select another Note. |
| 5 | **Project Overview (return)** — resume project work. | Return via project navigation; choose a Recent Note to reopen its exact source detail in Notes. | The project context and Note’s committed status remain clear. This scenario does not assume that committing a Note created a Review Queue decision or a Graph assertion. | If no recent Note is shown, the user can return to Notes from workspace navigation; do not imply that an absent overview item is a source or commit failure. |

### Journey 2 acceptance checks

- The screen states the purpose and consequence of Composer, Assisted import, and exact-span capture before the user chooses.
- Assisted import proposals are editable and require explicit save; abstention and operation failure are legible.
- Save and commit are separate, observable transitions. A committed Note detail exposes its source/evidence coverage and a clear return to the list/workspace.
- A Note commit is not represented as a candidate approval, relation decision, or graph materialization.

## Journey 3 — Follow a project knowledge item into Graph and return

**User goal:** start from a project-level item, inspect its evidence and lifecycle in Graph, then return without changing knowledge.

| Step | Screen and purpose | User action and next screen | Observable result and state | Failure and return path |
| --- | --- | --- | --- | --- |
| 1 | **Projects → Project Overview** — orient to an existing project question or requirement. | Open the project and choose a listed question/requirement from its overview collection. | The link opens Graph in the same project and conveys which overview item the user selected. | The selected handle is resolved within the active project; if its detail is missing or unavailable, show the selected context and recovery instead of silently opening another item. |
| 2 | **Graph** — inspect a finite read-only projection. | If needed, select the relevant domain-type/evidence filters; select the matching node in the canvas or companion table. | Detail identifies the node’s type, verification, provenance, project, evidence count, lifecycle, and freshness. Labels, edges, and status remain understandable in the legend and without relying on color alone. | No matching nodes explains the active filters and offers a way to broaden/clear them. A stale projection offers refresh; an API error is not presented as an empty graph. |
| 3 | **Graph detail → Project Overview** — close the inspection and resume. | Close detail or use project navigation to return to Overview. | No graph write or review decision occurred from inspection; active project context is unchanged. | If detail/expansion fails or freshness changes, keep the error/stale state visible and allow refresh/close/return. |

### Journey 3 acceptance checks

- An Overview item link lands in a useful Graph context; no raw identifier is required from the user.
- Graph filters and detail expose type, relationship/state, provenance/evidence, and freshness. Canvas and companion table provide equivalent access to a node.
- Light and dark theme states, focus/selection, edge direction, node labels, and legend are distinguishable without color being the only signal.
- Graph navigation is observational. Candidate review remains in Review Queue and no hidden write occurs.

## Cross-project and session acceptance scenario

Run this as a common precondition and return check for Journeys 1–3:

1. Sign in and confirm that the session state is visible before entering project work.
2. Select project A, note its visible name, then traverse one selected journey.
3. Choose **Change project**. Projects is a distinct project-selection surface; project A’s content must not remain presented as project B loads.
4. Select project B from the returned catalog and verify the workspace header and data are for B only. If there is no second authorized project, record the isolation branch as not exercisable rather than inventing a project.
5. If selection becomes stale or the catalog/API fails, show explicit recovery and no default/last-project fallback. A healthy empty catalog is not an infrastructure failure.
6. Sign out remains available from the session shell and returns to the sign-in gate; it is not a project-navigation action.

## Acceptance mapping for implementation and trial

| Task | Journey evidence to deliver | Observable pass condition |
| --- | --- | --- |
| S14-02 — Project navigation | Shared entry and cross-project scenario; all three journeys. | Project choice/change is distinct from workspace navigation; the active project is visible; changing selection never leaks the previous project or falls back silently. |
| S14-03 — Session chrome | Shared session-shell states; cross-project scenario. | Signed-in/session status and sign-out are discoverable on workspace screens; sign-in/loading/unavailable states do not masquerade as project states. |
| S14-04 — Notes capture path | Journeys 1 and 2. | Notes explains the three existing capture methods, makes exact-span capture discoverable, and shows a successful capture’s next review action; import remains proposal-only until explicit save. |
| S14-05 — Cross-screen journeys | Journeys 1–3 and all return/error paths. | Entry, selected-item context, next action, result, stale/error/empty states, and return path remain clear across screens; review remains source-bound and does not hide graph writes. |
| S14-06 — Graph legibility | Journey 3. | Real project labels, directed relationships, lifecycle/verification/provenance, evidence, freshness, and legend are legible in relevant themes and interactive states without color-only encoding. |
| S14-12 — Clean-install and transfer verification | Run Journeys 1–3 on the approved clean-install path without Docker. Then perform manual transfer only against the separately approved S14-09 export/import contract. | The actual no-Docker install/start path opens the local UI and supports the selected journey; the transfer result preserves exactly the approved data/evidence scope and remains usable on installation B. Do not infer export format, merge policy, or portability before S14-09–11 approve them. |
| S14-13 — Direct owner/target-user trial | Give the owner/target user concise steps for Journeys 1–3 and the approved S14-12 transfer trial. | The person personally installs/starts, navigates, captures/reviews, inspects Graph, and tries the approved transfer. Record their observations and explicit pass/fail; agent execution, tests, and screenshots are not a substitute. This is not an external business-quality study or release approval. |

## Cross-screen implementation contracts and remaining evidence

Source inspection describes implementation contracts, not runtime proof. S14-05 must exercise connected UI journeys against the real backend; focused fixture tests are supplemental, and the separately assigned owner trial remains a distinct evidence gate.

| Existing contract observed | Journey implication for later implementation |
| --- | --- |
| Notes exposes Note Composer, Assisted import, and a separate **Capture exact spans** action. Capture requires at least one selected span; the result offers candidate buttons. | S14-04 must explain when to choose each path and make the exact-span action part of the on-screen workflow, not an obscure shortcut. |
| Notes routes an exact-span capture with the server-issued project-scoped opaque handle used by Review Queue; the Core capture ID is not used as a queue handle. | The queue selects that exact candidate and waits for source detail; missing or unavailable candidates remain explicit, and review decisions stay source-bound. |
| Project Overview preserves clicked item context for Graph and Review Queue, and recent-Note links pass the exact handle into Notes. Its projection emits Core-compatible, route-specific project-scoped `node-h-`, `note-h-`, and `candidate-h-` handles from the exact resource identity; Notes resolves the selected Note to source detail or reports missing/unavailable without substitution and provides retry/return, while Graph resolves its selected item in the active project and offers an explicit return to Project Overview. | S14-05 keeps selected records meaningful on arrival and makes return/error states clear. |
| ReviewScreen shows source text/highlights and source/candidate/receipt state; route-selected review actions wait for matching source detail, manual approval is gated by validation, and the explicit assertion outcome remains non-materializing. | Keep source-first review and the accepted RM-63 no-hidden-write boundary visible through UI changes. |
| Graph is a filtered finite projection with node detail and a companion table; stale state has a refresh message. | S14-06 should improve readability on this real projection, not replace Graph with a disconnected screen or treat candidates as assertions. |
| The exact-capture form previously discarded its component-local state on return. Its unfinished source and selection now remain in memory while the project is active; Notes offers Continue capture or explicit discard, and switching projects clears the unsaved draft. | S14-05 exposes this unsaved boundary without signaling that an unsubmitted capture was saved. |

## Evidence basis and scope locks

- Owner requirements: [Sprint 14 requirements §§1–3](../sprint-14-requirements.md); task order and scope: [Sprint 14 plan](../sprint-14.md).
- Navigation and context: [App shell](../../../apps/web/src/shell/App.tsx), [navigation groups](../../../apps/web/src/shell/navigation.ts), [Projects](../../../apps/web/src/screens/ProjectsScreen.tsx), [Project Overview](../../../apps/web/src/screens/ProjectOverviewScreen.tsx), and the [authorized project-context contract](../../architecture/project-context-selection.md).
- Notes and review: [Notes screen](../../../apps/web/src/screens/NotesScreen.tsx), [manual capture form](../../../apps/web/src/screens/CaptureScreen.tsx), [API client](../../../apps/web/src/api/client.ts), and [Review screen](../../../apps/web/src/screens/ReviewScreen.tsx).
- Graph: [Graph screen](../../../apps/web/src/screens/GraphScreen.tsx).
- Evidence-first and materialization boundaries: [Sprint 13 authoring contract](../sprint-13/evidence-first-assisted-authoring.v1.md).

S14-01 does not implement UI, alter ontology/SHACL, enable production materialization, request external/provider execution, define the still-unapproved installation or transfer contracts, perform an owner trial, or authorize release. Those decisions and implementations remain with their ordered Sprint 14 tasks and owner gates.
