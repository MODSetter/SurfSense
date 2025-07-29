"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
	value?: number;
}

const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
	({ className, value = 0, ...props }, ref) => (
		<div
			ref={ref}
			className={cn("relative h-4 w-full overflow-hidden rounded-full bg-secondary", className)}
			{...props}
		>
			<div
				className="h-full bg-primary transition-all duration-300 ease-in-out"
				style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
			/>
		</div>
	)
);
Progress.displayName = "Progress";

export { Progress };
