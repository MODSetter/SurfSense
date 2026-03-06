/** Remotion Studio compositions for sequence scene. */
import React from "react";
import { Composition } from "remotion";
import { SequenceScene } from "./SequenceScene";
import { THEMES } from "../../theme";
import type { SequenceVariant, SequenceLayout } from "./variant";
import { DEMO_SEQUENCE } from "./demo";
import { sequenceSceneDuration } from "./layout";

const THEME = "dark" as const;
const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;

const SequencePreview: React.FC<{ variant: SequenceVariant }> = ({ variant }) => {
  const theme = THEMES[THEME];
  return <SequenceScene input={DEMO_SEQUENCE} theme={theme} variant={variant} />;
};

const layouts: SequenceLayout[] = ["steps", "timeline", "snake", "ascending", "zigzag"];

const base: SequenceVariant = {
  layout: "steps",
  itemShape: "rounded",
  arrowStyle: "solid",
  cardStyle: "top-bar",
  showStepNumber: true,
};

export const sequencePreviews = (
  <>
    {layouts.map((layout) => {
      const v: SequenceVariant = { ...base, layout };
      const dur = sequenceSceneDuration(DEMO_SEQUENCE, layout, WIDTH, HEIGHT);
      return (
        <Composition
          key={layout}
          id={`sequence-${layout}`}
          component={() => <SequencePreview variant={v} />}
          durationInFrames={dur}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
      );
    })}
    <Composition
      id="sequence-timeline-dashed"
      component={() => (
        <SequencePreview variant={{ ...base, layout: "timeline", arrowStyle: "dashed", cardStyle: "glow", showStepNumber: false }} />
      )}
      durationInFrames={sequenceSceneDuration(DEMO_SEQUENCE, "timeline", WIDTH, HEIGHT, false)}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  </>
);
