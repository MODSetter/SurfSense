"use client";

import { useAtomValue } from "jotai";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { updateModelRolesMutationAtom } from "@/atoms/model-connections/model-connections-mutation.atoms";
import {
	globalModelConnectionsAtom,
	modelConnectionsAtom,
	modelRolesAtom,
} from "@/atoms/model-connections/model-connections-query.atoms";
import { Logo } from "@/components/Logo";
import { ModelProviderConnectionsPanel } from "@/components/settings/model-connections/model-provider-connections-panel";
import { capability } from "@/components/settings/model-connections/model-utils";
import { Button } from "@/components/ui/button";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { getBearerToken, redirectToLogin } from "@/lib/auth-utils";

export default function OnboardPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);
	const { data: globalConnections = [], isFetching: globalLoading } = useAtomValue(
		globalModelConnectionsAtom
	);
	const { data: connections = [], isFetching: connectionsLoading } =
		useAtomValue(modelConnectionsAtom);
	const { data: roles = {}, isFetching: rolesLoading } = useAtomValue(modelRolesAtom);
	const { mutateAsync: updateRoles, isPending } = useAtomValue(updateModelRolesMutationAtom);
	const [isAutoConfiguring, setIsAutoConfiguring] = useState(false);
	const hasAttemptedAutoConfig = useRef(false);

	useEffect(() => {
		if (!getBearerToken()) redirectToLogin();
	}, []);

	const firstGlobalChatModel = useMemo(() => {
		for (const connection of globalConnections) {
			const model = connection.models.find((item) => item.enabled && item.supports_chat);
			if (model) return model;
		}
		return null;
	}, [globalConnections]);
	const hasEnabledChatModel = useMemo(
		() =>
			connections.some(
				(connection) =>
					connection.enabled &&
					connection.models.some((model) => model.enabled && capability(model, "chat"))
			),
		[connections]
	);

	const isComplete = (roles.chat_model_id ?? 0) !== 0 || Boolean(firstGlobalChatModel);

	useEffect(() => {
		if (globalLoading || rolesLoading || hasAttemptedAutoConfig.current) return;
		if ((roles.chat_model_id ?? 0) !== 0) {
			router.push(`/dashboard/${searchSpaceId}/new-chat`);
			return;
		}
		if (!firstGlobalChatModel) return;

		hasAttemptedAutoConfig.current = true;
		setIsAutoConfiguring(true);
		updateRoles({ chat_model_id: firstGlobalChatModel.id })
			.then(() => {
				toast.success("AI configured automatically", {
					description: `Using ${firstGlobalChatModel.display_name || firstGlobalChatModel.model_id}.`,
				});
				router.push(`/dashboard/${searchSpaceId}/new-chat`);
			})
			.catch((error) => {
				console.error("Auto-configuration failed:", error);
				toast.error("Auto-configuration failed. Add a connection manually.");
				setIsAutoConfiguring(false);
			});
	}, [
		firstGlobalChatModel,
		globalLoading,
		roles.chat_model_id,
		rolesLoading,
		router,
		searchSpaceId,
		updateRoles,
	]);

	const isLoading =
		globalLoading || connectionsLoading || rolesLoading || isAutoConfiguring || isPending;
	useGlobalLoadingEffect(isLoading);

	if (isLoading || isComplete) return null;

	return (
		<div className="flex min-h-screen select-none flex-col items-center justify-center bg-main-panel p-4">
			<div className="w-full max-w-3xl space-y-6 text-center">
				<Logo className="mx-auto h-12 w-12" />
				<div className="space-y-2">
					<h1 className="text-2xl font-semibold tracking-tight">Choose a model</h1>
					<p className="text-sm text-muted-foreground">
						Connect any supported provider, then enable the models you want SurfSense to use.
					</p>
				</div>
				<ModelProviderConnectionsPanel
					searchSpaceId={searchSpaceId}
					connections={connections}
					className="flex flex-col gap-6 text-left"
					footerAction={
						<Button
							className="min-w-[112px]"
							disabled={!hasEnabledChatModel}
							onClick={() => router.push(`/dashboard/${searchSpaceId}/new-chat`)}
						>
							Start
						</Button>
					}
					showAddProviderHeader={false}
				/>
			</div>
		</div>
	);
}
