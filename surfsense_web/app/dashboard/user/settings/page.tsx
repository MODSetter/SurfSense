"use client";

import { Key, User } from "lucide-react";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import { ApiKeyContent } from "./components/ApiKeyContent";
import { ProfileContent } from "./components/ProfileContent";
import { type SettingsNavItem, UserSettingsSidebar } from "./components/UserSettingsSidebar";

export default function UserSettingsPage() {
	const t = useTranslations("userSettings");
	const router = useRouter();
	const [activeSection, setActiveSection] = useState("profile");
	const [isSidebarOpen, setIsSidebarOpen] = useState(false);

	const navItems: SettingsNavItem[] = [
		{
			id: "profile",
			label: t("profile_nav_label"),
			description: t("profile_nav_description"),
			icon: User,
		},
		{
			id: "api-key",
			label: t("api_key_nav_label"),
			description: t("api_key_nav_description"),
			icon: Key,
		},
	];

	const handleBackToApp = useCallback(() => {
		router.back();
	}, [router]);

	return (
		<motion.div
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			transition={{ duration: 0.3 }}
			className="fixed inset-0 z-50 flex bg-muted/40"
		>
			<div className="flex h-full w-full p-0 md:p-2">
				<div className="flex h-full w-full overflow-hidden bg-background md:rounded-xl md:border md:shadow-sm">
					<UserSettingsSidebar
						activeSection={activeSection}
						onSectionChange={setActiveSection}
						onBackToApp={handleBackToApp}
						isOpen={isSidebarOpen}
						onClose={() => setIsSidebarOpen(false)}
						navItems={navItems}
					/>
					{activeSection === "profile" && (
						<ProfileContent onMenuClick={() => setIsSidebarOpen(true)} />
					)}
					{activeSection === "api-key" && (
						<ApiKeyContent onMenuClick={() => setIsSidebarOpen(true)} />
					)}
				</div>
			</div>
		</motion.div>
	);
}
