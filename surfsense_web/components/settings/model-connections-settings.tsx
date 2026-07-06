"use client";

import { useAtom, useAtomValue } from "jotai";
import { Dot } from "lucide-react";
import { updateModelRolesMutationAtom } from "@/atoms/model-connections/model-connections-mutation.atoms";
import {
	globalModelConnectionsAtom,
	modelConnectionsAtom,
	modelRolesAtom,
} from "@/atoms/model-connections/model-connections-query.atoms";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import type { ConnectionRead, ModelRead } from "@/contracts/types/model-connections.types";
import { AUTO_PROVIDER_ICON_KEY, getProviderIcon } from "@/lib/provider-icons";
import { ModelProviderConnectionsPanel } from "./model-connections/model-provider-connections-panel";
import { capability, modelLabel } from "./model-connections/model-utils";
import { providerDisplay, providerIcon } from "./model-connections/provider-metadata";

function flattenModels(connections: ConnectionRead[]) {
	return connections.flatMap((connection) =>
		connection.models.map((model) => ({
			...model,
			connectionName: providerDisplay(connection.provider).name,
			connectionId: connection.id,
			provider: connection.provider,
		}))
	);
}

function roleSelectValue(modelId: number | null | undefined, models: Array<{ id: number }>) {
	if (!modelId) return "0";
	return models.some((model) => model.id === modelId) ? String(modelId) : "0";
}

function renderAutoModeOption() {
	return (
		<SelectItem value="0">
			<span className="inline-flex items-center gap-2">
				{getProviderIcon(AUTO_PROVIDER_ICON_KEY)}
				<span>Auto mode</span>
			</span>
		</SelectItem>
	);
}

export function ModelConnectionsSettings({ workspaceId }: { workspaceId: number }) {
	const searchSpaceId = workspaceId;
	const [{ data: globalConnections = [] }] = useAtom(globalModelConnectionsAtom);
	const [{ data: connections = [] }] = useAtom(modelConnectionsAtom);
	const [{ data: roles }] = useAtom(modelRolesAtom);
	const updateRoles = useAtomValue(updateModelRolesMutationAtom);

	const allConnections = [...globalConnections, ...connections];
	const enabledModels = flattenModels(allConnections).filter((model) => model.enabled);
	const chatModels = enabledModels.filter((model) => capability(model, "chat"));
	const visionModels = enabledModels.filter((model) => capability(model, "vision"));
	const imageModels = enabledModels.filter((model) => capability(model, "image_gen"));

	function renderModelOption(model: ModelRead & { connectionName: string; provider: string }) {
		return (
			<SelectItem key={model.id} value={String(model.id)}>
				<span className="inline-flex items-center gap-2">
					{providerIcon(model.provider)}
					<span className="inline-flex items-center gap-1">
						<span>{modelLabel(model)}</span>
						<Dot className="size-4 text-muted-foreground" aria-hidden="true" />
						<span>{model.connectionName}</span>
					</span>
				</span>
			</SelectItem>
		);
	}

	return (
		<div className="flex flex-col gap-6">
			<div className="flex flex-col gap-4">
				<div>
					<h3 className="text-base font-semibold">Model Roles</h3>
					<p className="text-sm text-muted-foreground">
						Pick which enabled model powers chat, vision, and image generation for this search
						space.
					</p>
				</div>
				<div className="flex w-full max-w-2xl flex-col gap-4">
					<div className="flex flex-col gap-2">
						<Label>Chat model</Label>
						<p className="text-xs text-muted-foreground">
							Primary model for chat responses and agent tasks. You can also change it from the
							chat.
						</p>
						<Select
							value={roleSelectValue(roles?.chat_model_id, chatModels)}
							onValueChange={(value) => updateRoles.mutate({ chat_model_id: Number(value) })}
						>
							<SelectTrigger className="w-full">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{renderAutoModeOption()}
								{chatModels.map(renderModelOption)}
							</SelectContent>
						</Select>
					</div>
					<div className="flex flex-col gap-2">
						<Label>Vision model</Label>
						<p className="text-xs text-muted-foreground">
							Used to understand images in uploads, documents, connectors, and automations. Falls
							back to chat model when possible.
						</p>
						<Select
							value={roleSelectValue(roles?.vision_model_id, visionModels)}
							onValueChange={(value) => updateRoles.mutate({ vision_model_id: Number(value) })}
						>
							<SelectTrigger className="w-full">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{renderAutoModeOption()}
								{visionModels.map(renderModelOption)}
							</SelectContent>
						</Select>
					</div>
					<div className="flex flex-col gap-2">
						<Label>Image generation model</Label>
						<p className="text-xs text-muted-foreground">Used when generating images in chat.</p>
						<Select
							value={roleSelectValue(roles?.image_gen_model_id, imageModels)}
							onValueChange={(value) => updateRoles.mutate({ image_gen_model_id: Number(value) })}
						>
							<SelectTrigger className="w-full">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{renderAutoModeOption()}
								{imageModels.map(renderModelOption)}
							</SelectContent>
						</Select>
					</div>
				</div>
			</div>

			<Separator />

			<ModelProviderConnectionsPanel searchSpaceId={searchSpaceId} connections={connections} />
		</div>
	);
}
