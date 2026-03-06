/** Remotion Studio compositions for outro scene. */
import { Composition } from "remotion";
import { OutroScene } from "./OutroScene";
import { THEMES } from "../../theme";
import type { OutroVariant } from "./variant";
import { DEMO_OUTRO, DEMO_OUTRO_MINIMAL } from "./demo";
import { OUTRO_DURATION } from "./constants";

const THEME = "dark" as const;
const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;

const base: OutroVariant = {
  animation: "fadeCenter",
  bgStyle: "radialGlow",
  decor: "line",
  accentHue: 230,
};

export const outroPreviews = (
  <>
    <Composition
      id="outro-fadeCenter"
      component={() => <OutroScene input={DEMO_OUTRO} theme={THEMES[THEME]} variant={base} />}
      durationInFrames={OUTRO_DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="outro-shrinkOut"
      component={() => (
        <OutroScene
          input={DEMO_OUTRO}
          theme={THEMES[THEME]}
          variant={{ ...base, animation: "shrinkOut", bgStyle: "vignette", decor: "ring" }}
        />
      )}
      durationInFrames={OUTRO_DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="outro-slideUp"
      component={() => (
        <OutroScene
          input={DEMO_OUTRO}
          theme={THEMES[THEME]}
          variant={{ ...base, animation: "slideUp", bgStyle: "gradientSweep", decor: "particles", accentHue: 160 }}
        />
      )}
      durationInFrames={OUTRO_DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="outro-dissolve"
      component={() => (
        <OutroScene
          input={DEMO_OUTRO}
          theme={THEMES[THEME]}
          variant={{ ...base, animation: "dissolve", bgStyle: "minimal", decor: "none", accentHue: 30 }}
        />
      )}
      durationInFrames={OUTRO_DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="outro-wipeOut"
      component={() => (
        <OutroScene
          input={DEMO_OUTRO}
          theme={THEMES[THEME]}
          variant={{ ...base, animation: "wipeOut", bgStyle: "radialGlow", decor: "ring", accentHue: 280 }}
        />
      )}
      durationInFrames={OUTRO_DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="outro-minimal"
      component={() => (
        <OutroScene
          input={DEMO_OUTRO_MINIMAL}
          theme={THEMES[THEME]}
          variant={{ ...base, animation: "fadeCenter", bgStyle: "minimal", decor: "line", accentHue: 200 }}
        />
      )}
      durationInFrames={OUTRO_DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  </>
);
