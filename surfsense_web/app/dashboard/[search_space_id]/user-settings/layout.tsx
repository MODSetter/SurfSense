import type React from "react";
import { use } from "react";
import { UserSettingsLayoutShell } from "./layout-shell";

export default function UserSettingsLayout({
	params,
	children,
}: {
	params: Promise<{ search_space_id: string }>;
	children: React.ReactNode;
}) {
	const { search_space_id } = use(params);

	return (
		<UserSettingsLayoutShell searchSpaceId={search_space_id}>{children}</UserSettingsLayoutShell>
	);
}
