"use client";

import { compileCode } from "@/app/remotion/compiler";
import { Player } from "@remotion/player";
import { useEffect, useState } from "react";
import type React from "react";

export const VideoPreview = ({ code }: { code: string }) => {
  const [Component, setComponent] = useState<React.ComponentType | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const result = compileCode(code);
    if (result.error) setError(result.error);
    else setComponent(() => result.Component);
  }, [code]);

  if (error) return <div style={{ color: "red" }}>{error}</div>;
  if (!Component) return <div>Compiling...</div>;

  return (
    <Player
      component={Component}
      durationInFrames={180}
      fps={30}
      compositionWidth={1920}
      compositionHeight={1080}
      style={{ width: "100%", borderRadius: 8 }}
      controls
      autoPlay
      loop
    />
  );
};
