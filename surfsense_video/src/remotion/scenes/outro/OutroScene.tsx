/**
 * OutroScene -- animated closing card with reveal + fade-out.
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
import type { OutroSceneInput } from "./types";
import type { OutroVariant } from "./variant";
import { TEXT_DELAY, FADEOUT_START, OUTRO_DURATION } from "./constants";

interface OutroSceneProps {
  input: OutroSceneInput;
  theme: ThemeColors;
  variant: OutroVariant;
}

function accentColor(hue: number): string {
  return `hsl(${hue}, 70%, 65%)`;
}

function accentAlpha(hue: number, a: string): string {
  return `hsla(${hue}, 70%, 65%, ${a})`;
}

export const OutroScene: React.FC<OutroSceneProps> = ({
  input,
  theme,
  variant,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const vmin = Math.min(width, height) / 100;

  const title = input.title ?? "Thank you";
  const accent = accentColor(variant.accentHue);
  const textLocal = frame - TEXT_DELAY;

  const fadeOutProgress = interpolate(
    frame,
    [OUTRO_DURATION - FADEOUT_START, OUTRO_DURATION],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  let textOpacity: number;
  let textTransform: string;

  switch (variant.animation) {
    case "fadeCenter": {
      textOpacity = interpolate(textLocal, [0, 18], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      textTransform = "";
      break;
    }
    case "shrinkOut": {
      const s = spring({
        frame: Math.max(0, textLocal),
        fps,
        config: { damping: 14, stiffness: 90, mass: 0.7 },
      });
      textOpacity = interpolate(textLocal, [0, 10], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      const scaleOut = interpolate(
        frame,
        [OUTRO_DURATION - FADEOUT_START, OUTRO_DURATION],
        [1, 0.85],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
      );
      textTransform = `scale(${s * scaleOut})`;
      break;
    }
    case "slideUp": {
      textOpacity = interpolate(textLocal, [0, 15], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      const y = interpolate(textLocal, [0, 20], [vmin * 5, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.ease),
      });
      textTransform = `translateY(${y}px)`;
      break;
    }
    case "dissolve": {
      textOpacity = interpolate(textLocal, [0, 25], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      const blur = interpolate(textLocal, [0, 20], [vmin * 0.8, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      textTransform = `blur(${blur}px)`;
      break;
    }
    case "wipeOut":
    default: {
      textOpacity = interpolate(textLocal, [0, 12], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      const x = interpolate(textLocal, [0, 18], [-vmin * 6, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.cubic),
      });
      textTransform = `translateX(${x}px)`;
      break;
    }
  }

  const isBlur = variant.animation === "dissolve";
  const subtitleOpacity = interpolate(textLocal - 12, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const bgNode = (() => {
    const p = interpolate(frame, [0, 50], [0, 1], { extrapolateRight: "clamp" });
    switch (variant.bgStyle) {
      case "radialGlow": {
        const r = 25 + p * 15;
        return (
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `radial-gradient(ellipse ${r}% ${r}% at 50% 50%, ${accentAlpha(variant.accentHue, "0.1")} 0%, transparent 70%)`,
            }}
          />
        );
      }
      case "gradientSweep": {
        const angle = 180 + p * 60;
        return (
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `linear-gradient(${angle}deg, ${accentAlpha(variant.accentHue, "0.06")} 0%, transparent 60%)`,
            }}
          />
        );
      }
      case "vignette":
        return (
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `radial-gradient(ellipse 70% 70% at 50% 50%, transparent 30%, rgba(0,0,0,${0.4 * p}) 100%)`,
            }}
          />
        );
      case "minimal":
      default:
        return null;
    }
  })();

  const decorNode = (() => {
    const dp = interpolate(frame - 5, [0, 35], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    const eased = Easing.out(Easing.ease)(dp);

    switch (variant.decor) {
      case "line": {
        const w = eased * vmin * 20;
        return (
          <div
            style={{
              position: "absolute",
              left: width / 2 - w / 2,
              top: height / 2 + vmin * 7,
              width: w,
              height: vmin * 0.12,
              background: `linear-gradient(90deg, transparent, ${accent}, transparent)`,
              opacity: eased,
            }}
          />
        );
      }
      case "ring": {
        const size = vmin * 16 * eased;
        return (
          <div
            style={{
              position: "absolute",
              left: width / 2 - size / 2,
              top: height / 2 - size / 2,
              width: size,
              height: size,
              borderRadius: "50%",
              border: `${vmin * 0.06}px solid ${accentAlpha(variant.accentHue, "0.2")}`,
              opacity: eased * 0.5,
            }}
          />
        );
      }
      case "particles": {
        return (
          <>
            {Array.from({ length: 8 }, (_, i) => {
              const angle = (i / 8) * Math.PI * 2;
              const dist = vmin * 14 * eased;
              const x = width / 2 + Math.cos(angle) * dist;
              const y = height / 2 + Math.sin(angle) * dist;
              const s = vmin * 0.25;
              const delay = i * 2;
              const o = interpolate(frame - delay, [0, 20], [0, 0.35], {
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
                    width: s,
                    height: s,
                    borderRadius: "50%",
                    background: accent,
                    opacity: o * fadeOutProgress,
                  }}
                />
              );
            })}
          </>
        );
      }
      case "none":
      default:
        return null;
    }
  })();

  return (
    <AbsoluteFill style={{ background: theme.bg, overflow: "hidden" }}>
      {bgNode}
      {decorNode}

      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: vmin * 1.5,
          opacity: fadeOutProgress,
        }}
      >
        <div
          style={{
            fontSize: vmin * 4.5,
            fontWeight: 700,
            color: theme.textPrimary,
            fontFamily: "Inter, system-ui, sans-serif",
            textAlign: "center",
            lineHeight: 1.2,
            opacity: textOpacity,
            transform: isBlur ? undefined : textTransform,
            filter: isBlur ? textTransform : undefined,
            textShadow: `0 0 ${vmin * 2}px ${accentAlpha(variant.accentHue, String(textOpacity * 0.25))}`,
            maxWidth: "75%",
          }}
        >
          {title}
        </div>

        {input.subtitle && (
          <div
            style={{
              fontSize: vmin * 2,
              fontWeight: 400,
              color: accent,
              fontFamily: "Inter, system-ui, sans-serif",
              textAlign: "center",
              lineHeight: 1.4,
              opacity: subtitleOpacity * fadeOutProgress,
              maxWidth: "65%",
            }}
          >
            {input.subtitle}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
