/** Remotion Studio compositions for spotlight scene. */
import React from "react";
import { Composition } from "remotion";
import { SpotlightScene } from "./SpotlightScene";
import { THEMES } from "../../theme";
import type { SpotlightVariant } from "./variant";
import type { SpotlightSceneInput } from "./types";
import {
  DEMO_SPOTLIGHT_SINGLE,
  DEMO_SPOTLIGHT_STATS,
  DEMO_SPOTLIGHT_MIXED,
} from "./demo";
import { spotlightSceneDuration } from "./layout";

const THEME = "dark" as const;
const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;

const Preview: React.FC<{
  variant: SpotlightVariant;
  data: SpotlightSceneInput;
}> = ({ variant, data }) => {
  const theme = THEMES[THEME];
  return <SpotlightScene input={data} theme={theme} variant={variant} />;
};

function dur(data: SpotlightSceneInput) {
  return spotlightSceneDuration(data.items.length, WIDTH, HEIGHT);
}

const base: SpotlightVariant = {
  cardBg: "gradient",
  valueStyle: "hero",
  reveal: "drawSingle",
  glowAngle: 45,
};

export const spotlightPreviews = (
  <>
    {/* Single card */}
    <Composition
      id="spotlight-single"
      component={() => <Preview variant={base} data={DEMO_SPOTLIGHT_SINGLE} />}
      durationInFrames={dur(DEMO_SPOTLIGHT_SINGLE)}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />

    {/* Stats -- drawSingle */}
    <Composition
      id="spotlight-stats"
      component={() => <Preview variant={base} data={DEMO_SPOTLIGHT_STATS} />}
      durationInFrames={dur(DEMO_SPOTLIGHT_STATS)}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    {/* Stats -- drawDouble + glass */}
    <Composition
      id="spotlight-stats-glass"
      component={() => (
        <Preview
          variant={{ ...base, cardBg: "glass", reveal: "drawDouble" }}
          data={DEMO_SPOTLIGHT_STATS}
        />
      )}
      durationInFrames={dur(DEMO_SPOTLIGHT_STATS)}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    {/* Stats -- drawBrackets + subtle */}
    <Composition
      id="spotlight-stats-brackets"
      component={() => (
        <Preview
          variant={{ ...base, cardBg: "subtle", reveal: "drawBrackets" }}
          data={DEMO_SPOTLIGHT_STATS}
        />
      )}
      durationInFrames={dur(DEMO_SPOTLIGHT_STATS)}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    {/* Stats -- drawNoisy + solid */}
    <Composition
      id="spotlight-stats-noisy"
      component={() => (
        <Preview
          variant={{ ...base, cardBg: "solid", reveal: "drawNoisy" }}
          data={DEMO_SPOTLIGHT_STATS}
        />
      )}
      durationInFrames={dur(DEMO_SPOTLIGHT_STATS)}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />

    {/* Mixed categories */}
    <Composition
      id="spotlight-mixed"
      component={() => (
        <Preview
          variant={{ ...base, reveal: "drawEdges", cardBg: "glass" }}
          data={DEMO_SPOTLIGHT_MIXED}
        />
      )}
      durationInFrames={dur(DEMO_SPOTLIGHT_MIXED)}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  </>
);
