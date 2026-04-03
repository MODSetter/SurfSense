import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

export const Logo = ({
	className,
	disableLink = false,
	priority = false,
}: {
	className?: string;
	disableLink?: boolean;
	priority?: boolean;
}) => {
	const image = (
		<Image
			src="/icon-128.svg"
			className={cn("select-none dark:invert", className)}
			alt="logo"
			width={128}
			height={128}
			priority={priority}
		/>
	);

	if (disableLink) {
		return image;
	}

	return (
		<Link href="/" className="select-none">
			{image}
		</Link>
	);
};
