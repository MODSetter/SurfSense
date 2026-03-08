"use client";

import { UserKey, User } from "lucide-react";
import { useTranslations } from "next-intl";
import {
	Tabs,
	TabsContent,
	TabsList,
	TabsTrigger,
} from "@/components/ui/animated-tabs";
import { ApiKeyContent } from "./components/ApiKeyContent";
import { ProfileContent } from "./components/ProfileContent";

export default function UserSettingsPage() {
	const t = useTranslations("userSettings");

	return (
		<div className="h-full overflow-y-auto">
			<div className="mx-auto w-full max-w-4xl px-4 py-10">
				<Tabs defaultValue="profile" className="w-full">
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
