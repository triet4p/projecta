# Design language

## Contents

- Visual character
- Theme tokens
- Typography
- Geometry and density
- Interaction states
- Accessibility
- Anti-patterns

## Visual character

Build a quiet professional workspace, not a marketing page. The visual signature is compact controls, restrained color, crisp borders, nested work surfaces, and strong information hierarchy. Dense does not mean cramped: keep predictable 4px-grid spacing and align every control to shared rows and columns.

## Theme tokens

Use semantic roles. The exact reusable implementation is in `../assets/workspace-theme.css`.

### Light

| Role | Value | Use |
|---|---:|---|
| Canvas | `#FFFFFF` | Main content background |
| Subtle surface | `#F7F7F7` | Sidebar, toolbar, grouped controls |
| Raised surface | `#FFFFFF` | Cards, menus, dialogs |
| Border | `#EBEBEB` | Normal separation |
| Border strong | `#CBCBCB` | Inputs and interactive outlines |
| Text | `#161616` | Primary text |
| Text muted | `#6F6F6F` | Metadata, placeholders |
| Primary | `#2272B4` | Main actions, links, selected control |
| Primary hover | `#0E538B` | Hover |
| Primary pressed | `#04355D` | Pressed/active |
| Primary soft | `rgba(34,114,180,.08)` | Hover/selected background |
| Danger | `#C82D4C` | Destructive actions and errors |
| Success | `#277C43` | Positive state |
| Warning | `#BE501E` | Warning state |

### Dark

These values were measured from the authenticated workspace in dark mode and normalized into semantic roles.

| Role | Value | Use |
|---|---:|---|
| Canvas | `#11171C` | Main content and editor background |
| Navigation surface | `#1F272D` | Top bar and sidebar |
| Raised surface | `#182027` | Cards, menus, dialog bodies |
| Hover surface | `#26323A` | Hover and active navigation |
| Border | `#252F36` | Quiet separation |
| Border strong | `#37444F` | Inputs, buttons, split panes |
| Text | `#E8ECF0` | Primary text |
| Text muted | `#92A4B3` | Secondary text and icons |
| Primary | `#4299E0` | Main actions and links |
| Primary hover | `#69B4EE` | Hover |
| Primary pressed | `#8ACAFF` | Pressed/focus emphasis |
| Primary soft | `rgba(66,153,224,.12)` | Selected background |
| Creation soft | `rgba(255,73,73,.08)` | Optional “New” affordance |
| Danger | `#FF6B86` | Errors/destructive action |
| Success | `#70C98F` | Positive state |
| Warning | `#E7A65A` | Warning state |

Do not use light-theme primary text (`#161616`) directly on dark surfaces. Primary dark buttons use `#4299E0` with dark label text `#11171C` for contrast.

## Typography

Use the system stack:

```css
-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial,
"Noto Sans", sans-serif
```

| Style | Size / line | Weight | Use |
|---|---|---:|---|
| Page title | `22px / 28px` | 600 | One per screen |
| Section title | `18px / 24px` | 600 | Major regions |
| Subsection | `15px / 20px` | 600 | Cards and grouped forms |
| Body/control | `13px / 18px` | 400 | Default UI |
| Emphasized body | `13px / 18px` | 600 | Labels and table headers |
| Metadata | `12px / 16px` | 400 | Timestamps, helper text |

Avoid uppercase except tiny category labels. Do not use letter spacing on ordinary navigation or headings. Truncate long one-line values with ellipsis and expose the full value through a title, tooltip, or detail view.

## Geometry and density

- Base grid: `4px`.
- Spacing: `4, 8, 12, 16, 24, 32px`.
- Top bar: `48px` high with `8px` padding and `8px` gap.
- Desktop sidebar: `200px`; navigation row `30–32px`; “New” row `40px`.
- Standard control: `32px`; compact icon control: `28–32px`; touch target must remain at least `32px`, preferably `36px` on narrow screens.
- Table header: about `36px`; table row `32–36px`; cell horizontal padding `8px`.
- Main content: `24–32px` page padding on wide screens; `16px` on narrow screens.
- Control radius: `4px`; card/panel radius: `8px`; large dialog: at most `12px`.
- Card shadow: none by default. If a floating menu needs elevation, use `0 8px 24px rgba(0,0,0,.18)` in dark or `.12` in light.

## Interaction states

- Hover: change background by one surface step or use an 8% primary tint. Do not move or scale controls.
- Selected navigation: use a tinted background plus stronger text/icon color. Add `aria-current="page"`.
- Pressed: use the pressed primary color or a 16% tint.
- Focus-visible: `2px` solid primary/focus color with `2px` offset. Never remove focus without replacement.
- Disabled: keep content readable; use muted foreground and subtle background. Cursor may be `not-allowed`.
- Loading: preserve layout geometry with skeleton rows or a compact progress indicator.
- Error: show a concise message near the failing region, not only a toast.
- Destructive: require text plus icon where ambiguity is possible.

## Accessibility

- Target WCAG 2.2 AA contrast.
- Use real `button`, `a`, `input`, `table`, `nav`, `main`, and heading elements before ARIA simulation.
- Every field needs a visible label; helper/error text must be programmatically associated.
- Make icon-only buttons discoverable with `aria-label` and tooltip.
- Preserve logical tab order. Keep scroll containers focused only when keyboard scrolling is necessary.
- Announce async errors assertively and success/loading politely.
- Respect `prefers-reduced-motion`; transitions should be 100–160ms and opacity/color based.

## Anti-patterns

- Huge hero headings inside an operational app.
- More than one saturated primary color in the same toolbar.
- 16–24px radii on every object.
- Heavy shadows around ordinary cards.
- Gradient backgrounds, glass blur, glow, bounce, or scale-on-hover.
- Cards used where a simple bordered row or section would communicate hierarchy better.
- Text smaller than 12px to force density.
- A desktop sidebar squeezed into mobile instead of collapsed or replaced.
