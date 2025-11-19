"use client";

import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface LogoProps {
	className?: string;
	href?: string;
}

export const Logo = ({ className, href = "/" }: LogoProps) => {
	return (
		<Link href={href}>
			<Image src="/icon-128.png" className={cn(className)} alt="logo" width={128} height={128} />
		</Link>
	);
};
