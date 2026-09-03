"use client";

import * as RadioGroupPrimitive from "@radix-ui/react-radio-group";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface SegmentedControlOption {
	value: string;
	label: string;
	ariaLabel?: string;
	tooltip?: string;
	disabled?: boolean;
}

export interface SegmentedControlProps {
	value: string;
	options: readonly SegmentedControlOption[];
	onValueChange: (value: string) => void;
	ariaLabel: string;
	className?: string;
}

export function SegmentedControl({
	value,
	options,
	onValueChange,
	ariaLabel,
	className,
}: SegmentedControlProps) {
	const selectedIndex = options.findIndex((option) => option.value === value);
	const segmentCount = Math.max(options.length, 1);

	return (
		<div
			data-slot="segmented-control"
			className={cn(
				"relative inline-flex h-9 w-fit rounded-full border border-primary/10 bg-secondary/50 p-px",
				className
			)}
		>
			<span
				aria-hidden="true"
				className="pointer-events-none absolute inset-y-px left-px rounded-full bg-primary transition-[transform,opacity] duration-250 ease-out motion-reduce:transition-none"
				style={{
					width: `calc((100% - 2px) / ${segmentCount})`,
					transform: `translateX(${Math.max(selectedIndex, 0) * 100}%)`,
					opacity: selectedIndex >= 0 ? 1 : 0,
				}}
			/>
			<RadioGroupPrimitive.Root
				value={value}
				onValueChange={onValueChange}
				aria-label={ariaLabel}
				className="relative grid items-center"
				style={{
					gridTemplateColumns: `repeat(${segmentCount}, minmax(0, 1fr))`,
				}}
			>
				{options.map((option) => {
					const item = (
						<RadioGroupPrimitive.Item
							key={option.value}
							value={option.value}
							disabled={option.disabled}
							aria-label={option.ariaLabel}
							className="relative flex h-8 items-center justify-center rounded-full px-2.5 text-sm font-medium text-foreground/70 outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 aria-checked:text-primary-foreground"
						>
							{option.label}
						</RadioGroupPrimitive.Item>
					);

					if (!option.tooltip) return item;

					return (
						<Tooltip key={option.value}>
							<TooltipTrigger asChild>{item}</TooltipTrigger>
							<TooltipContent side="top" className="max-w-64">
								{option.tooltip}
							</TooltipContent>
						</Tooltip>
					);
				})}
			</RadioGroupPrimitive.Root>
		</div>
	);
}
