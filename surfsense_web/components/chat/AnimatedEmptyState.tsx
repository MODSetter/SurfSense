"use client";
import { cn } from "@/lib/utils";
import { Manrope } from "next/font/google";
import React, { useRef, useEffect, useState } from "react";
import { RoughNotation, RoughNotationGroup } from "react-rough-notation";
import { useInView } from "framer-motion";
import { useSidebar } from "@/components/ui/sidebar";

const manrope = Manrope({ subsets: ["latin"], weight: ["400", "700"] });

export function AnimatedEmptyState() {
  const ref = useRef(null);
  const isInView = useInView(ref);
  const { state } = useSidebar();
  const [shouldShowHighlight, setShouldShowHighlight] = useState(false);
  const [layoutStable, setLayoutStable] = useState(true);

  // Track sidebar state changes and manage highlight visibility
  useEffect(() => {
    // Set layout as unstable when sidebar state changes
    setLayoutStable(false);
    setShouldShowHighlight(false);

    // Wait for layout to stabilize after sidebar transition
    const stabilizeTimer = setTimeout(() => {
      setLayoutStable(true);
    }, 300); // Wait for sidebar transition (200ms) + buffer

    return () => clearTimeout(stabilizeTimer);
  }, [state]);

  // Re-enable highlights after layout stabilizes and component is in view
  useEffect(() => {
    if (layoutStable && isInView) {
      const showTimer = setTimeout(() => {
        setShouldShowHighlight(true);
      }, 100); // Small delay to ensure layout is fully settled

      return () => clearTimeout(showTimer);
    } else {
      setShouldShowHighlight(false);
    }
  }, [layoutStable, isInView]);

  return (
    <div
      ref={ref}
      className="flex-1 flex items-center justify-center w-full min-h-[400px]"
    >
      <div className="max-w-4xl mx-auto px-4 py-10 text-center">
        <RoughNotationGroup show={shouldShowHighlight}>
          <h1
            className={cn(
              "text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-neutral-900 dark:text-neutral-50 mb-6",
              manrope.className,
            )}
          >
            <RoughNotation
              type="highlight"
              animationDuration={2000}
              iterations={3}
              color="#3b82f680"
              multiline
            >
              <span>SurfSense</span>
            </RoughNotation>
          </h1>

          <p className="text-lg sm:text-xl text-neutral-600 dark:text-neutral-300 mb-8 max-w-2xl mx-auto">
            <RoughNotation
              type="underline"
              animationDuration={2000}
              iterations={3}
              color="#10b981"
            >
              Let's Start Surfing
            </RoughNotation>{" "}
            through your knowledge base.
          </p>
        </RoughNotationGroup>
      </div>
    </div>
  );
}
