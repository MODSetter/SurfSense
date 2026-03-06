/** Shared prop types for category card renderers. */
import type { ThemeColors } from "../../../../theme";
import type { SpotlightVariant } from "../../variant";
import type { CardItem } from "../../types";

export interface BaseCardProps {
  index: number;
  vmin: number;
  theme: ThemeColors;
  variant: SpotlightVariant;
}

export type CardRendererProps<T extends CardItem> = BaseCardProps & {
  item: T;
};
