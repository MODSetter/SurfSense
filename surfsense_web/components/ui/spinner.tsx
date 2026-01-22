import { cn } from "@/lib/utils";

interface SpinnerProps {
	/** Size of the spinner */
	size?: "xs" | "sm" | "md" | "lg" | "xl";
	/** Whether to hide the track behind the spinner arc */
	hideTrack?: boolean;
	/** Additional classes to apply */
	className?: string;
}

const sizeClasses = {
	xs: "h-3 w-3 border-[1.5px]",
	sm: "h-4 w-4 border-2",
	md: "h-6 w-6 border-2",
	lg: "h-8 w-8 border-[3px]",
	xl: "h-10 w-10 border-4",
};

export function Spinner({ size = "md", hideTrack = false, className }: SpinnerProps) {
	return (
		<output
			aria-label="Loading"
			className={cn(
				"block animate-spin rounded-full",
				hideTrack ? "border-transparent" : "border-current/20",
				"border-t-current",
				sizeClasses[size],
				className
			)}
		/>
	);
}
