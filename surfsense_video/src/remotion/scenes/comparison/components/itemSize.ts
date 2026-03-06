/**
 * Comparison item dimensions — width/height measured via canvas measureText
 * so layout can compute positions before React rendering.
 */
import type { CompareItem } from "../types";

export interface ItemDimensions {
  width: number;
  height: number;
  paddingX: number;
  paddingY: number;
  fontSize: number;
  descFontSize: number;
}

const LINE_HEIGHT = 1.3;
const GAP_FACTOR = 0.35;
const FONT_FAMILY = "Inter, system-ui, sans-serif";

let _ctx: CanvasRenderingContext2D | null = null;
function ctx(): CanvasRenderingContext2D {
  if (!_ctx) _ctx = document.createElement("canvas").getContext("2d")!;
  return _ctx;
}

function measureLines(
  text: string,
  fontSize: number,
  fontWeight: number | string,
  availableWidth: number,
): number {
  const c = ctx();
  c.font = `${fontWeight} ${fontSize}px ${FONT_FAMILY}`;

  const words = text.split(/\s+/).filter(Boolean);
  if (words.length === 0) return 1;

  let lines = 1;
  let lineWidth = 0;
  const spaceW = c.measureText(" ").width;

  for (const word of words) {
    const wordW = c.measureText(word).width;
    if (lineWidth === 0) {
      lineWidth = wordW;
    } else if (lineWidth + spaceW + wordW <= availableWidth) {
      lineWidth += spaceW + wordW;
    } else {
      lines++;
      lineWidth = wordW;
    }
  }

  return lines;
}

export function getItemDimensions(
  item: CompareItem,
  vmin: number,
  fixedWidth?: number,
): ItemDimensions {
  const paddingX = vmin * 2.5;
  const paddingY = vmin * 1.5;
  const fontSize = vmin * 2;
  const descFontSize = vmin * 1.5;
  const borderW = vmin * 0.14;

  const width = fixedWidth ?? vmin * 32;
  const minHeight = vmin * 7;

  const innerW = width - 2 * paddingX - 2 * borderW;
  const labelLines = measureLines(item.label, fontSize, 600, innerW);
  const labelH = labelLines * fontSize * LINE_HEIGHT;

  let contentH = labelH;
  if (item.desc) {
    const descLines = measureLines(item.desc, descFontSize, 400, innerW);
    const descH = descLines * descFontSize * LINE_HEIGHT;
    contentH += vmin * GAP_FACTOR + descH;
  }

  const height = Math.max(minHeight, contentH + 2 * paddingY + 2 * borderW);

  return { width, height, paddingX, paddingY, fontSize, descFontSize };
}

/** Returns the tallest item height across all items. */
export function getMaxItemHeight(
  items: CompareItem[],
  vmin: number,
  fixedWidth?: number,
): number {
  let maxH = 0;
  for (const item of items) {
    const dims = getItemDimensions(item, vmin, fixedWidth);
    maxH = Math.max(maxH, dims.height);
  }
  return maxH;
}
