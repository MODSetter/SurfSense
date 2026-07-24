import type React from "react";
import { use } from "react";
import { PlaygroundLayoutShell } from "./layout-shell";

export default function PlaygroundLayout({
	params,
	children,
}: {
	params: Promise<{ workspace_id: string }>;
	children: React.ReactNode;
}) {
	const { workspace_id } = use(params);

	return <PlaygroundLayoutShell workspaceId={workspace_id}>{children}</PlaygroundLayoutShell>;
}
