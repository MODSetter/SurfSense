"use client";

import { Menu, User } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

interface ProfileContentProps {
	onMenuClick: () => void;
}

export function ProfileContent({ onMenuClick }: ProfileContentProps) {
	const t = useTranslations("userSettings");

	return (
		<motion.div
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			transition={{ delay: 0.2, duration: 0.4 }}
			className="h-full min-w-0 flex-1 overflow-hidden bg-background"
		>
			<div className="h-full overflow-y-auto">
				<div className="mx-auto max-w-4xl p-4 md:p-6 lg:p-10">
					<AnimatePresence mode="wait">
						<motion.div
							key="profile-header"
							initial={{ opacity: 0, y: 10 }}
							animate={{ opacity: 1, y: 0 }}
							exit={{ opacity: 0, y: -10 }}
							transition={{ duration: 0.3 }}
							className="mb-6 md:mb-8"
						>
							<div className="flex items-center gap-3 md:gap-4">
								<Button
									variant="outline"
									size="icon"
									onClick={onMenuClick}
									className="h-10 w-10 shrink-0 md:hidden"
								>
									<Menu className="h-5 w-5" />
								</Button>
								<motion.div
									initial={{ scale: 0.8, opacity: 0 }}
									animate={{ scale: 1, opacity: 1 }}
									transition={{ delay: 0.1, duration: 0.3 }}
									className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-primary/10 bg-gradient-to-br from-primary/20 to-primary/5 shadow-sm md:h-14 md:w-14 md:rounded-2xl"
								>
									<User className="h-5 w-5 text-primary md:h-7 md:w-7" />
								</motion.div>
								<div className="min-w-0">
									<h1 className="truncate text-lg font-bold tracking-tight md:text-2xl">
										{t("profile_title")}
									</h1>
									<p className="text-sm text-muted-foreground">{t("profile_description")}</p>
								</div>
							</div>
						</motion.div>
					</AnimatePresence>

					<AnimatePresence mode="wait">
						<motion.div
							key="profile-content"
							initial={{ opacity: 0, y: 20 }}
							animate={{ opacity: 1, y: 0 }}
							exit={{ opacity: 0, y: -20 }}
							transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
							className="space-y-6"
						>
							{/* Profile form will be added in Task 5 */}
							<div className="rounded-lg border bg-card p-6">
								<p className="text-muted-foreground">Profile settings coming soon...</p>
							</div>
						</motion.div>
					</AnimatePresence>
				</div>
			</div>
		</motion.div>
	);
}

