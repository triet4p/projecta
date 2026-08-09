import { describe, expect, it } from "vitest";

import { moveNoteItem, type NoteDraftItem } from "./screens/note-composer";

const items: NoteDraftItem[] = [
  { itemType: "task", content: "Repeat" },
  { itemType: "task", content: "Repeat" },
  { itemType: "risk", content: "Keep last" },
];

describe("structured Note composer keyboard-order semantics", () => {
  it("moves repeated items by position rather than content", () => {
    expect(moveNoteItem(items, 1, 1)).toEqual([items[0], items[2], items[1]]);
    expect(moveNoteItem(items, 0, 1)).toEqual([items[1], items[0], items[2]]);
  });

  it("keeps boundary moves stable", () => {
    expect(moveNoteItem(items, 0, -1)).toBe(items);
    expect(moveNoteItem(items, items.length - 1, 1)).toBe(items);
  });
});
