"use client";

import { useAtomValue } from "jotai";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { updateUserMutationAtom } from "@/atoms/user/user-mutation.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

function AvatarDisplay({ url, fallback }: { url?: string; fallback: string }) {
	const [errorUrl, setErrorUrl] = useState<string>();
	const hasError = errorUrl === url;

	if (url && !hasError) {
		return (
			<Image
				src={url}
				alt="Avatar"
				width={64}
				height={64}
				className="h-16 w-16 rounded-xl object-cover"
				onError={() => setErrorUrl(url)}
				unoptimized
			/>
		);
	}

	return (
		<div className="flex h-16 w-16 items-center justify-center rounded-xl bg-muted text-xl font-semibold text-muted-foreground">
			{fallback}
		</div>
	);
}

export function ProfileContent() {
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
		<div>
			{isUserLoading ? (
				<div className="flex items-center justify-center py-12">
					<Spinner size="md" className="text-muted-foreground" />
				</div>
			) : (
				<form onSubmit={handleSubmit} className="space-y-6">
					<div className="rounded-lg bg-card">
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
									autoComplete="name"
									placeholder={user?.email?.split("@")[0]}
									value={displayName}
									onChange={(e) => setDisplayName(e.target.value)}
								/>
								<p className="text-xs text-muted-foreground">{t("profile_display_name_hint")}</p>
							</div>

							<div className="space-y-2">
								<Label>{t("profile_email")}</Label>
								<Input type="email" value={user?.email || ""} disabled />
							</div>
						</div>
					</div>

					<div className="flex justify-end">
						<Button
							type="submit"
							variant="outline"
							disabled={isPending || !hasChanges}
							className="relative gap-2 bg-white text-black hover:bg-neutral-100 dark:bg-white dark:text-black dark:hover:bg-neutral-200"
						>
							<span className={isPending ? "opacity-0" : ""}>{t("profile_save")}</span>
							{isPending && <Spinner size="sm" className="absolute" />}
						</Button>
					</div>
				</form>
			)}
		</div>
	);
}
