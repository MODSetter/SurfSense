import {Transformer} from "markmap-lib";
import {Markmap} from "markmap-view";
import type React from "react";
import {useEffect, useRef, useState} from "react";
import {
  AbsoluteFill,
  cancelRender,
  continueRender,
  delayRender,
} from "remotion";

export type MindmapStillProps = {
  markdown: string;
};

const LAYOUT_TIMEOUT_MS = 15_000;
const MIN_READABLE_SCALE = 0.25;
const transformer = new Transformer([]);

const nextPaint = () =>
  new Promise<void>((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
  );

export const MindmapStill: React.FC<MindmapStillProps> = ({markdown}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [renderHandle] = useState(() =>
    delayRender("Rendering mind map", {timeoutInMilliseconds: LAYOUT_TIMEOUT_MS}),
  );

  useEffect(() => {
    let disposed = false;
    let markmap: Markmap | undefined;

    const render = async () => {
      try {
        await document.fonts.ready;
        if (!svgRef.current) throw new Error("Mind-map SVG is unavailable");

        const {root} = transformer.transform(markdown);
        if (!root.children?.length) {
          throw new Error("Mind map must contain at least one child node");
        }

        // No Markmap options are supplied: export uses its built-in stylesheet,
        // default colors, default spacing, and default all-expanded state.
        markmap = Markmap.create(svgRef.current);
        await markmap.setData(root);
        await markmap.fit();
        await nextPaint();
        if (disposed) return;

        const bounds = markmap.g.node()?.getBoundingClientRect();
        const zoomState = (
          svgRef.current as SVGSVGElement & {__zoom?: {k?: number}}
        ).__zoom;
        const scale = zoomState?.k;
        if (
          !bounds ||
          ![bounds.left, bounds.top, bounds.right, bounds.bottom].every(
            Number.isFinite,
          ) ||
          bounds.width <= 0 ||
          bounds.height <= 0
        ) {
          throw new Error("Mind-map layout produced invalid bounds");
        }
        if (!Number.isFinite(scale) || (scale as number) < MIN_READABLE_SCALE) {
          throw new Error("Mind-map layout is too dense for a readable export");
        }

        continueRender(renderHandle);
      } catch (error) {
        cancelRender(error instanceof Error ? error : new Error(String(error)));
      }
    };

    void render();
    return () => {
      disposed = true;
      markmap?.destroy();
    };
  }, [markdown, renderHandle]);

  return (
    <AbsoluteFill style={{backgroundColor: "#fff"}}>
      <svg
        ref={svgRef}
        className="markmap"
        width="2400"
        height="1600"
        aria-label="Mind map"
      />
    </AbsoluteFill>
  );
};
