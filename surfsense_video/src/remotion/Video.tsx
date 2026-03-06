/**
 * Video compositor -- renders a sequence of scenes from structured JSON input.
 * Each scene independently derives its own variant using Remotion's random().
 */
import React, { useMemo } from "react";
import { Series, useVideoConfig, random } from "remotion";
import { THEMES } from "./theme";
import type { VideoInput, SceneInput } from "./types";

import { IntroScene } from "./scenes/intro/IntroScene";
import { SpotlightScene } from "./scenes/spotlight/SpotlightScene";
import { HierarchyScene } from "./scenes/hierarchy/HierarchyScene";
import { ListScene } from "./scenes/list/ListScene";
import { SequenceScene } from "./scenes/sequence/SequenceScene";
import { ChartScene } from "./scenes/chart/ChartScene";
import { RelationScene } from "./scenes/relation/RelationScene";
import { ComparisonScene } from "./scenes/comparison/ComparisonScene";
import { OutroScene } from "./scenes/outro/OutroScene";

import { INTRO_DURATION } from "./scenes/intro/constants";
import { spotlightSceneDuration } from "./scenes/spotlight/layout";
import { hierarchySceneDuration } from "./scenes/hierarchy/layout";
import { listSceneDuration } from "./scenes/list/layout";
import { sequenceSceneDuration } from "./scenes/sequence/layout";
import { chartSceneDuration } from "./scenes/chart/layout";
import { relationSceneDuration } from "./scenes/relation/layout";
import { comparisonSceneDuration } from "./scenes/comparison/layout";
import { OUTRO_DURATION } from "./scenes/outro/constants";

import { deriveIntroVariant } from "./scenes/intro/variant";
import { deriveSpotlightVariant } from "./scenes/spotlight/variant";
import { deriveHierarchyVariant } from "./scenes/hierarchy/variant";
import { deriveListVariant } from "./scenes/list/variant";
import { deriveSequenceVariant } from "./scenes/sequence/variant";
import { deriveChartVariant } from "./scenes/chart/variant";
import { deriveRelationVariant } from "./scenes/relation/variant";
import { deriveComparisonVariant } from "./scenes/comparison/variant";
import { deriveOutroVariant } from "./scenes/outro/variant";

const THEME = THEMES["dark"];

function sceneSeed(scene: SceneInput, index: number): number {
  return Math.floor(random(`${scene.type}-${index}`) * 2147483647);
}

interface ResolvedScene {
  scene: SceneInput;
  duration: number;
  element: React.ReactNode;
}

function resolveScene(
  scene: SceneInput,
  index: number,
  width: number,
  height: number,
): ResolvedScene {
  const seed = sceneSeed(scene, index);
  const vmin = Math.min(width, height) / 100;

  switch (scene.type) {
    case "intro": {
      const variant = deriveIntroVariant(seed);
      return {
        scene, duration: INTRO_DURATION,
        element: <IntroScene input={scene} theme={THEME} variant={variant} />,
      };
    }
    case "spotlight": {
      const variant = deriveSpotlightVariant(seed);
      const duration = spotlightSceneDuration(scene.items.length, width, height);
      return {
        scene, duration,
        element: <SpotlightScene input={scene} theme={THEME} variant={variant} />,
      };
    }
    case "hierarchy": {
      const variant = deriveHierarchyVariant(seed);
      const isHoriz = variant.orientation === "left-right";
      const duration = hierarchySceneDuration(scene, width, height, isHoriz);
      return {
        scene, duration,
        element: <HierarchyScene input={scene} theme={THEME} variant={variant} />,
      };
    }
    case "list": {
      const variant = deriveListVariant(seed);
      const duration = listSceneDuration(scene, variant.layout, width, height);
      return {
        scene, duration,
        element: <ListScene input={scene} theme={THEME} variant={variant} />,
      };
    }
    case "sequence": {
      const variant = deriveSequenceVariant(seed);
      const duration = sequenceSceneDuration(scene, variant.layout, width, height);
      return {
        scene, duration,
        element: <SequenceScene input={scene} theme={THEME} variant={variant} />,
      };
    }
    case "chart": {
      const variant = deriveChartVariant(seed);
      const duration = chartSceneDuration(scene.items.length, variant.layout, width, height, vmin);
      return {
        scene, duration,
        element: <ChartScene input={scene} theme={THEME} variant={variant} />,
      };
    }
    case "relation": {
      const variant = deriveRelationVariant(seed);
      const duration = relationSceneDuration(scene, variant.layout, width, height);
      return {
        scene, duration,
        element: <RelationScene input={scene} theme={THEME} variant={variant} />,
      };
    }
    case "comparison": {
      const variant = deriveComparisonVariant(seed);
      const duration = comparisonSceneDuration(scene, variant.layout, width, height);
      return {
        scene, duration,
        element: <ComparisonScene input={scene} theme={THEME} variant={variant} />,
      };
    }
    case "outro": {
      const variant = deriveOutroVariant(seed);
      return {
        scene, duration: OUTRO_DURATION,
        element: <OutroScene input={scene} theme={THEME} variant={variant} />,
      };
    }
  }
}

export function videoDuration(input: VideoInput, width: number, height: number): number {
  let total = 0;
  for (let i = 0; i < input.scenes.length; i++) {
    const { duration } = resolveScene(input.scenes[i], i, width, height);
    total += duration;
  }
  return total;
}

interface VideoProps {
  input: VideoInput;
}

export const Video: React.FC<VideoProps> = ({ input }) => {
  const { width, height } = useVideoConfig();

  const resolved = useMemo(
    () => input.scenes.map((s, i) => resolveScene(s, i, width, height)),
    [input.scenes, width, height],
  );

  return (
    <Series>
      {resolved.map((r, i) => (
        <Series.Sequence key={`scene-${i}`} durationInFrames={r.duration}>
          {r.element}
        </Series.Sequence>
      ))}
    </Series>
  );
};
