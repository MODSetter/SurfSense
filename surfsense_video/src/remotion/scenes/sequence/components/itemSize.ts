/**
 * Measure sequence item dimensions using canvas.measureText.
 * Same approach as list/itemSize.ts — deterministic text measurement
 * before layout so positioning is based on actual content size.
 */
import type { SequenceItem } from "../types";

export interface ItemDimensions {
  width: number;
  height: number;
  paddingX: number;
  paddingY: number;
  labelFontSize: number;
  descFontSize: number;
  badgeSize: number;
}

const LINE_HEIGHT_LABEL = 1.3;
const LINE_HEIGHT_DESC = 1.4;
const FONT_FAMILY = "Inter, system-ui, sans-serif";
const BORDER_FACTOR = 0.14;

let _ctx: CanvasRenderingContext2D | null = null;
function ctx(): CanvasRenderingContext2D {
  if (!_ctx) {
    _ctx = document.createElement("canvas").getContext("2d")!;
  }
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

export function measureItemDimensions(
  item: SequenceItem,
  vmin: number,
  cardW: number,
  showBadge: boolean,
): ItemDimensions {
  const paddingX = vmin * 2;
  const paddingY = vmin * 1.5;
  const borderW = vmin * BORDER_FACTOR;
  const gap = vmin * 1.5;
  const textGap = vmin * 0.3;

  const labelFontSize = vmin * 1.8;
  const descFontSize = vmin * 1.2;
  const badgeSize = vmin * 5;

  const badgeSpace = showBadge ? badgeSize + gap : 0;
  const textW = cardW - 2 * paddingX - 2 * borderW - badgeSpace;

  const labelLines = measureLines(item.label, labelFontSize, 600, textW);
  const labelH = labelLines * labelFontSize * LINE_HEIGHT_LABEL;

  let contentH = labelH;
  if (item.desc) {
    const descLines = measureLines(item.desc, descFontSize, 400, textW);
    const descH = descLines * descFontSize * LINE_HEIGHT_DESC;
    contentH += textGap + descH;
  }

  const minHeight = Math.max(
    showBadge ? badgeSize + 2 * paddingY : vmin * 5,
    vmin * 6,
  );
  const height = Math.max(minHeight, contentH + 2 * paddingY + 2 * borderW);

  return {
    width: cardW,
    height,
    paddingX,
    paddingY,
    labelFontSize,
    descFontSize,
    badgeSize,
  };
}
