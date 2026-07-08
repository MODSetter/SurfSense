import { Info } from "lucide-react";
import { WorkspaceApiAccessControl } from "@/components/settings/workspace-api-access-control";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { ApiKeyContent } from "../../user-settings/components/ApiKeyContent";

export default async function PlaygroundApiKeysPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;
	const workspaceId = Number(workspace_id);

	return (
		<div className="mx-auto w-full max-w-5xl space-y-6">
			<div className="space-y-1">
				<h2 className="text-xl font-semibold tracking-tight">API keys</h2>
				<p className="text-sm text-muted-foreground">
					Create user API keys and choose whether they can access this workspace.
				</p>
			</div>

			<Alert>
				<Info />
				<AlertDescription>
					External API calls need both a user API key and workspace API key access enabled.
				</AlertDescription>
			</Alert>

			<section>
				<WorkspaceApiAccessControl workspaceId={workspaceId} />
			</section>

			<Separator className="bg-border" />

			<section>
				<ApiKeyContent />
			</section>
		</div>
	);
}
