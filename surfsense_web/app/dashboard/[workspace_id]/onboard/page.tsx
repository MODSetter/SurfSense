"use client";

import { useAtomValue } from "jotai";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import {
	llmSetupStatusAtomFamily,
	modelConnectionsAtom,
} from "@/atoms/model-connections/model-connections-query.atoms";
import { Logo } from "@/components/Logo";
import { ModelProviderConnectionsPanel } from "@/components/settings/model-connections/model-provider-connections-panel";
import { Button } from "@/components/ui/button";
import { useSession } from "@/hooks/use-session";
import { redirectToLogin } from "@/lib/auth-utils";

export default function OnboardPage() {
	const router = useRouter();
	const params = useParams();
	const workspaceId = Number(params.workspace_id);
	const session = useSession();
	const { data: connections = [] } = useAtomValue(modelConnectionsAtom);
	const { data: setupStatus } = useAtomValue(llmSetupStatusAtomFamily(workspaceId));

	useEffect(() => {
		if (session.status === "unauthenticated") redirectToLogin();
	}, [session.status]);

	// Leaving onboarding is the layout gate's job; here we only enable the
	// explicit CTA once the workspace can chat.
	const isReady = setupStatus?.status === "ready";

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
					workspaceId={workspaceId}
					connections={connections}
					className="flex flex-col gap-6 text-left"
					footerAction={
						<Button
							className="min-w-[112px]"
							disabled={!isReady}
							onClick={() => router.replace(`/dashboard/${workspaceId}/new-chat`)}
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
