import type React from "react";
import { use } from "react";
import { UserSettingsLayoutShell } from "./layout-shell";

export default function UserSettingsLayout({
	params,
	children,
}: {
	params: Promise<{ workspace_id: string }>;
	children: React.ReactNode;
}) {
	const { workspace_id } = use(params);

	return (
		<UserSettingsLayoutShell workspaceId={workspace_id}>{children}</UserSettingsLayoutShell>
	);
}
