# Example: Focused Scenes via Series — "The AI Revolution"

## Architecture

This example demonstrates the **Focused Scenes via Series** architecture:
- 7 self-contained scene components composed with `<Series>`.
- `useCurrentFrame()` resets to 0 per scene — all timing is local.
- No cross-scene state. Each scene has its own DotGrid, gradient background, and layout.
- Every scene fades in over the first 15 frames (`sceneOpacity`) for smooth transitions.
- Total: 1890 frames / 63 seconds.

## Capabilities Demonstrated

| Capability | Where Used |
|---|---|
| `loadFont` from `@remotion/google-fonts/Inter` | Font loading at module level |
| `AnimatedText` | Title scenes (word split, stagger) |
| `AnimatedCounter` | Stats scene (counting up values), donut center |
| `StaggeredMotion` | Neural net captions, summary checklist |
| `Connector` (straight) | Timeline arms, applications hub |
| `Connector` (curved + labeled) | Neural net flow arrows, market chart bridge |
| `evolvePath` | Timeline vertical line, neural net bezier connections, market line chart |
| `Circle` from `@remotion/shapes` | Neural net nodes |
| `circlePoints` | Output neuron orbital indicators |
| `distributeX` | Layer horizontal spacing |
| `distributeY` | Node vertical spacing |
| `gridPositions` | Stats grid (3×2), applications grid (3×3) |
| `makeTransform` + `scale` + `translateY` | Applications card hover animation |
| `interpolateColors` | Node color shift on data flow pulse |
| `spring` / `interpolate` / `Easing` | Throughout all scenes |
| `Series` / `Sequence` | Scene structure + delayed elements within scenes |
| `DotGrid` | Background texture on every scene |
| `FloatingParticles` | Title and summary atmospheric particles |
| `GradientText` | Summary emphasis text |
| `ProgressRing` | Stats scene circular indicators |
| Donut chart (SVG) | Market segments with animated segments |
| Line chart with area fill | Market growth data with evolvePath |
| Looping animation (modulo) | Neural net data flow pulse dots |
| Hub-and-spoke Connectors | Applications grid center-to-edges |
| 3-layer z-index | Neural net scene (connections z:1, nodes z:2, flow z:3) |
| Scene fade-in (`sceneOpacity`) | Every scene fades in over 15 frames for smooth transitions |
| lucide-react icons (20+) | Every scene uses contextual icons |

## Scene Inventory

| Scene | Duration | Content |
|---|---|---|
| 1. Title | 240 frames (8s) | Brain icon, AnimatedText "The AI Revolution", gradient underline, subtitle, year badge, FloatingParticles |
| 2. Timeline | 300 frames (10s) | Vertical line (evolvePath + gradient), 6 milestone cards alternating L/R, Connector arms, dots on timeline |
| 3. Statistics | 240 frames (8s) | 3×2 grid (gridPositions), AnimatedCounter per stat, ProgressRing + icon per card |
| 4. Neural Network | 360 frames (12s) | 4-layer network, Circle nodes (interpolateColors), bezier connections (evolvePath), curved Connectors between layers, circlePoints orbital dots, looping data flow pulse |
| 5. Market Growth | 300 frames (10s) | Line chart (evolvePath + area fill), donut chart (animated segments), Connector bridge between charts, AnimatedCounter in donut center |
| 6. Applications | 240 frames (8s) | 3×3 grid (gridPositions), icon cards with tag badges, hub Connectors from center, makeTransform hover animation |
| 7. Summary | 210 frames (7s) | AnimatedText title, gradient underline, StaggeredMotion checklist with CheckCircle icons, FloatingParticles, tagline |

## Full Code

```tsx
/**
 * "The AI Revolution: From Research to Reality"
 *
 * Architecture: FOCUSED SCENES VIA SERIES
 * Each Series.Sequence is a self-contained scene with its own layout.
 * useCurrentFrame() resets to 0 per scene — simple local timing.
 * No cross-scene state, no global frame tracking.
 *
 * Scene 1: Title                    240 frames  (8s)
 * Scene 2: Timeline of Milestones   300 frames  (10s)
 * Scene 3: Key Statistics            240 frames  (8s)
 * Scene 4: Neural Network Diagram   360 frames  (12s)
 * Scene 5: Market Growth Charts     300 frames  (10s)
 * Scene 6: AI Applications Grid     240 frames  (8s)
 * Scene 7: Summary & Takeaways      210 frames  (7s)
 *
 * Total: 1890 frames / 63s
 */
import React from "react";
import {
  AbsoluteFill,
  Series,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  interpolateColors,
  spring,
  Easing,
} from "remotion";
import { AnimatedText, AnimatedCounter, StaggeredMotion } from "remotion-bits";
import { evolvePath } from "@remotion/paths";
import { makeTransform, scale, translateY } from "@remotion/animation-utils";
import { loadFont } from "@remotion/google-fonts/Inter";
import { Circle } from "@remotion/shapes";
import { Connector } from "../toolkit/Connector";
import { distributeX, distributeY, gridPositions, circlePoints } from "../toolkit/layout";
import {
  Brain,
  Cpu,
  Sparkles,
  TrendingUp,
  Globe,
  DollarSign,
  Users,
  Zap,
  Eye,
  MessageSquare,
  Car,
  Stethoscope,
  Palette,
  Shield,
  Code,
  BarChart3,
  PieChart,
  CheckCircle,
  ArrowRight,
  Layers,
  Network,
  Bot,
  Rocket,
  Calendar,
  Award,
  Lightbulb,
} from "lucide-react";

// ── Palette ──
const BG = "#0f172a";
const SURFACE = "#1e293b";
const TEXT = "#f8fafc";
const MUTED = "#94a3b8";
const DIM = "#475569";
const BLUE = "#3b82f6";
const GREEN = "#22c55e";
const AMBER = "#f59e0b";
const PURPLE = "#8b5cf6";
const CYAN = "#06b6d4";
const ROSE = "#f43f5e";

const { fontFamily: FONT } = loadFont();

// ── Shared inline components ──

const DotGrid: React.FC<{ opacity?: number }> = ({ opacity = 0.03 }) => (
  <svg
    style={{
      position: "absolute",
      top: 0,
      left: 0,
      width: 1920,
      height: 1080,
      opacity,
      pointerEvents: "none",
    }}
  >
    {Array.from({ length: 40 }, (_, i) =>
      Array.from({ length: 22 }, (_, j) => (
        <circle key={`${i}-${j}`} cx={48 * i} cy={48 * j} r={1.5} fill="#fff" />
      )),
    )}
  </svg>
);

const FloatingParticles: React.FC = () => {
  const frame = useCurrentFrame();
  const particles = [
    { x: 150, y: 200, r: 3, speed: 0.008, offset: 0 },
    { x: 400, y: 800, r: 2, speed: 0.012, offset: 1.5 },
    { x: 700, y: 150, r: 4, speed: 0.006, offset: 3 },
    { x: 1100, y: 900, r: 2.5, speed: 0.01, offset: 0.8 },
    { x: 1400, y: 300, r: 3, speed: 0.009, offset: 2 },
    { x: 1700, y: 700, r: 2, speed: 0.011, offset: 4 },
    { x: 300, y: 500, r: 3.5, speed: 0.007, offset: 1 },
    { x: 1600, y: 100, r: 2, speed: 0.013, offset: 3.5 },
  ];

  return (
    <>
      {particles.map((p, i) => {
        const yOff = Math.sin(frame * p.speed + p.offset) * 30;
        const xOff = Math.cos(frame * p.speed * 0.7 + p.offset) * 15;
        const op = interpolate(
          Math.sin(frame * p.speed * 0.5 + p.offset),
          [-1, 1],
          [0.03, 0.12],
        );
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: p.x + xOff,
              top: p.y + yOff,
              width: p.r * 2,
              height: p.r * 2,
              borderRadius: p.r,
              backgroundColor: BLUE,
              opacity: op,
              boxShadow: `0 0 ${p.r * 4}px ${BLUE}40`,
              pointerEvents: "none",
            }}
          />
        );
      })}
    </>
  );
};

const GradientText: React.FC<{
  children: string;
  from: string;
  to: string;
  style?: React.CSSProperties;
}> = ({ children, from, to, style }) => (
  <span
    style={{
      background: `linear-gradient(135deg, ${from}, ${to})`,
      WebkitBackgroundClip: "text",
      WebkitTextFillColor: "transparent",
      backgroundClip: "text",
      ...style,
    }}
  >
    {children}
  </span>
);

const ProgressRing: React.FC<{
  progress: number;
  radius: number;
  stroke: number;
  color: string;
  x: number;
  y: number;
}> = ({ progress, radius, stroke, color, x, y }) => {
  const circ = 2 * Math.PI * radius;
  return (
    <svg
      style={{
        position: "absolute",
        left: x - radius - stroke / 2,
        top: y - radius - stroke / 2,
        width: (radius + stroke / 2) * 2,
        height: (radius + stroke / 2) * 2,
        pointerEvents: "none",
      }}
    >
      <circle
        cx={radius + stroke / 2}
        cy={radius + stroke / 2}
        r={radius}
        fill="none"
        stroke={`${color}20`}
        strokeWidth={stroke}
      />
      <circle
        cx={radius + stroke / 2}
        cy={radius + stroke / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeDasharray={`${circ * progress} ${circ}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${radius + stroke / 2} ${radius + stroke / 2})`}
      />
    </svg>
  );
};

// ═══════════════════════════════════════════════════════════════════════
// MAIN COMPOSITION — Series of focused scenes
// ═══════════════════════════════════════════════════════════════════════

export const AIRevolution: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: BG }}>
    <Series>
      <Series.Sequence durationInFrames={240}>
        <TitleScene />
      </Series.Sequence>
      <Series.Sequence durationInFrames={300}>
        <TimelineScene />
      </Series.Sequence>
      <Series.Sequence durationInFrames={240}>
        <StatsScene />
      </Series.Sequence>
      <Series.Sequence durationInFrames={360}>
        <NeuralNetScene />
      </Series.Sequence>
      <Series.Sequence durationInFrames={300}>
        <MarketGrowthScene />
      </Series.Sequence>
      <Series.Sequence durationInFrames={240}>
        <ApplicationsScene />
      </Series.Sequence>
      <Series.Sequence durationInFrames={210}>
        <SummaryScene />
      </Series.Sequence>
    </Series>
  </AbsoluteFill>
);

// ═══════════════════════════════════════════════════════════════════════
// SCENE 1: TITLE
// Tools: AnimatedText, GradientText, DotGrid, FloatingParticles,
//        animated underline, lucide icon, spring scale
// ═══════════════════════════════════════════════════════════════════════

const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sceneOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const iconScale = spring({ frame, fps, delay: 5, config: { damping: 12 } });
  const lineW = interpolate(frame, [40, 80], [0, 320], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const subtitleOp = interpolate(frame, [60, 90], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const yearOp = interpolate(frame, [100, 130], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 40%, #1e1b4b 0%, ${BG} 70%)`,
        opacity: sceneOpacity,
      }}
    >
      <DotGrid />
      <FloatingParticles />

      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* Icon with glow */}
        <div
          style={{
            transform: `scale(${iconScale})`,
            marginBottom: 30,
          }}
        >
          <div
            style={{
              width: 100,
              height: 100,
              borderRadius: 28,
              backgroundColor: `${PURPLE}15`,
              border: `2px solid ${PURPLE}40`,
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              boxShadow: `0 0 60px ${PURPLE}20`,
            }}
          >
            <Brain size={52} color={PURPLE} />
          </div>
        </div>

        {/* Title with gradient */}
        <AnimatedText
          transition={{
            y: [40, 0],
            opacity: [0, 1],
            split: "word",
            splitStagger: 5,
            duration: 35,
          }}
          style={{
            fontSize: 76,
            fontFamily: FONT,
            fontWeight: 700,
            textAlign: "center",
            maxWidth: 1600,
          }}
        >
          The AI Revolution
        </AnimatedText>

        {/* Animated underline */}
        <div
          style={{
            width: lineW,
            height: 4,
            borderRadius: 2,
            marginTop: 20,
            marginBottom: 20,
            background: `linear-gradient(90deg, ${PURPLE}, ${CYAN})`,
          }}
        />

        {/* Subtitle */}
        <div style={{ opacity: subtitleOp }}>
          <AnimatedText
            transition={{ opacity: [0, 1], duration: 25, delay: 60 }}
            style={{
              fontSize: 30,
              color: MUTED,
              fontFamily: FONT,
              textAlign: "center",
            }}
          >
            From Research Labs to Everyday Reality
          </AnimatedText>
        </div>

        {/* Year badge */}
        <div
          style={{
            marginTop: 40,
            opacity: yearOp,
            display: "flex",
            alignItems: "center",
            gap: 10,
            backgroundColor: `${AMBER}10`,
            border: `1px solid ${AMBER}30`,
            padding: "8px 24px",
            borderRadius: 20,
          }}
        >
          <Calendar size={18} color={AMBER} />
          <span
            style={{
              fontSize: 16,
              color: AMBER,
              fontFamily: FONT,
              fontWeight: 600,
              letterSpacing: 1,
            }}
          >
            2024 — 2025 LANDSCAPE
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════════════════
// SCENE 2: TIMELINE OF MILESTONES
// Tools: vertical timeline layout, StaggeredMotion, icons, badges,
//        animated connecting line (evolvePath), spring pop-ins
// ═══════════════════════════════════════════════════════════════════════

const MILESTONES = [
  { year: "1956", label: "Dartmouth Workshop", desc: "AI coined as a field", icon: Lightbulb, color: AMBER },
  { year: "1997", label: "Deep Blue", desc: "Beats chess champion Kasparov", icon: Award, color: BLUE },
  { year: "2012", label: "AlexNet", desc: "Deep learning revolution begins", icon: Layers, color: PURPLE },
  { year: "2017", label: "Transformers", desc: "Attention Is All You Need paper", icon: Zap, color: CYAN },
  { year: "2022", label: "ChatGPT", desc: "AI becomes mainstream", icon: MessageSquare, color: GREEN },
  { year: "2024", label: "Multimodal AI", desc: "Vision, audio, code, reasoning", icon: Sparkles, color: ROSE },
];

const TimelineScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sceneOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const TIMELINE_X = 960;
  const START_Y = 160;
  const STEP_Y = 130;
  const CARD_W = 500;

  // Animated vertical line using evolvePath
  const lineEndY = START_Y + STEP_Y * (MILESTONES.length - 1);
  const timelinePathD = `M ${TIMELINE_X} ${START_Y} L ${TIMELINE_X} ${lineEndY}`;
  const lineProgress = interpolate(frame, [20, 150], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const evolvedLine = evolvePath(lineProgress, timelinePathD);

  const titleOp = interpolate(frame, [0, 25], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, ${BG} 0%, #0c1222 100%)`,
        opacity: sceneOpacity,
      }}
    >
      <DotGrid />

      {/* Scene title */}
      <div
        style={{
          position: "absolute",
          top: 40,
          left: 0,
          width: 1920,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          gap: 12,
          opacity: titleOp,
        }}
      >
        <Calendar size={28} color={CYAN} />
        <span style={{ fontSize: 38, color: TEXT, fontFamily: FONT, fontWeight: 700 }}>
          Milestones That Shaped AI
        </span>
      </div>

      {/* Animated vertical line using evolvePath */}
      <svg
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: 1920,
          height: 1080,
          pointerEvents: "none",
        }}
      >
        <defs>
          <linearGradient id="timelineGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CYAN} />
            <stop offset="100%" stopColor={PURPLE} />
          </linearGradient>
        </defs>
        <path
          d={timelinePathD}
          fill="none"
          stroke="url(#timelineGrad)"
          strokeWidth={3}
          strokeDasharray={evolvedLine.strokeDasharray}
          strokeDashoffset={evolvedLine.strokeDashoffset}
          strokeLinecap="round"
        />
      </svg>

      {/* Milestone entries with Connector arms */}
      {MILESTONES.map((m, i) => {
        const entryScale = spring({
          frame,
          fps,
          delay: 30 + i * 25,
          config: { damping: 14, stiffness: 120 },
        });
        const y = START_Y + i * STEP_Y;
        const isRight = i % 2 === 0;

        return (
          <React.Fragment key={m.year}>
            {/* Connector arm from timeline dot to card */}
            <Connector
              from={[TIMELINE_X, y]}
              to={[isRight ? TIMELINE_X + 38 : TIMELINE_X - 38, y]}
              color={m.color}
              strokeWidth={2}
              delay={30 + i * 25 + 5}
              duration={15}
            />

            {/* Dot on timeline */}
            <div
              style={{
                position: "absolute",
                left: TIMELINE_X - 8,
                top: y - 8,
                width: 18,
                height: 18,
                borderRadius: 9,
                backgroundColor: m.color,
                border: `3px solid ${BG}`,
                boxShadow: `0 0 12px ${m.color}50`,
                transform: `scale(${entryScale})`,
                zIndex: 2,
              }}
            />

            {/* Content card */}
            <div
              style={{
                position: "absolute",
                left: isRight ? TIMELINE_X + 40 : TIMELINE_X - 40 - CARD_W,
                top: y - 35,
                opacity: entryScale,
                transform: `translateX(${isRight ? (1 - entryScale) * 30 : -(1 - entryScale) * 30}px)`,
                display: "flex",
                alignItems: "center",
                gap: 16,
                backgroundColor: `${SURFACE}cc`,
                border: `1px solid ${m.color}25`,
                borderRadius: 14,
                padding: "14px 22px",
                width: CARD_W,
              }}
            >
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  backgroundColor: `${m.color}15`,
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  flexShrink: 0,
                }}
              >
                <m.icon size={24} color={m.color} />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span
                    style={{
                      fontSize: 14,
                      color: m.color,
                      fontFamily: FONT,
                      fontWeight: 700,
                      backgroundColor: `${m.color}15`,
                      padding: "2px 10px",
                      borderRadius: 6,
                    }}
                  >
                    {m.year}
                  </span>
                  <span style={{ fontSize: 18, color: TEXT, fontFamily: FONT, fontWeight: 600 }}>
                    {m.label}
                  </span>
                </div>
                <span style={{ fontSize: 14, color: MUTED, fontFamily: FONT }}>
                  {m.desc}
                </span>
              </div>
            </div>
          </React.Fragment>
        );
      })}

      {/* "And it's accelerating…" callout */}
      <div
        style={{
          position: "absolute",
          bottom: 50,
          right: 120,
          opacity: interpolate(frame, [220, 260], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <Rocket size={22} color={AMBER} />
        <span style={{ fontSize: 20, color: AMBER, fontFamily: FONT, fontWeight: 600 }}>
          And it's accelerating…
        </span>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════════════════
// SCENE 3: KEY STATISTICS
// Tools: gridPositions, AnimatedCounter, ProgressRing, stat cards,
//        spring stagger, icons in containers
// ═══════════════════════════════════════════════════════════════════════

const STATS = [
  { icon: Globe, label: "AI Companies", value: 68000, suffix: "+", color: BLUE, pct: 0.85 },
  { icon: DollarSign, label: "Global AI Market ($B)", value: 305, suffix: "", color: GREEN, pct: 0.72 },
  { icon: Users, label: "AI Developers", value: 4, suffix: "M+", color: PURPLE, pct: 0.65 },
  { icon: Cpu, label: "GPU Compute (exaFLOPS)", value: 12, suffix: "", color: CYAN, pct: 0.91 },
  { icon: Code, label: "Open Source Models", value: 950, suffix: "K+", color: AMBER, pct: 0.78 },
  { icon: TrendingUp, label: "YoY Growth", value: 37, suffix: "%", color: ROSE, pct: 0.37 },
];

const StatsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sceneOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const cells = gridPositions(6, 3, 540, 320, 160, 200);

  const titleOp = interpolate(frame, [0, 25], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, ${BG} 0%, #0c1222 100%)`,
        opacity: sceneOpacity,
      }}
    >
      <DotGrid />

      <div
        style={{
          position: "absolute",
          top: 40,
          left: 0,
          width: 1920,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          gap: 12,
          opacity: titleOp,
        }}
      >
        <BarChart3 size={28} color={GREEN} />
        <span style={{ fontSize: 38, color: TEXT, fontFamily: FONT, fontWeight: 700 }}>
          AI by the Numbers (2025)
        </span>
      </div>

      {STATS.map((stat, i) => {
        const s = spring({
          frame,
          fps,
          delay: 20 + i * 14,
          config: { damping: 14, stiffness: 100 },
        });
        const cell = cells[i];
        const ringProgress = spring({
          frame,
          fps,
          delay: 40 + i * 14,
          config: { damping: 200 },
        });

        return (
          <div
            key={stat.label}
            style={{
              position: "absolute",
              left: cell.x,
              top: cell.y,
              transform: `translate(-50%, -50%) scale(${s})`,
              opacity: s,
              width: 460,
              display: "flex",
              alignItems: "center",
              gap: 20,
              padding: "24px 28px",
              backgroundColor: `${SURFACE}cc`,
              borderRadius: 18,
              border: `1px solid ${stat.color}25`,
            }}
          >
            {/* Progress ring + icon */}
            <div style={{ position: "relative", width: 70, height: 70, flexShrink: 0 }}>
              <ProgressRing
                progress={stat.pct * ringProgress}
                radius={30}
                stroke={5}
                color={stat.color}
                x={35}
                y={35}
              />
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                }}
              >
                <stat.icon size={26} color={stat.color} />
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <AnimatedCounter
                transition={{
                  values: [0, stat.value],
                  duration: 70,
                  delay: 30 + i * 14,
                }}
                postfix={
                  <span style={{ fontSize: 20, color: MUTED, fontFamily: FONT }}>
                    {stat.suffix}
                  </span>
                }
                style={{ fontSize: 40, color: TEXT, fontFamily: FONT, fontWeight: 700 }}
              />
              <span style={{ fontSize: 15, color: MUTED, fontFamily: FONT }}>
                {stat.label}
              </span>
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════════════════
// SCENE 4: NEURAL NETWORK DIAGRAM
// Tools: circlePoints for node layout, Connector (curved), distributeX,
//        z-index layering, data flow animation, HealthDot pulse
// ═══════════════════════════════════════════════════════════════════════

const LAYER_NAMES = ["Input", "Hidden 1", "Hidden 2", "Output"];
const LAYER_SIZES = [4, 6, 6, 3];
const LAYER_COLORS = [BLUE, PURPLE, CYAN, GREEN];

const NeuralNetScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sceneOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const layerXs = distributeX(4, 300, 1620);
  const NODE_R = 20;
  const AREA_TOP = 240;
  const AREA_BOTTOM = 820;

  const titleOp = interpolate(frame, [0, 25], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, ${BG} 0%, #0c1222 100%)`,
        opacity: sceneOpacity,
      }}
    >
      <DotGrid opacity={0.02} />

      {/* Title */}
      <div
        style={{
          position: "absolute",
          top: 35,
          left: 0,
          width: 1920,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          gap: 12,
          opacity: titleOp,
        }}
      >
        <Network size={28} color={PURPLE} />
        <span style={{ fontSize: 38, color: TEXT, fontFamily: FONT, fontWeight: 700 }}>
          Inside a Neural Network
        </span>
      </div>

      {/* Layer labels */}
      {LAYER_NAMES.map((name, li) => {
        const labelOp = interpolate(frame - (15 + li * 20), [0, 20], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
          <div
            key={name}
            style={{
              position: "absolute",
              left: layerXs[li],
              top: AREA_TOP - 50,
              transform: "translateX(-50%)",
              fontSize: 15,
              color: LAYER_COLORS[li],
              fontFamily: FONT,
              fontWeight: 600,
              opacity: labelOp,
              textTransform: "uppercase",
              letterSpacing: 1,
            }}
          >
            {name}
          </div>
        );
      })}

      {/* Layer-to-layer directional Connectors (z:1) — curved arrows between layers */}
      {LAYER_NAMES.slice(0, -1).map((_, li) => (
        <Connector
          key={`layer-conn-${li}`}
          from={[layerXs[li] + 35, AREA_TOP - 55]}
          to={[layerXs[li + 1] - 35, AREA_TOP - 55]}
          curved
          color={LAYER_COLORS[li]}
          strokeWidth={2}
          delay={40 + li * 50}
          duration={35}
          label={li === 0 ? "Forward" : li === 1 ? "Transform" : "Classify"}
        />
      ))}

      {/* Connection paths (z:1) — animated SVG paths using evolvePath */}
      <div style={{ position: "absolute", inset: 0, zIndex: 1 }}>
        <svg
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: 1920,
            height: 1080,
            pointerEvents: "none",
          }}
        >
          {LAYER_SIZES.slice(0, -1).map((srcCount, li) => {
            const dstCount = LAYER_SIZES[li + 1];
            const srcYs = distributeY(srcCount, AREA_TOP, AREA_BOTTOM);
            const dstYs = distributeY(dstCount, AREA_TOP, AREA_BOTTOM);
            const connDelay = 60 + li * 50;

            return srcYs.map((sy, si) =>
              dstYs.map((dy, di) => {
                const pathD = `M ${layerXs[li]} ${sy} C ${layerXs[li] + 100} ${sy}, ${layerXs[li + 1] - 100} ${dy}, ${layerXs[li + 1]} ${dy}`;
                const progress = interpolate(
                  frame - (connDelay + si * 2 + di),
                  [0, 40],
                  [0, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                );
                if (progress <= 0) return null;
                const evolved = evolvePath(progress, pathD);
                return (
                  <path
                    key={`${li}-${si}-${di}`}
                    d={pathD}
                    fill="none"
                    stroke={LAYER_COLORS[li]}
                    strokeWidth={1.2}
                    strokeDasharray={evolved.strokeDasharray}
                    strokeDashoffset={evolved.strokeDashoffset}
                    strokeLinecap="round"
                    opacity={0.35}
                  />
                );
              }),
            );
          })}
        </svg>
      </div>

      {/* Nodes (z:2) — using @remotion/shapes Circle */}
      <div style={{ position: "absolute", inset: 0, zIndex: 2 }}>
        {LAYER_SIZES.map((count, li) => {
          const ys = distributeY(count, AREA_TOP, AREA_BOTTOM);
          return ys.map((ny, ni) => {
            const nodeScale = spring({
              frame,
              fps,
              delay: 20 + li * 20 + ni * 3,
              config: { damping: 14, stiffness: 150 },
            });
            const pulsePhase = frame > 180
              ? ((frame - 180) % 120) / 120
              : 0;
            const layerActivation = Math.max(0, 1 - Math.abs(pulsePhase - li / 3) * 4);
            const nodeColor = interpolateColors(
              layerActivation,
              [0, 1],
              [LAYER_COLORS[li], AMBER],
            );
            return (
              <div
                key={`n-${li}-${ni}`}
                style={{
                  position: "absolute",
                  left: layerXs[li] - NODE_R,
                  top: ny - NODE_R,
                  transform: `scale(${nodeScale})`,
                  filter: `drop-shadow(0 0 ${6 + layerActivation * 8}px ${nodeColor}${layerActivation > 0.3 ? "60" : "20"})`,
                }}
              >
                <Circle
                  radius={NODE_R}
                  fill={`${LAYER_COLORS[li]}20`}
                  stroke={`${nodeColor}90`}
                  strokeWidth={2}
                />
              </div>
            );
          });
        })}
      </div>

      {/* Output node orbital indicators (z:2) — circlePoints around each output neuron */}
      <div style={{ position: "absolute", inset: 0, zIndex: 2, pointerEvents: "none" }}>
        {frame > 200 &&
          distributeY(LAYER_SIZES[3], AREA_TOP, AREA_BOTTOM).map((ny, ni) => {
            const orbits = circlePoints(5, layerXs[3], ny, NODE_R + 14, -90 + frame * 0.8 + ni * 40);
            const orbitOp = interpolate(frame - (220 + ni * 15), [0, 30], [0, 0.7], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            return orbits.map((pt, pi) => (
              <div
                key={`orbit-${ni}-${pi}`}
                style={{
                  position: "absolute",
                  left: pt.x - 3,
                  top: pt.y - 3,
                  width: 6,
                  height: 6,
                  borderRadius: 3,
                  backgroundColor: GREEN,
                  opacity: orbitOp * (0.4 + 0.6 * Math.sin(frame * 0.05 + pi)),
                  boxShadow: `0 0 6px ${GREEN}50`,
                }}
              />
            ));
          })}
      </div>

      {/* Data flow pulse (z:3) — animated dot flowing through layers */}
      <div style={{ position: "absolute", inset: 0, zIndex: 3, pointerEvents: "none" }}>
        {frame > 180 &&
          [0, 1, 2].map((flowIdx) => {
            const loopFrame = (frame - 180 + flowIdx * 30) % 120;
            const flowX = interpolate(loopFrame, [0, 120], [layerXs[0], layerXs[3]], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const flowY = interpolate(
              loopFrame,
              [0, 40, 80, 120],
              [AREA_TOP + 100, AREA_TOP + 250, AREA_TOP + 150, AREA_TOP + 300],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );
            const flowOp = interpolate(loopFrame, [0, 10, 100, 120], [0, 0.9, 0.9, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });

            return (
              <div
                key={flowIdx}
                style={{
                  position: "absolute",
                  left: flowX,
                  top: flowY,
                  width: 8,
                  height: 8,
                  borderRadius: 4,
                  backgroundColor: AMBER,
                  transform: "translate(-50%, -50%)",
                  boxShadow: `0 0 16px ${AMBER}80`,
                  opacity: flowOp,
                }}
              />
            );
          })}
      </div>

      {/* Caption cards at bottom */}
      <Sequence from={250}>
        <div
          style={{
            position: "absolute",
            bottom: 40,
            left: 0,
            width: 1920,
            display: "flex",
            justifyContent: "center",
            gap: 30,
          }}
        >
          <StaggeredMotion
            transition={{ y: [20, 0], opacity: [0, 1], stagger: 15, duration: 20, delay: 0 }}
          >
            {[
              { label: "Weights adjust via backpropagation", icon: ArrowRight, color: BLUE },
              { label: "Each layer extracts higher-level features", icon: Layers, color: PURPLE },
              { label: "Billions of parameters in modern models", icon: Cpu, color: CYAN },
            ].map((item) => (
              <div
                key={item.label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  backgroundColor: `${SURFACE}cc`,
                  border: `1px solid ${item.color}25`,
                  padding: "10px 18px",
                  borderRadius: 10,
                }}
              >
                <item.icon size={16} color={item.color} />
                <span style={{ fontSize: 14, color: MUTED, fontFamily: FONT }}>
                  {item.label}
                </span>
              </div>
            ))}
          </StaggeredMotion>
        </div>
      </Sequence>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════════════════
// SCENE 5: MARKET GROWTH — Line chart + donut chart side by side
// Tools: evolvePath, SVG donut, animated dots, AnimatedCounter,
//        grid lines, legend, distributeX
// ═══════════════════════════════════════════════════════════════════════

const MARKET_DATA = [
  { year: "2020", value: 62 },
  { year: "2021", value: 93 },
  { year: "2022", value: 136 },
  { year: "2023", value: 197 },
  { year: "2024", value: 244 },
  { year: "2025", value: 305 },
];

const SEGMENTS = [
  { label: "Machine Learning", value: 40, color: BLUE },
  { label: "NLP & LLMs", value: 28, color: PURPLE },
  { label: "Computer Vision", value: 18, color: CYAN },
  { label: "Robotics & Other", value: 14, color: AMBER },
];

const DONUT_R = 120;
const DONUT_SW = 36;
const DONUT_CIRC = 2 * Math.PI * DONUT_R;

const DONUT_ANGLES = (() => {
  const total = SEGMENTS.reduce((s, d) => s + d.value, 0);
  let cum = -90;
  return SEGMENTS.map((d) => {
    const start = cum;
    const arc = (d.value / total) * DONUT_CIRC;
    cum += (d.value / total) * 360;
    return { start, arc };
  });
})();

const MarketGrowthScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sceneOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // --- Line chart (left half) ---
  const CL = 120;
  const CR = 900;
  const CT = 220;
  const CB = 750;
  const cW = CR - CL;
  const cH = CB - CT;
  const minV = 0;
  const maxV = 350;

  const pts = MARKET_DATA.map((d, i) => ({
    x: CL + (i / (MARKET_DATA.length - 1)) * cW,
    y: CB - ((d.value - minV) / (maxV - minV)) * cH,
    label: d.year,
    value: d.value,
  }));

  const pathD = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");

  const lineProgress = interpolate(frame, [30, 140], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });
  const evolved = evolvePath(lineProgress, pathD);

  // --- Donut chart (right half) ---
  const donutCx = 1350;
  const donutCy = 500;

  const titleOp = interpolate(frame, [0, 25], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const gridVals = [0, 100, 200, 300];

  return (
    <AbsoluteFill style={{ backgroundColor: BG, opacity: sceneOpacity }}>
      <DotGrid />

      <div
        style={{
          position: "absolute",
          top: 35,
          left: 0,
          width: 1920,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          gap: 12,
          opacity: titleOp,
        }}
      >
        <TrendingUp size={28} color={GREEN} />
        <span style={{ fontSize: 38, color: TEXT, fontFamily: FONT, fontWeight: 700 }}>
          AI Market Explosion
        </span>
      </div>

      {/* Sub-labels */}
      <div
        style={{
          position: "absolute",
          top: 100,
          left: CL + cW / 2,
          transform: "translateX(-50%)",
          fontSize: 16,
          color: MUTED,
          fontFamily: FONT,
          opacity: titleOp,
        }}
      >
        Global AI Market Size ($B)
      </div>
      <div
        style={{
          position: "absolute",
          top: 100,
          left: donutCx,
          transform: "translateX(-50%)",
          fontSize: 16,
          color: MUTED,
          fontFamily: FONT,
          opacity: titleOp,
        }}
      >
        Market Segments 2025
      </div>

      {/* Grid lines */}
      {gridVals.map((val) => {
        const y = CB - ((val - minV) / (maxV - minV)) * cH;
        return (
          <React.Fragment key={val}>
            <div
              style={{
                position: "absolute",
                left: CL,
                top: y,
                width: cW,
                height: 1,
                backgroundColor: `${DIM}15`,
              }}
            />
            <div
              style={{
                position: "absolute",
                left: CL - 45,
                top: y - 9,
                fontSize: 12,
                color: DIM,
                fontFamily: FONT,
                textAlign: "right",
                width: 35,
              }}
            >
              ${val}B
            </div>
          </React.Fragment>
        );
      })}

      {/* Baseline */}
      <div
        style={{
          position: "absolute",
          left: CL,
          top: CB,
          width: cW,
          height: 2,
          backgroundColor: `${DIM}30`,
        }}
      />

      {/* Animated line + area fill */}
      <svg
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: 1920,
          height: 1080,
          pointerEvents: "none",
        }}
      >
        <path
          d={`${pathD} L ${pts[pts.length - 1].x} ${CB} L ${pts[0].x} ${CB} Z`}
          fill={`${GREEN}08`}
          opacity={lineProgress}
        />
        <path
          d={pathD}
          fill="none"
          stroke={GREEN}
          strokeWidth={3}
          strokeDasharray={evolved.strokeDasharray}
          strokeDashoffset={evolved.strokeDashoffset}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>

      {/* Data dots + labels */}
      {pts.map((p, i) => {
        const pointProg = i / (pts.length - 1);
        const dotScale = spring({
          frame: frame - (30 + pointProg * 110 + 15),
          fps,
          config: { damping: 12, stiffness: 180 },
        });
        const labelOp = interpolate(frame - (30 + pointProg * 110 + 25), [0, 20], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        return (
          <React.Fragment key={p.label}>
            <div
              style={{
                position: "absolute",
                left: p.x,
                top: p.y,
                width: 12,
                height: 12,
                borderRadius: 6,
                backgroundColor: GREEN,
                border: `3px solid ${BG}`,
                transform: `translate(-50%, -50%) scale(${dotScale})`,
                boxShadow: `0 0 8px ${GREEN}40`,
              }}
            />
            <div
              style={{
                position: "absolute",
                left: p.x,
                top: p.y - 26,
                transform: "translateX(-50%)",
                fontSize: 13,
                color: TEXT,
                fontFamily: FONT,
                fontWeight: 600,
                opacity: labelOp,
              }}
            >
              ${p.value}B
            </div>
            <div
              style={{
                position: "absolute",
                left: p.x,
                top: CB + 14,
                transform: "translateX(-50%)",
                fontSize: 12,
                color: DIM,
                fontFamily: FONT,
                opacity: labelOp,
              }}
            >
              {p.label}
            </div>
          </React.Fragment>
        );
      })}

      {/* Connector from last line-chart point to donut — "how the $305B breaks down" */}
      <Connector
        from={[pts[pts.length - 1].x + 20, pts[pts.length - 1].y]}
        to={[donutCx - DONUT_R - DONUT_SW / 2 - 20, donutCy - 40]}
        curved
        color={MUTED}
        strokeWidth={1.5}
        delay={145}
        duration={40}
        label="Segment breakdown"
      />

      {/* Donut chart */}
      <svg
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: 1920,
          height: 1080,
          pointerEvents: "none",
        }}
      >
        {SEGMENTS.map((seg, i) => {
          const da = DONUT_ANGLES[i];
          const progress = spring({
            frame: frame - 40 - i * 15,
            fps,
            config: { damping: 200 },
          });
          return (
            <circle
              key={seg.label}
              cx={donutCx}
              cy={donutCy}
              r={DONUT_R}
              fill="none"
              stroke={seg.color}
              strokeWidth={DONUT_SW}
              strokeDasharray={`${da.arc * progress} ${DONUT_CIRC}`}
              strokeDashoffset={0}
              strokeLinecap="butt"
              transform={`rotate(${da.start} ${donutCx} ${donutCy})`}
              opacity={0.9}
            />
          );
        })}
      </svg>

      {/* Donut center */}
      <div
        style={{
          position: "absolute",
          left: donutCx,
          top: donutCy,
          transform: "translate(-50%, -50%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <AnimatedCounter
          transition={{ values: [0, 305], duration: 80, delay: 50 }}
          prefix={<span style={{ fontSize: 18, color: MUTED }}>$</span>}
          postfix={<span style={{ fontSize: 18, color: MUTED }}>B</span>}
          style={{ fontSize: 36, color: TEXT, fontFamily: FONT, fontWeight: 700 }}
        />
        <span style={{ fontSize: 12, color: DIM, fontFamily: FONT }}>2025 Total</span>
      </div>

      {/* Donut legend */}
      <div
        style={{
          position: "absolute",
          left: donutCx - 190,
          top: donutCy + DONUT_R + 50,
          width: 380,
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          justifyContent: "center",
        }}
      >
        {SEGMENTS.map((seg, i) => (
          <div
            key={seg.label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              opacity: interpolate(frame - (80 + i * 15), [0, 15], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            <div
              style={{
                width: 10,
                height: 10,
                borderRadius: 3,
                backgroundColor: seg.color,
              }}
            />
            <span style={{ fontSize: 12, color: MUTED, fontFamily: FONT }}>
              {seg.label} ({seg.value}%)
            </span>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════════════════
// SCENE 6: AI APPLICATIONS GRID
// Tools: gridPositions, StaggeredMotion, icon cards, badge pills,
//        spring pop-ins, various lucide icons
// ═══════════════════════════════════════════════════════════════════════

const APPS = [
  { label: "Chatbots & Assistants", icon: Bot, color: BLUE, tag: "NLP" },
  { label: "Self-Driving Cars", icon: Car, color: PURPLE, tag: "Vision" },
  { label: "Medical Diagnosis", icon: Stethoscope, color: GREEN, tag: "Healthcare" },
  { label: "Creative AI", icon: Palette, color: ROSE, tag: "Generative" },
  { label: "Cybersecurity", icon: Shield, color: AMBER, tag: "Security" },
  { label: "Code Generation", icon: Code, color: CYAN, tag: "DevTools" },
  { label: "Search & Discovery", icon: Eye, color: BLUE, tag: "Information" },
  { label: "Robotics", icon: Cpu, color: PURPLE, tag: "Hardware" },
  { label: "Language Translation", icon: Globe, color: GREEN, tag: "NLP" },
];

const ApplicationsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sceneOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const cells = gridPositions(9, 3, 520, 260, 180, 200);

  const titleOp = interpolate(frame, [0, 25], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(135deg, ${BG} 0%, #1e1b4b40 50%, ${BG} 100%)`,
        opacity: sceneOpacity,
      }}
    >
      <DotGrid />

      <div
        style={{
          position: "absolute",
          top: 35,
          left: 0,
          width: 1920,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          gap: 12,
          opacity: titleOp,
        }}
      >
        <Sparkles size={28} color={AMBER} />
        <span style={{ fontSize: 38, color: TEXT, fontFamily: FONT, fontWeight: 700 }}>
          AI Is Everywhere
        </span>
      </div>

      {/* Hub connectors from center card (index 4) to surrounding cards (z:1) */}
      {cells
        .filter((_, i) => i !== 4)
        .map((cell, idx) => {
          const centerCell = cells[4];
          const dx = cell.x - centerCell.x;
          const dy = cell.y - centerCell.y;
          const angle = Math.atan2(dy, dx);
          const fromX = centerCell.x + Math.cos(angle) * 60;
          const fromY = centerCell.y + Math.sin(angle) * 60;
          const toX = cell.x - Math.cos(angle) * 60;
          const toY = cell.y - Math.sin(angle) * 60;
          return (
            <Connector
              key={`hub-${idx}`}
              from={[fromX, fromY]}
              to={[toX, toY]}
              color={APPS[idx >= 4 ? idx + 1 : idx].color}
              strokeWidth={1.2}
              delay={90 + idx * 8}
              duration={25}
            />
          );
        })}

      {APPS.map((app, i) => {
        const s = spring({
          frame,
          fps,
          delay: 15 + i * 10,
          config: { damping: 14, stiffness: 120 },
        });
        const cell = cells[i];

        const hoverY = interpolate(
          Math.sin(frame * 0.04 + i * 1.2),
          [-1, 1],
          [-4, 4],
        );

        return (
          <div
            key={app.label}
            style={{
              position: "absolute",
              left: cell.x,
              top: cell.y,
              transform: makeTransform([
                scale(s),
                translateY(hoverY),
              ]),
              marginLeft: -220,
              marginTop: -40,
              opacity: s,
              width: 440,
              display: "flex",
              alignItems: "center",
              gap: 18,
              padding: "20px 24px",
              backgroundColor: `${SURFACE}cc`,
              borderRadius: 16,
              border: `1px solid ${app.color}25`,
              boxShadow: `0 4px 20px rgba(0,0,0,0.3)`,
            }}
          >
            <div
              style={{
                width: 52,
                height: 52,
                borderRadius: 14,
                backgroundColor: `${app.color}15`,
                border: `1px solid ${app.color}25`,
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                flexShrink: 0,
              }}
            >
              <app.icon size={26} color={app.color} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 5, flex: 1 }}>
              <span style={{ fontSize: 17, color: TEXT, fontFamily: FONT, fontWeight: 600 }}>
                {app.label}
              </span>
              <span
                style={{
                  fontSize: 11,
                  color: app.color,
                  fontFamily: FONT,
                  fontWeight: 600,
                  backgroundColor: `${app.color}12`,
                  padding: "2px 8px",
                  borderRadius: 4,
                  alignSelf: "flex-start",
                  textTransform: "uppercase",
                  letterSpacing: 0.5,
                }}
              >
                {app.tag}
              </span>
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════════════════
// SCENE 7: SUMMARY & TAKEAWAYS
// Tools: animated checklist, StaggeredMotion, GradientText,
//        animated underline, final callout
// ═══════════════════════════════════════════════════════════════════════

const TAKEAWAYS = [
  "AI market growing 37% year-over-year, reaching $305B in 2025",
  "Transformer architecture powers modern LLMs, vision, and multimodal AI",
  "Open-source models democratizing access — 950K+ models on Hugging Face",
  "AI embedded in healthcare, transport, security, and creative industries",
  "The pace of innovation is accelerating, not slowing down",
];

const SummaryScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sceneOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const lineW = interpolate(frame, [25, 55], [0, 280], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(135deg, #1e1b4b 0%, ${BG} 50%, #0c1222 100%)`,
        opacity: sceneOpacity,
      }}
    >
      <DotGrid />
      <FloatingParticles />

      {/* Title */}
      <div
        style={{
          position: "absolute",
          top: 60,
          left: 0,
          width: 1920,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <AnimatedText
          transition={{ y: [20, 0], opacity: [0, 1], duration: 30 }}
          style={{ fontSize: 48, color: TEXT, fontFamily: FONT, fontWeight: 700 }}
        >
          Key Takeaways
        </AnimatedText>
        <div
          style={{
            width: lineW,
            height: 3,
            borderRadius: 2,
            marginTop: 16,
            background: `linear-gradient(90deg, ${PURPLE}, ${CYAN})`,
          }}
        />
      </div>

      {/* Checklist */}
      <div style={{ position: "absolute", top: 200, left: 300, width: 1320 }}>
        <StaggeredMotion
          transition={{
            x: [-30, 0],
            opacity: [0, 1],
            stagger: 18,
            duration: 22,
            delay: 30,
          }}
        >
          {TAKEAWAYS.map((text, i) => {
            const checkScale = spring({
              frame,
              fps,
              delay: 50 + i * 18,
              config: { damping: 12, stiffness: 150 },
            });
            const checkColor = [GREEN, BLUE, PURPLE, CYAN, AMBER][i];

            return (
              <div
                key={text}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 18,
                  marginBottom: 22,
                  padding: "18px 26px",
                  backgroundColor: `${checkColor}06`,
                  border: `1px solid ${checkColor}18`,
                  borderRadius: 14,
                }}
              >
                <div
                  style={{
                    transform: `scale(${checkScale})`,
                    flexShrink: 0,
                    marginTop: 2,
                  }}
                >
                  <CheckCircle size={24} color={checkColor} />
                </div>
                <span
                  style={{
                    fontSize: 19,
                    color: TEXT,
                    fontFamily: FONT,
                    lineHeight: 1.5,
                  }}
                >
                  {text}
                </span>
              </div>
            );
          })}
        </StaggeredMotion>
      </div>

      {/* Bottom tagline */}
      <div
        style={{
          position: "absolute",
          bottom: 45,
          left: 0,
          width: 1920,
          display: "flex",
          justifyContent: "center",
          gap: 10,
          alignItems: "center",
          opacity: interpolate(frame, [160, 190], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <Brain size={18} color={PURPLE} />
        <span style={{ fontSize: 15, color: DIM, fontFamily: FONT }}>
          The AI Revolution is not coming — it's already here.
        </span>
      </div>
    </AbsoluteFill>
  );
};
```
