import React from "react";
import { Composition } from "remotion";
import {
  COMP_NAME,
  VIDEO_FPS,
  VIDEO_HEIGHT,
  VIDEO_WIDTH,
} from "../types/constants";
import { Video, videoDuration } from "./Video";
import { DEMO_VIDEO } from "./demo";
import { introPreviews } from "./scenes/intro/preview";
import { spotlightPreviews } from "./scenes/spotlight/preview";
import { hierarchyPreviews } from "./scenes/hierarchy/preview";
import { listPreviews } from "./scenes/list/preview";
import { sequencePreviews } from "./scenes/sequence/preview";
import { chartPreviews } from "./scenes/chart/preview";
import { relationPreviews } from "./scenes/relation/preview";
import { comparisonPreviews } from "./scenes/comparison/preview";
import { outroPreviews } from "./scenes/outro/preview";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* Main composition — receives VideoInput as props, computes duration dynamically */}
      <Composition
        id={COMP_NAME}
        component={Video}
        calculateMetadata={({ props }) => ({
          durationInFrames: videoDuration(props.scenes, VIDEO_WIDTH, VIDEO_HEIGHT),
          fps: VIDEO_FPS,
          width: VIDEO_WIDTH,
          height: VIDEO_HEIGHT,
        })}
        defaultProps={DEMO_VIDEO}
      />

      {/* Individual scene previews */}
      {introPreviews}
      {spotlightPreviews}
      {hierarchyPreviews}
      {listPreviews}
      {sequencePreviews}
      {chartPreviews}
      {relationPreviews}
      {comparisonPreviews}
      {outroPreviews}
    </>
  );
};

