# Example: Architecture Diagram — "Microservices Architecture"

## Pattern: LAYERED ADDITIVE BUILD-UP (Pattern A variant)

Elements appear progressively from top to bottom, building a complete
system diagram. All elements persist — the viewer sees the full picture forming.
Use for: system architecture, infrastructure diagrams, network topologies,
deployment diagrams, data flow visualizations.

## Capabilities demonstrated

- **Sequence** for progressive layer reveal (no Scene Replacement)
- **AnimatedText** with word-split for title (remotion-bits)
- **Connector** (inline) — straight and curved SVG arrows between layers
- **distributeX** (inline) — evenly space services horizontally
- **DotGrid** (inline) — subtle background texture
- **spring()** for bouncy service box pop-ins
- **interpolate()** for fades and positioning
- **HealthDot** — pulsing indicator using Math.sin for organic animation
- **RequestFlow** — looping dot that travels through the architecture
- **ServiceBox** (inline) — reusable service card with icon/label/sublabel
- **lucide-react icons** — Globe, Users, ShoppingCart, Package, CreditCard, etc.
- **Fixed Y-tiers** — LB_Y, GATEWAY_Y, SERVICE_Y, QUEUE_Y, DB_Y for vertical layout
- **Multi-layer progressive reveal** — top layers first, connections second

## Scene inventory (what's on screen at each point)

- **Frame 0–110**: Title centered (AnimatedText + underline). Fades out.
- **Frame 60+**: Load Balancer pill appears at top center. PERSISTS.
- **Frame 100+**: API Gateway box appears below LB. PERSISTS.
- **Frame 120+**: LB → Gateway connector draws. PERSISTS.
- **Frame 150+**: 4 Service boxes appear with staggered spring. PERSIST.
- **Frame 220+**: 4 curved connectors draw from Gateway to Services. PERSIST.
- **Frame 260+**: Health dots pulse on each service box. PERSIST.
- **Frame 300+**: Message Queue bar + Service→Queue connectors. PERSIST.
- **Frame 370+**: 4 Database icons appear below queue. PERSIST.
- **Frame 410+**: Service→DB connectors draw. PERSIST.
- **Frame 450+**: Request flow dot starts looping through architecture. PERSISTS.
- **Frame 480+**: Footer description fades in. PERSISTS.

Everything accumulates — nothing disappears (except the initial title).

## Full code

```tsx
import React from "react";
import {
  AbsoluteFill, Sequence, useCurrentFrame, interpolate, spring,
  useVideoConfig,
} from "remotion";
import { AnimatedText } from "remotion-bits";
// CAPABILITY: evolvePath is used inside Connector for animated SVG path drawing.
import { evolvePath } from "@remotion/paths";
import {
  Globe, Users, ShoppingCart, Package, CreditCard,
  Database, MessageSquare, Shield, Activity,
} from "lucide-react";

const BG = "#0f172a";
const TEXT = "#f8fafc";
const MUTED = "#94a3b8";
const DIM = "#475569";
const BLUE = "#3b82f6";
const PURPLE = "#8b5cf6";
const CYAN = "#06b6d4";
const ROSE = "#f43f5e";
const AMBER = "#f59e0b";
const GREEN = "#22c55e";

// ── Data: define services as an array for data-driven rendering ──
const SERVICES = [
  { label: "Users", sublabel: "Auth & Profiles", icon: Users, color: BLUE },
  { label: "Orders", sublabel: "Order Processing", icon: ShoppingCart, color: PURPLE },
  { label: "Products", sublabel: "Catalog & Inventory", icon: Package, color: CYAN },
  { label: "Payments", sublabel: "Billing & Invoicing", icon: CreditCard, color: ROSE },
];

// ── SPATIAL: Fixed Y-positions for each architectural tier ──
// This creates clear horizontal "lanes" from top to bottom.
const LB_Y = 170;       // Load Balancer
const GATEWAY_Y = 280;  // API Gateway
const SERVICE_Y = 500;  // Microservices
const QUEUE_Y = 650;    // Message Queue
const DB_Y = 780;       // Databases

// ── CAPABILITY: distributeX — evenly space N items between startX and endX ──
function distributeX(count: number, startX: number, endX: number): number[] {
  if (count <= 1) return [(startX + endX) / 2];
  const step = (endX - startX) / (count - 1);
  return Array.from({ length: count }, (_, i) => startX + i * step);
}

// ── CAPABILITY: DotGrid — creates subtle depth texture ──
const DotGrid: React.FC = () => (
  <svg style={{
    position: "absolute", top: 0, left: 0,
    width: 1920, height: 1080, opacity: 0.025,
  }}>
    {Array.from({ length: 40 }, (_, i) =>
      Array.from({ length: 22 }, (_, j) => (
        <circle key={`${i}-${j}`} cx={48 * i} cy={48 * j} r={1.2} fill="#fff" />
      )),
    )}
  </svg>
);

// ── CAPABILITY: HealthDot — pulsing indicator using Math.sin ──
// Math.sin(frame * 0.15) creates organic, continuous pulsing.
// Maps [-1, 1] to [0.7, 1] for subtle scale + glow variation.
const HealthDot: React.FC<{ x: number; y: number }> = ({ x, y }) => {
  const frame = useCurrentFrame();
  const pulse = interpolate(Math.sin(frame * 0.15), [-1, 1], [0.7, 1]);

  return (
    <div style={{
      position: "absolute", left: x, top: y,
      width: 10, height: 10, borderRadius: 5,
      backgroundColor: GREEN,
      boxShadow: `0 0 ${8 * pulse}px ${GREEN}80`,
      transform: `scale(${pulse})`,
    }} />
  );
};

// ── CAPABILITY: ServiceBox — reusable card with icon, label, sublabel ──
// Positioned absolutely with translate(-50%, -50%) to center on (x, y).
const ServiceBox: React.FC<{
  icon: React.ElementType; label: string; sublabel: string;
  x: number; y: number; color: string;
}> = ({ icon: Icon, label, sublabel, x, y, color }) => (
  <div style={{
    position: "absolute", left: x, top: y,
    transform: "translate(-50%, -50%)",
    width: 200, height: 140, borderRadius: 16,
    backgroundColor: `${color}08`,
    border: `1.5px solid ${color}35`,
    display: "flex", flexDirection: "column",
    alignItems: "center", justifyContent: "center", gap: 10,
  }}>
    <div style={{
      width: 48, height: 48, borderRadius: 12,
      backgroundColor: `${color}15`,
      display: "flex", justifyContent: "center", alignItems: "center",
    }}>
      <Icon size={26} color={color} />
    </div>
    <div style={{
      fontSize: 17, color: TEXT,
      fontFamily: "Inter, system-ui, sans-serif", fontWeight: 600,
    }}>
      {label}
    </div>
    <div style={{
      fontSize: 11, color: DIM,
      fontFamily: "Inter, system-ui, sans-serif",
    }}>
      {sublabel}
    </div>
  </div>
);

// ── CAPABILITY: Connector — animated SVG arrow (straight or curved) ──
// Uses evolvePath for progressive drawing animation.
// Arrowhead appears at 85% progress. Optional label at midpoint.
type ConnectorProps = {
  from: [number, number]; to: [number, number];
  color?: string; strokeWidth?: number;
  delay?: number; duration?: number;
  curved?: boolean; label?: string; labelColor?: string;
};

const Connector: React.FC<ConnectorProps> = ({
  from, to, color = "#94a3b8", strokeWidth = 2,
  delay = 0, duration = 30, curved = false, label, labelColor,
}) => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame - delay, [0, duration], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  if (progress <= 0) return null;

  const [x1, y1] = from;
  const [x2, y2] = to;

  let d: string;
  if (curved) {
    const mx = (x1 + x2) / 2;
    const my = Math.min(y1, y2) - Math.abs(x2 - x1) * 0.15;
    d = `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`;
  } else {
    d = `M ${x1} ${y1} L ${x2} ${y2}`;
  }

  const evolved = evolvePath(progress, d);
  const midX = (x1 + x2) / 2;
  const midY = curved
    ? Math.min(y1, y2) - Math.abs(x2 - x1) * 0.1
    : (y1 + y2) / 2;
  const labelOpacity = interpolate(progress, [0.6, 1], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const aSize = 10;
  const arrowOpacity = interpolate(progress, [0.85, 1], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <>
      <svg style={{
        position: "absolute", top: 0, left: 0,
        width: 1920, height: 1080, pointerEvents: "none",
      }}>
        <path
          d={d} fill="none" stroke={color} strokeWidth={strokeWidth}
          strokeDasharray={evolved.strokeDasharray}
          strokeDashoffset={evolved.strokeDashoffset}
          strokeLinecap="round"
        />
        <polygon
          points={[
            `${x2},${y2}`,
            `${x2 - aSize * Math.cos(angle - 0.4)},${y2 - aSize * Math.sin(angle - 0.4)}`,
            `${x2 - aSize * Math.cos(angle + 0.4)},${y2 - aSize * Math.sin(angle + 0.4)}`,
          ].join(" ")}
          fill={color} opacity={arrowOpacity}
        />
      </svg>
      {label && (
        <div style={{
          position: "absolute", left: midX, top: midY - 24,
          transform: "translateX(-50%)", fontSize: 16,
          color: labelColor || color, opacity: labelOpacity,
          fontFamily: "Inter, system-ui, sans-serif", fontWeight: 500,
          whiteSpace: "nowrap", backgroundColor: "rgba(15, 23, 42, 0.8)",
          padding: "4px 12px", borderRadius: 6,
        }}>
          {label}
        </div>
      )}
    </>
  );
};

// ═══════════════════════════════════════════════════════════════════════
// MAIN COMPONENT — Layered additive build-up
// ═══════════════════════════════════════════════════════════════════════
// Sequences are ordered by `from` to build the diagram top-to-bottom.
// No durationInFrames = element persists forever after appearing.
// durationInFrames on title = title disappears after 110 frames.

export const MyComp: React.FC = () => {
  const xs = distributeX(4, 340, 1580);

  return (
    <AbsoluteFill style={{
      backgroundColor: BG,
      background: `linear-gradient(180deg, ${BG} 0%, #0c1222 100%)`,
    }}>
      <DotGrid />

      {/* Title — fades out (durationInFrames limits its lifetime) */}
      <Sequence from={0} durationInFrames={110}>
        <TitleScene />
      </Sequence>

      {/* Load Balancer — top of diagram */}
      <Sequence from={60}>
        <LoadBalancerEntry />
      </Sequence>

      {/* API Gateway — second tier */}
      <Sequence from={100}>
        <GatewayEntry />
      </Sequence>

      {/* Connector: LB → Gateway */}
      <Sequence from={120}>
        <Connector
          from={[960, LB_Y + 30]} to={[960, GATEWAY_Y - 30]}
          color={DIM} strokeWidth={1.5} delay={5} duration={20}
        />
      </Sequence>

      {/* Service boxes — third tier, staggered spring entrances */}
      <Sequence from={150}>
        <ServiceBoxes xs={xs} />
      </Sequence>

      {/* CAPABILITY: Curved connectors from Gateway to each Service ──
          Each connector has a staggered delay (i * 8) for visual rhythm.
          curved=true creates a quadratic Bezier arc above the straight line. */}
      <Sequence from={220}>
        {xs.map((x, i) => (
          <Connector
            key={`gw-${i}`}
            from={[960, GATEWAY_Y + 30]}
            to={[x, SERVICE_Y - 72]}
            color={AMBER} strokeWidth={1.5}
            delay={i * 8} duration={25} curved
          />
        ))}
      </Sequence>

      {/* Health dots — pulsing indicators on each service */}
      <Sequence from={260}>
        {xs.map((x, i) => (
          <HealthDot key={`h-${i}`} x={x + 85} y={SERVICE_Y - 80} />
        ))}
      </Sequence>

      {/* Message Queue — horizontal bar connecting all services */}
      <Sequence from={300}>
        <MessageQueueEntry xs={xs} />
      </Sequence>

      {/* Database icons — bottom tier */}
      <Sequence from={370}>
        <DatabaseLayer xs={xs} />
      </Sequence>

      {/* Service → DB connectors */}
      <Sequence from={410}>
        {xs.map((x, i) => (
          <Connector
            key={`db-c-${i}`}
            from={[x, QUEUE_Y + 25]} to={[x, DB_Y - 30]}
            color={SERVICES[i].color} strokeWidth={1}
            delay={i * 6} duration={18}
          />
        ))}
      </Sequence>

      {/* CAPABILITY: RequestFlow — looping animated dot that travels
          through the architecture using modulo for infinite repetition */}
      <Sequence from={450}>
        <RequestFlow xs={xs} />
      </Sequence>

      {/* Footer description */}
      <Sequence from={480}>
        <FooterDescription />
      </Sequence>
    </AbsoluteFill>
  );
};

const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const fadeOut = interpolate(frame, [70, 100], [1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const lineW = interpolate(frame, [20, 50], [0, 260], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <div style={{
      position: "absolute", top: 0, left: 0, width: 1920, height: 1080,
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      opacity: fadeOut,
    }}>
      <AnimatedText
        transition={{
          y: [30, 0], opacity: [0, 1],
          split: "word", splitStagger: 3, duration: 30,
        }}
        style={{
          fontSize: 62, color: TEXT,
          fontFamily: "Inter, system-ui, sans-serif", fontWeight: 700,
        }}
      >
        Microservices Architecture
      </AnimatedText>
      <div style={{
        width: lineW, height: 3, backgroundColor: BLUE,
        borderRadius: 2, marginTop: 18, marginBottom: 14,
      }} />
      <AnimatedText
        transition={{ opacity: [0, 1], duration: 25, delay: 18 }}
        style={{
          fontSize: 24, color: MUTED,
          fontFamily: "Inter, system-ui, sans-serif",
        }}
      >
        Scalable, independent services communicating via APIs
      </AnimatedText>
    </div>
  );
};

const LoadBalancerEntry: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 15 } });

  return (
    <div style={{ opacity: s, transform: `scale(${s})` }}>
      <div style={{
        position: "absolute", left: 960, top: LB_Y,
        transform: "translate(-50%, -50%)",
        display: "flex", alignItems: "center", gap: 10,
        backgroundColor: `${GREEN}10`, border: `1.5px solid ${GREEN}35`,
        padding: "10px 24px", borderRadius: 12,
      }}>
        <Shield size={22} color={GREEN} />
        <span style={{
          fontSize: 16, color: TEXT,
          fontFamily: "Inter, system-ui, sans-serif", fontWeight: 600,
        }}>
          Load Balancer
        </span>
      </div>
    </div>
  );
};

const GatewayEntry: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 14 } });

  return (
    <div style={{ opacity: s, transform: `scale(${s})` }}>
      <div style={{
        position: "absolute", left: 960, top: GATEWAY_Y,
        transform: "translate(-50%, -50%)",
        width: 280, height: 60, borderRadius: 14,
        backgroundColor: `${AMBER}10`, border: `2px solid ${AMBER}40`,
        display: "flex", alignItems: "center", justifyContent: "center", gap: 12,
      }}>
        <Globe size={26} color={AMBER} />
        <span style={{
          fontSize: 20, color: TEXT,
          fontFamily: "Inter, system-ui, sans-serif", fontWeight: 600,
        }}>
          API Gateway
        </span>
      </div>
    </div>
  );
};

// ── CAPABILITY: Staggered service box entrances using spring delay ──
const ServiceBoxes: React.FC<{ xs: number[] }> = ({ xs }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <>
      {SERVICES.map((svc, i) => {
        const s = spring({
          frame, fps, delay: i * 10,
          config: { damping: 14, stiffness: 120 },
        });
        return (
          <div key={svc.label} style={{ opacity: s, transform: `scale(${s})` }}>
            <ServiceBox
              icon={svc.icon} label={svc.label} sublabel={svc.sublabel}
              x={xs[i]} y={SERVICE_Y} color={svc.color}
            />
          </div>
        );
      })}
    </>
  );
};

const MessageQueueEntry: React.FC<{ xs: number[] }> = ({ xs }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 200 } });
  const queueWidth = xs[xs.length - 1] - xs[0] + 160;

  return (
    <>
      {/* Service → Queue connectors */}
      {xs.map((x, i) => (
        <Connector
          key={`sq-${i}`}
          from={[x, SERVICE_Y + 70]} to={[x, QUEUE_Y - 18]}
          color={SERVICES[i].color} strokeWidth={1}
          delay={5 + i * 5} duration={18}
        />
      ))}
      {/* Queue bar — spans all services */}
      <div style={{
        position: "absolute",
        left: 960 - queueWidth / 2, top: QUEUE_Y - 18,
        width: queueWidth, height: 36, borderRadius: 8,
        backgroundColor: `${PURPLE}10`, border: `1px solid ${PURPLE}25`,
        display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
        opacity: s,
      }}>
        <MessageSquare size={16} color={PURPLE} />
        <span style={{
          fontSize: 13, color: MUTED,
          fontFamily: "Inter, system-ui, sans-serif", fontWeight: 500,
        }}>
          Message Queue (Kafka / RabbitMQ)
        </span>
      </div>
    </>
  );
};

const DatabaseLayer: React.FC<{ xs: number[] }> = ({ xs }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <>
      {xs.map((x, i) => {
        const s = spring({ frame, fps, delay: i * 8, config: { damping: 200 } });
        return (
          <div key={`db-${i}`} style={{
            position: "absolute", left: x, top: DB_Y,
            transform: "translate(-50%, -50%)", opacity: s,
            display: "flex", flexDirection: "column",
            alignItems: "center", gap: 6,
          }}>
            <div style={{
              width: 44, height: 44, borderRadius: 10,
              backgroundColor: `${SERVICES[i].color}12`,
              border: `1px solid ${SERVICES[i].color}30`,
              display: "flex", justifyContent: "center", alignItems: "center",
            }}>
              <Database size={22} color={SERVICES[i].color} />
            </div>
            <div style={{
              fontSize: 11, color: DIM,
              fontFamily: "Inter, system-ui, sans-serif",
            }}>
              {["PostgreSQL", "MongoDB", "Redis", "Stripe"][i]}
            </div>
          </div>
        );
      })}
    </>
  );
};

// ── CAPABILITY: RequestFlow — looping animated dot ──
// Uses modulo (frame % 90) to create infinite repetition.
// interpolate maps the loop frame to x,y positions through the architecture.
const RequestFlow: React.FC<{ xs: number[] }> = ({ xs }) => {
  const frame = useCurrentFrame();
  const loopFrame = frame % 90;
  const dotY = interpolate(
    loopFrame, [0, 30, 60, 90],
    [LB_Y, GATEWAY_Y, SERVICE_Y - 70, QUEUE_Y - 18],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const dotX = interpolate(
    loopFrame, [0, 30, 60, 90],
    [960, 960, xs[1], xs[1]],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const opacity = interpolate(
    loopFrame, [0, 5, 80, 90], [0, 0.9, 0.9, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <>
      <div style={{
        position: "absolute", left: dotX, top: dotY,
        width: 10, height: 10, borderRadius: 5,
        backgroundColor: AMBER,
        transform: "translate(-50%, -50%)",
        boxShadow: `0 0 14px ${AMBER}80`,
        opacity,
      }} />
      {/* "Live Request Flow" label */}
      <div style={{
        position: "absolute", top: LB_Y - 45, left: 960,
        transform: "translateX(-50%)",
        display: "flex", alignItems: "center", gap: 6,
        opacity: interpolate(frame, [0, 15], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        }),
      }}>
        <Activity size={14} color={AMBER} />
        <span style={{
          fontSize: 12, color: AMBER,
          fontFamily: "Inter, system-ui, sans-serif",
          fontWeight: 500, textTransform: "uppercase", letterSpacing: 1,
        }}>
          Live Request Flow
        </span>
      </div>
    </>
  );
};

const FooterDescription: React.FC = () => (
  <div style={{
    position: "absolute", bottom: 20, left: 0, width: 1920,
    display: "flex", flexDirection: "column",
    alignItems: "center", gap: 10,
  }}>
    <AnimatedText
      transition={{ opacity: [0, 1], duration: 20 }}
      style={{
        fontSize: 16, color: DIM,
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      Each service owns its data · Scales independently · Communicates via REST / gRPC / Event Streams
    </AnimatedText>
  </div>
);
```
