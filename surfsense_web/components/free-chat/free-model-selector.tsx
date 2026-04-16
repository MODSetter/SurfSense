"use client";

import { Bot, Check, ChevronDown, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
	const [searchQuery, setSearchQuery] = useState("");
	const [focusedIndex, setFocusedIndex] = useState(-1);
	const searchInputRef = useRef<HTMLInputElement>(null);

	useEffect(() => {
		anonymousChatApiService.getModels().then(setModels).catch(console.error);
	}, []);

	useEffect(() => {
		if (open) {
			setSearchQuery("");
			setFocusedIndex(-1);
			requestAnimationFrame(() => searchInputRef.current?.focus());
		}
	}, [open]);

	const currentModel = useMemo(
		() => models.find((m) => m.seo_slug === currentSlug) ?? null,
		[models, currentSlug]
	);

	const sortedModels = useMemo(
		() => [...models].sort((a, b) => Number(a.is_premium) - Number(b.is_premium)),
		[models]
	);

	const filteredModels = useMemo(() => {
		if (!searchQuery.trim()) return sortedModels;
		const q = searchQuery.toLowerCase();
		return sortedModels.filter(
			(m) =>
				m.name.toLowerCase().includes(q) ||
				m.model_name.toLowerCase().includes(q) ||
				m.provider.toLowerCase().includes(q)
		);
	}, [sortedModels, searchQuery]);

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

	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent<HTMLInputElement>) => {
			const count = filteredModels.length;
			if (count === 0) return;
			switch (e.key) {
				case "ArrowDown":
					e.preventDefault();
					setFocusedIndex((p) => (p < count - 1 ? p + 1 : 0));
					break;
				case "ArrowUp":
					e.preventDefault();
					setFocusedIndex((p) => (p > 0 ? p - 1 : count - 1));
					break;
				case "Enter":
					e.preventDefault();
					if (focusedIndex >= 0 && focusedIndex < count) {
						handleSelect(filteredModels[focusedIndex]);
					}
					break;
			}
		},
		[filteredModels, focusedIndex, handleSelect]
	);

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<Button
					variant="ghost"
					size="sm"
					role="combobox"
					aria-expanded={open}
					className={cn(
						"h-8 gap-2 px-3 text-sm bg-main-panel hover:bg-accent/50 dark:hover:bg-white/6 border border-border/40 select-none",
						className
					)}
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
					<ChevronDown className="h-3.5 w-3.5 text-muted-foreground ml-1 shrink-0" />
				</Button>
			</PopoverTrigger>
			<PopoverContent
				className="w-[320px] p-0 rounded-lg shadow-lg overflow-hidden bg-white border-border/60 dark:bg-neutral-900 dark:border dark:border-white/5 select-none"
				align="start"
				sideOffset={8}
				onCloseAutoFocus={(e) => e.preventDefault()}
			>
				<div className="relative">
					<Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground pointer-events-none" />
					<input
						ref={searchInputRef}
						placeholder="Search models"
						value={searchQuery}
						onChange={(e) => setSearchQuery(e.target.value)}
						onKeyDown={handleKeyDown}
						className="w-full pl-8 pr-3 py-2.5 text-sm bg-transparent focus:outline-none placeholder:text-muted-foreground"
					/>
				</div>
				<div className="overflow-y-auto max-h-[320px] py-1 space-y-0.5">
					{filteredModels.length === 0 ? (
						<div className="flex flex-col items-center justify-center gap-2 py-8 px-4">
							<Search className="size-6 text-muted-foreground" />
							<p className="text-sm text-muted-foreground">No models found</p>
						</div>
					) : (
						filteredModels.map((model, index) => {
							const isSelected = model.seo_slug === currentSlug;
							const isFocused = focusedIndex === index;
							return (
								<div
									key={model.id}
									role="option"
									tabIndex={0}
									aria-selected={isSelected}
									onClick={() => handleSelect(model)}
									onKeyDown={(e) => {
										if (e.key === "Enter" || e.key === " ") {
											e.preventDefault();
											handleSelect(model);
										}
									}}
									onMouseEnter={() => setFocusedIndex(index)}
									className={cn(
										"group flex items-center gap-2.5 px-3 py-2 rounded-xl cursor-pointer",
										"transition-all duration-150 mx-2",
										"hover:bg-accent/40",
										isSelected && "bg-primary/6 dark:bg-primary/8",
										isFocused && "bg-accent/50"
									)}
								>
									<div className="shrink-0">
										{getProviderIcon(model.provider, { className: "size-5" })}
									</div>
									<div className="flex-1 min-w-0">
										<div className="flex items-center gap-1.5">
											<span className="font-medium text-sm truncate">{model.name}</span>
											{model.is_premium ? (
												<Badge
													variant="secondary"
													className="text-[9px] px-1 py-0 h-3.5 bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300 border-0"
												>
													Premium
												</Badge>
											) : (
												<Badge
													variant="secondary"
													className="text-[9px] px-1 py-0 h-3.5 bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300 border-0"
												>
													Free
												</Badge>
											)}
										</div>
										<span className="text-xs text-muted-foreground truncate block">
											{model.model_name}
										</span>
									</div>
									{isSelected && <Check className="size-4 text-primary shrink-0" />}
								</div>
							);
						})
					)}
				</div>
			</PopoverContent>
		</Popover>
	);
}
