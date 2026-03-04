# Example: Data Presentation — "Cloud Computing Market 2025"

## Pattern: SCENE REPLACEMENT (Pattern B)

Each slide fully replaces the previous via `<Series>`.
Use for: data presentations, reports, comparisons, dashboards, market analysis.

## Capabilities demonstrated

- **Series** for sequential scene replacement (6 slides)
- **AnimatedCounter** for animated number counting (remotion-bits)
- **AnimatedText** with word-split for titles (remotion-bits)
- **StaggeredMotion** for staggered list/grid reveals (remotion-bits)
- **evolvePath** for animated SVG trend line (@remotion/paths)
- **gridPositions** (inline utility) — 2×2 grid layout for stat cards
- **distributeX** (inline utility) — even horizontal spacing for bar chart
- **SVG donut chart** with pre-computed angles and animated arc segments
- **SVG bar chart** with year-over-year comparison
- **SVG line chart** with area fill, animated dots, and callout
- **spring()** for organic card pop-ins, donut center label, bar growth
- **interpolate() + Easing** for controlled line drawing and fade timing
- **lucide-react icons** — Cloud, BarChart3, PieChart, TrendingUp, etc.
- **Gradient backgrounds** — different gradient per slide for visual variety
- **Legend with change indicators** (▲/▼ arrows, color-coded)
- **Grid lines + axis labels** for professional chart formatting

## Scene inventory (what's on screen at each point)

In Pattern B, each `Series.Sequence` is a CLEAN SLATE. When a sequence ends,
EVERYTHING inside it disappears. The next sequence starts fresh.
Never reference elements from a previous slide — they don't exist anymore.

- **Slide 1 (0–180)**: Title centered with Cloud icon, AnimatedText, underline.
- **Slide 2 (180–380)**: 4 stat cards in 2×2 grid, each with icon + AnimatedCounter.
- **Slide 3 (380–590)**: Donut chart left, legend right. Pre-computed angles.
- **Slide 4 (590–800)**: Bar chart with grid lines, paired bars (prev + current).
- **Slide 5 (800–1010)**: Trend line drawn with evolvePath, dots pop in, callout.
- **Slide 6 (1010–1210)**: Key takeaways list with StaggeredMotion + CheckCircle icons.

## Full code

```tsx
import React from "react";
import {
  AbsoluteFill, Series, useCurrentFrame, useVideoConfig,
  interpolate, spring, Easing,
} from "remotion";
// CAPABILITY: AnimatedCounter counts from 0 to target value over specified duration.
// AnimatedText splits text into words/chars with staggered entrance.
// StaggeredMotion wraps children and staggers their entrance animation.
import { AnimatedText, AnimatedCounter, StaggeredMotion } from "remotion-bits";
// CAPABILITY: evolvePath takes a progress (0→1) and an SVG path string,
// returns { strokeDasharray, strokeDashoffset } for animating the path drawing.
import { evolvePath } from "@remotion/paths";
import {
  Cloud, BarChart3, CheckCircle, Globe, Cpu, Wifi,
  DollarSign, PieChart, TrendingUp,
} from "lucide-react";

const BG = "#0f172a";
const SURFACE = "#1e293b";
const TEXT = "#f8fafc";
const MUTED = "#94a3b8";
const DIM = "#475569";
const GREEN = "#22c55e";
const BLUE = "#3b82f6";
const RED = "#ef4444";
const FONT = "Inter, system-ui, sans-serif";

// ── Data arrays — define outside component for clarity ──
const PROVIDERS = [
  { label: "AWS", value: 32, prev: 28, color: "#FF9900" },
  { label: "Azure", value: 23, prev: 20, color: "#0078D4" },
  { label: "GCP", value: 11, prev: 9, color: "#4285F4" },
  { label: "Others", value: 34, prev: 43, color: "#6B7280" },
];

const STATS = [
  { icon: Globe, label: "Cloud Regions", value: 84, suffix: "+", color: BLUE },
  { icon: Cpu, label: "Managed Services", value: 620, suffix: "+", color: "#8b5cf6" },
  { icon: Wifi, label: "Edge Locations", value: 400, suffix: "+", color: "#06b6d4" },
  { icon: DollarSign, label: "Market Size ($B)", value: 680, suffix: "", color: GREEN },
];

const QUARTERLY = [
  { q: "Q1'24", value: 520 },
  { q: "Q2'24", value: 548 },
  { q: "Q3'24", value: 575 },
  { q: "Q4'24", value: 610 },
  { q: "Q1'25", value: 635 },
  { q: "Q2'25", value: 658 },
  { q: "Q3'25", value: 680 },
];

const TAKEAWAYS = [
  "Multi-cloud adoption grew 28% year-over-year",
  "AI/ML workloads drove 40% of new cloud spending",
  "Edge computing expanded to 15% of total market",
  "Serverless functions usage doubled since 2023",
];

// ── CAPABILITY: distributeX — evenly space N items between startX and endX ──
// Define inline. Returns array of x-coordinates.
function distributeX(count: number, startX: number, endX: number): number[] {
  if (count <= 1) return [(startX + endX) / 2];
  const step = (endX - startX) / (count - 1);
  return Array.from({ length: count }, (_, i) => startX + i * step);
}

// ── CAPABILITY: gridPositions — arrange N items in a grid with cols columns ──
// Returns array of {x, y} center positions for each cell.
function gridPositions(
  count: number, cols: number, cellW: number, cellH: number,
  originX: number, originY: number,
): { x: number; y: number }[] {
  return Array.from({ length: count }, (_, i) => ({
    x: originX + (i % cols) * cellW + cellW / 2,
    y: originY + Math.floor(i / cols) * cellH + cellH / 2,
  }));
}

// ═══════════════════════════════════════════════════════════════════════
// MAIN COMPONENT — Series-based scene replacement
// ═══════════════════════════════════════════════════════════════════════
// CAPABILITY: <Series> plays children sequentially. Each Series.Sequence
// gets its own local frame counter (useCurrentFrame() starts at 0).
// When a sequence ends, its content is UNMOUNTED — completely removed.

export const MyComp: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      <Series>
        <Series.Sequence durationInFrames={180}>
          <TitleSlide />
        </Series.Sequence>
        <Series.Sequence durationInFrames={200}>
          <StatsGrid />
        </Series.Sequence>
        <Series.Sequence durationInFrames={210}>
          <DonutChartSlide />
        </Series.Sequence>
        <Series.Sequence durationInFrames={210}>
          <BarChartSlide />
        </Series.Sequence>
        <Series.Sequence durationInFrames={210}>
          <TrendLineSlide />
        </Series.Sequence>
        <Series.Sequence durationInFrames={200}>
          <TakeawaysSlide />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};

// ── Slide 1: Title ──
const TitleSlide: React.FC = () => {
  const frame = useCurrentFrame();
  const lineW = interpolate(frame, [35, 75], [0, 240], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{
      background: `linear-gradient(135deg, ${SURFACE} 0%, ${BG} 50%, #1e1b4b 100%)`,
      justifyContent: "center", alignItems: "center",
    }}>
      <div style={{
        display: "flex", flexDirection: "column", alignItems: "center",
      }}>
        <div style={{ marginBottom: 24 }}>
          <Cloud size={64} color={BLUE} />
        </div>
        <AnimatedText
          transition={{
            y: [40, 0], opacity: [0, 1],
            split: "word", splitStagger: 6, duration: 40,
          }}
          style={{ fontSize: 68, color: TEXT, fontFamily: FONT, fontWeight: 700 }}
        >
          Cloud Computing Market
        </AnimatedText>
        <div style={{
          width: lineW, height: 3, backgroundColor: BLUE,
          borderRadius: 2, marginTop: 18, marginBottom: 14,
        }} />
        <AnimatedText
          transition={{ opacity: [0, 1], duration: 30, delay: 40 }}
          style={{ fontSize: 28, color: MUTED, fontFamily: FONT }}
        >
          2025 Global Infrastructure Report
        </AnimatedText>
      </div>
    </AbsoluteFill>
  );
};

// ── Slide 2: Key Metrics — gridPositions + AnimatedCounter ──
const StatsGrid: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // CAPABILITY: gridPositions arranges 4 items in 2 columns
  const cells = gridPositions(4, 2, 440, 270, 530, 260);

  return (
    <AbsoluteFill style={{
      background: `linear-gradient(180deg, ${BG} 0%, #0c1222 100%)`,
    }}>
      <div style={{
        position: "absolute", top: 55, left: 0, width: 1920,
        display: "flex", flexDirection: "column", alignItems: "center",
      }}>
        <AnimatedText
          transition={{ y: [20, 0], opacity: [0, 1], duration: 35 }}
          style={{ fontSize: 42, color: TEXT, fontFamily: FONT, fontWeight: 700 }}
        >
          Industry at a Glance
        </AnimatedText>
      </div>

      {STATS.map((stat, i) => {
        // CAPABILITY: spring with staggered delay for each card
        const s = spring({
          frame, fps, delay: 20 + i * 18,
          config: { damping: 16, stiffness: 100 },
        });
        const cell = cells[i];
        return (
          <div key={stat.label} style={{
            position: "absolute", left: cell.x, top: cell.y,
            width: 380,
            // CAPABILITY: translate(-50%, -50%) centers the card on its grid position
            transform: `translate(-50%, -50%) scale(${s})`,
            opacity: s,
            display: "flex", flexDirection: "column",
            alignItems: "center", gap: 14,
            padding: "34px 24px",
            backgroundColor: `${SURFACE}cc`,
            borderRadius: 18, border: `1px solid ${stat.color}25`,
          }}>
            <div style={{
              width: 52, height: 52, borderRadius: 14,
              backgroundColor: `${stat.color}15`,
              display: "flex", justifyContent: "center", alignItems: "center",
            }}>
              <stat.icon size={28} color={stat.color} />
            </div>
            {/* CAPABILITY: AnimatedCounter counts from 0 → value over 80 frames */}
            <AnimatedCounter
              transition={{
                values: [0, stat.value], duration: 80, delay: 35 + i * 18,
              }}
              postfix={
                <span style={{ fontSize: 22, color: MUTED }}>{stat.suffix}</span>
              }
              style={{ fontSize: 48, color: TEXT, fontFamily: FONT, fontWeight: 700 }}
            />
            <div style={{ fontSize: 17, color: MUTED, fontFamily: FONT }}>
              {stat.label}
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// ── Slide 3: Donut Chart — pre-computed angles + animated SVG arcs ──

const DONUT_RADIUS = 185;
const DONUT_STROKE = 46;
const DONUT_CIRC = 2 * Math.PI * DONUT_RADIUS;

// CAPABILITY: Pre-compute cumulative angles OUTSIDE render to avoid
// mutating variables inside .map() render loops (Hard Rule #11).
const SEGMENT_ANGLES = (() => {
  const total = PROVIDERS.reduce((s, p) => s + p.value, 0);
  let cum = -90;
  return PROVIDERS.map((p) => {
    const start = cum;
    const sweep = (p.value / total) * 360;
    const arc = (p.value / total) * DONUT_CIRC;
    cum += sweep;
    return { start, arc };
  });
})();

const DonutChartSlide: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // CAPABILITY: Calculate donut + legend positioning to center the whole group
  const donutVisualW = (DONUT_RADIUS + DONUT_STROKE / 2) * 2;
  const legendW = 420;
  const gap = 100;
  const totalW = donutVisualW + gap + legendW;
  const startX = (1920 - totalW) / 2;
  const cx = startX + donutVisualW / 2;
  const cy = 520;
  const legendLeft = startX + donutVisualW + gap;

  const titleOpacity = interpolate(frame, [0, 30], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  const centerScale = spring({
    frame: frame - 60, fps,
    config: { damping: 14, stiffness: 100 },
  });

  const legendItemH = 68;
  const legendGap = 14;
  const legendTotalH = PROVIDERS.length * legendItemH + (PROVIDERS.length - 1) * legendGap;
  const legendTop = cy - legendTotalH / 2;

  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      {/* Slide title with icon */}
      <div style={{
        position: "absolute", top: 50, left: 0, width: 1920,
        display: "flex", justifyContent: "center", alignItems: "center",
        gap: 12, opacity: titleOpacity,
      }}>
        <PieChart size={30} color={BLUE} />
        <span style={{ fontSize: 38, color: TEXT, fontFamily: FONT, fontWeight: 700 }}>
          Market Share by Provider
        </span>
      </div>

      {/* CAPABILITY: SVG donut chart — each segment is a <circle> with
          strokeDasharray to show only its arc portion, rotated to its start angle.
          spring() animates each segment with staggered delay. */}
      <svg style={{
        position: "absolute", top: 0, left: 0,
        width: 1920, height: 1080, pointerEvents: "none",
      }}>
        {PROVIDERS.map((provider, i) => {
          const seg = SEGMENT_ANGLES[i];
          const progress = spring({
            frame: frame - 15 - i * 15, fps,
            config: { damping: 200 },
          });
          return (
            <circle
              key={provider.label}
              cx={cx} cy={cy} r={DONUT_RADIUS}
              fill="none" stroke={provider.color}
              strokeWidth={DONUT_STROKE}
              strokeDasharray={`${seg.arc * progress} ${DONUT_CIRC}`}
              strokeDashoffset={0} strokeLinecap="butt"
              transform={`rotate(${seg.start} ${cx} ${cy})`}
              opacity={0.9}
            />
          );
        })}
      </svg>

      {/* Center label with AnimatedCounter */}
      <div style={{
        position: "absolute", left: cx, top: cy,
        transform: `translate(-50%, -50%) scale(${centerScale})`,
        display: "flex", flexDirection: "column", alignItems: "center",
      }}>
        <AnimatedCounter
          transition={{ values: [0, 680], duration: 80, delay: 50 }}
          prefix={<span style={{ fontSize: 22, color: MUTED }}>$</span>}
          postfix={<span style={{ fontSize: 22, color: MUTED }}>B</span>}
          style={{ fontSize: 48, color: TEXT, fontFamily: FONT, fontWeight: 700 }}
        />
        <span style={{ fontSize: 14, color: DIM, fontFamily: FONT }}>
          Total Market
        </span>
      </div>

      {/* Legend — vertically centered next to donut */}
      <div style={{
        position: "absolute", left: legendLeft, top: legendTop,
        width: legendW, display: "flex", flexDirection: "column", gap: legendGap,
      }}>
        {PROVIDERS.map((provider, i) => {
          const opacity = interpolate(frame - (40 + i * 18), [0, 20], [0, 1], {
            extrapolateLeft: "clamp", extrapolateRight: "clamp",
          });
          return (
            <div key={provider.label} style={{
              display: "flex", alignItems: "center", gap: 16, opacity,
              backgroundColor: `${SURFACE}80`,
              padding: "14px 20px", borderRadius: 12,
              border: `1px solid ${provider.color}20`,
              height: legendItemH - 28,
            }}>
              <div style={{
                width: 18, height: 18, borderRadius: 5,
                backgroundColor: provider.color, flexShrink: 0,
              }} />
              <div style={{
                display: "flex", flexDirection: "column", flex: 1,
              }}>
                <span style={{
                  fontSize: 19, color: TEXT, fontFamily: FONT, fontWeight: 600,
                }}>
                  {provider.label}
                </span>
                <span style={{ fontSize: 14, color: MUTED, fontFamily: FONT }}>
                  {provider.value}% market share
                </span>
              </div>
              {/* Change indicator with color coding */}
              <div style={{
                fontSize: 14,
                color: provider.value > provider.prev ? GREEN : RED,
                fontFamily: FONT, fontWeight: 600, whiteSpace: "nowrap",
              }}>
                {provider.value > provider.prev ? "▲" : "▼"}{" "}
                {Math.abs(provider.value - provider.prev)}pp
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ── Slide 4: Bar Chart — distributeX + paired bars + grid lines ──
const BarChartSlide: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // CAPABILITY: distributeX evenly spaces bars across the chart area
  const xs = distributeX(PROVIDERS.length, 520, 1400);
  const maxVal = 40;
  const BAR_W = 90;
  const PREV_W = 50;
  const MAX_H = 380;
  const BAR_BOTTOM = 750;

  const titleOpacity = interpolate(frame, [0, 30], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  const gridLines = [0, 10, 20, 30, 40];

  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      <div style={{
        position: "absolute", top: 50, left: 0, width: 1920,
        display: "flex", justifyContent: "center", alignItems: "center",
        gap: 12, opacity: titleOpacity,
      }}>
        <BarChart3 size={30} color={BLUE} />
        <span style={{ fontSize: 38, color: TEXT, fontFamily: FONT, fontWeight: 700 }}>
          Provider Market Share (%)
        </span>
      </div>

      {/* Y-axis label */}
      <div style={{
        position: "absolute", left: 405, top: BAR_BOTTOM - MAX_H / 2,
        transform: "rotate(-90deg)",
        fontSize: 13, color: DIM, fontFamily: FONT,
        whiteSpace: "nowrap", opacity: titleOpacity,
      }}>
        Market Share %
      </div>

      {/* Grid lines for professional chart formatting */}
      {gridLines.map((val) => {
        const y = BAR_BOTTOM - (val / maxVal) * MAX_H;
        return (
          <React.Fragment key={val}>
            <div style={{
              position: "absolute", left: 460, top: y,
              width: 1000, height: 1, backgroundColor: `${DIM}20`,
            }} />
            <div style={{
              position: "absolute", left: 428, top: y - 9,
              fontSize: 13, color: DIM, fontFamily: FONT,
              textAlign: "right", width: 28,
            }}>
              {val}
            </div>
          </React.Fragment>
        );
      })}

      {/* CAPABILITY: Paired bars — dashed "previous year" bar + solid "current" bar */}
      {PROVIDERS.map((item, i) => {
        const heightProgress = spring({
          frame, fps, delay: 30 + i * 18,
          config: { damping: 200 },
        });
        const prevProgress = spring({
          frame, fps, delay: 50 + i * 18,
          config: { damping: 200 },
        });
        const barH = (item.value / maxVal) * MAX_H * heightProgress;
        const prevH = (item.prev / maxVal) * MAX_H * prevProgress;
        const labelOpacity = interpolate(
          frame - (55 + i * 18), [0, 25], [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );

        return (
          <React.Fragment key={item.label}>
            {/* Previous year bar (dashed outline) */}
            <div style={{
              position: "absolute",
              left: xs[i] - BAR_W / 2 - PREV_W / 2 - 4,
              top: BAR_BOTTOM - prevH, width: PREV_W, height: prevH,
              backgroundColor: `${item.color}20`,
              borderRadius: "6px 6px 0 0",
              border: `1px dashed ${item.color}40`,
            }} />
            {/* Current year bar (solid fill) */}
            <div style={{
              position: "absolute",
              left: xs[i] - BAR_W / 2 + PREV_W / 2 + 4,
              top: BAR_BOTTOM - barH, width: BAR_W, height: barH,
              backgroundColor: item.color,
              borderRadius: "8px 8px 0 0",
              boxShadow: `0 -4px 20px ${item.color}20`,
            }} />
            {/* Value label */}
            <div style={{
              position: "absolute",
              left: xs[i] + 4, top: BAR_BOTTOM - barH - 36,
              transform: "translateX(-50%)",
              fontSize: 22, color: TEXT, fontFamily: FONT,
              fontWeight: 700, opacity: labelOpacity,
            }}>
              {item.value}%
            </div>
            {/* Change indicator */}
            <div style={{
              position: "absolute",
              left: xs[i] + 4, top: BAR_BOTTOM - barH - 60,
              transform: "translateX(-50%)",
              fontSize: 14,
              color: item.value > item.prev ? GREEN : RED,
              fontFamily: FONT, fontWeight: 600, opacity: labelOpacity,
            }}>
              {item.value > item.prev ? "▲" : "▼"}{" "}
              {Math.abs(item.value - item.prev)}pp
            </div>
            {/* X-axis label */}
            <div style={{
              position: "absolute",
              left: xs[i], top: BAR_BOTTOM + 18,
              transform: "translateX(-50%)",
              fontSize: 18, color: MUTED, fontFamily: FONT,
              fontWeight: 600, opacity: labelOpacity,
            }}>
              {item.label}
            </div>
          </React.Fragment>
        );
      })}

      {/* Baseline */}
      <div style={{
        position: "absolute", left: 460, top: BAR_BOTTOM,
        width: 1000, height: 2, backgroundColor: DIM,
      }} />

      {/* Legend */}
      <div style={{
        position: "absolute", bottom: 50, left: 0, width: 1920,
        display: "flex", justifyContent: "center", gap: 40,
        opacity: interpolate(frame, [80, 110], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        }),
      }}>
        {[
          { label: "2024", border: `1px dashed ${DIM}`, bg: "transparent" },
          { label: "2025", border: "none", bg: DIM },
        ].map((leg) => (
          <div key={leg.label} style={{
            display: "flex", alignItems: "center", gap: 10,
          }}>
            <div style={{
              width: 18, height: 14, borderRadius: 3,
              backgroundColor: leg.bg, border: leg.border,
            }} />
            <span style={{ fontSize: 15, color: MUTED, fontFamily: FONT }}>
              {leg.label}
            </span>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ── Slide 5: Trend Line — evolvePath animation + area fill + staggered dots ──
const TrendLineSlide: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const CHART_LEFT = 280;
  const CHART_RIGHT = 1640;
  const CHART_TOP = 200;
  const CHART_BOTTOM = 780;
  const chartW = CHART_RIGHT - CHART_LEFT;
  const chartH = CHART_BOTTOM - CHART_TOP;
  const minVal = 480;
  const maxVal = 720;

  // Map data to pixel coordinates
  const points = QUARTERLY.map((d, i) => ({
    x: CHART_LEFT + (i / (QUARTERLY.length - 1)) * chartW,
    y: CHART_BOTTOM - ((d.value - minVal) / (maxVal - minVal)) * chartH,
    label: d.q,
    value: d.value,
  }));

  // Build SVG path string
  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
    .join(" ");

  // CAPABILITY: evolvePath animates the line drawing from 0% → 100%
  const lineProgress = interpolate(frame, [20, 120], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });
  const evolved = evolvePath(lineProgress, pathD);

  const gridVals = [500, 550, 600, 650, 700];
  const titleOpacity = interpolate(frame, [0, 25], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      <div style={{
        position: "absolute", top: 50, left: 0, width: 1920,
        display: "flex", justifyContent: "center", alignItems: "center",
        gap: 12, opacity: titleOpacity,
      }}>
        <TrendingUp size={30} color={GREEN} />
        <span style={{ fontSize: 38, color: TEXT, fontFamily: FONT, fontWeight: 700 }}>
          Quarterly Market Growth ($B)
        </span>
      </div>

      {/* Y-axis grid */}
      {gridVals.map((val) => {
        const y = CHART_BOTTOM - ((val - minVal) / (maxVal - minVal)) * chartH;
        return (
          <React.Fragment key={val}>
            <div style={{
              position: "absolute", left: CHART_LEFT, top: y,
              width: chartW, height: 1, backgroundColor: `${DIM}15`,
            }} />
            <div style={{
              position: "absolute", left: CHART_LEFT - 50, top: y - 9,
              fontSize: 13, color: DIM, fontFamily: FONT,
              textAlign: "right", width: 40,
            }}>
              ${val}
            </div>
          </React.Fragment>
        );
      })}

      {/* X-axis labels — staggered fade-in */}
      {points.map((p, i) => (
        <div key={p.label} style={{
          position: "absolute", left: p.x, top: CHART_BOTTOM + 16,
          transform: "translateX(-50%)",
          fontSize: 14, color: DIM, fontFamily: FONT,
          opacity: interpolate(frame - (20 + i * 12), [0, 15], [0, 1], {
            extrapolateLeft: "clamp", extrapolateRight: "clamp",
          }),
        }}>
          {p.label}
        </div>
      ))}

      {/* Baseline */}
      <div style={{
        position: "absolute", left: CHART_LEFT, top: CHART_BOTTOM,
        width: chartW, height: 2, backgroundColor: `${DIM}40`,
      }} />

      {/* Animated SVG line + area fill */}
      <svg style={{
        position: "absolute", top: 0, left: 0,
        width: 1920, height: 1080, pointerEvents: "none",
      }}>
        {/* Semi-transparent area fill under the line */}
        <path
          d={`${pathD} L ${points[points.length - 1].x} ${CHART_BOTTOM} L ${points[0].x} ${CHART_BOTTOM} Z`}
          fill={`${GREEN}08`}
          strokeDasharray={evolved.strokeDasharray}
          strokeDashoffset={evolved.strokeDashoffset}
          opacity={lineProgress}
        />
        {/* The line itself */}
        <path
          d={pathD} fill="none" stroke={GREEN} strokeWidth={3}
          strokeDasharray={evolved.strokeDasharray}
          strokeDashoffset={evolved.strokeDashoffset}
          strokeLinecap="round" strokeLinejoin="round"
        />
      </svg>

      {/* Data point dots — pop in AFTER the line passes each point */}
      {points.map((p, i) => {
        const pointProgress = i / (points.length - 1);
        const dotScale = spring({
          frame: frame - (20 + pointProgress * 100 + 15), fps,
          config: { damping: 12, stiffness: 180 },
        });
        const labelOpacity = interpolate(
          frame - (20 + pointProgress * 100 + 30), [0, 20], [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );

        return (
          <React.Fragment key={p.label}>
            <div style={{
              position: "absolute", left: p.x, top: p.y,
              width: 14, height: 14, borderRadius: 7,
              backgroundColor: GREEN, border: `3px solid ${BG}`,
              transform: `translate(-50%, -50%) scale(${dotScale})`,
              boxShadow: `0 0 10px ${GREEN}40`,
            }} />
            <div style={{
              position: "absolute", left: p.x, top: p.y - 30,
              transform: "translateX(-50%)",
              fontSize: 14, color: TEXT, fontFamily: FONT,
              fontWeight: 600, opacity: labelOpacity,
            }}>
              ${p.value}B
            </div>
          </React.Fragment>
        );
      })}

      {/* Growth callout — appears after line finishes drawing */}
      <div style={{
        position: "absolute", right: 120, top: 180,
        opacity: interpolate(frame, [130, 155], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        }),
        display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4,
      }}>
        <span style={{ fontSize: 16, color: DIM, fontFamily: FONT }}>
          7-quarter growth
        </span>
        <span style={{ fontSize: 42, color: GREEN, fontFamily: FONT, fontWeight: 700 }}>
          +30.8%
        </span>
      </div>
    </AbsoluteFill>
  );
};

// ── Slide 6: Key Takeaways — StaggeredMotion + CheckCircle icons ──
const TakeawaysSlide: React.FC = () => (
  <AbsoluteFill style={{
    background: `linear-gradient(135deg, ${SURFACE} 0%, ${BG} 100%)`,
  }}>
    <div style={{
      position: "absolute", top: 60, left: 0, width: 1920,
      display: "flex", flexDirection: "column", alignItems: "center",
    }}>
      <AnimatedText
        transition={{ y: [20, 0], opacity: [0, 1], duration: 35 }}
        style={{ fontSize: 44, color: TEXT, fontFamily: FONT, fontWeight: 700 }}
      >
        Key Takeaways
      </AnimatedText>
    </div>

    <div style={{ position: "absolute", top: 200, left: 380, width: 1160 }}>
      {/* CAPABILITY: StaggeredMotion wraps children and animates them
          one-by-one with configurable stagger delay. x: [-40, 0] slides from left. */}
      <StaggeredMotion
        transition={{
          x: [-40, 0], opacity: [0, 1],
          stagger: 20, duration: 25, delay: 20,
        }}
      >
        {TAKEAWAYS.map((text) => (
          <div key={text} style={{
            display: "flex", alignItems: "center", gap: 20,
            marginBottom: 28, padding: "24px 30px",
            backgroundColor: `${BLUE}08`,
            border: `1px solid ${BLUE}20`, borderRadius: 14,
          }}>
            <CheckCircle size={28} color={GREEN} style={{ flexShrink: 0 }} />
            <span style={{ fontSize: 24, color: TEXT, fontFamily: FONT }}>
              {text}
            </span>
          </div>
        ))}
      </StaggeredMotion>
    </div>

    <div style={{
      position: "absolute", bottom: 50, left: 0, width: 1920,
      textAlign: "center",
    }}>
      <AnimatedText
        transition={{ opacity: [0, 1], duration: 25, delay: 100 }}
        style={{ fontSize: 16, color: DIM, fontFamily: FONT }}
      >
        Source: Synergy Research Group, Gartner, IDC 2025 Reports
      </AnimatedText>
    </div>
  </AbsoluteFill>
);
```
