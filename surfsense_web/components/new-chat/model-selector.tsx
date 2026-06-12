"use client";

import { useAtom, useAtomValue } from "jotai";
import { Check, ChevronDown, Cpu, ImageOff, Search, Settings2, Zap } from "lucide-react";
import { useMemo, useState } from "react";
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
	DrawerHeader,
	DrawerTitle,
	DrawerTrigger,
} from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import type { ConnectionRead, ModelRead } from "@/contracts/types/model-connections.types";
import type {
	GlobalImageGenConfig,
	GlobalNewLLMConfig,
	GlobalVisionLLMConfig,
	ImageGenerationConfig,
	NewLLMConfigPublic,
	VisionLLMConfig,
} from "@/contracts/types/new-llm-config.types";
import { useIsMobile } from "@/hooks/use-mobile";
import { getProviderIcon } from "@/lib/provider-icons";
import { cn } from "@/lib/utils";

interface ModelSelectorProps {
	onEditLLM: (config: NewLLMConfigPublic | GlobalNewLLMConfig, isGlobal: boolean) => void;
	onAddNewLLM: (provider?: string) => void;
	onEditImage?: (config: ImageGenerationConfig | GlobalImageGenConfig, isGlobal: boolean) => void;
	onAddNewImage?: (provider?: string) => void;
	onEditVision?: (config: VisionLLMConfig | GlobalVisionLLMConfig, isGlobal: boolean) => void;
	onAddNewVision?: (provider?: string) => void;
	className?: string;
}

type ChatModel = ModelRead & {
	connectionId: number;
	connectionLabel: string;
	provider: string;
};

function modelName(model: ModelRead) {
	return model.display_name || model.model_id;
}

function connectionLabel(connection: ConnectionRead) {
	if (connection.scope === "GLOBAL") return "Hosted";
	return connection.provider;
}

function flattenChatModels(connections: ConnectionRead[]) {
	return connections.flatMap((connection) =>
		connection.models
			.filter((model) => model.enabled && Boolean(model.supports_chat))
			.map((model) => ({
				...model,
				connectionId: connection.id,
				connectionLabel: connectionLabel(connection),
				provider: connection.provider,
			}))
	);
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
	onAddNewLLM,
	onEditLLM,
	onEditImage,
	onAddNewImage,
	onEditVision,
	onAddNewVision,
	className,
}: ModelSelectorProps) {
	void onEditLLM;
	void onEditImage;
	void onAddNewImage;
	void onEditVision;
	void onAddNewVision;

	const isMobile = useIsMobile();
	const [open, setOpen] = useState(false);
	const [search, setSearch] = useState("");
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

	const content = (
		<div className="flex max-h-[min(520px,80vh)] flex-col">
			<div className="border-b p-3">
				<div className="relative">
					<Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
					<Input
						value={search}
						onChange={(event) => setSearch(event.target.value)}
						placeholder="Search chat models..."
						className="pl-9"
					/>
				</div>
			</div>
			<div className="overflow-y-auto p-2">
				<button
					type="button"
					className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left hover:bg-accent"
					onClick={() => selectModel(0)}
				>
					<div className="flex items-center gap-3">
						<div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10 text-primary">
							<Zap className="h-4 w-4" />
						</div>
						<div>
							<div className="font-medium">Auto</div>
							<div className="text-xs text-muted-foreground">Use the hosted/global router</div>
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
							<div className="px-3 py-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
								{connection}
							</div>
							{models.map((model) => (
								<button
									type="button"
									key={model.id}
									className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left hover:bg-accent"
									onClick={() => selectModel(model.id)}
								>
									<div className="min-w-0">
										<div className="flex items-center gap-2 truncate font-medium">
											{getProviderIcon(model.provider, { className: "size-4 shrink-0" })}
											<span className="truncate">{modelName(model)}</span>
										</div>
										<div className="truncate text-xs text-muted-foreground">{model.model_id}</div>
										{model.max_input_tokens ? (
											<div className="text-xs text-muted-foreground">
												{model.max_input_tokens.toLocaleString()} context
											</div>
										) : null}
									</div>
									<div className="ml-3 flex items-center gap-2">
										{!model.supports_image_input ? (
											<Badge variant="outline" className="gap-1">
												<ImageOff className="h-3 w-3" /> No image
											</Badge>
										) : null}
										{roles?.chat_model_id === model.id ? <Check className="h-4 w-4" /> : null}
									</div>
								</button>
							))}
						</div>
					))
				)}
			</div>
			<div className="border-t p-3">
				<Button variant="outline" className="w-full justify-start" onClick={() => onAddNewLLM()}>
					<Settings2 className="mr-2 h-4 w-4" /> Manage model connections
				</Button>
			</div>
		</div>
	);

	const trigger = (
		<Button
			type="button"
			variant="ghost"
			size="sm"
			className={cn("h-8 gap-2 rounded-full px-3 text-muted-foreground", className)}
		>
			{selected ? (
				getProviderIcon(selected.provider, { className: "size-4" })
			) : (
				<Cpu className="h-4 w-4" />
			)}
			<span className="max-w-[180px] truncate text-sm">
				{selected ? modelName(selected) : "Auto"}
			</span>
			<ChevronDown className="h-3.5 w-3.5" />
		</Button>
	);

	if (isMobile) {
		return (
			<Drawer open={open} onOpenChange={setOpen}>
				<DrawerTrigger asChild>{trigger}</DrawerTrigger>
				<DrawerContent>
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
			<PopoverContent align="start" className="w-[420px] p-0">
				{content}
			</PopoverContent>
		</Popover>
	);
}
