"use client";

import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

export const Logo = ({ className, disableLink = false }: { className?: string; disableLink?: boolean }) => {
	const image = (
		<Image
			src="/icon-128.svg"
			className={cn("dark:invert", className)}
			alt="logo"
			width={128}
			height={128}
		/>
	);

	if (disableLink) {
		return image;
	}

	return <Link href="/">{image}</Link>;
};
