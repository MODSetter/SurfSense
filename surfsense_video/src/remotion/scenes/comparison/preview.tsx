/** Remotion Studio compositions for comparison scene. */
import React from "react";
import { Composition } from "remotion";
import { ComparisonScene } from "./ComparisonScene";
import { THEMES } from "../../theme";
import type { ComparisonVariant } from "./variant";
import type { ComparisonSceneInput } from "./types";
import {
  DEMO_COMPARE_BINARY,
  DEMO_COMPARE_TABLE,
  DEMO_COMPARE_LARGE,
} from "./demo";
import { comparisonSceneDuration } from "./layout";

const THEME = "dark" as const;
const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;

const Preview: React.FC<{
  variant: ComparisonVariant;
  data: ComparisonSceneInput;
}> = ({ variant, data }) => {
  const theme = THEMES[THEME];
  return <ComparisonScene input={data} theme={theme} variant={variant} />;
};

function dur(data: ComparisonSceneInput, layout: ComparisonVariant["layout"]) {
  return comparisonSceneDuration(data, layout, WIDTH, HEIGHT);
}

const base: ComparisonVariant = {
  layout: "binary",
  cardStyle: "gradient",
  divider: "vs",
};

export const comparisonPreviews = (
  <>
    {/* Binary — gradient + VS */}
    <Composition
      id="compare-binary"
      component={() => (
        <Preview variant={{ ...base, layout: "binary", divider: "vs" }} data={DEMO_COMPARE_BINARY} />
      )}
      durationInFrames={dur(DEMO_COMPARE_BINARY, "binary")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    {/* Binary — glass + line */}
    <Composition
      id="compare-binary-glass"
      component={() => (
        <Preview
          variant={{ ...base, layout: "binary", cardStyle: "glass", divider: "line" }}
          data={DEMO_COMPARE_BINARY}
        />
      )}
      durationInFrames={dur(DEMO_COMPARE_BINARY, "binary")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    {/* Binary — outline + none */}
    <Composition
      id="compare-binary-outline"
      component={() => (
        <Preview
          variant={{ ...base, layout: "binary", cardStyle: "outline", divider: "none" }}
          data={DEMO_COMPARE_BINARY}
        />
      )}
      durationInFrames={dur(DEMO_COMPARE_BINARY, "binary")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    {/* Binary — solid + VS */}
    <Composition
      id="compare-binary-solid"
      component={() => (
        <Preview
          variant={{ ...base, layout: "binary", cardStyle: "solid", divider: "vs" }}
          data={DEMO_COMPARE_BINARY}
        />
      )}
      durationInFrames={dur(DEMO_COMPARE_BINARY, "binary")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />

    {/* Table — gradient */}
    <Composition
      id="compare-table"
      component={() => (
        <Preview variant={{ ...base, layout: "table", divider: "none" }} data={DEMO_COMPARE_TABLE} />
      )}
      durationInFrames={dur(DEMO_COMPARE_TABLE, "table")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    {/* Table — glass */}
    <Composition
      id="compare-table-glass"
      component={() => (
        <Preview
          variant={{ ...base, layout: "table", cardStyle: "glass", divider: "none" }}
          data={DEMO_COMPARE_TABLE}
        />
      )}
      durationInFrames={dur(DEMO_COMPARE_TABLE, "table")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    {/* Table — outline */}
    <Composition
      id="compare-table-outline"
      component={() => (
        <Preview
          variant={{ ...base, layout: "table", cardStyle: "outline", divider: "none" }}
          data={DEMO_COMPARE_TABLE}
        />
      )}
      durationInFrames={dur(DEMO_COMPARE_TABLE, "table")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    {/* Table — solid */}
    <Composition
      id="compare-table-solid"
      component={() => (
        <Preview
          variant={{ ...base, layout: "table", cardStyle: "solid", divider: "none" }}
          data={DEMO_COMPARE_TABLE}
        />
      )}
      durationInFrames={dur(DEMO_COMPARE_TABLE, "table")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />

    {/* Large table — long text, camera paging */}
    <Composition
      id="compare-table-large"
      component={() => (
        <Preview variant={{ ...base, layout: "table", divider: "none" }} data={DEMO_COMPARE_LARGE} />
      )}
      durationInFrames={dur(DEMO_COMPARE_LARGE, "table")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  </>
);
