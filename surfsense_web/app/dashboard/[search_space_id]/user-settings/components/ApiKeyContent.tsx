"use client";

import { Check, Copy, Info, Plus, Trash2 } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
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
import { Skeleton } from "@/components/ui/skeleton";
import { usePats } from "@/hooks/use-pats";
import { copyToClipboard as copyToClipboardUtil } from "@/lib/utils";

export function ApiKeyContent() {
	const { tokens, createdToken, setCreatedToken, isLoading, isMutating, createToken, deleteToken } =
		usePats();
	const [createOpen, setCreateOpen] = useState(false);
	const [label, setLabel] = useState("");
	const [expiresInDays, setExpiresInDays] = useState("");
	const [copiedToken, setCopiedToken] = useState(false);

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

	const handleDelete = useCallback(
		async (id: number, tokenLabel: string) => {
			if (!window.confirm(`Delete personal access token "${tokenLabel}"? This cannot be undone.`)) {
				return;
			}
			await deleteToken(id);
		},
		[deleteToken]
	);

	return (
		<div className="space-y-6 min-w-0 overflow-hidden">
			<Alert>
				<Info />
				<AlertDescription>
					Personal access tokens are long-lived credentials for extensions, Obsidian, and
					programmatic API clients. Copy a token when you create it; it is shown only once.
				</AlertDescription>
			</Alert>

			<div className="flex items-center justify-between gap-3">
				<div>
					<h3 className="text-sm font-semibold tracking-tight">Personal access tokens</h3>
					<p className="text-xs text-muted-foreground">
						Expired tokens stay listed until you delete them.
					</p>
				</div>
				<Button size="sm" onClick={() => setCreateOpen(true)}>
					<Plus className="mr-2 h-4 w-4" />
					Create token
				</Button>
			</div>

			<div className="min-w-0 overflow-hidden rounded-lg border border-border/60">
				{isLoading ? (
					<div className="space-y-3 p-4">
						<Skeleton className="h-12 w-full" />
						<Skeleton className="h-12 w-full" />
					</div>
				) : sortedTokens.length > 0 ? (
					<div className="divide-y divide-border/60">
						{sortedTokens.map((token) => {
							const expiresAt = token.expires_at ? new Date(token.expires_at) : null;
							const isExpired = expiresAt ? expiresAt.getTime() <= Date.now() : false;
							return (
								<div key={token.id} className="flex items-center gap-3 p-4">
									<div className="min-w-0 flex-1">
										<div className="flex items-center gap-2">
											<p className="truncate text-sm font-medium">{token.label}</p>
											{isExpired ? <Badge variant="secondary">Expired</Badge> : null}
										</div>
										<p className="font-mono text-xs text-muted-foreground">{token.prefix}...</p>
										<p className="text-xs text-muted-foreground">
											Expires: {expiresAt ? expiresAt.toLocaleDateString() : "Never"} · Last used:{" "}
											{token.last_used_at
												? new Date(token.last_used_at).toLocaleString()
												: "Never"}
										</p>
									</div>
									<Button
										variant="ghost"
										size="icon"
										disabled={isMutating}
										onClick={() => handleDelete(token.id, token.label)}
									>
										<Trash2 className="h-4 w-4 text-muted-foreground" />
									</Button>
								</div>
							);
						})}
					</div>
				) : (
					<p className="p-6 text-center text-sm text-muted-foreground">
						No personal access tokens yet.
					</p>
				)}
			</div>

			<Dialog open={createOpen} onOpenChange={setCreateOpen}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Create personal access token</DialogTitle>
						<DialogDescription>
							Name this token so you can recognize where it is used later.
						</DialogDescription>
					</DialogHeader>
					<div className="space-y-4">
						<div className="space-y-2">
							<Label htmlFor="pat-label">Label</Label>
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
						<Button variant="outline" onClick={() => setCreateOpen(false)}>
							Cancel
						</Button>
						<Button disabled={isMutating || !label.trim()} onClick={handleCreate}>
							Create token
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			<Dialog open={!!createdToken} onOpenChange={(open) => !open && setCreatedToken(null)}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Copy your token now</DialogTitle>
						<DialogDescription>
							This token is shown only once. Store it somewhere secure before closing this
							dialog.
						</DialogDescription>
					</DialogHeader>
					<div className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/30 p-2">
						<code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap text-xs">
							{createdToken?.token}
						</code>
						<Button variant="outline" size="sm" onClick={copyCreatedToken}>
							{copiedToken ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
						</Button>
					</div>
					<DialogFooter>
						<Button onClick={() => setCreatedToken(null)}>Done</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}
