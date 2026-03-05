/**
 * Shared prop types for category card renderers.
 */
import type { ThemeColors } from "../../../../theme";
import type { GridVariant } from "../../variant";
import type { CardItem } from "../../types";

/** Props shared by all card renderers (minus the item itself). */
export interface BaseCardProps {
  index: number;
  vmin: number;
  theme: ThemeColors;
  variant: GridVariant;
  isCenter: boolean;
}

/** Concrete renderer props — BaseCardProps + the typed item. */
export type CardRendererProps<T extends CardItem> = BaseCardProps & {
  item: T;
};
