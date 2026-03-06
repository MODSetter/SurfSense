/** Directional arrow connector between sequence steps. */
import React from "react";
import { useCurrentFrame, interpolate } from "remotion";
import type { SequenceVariant } from "../variant";
import { ARROW_FADE_DURATION } from "../constants";

interface ArrowProps {
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
  curvePath?: string;
  enterFrame: number;
  vmin: number;
  color: string;
  variant: SequenceVariant;
}

export const Arrow: React.FC<ArrowProps> = ({
  fromX,
  fromY,
  toX,
  toY,
  curvePath,
  enterFrame,
  vmin,
  color,
  variant,
}) => {
  const frame = useCurrentFrame();
  const localFrame = frame - enterFrame;

  const opacity = interpolate(localFrame, [0, ARROW_FADE_DURATION], [0, 0.6], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const headSize = vmin * 1.5;
  const strokeW = vmin * 0.25;
  const dashArr = variant.arrowStyle === "dashed"
    ? `${vmin * 0.8} ${vmin * 0.5}`
    : "none";

  const allX = [fromX, toX];
  const allY = [fromY, toY];

  if (curvePath) {
    const nums = curvePath.match(/-?\d+(\.\d+)?/g)?.map(Number) ?? [];
    for (let n = 0; n < nums.length; n += 2) {
      if (n + 1 < nums.length) {
        allX.push(nums[n]);
        allY.push(nums[n + 1]);
      }
    }
  }

  const pad = headSize * 2;
  const minX = Math.min(...allX) - pad;
  const minY = Math.min(...allY) - pad;
  const maxX = Math.max(...allX) + pad;
  const maxY = Math.max(...allY) + pad;
  const svgW = maxX - minX;
  const svgH = maxY - minY;

  const ox = -minX;
  const oy = -minY;

  let pathD: string;
  let tipDx: number;
  let tipDy: number;

  if (curvePath) {
    pathD = curvePath.replace(
      /(-?\d+(\.\d+)?)/g,
      (match, _p1, _p2, offset) => {
        const before = curvePath!.substring(0, offset);
        const numsBefore = before.match(/-?\d+(\.\d+)?/g) ?? [];
        const idx = numsBefore.length;
        if (idx % 2 === 0) return String(Number(match) + ox);
        return String(Number(match) + oy);
      },
    );
    const controlNums = curvePath.match(/-?\d+(\.\d+)?/g)?.map(Number) ?? [];
    const n = controlNums.length;
    if (n >= 4) {
      tipDx = toX - controlNums[n - 4];
      tipDy = toY - controlNums[n - 3];
    } else {
      tipDx = toX - fromX;
      tipDy = toY - fromY;
    }
  } else {
    pathD = `M ${fromX + ox} ${fromY + oy} L ${toX + ox} ${toY + oy}`;
    tipDx = toX - fromX;
    tipDy = toY - fromY;
  }

  const tipLen = Math.sqrt(tipDx * tipDx + tipDy * tipDy);
  if (tipLen < 0.5) return null;

  const ux = tipDx / tipLen;
  const uy = tipDy / tipLen;
  const tx = toX + ox;
  const ty = toY + oy;
  const bx = tx - ux * headSize;
  const by = ty - uy * headSize;
  const px = -uy * headSize * 0.5;
  const py = ux * headSize * 0.5;

  return (
    <svg
      style={{
        position: "absolute",
        left: minX,
        top: minY,
        overflow: "visible",
        pointerEvents: "none",
        opacity,
      }}
      width={svgW}
      height={svgH}
    >
      <path
        d={pathD}
        fill="none"
        stroke={color}
        strokeWidth={strokeW}
        strokeDasharray={dashArr}
      />
      <polygon
        points={`${tx},${ty} ${bx + px},${by + py} ${bx - px},${by - py}`}
        fill={color}
      />
    </svg>
  );
};
