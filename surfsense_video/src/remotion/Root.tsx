import React from "react";
import { Composition } from "remotion";
import {
  COMP_NAME,
  defaultMyCompProps,
  DURATION_IN_FRAMES,
  VIDEO_FPS,
  VIDEO_HEIGHT,
  VIDEO_WIDTH,
} from "../types/constants";
import { Main } from "./MyComp/Main";
import { NextLogo } from "./MyComp/NextLogo";
import { gridPreviews } from "./scenes/grid/preview";
import { hierarchyPreviews } from "./scenes/hierarchy/preview";
import { listPreviews } from "./scenes/list/preview";
import { sequencePreviews } from "./scenes/sequence/preview";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id={COMP_NAME}
        component={Main}
        durationInFrames={DURATION_IN_FRAMES}
        fps={VIDEO_FPS}
        width={VIDEO_WIDTH}
        height={VIDEO_HEIGHT}
        defaultProps={defaultMyCompProps}
      />
      <Composition
        id="NextLogo"
        component={NextLogo}
        durationInFrames={300}
        fps={30}
        width={140}
        height={140}
        defaultProps={{
          outProgress: 0,
        }}
      />
      {gridPreviews}
      {hierarchyPreviews}
      {listPreviews}
      {sequencePreviews}
    </>
  );
};



