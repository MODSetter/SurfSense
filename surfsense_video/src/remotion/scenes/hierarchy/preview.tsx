/** Remotion Studio compositions for hierarchy scene. */
import React from "react";
import { Composition } from "remotion";
import { HierarchyScene } from "./HierarchyScene";
import { hierarchySceneDuration } from "./layout";
import { THEMES } from "../../theme";
import type { HierarchyVariant } from "./variant";
import { DEMO_HIERARCHY } from "./demo";

const THEME = "dark" as const;
const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;

const HierarchyPreview: React.FC<{ variant: HierarchyVariant }> = ({ variant }) => {
  const theme = THEMES[THEME];
  return <HierarchyScene input={DEMO_HIERARCHY} theme={theme} variant={variant} />;
};

const base: HierarchyVariant = {
  orientation: "top-bottom",
  edgeType: "curved",
  edgeColorMode: "gradient",
  nodeShape: "rounded",
  cardStyle: "gradient",
  edgeCornerRadius: 0.8,
};

const variants: { id: string; v: HierarchyVariant }[] = [
  { id: "tb-curved-gradient-rounded", v: { ...base } },
  { id: "tb-straight-solid-pill", v: { ...base, edgeType: "straight", edgeColorMode: "solid", nodeShape: "pill" } },
  { id: "tb-curved-solid-rounded", v: { ...base, edgeColorMode: "solid" } },
  { id: "tb-straight-gradient-rounded", v: { ...base, edgeType: "straight" } },
  { id: "lr-curved-gradient-rounded", v: { ...base, orientation: "left-right" } },
  { id: "lr-straight-solid-pill", v: { ...base, orientation: "left-right", edgeType: "straight", edgeColorMode: "solid", nodeShape: "pill" } },
];

export const hierarchyPreviews = (
  <>
    {variants.map(({ id, v }) => {
      const isHoriz = v.orientation === "left-right";
      const dur = hierarchySceneDuration(DEMO_HIERARCHY, WIDTH, HEIGHT, isHoriz);
      return (
        <Composition
          key={id}
          id={`hierarchy-${id}`}
          component={() => <HierarchyPreview variant={v} />}
          durationInFrames={dur}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
      );
    })}
  </>
);
