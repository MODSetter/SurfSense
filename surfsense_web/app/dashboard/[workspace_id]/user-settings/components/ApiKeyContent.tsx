"use client";

import { Check, Copy, Info, Trash2 } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { usePats } from "@/hooks/use-pats";
import { copyToClipboard as copyToClipboardUtil } from "@/lib/utils";

export function ApiKeyContent() {
	const { tokens, createdToken, setCreatedToken, isLoading, isMutating, createToken, deleteToken } =
		usePats();
	const [createOpen, setCreateOpen] = useState(false);
	const [label, setLabel] = useState("");
	const [expiresInDays, setExpiresInDays] = useState("");
	const [copiedToken, setCopiedToken] = useState(false);
	const [deleteTarget, setDeleteTarget] = useState<{ id: number; label: string } | null>(null);

	const sortedTokens = useMemo(() => tokens, [tokens]);

	const handleCreate = useCallback(async () => {
		const trimmedLabel = label.trim();
		if (!trimmedLabel) return;

		await createToken({
			label: trimmedLabel,
			expires_in_days: expiresInDays ? Number(expiresInDays) : null,
		});
		setLabel("");
		setExpiresInDays("");
		setCreateOpen(false);
	}, [createToken, expiresInDays, label]);

	const copyCreatedToken = useCallback(async () => {
		if (!createdToken) return;
		const success = await copyToClipboardUtil(createdToken.token);
		if (success) {
			setCopiedToken(true);
			setTimeout(() => setCopiedToken(false), 2000);
		}
	}, [createdToken]);

	const handleConfirmDelete = useCallback(async () => {
		if (!deleteTarget) return;

		await deleteToken(deleteTarget.id);
		setDeleteTarget(null);
	}, [deleteTarget, deleteToken]);

	return (
		<div className="space-y-6 min-w-0">
			<Alert>
				<Info />
				<AlertDescription>
					API keys let extensions, Obsidian, and other apps connect to SurfSense.
				</AlertDescription>
			</Alert>

			<div className="flex items-center justify-between gap-3">
				<div>
					<h3 className="text-sm font-semibold tracking-tight">API keys</h3>
					<p className="text-xs text-muted-foreground">
						Expired API keys stay listed until you delete them.
					</p>
				</div>
				<Button size="sm" onClick={() => setCreateOpen(true)}>
					Create API key
				</Button>
			</div>

			{isLoading ? (
				<div className="-m-1 grid grid-cols-1 gap-3 p-1">
					{["skeleton-a", "skeleton-b"].map((key) => (
						<Card
							key={key}
							className="group relative overflow-hidden transition-all duration-200 border-accent bg-accent/20 hover:shadow-md h-full"
						>
							<CardContent className="p-4 flex flex-col gap-3 h-full min-h-24">
								<Skeleton className="h-4 w-32 md:w-40 bg-accent" />
								<Skeleton className="h-3 w-full bg-accent" />
								<Skeleton className="h-3 w-24 md:w-28 bg-accent" />
							</CardContent>
						</Card>
					))}
				</div>
			) : sortedTokens.length > 0 ? (
				<div className="-m-1 grid grid-cols-1 gap-3 p-1">
					{sortedTokens.map((token) => {
						const expiresAt = token.expires_at ? new Date(token.expires_at) : null;
						const isExpired = expiresAt ? expiresAt.getTime() <= Date.now() : false;
						return (
							<Card
								key={token.id}
								className="group relative overflow-hidden transition-all duration-200 border-accent bg-accent/20 hover:shadow-md h-full"
							>
								<CardContent className="flex min-h-24 items-center gap-3 p-4">
									<div className="min-w-0 flex-1">
										<div className="flex flex-col gap-1">
											<div className="flex items-center gap-2">
												<h4 className="truncate text-sm font-semibold tracking-tight">
													{token.label}
												</h4>
												{isExpired ? (
													<span className="rounded-md border-0 bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
														Expired
													</span>
												) : null}
											</div>
											<p className="truncate font-mono text-xs text-muted-foreground">
												{token.prefix}...
											</p>
											<p className="text-xs text-muted-foreground">
												Expires: {expiresAt ? expiresAt.toLocaleDateString() : "Never"} · Last used:{" "}
												{token.last_used_at
													? new Date(token.last_used_at).toLocaleString()
													: "Never"}
											</p>
										</div>
									</div>
									<Button
										variant="ghost"
										size="icon"
										disabled={isMutating}
										onClick={() => setDeleteTarget({ id: token.id, label: token.label })}
										className="h-7 w-7 shrink-0 rounded-lg text-muted-foreground transition-opacity duration-150 hover:text-accent-foreground sm:opacity-0 sm:pointer-events-none sm:group-hover:opacity-100 sm:group-hover:pointer-events-auto"
									>
										<Trash2 className="h-4 w-4" />
									</Button>
								</CardContent>
							</Card>
						);
					})}
				</div>
			) : (
				<p className="py-6 text-center text-sm text-muted-foreground">No API keys yet.</p>
			)}

			<Dialog open={createOpen} onOpenChange={setCreateOpen}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Create API key</DialogTitle>
						<DialogDescription>
							Name this API key so you can recognize where it is used later.
						</DialogDescription>
					</DialogHeader>
					<div className="space-y-4">
						<div className="space-y-2">
							<Label htmlFor="pat-label">Name</Label>
							<Input
								id="pat-label"
								value={label}
								onChange={(event) => setLabel(event.target.value)}
								placeholder="Obsidian vault"
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="pat-expiry">Expires in days (optional)</Label>
							<Input
								id="pat-expiry"
								type="number"
								min={1}
								value={expiresInDays}
								onChange={(event) => setExpiresInDays(event.target.value)}
								placeholder="Never expires"
							/>
						</div>
					</div>
					<DialogFooter>
						<Button
							type="button"
							variant="secondary"
							size="sm"
							onClick={() => setCreateOpen(false)}
							disabled={isMutating}
							className="text-sm h-9"
						>
							Cancel
						</Button>
						<Button
							size="sm"
							disabled={isMutating || !label.trim()}
							onClick={handleCreate}
							className="relative text-sm h-9 min-w-[128px]"
						>
							<span className={isMutating ? "opacity-0" : ""}>Create API key</span>
							{isMutating && <Spinner size="sm" className="absolute" />}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			<Dialog open={!!createdToken} onOpenChange={(open) => !open && setCreatedToken(null)}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Copy your API key now</DialogTitle>
						<DialogDescription>
							This API key is shown only once. Store it somewhere secure before closing this dialog.
						</DialogDescription>
					</DialogHeader>
					<div className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/30 p-2">
						<code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap text-xs">
							{createdToken?.token}
						</code>
						<Button
							variant="outline"
							size="sm"
							onClick={copyCreatedToken}
							className="border-0 bg-muted/30 hover:bg-muted/50"
						>
							{copiedToken ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
						</Button>
					</div>
					<DialogFooter>
						<Button onClick={() => setCreatedToken(null)}>Done</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			<AlertDialog
				open={deleteTarget !== null}
				onOpenChange={(open) => !open && setDeleteTarget(null)}
			>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Delete API key?</AlertDialogTitle>
						<AlertDialogDescription>
							<span className="font-medium text-foreground">{deleteTarget?.label}</span> will be
							permanently removed. This cannot be undone.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={isMutating}>Cancel</AlertDialogCancel>
						<AlertDialogAction
							disabled={isMutating}
							className="bg-destructive text-white hover:bg-destructive/90"
							onClick={(event) => {
								event.preventDefault();
								void handleConfirmDelete();
							}}
						>
							{isMutating ? (
								<span className="inline-flex items-center gap-2">
									<Spinner size="xs" />
									Deleting...
								</span>
							) : (
								"Delete"
							)}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</div>
	);
}
