import { UserSettingsPanel, type UserSettingsTab } from "@/components/settings/user-settings-panel";

const USER_SETTINGS_TABS = new Set<string>([
	"profile",
	"api-key",
	"prompts",
	"community-prompts",
	"memory",
	"agent-permissions",
	"agent-status",
	"purchases",
	"desktop",
	"desktop-shortcuts",
]);

function getInitialTab(tab: string | string[] | undefined): UserSettingsTab {
	const value = Array.isArray(tab) ? tab[0] : tab;
	return value && USER_SETTINGS_TABS.has(value) ? (value as UserSettingsTab) : "profile";
}

export default async function UserSettingsPage({
	params,
	searchParams,
}: {
	params: Promise<{ search_space_id: string }>;
	searchParams: Promise<{ tab?: string | string[] }>;
}) {
	const [{ search_space_id }, resolvedSearchParams] = await Promise.all([params, searchParams]);

	return (
		<UserSettingsPanel
			searchSpaceId={search_space_id}
			initialTab={getInitialTab(resolvedSearchParams.tab)}
		/>
	);
}
