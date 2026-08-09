import type { StructuredNoteDraftInput } from "../api/generated";

export type NoteDraftItem = StructuredNoteDraftInput["items"][number];

export function moveNoteItem(
  items: NoteDraftItem[],
  index: number,
  direction: -1 | 1,
): NoteDraftItem[] {
  const nextIndex = index + direction;
  if (index < 0 || index >= items.length || nextIndex < 0 || nextIndex >= items.length) {
    return items;
  }
  const next = [...items];
  [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
  return next;
}
