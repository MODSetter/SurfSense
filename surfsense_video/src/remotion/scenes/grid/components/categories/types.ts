import type { ThemeColors } from "../../../../theme";
import type { GridVariant } from "../../variant";
import type { CardItem } from "../../types";

export interface BaseCardProps {
  vmin: number;
  theme: ThemeColors;
  variant: GridVariant;
  isCenter: boolean;
}

export type CardRendererProps<T extends CardItem> = BaseCardProps & {
  item: T;
};
