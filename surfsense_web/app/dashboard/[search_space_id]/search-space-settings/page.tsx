import {
	SearchSpaceSettingsPanel,
	type SearchSpaceSettingsTab,
} from "@/components/settings/search-space-settings-panel";

const SEARCH_SPACE_SETTINGS_TABS = new Set<string>([
	"general",
	"roles",
	"models",
	"image-models",
	"vision-models",
	"team-roles",
	"prompts",
	"team-memory",
	"public-links",
]);

function getInitialTab(tab: string | string[] | undefined): SearchSpaceSettingsTab {
	const value = Array.isArray(tab) ? tab[0] : tab;
	return value && SEARCH_SPACE_SETTINGS_TABS.has(value)
		? (value as SearchSpaceSettingsTab)
		: "general";
}

export default async function SearchSpaceSettingsPage({
	params,
	searchParams,
}: {
	params: Promise<{ search_space_id: string }>;
	searchParams: Promise<{ tab?: string | string[] }>;
}) {
	const [{ search_space_id }, resolvedSearchParams] = await Promise.all([params, searchParams]);

	return (
		<SearchSpaceSettingsPanel
			searchSpaceId={search_space_id}
			initialTab={getInitialTab(resolvedSearchParams.tab)}
		/>
	);
}
