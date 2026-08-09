/* global console, process */

import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const snapshotPath = path.join(root, "docs/architecture/application-api.sprint7.openapi.json");
const outputPath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "../src/api/operation-ids.generated.ts",
);
const snapshot = JSON.parse(await readFile(snapshotPath, "utf8"));
const forbiddenFields = [
  "_projecta_http_status",
  "secretReference",
  "X-Projecta-Context-Secret",
  "apiKey",
];
const snapshotText = JSON.stringify(snapshot);
const forbiddenField = forbiddenFields.find((field) => snapshotText.includes(field));
if (forbiddenField) {
  console.error(`Snapshot contains forbidden internal field: ${forbiddenField}`);
  process.exit(1);
}
const operationIds = Object.values(snapshot.paths)
  .flatMap((operations) => Object.values(operations))
  .map((operation) => operation.operationId)
  .filter((value) => typeof value === "string")
  .sort();
const generatedIds = operationIds
  .map((operationId) => `  ${JSON.stringify(operationId)},`)
  .join("\n");
const output = `/** Generated from docs/architecture/application-api.sprint7.openapi.json (Sprint 8 contract). */\nexport const apiContractVersion = ${JSON.stringify(snapshot.info.version)} as const;\nexport const generatedOperationIds = [\n${generatedIds}\n] as const;\n`;

if (process.argv.includes("--check")) {
  const current = await readFile(outputPath, "utf8").catch(() => "");
  if (current !== output) {
    console.error("Generated Application API client metadata is out of date.");
    process.exit(1);
  }
} else {
  await writeFile(outputPath, output, "utf8");
}
