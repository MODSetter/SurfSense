import type React from "react";
import { use } from "react";
import { WorkspaceSettingsLayoutShell } from "./layout-shell";

export default function WorkspaceSettingsLayout({
	params,
	children,
}: {
	params: Promise<{ workspace_id: string }>;
	children: React.ReactNode;
}) {
	const { workspace_id } = use(params);

	return (
		<WorkspaceSettingsLayoutShell workspaceId={workspace_id}>
			{children}
		</WorkspaceSettingsLayoutShell>
	);
}
