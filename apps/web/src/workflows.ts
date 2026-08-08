import type { EntityType, TypedSegment } from "./api/generated";

export function normalizeNoteText(value: string): string {
  return value.replace(/\r\n?/g, "\n");
}

export function utf16OffsetToCodePoint(value: string, offset: number): number {
  return Array.from(value.slice(0, offset)).length;
}

export function selectedTypedSegment(
  value: string,
  start: number,
  end: number,
  type: EntityType,
): TypedSegment | null {
  const normalized = normalizeNoteText(value);
  const startOffset = utf16OffsetToCodePoint(normalized, start);
  const endOffset = utf16OffsetToCodePoint(normalized, end);
  if (startOffset >= endOffset) return null;
  const codePoints = Array.from(normalized);
  return { type, startOffset, endOffset, text: codePoints.slice(startOffset, endOffset).join("") };
}

export function canAddSegment(segments: TypedSegment[], next: TypedSegment): boolean {
  return !segments.some(
    (segment) => next.startOffset < segment.endOffset && next.endOffset > segment.startOffset,
  );
}
