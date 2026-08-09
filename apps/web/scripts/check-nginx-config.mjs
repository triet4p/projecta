import assert from "node:assert/strict";
import console from "node:console";
import { readFileSync } from "node:fs";
import { URL } from "node:url";

const configuration = readFileSync(new URL("../nginx.conf", import.meta.url), "utf8");
const apiLocation = configuration.match(/location \/v1\/ \{(?<body>[\s\S]*?)\n\s*\}/)?.groups?.body;

assert.ok(apiLocation, "nginx.conf must define the /v1/ API proxy location");

const readTimeout = timeoutSeconds(apiLocation, "proxy_read_timeout");
const sendTimeout = timeoutSeconds(apiLocation, "proxy_send_timeout");
const minimumProxyBudgetSeconds = 61;

assert.ok(
  readTimeout >= minimumProxyBudgetSeconds,
  `proxy_read_timeout must cover the single bounded provider attempt; received ${readTimeout}s`,
);
assert.ok(
  sendTimeout >= minimumProxyBudgetSeconds,
  `proxy_send_timeout must cover the bounded extraction operation; received ${sendTimeout}s`,
);

assert.match(configuration, /log_format\s+projecta_json/);
assert.match(configuration, /access_log\s+\/dev\/stdout\s+projecta_json/);
assert.match(configuration, /error_log\s+\/dev\/stderr\s+warn/);
assert.match(configuration, /"requestId"/);
assert.match(configuration, /"operationId"/);
assert.doesNotMatch(configuration, /\$request"/);

console.log(`Nginx API proxy timeout budget verified: read=${readTimeout}s send=${sendTimeout}s`);

function timeoutSeconds(location, directive) {
  const value = location.match(new RegExp(`\\b${directive}\\s+(\\d+)(ms|s|m);`));
  assert.ok(value, `${directive} must be explicitly configured in the /v1/ location`);
  const amount = Number(value[1]);
  const unit = value[2];
  return unit === "ms" ? amount / 1000 : unit === "m" ? amount * 60 : amount;
}
