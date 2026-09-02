"use client";

import * as RadioGroupPrimitive from "@radix-ui/react-radio-group";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export interface SegmentedControlOption {
	value: string;
	label: string;
	ariaLabel?: string;
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
	const containerRef = useRef<HTMLDivElement>(null);
	const itemRefs = useRef(new Map<string, HTMLButtonElement>());
	const [indicator, setIndicator] = useState({ offset: 0, width: 0, visible: false });

	const updateIndicator = useCallback(() => {
		const activeItem = itemRefs.current.get(value);
		if (!activeItem) {
			setIndicator((current) =>
				current.visible ? { ...current, visible: false } : current
			);
			return;
		}

		setIndicator({
			offset: activeItem.offsetLeft,
			width: activeItem.offsetWidth,
			visible: true,
		});
	}, [value]);

	useEffect(() => {
		const frame = requestAnimationFrame(updateIndicator);
		const observer = new ResizeObserver(updateIndicator);
		if (containerRef.current) observer.observe(containerRef.current);

		return () => {
			cancelAnimationFrame(frame);
			observer.disconnect();
		};
	}, [updateIndicator]);

	return (
		<div
			ref={containerRef}
			data-slot="segmented-control"
			className={cn(
				"relative inline-flex h-9 w-fit rounded-full border border-primary/10 bg-secondary/50 p-px",
				className
			)}
		>
			<span
				aria-hidden="true"
				className="pointer-events-none absolute inset-y-px left-px rounded-full bg-primary transition-[width,transform,opacity] duration-250 ease-out motion-reduce:transition-none"
				style={{
					width: indicator.width,
					transform: `translateX(${indicator.offset}px)`,
					opacity: indicator.visible ? 1 : 0,
				}}
			/>
			<RadioGroupPrimitive.Root
				value={value}
				onValueChange={onValueChange}
				aria-label={ariaLabel}
				className="relative flex items-center"
			>
				{options.map((option) => (
					<RadioGroupPrimitive.Item
						key={option.value}
						ref={(node) => {
							if (node) itemRefs.current.set(option.value, node);
							else itemRefs.current.delete(option.value);
						}}
						value={option.value}
						disabled={option.disabled}
						aria-label={option.ariaLabel}
						className="relative flex h-8 items-center justify-center rounded-full px-2.5 text-sm font-medium text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 data-[state=checked]:text-primary-foreground"
					>
						{option.label}
					</RadioGroupPrimitive.Item>
				))}
			</RadioGroupPrimitive.Root>
		</div>
	);
}
