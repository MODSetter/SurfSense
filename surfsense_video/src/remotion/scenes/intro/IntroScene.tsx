/**
 * IntroScene -- animated title card with multiple reveal styles.
 * 5 animation variants x 4 background styles x 4 decorative elements.
 */
import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";
import type { ThemeColors } from "../../theme";
import type { IntroSceneInput } from "./types";
import type { IntroVariant } from "./variant";
import { TITLE_DELAY, SUBTITLE_DELAY, DECOR_DELAY } from "./constants";

interface IntroSceneProps {
  input: IntroSceneInput;
  theme: ThemeColors;
  variant: IntroVariant;
}

function accentColor(hue: number): string {
  return `hsl(${hue}, 70%, 65%)`;
}

function accentColorAlpha(hue: number, alpha: string): string {
  return `hsla(${hue}, 70%, 65%, ${alpha})`;
}

function renderBg(
  variant: IntroVariant,
  theme: ThemeColors,
  frame: number,
  vmin: number,
  width: number,
  height: number,
): React.ReactNode {
  const accent = accentColor(variant.accentHue);
  const progress = interpolate(frame, [0, 60], [0, 1], {
    extrapolateRight: "clamp",
  });

  switch (variant.bgStyle) {
    case "radialGlow": {
      const radius = 30 + progress * 20;
      return (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(ellipse ${radius}% ${radius}% at 50% 50%, ${accentColorAlpha(variant.accentHue, "0.12")} 0%, transparent 70%)`,
          }}
        />
      );
    }
    case "gradientSweep": {
      const angle = progress * 120;
      return (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `linear-gradient(${angle}deg, ${accentColorAlpha(variant.accentHue, "0.08")} 0%, transparent 50%, ${accentColorAlpha(variant.accentHue, "0.05")} 100%)`,
          }}
        />
      );
    }
    case "particleDots": {
      const dots = Array.from({ length: 12 }, (_, i) => {
        const x = (Math.sin(i * 2.39) * 0.4 + 0.5) * width;
        const y = (Math.cos(i * 2.39) * 0.4 + 0.5) * height;
        const size = vmin * (0.3 + (i % 3) * 0.15);
        const delay = i * 3;
        const opacity = interpolate(frame - delay, [0, 20], [0, 0.3], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: size,
              height: size,
              borderRadius: "50%",
              background: accent,
              opacity,
            }}
          />
        );
      });
      return <>{dots}</>;
    }
    case "minimal":
    default:
      return null;
  }
}

function renderDecor(
  variant: IntroVariant,
  frame: number,
  vmin: number,
  width: number,
  height: number,
): React.ReactNode {
  const accent = accentColor(variant.accentHue);
  const progress = interpolate(frame - DECOR_DELAY, [0, 40], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const eased = Easing.out(Easing.ease)(progress);

  switch (variant.decor) {
    case "line": {
      const lineW = eased * vmin * 30;
      return (
        <div
          style={{
            position: "absolute",
            left: width / 2 - lineW / 2,
            top: height / 2 + vmin * 8,
            width: lineW,
            height: vmin * 0.15,
            background: `linear-gradient(90deg, transparent, ${accent}, transparent)`,
            opacity: eased,
          }}
        />
      );
    }
    case "corners": {
      const armLen = vmin * 4 * eased;
      const strokeW = vmin * 0.12;
      const inset = vmin * 8;
      const opacity = eased * 0.5;
      const cornerStyle = (left: number, top: number, bL: string, bT: string): React.CSSProperties => ({
        position: "absolute",
        left,
        top,
        width: armLen,
        height: armLen,
        [bL]: `${strokeW}px solid ${accent}`,
        [bT]: `${strokeW}px solid ${accent}`,
        opacity,
      });
      return (
        <>
          <div style={cornerStyle(inset, inset, "borderLeft", "borderTop")} />
          <div style={cornerStyle(width - inset - armLen, inset, "borderRight", "borderTop")} />
          <div style={cornerStyle(inset, height - inset - armLen, "borderLeft", "borderBottom")} />
          <div style={cornerStyle(width - inset - armLen, height - inset - armLen, "borderRight", "borderBottom")} />
        </>
      );
    }
    case "ring": {
      const size = vmin * 20 * eased;
      return (
        <div
          style={{
            position: "absolute",
            left: width / 2 - size / 2,
            top: height / 2 - size / 2,
            width: size,
            height: size,
            borderRadius: "50%",
            border: `${vmin * 0.08}px solid ${accentColorAlpha(variant.accentHue, "0.2")}`,
            opacity: eased * 0.6,
          }}
        />
      );
    }
    case "none":
    default:
      return null;
  }
}

export const IntroScene: React.FC<IntroSceneProps> = ({
  input,
  theme,
  variant,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const vmin = Math.min(width, height) / 100;

  const titleLocal = frame - TITLE_DELAY;
  const subtitleLocal = frame - (TITLE_DELAY + SUBTITLE_DELAY);

  let titleOpacity: number;
  let titleTransform: string;

  switch (variant.animation) {
    case "fadeUp": {
      titleOpacity = interpolate(titleLocal, [0, 20], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      const y = interpolate(titleLocal, [0, 20], [vmin * 4, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.ease),
      });
      titleTransform = `translateY(${y}px)`;
      break;
    }
    case "scaleIn": {
      const s = spring({
        frame: Math.max(0, titleLocal),
        fps,
        config: { damping: 12, stiffness: 80, mass: 0.8 },
      });
      titleOpacity = interpolate(titleLocal, [0, 10], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      titleTransform = `scale(${s})`;
      break;
    }
    case "typewriter": {
      const totalChars = input.title.length;
      const charsVisible = Math.floor(
        interpolate(titleLocal, [0, totalChars * 1.5], [0, totalChars], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
      );
      titleOpacity = titleLocal >= 0 ? 1 : 0;
      titleTransform = "";
      input = {
        ...input,
        title: input.title.slice(0, charsVisible) + (charsVisible < totalChars && titleLocal >= 0 ? "\u258C" : ""),
      };
      break;
    }
    case "splitReveal": {
      titleOpacity = interpolate(titleLocal, [0, 15], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      const spread = interpolate(titleLocal, [0, 25], [vmin * 6, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.cubic),
      });
      titleTransform = `translateX(${spread}px)`;
      break;
    }
    case "glowIn":
    default: {
      titleOpacity = interpolate(titleLocal, [0, 25], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      const blur = interpolate(titleLocal, [0, 20], [vmin * 1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      titleTransform = `blur(${blur}px)`;
      break;
    }
  }

  const subtitleOpacity = interpolate(subtitleLocal, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const subtitleY = interpolate(subtitleLocal, [0, 18], [vmin * 2, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.ease),
  });

  const accent = accentColor(variant.accentHue);
  const isGlow = variant.animation === "glowIn";

  return (
    <AbsoluteFill style={{ background: theme.bg, overflow: "hidden" }}>
      {renderBg(variant, theme, frame, vmin, width, height)}
      {renderDecor(variant, frame, vmin, width, height)}

      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: vmin * 2,
        }}
      >
        <div
          style={{
            fontSize: vmin * 5,
            fontWeight: 800,
            color: theme.textPrimary,
            fontFamily: "Inter, system-ui, sans-serif",
            textAlign: "center",
            lineHeight: 1.2,
            opacity: titleOpacity,
            transform: isGlow ? undefined : titleTransform,
            filter: isGlow ? titleTransform : undefined,
            textShadow: `0 0 ${vmin * 3}px ${accentColorAlpha(variant.accentHue, String(titleOpacity * 0.3))}`,
            maxWidth: "80%",
          }}
        >
          {input.title}
        </div>

        {input.subtitle && (
          <div
            style={{
              fontSize: vmin * 2.2,
              fontWeight: 400,
              color: accent,
              fontFamily: "Inter, system-ui, sans-serif",
              textAlign: "center",
              lineHeight: 1.4,
              opacity: subtitleOpacity,
              transform: `translateY(${subtitleY}px)`,
              maxWidth: "70%",
            }}
          >
            {input.subtitle}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
