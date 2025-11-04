"use client";

import { ExternalLink, Info, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

export function AnnouncementBanner() {
	const [isVisible, setIsVisible] = useState(true);

	if (!isVisible) return null;

	return (
		<div className="relative bg-gradient-to-r from-blue-600 to-blue-500 dark:from-blue-700 dark:to-blue-600 border-b border-blue-700 dark:border-blue-800">
			<div className="container mx-auto px-4">
				<div className="flex items-center justify-center gap-3 py-2.5">
					<Info className="h-4 w-4 text-blue-50 flex-shrink-0" />
					<p className="text-sm text-blue-50 text-center font-medium">
						SurfSense is a work in progress.{" "}
						<a
							href="https://github.com/MODSetter/SurfSense/issues"
							target="_blank"
							rel="noopener noreferrer"
							className="inline-flex items-center gap-1 underline decoration-blue-200 underline-offset-2 hover:decoration-white transition-colors"
						>
							Report issues on GitHub
							<ExternalLink className="h-3 w-3" />
						</a>
					</p>
					<Button
						variant="ghost"
						size="sm"
						className="h-7 w-7 p-0 shrink-0 text-blue-100 hover:text-white hover:bg-blue-700/50 dark:hover:bg-blue-800/50 absolute right-4"
						onClick={() => setIsVisible(false)}
					>
						<X className="h-3.5 w-3.5" />
						<span className="sr-only">Dismiss</span>
					</Button>
				</div>
			</div>
		</div>
	);
}
