# Visual audit

## Source and scope

Observed on 2026-08-09 in an authenticated Databricks Free Edition workspace using a 902×552 CSS-pixel viewport at 1.5 device pixel ratio. Reviewed Home, Workspace explorer, Catalog explorer, Jobs & Pipelines, SQL Editor landing, Data Ingestion, and the global New menu. No authenticated URL, account identifier, email, or screenshot containing personal data is stored in this skill.

This is an implementation observation, not permission to copy trademarks or proprietary assets.

## Measured constants

| Element | Measurement |
|---|---:|
| Top navigation | `48px` height, `8px` padding/gap |
| Expanded sidebar | `200px` width |
| Main UI text | `13px / 18px`, weight 400 |
| Page heading | `22px / 28px`, weight 600 |
| Section heading | `18px / 24px`, weight 600 |
| Standard button | `32px` height, `4px 12px` padding, 4px radius |
| Icon button | `32×32px` |
| Sidebar New action | `176×40px`, 8px radius |
| Sidebar section header | `12px / 16px` |
| Table header | about `36px`, 13px weight 700 |
| Table row | about `33px` |
| Table cell padding | `8px` |
| Card/panel radius | `8px` |
| Standard card padding | `8px 16px` to `16px` |

## Observed dark surfaces

- Canvas: `rgb(17,23,28)` / `#11171C`.
- Top and side navigation: `rgb(31,39,45)` / `#1F272D`.
- Strong border/input outline: `rgb(55,68,79)` / `#37444F`.
- Primary text: `rgb(232,236,240)` / `#E8ECF0`.
- Secondary text/icon: `rgb(146,164,179)` / `#92A4B3`.
- Primary action/link: `rgb(66,153,224)` / `#4299E0`.
- New-action tint: `rgba(255,73,73,.08)`.

## Composition observations

- Home uses a large whitespace field with five compact metric cards and a simple section heading; cards do not float dramatically.
- Workspace uses a tree region above the main file table, a title/action toolbar, then search and filter controls.
- Catalog uses a split tree/detail layout, compact action buttons, pill-like filters, and a simple list with icon tiles.
- Jobs uses small creation cards, filter chips, a single Create button, and a dense list/table below.
- SQL Editor keeps the global shell but introduces a thin local rail and a tab strip; empty state is centered in the editor canvas.
- Data Ingestion uses a title, one search/select control, grouped resource cards, then connector tiles.
- The New menu is a tall overlay aligned to the sidebar edge, with 32px-ish rows, muted 16px line icons, and no decorative imagery.

## Fidelity test

The result is faithful when it feels immediately operable at a glance: the shell is stable, hierarchy comes from alignment and surface steps, actions are compact, and the content—not decoration—dominates the screen.
