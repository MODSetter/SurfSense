"use client";

import "./globals.css";
import posthog from "posthog-js";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    posthog.captureException(error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-4">
          <h2 className="text-xl font-semibold">Something went wrong</h2>
          <p className="text-sm text-muted-foreground">
            An unexpected error occurred.
          </p>
          <Button onClick={reset}>Try again</Button>
        </div>
      </body>
    </html>
  );
}
