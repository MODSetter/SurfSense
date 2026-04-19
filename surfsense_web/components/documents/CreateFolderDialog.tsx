"use client";

import { useCallback, useRef, useState } from "react";
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

interface CreateFolderDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	parentFolderName?: string | null;
	onConfirm: (name: string) => void;
}

export function CreateFolderDialog({
	open,
	onOpenChange,
	parentFolderName,
	onConfirm,
}: CreateFolderDialogProps) {
	const [name, setName] = useState("");
	const inputRef = useRef<HTMLInputElement>(null);

	const handleOpenChange = useCallback(
		(next: boolean) => {
			if (next) {
				setName("");
				setTimeout(() => inputRef.current?.focus(), 0);
			}
			onOpenChange(next);
		},
		[onOpenChange]
	);

	const handleSubmit = useCallback(
		(e?: React.FormEvent) => {
			e?.preventDefault();
			const trimmed = name.trim();
			if (!trimmed) return;
			onConfirm(trimmed);
			onOpenChange(false);
		},
		[name, onConfirm, onOpenChange]
	);

	const isSubfolder = !!parentFolderName;

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent className="select-none max-w-[90vw] sm:max-w-sm p-4 sm:p-5 data-[state=open]:animate-none data-[state=closed]:animate-none">
				<DialogHeader className="space-y-2 pb-2">
					<div className="flex items-center gap-2 sm:gap-3">
						<div className="flex-1 min-w-0">
							<DialogTitle className="text-base sm:text-lg">
								{isSubfolder ? "New subfolder" : "New folder"}
							</DialogTitle>
							<DialogDescription className="text-xs sm:text-sm mt-0.5">
								{isSubfolder
									? `Create a new folder inside "${parentFolderName}".`
									: "Create a new folder at the root level."}
							</DialogDescription>
						</div>
					</div>
				</DialogHeader>

				<form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:gap-4">
					<div className="flex flex-col gap-2">
						<Label htmlFor="folder-name" className="text-sm">
							Folder name
						</Label>
						<Input
							ref={inputRef}
							id="folder-name"
							placeholder="e.g. Research, Notes, Archive…"
							value={name}
							onChange={(e) => setName(e.target.value)}
							maxLength={255}
							autoComplete="off"
							className="text-sm h-9 sm:h-10"
						/>
					</div>

					<DialogFooter className="flex-row justify-end pt-2 sm:pt-3">
						<Button
							type="button"
							variant="secondary"
							onClick={() => onOpenChange(false)}
							className="h-8 sm:h-9 text-xs sm:text-sm"
						>
							Cancel
						</Button>
						<Button type="submit" disabled={!name.trim()} className="h-8 sm:h-9 text-xs sm:text-sm">
							Create
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
