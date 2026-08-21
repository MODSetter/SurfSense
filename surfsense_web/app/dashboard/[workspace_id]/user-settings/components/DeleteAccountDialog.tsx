"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { userApiService } from "@/lib/apis/user-api.service";
import { logout } from "@/lib/auth-utils";

// Not translated: the label interpolates this exact word.
const CONFIRMATION_WORD = "DELETE";

interface DeleteAccountDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

/** Spell out what leaving costs, then erase the account. */
export function DeleteAccountDialog({ open, onOpenChange }: DeleteAccountDialogProps) {
	const t = useTranslations("userSettings");
	const [confirmation, setConfirmation] = useState("");
	const [deleting, setDeleting] = useState(false);

	useEffect(() => {
		if (open) setConfirmation("");
	}, [open]);

	const handleDelete = async () => {
		setDeleting(true);
		try {
			await userApiService.deleteMe();
			await logout();
			// Reload, not a route push: no cache should outlive the account.
			window.location.href = "/";
		} catch {
			toast.error(t("delete_account_error"));
			setDeleting(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="sm:max-w-lg">
				<DialogHeader>
					<DialogTitle>{t("delete_account_title")}</DialogTitle>
					<DialogDescription>{t("delete_account_consequences")}</DialogDescription>
				</DialogHeader>

				<div className="space-y-2">
					<Label htmlFor="delete-confirmation">
						{t("delete_account_confirm_label", { word: CONFIRMATION_WORD })}
					</Label>
					<Input
						id="delete-confirmation"
						autoComplete="off"
						value={confirmation}
						onChange={(e) => setConfirmation(e.target.value)}
					/>
				</div>

				<DialogFooter>
					<Button variant="ghost" onClick={() => onOpenChange(false)} disabled={deleting}>
						{t("delete_account_cancel")}
					</Button>
					<Button
						variant="destructive"
						onClick={handleDelete}
						disabled={confirmation !== CONFIRMATION_WORD || deleting}
						className="relative"
					>
						<span className={deleting ? "opacity-0" : ""}>{t("delete_account_confirm")}</span>
						{deleting && <Spinner size="sm" className="absolute" />}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
