import { describe, expect, it } from "vitest";

import { canAddSegment, selectedTypedSegment, utf16OffsetToCodePoint } from "./workflows";

describe("manual capture evidence semantics", () => {
  it("converts browser UTF-16 offsets to Unicode code-point offsets", () => {
    const note = "Pay 💳 now";
    expect(utf16OffsetToCodePoint(note, note.indexOf("now"))).toBe(6);
    expect(
      selectedTypedSegment(note, note.indexOf("💳"), note.indexOf("💳") + 2, "risk"),
    ).toMatchObject({
      startOffset: 4,
      endOffset: 5,
      text: "💳",
    });
  });

  it("rejects overlapping typed segments", () => {
    const first = selectedTypedSegment("Confirm payment", 0, 7, "requirement");
    const overlap = selectedTypedSegment("Confirm payment", 4, 12, "risk");
    expect(first).not.toBeNull();
    expect(overlap).not.toBeNull();
    expect(canAddSegment([first!], overlap!)).toBe(false);
  });
});
