import { describe, expect, it } from "vitest";

import { connectorRunLabel, connectionsLoadState } from "./connections-state";

describe("connector UI state", () => {
  it("distinguishes loading, healthy empty, and unavailable", () => {
    expect(connectionsLoadState(true, false, null)).toBe("loading");
    expect(connectionsLoadState(false, false, null)).toBe("empty");
    expect(connectionsLoadState(false, false, new Error("down"))).toBe("unavailable");
  });

  it("keeps terminal connector states truthful", () => {
    expect(connectorRunLabel({ state: "replayed", failureCode: null } as never)).toBe("Replayed");
    expect(connectorRunLabel({ state: "failed", failureCode: "CONNECTOR_FAILED" } as never)).toBe(
      "Failed (CONNECTOR_FAILED)",
    );
  });
});
