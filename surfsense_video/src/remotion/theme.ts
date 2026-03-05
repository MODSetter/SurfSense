export interface ThemeColors {
  bg: string;
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  border: string;
  glowOpacity: string;
  badgeBg: string;
  badgeBorder: string;
  accentGlowSuffix: string;
  gradientBase: [string, string, string];
}

export const THEMES: Record<"dark" | "light", ThemeColors> = {
  dark: {
    bg: "#050510",
    textPrimary: "rgba(255,255,255,0.95)",
    textSecondary: "rgba(255,255,255,0.5)",
    textMuted: "rgba(255,255,255,0.35)",
    border: "rgba(255,255,255,0.04)",
    glowOpacity: "0d",
    badgeBg: "15",
    badgeBorder: "25",
    accentGlowSuffix: "50",
    gradientBase: ["#0a0a2e", "#1a0a3e", "#0a1a2e"],
  },
  light: {
    bg: "#f5f5f7",
    textPrimary: "rgba(0,0,0,0.88)",
    textSecondary: "rgba(0,0,0,0.45)",
    textMuted: "rgba(0,0,0,0.3)",
    border: "rgba(0,0,0,0.06)",
    glowOpacity: "12",
    badgeBg: "10",
    badgeBorder: "20",
    accentGlowSuffix: "40",
    gradientBase: ["#e8e8f0", "#f0e8f4", "#e8f0f0"],
  },
};