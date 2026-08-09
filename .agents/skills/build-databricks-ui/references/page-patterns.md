# Page patterns

## Contents

- Application shell
- Overview
- Explorer and tables
- Editor
- Forms and settings
- Review queues
- States
- Responsive rules

## Application shell

Use a three-region shell: 48px top bar, 200px side navigation, and a scrollable main surface. Keep global search centered or prominent in the top bar. Put workspace/account utilities at the right. Let only the main region and long navigation lists scroll; avoid nested full-page scrollbars.

Sidebar order:

1. Product mark/name.
2. One prominent “New” action.
3. Primary destinations with 16–18px icons.
4. Muted section labels at 12px/16px.
5. Secondary destinations.

Selected items use a filled soft background, not a left-border-only indicator.

## Overview

Operational overview pages should start with a 22px title and an optional compact action on the same row. Follow with a grid of summary cards or next-step cards. Cards use 1px borders, 8px radius, 16px padding, and little or no shadow. Keep descriptions to one or two lines.

Do not use a marketing hero. A short contextual sentence under the title is enough.

## Explorer and tables

Use this vertical order:

1. Breadcrumb or object hierarchy.
2. Title and right-aligned actions.
3. Search/filter toolbar using 32px controls.
4. Tabs or segmented filter pills.
5. Table/list body.

Tables use 13px text, 36px headers, 32–36px rows, and 8px cell padding. Make the primary name column widest. Right-align numeric values. Keep metadata muted. Use a row hover surface, not a floating card per row. Sticky headers are appropriate inside long bounded lists.

For split explorers, use a 260–320px tree pane and a flexible detail pane separated by a 1px border. Each pane owns its scroll.

## Editor

An editor page has:

- A compact tab strip immediately below the global header.
- A narrow local tool rail when multiple editor contexts exist.
- A flexible working canvas.
- Optional resizable inspector/result panes with 1px separators.

Do not wrap the editor in a decorative card. Keep editor background continuous with the canvas. Toolbars remain 32–36px high.

## Forms and settings

Use one logical group per bordered section. Group title is 15–18px semibold; helper text is 12–13px muted. Standard fields are 32–36px high with 4px radius and visible labels. Use a two-column grid only when fields are short and related; collapse to one column below 760px.

Place the primary submit action first in visual prominence, not necessarily first in DOM order. Keep destructive settings in a separate section. Never store or echo credentials in browser-visible debug output.

## Review queues

Use a list/detail split when users inspect many candidates. The list displays type, title, evidence summary, and status. The detail view puts evidence before irreversible decisions. Confirmation is primary; rejection is danger-secondary. Show provenance and timestamps as muted metadata, not as visual decoration.

## States

- Loading: skeleton rows that match final geometry; avoid a full-screen spinner after shell load.
- Empty: centered within the content region, with a 15–18px title, one explanatory sentence, and at most one action.
- Error: inline bordered status surface with retry; retain valid surrounding content.
- Success: brief inline confirmation or toast plus durable updated state.
- Offline/unavailable: show the affected dependency and what remains usable.
- Disabled: include a visible reason when users may not know why.

## Responsive rules

- At `<= 900px`, collapse the 200px sidebar to a 48px icon rail if icons are unambiguous; otherwise use a menu/drawer.
- At `<= 760px`, stack two-column forms and split explorers.
- At `<= 520px`, hide nonessential table columns and provide a row detail view; do not horizontally squeeze six columns.
- Keep page titles, control heights, and minimum 12px text unchanged. Reduce outer padding before reducing typography.
- Prevent page-level horizontal overflow. A data table may own horizontal scrolling inside a labeled region.
