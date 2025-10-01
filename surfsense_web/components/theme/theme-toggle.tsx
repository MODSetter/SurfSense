"use client";

import { MoonIcon, SunIcon } from "lucide-react";
import { motion } from "motion/react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

export function ThemeTogglerComponent() {
	const { theme, setTheme } = useTheme();

	const [isClient, setIsClient] = useState(false);

	useEffect(() => {
		setIsClient(true);
	}, []);

	return (
		isClient && (
			<Button
				variant="ghost"
				onClick={() => {
					theme === "dark" ? setTheme("light") : setTheme("dark");
				}}
				className="w-8 h-8 flex hover:bg-gray-50 dark:hover:bg-white/[0.1] rounded-lg items-center cursor-pointer justify-center outline-none focus:ring-0 focus:outline-none active:ring-0 active:outline-none overflow-hidden"
			>
				{theme === "light" && (
					<motion.div
						key={theme}
						initial={{
							x: 40,
							opacity: 0,
						}}
						animate={{
							x: 0,
							opacity: 1,
						}}
						transition={{
							duration: 0.3,
							ease: "easeOut",
						}}
					>
						<SunIcon className="h-4 w-4 flex-shrink-0  dark:text-neutral-500 text-neutral-700" />
					</motion.div>
				)}

				{theme === "dark" && (
					<motion.div
						key={theme}
						initial={{
							x: 40,
							opacity: 0,
						}}
						animate={{
							x: 0,
							opacity: 1,
						}}
						transition={{
							ease: "easeOut",
							duration: 0.3,
						}}
					>
						<MoonIcon className="h-4 w-4 flex-shrink-0 " />
					</motion.div>
				)}

				<span className="sr-only">Toggle theme</span>
			</Button>
		)
	);
}
