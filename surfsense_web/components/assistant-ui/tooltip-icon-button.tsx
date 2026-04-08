"use client";

import { Slottable } from "@radix-ui/react-slot";
import { type ComponentPropsWithRef, forwardRef, type ReactNode, useState } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";

export type TooltipIconButtonProps = ComponentPropsWithRef<typeof Button> & {
	tooltip: ReactNode;
	side?: "top" | "bottom" | "left" | "right";
	disableTooltip?: boolean;
};

export const TooltipIconButton = forwardRef<HTMLButtonElement, TooltipIconButtonProps>(
	({ children, tooltip, side = "bottom", className, disableTooltip, ...rest }, ref) => {
		const isTouchDevice = useMediaQuery("(pointer: coarse)");
		const suppressTooltip = disableTooltip || isTouchDevice;
		const [tooltipOpen, setTooltipOpen] = useState(false);

		return (
			<Tooltip
				open={suppressTooltip ? false : tooltipOpen}
				onOpenChange={suppressTooltip ? undefined : setTooltipOpen}
			>
				<TooltipTrigger asChild>
					<Button
						variant="ghost"
						size="icon"
						{...rest}
						className={cn("aui-button-icon size-6 p-1", className)}
						ref={ref}
					>
						<Slottable>{children}</Slottable>
						<span className="aui-sr-only sr-only">{tooltip}</span>
					</Button>
				</TooltipTrigger>
				<TooltipContent side={side}>{tooltip}</TooltipContent>
			</Tooltip>
		);
	}
);

TooltipIconButton.displayName = "TooltipIconButton";
