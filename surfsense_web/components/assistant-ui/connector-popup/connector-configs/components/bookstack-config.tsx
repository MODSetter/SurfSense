"use client";

import { KeyRound, Loader2, RefreshCw, X } from "lucide-react";
import type { FC } from "react";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import type { ConnectorConfigProps } from "../index";

export interface BookStackConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

interface BookStackShelf {
	id: number;
	name: string;
	book_count: number;
	books: { id: number; name: string }[];
}

export const BookStackConfig: FC<BookStackConfigProps> = ({
	connector,
	onConfigChange,
	onNameChange,
}) => {
	const [baseUrl, setBaseUrl] = useState<string>(
		(connector.config?.BOOKSTACK_BASE_URL as string) || ""
	);
	const [tokenId, setTokenId] = useState<string>(
		(connector.config?.BOOKSTACK_TOKEN_ID as string) || ""
	);
	const [tokenSecret, setTokenSecret] = useState<string>(
		(connector.config?.BOOKSTACK_TOKEN_SECRET as string) || ""
	);
	const [name, setName] = useState<string>(connector.name || "");
	const [shelves, setShelves] = useState<BookStackShelf[]>([]);
	const [excludedShelfIds, setExcludedShelfIds] = useState<number[]>(
		(connector.config?.BOOKSTACK_EXCLUDED_SHELF_IDS as number[]) || []
	);
	const [loadingShelves, setLoadingShelves] = useState(false);
	const [shelvesError, setShelvesError] = useState<string | null>(null);
	const [shelvesLoaded, setShelvesLoaded] = useState(false);

	// Update values when connector changes
	useEffect(() => {
		const url = (connector.config?.BOOKSTACK_BASE_URL as string) || "";
		const id = (connector.config?.BOOKSTACK_TOKEN_ID as string) || "";
		const secret = (connector.config?.BOOKSTACK_TOKEN_SECRET as string) || "";
		const excluded = (connector.config?.BOOKSTACK_EXCLUDED_SHELF_IDS as number[]) || [];
		setBaseUrl(url);
		setTokenId(id);
		setTokenSecret(secret);
		setExcludedShelfIds(excluded);
		setName(connector.name || "");
	}, [connector.config, connector.name]);

	const fetchShelves = useCallback(async () => {
		if (!baseUrl || !tokenId || !tokenSecret) {
			setShelvesError("Please fill in Base URL, Token ID, and Token Secret first.");
			return;
		}

		setLoadingShelves(true);
		setShelvesError(null);

		try {
			const data = await connectorsApiService.listBookStackShelves(
				baseUrl,
				tokenId,
				tokenSecret,
			) as BookStackShelf[];
			setShelves(data);
			setShelvesLoaded(true);
		} catch (err) {
			setShelvesError(err instanceof Error ? err.message : "Failed to fetch shelves");
			setShelves([]);
			setShelvesLoaded(false);
		} finally {
			setLoadingShelves(false);
		}
	}, [baseUrl, tokenId, tokenSecret]);

	const toggleShelfExclusion = (shelfId: number) => {
		const newExcluded = excludedShelfIds.includes(shelfId)
			? excludedShelfIds.filter((id) => id !== shelfId)
			: [...excludedShelfIds, shelfId];
		setExcludedShelfIds(newExcluded);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				BOOKSTACK_EXCLUDED_SHELF_IDS: newExcluded,
			});
		}
	};

	const handleBaseUrlChange = (value: string) => {
		setBaseUrl(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				BOOKSTACK_BASE_URL: value,
			});
		}
	};

	const handleTokenIdChange = (value: string) => {
		setTokenId(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				BOOKSTACK_TOKEN_ID: value,
			});
		}
	};

	const handleTokenSecretChange = (value: string) => {
		setTokenSecret(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				BOOKSTACK_TOKEN_SECRET: value,
			});
		}
	};

	const handleNameChange = (value: string) => {
		setName(value);
		if (onNameChange) {
			onNameChange(value);
		}
	};

	return (
		<div className="space-y-6">
			{/* Connector Name */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-2">
					<Label className="text-xs sm:text-sm">Connector Name</Label>
					<Input
						value={name}
						onChange={(e) => handleNameChange(e.target.value)}
						placeholder="My BookStack Connector"
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						A friendly name to identify this connector.
					</p>
				</div>
			</div>

			{/* Configuration */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base">Configuration</h3>
				</div>

				<div className="space-y-4">
					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">BookStack Base URL</Label>
						<Input
							type="url"
							value={baseUrl}
							onChange={(e) => handleBaseUrlChange(e.target.value)}
							placeholder="https://your-bookstack-instance.com"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							The base URL of your BookStack instance.
						</p>
					</div>

					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">Token ID</Label>
						<Input
							value={tokenId}
							onChange={(e) => handleTokenIdChange(e.target.value)}
							placeholder="Your Token ID"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Your BookStack API Token ID.
						</p>
					</div>

					<div className="space-y-2">
						<Label className="flex items-center gap-2 text-xs sm:text-sm">
							<KeyRound className="h-4 w-4" />
							Token Secret
						</Label>
						<Input
							type="password"
							value={tokenSecret}
							onChange={(e) => handleTokenSecretChange(e.target.value)}
							placeholder="Your Token Secret"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Update your BookStack Token Secret if needed.
						</p>
					</div>
				</div>
			</div>

			{/* Shelf Exclusion Picker */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="flex items-center justify-between">
					<div className="space-y-1 sm:space-y-2">
						<h3 className="font-medium text-sm sm:text-base">Shelf Filter</h3>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Select which shelves to include in indexing. Unchecked shelves will be excluded.
						</p>
					</div>
					<Button
						type="button"
						variant="outline"
						size="sm"
						onClick={fetchShelves}
						disabled={loadingShelves}
						className="text-xs"
					>
						{loadingShelves ? (
							<Loader2 className="h-3 w-3 animate-spin mr-1" />
						) : (
							<RefreshCw className="h-3 w-3 mr-1" />
						)}
						{shelvesLoaded ? "Refresh" : "Load Shelves"}
					</Button>
				</div>

				{shelvesError && (
					<p className="text-xs text-destructive">{shelvesError}</p>
				)}

				{shelvesLoaded && shelves.length > 0 && (
					<div className="rounded-lg border border-slate-400/20 divide-y divide-slate-400/10">
						{shelves.map((shelf) => {
							const isExcluded = excludedShelfIds.includes(shelf.id);
							return (
								<label
									key={shelf.id}
									className={`flex items-center gap-3 p-2.5 sm:p-3 cursor-pointer hover:bg-slate-400/5 transition-colors ${
										isExcluded ? "opacity-50" : ""
									}`}
								>
									<Checkbox
										checked={!isExcluded}
										onCheckedChange={() => toggleShelfExclusion(shelf.id)}
									/>
									<div className="flex-1 min-w-0">
										<div className="text-xs sm:text-sm font-medium truncate">
											{shelf.name}
										</div>
										<div className="text-[10px] sm:text-xs text-muted-foreground">
											{shelf.book_count} {shelf.book_count === 1 ? "book" : "books"}
										</div>
									</div>
									{isExcluded && (
										<Badge variant="secondary" className="text-[10px] shrink-0">
											Excluded
										</Badge>
									)}
								</label>
							);
						})}
					</div>
				)}

				{!shelvesLoaded && excludedShelfIds.length > 0 && (
					<div className="flex flex-wrap gap-1.5">
						<span className="text-[10px] sm:text-xs text-muted-foreground">Currently excluding shelf IDs:</span>
						{excludedShelfIds.map((id) => (
							<Badge key={id} variant="secondary" className="text-[10px]">
								{id}
							</Badge>
						))}
						<p className="text-[10px] sm:text-xs text-muted-foreground w-full mt-1">
							Click &quot;Load Shelves&quot; to see shelf names and modify exclusions.
						</p>
					</div>
				)}

				{excludedShelfIds.length > 0 && shelvesLoaded && (
					<div className="flex flex-wrap gap-1.5 mt-2">
						<span className="text-[10px] sm:text-xs text-muted-foreground">Excluding:</span>
						{excludedShelfIds.map((id) => {
							const shelf = shelves.find((s) => s.id === id);
							return (
								<Badge
									key={id}
									variant="destructive"
									className="text-[10px] cursor-pointer hover:bg-destructive/80"
									onClick={() => toggleShelfExclusion(id)}
								>
									{shelf?.name || `ID ${id}`}
									<X className="h-2.5 w-2.5 ml-1" />
								</Badge>
							);
						})}
					</div>
				)}
			</div>
		</div>
	);
};
