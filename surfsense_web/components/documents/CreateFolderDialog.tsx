"use client";

import { FolderPlus } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
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

	useEffect(() => {
		if (open) {
			setName("");
			setTimeout(() => inputRef.current?.focus(), 0);
		}
	}, [open]);

	const handleSubmit = useCallback(
		(e?: React.FormEvent) => {
			e?.preventDefault();
			const trimmed = name.trim();
			if (!trimmed) return;
			onConfirm(trimmed);
			onOpenChange(false);
		},
		[name, onConfirm, onOpenChange],
	);

	const isSubfolder = !!parentFolderName;

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-sm">
				<DialogHeader>
					<DialogTitle className="flex items-center gap-2">
						<FolderPlus className="size-5 text-muted-foreground" />
						{isSubfolder ? "New subfolder" : "New folder"}
					</DialogTitle>
					<DialogDescription>
						{isSubfolder
							? `Create a new folder inside "${parentFolderName}".`
							: "Create a new folder at the root level."}
					</DialogDescription>
				</DialogHeader>

				<form onSubmit={handleSubmit} className="flex flex-col gap-4">
					<div className="flex flex-col gap-2">
						<Label htmlFor="folder-name">Folder name</Label>
						<Input
							ref={inputRef}
							id="folder-name"
							placeholder="e.g. Research, Notes, Archive…"
							value={name}
							onChange={(e) => setName(e.target.value)}
							maxLength={255}
							autoComplete="off"
						/>
					</div>

					<DialogFooter>
						<Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
							Cancel
						</Button>
						<Button type="submit" disabled={!name.trim()}>
							Create
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
