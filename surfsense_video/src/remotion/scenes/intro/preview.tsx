/** Remotion Studio compositions for intro scene. */
import { Composition } from "remotion";
import { IntroScene } from "./IntroScene";
import { THEMES } from "../../theme";
import type { IntroVariant } from "./variant";
import { DEMO_INTRO, DEMO_INTRO_SHORT } from "./demo";
import { INTRO_DURATION } from "./constants";

const THEME = "dark" as const;
const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;

const base: IntroVariant = {
  animation: "fadeUp",
  bgStyle: "radialGlow",
  decor: "line",
  accentHue: 230,
};

export const introPreviews = (
  <>
    <Composition
      id="intro-fadeUp"
      component={() => <IntroScene input={DEMO_INTRO} theme={THEMES[THEME]} variant={base} />}
      durationInFrames={INTRO_DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="intro-scaleIn"
      component={() => (
        <IntroScene
          input={DEMO_INTRO}
          theme={THEMES[THEME]}
          variant={{ ...base, animation: "scaleIn", bgStyle: "gradientSweep", decor: "corners" }}
        />
      )}
      durationInFrames={INTRO_DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="intro-typewriter"
      component={() => (
        <IntroScene
          input={DEMO_INTRO}
          theme={THEMES[THEME]}
          variant={{ ...base, animation: "typewriter", bgStyle: "minimal", decor: "none" }}
        />
      )}
      durationInFrames={INTRO_DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="intro-splitReveal"
      component={() => (
        <IntroScene
          input={DEMO_INTRO}
          theme={THEMES[THEME]}
          variant={{ ...base, animation: "splitReveal", bgStyle: "particleDots", decor: "ring" }}
        />
      )}
      durationInFrames={INTRO_DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="intro-glowIn"
      component={() => (
        <IntroScene
          input={DEMO_INTRO}
          theme={THEMES[THEME]}
          variant={{ ...base, animation: "glowIn", bgStyle: "radialGlow", decor: "corners", accentHue: 160 }}
        />
      )}
      durationInFrames={INTRO_DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="intro-short"
      component={() => (
        <IntroScene
          input={DEMO_INTRO_SHORT}
          theme={THEMES[THEME]}
          variant={{ ...base, animation: "scaleIn", bgStyle: "minimal", decor: "line", accentHue: 280 }}
        />
      )}
      durationInFrames={INTRO_DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  </>
);
