/** Remotion Studio compositions for list scene. */
import React from "react";
import { Composition } from "remotion";
import { ListScene } from "./ListScene";
import { THEMES } from "../../theme";
import type { ListVariant, ListLayout } from "./variant";
import { DEMO_LIST } from "./demo";
import { listSceneDuration } from "./layout";

const THEME = "dark" as const;
const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;

const ListPreview: React.FC<{ variant: ListVariant }> = ({ variant }) => {
  const theme = THEMES[THEME];
  return <ListScene input={DEMO_LIST} theme={theme} variant={variant} />;
};

const layouts: ListLayout[] = ["zigzag", "column", "row", "pyramid"];

const base: ListVariant = {
  layout: "zigzag",
  itemShape: "rounded",
  connectorStyle: "line",
  cardStyle: "accent-left",
  showIndex: true,
};

export const listPreviews = (
  <>
    {layouts.map((layout) => {
      const v: ListVariant = { ...base, layout };
      const dur = listSceneDuration(DEMO_LIST, layout, WIDTH, HEIGHT);
      return (
        <Composition
          key={layout}
          id={`list-${layout}`}
          component={() => <ListPreview variant={v} />}
          durationInFrames={dur}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
      );
    })}
    <Composition
      id="list-zigzag-pill"
      component={() => (
        <ListPreview variant={{ ...base, layout: "zigzag", itemShape: "pill", cardStyle: "minimal", showIndex: false }} />
      )}
      durationInFrames={listSceneDuration(DEMO_LIST, "zigzag", WIDTH, HEIGHT, false)}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  </>
);
