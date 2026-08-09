#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const target = resolve(process.argv[2] ?? "apps/web/src/styles.css");
const css = await readFile(target, "utf8");
const required = [
  "--dws-canvas", "--dws-surface-subtle", "--dws-border", "--dws-border-strong",
  "--dws-text", "--dws-text-muted", "--dws-primary", "--dws-control-height",
  "--dws-sidebar-width", ":focus-visible", "prefers-reduced-motion",
];
const missing = required.filter((token) => !css.includes(token));
const warnings = [];
if (!/font-size:\s*13px/i.test(css)) warnings.push("No explicit 13px base/control text found.");
if (!/(height|min-height):\s*(var\(--dws-control-height\)|32px)/i.test(css)) warnings.push("No 32px standard control height found.");
if (/backdrop-filter|filter:\s*blur/i.test(css)) warnings.push("Glass/blur effect found; remove it for this workspace style.");
if (/border-radius:\s*(1[6-9]|[2-9]\d)px/i.test(css)) warnings.push("Large non-pill radius found; verify it is intentional.");
if (/box-shadow:[^;]*(0\s+)?(1[2-9]|[2-9]\d)px[^;]*(0\s+)?(2[4-9]|[3-9]\d)px/i.test(css)) warnings.push("Heavy card shadow found; prefer border-first separation.");

for (const warning of warnings) console.warn(`WARN: ${warning}`);
if (missing.length) {
  console.error(`FAIL: ${target} is missing: ${missing.join(", ")}`);
  process.exitCode = 1;
} else {
  console.log(`PASS: ${target} contains the required data-workspace theme contract.`);
}
