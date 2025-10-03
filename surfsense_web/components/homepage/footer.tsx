"use client";
import {
	IconBrandDiscord,
	IconBrandGithub,
	IconBrandLinkedin,
	IconBrandTwitter,
} from "@tabler/icons-react";
import Link from "next/link";
import type React from "react";
import { cn } from "@/lib/utils";

export function Footer() {
	const pages = [
		{
			title: "Privacy",
			href: "/privacy",
		},
		{
			title: "Terms",
			href: "/terms",
		},
	];

	return (
		<div className="border-t border-neutral-100 dark:border-white/[0.1] px-8 py-20 w-full relative overflow-hidden">
			<div className="max-w-7xl mx-auto text-sm text-neutral-500 justify-between items-start md:px-8">
				<div className="flex flex-col items-center justify-center w-full relative">
					<div className="mr-0 md:mr-4 md:flex mb-4">
						<div className="flex items-center">
							<span className="font-medium text-black dark:text-white ml-2">SurfSense</span>
						</div>
					</div>

					<ul className="transition-colors flex sm:flex-row flex-col hover:text-text-neutral-800 text-neutral-600 dark:text-neutral-300 list-none gap-4">
						{pages.map((page) => (
							<li key={`pages-${page.title}`} className="list-none">
								<Link className="transition-colors hover:text-text-neutral-800" href={page.href}>
									{page.title}
								</Link>
							</li>
						))}
					</ul>

					<GridLineHorizontal className="max-w-7xl mx-auto mt-8" />
				</div>
				<div className="flex sm:flex-row flex-col justify-between mt-8 items-center w-full">
					<p className="text-neutral-500 dark:text-neutral-400 mb-8 sm:mb-0">
						&copy; SurfSense 2025
					</p>
					<div className="flex gap-4">
						<Link href="https://x.com/mod_setter">
							<IconBrandTwitter className="h-6 w-6 text-neutral-500 dark:text-neutral-300" />
						</Link>
						<Link href="https://www.linkedin.com/in/rohan-verma-sde/">
							<IconBrandLinkedin className="h-6 w-6 text-neutral-500 dark:text-neutral-300" />
						</Link>
						<Link href="https://github.com/MODSetter">
							<IconBrandGithub className="h-6 w-6 text-neutral-500 dark:text-neutral-300" />
						</Link>
						<Link href="https://discord.gg/ejRNvftDp9">
							<IconBrandDiscord className="h-6 w-6 text-neutral-500 dark:text-neutral-300" />
						</Link>
					</div>
				</div>
			</div>
		</div>
	);
}

const GridLineHorizontal = ({ className, offset }: { className?: string; offset?: string }) => {
	return (
		<div
			style={
				{
					"--background": "#ffffff",
					"--color": "rgba(0, 0, 0, 0.2)",
					"--height": "1px",
					"--width": "5px",
					"--fade-stop": "90%",
					"--offset": offset || "200px", //-100px if you want to keep the line inside
					"--color-dark": "rgba(255, 255, 255, 0.2)",
					maskComposite: "exclude",
				} as React.CSSProperties
			}
			className={cn(
				"w-[calc(100%+var(--offset))] h-[var(--height)]",
				"bg-[linear-gradient(to_right,var(--color),var(--color)_50%,transparent_0,transparent)]",
				"[background-size:var(--width)_var(--height)]",
				"[mask:linear-gradient(to_left,var(--background)_var(--fade-stop),transparent),_linear-gradient(to_right,var(--background)_var(--fade-stop),transparent),_linear-gradient(black,black)]",
				"[mask-composite:exclude]",
				"z-30",
				"dark:bg-[linear-gradient(to_right,var(--color-dark),var(--color-dark)_50%,transparent_0,transparent)]",
				className
			)}
		></div>
	);
};
