"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Logo } from "@/components/Logo";
import { Spinner } from "@/components/ui/spinner";
import { AmbientBackground } from "@/app/(home)/login/AmbientBackground";

interface UnifiedLoadingScreenProps {
	/** Optional message to display below the spinner */
	message?: string;
	/** Visual style variant */
	variant?: "login" | "default";
}

export function UnifiedLoadingScreen({
	message,
	variant = "default",
}: UnifiedLoadingScreenProps) {
	const [mounted, setMounted] = useState(false);

	useEffect(() => {
		setMounted(true);
	}, []);

	// Fixed-size container to prevent layout shifts
	const spinnerContainer = (
		<div className="h-12 w-12 flex items-center justify-center">
			<Spinner
				size={variant === "login" ? "lg" : "xl"}
				className={variant === "login" ? "text-muted-foreground" : "text-primary"}
			/>
		</div>
	);

	const content = variant === "login" ? (
		<div className="fixed inset-0 z-[9999] relative w-full overflow-hidden bg-background">
			<AmbientBackground />
			<div className="mx-auto flex h-screen max-w-lg flex-col items-center justify-center">
				<Logo className="rounded-md" />
				<div className="mt-8 flex flex-col items-center space-y-4">
					{spinnerContainer}
					{message && (
						<span className="text-muted-foreground text-sm min-h-[1.25rem] text-center max-w-xs">
							{message}
						</span>
					)}
				</div>
			</div>
		</div>
	) : (
		<div className="fixed inset-0 z-[9999] flex min-h-screen flex-col items-center justify-center bg-background">
			<div className="flex flex-col items-center space-y-4">
				{spinnerContainer}
				{message && (
					<span className="text-muted-foreground text-sm min-h-[1.25rem] text-center max-w-md px-4">
						{message}
					</span>
				)}
			</div>
		</div>
	);

	// Render inline during SSR, use portal after mounting
	// This prevents the black flash during initial render
	if (!mounted) {
		return content;
	}

	return createPortal(content, document.body);
}

