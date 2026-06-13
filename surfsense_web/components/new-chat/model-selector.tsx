"use client";

import { useAtom, useAtomValue } from "jotai";
import { Check, ChevronDown, Search, Settings2 } from "lucide-react";
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

interface ModelSelectorProps {
	searchSpaceId: number;
	className?: string;
}

type ChatModel = ModelRead & {
	connectionId: number;
	connectionLabel: string;
	connectionScope: string;
	provider: string;
};

function connectionLabel(connection: ConnectionRead) {
	if (connection.scope === "GLOBAL") return "Global";
	return providerDisplay(connection.provider).name;
}

function flattenChatModels(connections: ConnectionRead[]) {
	return connections.flatMap((connection) =>
		connection.models
			.filter((model) => model.enabled && Boolean(model.supports_chat))
			.map((model) => ({
				...model,
				connectionId: connection.id,
				connectionLabel: connectionLabel(connection),
				connectionScope: connection.scope,
				provider: connection.provider,
			}))
	);
}

function isFreeGlobalModel(model: ChatModel) {
	return model.connectionScope === "GLOBAL" && model.billing_tier?.toLowerCase() === "free";
}

function modelName(model: ChatModel) {
	const name = model.display_name || model.model_id;
	if (model.connectionScope === "GLOBAL") {
		return name.replace(/\s+\(free\)$/i, "");
	}
	return name;
}

function groupedModels(models: ChatModel[]) {
	return models.reduce<Record<string, ChatModel[]>>((groups, model) => {
		const key = model.connectionLabel;
		if (!groups[key]) groups[key] = [];
		groups[key].push(model);
		return groups;
	}, {});
}

export function ModelSelector({
	searchSpaceId,
	className,
}: ModelSelectorProps) {
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

	const chatModels = useMemo(() => {
		const normalized = search.trim().toLowerCase();
		const models = flattenChatModels([...globalConnections, ...connections]);
		if (!normalized) return models;
		return models.filter((model) =>
			[modelName(model), model.model_id, model.connectionLabel]
				.join(" ")
				.toLowerCase()
				.includes(normalized)
		);
	}, [globalConnections, connections, search]);

	const selected = chatModels.find((model) => model.id === roles?.chat_model_id);
	const groups = groupedModels(chatModels);
	const loading = globalLoading || connectionsLoading;

	function selectModel(modelId: number) {
		updateRoles.mutate({ chat_model_id: modelId });
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

	const content = (
		<div className="flex h-[320px] select-none flex-col overflow-hidden">
			<div className="p-2">
				<div className="relative">
					<Search className="absolute left-0.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
					<Input
						value={search}
						onChange={(event) => setSearch(event.target.value)}
						placeholder="Search chat models"
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
					onClick={() => selectModel(0)}
				>
					<div className="min-w-0 flex-1">
						<div className="flex min-w-0 items-center gap-2 font-medium">
							{getProviderIcon(AUTO_PROVIDER_ICON_KEY, { className: "size-4 shrink-0" })}
							<span className="truncate">Auto</span>
						</div>
					</div>
					{(roles?.chat_model_id ?? 0) === 0 ? <Check className="h-4 w-4" /> : null}
				</button>
				{loading ? (
					<div className="flex items-center justify-center py-8">
						<Spinner />
					</div>
				) : Object.keys(groups).length === 0 ? (
					<div className="px-3 py-8 text-center text-sm text-muted-foreground">
						No enabled chat models. Add or enable models in Settings.
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
										{/* {model.max_input_tokens ? (
											<div className="text-xs text-muted-foreground">
												{model.max_input_tokens.toLocaleString()} context
											</div>
										) : null} */}
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
										{/*
											Re-enable this once the chat composer supports image input.
											For now, surfacing `supports_image_input` in the chat model
											selector is misleading because users cannot attach images.

											{!model.supports_image_input ? (
												<Badge variant="outline" className="gap-1">
													<ImageOff className="h-3 w-3" /> No image
												</Badge>
											) : null}
										*/}
										{roles?.chat_model_id === model.id ? <Check className="h-4 w-4" /> : null}
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
					<Settings2 className="mr-2 h-4 w-4" /> Manage models
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
				getProviderIcon(AUTO_PROVIDER_ICON_KEY, { className: "size-4 shrink-0" })
			)}
			<span className="min-w-0 flex-1 truncate text-sm">
				{selected ? modelName(selected) : "Auto"}
			</span>
			<ChevronDown className="h-3.5 w-3.5 shrink-0" />
		</Button>
	);

	if (isMobile) {
		return (
			<Drawer open={open} onOpenChange={setOpen}>
				<DrawerTrigger asChild>{trigger}</DrawerTrigger>
				<DrawerContent className="max-h-[85vh]">
					<DrawerHandle />
					<DrawerHeader>
						<DrawerTitle>Select Chat Model</DrawerTitle>
					</DrawerHeader>
					{content}
				</DrawerContent>
			</Drawer>
		);
	}

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>{trigger}</PopoverTrigger>
			<PopoverContent align="start" className="w-[340px] p-0">
				{content}
			</PopoverContent>
		</Popover>
	);
}
