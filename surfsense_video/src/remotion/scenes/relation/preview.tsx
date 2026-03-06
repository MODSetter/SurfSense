/** Remotion Studio compositions for relation scene. */
import React from "react";
import { Composition } from "remotion";
import { RelationScene } from "./RelationScene";
import { THEMES } from "../../theme";
import type { RelationVariant, RelationLayout } from "./variant";
import type { RelationSceneInput } from "./types";
import { DEMO_RELATION, DEMO_RELATION_LARGE, DEMO_RELATION_XL } from "./demo";
import { relationSceneDuration } from "./layout";

const THEME = "dark" as const;
const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;

const RelationPreview: React.FC<{
  variant: RelationVariant;
  data?: RelationSceneInput;
}> = ({ variant, data = DEMO_RELATION }) => {
  const theme = THEMES[THEME];
  return <RelationScene input={data} theme={theme} variant={variant} />;
};

const base: RelationVariant = {
  layout: "network",
  cardStyle: "gradient",
  edgeStyle: "solid",
  edgeColorMode: "gradient",
  showEdgeLabels: true,
  showArrows: true,
};

const layouts: RelationLayout[] = ["circle", "network", "dagre-tb", "dagre-lr"];

function dur(data: RelationSceneInput, layout: RelationLayout) {
  return relationSceneDuration(data, layout, WIDTH, HEIGHT);
}

export const relationPreviews = (
  <>
    {layouts.map((layout) => {
      const v: RelationVariant = { ...base, layout };
      return (
        <Composition
          key={layout}
          id={`relation-${layout}`}
          component={() => <RelationPreview variant={v} />}
          durationInFrames={dur(DEMO_RELATION, layout)}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
      );
    })}
    <Composition
      id="relation-network-glass"
      component={() => (
        <RelationPreview variant={{ ...base, cardStyle: "glass" }} />
      )}
      durationInFrames={dur(DEMO_RELATION, "network")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="relation-dagre-tb-outline"
      component={() => (
        <RelationPreview
          variant={{ ...base, layout: "dagre-tb", cardStyle: "outline", edgeStyle: "dashed" }}
        />
      )}
      durationInFrames={dur(DEMO_RELATION, "dagre-tb")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    {/* Large dataset — camera paging */}
    {layouts.map((layout) => {
      const v: RelationVariant = { ...base, layout };
      return (
        <Composition
          key={`${layout}-large`}
          id={`relation-${layout}-large`}
          component={() => <RelationPreview variant={v} data={DEMO_RELATION_LARGE} />}
          durationInFrames={dur(DEMO_RELATION_LARGE, layout)}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
      );
    })}
    {/* XL dataset — heavy camera paging on both axes */}
    {layouts.map((layout) => {
      const v: RelationVariant = { ...base, layout };
      return (
        <Composition
          key={`${layout}-xl`}
          id={`relation-${layout}-xl`}
          component={() => <RelationPreview variant={v} data={DEMO_RELATION_XL} />}
          durationInFrames={dur(DEMO_RELATION_XL, layout)}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
      );
    })}
  </>
);
