"use client";

import { User, UserKey } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/animated-tabs";
import { ApiKeyContent } from "./components/ApiKeyContent";
import { ProfileContent } from "./components/ProfileContent";

const VALID_TABS = ["profile", "api-key"] as const;
const DEFAULT_TAB = "profile";

export default function UserSettingsPage() {
	const t = useTranslations("userSettings");
	const router = useRouter();
	const searchParams = useSearchParams();

	const tabParam = searchParams.get("tab") ?? "";
	const activeTab = VALID_TABS.includes(tabParam as (typeof VALID_TABS)[number])
		? tabParam
		: DEFAULT_TAB;

	const handleTabChange = useCallback(
		(value: string) => {
			const params = new URLSearchParams(searchParams.toString());
			params.set("tab", value);
			router.replace(`?${params.toString()}`, { scroll: false });
		},
		[router, searchParams]
	);

	return (
		<div className="h-full overflow-y-auto">
			<div className="mx-auto w-full max-w-4xl px-4 py-10">
				<Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
					<TabsList showBottomBorder>
						<TabsTrigger value="profile">
							<User className="mr-2 h-4 w-4" />
							{t("profile_nav_label")}
						</TabsTrigger>
						<TabsTrigger value="api-key">
							<UserKey className="mr-2 h-4 w-4" />
							{t("api_key_nav_label")}
						</TabsTrigger>
					</TabsList>
					<TabsContent value="profile" className="mt-6">
						<ProfileContent />
					</TabsContent>
					<TabsContent value="api-key" className="mt-6">
						<ApiKeyContent />
					</TabsContent>
				</Tabs>
			</div>
		</div>
	);
}
