"use client";

import { useAtomValue } from "jotai";
import { Menu, User } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { updateUserMutationAtom } from "@/atoms/user/user-mutation.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

interface ProfileContentProps {
	onMenuClick: () => void;
}

function AvatarDisplay({ url, fallback }: { url?: string; fallback: string }) {
	const [hasError, setHasError] = useState(false);

	useEffect(() => {
		setHasError(false);
	}, [url]);

	if (url && !hasError) {
		return (
			<img
				src={url}
				alt="Avatar"
				className="h-16 w-16 rounded-xl object-cover"
				onError={() => setHasError(true)}
			/>
		);
	}

	return (
		<div className="flex h-16 w-16 items-center justify-center rounded-xl bg-muted text-xl font-semibold text-muted-foreground">
			{fallback}
		</div>
	);
}

export function ProfileContent({ onMenuClick }: ProfileContentProps) {
	const t = useTranslations("userSettings");
	const { data: user, isLoading: isUserLoading } = useAtomValue(currentUserAtom);
	const { mutateAsync: updateUser, isPending } = useAtomValue(updateUserMutationAtom);

	const [displayName, setDisplayName] = useState("");

	useEffect(() => {
		if (user) {
			setDisplayName(user.display_name || "");
		}
	}, [user]);

	const getInitials = (email: string) => {
		const name = email.split("@")[0];
		return name.slice(0, 2).toUpperCase();
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();

		try {
			await updateUser({
				display_name: displayName || null,
			});
			toast.success(t("profile_saved"));
		} catch {
			toast.error(t("profile_save_error"));
		}
	};

	const hasChanges = displayName !== (user?.display_name || "");

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
						>
							{isUserLoading ? (
								<div className="flex items-center justify-center py-12">
									<Spinner size="md" className="text-muted-foreground" />
								</div>
							) : (
								<form onSubmit={handleSubmit} className="space-y-6">
									<div className="rounded-lg border bg-card p-6">
										<div className="flex flex-col gap-6">
											<div className="space-y-2">
												<Label>{t("profile_avatar")}</Label>
												<AvatarDisplay
													url={user?.avatar_url || undefined}
													fallback={getInitials(user?.email || "")}
												/>
											</div>

											<div className="space-y-2">
												<Label htmlFor="display-name">{t("profile_display_name")}</Label>
												<Input
													id="display-name"
													type="text"
													placeholder={user?.email?.split("@")[0]}
													value={displayName}
													onChange={(e) => setDisplayName(e.target.value)}
												/>
												<p className="text-xs text-muted-foreground">
													{t("profile_display_name_hint")}
												</p>
											</div>

											<div className="space-y-2">
												<Label>{t("profile_email")}</Label>
												<Input type="email" value={user?.email || ""} disabled />
											</div>
										</div>
									</div>

									<div className="flex justify-end">
										<Button type="submit" disabled={isPending || !hasChanges}>
											{isPending && <Spinner size="sm" className="mr-2" />}
											{t("profile_save")}
										</Button>
									</div>
								</form>
							)}
						</motion.div>
					</AnimatePresence>
				</div>
			</div>
		</motion.div>
	);
}
