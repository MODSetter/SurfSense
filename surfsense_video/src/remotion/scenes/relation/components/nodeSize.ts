/**
 * Relation node dimensions — width/height measured via canvas measureText
 * so layout can compute positions before React rendering.
 */
import type { RelationNode } from "../types";

export interface NodeDimensions {
  width: number;
  height: number;
  halfW: number;
  halfH: number;
  paddingX: number;
  paddingY: number;
  fontSize: number;
  descFontSize: number;
}

const LINE_HEIGHT = 1.3;
const GAP_FACTOR = 0.4;
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

export function getNodeDimensions(
  node: RelationNode,
  vmin: number,
): NodeDimensions {
  const paddingX = vmin * 2;
  const paddingY = vmin * 1;
  const fontSize = vmin * 1.6;
  const descFontSize = vmin * 1.2;
  const borderW = vmin * 0.14;

  const width = vmin * 18;
  const minHeight = vmin * 6;

  const innerW = width - 2 * paddingX - 2 * borderW;
  const labelLines = measureLines(node.label, fontSize, 600, innerW);
  const labelH = labelLines * fontSize * LINE_HEIGHT;

  let contentH = labelH;
  if (node.desc) {
    const descLines = measureLines(node.desc, descFontSize, 400, innerW);
    const descH = descLines * descFontSize * LINE_HEIGHT;
    contentH += vmin * GAP_FACTOR + descH;
  }

  const height = Math.max(minHeight, contentH + 2 * paddingY + 2 * borderW);

  return {
    width,
    height,
    halfW: width / 2,
    halfH: height / 2,
    paddingX,
    paddingY,
    fontSize,
    descFontSize,
  };
}

/** Returns the largest node box across all nodes. */
export function getMaxNodeSize(
  nodes: RelationNode[],
  vmin: number,
): { maxW: number; maxH: number } {
  let maxW = 0;
  let maxH = 0;
  for (const node of nodes) {
    const dims = getNodeDimensions(node, vmin);
    maxW = Math.max(maxW, dims.width);
    maxH = Math.max(maxH, dims.height);
  }
  return { maxW, maxH };
}
