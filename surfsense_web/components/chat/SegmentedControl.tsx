import type React from "react";
import { Button } from "@/components/ui/button";

type SegmentedControlProps<T extends string> = {
	value: T;
	onChange: (value: T) => void;
	options: Array<{
		value: T;
		label: string;
		icon: React.ReactNode;
	}>;
};

/**
 * A segmented control component for selecting between different options
 */
function SegmentedControl<T extends string>({
	value,
	onChange,
	options,
}: SegmentedControlProps<T>) {
	return (
		<div className="flex h-7 rounded-md border border-border overflow-hidden">
			{options.map((option) => (
				<Button
					key={option.value}
					className={`flex h-full items-center gap-1 px-2 text-xs transition-colors ${
						value === option.value ? "bg-primary text-primary-foreground" : "hover:bg-muted"
					}`}
					onClick={() => onChange(option.value)}
					aria-pressed={value === option.value}
				>
					{option.icon}
					<span>{option.label}</span>
				</Button>
			))}
		</div>
	);
}

export default SegmentedControl;
