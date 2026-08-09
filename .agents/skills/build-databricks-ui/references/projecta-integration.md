# Projecta integration

Projecta uses React 19, TypeScript, Vite, and a small internal component system. Do not introduce a UI framework solely for this visual redesign.

## Current boundaries

- Shell: `apps/web/src/shell/App.tsx`
- Shared primitives: `apps/web/src/ui.tsx`
- Global theme: `apps/web/src/styles.css`
- Screens: `apps/web/src/screens/*.tsx`
- API client and generated contracts: `apps/web/src/api/`

Keep the static SPA behind the same-origin Application API. Do not add direct browser access to Semantic Core, Fuseki, graph IRIs, provider credentials, or trusted project headers.

## Safe application sequence

1. Add the semantic `--dws-*` variables from `assets/workspace-theme.css` to `styles.css`.
2. Restyle existing `.topbar`, `.workspace`, `.sidebar`, `.nav-item`, `.main-content`, `.card`, form, status, and table-like classes before restructuring JSX.
3. Keep the existing navigation labels and state transitions unless the user asks for information-architecture changes.
4. Preserve the skip link, `main` landmark, `aria-current`, live regions, labels, button types, and redaction behavior.
5. Keep generated API files unchanged unless the API contract itself changed.
6. Run from `apps/web`:

   ```text
   npm run format:check
   npm run lint
   npm run typecheck
   npm test
   npm run build
   ```

7. Run the skill contract check against `apps/web/src/styles.css`.

## Projecta mapping

| Existing element | Target pattern |
|---|---|
| `.topbar` | 48px global top navigation |
| `.workspace` | 200px sidebar + flexible main |
| `.sidebar` | Compact grouped navigation |
| `.nav-item` | 32px navigation row with soft selected state |
| `.hero-card` | Convert to compact overview header/next-step panel |
| `.card` | 1px border, 8px radius, little/no shadow |
| `.form-grid` | Dense two-column settings form; stack under 760px |
| `.state-message` | Inline status surface with icon/text semantics |
| `.safe-json` | Editor-like code surface using canvas/border tokens |

The desired change is visual and structural, not a rewrite of workflow logic.
