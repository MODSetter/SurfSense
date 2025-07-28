"use client";

import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

export const Logo = ({ className }: { className?: string }) => {
	return (
		<Link href="/">
			<Image src="/icon-128.png" className={cn(className)} alt="logo" width={128} height={128} />
		</Link>
	);
};
