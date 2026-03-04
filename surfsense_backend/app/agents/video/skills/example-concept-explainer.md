# Example: Concept Explainer — "How HTTPS Works"

## Pattern: ADDITIVE BUILD-UP (Pattern A)

Elements persist across steps. Each step adds new elements on top.
Use for: processes, protocols, how-things-work, step-by-step concepts.

## Capabilities demonstrated

- **3-layer z-index architecture** (connectors z:1, content z:2, UI chrome z:3)
- **AnimatedText** with word-split stagger for titles
- **StaggeredMotion** for group entrance animations
- **Connector** (inline component) — straight and curved SVG arrows with evolvePath
- **DotGrid** (inline component) — subtle background texture
- **InfoCard** (inline component) — bordered card with icon, title, bullet items
- **EndpointNode** (inline component) — icon + label + detail badge
- **StepIndicator + ProgressBar** — UI chrome showing current position
- **spring()** for bouncy pop-in effects (cards, icons, badges)
- **interpolate()** for controlled fades, slides, width animations
- **Easing.out(Easing.cubic)** for deceleration curves
- **Fade-previous dimming** — reducing opacity of prior step before next starts
- **Animated underline** — width: 0 → 300 over 40 frames
- **Looping data packets** — repeating position animation with modulo
- **lucide-react icons** — Globe, Server, Shield, Lock, KeyRound, etc.
- **Absolute positioning with explicit x,y** — nothing uses centered flexbox for layout
- **STEPS array** — data-driven timeline with from/label/color per step

## Scene inventory (what's on screen at each point)

- **Frame 0–190**: Title phase (centered AnimatedText + animated underline). Nothing else.
- **Frame 120+**: Title fades out. Two EndpointNodes appear (Client, Server) with staggered entrance. Baseline dashed line draws between them. These PERSIST for the entire video.
- **Frame 200–370**: Step 1 — Client Hello arrow draws left→right. InfoCard pops in. Timing label appears. Previous content at full opacity.
- **Frame 370–540**: Step 2 — Previous step dims to 25% opacity. Certificate arrow draws right→left. InfoCard pops in. Shield badge bounces in. These PERSIST but will dim.
- **Frame 540–710**: Step 3 — Previous step dims. Two curved key exchange arrows draw. Key badges pop in at both endpoints. Session key badge fades in center. PERSIST.
- **Frame 710–880**: Step 4 — Tunnel bar draws. Lock icon bounces in center. TLS badges appear at endpoints. Data packets loop across the tunnel. InfoCard appears below.
- **Frame 880–1050**: Summary — Semi-opaque overlay covers everything. Summary title + 4 staggered takeaway cards.

## Full code

```tsx
import React from "react";
import {
  AbsoluteFill, Sequence, useCurrentFrame, interpolate, spring,
  useVideoConfig, Easing,
} from "remotion";
// CAPABILITY: remotion-bits provides AnimatedText (word-by-word reveal) and
// StaggeredMotion (children appear one-by-one with configurable stagger)
import { AnimatedText, StaggeredMotion } from "remotion-bits";
// CAPABILITY: evolvePath from @remotion/paths animates SVG path drawing.
// Returns { strokeDasharray, strokeDashoffset } for a given progress (0→1).
import { evolvePath } from "@remotion/paths";
// CAPABILITY: lucide-react provides 1000+ SVG icons as React components.
// Use size and color props. Always pick icons that match the concept.
import {
  Globe, Server, Shield, Lock, KeyRound, FileCheck, Zap,
  ArrowRight, Send, ShieldCheck,
} from "lucide-react";

// ── Color palette — dark background with vibrant accents ──
const BG = "#0f172a";
const SURFACE = "#1e293b";
const BLUE = "#3b82f6";
const GREEN = "#22c55e";
const AMBER = "#f59e0b";
const PURPLE = "#8b5cf6";
const TEXT = "#f8fafc";
const MUTED = "#94a3b8";
const DIM = "#475569";

// ── SPATIAL LAYOUT: Fixed coordinates for the two endpoints ──
// Using absolute x,y positions ensures elements are deliberately placed.
// CLIENT_X=300 (left third), SERVER_X=1620 (right third) fills the canvas width.
const CLIENT_X = 300;
const SERVER_X = 1620;
const NODE_Y = 440;
const ARROW_HI = 360;  // Y-position for top arrows
const ARROW_LO = 520;  // Y-position for bottom arrows

// ── TIMING: STEPS array is the master timeline ──
// Each step's `from` is the global frame where it starts.
// ~170 frames (5.7s) between steps = breathing room for the viewer.
const STEPS = [
  { from: 200, label: "Client Hello", color: AMBER },
  { from: 370, label: "Certificate Exchange", color: GREEN },
  { from: 540, label: "Key Exchange", color: PURPLE },
  { from: 710, label: "Encrypted Channel", color: GREEN },
] as const;

const SUMMARY_FROM = 880;

// ── CAPABILITY: DotGrid — subtle background texture for depth ──
// Creates a grid of tiny dots. opacity: 0.03 keeps it barely visible.
// Define inline (not imported) — the LLM should define this when needed.
const DotGrid: React.FC = () => (
  <svg
    style={{
      position: "absolute", top: 0, left: 0,
      width: 1920, height: 1080, opacity: 0.03,
    }}
  >
    {Array.from({ length: 40 }, (_, i) =>
      Array.from({ length: 22 }, (_, j) => (
        <circle key={`${i}-${j}`} cx={48 * i} cy={48 * j} r={1.5} fill="#fff" />
      )),
    )}
  </svg>
);

// ── CAPABILITY: StepIndicator — reads global frame, shows current step ──
// This is UI chrome (z-index: 3). It appears in the top-right corner.
// It reads useCurrentFrame() directly (not local frame) because it needs
// to track the global timeline across all steps.
const StepIndicator: React.FC = () => {
  const frame = useCurrentFrame();

  const activeIdx = (() => {
    for (let i = STEPS.length - 1; i >= 0; i--) {
      if (frame >= STEPS[i].from) return i;
    }
    return -1;
  })();

  if (activeIdx < 0 || frame >= SUMMARY_FROM) return null;

  const step = STEPS[activeIdx];
  const localF = frame - step.from;
  const slideIn = interpolate(localF, [0, 25], [30, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const opacity = interpolate(localF, [0, 20], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute", top: 30, right: 60,
        display: "flex", alignItems: "center", gap: 14,
        opacity, transform: `translateY(${slideIn}px)`,
      }}
    >
      <div
        style={{
          width: 42, height: 42, borderRadius: 21,
          backgroundColor: `${step.color}20`,
          border: `2px solid ${step.color}`,
          display: "flex", justifyContent: "center", alignItems: "center",
          fontSize: 18, color: step.color,
          fontFamily: "Inter, system-ui, sans-serif", fontWeight: 700,
        }}
      >
        {activeIdx + 1}
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <span style={{
          fontSize: 18, color: TEXT,
          fontFamily: "Inter, system-ui, sans-serif", fontWeight: 600,
        }}>
          {step.label}
        </span>
        <span style={{
          fontSize: 13, color: DIM,
          fontFamily: "Inter, system-ui, sans-serif",
        }}>
          Step {activeIdx + 1} of {STEPS.length}
        </span>
      </div>
    </div>
  );
};

// ── CAPABILITY: ProgressBar — horizontal step tracker at bottom ──
// Shows dots connected by lines. Active dots glow, lines fill as steps progress.
// Uses flex row layout with Fragment to alternate dots and connector lines.
const ProgressBar: React.FC = () => {
  const frame = useCurrentFrame();
  if (frame < 190 || frame >= SUMMARY_FROM) return null;

  return (
    <div
      style={{
        position: "absolute", bottom: 28, left: 0, width: 1920,
        display: "flex", justifyContent: "center",
      }}
    >
      <div style={{ display: "flex", alignItems: "center" }}>
        {STEPS.map((step, i) => {
          const isActive = frame >= step.from;
          const nextActive = i < STEPS.length - 1 && frame >= STEPS[i + 1].from;
          const lineProgress = isActive
            ? interpolate(frame - step.from, [0, 60], [0, 1], {
                extrapolateLeft: "clamp", extrapolateRight: "clamp",
              })
            : 0;

          return (
            <React.Fragment key={step.label}>
              <div style={{
                display: "flex", flexDirection: "column",
                alignItems: "center", gap: 8, minWidth: 160,
              }}>
                <div style={{
                  width: isActive ? 16 : 12, height: isActive ? 16 : 12,
                  borderRadius: 10,
                  backgroundColor: isActive ? step.color : `${DIM}40`,
                  border: `2px solid ${isActive ? step.color : DIM}`,
                  boxShadow: isActive ? `0 0 12px ${step.color}60` : "none",
                }} />
                <span style={{
                  fontSize: 14, color: isActive ? TEXT : DIM,
                  fontFamily: "Inter, system-ui, sans-serif",
                  fontWeight: isActive ? 600 : 400, whiteSpace: "nowrap",
                }}>
                  {step.label}
                </span>
              </div>

              {i < STEPS.length - 1 && (
                <div style={{
                  width: 80, height: 2,
                  backgroundColor: `${DIM}30`, borderRadius: 1,
                  overflow: "hidden", marginBottom: 26,
                }}>
                  <div style={{
                    width: `${(nextActive ? 1 : lineProgress) * 100}%`,
                    height: "100%",
                    backgroundColor: nextActive ? STEPS[i + 1].color : step.color,
                  }} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};

// ── CAPABILITY: InfoCard — reusable card with icon, title, bullet items ──
// Uses absolute positioning with transform: translateX(-50%) for centering.
// Background is solid BG (not transparent) so it occludes connectors behind it.
const InfoCard: React.FC<{
  x: number; y: number; items: string[]; color: string;
  width?: number; icon?: React.ReactNode; title?: string;
}> = ({ x, y, items, color, width = 280, icon, title }) => (
  <div
    style={{
      position: "absolute", left: x, top: y,
      transform: "translateX(-50%)", width,
      backgroundColor: BG,
      border: `1px solid ${color}40`, borderRadius: 14,
      padding: "16px 20px",
      boxShadow: `0 4px 24px rgba(0,0,0,0.4), 0 0 0 1px ${color}15`,
    }}
  >
    {title && (
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        marginBottom: 10, paddingBottom: 8,
        borderBottom: `1px solid ${color}20`,
      }}>
        {icon}
        <span style={{
          fontSize: 15, color, fontFamily: "Inter, system-ui, sans-serif",
          fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5,
        }}>
          {title}
        </span>
      </div>
    )}
    {items.map((item) => (
      <div key={item} style={{
        fontSize: 14, color: MUTED, fontFamily: "Inter, system-ui, sans-serif",
        lineHeight: 1.8, display: "flex", alignItems: "center", gap: 8,
      }}>
        <div style={{
          width: 5, height: 5, borderRadius: 3,
          backgroundColor: color, flexShrink: 0,
        }} />
        {item}
      </div>
    ))}
  </div>
);

// ── CAPABILITY: EndpointNode — icon inside rounded container + label + detail badge ──
// Uses transform: translate(-50%, -50%) to center on the given (x, y) coordinate.
const EndpointNode: React.FC<{
  icon: React.ReactNode; label: string; detail: string;
  x: number; y: number; color: string;
}> = ({ icon, label, detail, x, y, color }) => (
  <div style={{
    position: "absolute", left: x, top: y,
    transform: "translate(-50%, -50%)",
    display: "flex", flexDirection: "column", alignItems: "center", gap: 10,
  }}>
    <div style={{
      width: 100, height: 100, borderRadius: 24,
      backgroundColor: `${color}12`, border: `2px solid ${color}40`,
      display: "flex", justifyContent: "center", alignItems: "center",
      boxShadow: `0 0 40px ${color}10`,
    }}>
      {icon}
    </div>
    <div style={{
      fontSize: 22, color: TEXT,
      fontFamily: "Inter, system-ui, sans-serif", fontWeight: 600,
    }}>
      {label}
    </div>
    <div style={{
      fontSize: 13, color: DIM,
      fontFamily: "Inter, system-ui, sans-serif",
      backgroundColor: SURFACE, padding: "3px 12px", borderRadius: 6,
      border: `1px solid ${DIM}30`,
    }}>
      {detail}
    </div>
  </div>
);

// ── CAPABILITY: Connector — animated SVG arrow between two points ──
// Uses evolvePath to animate the path drawing. Supports straight and curved paths.
// Includes arrowhead polygon that appears at 85% progress.
// Label appears at 60% progress with background for readability.
// DEFINE THIS INLINE — do not import from external files.
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
// MAIN COMPONENT — 3-layer z-index architecture
// ═══════════════════════════════════════════════════════════════════════

export const MyComp: React.FC = () => {
  return (
    <AbsoluteFill style={{
      backgroundColor: BG,
      background: `linear-gradient(180deg, ${BG} 0%, #0c1222 100%)`,
    }}>
      <DotGrid />

      {/* ── LAYER 1 (z:1): Connectors — behind everything ── */}
      <div style={{ position: "absolute", inset: 0, zIndex: 1 }}>
        {/* Baseline dashed line between endpoints */}
        <Sequence from={120}>
          <BaselineDash />
        </Sequence>

        {/* Step 1: Client Hello arrow — SLOW draw (2.5s = 75 frames) */}
        <Sequence from={STEPS[0].from}>
          <Connector
            from={[CLIENT_X + 70, ARROW_HI]}
            to={[SERVER_X - 70, ARROW_HI]}
            color={AMBER} strokeWidth={2}
            delay={10} duration={75}
            label="ClientHello" labelColor={AMBER}
          />
        </Sequence>

        {/* Step 2: Certificate arrow — reverse direction, SLOW draw */}
        <Sequence from={STEPS[1].from}>
          <Connector
            from={[SERVER_X - 70, ARROW_LO]}
            to={[CLIENT_X + 70, ARROW_LO]}
            color={GREEN} strokeWidth={2}
            delay={10} duration={75}
            label="ServerHello + Certificate" labelColor={GREEN}
          />
        </Sequence>

        {/* Step 3: Key exchange — TWO curved arrows, staggered delay */}
        <Sequence from={STEPS[2].from}>
          <Connector
            from={[CLIENT_X + 70, ARROW_HI + 10]}
            to={[SERVER_X - 70, ARROW_HI + 10]}
            color={PURPLE} strokeWidth={2}
            delay={10} duration={60} curved
          />
          <Connector
            from={[SERVER_X - 70, ARROW_LO - 10]}
            to={[CLIENT_X + 70, ARROW_LO - 10]}
            color={PURPLE} strokeWidth={2}
            delay={45} duration={60} curved
          />
        </Sequence>

        {/* Step 4: Encrypted tunnel bar */}
        <Sequence from={STEPS[3].from}>
          <TunnelBar />
        </Sequence>
      </div>

      {/* ── LAYER 2 (z:2): Content — nodes, cards, icons, badges ── */}
      <div style={{ position: "absolute", inset: 0, zIndex: 2 }}>
        {/* Title — shows for 190 frames then disappears (durationInFrames) */}
        <Sequence from={0} durationInFrames={190}>
          <TitlePhase />
        </Sequence>

        {/* Endpoints — appear with StaggeredMotion, PERSIST forever (no durationInFrames) */}
        <Sequence from={120}>
          <StaggeredMotion
            transition={{ y: [40, 0], opacity: [0, 1], stagger: 25, duration: 45 }}
          >
            <EndpointNode
              icon={<Globe size={48} color={BLUE} />}
              label="Client" detail="Browser · 192.168.1.42"
              x={CLIENT_X} y={NODE_Y} color={BLUE}
            />
            <EndpointNode
              icon={<Server size={48} color={PURPLE} />}
              label="Server" detail="example.com · 93.184.216.34"
              x={SERVER_X} y={NODE_Y} color={PURPLE}
            />
          </StaggeredMotion>
        </Sequence>

        {/* Step content — each step has its own component */}
        <Sequence from={STEPS[0].from}><ClientHelloContent /></Sequence>
        <Sequence from={STEPS[1].from}><CertificateContent /></Sequence>
        <Sequence from={STEPS[2].from}><KeyExchangeContent /></Sequence>
        <Sequence from={STEPS[3].from}><EncryptedContent /></Sequence>

        {/* Summary phase */}
        <Sequence from={SUMMARY_FROM}><SummaryPhase /></Sequence>
      </div>

      {/* ── LAYER 3 (z:3): UI chrome — step indicator, progress bar ── */}
      <div style={{ position: "absolute", inset: 0, zIndex: 3, pointerEvents: "none" }}>
        <StepIndicator />
        <ProgressBar />
      </div>
    </AbsoluteFill>
  );
};

// ── CAPABILITY: Title phase with AnimatedText word-split + animated underline ──
const TitlePhase: React.FC = () => {
  const frame = useCurrentFrame();
  // Fade out title before endpoints appear
  const fadeOut = interpolate(frame, [140, 185], [1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  // Animated underline width grows over 40 frames
  const lineW = interpolate(frame, [30, 70], [0, 300], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <div style={{
      position: "absolute", inset: 0,
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      opacity: fadeOut,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 8 }}>
        <Lock size={42} color={GREEN} />
        <AnimatedText
          transition={{
            y: [30, 0], opacity: [0, 1],
            split: "word", splitStagger: 6, duration: 40,
          }}
          style={{
            fontSize: 72, color: TEXT,
            fontFamily: "Inter, system-ui, sans-serif", fontWeight: 700,
          }}
        >
          How HTTPS Works
        </AnimatedText>
      </div>
      <div style={{
        width: lineW, height: 3, backgroundColor: BLUE,
        borderRadius: 2, marginBottom: 18,
      }} />
      <AnimatedText
        transition={{ opacity: [0, 1], duration: 30, delay: 40 }}
        style={{
          fontSize: 26, color: MUTED,
          fontFamily: "Inter, system-ui, sans-serif",
        }}
      >
        The TLS 1.3 handshake, step by step
      </AnimatedText>
    </div>
  );
};

const BaselineDash: React.FC = () => {
  const frame = useCurrentFrame();
  const width = interpolate(frame, [20, 70], [0, SERVER_X - CLIENT_X - 160], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <div style={{
      position: "absolute", left: CLIENT_X + 70, top: NODE_Y,
      width, height: 0, borderTop: `1px dashed ${DIM}40`,
    }} />
  );
};

// ── CAPABILITY: Fade-previous dimming ──
// Each step content calculates `fadeIfNext` — opacity drops to 0.25
// in the last 20 frames before the next step starts.
// This keeps previous content visible but de-emphasized.
const ClientHelloContent: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const stepDuration = STEPS[1].from - STEPS[0].from;
  // CAPABILITY: spring() for bouncy card entrance — appears after arrow is ~60% drawn
  const cardScale = spring({
    frame: frame - 55, fps,
    config: { damping: 18, stiffness: 100 },
  });
  const fadeIfNext = interpolate(frame, [stepDuration - 20, stepDuration - 5], [1, 0.25], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <div style={{ opacity: fadeIfNext }}>
      <div style={{ transform: `scale(${cardScale})`, transformOrigin: "center top" }}>
        <InfoCard
          x={620} y={170} color={AMBER} width={290}
          icon={<Send size={14} color={AMBER} />}
          title="Client Hello"
          items={[
            "Protocol: TLS 1.3",
            "Cipher: TLS_AES_256_GCM_SHA384",
            "Client Random: 32 bytes",
            "SNI: example.com",
            "Key Share: X25519",
          ]}
        />
      </div>
      <div style={{
        position: "absolute",
        left: CLIENT_X + 120, top: ARROW_HI - 30,
        fontSize: 13, color: DIM,
        fontFamily: "Inter, system-ui, sans-serif",
        opacity: interpolate(frame, [70, 90], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        }),
      }}>
        ~0ms
      </div>
    </div>
  );
};

const CertificateContent: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const stepDuration = STEPS[2].from - STEPS[1].from;
  const cardScale = spring({
    frame: frame - 55, fps,
    config: { damping: 18, stiffness: 100 },
  });
  // CAPABILITY: separate spring with different config for secondary element
  const shieldScale = spring({
    frame: frame - 80, fps,
    config: { damping: 12, stiffness: 150 },
  });
  const fadeIfNext = interpolate(frame, [stepDuration - 20, stepDuration - 5], [1, 0.25], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <div style={{ opacity: fadeIfNext }}>
      <div style={{ transform: `scale(${cardScale})`, transformOrigin: "center top" }}>
        <InfoCard
          x={1300} y={590} color={GREEN} width={310}
          icon={<ShieldCheck size={14} color={GREEN} />}
          title="Server Certificate"
          items={[
            "Subject: example.com",
            "Issuer: Let's Encrypt R3",
            "Valid: 2025-01-15 → 2026-04-15",
            "Signature: SHA256withRSA",
            "Public Key: ECDSA P-256",
            "OCSP: ✓ Good",
          ]}
        />
      </div>
      {/* Shield verified badge — bouncy entrance after card */}
      <div style={{
        position: "absolute", left: 960, top: NODE_Y - 120,
        transform: `translate(-50%, -50%) scale(${shieldScale})`,
      }}>
        <div style={{
          width: 70, height: 70, borderRadius: 35,
          backgroundColor: `${GREEN}15`, border: `2px solid ${GREEN}40`,
          display: "flex", justifyContent: "center", alignItems: "center",
          boxShadow: `0 0 30px ${GREEN}15`,
        }}>
          <FileCheck size={32} color={GREEN} />
        </div>
        <div style={{
          position: "absolute", top: 78, left: "50%",
          transform: "translateX(-50%)",
          fontSize: 14, color: GREEN,
          fontFamily: "Inter, system-ui, sans-serif",
          fontWeight: 600, whiteSpace: "nowrap",
        }}>
          Certificate Verified
        </div>
      </div>
      <div style={{
        position: "absolute",
        left: SERVER_X - 120, top: ARROW_LO - 30,
        fontSize: 13, color: DIM,
        fontFamily: "Inter, system-ui, sans-serif",
        opacity: interpolate(frame, [70, 90], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        }),
      }}>
        ~50ms
      </div>
    </div>
  );
};

const KeyExchangeContent: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const stepDuration = STEPS[3].from - STEPS[2].from;
  const leftKeyScale = spring({ frame: frame - 20, fps, config: { damping: 12, stiffness: 150 } });
  const rightKeyScale = spring({ frame: frame - 50, fps, config: { damping: 12, stiffness: 150 } });
  const sessionOpacity = interpolate(frame, [90, 115], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const fadeIfNext = interpolate(frame, [stepDuration - 20, stepDuration - 5], [1, 0.25], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <div style={{ opacity: fadeIfNext }}>
      {/* Client-side key badge */}
      <div style={{
        position: "absolute", left: CLIENT_X, top: NODE_Y + 110,
        transform: `translate(-50%, 0) scale(${leftKeyScale})`,
        display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
      }}>
        <div style={{
          width: 50, height: 50, borderRadius: 12,
          backgroundColor: `${PURPLE}15`, border: `1px solid ${PURPLE}30`,
          display: "flex", justifyContent: "center", alignItems: "center",
        }}>
          <KeyRound size={24} color={PURPLE} />
        </div>
        <span style={{
          fontSize: 13, color: PURPLE,
          fontFamily: "Inter, system-ui, sans-serif", fontWeight: 600,
        }}>
          Client Key Share
        </span>
      </div>

      {/* Server-side key badge — delayed entrance */}
      <div style={{
        position: "absolute", left: SERVER_X, top: NODE_Y + 110,
        transform: `translate(-50%, 0) scale(${rightKeyScale})`,
        display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
      }}>
        <div style={{
          width: 50, height: 50, borderRadius: 12,
          backgroundColor: `${PURPLE}15`, border: `1px solid ${PURPLE}30`,
          display: "flex", justifyContent: "center", alignItems: "center",
        }}>
          <KeyRound size={24} color={PURPLE} />
        </div>
        <span style={{
          fontSize: 13, color: PURPLE,
          fontFamily: "Inter, system-ui, sans-serif", fontWeight: 600,
        }}>
          Server Key Share
        </span>
      </div>

      {/* Session key derived badge — center, fades in after both arrows complete */}
      <div style={{
        position: "absolute", left: 960, top: NODE_Y + 120,
        transform: "translateX(-50%)", opacity: sessionOpacity,
        display: "flex", alignItems: "center", gap: 10,
        backgroundColor: BG, border: `1.5px solid ${PURPLE}40`,
        padding: "10px 20px", borderRadius: 10,
        boxShadow: `0 0 20px ${PURPLE}15`,
      }}>
        <Lock size={18} color={PURPLE} />
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{
            fontSize: 15, color: PURPLE,
            fontFamily: "Inter, system-ui, sans-serif", fontWeight: 700,
          }}>
            Session Key Derived
          </span>
          <span style={{
            fontSize: 13, color: DIM,
            fontFamily: "Inter, system-ui, sans-serif",
          }}>
            ECDHE + X25519 → AES-256-GCM
          </span>
        </div>
      </div>

      <div style={{
        position: "absolute", left: 960, top: ARROW_HI - 30,
        transform: "translateX(-50%)",
        fontSize: 13, color: DIM,
        fontFamily: "Inter, system-ui, sans-serif",
        opacity: interpolate(frame, [60, 80], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        }),
      }}>
        ~75ms
      </div>
    </div>
  );
};

// ── CAPABILITY: Animated tunnel bar with Easing curve ──
const TunnelBar: React.FC = () => {
  const frame = useCurrentFrame();
  const tunnelWidth = interpolate(frame, [5, 65], [0, SERVER_X - CLIENT_X - 140], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  return (
    <div style={{
      position: "absolute", left: CLIENT_X + 70, top: NODE_Y - 2,
      width: tunnelWidth, height: 6,
      backgroundColor: `${GREEN}30`, borderRadius: 3,
      border: `1px solid ${GREEN}25`,
      boxShadow: `0 0 12px ${GREEN}10`,
    }} />
  );
};

const EncryptedContent: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lockScale = spring({ frame: frame - 50, fps, config: { damping: 12 } });
  const numPackets = 3;
  const packetOpacity = frame > 70 ? 0.85 : 0;

  return (
    <>
      {/* Lock icon — firm pop after tunnel draws */}
      <div style={{
        position: "absolute", left: 960, top: NODE_Y - 2,
        transform: `translate(-50%, -50%) scale(${lockScale})`,
      }}>
        <div style={{
          width: 48, height: 48, borderRadius: 24,
          backgroundColor: GREEN,
          display: "flex", justifyContent: "center", alignItems: "center",
          boxShadow: `0 0 24px ${GREEN}50`,
        }}>
          <Lock size={24} color="#fff" />
        </div>
      </div>

      {/* TLS badges at both endpoints */}
      {[
        { x: CLIENT_X + 100, label: "TLS Encrypt" },
        { x: SERVER_X - 100, label: "TLS Decrypt" },
      ].map((badge) => (
        <div key={badge.x} style={{
          position: "absolute", left: badge.x, top: NODE_Y - 40,
          transform: "translateX(-50%)",
          fontSize: 12, color: GREEN,
          fontFamily: "Inter, system-ui, sans-serif",
          fontWeight: 600, backgroundColor: `${GREEN}10`,
          border: `1px solid ${GREEN}25`,
          padding: "3px 10px", borderRadius: 5,
          opacity: lockScale, textTransform: "uppercase", letterSpacing: 1,
        }}>
          {badge.label}
        </div>
      ))}

      {/* CAPABILITY: Looping data packets — modulo creates repeating animation */}
      {Array.from({ length: numPackets }).map((_, i) => {
        const offset = (frame + i * 35) % 105;
        const pX = interpolate(offset, [0, 105], [CLIENT_X + 90, SERVER_X - 90], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        });
        const pOp = interpolate(offset, [0, 12, 90, 105], [0, 1, 1, 0], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        });

        return (
          <div key={i} style={{
            position: "absolute", left: pX, top: NODE_Y - 2,
            width: 10, height: 10, borderRadius: 5,
            backgroundColor: GREEN,
            transform: "translate(-50%, -50%)",
            boxShadow: `0 0 10px ${GREEN}60`,
            opacity: packetOpacity * pOp,
          }} />
        );
      })}

      {/* Info card — appears after lock settles */}
      <div style={{
        opacity: interpolate(frame, [80, 105], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        }),
      }}>
        <InfoCard
          x={960} y={620} color={GREEN} width={320}
          icon={<Shield size={14} color={GREEN} />}
          title="Secure Channel Active"
          items={[
            "Cipher: AES-256-GCM",
            "Key: Ephemeral (forward secrecy)",
            "All HTTP traffic encrypted",
            "Man-in-the-middle: ✗ Impossible",
          ]}
        />
      </div>

      <div style={{
        position: "absolute", left: 960, top: NODE_Y + 40,
        transform: "translateX(-50%)",
        fontSize: 14, color: GREEN,
        fontFamily: "Inter, system-ui, sans-serif", fontWeight: 600,
        opacity: interpolate(frame, [60, 80], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        }),
      }}>
        Handshake complete · ~100ms total
      </div>
    </>
  );
};

// ── CAPABILITY: Summary phase — overlay + staggered takeaway cards ──
// Semi-opaque overlay covers all previous content (like a "curtain").
// StaggeredMotion reveals takeaway cards one by one.
const SummaryPhase: React.FC = () => {
  const frame = useCurrentFrame();
  const bgOpacity = interpolate(frame, [0, 35], [0, 0.85], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <div style={{
      position: "absolute", inset: 0,
      backgroundColor: `rgba(15, 23, 42, ${bgOpacity})`,
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 30,
    }}>
      <AnimatedText
        transition={{ y: [20, 0], opacity: [0, 1], duration: 40 }}
        style={{
          fontSize: 48, color: TEXT,
          fontFamily: "Inter, system-ui, sans-serif", fontWeight: 700,
        }}
      >
        HTTPS = HTTP + TLS
      </AnimatedText>

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap", justifyContent: "center" }}>
        <StaggeredMotion
          transition={{
            y: [20, 0], opacity: [0, 1],
            stagger: 18, duration: 30, delay: 25,
          }}
        >
          {[
            { icon: Zap, text: "1-RTT handshake in TLS 1.3", color: AMBER },
            { icon: Shield, text: "X.509 certificate chain verification", color: GREEN },
            { icon: KeyRound, text: "Ephemeral keys — forward secrecy", color: PURPLE },
            { icon: ArrowRight, text: "All data encrypted end-to-end", color: BLUE },
          ].map((item) => (
            <div key={item.text} style={{
              display: "flex", alignItems: "center", gap: 12,
              backgroundColor: SURFACE,
              padding: "14px 22px", borderRadius: 10,
              border: `1px solid ${item.color}25`, width: 400,
            }}>
              <div style={{
                width: 40, height: 40, borderRadius: 10,
                backgroundColor: `${item.color}15`,
                display: "flex", justifyContent: "center", alignItems: "center",
                flexShrink: 0,
              }}>
                <item.icon size={20} color={item.color} />
              </div>
              <span style={{
                fontSize: 17, color: TEXT,
                fontFamily: "Inter, system-ui, sans-serif",
              }}>
                {item.text}
              </span>
            </div>
          ))}
        </StaggeredMotion>
      </div>
    </div>
  );
};
```
