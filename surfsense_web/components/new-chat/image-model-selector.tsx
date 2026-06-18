"use client";

import { useAtom, useAtomValue } from "jotai";
import { Check, ChevronDown, ImagePlus, Search, SlidersHorizontal } from "lucide-react";
import { useRouter } from "next/navigation";
import type { UIEvent } from "react";
import { useCallback, useMemo, useState } from "react";
import { updateModelRolesMutationAtom } from "@/atoms/model-connections/model-connections-mutation.atoms";
import {
	globalModelConnectionsAtom,
	modelConnectionsAtom,
	modelRolesAtom,
} from "@/atoms/model-connections/model-connections-query.atoms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerHeader,
	DrawerTitle,
	DrawerTrigger,
} from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import type { ConnectionRead, ModelRead } from "@/contracts/types/model-connections.types";
import { useIsMobile } from "@/hooks/use-mobile";
import { AUTO_PROVIDER_ICON_KEY, getProviderIcon } from "@/lib/provider-icons";
import { cn } from "@/lib/utils";
import { providerDisplay } from "../settings/model-connections/provider-metadata";

interface ImageModelSelectorProps {
	searchSpaceId: number;
	className?: string;
}

type ImageModel = ModelRead & {
	connectionId: number;
	connectionLabel: string;
	connectionScope: string;
	provider: string;
};

const AUTO_IMAGE_MODEL_ID = 0;

function connectionLabel(connection: ConnectionRead) {
	if (connection.scope === "GLOBAL") return "Global";
	return providerDisplay(connection.provider).name;
}

function flattenImageModels(connections: ConnectionRead[]) {
	return connections.flatMap((connection) =>
		connection.models
			.filter((model) => model.enabled && Boolean(model.supports_image_generation))
			.map((model) => ({
				...model,
				connectionId: connection.id,
				connectionLabel: connectionLabel(connection),
				connectionScope: connection.scope,
				provider: connection.provider,
			}))
	);
}

function isFreeGlobalModel(model: ImageModel) {
	return model.connectionScope === "GLOBAL" && model.billing_tier?.toLowerCase() === "free";
}

function modelName(model: ImageModel) {
	const name = model.display_name || model.model_id;
	if (model.connectionScope === "GLOBAL") {
		return name.replace(/\s+\(free\)$/i, "");
	}
	return name;
}

function filterImageModels(models: ImageModel[], search: string) {
	const normalized = search.trim().toLowerCase();
	if (!normalized) return models;
	return models.filter((model) =>
		[modelName(model), model.model_id, model.connectionLabel]
			.join(" ")
			.toLowerCase()
			.includes(normalized)
	);
}

function groupedModels(models: ImageModel[]) {
	return models.reduce<Record<string, ImageModel[]>>((groups, model) => {
		const key = model.connectionLabel;
		if (!groups[key]) groups[key] = [];
		groups[key].push(model);
		return groups;
	}, {});
}

export function ImageModelSelector({ searchSpaceId, className }: ImageModelSelectorProps) {
	const router = useRouter();
	const isMobile = useIsMobile();
	const [open, setOpen] = useState(false);
	const [search, setSearch] = useState("");
	const [scrollPos, setScrollPos] = useState<"top" | "middle" | "bottom">("top");
	const [{ data: globalConnections = [], isLoading: globalLoading }] = useAtom(
		globalModelConnectionsAtom
	);
	const [{ data: connections = [], isLoading: connectionsLoading }] = useAtom(modelConnectionsAtom);
	const [{ data: roles }] = useAtom(modelRolesAtom);
	const updateRoles = useAtomValue(updateModelRolesMutationAtom);

	const allImageModels = useMemo(
		() => flattenImageModels([...globalConnections, ...connections]),
		[globalConnections, connections]
	);

	const visibleImageModels = useMemo(
		() => filterImageModels(allImageModels, search),
		[allImageModels, search]
	);
	const imageModelsById = useMemo(
		() => new Map(allImageModels.map((model) => [model.id, model])),
		[allImageModels]
	);
	const selectedModelId = roles?.image_gen_model_id ?? AUTO_IMAGE_MODEL_ID;
	const selected = imageModelsById.get(selectedModelId);
	const groups = useMemo(() => groupedModels(visibleImageModels), [visibleImageModels]);
	const loading = globalLoading || connectionsLoading;
	const hasSearchQuery = search.trim().length > 0;

	function handleOpenChange(nextOpen: boolean) {
		if (!nextOpen) setSearch("");
		setOpen(nextOpen);
	}

	function selectModel(modelId: number) {
		updateRoles.mutate({ image_gen_model_id: modelId });
		setSearch("");
		setOpen(false);
	}

	function manageModelConnections() {
		setOpen(false);
		router.push(`/dashboard/${searchSpaceId}/search-space-settings/models`);
	}

	const handleScroll = useCallback((event: UIEvent<HTMLDivElement>) => {
		const el = event.currentTarget;
		const atTop = el.scrollTop <= 2;
		const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 2;
		setScrollPos(atTop ? "top" : atBottom ? "bottom" : "middle");
	}, []);

	// Only surface this control when usable image-generation models exist.
	if (!loading && allImageModels.length === 0) {
		return null;
	}

	const content = (
		<div className="flex h-[320px] select-none flex-col overflow-hidden">
			<div className="p-2">
				<div className="relative">
					<Search className="absolute left-0.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
					<Input
						value={search}
						onChange={(event) => setSearch(event.target.value)}
						placeholder="Search image models"
						className="h-8 border-0 bg-transparent pl-6 text-sm shadow-none"
					/>
				</div>
			</div>
			<div
				className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-1.5 py-1.5"
				onScroll={handleScroll}
				style={{
					maskImage: `linear-gradient(to bottom, ${scrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${scrollPos === "bottom" ? "black" : "transparent"})`,
					WebkitMaskImage: `linear-gradient(to bottom, ${scrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${scrollPos === "bottom" ? "black" : "transparent"})`,
				}}
			>
				<button
					type="button"
					className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left transition-colors hover:bg-accent hover:text-accent-foreground"
					onClick={() => selectModel(AUTO_IMAGE_MODEL_ID)}
				>
					<div className="min-w-0 flex-1">
						<div className="flex min-w-0 items-center gap-2 font-medium">
							{getProviderIcon(AUTO_PROVIDER_ICON_KEY, { className: "size-4 shrink-0" })}
							<span className="truncate">Auto</span>
						</div>
					</div>
					{selectedModelId === AUTO_IMAGE_MODEL_ID ? <Check className="h-4 w-4" /> : null}
				</button>
				{loading ? (
					<div className="flex items-center justify-center py-8">
						<Spinner />
					</div>
				) : Object.keys(groups).length === 0 ? (
					<div className="px-3 py-8 text-center text-sm text-muted-foreground">
						{hasSearchQuery
							? "No matching image models."
							: "No enabled image models. Add or enable models in Settings."}
					</div>
				) : (
					Object.entries(groups).map(([connection, models]) => (
						<div key={connection} className="mt-3">
							<div className="px-2 py-1 text-sm font-semibold text-muted-foreground">
								{connection}
							</div>
							{models.map((model) => (
								<button
									type="button"
									key={model.id}
									className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left transition-colors hover:bg-accent hover:text-accent-foreground"
									onClick={() => selectModel(model.id)}
								>
									<div className="min-w-0 flex-1">
										<div className="flex min-w-0 items-center gap-2 font-medium">
											{getProviderIcon(model.provider, { className: "size-4 shrink-0" })}
											<span className="truncate">{modelName(model)}</span>
										</div>
									</div>
									<div className="ml-3 flex shrink-0 items-center gap-2">
										{isFreeGlobalModel(model) ? (
											<Badge
												variant="secondary"
												className="h-5 shrink-0 rounded-sm border-0 bg-popover-foreground/10 px-1.5 text-[11px] text-popover-foreground hover:bg-popover-foreground/10"
											>
												Free
											</Badge>
										) : null}
										{roles?.image_gen_model_id === model.id ? <Check className="h-4 w-4" /> : null}
									</div>
								</button>
							))}
						</div>
					))
				)}
			</div>
			<div className="p-2">
				<Button
					variant="ghost"
					className="w-full justify-start rounded-md bg-foreground/5 hover:bg-foreground/10 hover:text-foreground"
					onClick={manageModelConnections}
				>
					<SlidersHorizontal className="h-4 w-4" /> Manage models
				</Button>
			</div>
		</div>
	);

	const trigger = (
		<Button
			type="button"
			variant="ghost"
			size="sm"
			className={cn(
				"h-8 min-w-0 gap-2 rounded-md px-3 text-muted-foreground transition-colors",
				"select-none",
				"hover:bg-foreground/10 hover:text-foreground",
				"data-[state=open]:bg-foreground/10 data-[state=open]:text-foreground",
				className
			)}
		>
			{selected ? (
				getProviderIcon(selected.provider, { className: "size-4 shrink-0" })
			) : (
				<ImagePlus className="size-4 shrink-0" />
			)}
			<span className="min-w-0 flex-1 truncate text-sm">
				{selected ? modelName(selected) : "Auto"}
			</span>
			<ChevronDown className="h-3.5 w-3.5 shrink-0" />
		</Button>
	);

	if (isMobile) {
		return (
			<Drawer open={open} onOpenChange={handleOpenChange}>
				<DrawerTrigger asChild>{trigger}</DrawerTrigger>
				<DrawerContent className="max-h-[85vh]">
					<DrawerHandle />
					<DrawerHeader>
						<DrawerTitle>Select Image Model</DrawerTitle>
					</DrawerHeader>
					{content}
				</DrawerContent>
			</Drawer>
		);
	}

	return (
		<Popover open={open} onOpenChange={handleOpenChange}>
			<PopoverTrigger asChild>{trigger}</PopoverTrigger>
			<PopoverContent
				align="start"
				className="w-[340px] border border-popover-border bg-popover p-0 text-popover-foreground shadow-md"
			>
				{content}
			</PopoverContent>
		</Popover>
	);
}
