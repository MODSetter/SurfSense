/** Remotion Studio compositions — one per card category for visual testing. */
import React from "react";
import { Composition } from "remotion";
import { GridScene, gridSceneDuration } from "./GridScene";
import { THEMES } from "../../theme";
import { deriveGridVariant } from "./variant";
import { DEMO_ITEMS } from "./demo";
import type { CardItem } from "./types";

const SEED = 42;
const THEME = "dark" as const;
const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;

const GridPreview: React.FC<{ category: CardItem["category"] }> = ({
  category,
}) => {
  const items = DEMO_ITEMS[category];
  const theme = THEMES[THEME];
  const variant = deriveGridVariant(SEED);

  return (
    <GridScene
      input={{ type: "grid", items }}
      theme={theme}
      variant={variant}
    />
  );
};

const CATEGORIES = Object.keys(DEMO_ITEMS) as CardItem["category"][];

export const gridPreviews = (
  <>
    {CATEGORIES.map((cat) => (
      <Composition
        key={`grid-${cat}`}
        id={`grid-${cat}`}
        component={() => <GridPreview category={cat} />}
        durationInFrames={gridSceneDuration(DEMO_ITEMS[cat].length)}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
    ))}
  </>
);
