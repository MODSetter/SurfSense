# Toolkit Showcase — Capability Patterns with Variations

Each section below shows a single toolkit capability used in 2–3 different
ways. Copy and adapt these patterns in your scenes.

---

## 1. Connector — Animated Arrows

### Variation A: Straight labeled arrow (diagram flows)

```tsx
<Connector
  from={[400, 440]}
  to={[900, 440]}
  color="#3b82f6"
  strokeWidth={2}
  delay={20}
  duration={50}
  label="HTTP Request"
/>
```

### Variation B: Curved labeled arrow (bridging two chart areas)

```tsx
<Connector
  from={[pts[pts.length - 1].x + 20, pts[pts.length - 1].y]}
  to={[donutCx - 160, donutCy - 40]}
  curved
  color="#94a3b8"
  strokeWidth={1.5}
  delay={145}
  duration={40}
  label="Segment breakdown"
/>
```

### Variation C: Hub-and-spoke (center card to surrounding grid items)

```tsx
const cells = gridPositions(9, 3, 520, 260, 180, 200);
const centerCell = cells[4]; // center of 3×3

{cells
  .filter((_, i) => i !== 4)
  .map((cell, idx) => {
    const dx = cell.x - centerCell.x;
    const dy = cell.y - centerCell.y;
    const angle = Math.atan2(dy, dx);
    return (
      <Connector
        key={`hub-${idx}`}
        from={[
          centerCell.x + Math.cos(angle) * 60,
          centerCell.y + Math.sin(angle) * 60,
        ]}
        to={[
          cell.x - Math.cos(angle) * 60,
          cell.y - Math.sin(angle) * 60,
        ]}
        color={items[idx >= 4 ? idx + 1 : idx].color}
        strokeWidth={1.2}
        delay={90 + idx * 8}
        duration={25}
      />
    );
  })}
```

### Variation D: Short arm connectors (timeline dot → card)

```tsx
{milestones.map((m, i) => {
  const y = START_Y + i * STEP_Y;
  const isRight = i % 2 === 0;
  return (
    <Connector
      key={`arm-${i}`}
      from={[TIMELINE_X, y]}
      to={[isRight ? TIMELINE_X + 38 : TIMELINE_X - 38, y]}
      color={m.color}
      strokeWidth={2}
      delay={30 + i * 25 + 5}
      duration={15}
    />
  );
})}
```

---

## 2. evolvePath — SVG Draw-On Animation

### Variation A: Vertical timeline line with gradient stroke

```tsx
const lineEndY = START_Y + STEP_Y * (items.length - 1);
const pathD = `M ${cx} ${START_Y} L ${cx} ${lineEndY}`;
const lineProgress = interpolate(frame, [20, 150], [0, 1], {
  extrapolateLeft: "clamp", extrapolateRight: "clamp",
  easing: Easing.out(Easing.cubic),
});
const evolved = evolvePath(lineProgress, pathD);

<svg style={{ position: "absolute", inset: 0, width: 1920, height: 1080, pointerEvents: "none" }}>
  <defs>
    <linearGradient id="tlGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor="#06b6d4" />
      <stop offset="100%" stopColor="#8b5cf6" />
    </linearGradient>
  </defs>
  <path d={pathD} fill="none" stroke="url(#tlGrad)" strokeWidth={3}
    strokeDasharray={evolved.strokeDasharray}
    strokeDashoffset={evolved.strokeDashoffset}
    strokeLinecap="round" />
</svg>
```

### Variation B: Line chart with area fill

```tsx
const pts = data.map((d, i) => ({
  x: LEFT + (i / (data.length - 1)) * chartW,
  y: BOTTOM - ((d.value - min) / (max - min)) * chartH,
}));
const pathD = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
const lineProgress = interpolate(frame, [30, 140], [0, 1], {
  extrapolateLeft: "clamp", extrapolateRight: "clamp",
  easing: Easing.out(Easing.quad),
});
const evolved = evolvePath(lineProgress, pathD);

<svg style={{ position: "absolute", inset: 0, width: 1920, height: 1080, pointerEvents: "none" }}>
  {/* Area fill underneath */}
  <path
    d={`${pathD} L ${pts.at(-1)!.x} ${BOTTOM} L ${pts[0].x} ${BOTTOM} Z`}
    fill="#22c55e08" opacity={lineProgress}
  />
  {/* Line */}
  <path d={pathD} fill="none" stroke="#22c55e" strokeWidth={3}
    strokeDasharray={evolved.strokeDasharray}
    strokeDashoffset={evolved.strokeDashoffset}
    strokeLinecap="round" strokeLinejoin="round" />
</svg>
```

### Variation C: Dense bezier connection mesh (neural network style)

```tsx
<svg style={{ position: "absolute", inset: 0, width: 1920, height: 1080, pointerEvents: "none" }}>
  {srcYs.map((sy, si) =>
    dstYs.map((dy, di) => {
      const pathD = `M ${x1} ${sy} C ${x1 + 100} ${sy}, ${x2 - 100} ${dy}, ${x2} ${dy}`;
      const progress = interpolate(
        frame - (connDelay + si * 2 + di), [0, 40], [0, 1],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
      );
      if (progress <= 0) return null;
      const evolved = evolvePath(progress, pathD);
      return (
        <path key={`${si}-${di}`} d={pathD} fill="none"
          stroke={layerColor} strokeWidth={1.2}
          strokeDasharray={evolved.strokeDasharray}
          strokeDashoffset={evolved.strokeDashoffset}
          strokeLinecap="round" opacity={0.35} />
      );
    }),
  )}
</svg>
```

---

## 3. Circle from @remotion/shapes — SVG Nodes

### Variation A: Diagram node with pulse glow

```tsx
import { Circle } from "@remotion/shapes";

const nodeColor = interpolateColors(activation, [0, 1], [LAYER_COLOR, AMBER]);

<div style={{
  position: "absolute",
  left: x - NODE_R, top: y - NODE_R,
  transform: `scale(${nodeScale})`,
  filter: `drop-shadow(0 0 ${6 + activation * 8}px ${nodeColor}60)`,
}}>
  <Circle
    radius={NODE_R}
    fill={`${LAYER_COLOR}20`}
    stroke={`${nodeColor}90`}
    strokeWidth={2}
  />
</div>
```

### Variation B: Decorative accent circles (background)

```tsx
{[200, 350, 500].map((r, i) => (
  <div key={i} style={{
    position: "absolute", left: 960 - r, top: 540 - r,
    opacity: interpolate(frame, [10 + i * 15, 40 + i * 15], [0, 0.06], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    }),
  }}>
    <Circle radius={r} fill="transparent" stroke="#8b5cf615" strokeWidth={1} />
  </div>
))}
```

---

## 4. circlePoints — Radial Layouts

### Variation A: Orbiting indicators around nodes (animated)

```tsx
const orbits = circlePoints(5, nodeX, nodeY, NODE_R + 14, -90 + frame * 0.8);

{orbits.map((pt, pi) => (
  <div key={pi} style={{
    position: "absolute",
    left: pt.x - 3, top: pt.y - 3,
    width: 6, height: 6, borderRadius: 3,
    backgroundColor: "#22c55e",
    opacity: 0.7 * (0.4 + 0.6 * Math.sin(frame * 0.05 + pi)),
    boxShadow: "0 0 6px #22c55e50",
  }} />
))}
```

### Variation B: Static ring of icons

```tsx
const pts = circlePoints(6, 960, 540, 320);

{categories.map((cat, i) => {
  const s = spring({ frame, fps, delay: 20 + i * 12, config: { damping: 14 } });
  return (
    <div key={i} style={{
      position: "absolute", left: pts[i].x, top: pts[i].y,
      transform: `translate(-50%, -50%) scale(${s})`,
      width: 80, height: 80, borderRadius: 20,
      backgroundColor: `${cat.color}15`,
      border: `1px solid ${cat.color}25`,
      display: "flex", justifyContent: "center", alignItems: "center",
    }}>
      <cat.icon size={32} color={cat.color} />
    </div>
  );
})}
```

---

## 5. interpolateColors — Dynamic Color Effects

### Variation A: Node activation pulse (data flow)

```tsx
const pulsePhase = frame > 180 ? ((frame - 180) % 120) / 120 : 0;
const activation = Math.max(0, 1 - Math.abs(pulsePhase - layerIndex / 3) * 4);
const nodeColor = interpolateColors(activation, [0, 1], [LAYER_COLOR, "#f59e0b"]);

// Use in fill, stroke, or boxShadow:
<Circle fill={`${nodeColor}30`} stroke={`${nodeColor}90`} strokeWidth={2} />
```

### Variation B: Background color shift over time

```tsx
const bgColor = interpolateColors(
  frame, [0, 150, 300],
  ["#0f172a", "#1e1b4b", "#0f172a"],
);

<AbsoluteFill style={{ backgroundColor: bgColor }}>
```

### Variation C: Progress-based color scale (green → amber → red)

```tsx
const statusColor = interpolateColors(
  percentage, [0, 0.5, 1],
  ["#22c55e", "#f59e0b", "#f43f5e"],
);
```

---

## 6. makeTransform — Composable Transforms

### Variation A: Scale + hover float (grid cards)

```tsx
import { makeTransform, scale, translateY } from "@remotion/animation-utils";

const s = spring({ frame, fps, delay: 15 + i * 10, config: { damping: 14 } });
const hover = interpolate(Math.sin(frame * 0.04 + i * 1.2), [-1, 1], [-4, 4]);

<div style={{
  position: "absolute", left: cell.x, top: cell.y,
  transform: makeTransform([scale(s), translateY(hover)]),
  marginLeft: -220, marginTop: -40,
}}>
```

### Variation B: Rotate + scale (spinning icon)

```tsx
import { makeTransform, scale, rotate } from "@remotion/animation-utils";

const angle = interpolate(frame, [0, 120], [0, 360], {
  extrapolateLeft: "clamp", extrapolateRight: "clamp",
});
const s = spring({ frame, fps, config: { damping: 20 } });

<div style={{ transform: makeTransform([scale(s), rotate(angle)]) }}>
  <Cpu size={32} color="#06b6d4" />
</div>
```

---

## 7. AnimatedText + AnimatedCounter — Text Animation

### Variation A: Title with word split stagger

```tsx
<AnimatedText
  transition={{
    y: [40, 0], opacity: [0, 1],
    split: "word", splitStagger: 5, duration: 35,
  }}
  style={{
    fontSize: 76, fontFamily: FONT, fontWeight: 700,
    textAlign: "center", maxWidth: 1600,
  }}
>
  The AI Revolution
</AnimatedText>
```

### Variation B: Subtitle with character split

```tsx
<AnimatedText
  transition={{
    opacity: [0, 1], split: "char", splitStagger: 2,
    duration: 40, delay: 50,
  }}
  style={{ fontSize: 28, color: "#94a3b8", fontFamily: FONT }}
>
  From Research Labs to Reality
</AnimatedText>
```

### Variation C: Counter with prefix/postfix

```tsx
<AnimatedCounter
  transition={{ values: [0, 305], duration: 80, delay: 50 }}
  prefix={<span style={{ fontSize: 18, color: "#94a3b8" }}>$</span>}
  postfix={<span style={{ fontSize: 18, color: "#94a3b8" }}>B</span>}
  style={{ fontSize: 36, color: "#f8fafc", fontFamily: FONT, fontWeight: 700 }}
/>
```

### Variation D: Counter for percentage

```tsx
<AnimatedCounter
  transition={{ values: [0, 37], duration: 60, delay: 30 }}
  postfix={<span style={{ fontSize: 20, color: "#94a3b8" }}>%</span>}
  style={{ fontSize: 48, color: "#22c55e", fontFamily: FONT, fontWeight: 700 }}
/>
```

---

## 8. ProgressRing — Circular Progress Indicators

### Usage: Stat card with icon centered inside ring

```tsx
<div style={{ position: "relative", width: 70, height: 70, flexShrink: 0 }}>
  <ProgressRing
    progress={stat.pct * ringProgress}
    radius={30} stroke={5}
    color={stat.color}
    x={35} y={35}
  />
  <div style={{
    position: "absolute", inset: 0,
    display: "flex", justifyContent: "center", alignItems: "center",
  }}>
    <stat.icon size={26} color={stat.color} />
  </div>
</div>
```

---

## 9. Donut Chart — Animated Segments

### Full pattern with pre-computed angles

```tsx
const R = 120, SW = 36, CIRC = 2 * Math.PI * R;

// Pre-compute outside render — NEVER mutate inside .map()
const ANGLES = (() => {
  const total = segments.reduce((s, d) => s + d.value, 0);
  let cum = -90;
  return segments.map((d) => {
    const start = cum;
    const arc = (d.value / total) * CIRC;
    cum += (d.value / total) * 360;
    return { start, arc };
  });
})();

// Render:
<svg style={{ position: "absolute", inset: 0, width: 1920, height: 1080, pointerEvents: "none" }}>
  {segments.map((seg, i) => {
    const progress = spring({
      frame: frame - 40 - i * 15, fps,
      config: { damping: 200 },
    });
    return (
      <circle key={seg.label}
        cx={cx} cy={cy} r={R} fill="none"
        stroke={seg.color} strokeWidth={SW}
        strokeDasharray={`${ANGLES[i].arc * progress} ${CIRC}`}
        strokeDashoffset={0} strokeLinecap="butt"
        transform={`rotate(${ANGLES[i].start} ${cx} ${cy})`}
        opacity={0.9} />
    );
  })}
</svg>

{/* Center label */}
<div style={{
  position: "absolute", left: cx, top: cy,
  transform: "translate(-50%, -50%)",
  display: "flex", flexDirection: "column", alignItems: "center",
}}>
  <AnimatedCounter
    transition={{ values: [0, totalValue], duration: 80, delay: 50 }}
    prefix={<span style={{ fontSize: 18, color: "#94a3b8" }}>$</span>}
    postfix={<span style={{ fontSize: 18, color: "#94a3b8" }}>B</span>}
    style={{ fontSize: 36, color: "#f8fafc", fontFamily: FONT, fontWeight: 700 }}
  />
  <span style={{ fontSize: 12, color: "#475569", fontFamily: FONT }}>
    2025 Total
  </span>
</div>
```

---

## 10. StaggeredMotion — Lists & Grids

### Variation A: Horizontal caption cards

```tsx
<StaggeredMotion
  transition={{ y: [20, 0], opacity: [0, 1], stagger: 15, duration: 20, delay: 0 }}
>
  {items.map((item) => (
    <div key={item.label} style={{
      display: "flex", alignItems: "center", gap: 10,
      backgroundColor: `${SURFACE}cc`,
      border: `1px solid ${item.color}25`,
      padding: "10px 18px", borderRadius: 10,
    }}>
      <item.icon size={16} color={item.color} />
      <span style={{ fontSize: 14, color: "#94a3b8", fontFamily: FONT }}>
        {item.label}
      </span>
    </div>
  ))}
</StaggeredMotion>
```

### Variation B: Vertical checklist with icons

```tsx
<StaggeredMotion
  transition={{ x: [-30, 0], opacity: [0, 1], stagger: 18, duration: 22, delay: 30 }}
>
  {takeaways.map((text, i) => {
    const checkScale = spring({
      frame, fps, delay: 50 + i * 18,
      config: { damping: 12, stiffness: 150 },
    });
    const color = [GREEN, BLUE, PURPLE, CYAN, AMBER][i];
    return (
      <div key={text} style={{
        display: "flex", alignItems: "flex-start", gap: 18,
        marginBottom: 22, padding: "18px 26px",
        backgroundColor: `${color}06`,
        border: `1px solid ${color}18`, borderRadius: 14,
      }}>
        <div style={{ transform: `scale(${checkScale})`, flexShrink: 0, marginTop: 2 }}>
          <CheckCircle size={24} color={color} />
        </div>
        <span style={{ fontSize: 19, color: "#f8fafc", fontFamily: FONT, lineHeight: 1.5 }}>
          {text}
        </span>
      </div>
    );
  })}
</StaggeredMotion>
```

---

## 11. Layout Utilities — Spatial Patterns

### distributeX — horizontal spacing (e.g. layer positions)

```tsx
const layerXs = distributeX(4, 300, 1620);
// → [300, 740, 1180, 1620]
```

### distributeY — vertical spacing (e.g. node rows)

```tsx
const nodeYs = distributeY(6, 240, 820);
// → 6 evenly-spaced Y positions from 240 to 820
```

### gridPositions — 2D grid (e.g. card layouts)

```tsx
const cells = gridPositions(9, 3, 520, 260, 180, 200);
// 3×3 grid: 520px wide cells, 260px tall, starting at (180, 200)
// Center cards with marginLeft: -cellW/2, marginTop: -cellH/2
```

### circlePoints — radial arrangement

```tsx
const pts = circlePoints(8, 960, 540, 300);
// 8 points in a circle, center (960, 540), radius 300
```

---

## 12. Info Card Patterns — Rich Containers

### Variation A: Icon + title + description card

```tsx
<div style={{
  position: "absolute", left: x, top: y,
  width: 460, padding: "20px 24px",
  backgroundColor: `${SURFACE}cc`,
  borderRadius: 16,
  border: `1px solid ${color}25`,
  boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
  display: "flex", alignItems: "center", gap: 18,
}}>
  <div style={{
    width: 52, height: 52, borderRadius: 14,
    backgroundColor: `${color}15`,
    border: `1px solid ${color}25`,
    display: "flex", justifyContent: "center", alignItems: "center",
    flexShrink: 0,
  }}>
    <Icon size={26} color={color} />
  </div>
  <div style={{ display: "flex", flexDirection: "column", gap: 5, flex: 1 }}>
    <span style={{ fontSize: 17, color: TEXT, fontFamily: FONT, fontWeight: 600 }}>
      {title}
    </span>
    <span style={{
      fontSize: 11, color, fontFamily: FONT, fontWeight: 600,
      backgroundColor: `${color}12`, padding: "2px 8px",
      borderRadius: 4, alignSelf: "flex-start",
      textTransform: "uppercase", letterSpacing: 0.5,
    }}>
      {tag}
    </span>
  </div>
</div>
```

### Variation B: Stat card with progress ring

```tsx
<div style={{
  position: "absolute", left: cell.x, top: cell.y,
  transform: `translate(-50%, -50%) scale(${s})`,
  width: 460, padding: "24px 28px",
  backgroundColor: `${SURFACE}cc`, borderRadius: 18,
  border: `1px solid ${stat.color}25`,
  display: "flex", alignItems: "center", gap: 20,
}}>
  <div style={{ position: "relative", width: 70, height: 70, flexShrink: 0 }}>
    <ProgressRing progress={stat.pct * ringProgress} radius={30}
      stroke={5} color={stat.color} x={35} y={35} />
    <div style={{
      position: "absolute", inset: 0,
      display: "flex", justifyContent: "center", alignItems: "center",
    }}>
      <stat.icon size={26} color={stat.color} />
    </div>
  </div>
  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
    <AnimatedCounter
      transition={{ values: [0, stat.value], duration: 70, delay: 30 }}
      postfix={<span style={{ fontSize: 20, color: MUTED }}>{stat.suffix}</span>}
      style={{ fontSize: 40, color: TEXT, fontFamily: FONT, fontWeight: 700 }}
    />
    <span style={{ fontSize: 15, color: MUTED, fontFamily: FONT }}>
      {stat.label}
    </span>
  </div>
</div>
```

### Variation C: Timeline milestone card

```tsx
<div style={{
  position: "absolute",
  left: isRight ? TIMELINE_X + 40 : TIMELINE_X - 40 - CARD_W,
  top: y - 35, opacity: entryScale, width: CARD_W,
  transform: `translateX(${isRight ? (1 - entryScale) * 30 : -(1 - entryScale) * 30}px)`,
  display: "flex", alignItems: "center", gap: 16,
  backgroundColor: `${SURFACE}cc`,
  border: `1px solid ${m.color}25`, borderRadius: 14,
  padding: "14px 22px",
}}>
  <div style={{
    width: 48, height: 48, borderRadius: 12,
    backgroundColor: `${m.color}15`,
    display: "flex", justifyContent: "center", alignItems: "center",
    flexShrink: 0,
  }}>
    <m.icon size={24} color={m.color} />
  </div>
  <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{
        fontSize: 14, color: m.color, fontFamily: FONT, fontWeight: 700,
        backgroundColor: `${m.color}15`, padding: "2px 10px", borderRadius: 6,
      }}>
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
```

---

## 13. Looping Animations — Modulo Patterns

### Data flow pulse through layers

```tsx
{frame > 180 &&
  [0, 1, 2].map((flowIdx) => {
    const loopFrame = (frame - 180 + flowIdx * 30) % 120;
    const flowX = interpolate(loopFrame, [0, 120], [startX, endX], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    });
    const flowY = interpolate(
      loopFrame, [0, 40, 80, 120],
      [y1, y2, y3, y4],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );
    const flowOp = interpolate(
      loopFrame, [0, 10, 100, 120], [0, 0.9, 0.9, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );
    return (
      <div key={flowIdx} style={{
        position: "absolute", left: flowX, top: flowY,
        width: 8, height: 8, borderRadius: 4,
        backgroundColor: "#f59e0b",
        transform: "translate(-50%, -50%)",
        boxShadow: "0 0 16px #f59e0b80",
        opacity: flowOp,
      }} />
    );
  })}
```

---

## 14. Scene Title Pattern — Consistent Header

Every scene should have a title bar in the HEADER zone:

```tsx
const titleOp = interpolate(frame, [0, 25], [0, 1], {
  extrapolateLeft: "clamp", extrapolateRight: "clamp",
});

<div style={{
  position: "absolute", top: 35, left: 0, width: 1920,
  display: "flex", justifyContent: "center", alignItems: "center",
  gap: 12, opacity: titleOp,
}}>
  <Network size={28} color={PURPLE} />
  <span style={{ fontSize: 38, color: TEXT, fontFamily: FONT, fontWeight: 700 }}>
    Inside a Neural Network
  </span>
</div>
```

For title scenes, use AnimatedText with a centered flex container:

```tsx
<div style={{
  position: "absolute", inset: 0,
  display: "flex", flexDirection: "column",
  alignItems: "center", justifyContent: "center",
}}>
  <AnimatedText
    transition={{ y: [40, 0], opacity: [0, 1], split: "word",
                  splitStagger: 5, duration: 35 }}
    style={{ fontSize: 76, fontFamily: FONT, fontWeight: 700,
             textAlign: "center", maxWidth: 1600 }}
  >
    The AI Revolution
  </AnimatedText>
  {/* Animated underline */}
  <div style={{
    width: lineW, height: 4, borderRadius: 2,
    marginTop: 20, marginBottom: 20,
    background: `linear-gradient(90deg, #8b5cf6, #06b6d4)`,
  }} />
</div>
```

---

## 15. loadFont — Proper Font Loading

ALWAYS at the top of your file, outside any component:

```tsx
import { loadFont } from "@remotion/google-fonts/Inter";
const { fontFamily: FONT } = loadFont();
```

Then use `FONT` in every style object:

```tsx
style={{ fontFamily: FONT, fontSize: 38, fontWeight: 700 }}
```

NEVER hardcode `"Inter"` or `"Inter, system-ui, sans-serif"` — always use the
loaded `FONT` variable to guarantee the font is available during rendering.
