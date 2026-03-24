"use client";

import { useAtom } from "jotai";
import { useTranslations } from "next-intl";
import { TeamContent } from "@/app/dashboard/[search_space_id]/team/team-content";
import { teamDialogAtom } from "@/atoms/settings/settings-dialog.atoms";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

interface TeamDialogProps {
	searchSpaceId: number;
}

export function TeamDialog({ searchSpaceId }: TeamDialogProps) {
	const t = useTranslations("sidebar");
	const [open, setOpen] = useAtom(teamDialogAtom);

	return (
		<Dialog open={open} onOpenChange={setOpen}>
			<DialogContent
				className="select-none max-w-[900px] w-[95vw] md:w-[90vw] h-[90vh] md:h-[80vh] max-h-[640px] flex flex-col p-0 gap-0 overflow-hidden [--card:var(--background)] dark:[--card:oklch(0.205_0_0)] dark:[--background:oklch(0.205_0_0)]"
				onOpenAutoFocus={(e) => e.preventDefault()}
			>
				<DialogTitle className="sr-only">{t("manage_members")}</DialogTitle>
				<div className="flex-1 overflow-y-auto overflow-x-hidden">
					<div className="px-6 md:px-8 py-6 min-w-0">
						<TeamContent searchSpaceId={searchSpaceId} />
					</div>
				</div>
			</DialogContent>
		</Dialog>
	);
}
