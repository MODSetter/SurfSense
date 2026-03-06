"use client";

import { Player } from "@remotion/player";
import type { NextPage } from "next";
import React, { useMemo } from "react";
import { Video, videoDuration } from "../remotion/Video";
import { DEMO_VIDEO } from "../remotion/demo";
import {
  VIDEO_FPS,
  VIDEO_HEIGHT,
  VIDEO_WIDTH,
} from "../types/constants";

const container: React.CSSProperties = {
  maxWidth: 960,
  margin: "auto",
  marginBottom: 20,
  paddingLeft: 16,
  paddingRight: 16,
};

const outer: React.CSSProperties = {
  borderRadius: "var(--geist-border-radius)",
  overflow: "hidden",
  boxShadow: "0 0 200px rgba(0, 0, 0, 0.15)",
  marginBottom: 40,
  marginTop: 60,
};

const player: React.CSSProperties = {
  width: "100%",
};

const Home: NextPage = () => {
  const duration = useMemo(
    () => videoDuration(DEMO_VIDEO.scenes, VIDEO_WIDTH, VIDEO_HEIGHT),
    [],
  );

  return (
    <div>
      <div style={container}>
        <div className="cinematics" style={outer}>
          <Player
            component={Video}
            inputProps={DEMO_VIDEO}
            durationInFrames={duration}
            fps={VIDEO_FPS}
            compositionHeight={VIDEO_HEIGHT}
            compositionWidth={VIDEO_WIDTH}
            style={player}
            controls
            autoPlay
            loop
          />
        </div>
      </div>
    </div>
  );
};

export default Home;
