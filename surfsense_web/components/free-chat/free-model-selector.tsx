"use client";

import { Bot, Check, ChevronDown } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
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
import { useAnonymousMode } from "@/contexts/anonymous-mode";
import type { AnonModel } from "@/contracts/types/anonymous-chat.types";
import { anonymousChatApiService } from "@/lib/apis/anonymous-chat-api.service";
import { getProviderIcon } from "@/lib/provider-icons";
import { cn } from "@/lib/utils";

export function FreeModelSelector({ className }: { className?: string }) {
	const router = useRouter();
	const anonMode = useAnonymousMode();
	const currentSlug = anonMode.isAnonymous ? anonMode.modelSlug : "";

	const [open, setOpen] = useState(false);
	const [models, setModels] = useState<AnonModel[]>([]);

	useEffect(() => {
		const controller = new AbortController();
		anonymousChatApiService
			.getModels()
			.then((data) => {
				if (!controller.signal.aborted) setModels(data);
			})
			.catch((err) => {
				if (!controller.signal.aborted) console.error(err);
			});
		return () => controller.abort();
	}, []);

	const currentModel = useMemo(
		() => models.find((m) => m.seo_slug === currentSlug) ?? null,
		[models, currentSlug]
	);

	// Free models first, premium last; immutable sort to avoid mutating state.
	const sortedModels = useMemo(
		() => models.toSorted((a, b) => Number(a.is_premium) - Number(b.is_premium)),
		[models]
	);

	const handleSelect = useCallback(
		(model: AnonModel) => {
			setOpen(false);
			if (model.seo_slug === currentSlug) return;
			if (anonMode.isAnonymous) {
				anonMode.setModelSlug(model.seo_slug ?? "");
				anonMode.resetChat();
			}
			router.replace(`/free/${model.seo_slug}`);
		},
		[currentSlug, anonMode, router]
	);

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<Button
					variant="ghost"
					size="sm"
					role="combobox"
					aria-expanded={open}
					className={cn("gap-2 bg-muted hover:bg-muted/80", className)}
				>
					{currentModel ? (
						<>
							{getProviderIcon(currentModel.provider, { className: "size-4" })}
							<span className="max-w-[160px] truncate">{currentModel.name}</span>
						</>
					) : (
						<>
							<Bot className="size-4 text-muted-foreground" />
							<span className="text-muted-foreground">Select Model</span>
						</>
					)}
					<ChevronDown className="ml-1 size-3.5 shrink-0 text-muted-foreground" />
				</Button>
			</PopoverTrigger>
			<PopoverContent className="w-[320px] p-0" align="start" sideOffset={8}>
				<Command
					filter={(value, search) => (value.toLowerCase().includes(search.toLowerCase()) ? 1 : 0)}
				>
					<CommandInput placeholder="Search models" />
					<CommandList>
						<CommandEmpty>No models found.</CommandEmpty>
						<CommandGroup>
							{sortedModels.map((model) => {
								const isSelected = model.seo_slug === currentSlug;
								return (
									<CommandItem
										key={model.id}
										value={`${model.name} ${model.model_name} ${model.provider}`}
										onSelect={() => handleSelect(model)}
										className="gap-2.5"
									>
										<div className="shrink-0">
											{getProviderIcon(model.provider, { className: "size-5" })}
										</div>
										<div className="flex min-w-0 flex-1 flex-col">
											<div className="flex items-center gap-1.5">
												<span className="truncate text-sm font-medium">{model.name}</span>
												<Badge variant={model.is_premium ? "default" : "secondary"}>
													{model.is_premium ? "Premium" : "Free"}
												</Badge>
											</div>
											<span className="block truncate text-xs text-muted-foreground">
												{model.model_name}
											</span>
										</div>
										{isSelected && <Check className="size-4 shrink-0 text-primary" />}
									</CommandItem>
								);
							})}
						</CommandGroup>
					</CommandList>
				</Command>
			</PopoverContent>
		</Popover>
	);
}
