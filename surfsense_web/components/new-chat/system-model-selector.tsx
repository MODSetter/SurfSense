"use client";

import { useAtom, useAtomValue } from "jotai";
import { Bot, Check, ChevronDown, Crown, Zap } from "lucide-react";
import { useState } from "react";
import {
	selectedSystemModelIdAtom,
	systemModelsAtom,
} from "@/atoms/new-llm-config/system-models-query.atoms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Command,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import type { SystemModelItem } from "@/contracts/types/new-llm-config.types";
import { cn } from "@/lib/utils";

interface SystemModelSelectorProps {
	className?: string;
}

const TIER_CONFIG: Record<string, { label: string; icon: React.ComponentType<{ className?: string }>; variant: "default" | "secondary" | "outline" }> = {
	free: { label: "Free", icon: Zap, variant: "secondary" },
	pro: { label: "Pro", icon: Crown, variant: "default" },
	enterprise: { label: "Enterprise", icon: Crown, variant: "default" },
};

function TierBadge({ tier }: { tier: string }) {
	const config = TIER_CONFIG[tier.toLowerCase()] ?? { label: tier, icon: Zap, variant: "outline" as const };
	const Icon = config.icon;
	return (
		<Badge variant={config.variant} className="ml-auto flex items-center gap-1 text-[10px] px-1.5 py-0 h-4">
			<Icon className="h-2.5 w-2.5" />
			{config.label}
		</Badge>
	);
}

export function SystemModelSelector({ className }: SystemModelSelectorProps) {
	const [open, setOpen] = useState(false);
	const [searchQuery, setSearchQuery] = useState("");
	const { data: models, isPending } = useAtomValue(systemModelsAtom);
	const [selectedId, setSelectedId] = useAtom(selectedSystemModelIdAtom);

	const selectedModel: SystemModelItem | undefined =
		selectedId != null ? models?.find((m) => m.id === selectedId) : undefined;

	// Use first model as implicit default when nothing selected; guard empty array
	const displayModel = selectedModel ?? (models && models.length > 0 ? models[0] : undefined);

	// Auto-select the first model so the ID is available for API calls
	const effectiveId = selectedId ?? displayModel?.id ?? null;

	const filteredModels = models?.filter(
		(m) =>
			!searchQuery ||
			m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
			m.provider.toLowerCase().includes(searchQuery.toLowerCase()) ||
			m.model_name.toLowerCase().includes(searchQuery.toLowerCase())
	) ?? [];

	function handleSelect(model: SystemModelItem) {
		setSelectedId(model.id);
		setOpen(false);
		setSearchQuery("");
	}

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<Button
					variant="outline"
					size="sm"
					className={cn(
						"flex items-center gap-2 h-8 px-3 text-sm font-normal",
						className
					)}
					aria-label="Select AI model"
				>
					<Bot className="h-4 w-4 shrink-0 text-muted-foreground" />
					{isPending ? (
						<Spinner className="h-3 w-3" />
					) : displayModel ? (
						<span className="max-w-[140px] truncate">{displayModel.name}</span>
					) : (
						<span className="text-muted-foreground">Select model</span>
					)}
					<ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground ml-1" />
				</Button>
			</PopoverTrigger>
			<PopoverContent className="w-72 p-0" align="start">
				<Command shouldFilter={false}>
					<CommandInput
						placeholder="Search models…"
						value={searchQuery}
						onValueChange={setSearchQuery}
					/>
					<CommandList className="max-h-64">
						{isPending ? (
							<div className="flex items-center justify-center py-6">
								<Spinner className="h-5 w-5" />
							</div>
						) : filteredModels.length === 0 ? (
							<CommandEmpty>No models found.</CommandEmpty>
						) : (
							<CommandGroup>
								{filteredModels.map((model) => {
									const isSelected =
										selectedId === model.id ||
										(selectedId === null && displayModel?.id === model.id);
									return (
										<CommandItem
											key={model.id}
											value={String(model.id)}
											onSelect={() => handleSelect(model)}
											className="flex items-center gap-2 cursor-pointer"
										>
											<Check
												className={cn(
													"h-3.5 w-3.5 shrink-0",
													isSelected ? "opacity-100" : "opacity-0"
												)}
											/>
											<div className="flex flex-col flex-1 min-w-0">
												<span className="truncate font-medium text-sm">{model.name}</span>
												<span className="truncate text-[11px] text-muted-foreground">
													{model.model_name}
												</span>
											</div>
											<TierBadge tier={model.tier_required} />
										</CommandItem>
									);
								})}
							</CommandGroup>
						)}
					</CommandList>
				</Command>
			</PopoverContent>
		</Popover>
	);
}
