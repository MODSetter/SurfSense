"use client";

import { useAtomValue } from "jotai";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { updateModelRolesMutationAtom } from "@/atoms/model-connections/model-connections-mutation.atoms";
import {
	globalModelConnectionsAtom,
	modelRolesAtom,
} from "@/atoms/model-connections/model-connections-query.atoms";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { getBearerToken, redirectToLogin } from "@/lib/auth-utils";

export default function OnboardPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);
	const { data: globalConnections = [], isFetching: globalLoading } = useAtomValue(
		globalModelConnectionsAtom
	);
	const { data: roles = {}, isFetching: rolesLoading } = useAtomValue(modelRolesAtom);
	const { mutateAsync: updateRoles, isPending } = useAtomValue(updateModelRolesMutationAtom);
	const [isAutoConfiguring, setIsAutoConfiguring] = useState(false);
	const hasAttemptedAutoConfig = useRef(false);

	useEffect(() => {
		if (!getBearerToken()) redirectToLogin();
	}, []);

	const firstGlobalChatModel = useMemo(() => {
		for (const connection of globalConnections) {
			const model = connection.models.find((item) => item.enabled && item.capabilities?.chat);
			if (model) return model;
		}
		return null;
	}, [globalConnections]);

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

	const isLoading = globalLoading || rolesLoading || isAutoConfiguring || isPending;
	useGlobalLoadingEffect(isLoading);

	if (isLoading || isComplete) return null;

	return (
		<div className="flex h-screen select-none flex-col items-center justify-center bg-main-panel p-4">
			<div className="w-full max-w-md space-y-6 rounded-xl border bg-main-panel p-8 text-center">
				<Logo className="mx-auto h-12 w-12" />
				<div className="space-y-2">
					<h1 className="text-2xl font-semibold tracking-tight">Connect a Model</h1>
					<p className="text-sm text-muted-foreground">
						Add one connection, discover its models, then choose a chat model for this search space.
					</p>
				</div>
				<Button
					className="min-w-[180px]"
					onClick={() => router.push(`/dashboard/${searchSpaceId}/search-space-settings/models`)}
				>
					Open Models Settings
				</Button>
				{isPending ? <Spinner size="sm" /> : null}
			</div>
		</div>
	);
}
