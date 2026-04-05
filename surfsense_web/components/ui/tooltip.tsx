"use client";

import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type * as React from "react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const MOBILE_BREAKPOINT = 768;

function useIsTouchDevice() {
	const [isTouch, setIsTouch] = useState(false);

	useEffect(() => {
		const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
		const update = () => setIsTouch(mql.matches);
		update();
		mql.addEventListener("change", update);
		return () => mql.removeEventListener("change", update);
	}, []);

	return isTouch;
}

function TooltipProvider({
	delayDuration = 0,
	disableHoverableContent = true,
	...props
}: React.ComponentProps<typeof TooltipPrimitive.Provider>) {
	return (
		<TooltipPrimitive.Provider
			data-slot="tooltip-provider"
			delayDuration={delayDuration}
			disableHoverableContent={disableHoverableContent}
			{...props}
		/>
	);
}

function Tooltip({
	open,
	onOpenChange,
	...props
}: React.ComponentProps<typeof TooltipPrimitive.Root>) {
	const isMobile = useIsTouchDevice();

	return (
		<TooltipProvider>
			<TooltipPrimitive.Root
				data-slot="tooltip"
				open={isMobile ? false : open}
				onOpenChange={isMobile ? undefined : onOpenChange}
				{...props}
			/>
		</TooltipProvider>
	);
}

function TooltipTrigger({ ...props }: React.ComponentProps<typeof TooltipPrimitive.Trigger>) {
	return <TooltipPrimitive.Trigger data-slot="tooltip-trigger" {...props} />;
}

function TooltipContent({
	className,
	sideOffset = 4,
	children,
	...props
}: React.ComponentProps<typeof TooltipPrimitive.Content>) {
	return (
		<TooltipPrimitive.Portal>
			<TooltipPrimitive.Content
				data-slot="tooltip-content"
				sideOffset={sideOffset}
				className={cn(
					"bg-black text-white font-medium shadow-xl px-3 py-1.5 dark:bg-zinc-800 dark:text-zinc-50 border-none animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-50 w-fit rounded-md text-xs text-balance pointer-events-none select-none",
					className
				)}
				{...props}
			>
				{children}
			</TooltipPrimitive.Content>
		</TooltipPrimitive.Portal>
	);
}

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider };
