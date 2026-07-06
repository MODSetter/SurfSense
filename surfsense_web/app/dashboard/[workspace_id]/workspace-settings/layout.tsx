import type React from "react";
import { use } from "react";
import { SearchSpaceSettingsLayoutShell } from "./layout-shell";

export default function SearchSpaceSettingsLayout({
	params,
	children,
}: {
	params: Promise<{ workspace_id: string }>;
	children: React.ReactNode;
}) {
	const { workspace_id } = use(params);

	return (
		<SearchSpaceSettingsLayoutShell workspaceId={workspace_id}>
			{children}
		</SearchSpaceSettingsLayoutShell>
	);
}
