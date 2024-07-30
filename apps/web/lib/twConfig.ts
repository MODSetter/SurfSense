import { content, theme } from "@/tailwind.config";
import resolveConfig from "tailwindcss/resolveConfig";
import type { DefaultColors } from "tailwindcss/types/generated/colors";

export const fullTwConfig = resolveConfig({
  content,
  theme,
});

interface TailwindCustomColours extends DefaultColors {
  border: string;
  input: string;
  ring: string;
  background: string;
  foreground: string;
  primary: {
    DEFAULT: string;
    foreground: string;
  };
  secondary: {
    DEFAULT: string;
    foreground: string;
  };
  destructive: {
    DEFAULT: string;
    foreground: string;
  };
  muted: {
    DEFAULT: string;
    foreground: string;
  };
  accent: {
    DEFAULT: string;
    foreground: string;
  };
  popover: {
    DEFAULT: string;
    foreground: string;
  };
  card: {
    DEFAULT: string;
    foreground: string;
  };
}

export const twColourConfig: TailwindCustomColours = fullTwConfig.theme
  .colors as TailwindCustomColours;
