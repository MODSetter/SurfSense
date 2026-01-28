"use client";

import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { globalLoadingAtom } from "@/atoms/ui/loading.atoms";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

/**
 * GlobalLoadingProvider renders a persistent loading overlay.
 * The spinner is ALWAYS in the DOM to prevent animation reset when
 * loading states change between different pages/components.
 *
 * Visibility is controlled via CSS opacity/pointer-events, NOT mounting/unmounting.
 */
export function GlobalLoadingProvider({ children }: { children: React.ReactNode }) {
	const [mounted, setMounted] = useState(false);
	const { isLoading } = useAtomValue(globalLoadingAtom);

	useEffect(() => {
		setMounted(true);
	}, []);

	// The overlay is ALWAYS rendered, but visibility is controlled by CSS
	// This prevents the spinner animation from resetting
	const loadingOverlay = (
		<div
			className={cn(
				"fixed inset-0 z-[9999]",
				isLoading
					? "opacity-100 pointer-events-auto"
					: "opacity-0 pointer-events-none transition-opacity duration-150"
			)}
			aria-hidden={!isLoading}
		>
			<div className="flex min-h-screen flex-col items-center justify-center bg-background">
				<div className="h-12 w-12 flex items-center justify-center">
					<Spinner size="lg" className="text-muted-foreground" />
				</div>
			</div>
		</div>
	);

	// Render inline during SSR/before hydration, use portal after mounting
	// This prevents the white flash during initial render
	return (
		<>
			{children}
			{mounted ? createPortal(loadingOverlay, document.body) : loadingOverlay}
		</>
	);
}
