/**
 * CardReveal — animated SVG stroke reveal for card borders.
 * Uses @remotion/paths evolvePath to draw a rounded-rect stroke.
 * Content fades in as the stroke draws.
 */
import React from "react";
import { useCurrentFrame, interpolate } from "remotion";
import { evolvePath } from "@remotion/paths";
import { DRAW_DURATION } from "../constants";

type RevealStyle =
  | "drawSingle"
  | "drawDouble"
  | "drawEdges"
  | "drawBrackets"
  | "drawNoisy";

function roundedPath(w: number, h: number, r: number, startCorner: number): string {
  const corners = [
    { mx: r, my: 0, lx: w - r, ly: 0, qx: w, qy: 0, qex: w, qey: r },
    { mx: w, my: r, lx: w, ly: h - r, qx: w, qy: h, qex: w - r, qey: h },
    { mx: w - r, my: h, lx: r, ly: h, qx: 0, qy: h, qex: 0, qey: h - r },
    { mx: 0, my: h - r, lx: 0, ly: r, qx: 0, qy: 0, qex: r, qey: 0 },
  ];
  const shifted = [...corners.slice(startCorner), ...corners.slice(0, startCorner)];
  const first = shifted[0];
  const parts = [`M ${first.mx} ${first.my}`];
  for (const c of shifted) {
    parts.push(`L ${c.lx} ${c.ly}`, `Q ${c.qx} ${c.qy} ${c.qex} ${c.qey}`);
  }
  parts.push("Z");
  return parts.join(" ");
}

function roundedEdgePaths(w: number, h: number, r: number): string[] {
  return [
    `M ${r} 0 L ${w - r} 0 Q ${w} 0 ${w} ${r}`,
    `M ${w} ${r} L ${w} ${h - r} Q ${w} ${h} ${w - r} ${h}`,
    `M ${w - r} ${h} L ${r} ${h} Q 0 ${h} 0 ${h - r}`,
    `M 0 ${h - r} L 0 ${r} Q 0 0 ${r} 0`,
  ];
}

function roundedBracketPaths(w: number, h: number, r: number) {
  const armLen = Math.min(w, h) * 0.18;
  return [
    { path: `M ${r + armLen} 0 L ${r} 0 Q 0 0 0 ${r} L 0 ${r + armLen}`, delay: 0 },
    { path: `M ${w - r - armLen} 0 L ${w - r} 0 Q ${w} 0 ${w} ${r} L ${w} ${r + armLen}`, delay: 0.1 },
    { path: `M ${w} ${h - r - armLen} L ${w} ${h - r} Q ${w} ${h} ${w - r} ${h} L ${w - r - armLen} ${h}`, delay: 0.2 },
    { path: `M 0 ${h - r - armLen} L 0 ${h - r} Q 0 ${h} ${r} ${h} L ${r + armLen} ${h}`, delay: 0.3 },
  ];
}

interface CardRevealProps {
  enterFrame: number;
  index: number;
  width: number;
  height: number;
  radius: number;
  color: string;
  vmin: number;
  reveal: RevealStyle;
  children: React.ReactNode;
}

export const CardReveal: React.FC<CardRevealProps> = ({
  enterFrame, index, width, height, radius, color, vmin, reveal, children,
}) => {
  const frame = useCurrentFrame();
  const local = frame - enterFrame;

  let progress: number;
  if (local < 0) progress = 0;
  else if (local >= DRAW_DURATION) progress = 1;
  else {
    const raw = local / DRAW_DURATION;
    progress = 1 - Math.pow(1 - raw, 3);
  }

  let strokeOpacity: number;
  if (local < 0) strokeOpacity = 0;
  else if (local < 2) strokeOpacity = interpolate(local, [0, 2], [0, 1], { extrapolateRight: "clamp" });
  else strokeOpacity = 1;

  const contentOpacity = interpolate(progress, [0.15, 0.6], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  const strokeW = vmin * 0.06;
  const glowFilter = `drop-shadow(0 0 ${vmin * 0.8}px ${color}80)`;
  const contentClip: React.CSSProperties = { borderRadius: radius, overflow: "hidden" };
  const svgStyle: React.CSSProperties = {
    position: "absolute", top: 0, left: 0,
    pointerEvents: "none", overflow: "visible",
  };

  const clamp = Math.min(Math.max(progress, 0), 1);

  if (reveal === "drawSingle") {
    const path = roundedPath(width, height, radius, index % 4);
    const evolved = evolvePath(clamp, path);
    return (
      <div style={{ position: "relative", width, height }}>
        <svg width={width} height={height} style={svgStyle}>
          <path d={path} fill="none" stroke={color} strokeWidth={strokeW}
            strokeDasharray={evolved.strokeDasharray} strokeDashoffset={evolved.strokeDashoffset}
            strokeLinecap="round" opacity={strokeOpacity} style={{ filter: glowFilter }} />
        </svg>
        <div style={{ position: "relative", opacity: contentOpacity, ...contentClip }}>{children}</div>
      </div>
    );
  }

  if (reveal === "drawDouble") {
    const pathA = roundedPath(width, height, radius, 0);
    const pathB = roundedPath(width, height, radius, 2);
    const eA = evolvePath(clamp, pathA);
    const eB = evolvePath(clamp, pathB);
    return (
      <div style={{ position: "relative", width, height }}>
        <svg width={width} height={height} style={svgStyle}>
          <path d={pathA} fill="none" stroke={color} strokeWidth={strokeW}
            strokeDasharray={eA.strokeDasharray} strokeDashoffset={eA.strokeDashoffset}
            strokeLinecap="round" opacity={strokeOpacity} style={{ filter: glowFilter }} />
          <path d={pathB} fill="none" stroke={color} strokeWidth={strokeW}
            strokeDasharray={eB.strokeDasharray} strokeDashoffset={eB.strokeDashoffset}
            strokeLinecap="round" opacity={strokeOpacity} style={{ filter: glowFilter }} />
        </svg>
        <div style={{ position: "relative", opacity: contentOpacity, ...contentClip }}>{children}</div>
      </div>
    );
  }

  if (reveal === "drawEdges") {
    const edgePaths = roundedEdgePaths(width, height, radius);
    return (
      <div style={{ position: "relative", width, height }}>
        <svg width={width} height={height} style={svgStyle}>
          {edgePaths.map((ep, i) => {
            const stagger = i * 0.15;
            const edgeProgress = interpolate(clamp, [stagger, Math.min(stagger + 0.7, 1)], [0, 1], {
              extrapolateLeft: "clamp", extrapolateRight: "clamp",
            });
            const evolved = evolvePath(edgeProgress, ep);
            return (
              <path key={i} d={ep} fill="none" stroke={color} strokeWidth={strokeW}
                strokeDasharray={evolved.strokeDasharray} strokeDashoffset={evolved.strokeDashoffset}
                strokeLinecap="round" opacity={strokeOpacity} style={{ filter: glowFilter }} />
            );
          })}
        </svg>
        <div style={{ position: "relative", opacity: contentOpacity, ...contentClip }}>{children}</div>
      </div>
    );
  }

  if (reveal === "drawNoisy") {
    const path = roundedPath(width, height, radius, index % 4);
    const evolved = evolvePath(clamp, path);
    const filterId = `noise-${index}`;
    const turbScale = interpolate(clamp, [0, 0.3, 1], [0.08, 0.05, 0.02]);
    return (
      <div style={{ position: "relative", width, height }}>
        <svg width={width} height={height} style={svgStyle}>
          <defs>
            <filter id={filterId} x="-10%" y="-10%" width="120%" height="120%">
              <feTurbulence type="turbulence" baseFrequency={turbScale} numOctaves={3}
                seed={index * 7 + 13} result="noise" />
              <feDisplacementMap in="SourceGraphic" in2="noise" scale={vmin * 1.5}
                xChannelSelector="R" yChannelSelector="G" result="displaced" />
              <feGaussianBlur in="displaced" stdDeviation={vmin * 0.15} result="glow" />
              <feMerge>
                <feMergeNode in="glow" />
                <feMergeNode in="displaced" />
              </feMerge>
            </filter>
          </defs>
          <path d={path} fill="none" stroke={color} strokeWidth={strokeW * 1.8}
            strokeDasharray={evolved.strokeDasharray} strokeDashoffset={evolved.strokeDashoffset}
            strokeLinecap="round" opacity={strokeOpacity} filter={`url(#${filterId})`} />
        </svg>
        <div style={{ position: "relative", opacity: contentOpacity, ...contentClip }}>{children}</div>
      </div>
    );
  }

  const brackets = roundedBracketPaths(width, height, radius);
  return (
    <div style={{ position: "relative", width, height }}>
      <svg width={width} height={height} style={svgStyle}>
        {brackets.map((corner, i) => {
          const cornerProgress = interpolate(clamp,
            [corner.delay, Math.min(corner.delay + 0.5, 1)], [0, 1], {
              extrapolateLeft: "clamp", extrapolateRight: "clamp",
            });
          const eased = 1 - Math.pow(1 - cornerProgress, 3);
          const evolved = evolvePath(eased, corner.path);
          return (
            <path key={i} d={corner.path} fill="none" stroke={color} strokeWidth={strokeW * 2}
              strokeDasharray={evolved.strokeDasharray} strokeDashoffset={evolved.strokeDashoffset}
              strokeLinecap="round" opacity={strokeOpacity} style={{ filter: glowFilter }} />
          );
        })}
      </svg>
      <div style={{ position: "relative", opacity: contentOpacity, ...contentClip }}>{children}</div>
    </div>
  );
};
