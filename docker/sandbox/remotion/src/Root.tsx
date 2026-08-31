import {parseMedia} from "@remotion/media-parser";
import type React from "react";
import {Composition, staticFile, Still} from "remotion";
import {Deck, type DeckProps} from "./Deck";
import {MindmapPng, type MindmapPngProps} from "./MindmapPng";

const defaultProps: DeckProps = {
  fps: 30,
  min_duration_in_frames: 300,
  scenes: [],
  sceneDurations: [],
};

const defaultMindmapProps: MindmapPngProps = {
  markdown: "# Mind map\n\n- Branch\n  - Leaf",
};

export const Root: React.FC = () => (
  <>
    <Composition
      id="Main"
      component={Deck}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={1}
      defaultProps={defaultProps}
      calculateMetadata={async ({props}) => {
        const sceneDurations = await Promise.all(
          props.scenes.map(async (scene) => {
            if (!scene.audio) {
              return props.min_duration_in_frames;
            }
            const {durationInSeconds} = await parseMedia({
              src: staticFile(scene.audio),
              fields: {durationInSeconds: true},
              acknowledgeRemotionLicense: true,
            });
            if (
              durationInSeconds === null ||
              !Number.isFinite(durationInSeconds)
            ) {
              throw new Error(
                `Could not measure audio for slide ${scene.slide_number}`,
              );
            }
            return Math.max(
              Math.ceil(durationInSeconds * props.fps),
              props.min_duration_in_frames,
            );
          }),
        );

        return {
          fps: props.fps,
          durationInFrames: Math.max(
            1,
            sceneDurations.reduce((sum, duration) => sum + duration, 0),
          ),
          props: {...props, sceneDurations},
        };
      }}
    />
    <Still
      id="Mindmap"
      component={MindmapPng}
      width={2400}
      height={1600}
      defaultProps={defaultMindmapProps}
    />
  </>
);
