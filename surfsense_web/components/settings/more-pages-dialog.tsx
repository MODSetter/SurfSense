"use client";

import { useAtom } from "jotai";
import { morePagesDialogAtom } from "@/atoms/settings/settings-dialog.atoms";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { MorePagesContent } from "./more-pages-content";

export function MorePagesDialog() {
	const [open, setOpen] = useAtom(morePagesDialogAtom);

	return (
		<Dialog open={open} onOpenChange={setOpen}>
			<DialogContent
				className="select-none max-w-md w-[95vw] max-h-[90vh] flex flex-col p-0 gap-0 overflow-hidden"
				onOpenAutoFocus={(e) => e.preventDefault()}
			>
				<DialogTitle className="sr-only">Get More Pages</DialogTitle>
				<div className="flex-1 overflow-y-auto p-6">
					<MorePagesContent />
				</div>
			</DialogContent>
		</Dialog>
	);
}
