import {Audio} from "@remotion/media";
import type React from "react";
import type {ComponentType} from "react";
import {
  AbsoluteFill,
  interpolate,
  Series,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {sceneComponents} from "./scenes/generated";

export type SceneInput = {
  slide_number: number;
  code: string;
  audio?: string;
};

export type DeckProps = {
  fps: number;
  min_duration_in_frames: number;
  scenes: SceneInput[];
  sceneDurations?: number[];
};

const Watermark: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const opacity = interpolate(frame, [0, fps * 0.5], [0, 0.68], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        bottom: 28,
        right: 36,
        display: "grid",
        placeItems: "center",
        width: 44,
        height: 44,
        alignItems: "center",
        borderRadius: 9999,
        background: "rgba(0, 0, 0, 0.2)",
        backdropFilter: "blur(12px)",
        border: "1px solid rgba(255, 255, 255, 0.12)",
        pointerEvents: "none",
        zIndex: 9999,
        opacity,
      }}
    >
      <img
        src={staticFile("icon-128.svg")}
        alt=""
        style={{
          width: 28,
          height: 28,
          objectFit: "contain",
          filter: "brightness(0) invert(1)",
          opacity: 0.82,
        }}
      />
    </div>
  );
};

export const Deck: React.FC<DeckProps> = ({
  scenes,
  sceneDurations = [],
}) => {
  const {fps} = useVideoConfig();
  if (scenes.length !== sceneComponents.length) {
    throw new Error(
      `Compiled ${sceneComponents.length} scenes, received ${scenes.length} scene props`,
    );
  }

  return (
    <AbsoluteFill>
      <Series>
        {scenes.map((scene, index) => {
          const Scene = sceneComponents[index] as ComponentType;
          const durationInFrames = sceneDurations[index];
          if (!durationInFrames) {
            throw new Error(`Missing duration for slide ${scene.slide_number}`);
          }
          return (
            <Series.Sequence
              key={scene.slide_number}
              durationInFrames={durationInFrames}
              premountFor={fps}
            >
              <Scene />
              {scene.audio ? <Audio src={staticFile(scene.audio)} /> : null}
            </Series.Sequence>
          );
        })}
      </Series>
      <Watermark />
    </AbsoluteFill>
  );
};
