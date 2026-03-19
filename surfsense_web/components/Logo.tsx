"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";

export const Logo = ({
	className,
	disableLink = false,
}: {
	className?: string;
	disableLink?: boolean;
}) => {
	// TODO: Replace this placeholder with the actual NeoNote logo
	const placeholder = (
		<div
			className={cn(
				"flex items-center justify-center rounded-md font-bold text-white",
				className
			)}
			style={{ backgroundColor: "#1a3a2a", width: "32px", height: "32px", minWidth: "32px", minHeight: "32px" }}
		>
			NN
		</div>
	);

	if (disableLink) {
		return placeholder;
	}

	return <Link href="/">{placeholder}</Link>;
};
