/**
 * Shared node dimensions — width is fixed per depth level,
 * height is measured from content via canvas measureText.
 */
import type { HierarchyNode } from "../types";

interface NodeDimensions {
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

export function getNodeDimensions(
  node: HierarchyNode,
  vmin: number,
  isRoot: boolean,
): NodeDimensions {
  const paddingX = vmin * (isRoot ? 3 : 2);
  const paddingY = vmin * (isRoot ? 1.5 : 1);
  const fontSize = vmin * (isRoot ? 2.2 : 1.6);
  const descFontSize = vmin * 1.2;

  const borderW = vmin * BORDER_FACTOR;
  const width = vmin * (isRoot ? 22 : 18);
  const minHeight = vmin * (isRoot ? 10 : 8);

  const innerW = width - 2 * paddingX - 2 * borderW;
  const labelWeight = isRoot ? 700 : 500;
  const labelLines = measureLines(node.label, fontSize, labelWeight, innerW);
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

/** Returns the largest node box across all nodes in the tree. */
export function getMaxNodeSize(
  root: HierarchyNode,
  vmin: number,
): { maxW: number; maxH: number } {
  let maxW = 0;
  let maxH = 0;

  function walk(node: HierarchyNode, isRoot: boolean) {
    const dims = getNodeDimensions(node, vmin, isRoot);
    maxW = Math.max(maxW, dims.width);
    maxH = Math.max(maxH, dims.height);
    for (const child of node.children ?? []) {
      walk(child, false);
    }
  }

  walk(root, true);
  return { maxW, maxH };
}
