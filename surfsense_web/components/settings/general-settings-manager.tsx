"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { updateSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { Spinner } from "../ui/spinner";
import { BACKEND_URL } from "@/lib/env-config";

interface GeneralSettingsManagerProps {
	searchSpaceId: number;
}

export function GeneralSettingsManager({ searchSpaceId }: GeneralSettingsManagerProps) {
	const t = useTranslations("searchSpaceSettings");
	const tCommon = useTranslations("common");
	const {
		data: searchSpace,
		isLoading: loading,
		isError,
		refetch: fetchSearchSpace,
	} = useQuery({
		queryKey: cacheKeys.searchSpaces.detail(searchSpaceId.toString()),
		queryFn: () => searchSpacesApiService.getSearchSpace({ id: searchSpaceId }),
		enabled: !!searchSpaceId,
	});

	const { mutateAsync: updateSearchSpace } = useAtomValue(updateSearchSpaceMutationAtom);

	const [name, setName] = useState("");
	const [description, setDescription] = useState("");
	const [saving, setSaving] = useState(false);
	const [isExporting, setIsExporting] = useState(false);
	const hasSearchSpace = !!searchSpace;
	const searchSpaceName = searchSpace?.name;
	const searchSpaceDescription = searchSpace?.description;

	const handleExportKB = useCallback(async () => {
		if (isExporting) return;
		setIsExporting(true);
		try {
			const response = await authenticatedFetch(
				`${BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/export`,
				{ method: "GET" }
			);
			if (!response.ok) {
				const errorData = await response.json().catch(() => ({ detail: "Export failed" }));
				throw new Error(errorData.detail || "Export failed");
			}
			const blob = await response.blob();
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = "knowledge-base.zip";
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
			toast.success("Knowledge base exported");
		} catch (err) {
			console.error("KB export failed:", err);
			toast.error(err instanceof Error ? err.message : "Export failed");
		} finally {
			setIsExporting(false);
		}
	}, [searchSpaceId, isExporting]);

	// Initialize state from fetched search space
	useEffect(() => {
		if (hasSearchSpace) {
			setName(searchSpaceName || "");
			setDescription(searchSpaceDescription || "");
		}
	}, [hasSearchSpace, searchSpaceName, searchSpaceDescription]);

	// Derive hasChanges during render
	const hasChanges =
		!!searchSpace &&
		((searchSpace.name || "") !== name || (searchSpace.description || "") !== description);

	const handleSave = async () => {
		try {
			setSaving(true);

			await updateSearchSpace({
				id: searchSpaceId,
				data: {
					name: name.trim(),
					description: description.trim() || undefined,
				},
			});

			await fetchSearchSpace();
		} catch (error: unknown) {
			console.error("Error saving search space details:", error);
			toast.error(error instanceof Error ? error.message : "Failed to save search space details");
		} finally {
			setSaving(false);
		}
	};

	const onSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		handleSave();
	};

	if (loading) {
		return (
			<div className="space-y-4 md:space-y-6">
				<div className="flex flex-col gap-6">
					<Skeleton className="h-10 md:h-12 w-full" />
					<Skeleton className="h-10 md:h-12 w-full" />
				</div>
			</div>
		);
	}

	if (isError) {
		return (
			<div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
				<p className="text-sm text-destructive">Failed to load settings.</p>
				<Button variant="outline" size="sm" onClick={() => fetchSearchSpace()}>
					Retry
				</Button>
			</div>
		);
	}

	return (
		<div className="space-y-4 md:space-y-6">
			<form onSubmit={onSubmit} className="space-y-6">
				<div className="flex flex-col gap-6">
					<div className="space-y-2">
						<Label htmlFor="search-space-name">{t("general_name_label")}</Label>
						<Input
							id="search-space-name"
							maxLength={100}
							placeholder={t("general_name_placeholder")}
							value={name}
							onChange={(e) => setName(e.target.value)}
						/>
						<p className="text-xs text-muted-foreground">{t("general_name_description")}</p>
					</div>

					<div className="space-y-2">
						<Label htmlFor="search-space-description">
							{t("general_description_label")}{" "}
							<span className="text-muted-foreground font-normal">({tCommon("optional")})</span>
						</Label>
						<Input
							id="search-space-description"
							placeholder={t("general_description_placeholder")}
							value={description}
							onChange={(e) => setDescription(e.target.value)}
						/>
						<p className="text-xs text-muted-foreground">{t("general_description_description")}</p>
					</div>
				</div>

				<div className="flex justify-end">
					<Button
						type="submit"
						variant="outline"
						disabled={!hasChanges || saving || !name.trim()}
						className="relative gap-2 bg-white text-black hover:bg-accent hover:text-accent-foreground dark:bg-white dark:text-black"
					>
						<span className={saving ? "opacity-0" : ""}>{t("general_save")}</span>
						{saving && <Spinner size="sm" className="absolute" />}
					</Button>
				</div>
			</form>

			<div className="border-t pt-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
				<div className="space-y-1">
					<Label>Export knowledge base</Label>
					<p className="text-xs text-muted-foreground">
						Download all documents in this search space as a ZIP of markdown files.
					</p>
				</div>
				<Button
					type="button"
					variant="secondary"
					size="sm"
					disabled={isExporting}
					onClick={handleExportKB}
					className="relative w-fit shrink-0"
				>
					<span className={isExporting ? "opacity-0" : ""}>Export</span>
					{isExporting && <Spinner size="sm" className="absolute" />}
				</Button>
			</div>
		</div>
	);
}
