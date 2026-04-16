import { cn } from "@/lib/utils";

export function Container({
	className,
	children,
}: {
	className?: string;
	children: React.ReactNode;
}) {
	return <div className={cn("mx-auto max-w-7xl px-4 sm:px-6 lg:px-8", className)}>{children}</div>;
}
