"use client";

import { useId, useState } from "react";
import { CheckIcon, ChevronDownIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

// Local ones first: the built-in catalog's text models, then two hosted providers.
const MODELS = [
	{ name: "Qwen3", where: "local" },
	{ name: "Gemma 4", where: "local" },
	{ name: "OpenAI", where: "hosted" },
	{ name: "Anthropic", where: "hosted" },
];

/**
 * The model as a setting: a picker the visitor can actually change. Native
 * radios underneath, so arrow keys and screen readers work without extra code;
 * the picker's label follows the choice.
 */
export function ModelPreview() {
	const name = useId();
	const [selected, setSelected] = useState(MODELS[0].name);

	return (
		<div className="flex w-full max-w-56 flex-col gap-1.5">
			<div
				aria-hidden="true"
				className="flex items-center justify-between rounded-lg bg-card px-3 py-2 text-xs font-medium text-foreground shadow-sm ring-1 ring-black/5"
			>
				{selected}
				<ChevronDownIcon className="size-3.5 text-muted-foreground" />
			</div>
			<fieldset className="m-0 flex min-w-0 flex-col rounded-lg border-0 bg-card p-1 shadow-sm ring-1 ring-black/5">
				<legend className="sr-only">Model</legend>
				{MODELS.map((model) => {
					const isSelected = model.name === selected;
					return (
						<label
							key={model.name}
							className={cn(
								"flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-xs has-focus-visible:outline-2 has-focus-visible:outline-ring",
								isSelected ? "bg-(--notice)/10" : "hover:bg-muted"
							)}
						>
							<input
								type="radio"
								name={name}
								value={model.name}
								checked={isSelected}
								onChange={() => setSelected(model.name)}
								className="sr-only"
							/>
							<span className="flex-1 text-foreground">{model.name}</span>
							<span className="text-[10px] text-muted-foreground">{model.where}</span>
							<CheckIcon
								aria-hidden="true"
								className={cn("size-3 text-(--notice)", !isSelected && "invisible")}
							/>
						</label>
					);
				})}
			</fieldset>
		</div>
	);
}
