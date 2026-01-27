"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { Info, RotateCcw, Save } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { updateSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface GeneralSettingsManagerProps {
	searchSpaceId: number;
}

export function GeneralSettingsManager({ searchSpaceId }: GeneralSettingsManagerProps) {
	const t = useTranslations("searchSpaceSettings");
	const tCommon = useTranslations("common");
	const {
		data: searchSpace,
		isLoading: loading,
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
	const [hasChanges, setHasChanges] = useState(false);

	// Initialize state from fetched search space
	useEffect(() => {
		if (searchSpace) {
			setName(searchSpace.name || "");
			setDescription(searchSpace.description || "");
			setHasChanges(false);
		}
	}, [searchSpace]);

	// Track changes
	useEffect(() => {
		if (searchSpace) {
			const currentName = searchSpace.name || "";
			const currentDescription = searchSpace.description || "";
			const changed = currentName !== name || currentDescription !== description;
			setHasChanges(changed);
		}
	}, [searchSpace, name, description]);

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

			setHasChanges(false);
			await fetchSearchSpace();
		} catch (error: any) {
			console.error("Error saving search space details:", error);
			toast.error(error.message || "Failed to save search space details");
		} finally {
			setSaving(false);
		}
	};

	const handleReset = () => {
		if (searchSpace) {
			setName(searchSpace.name || "");
			setDescription(searchSpace.description || "");
			setHasChanges(false);
		}
	};

	if (loading) {
		return (
			<div className="space-y-4 md:space-y-6">
				<Card>
					<CardHeader className="px-3 md:px-6 pt-3 md:pt-6 pb-2 md:pb-3">
						<Skeleton className="h-5 md:h-6 w-36 md:w-48" />
						<Skeleton className="h-3 md:h-4 w-full max-w-md mt-2" />
					</CardHeader>
					<CardContent className="space-y-3 md:space-y-4 px-3 md:px-6 pb-3 md:pb-6">
						<Skeleton className="h-10 md:h-12 w-full" />
						<Skeleton className="h-10 md:h-12 w-full" />
					</CardContent>
				</Card>
			</div>
		);
	}

	return (
		<div className="space-y-4 md:space-y-6">
			<Alert className="py-3 md:py-4">
				<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
				<AlertDescription className="text-xs md:text-sm">
					Update your search space name and description. These details help identify and organize
					your workspace.
				</AlertDescription>
			</Alert>

			{/* Search Space Details Card */}
			<Card>
				<CardHeader className="px-3 md:px-6 pt-3 md:pt-6 pb-2 md:pb-3">
					<CardTitle className="text-base md:text-lg">Search Space Details</CardTitle>
					<CardDescription className="text-xs md:text-sm">
						Manage the basic information for this search space.
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-4 md:space-y-5 px-3 md:px-6 pb-3 md:pb-6">
					<div className="space-y-1.5 md:space-y-2">
						<Label htmlFor="search-space-name" className="text-sm md:text-base font-medium">
							{t("general_name_label")}
						</Label>
						<Input
							id="search-space-name"
							placeholder={t("general_name_placeholder")}
							value={name}
							onChange={(e) => setName(e.target.value)}
							className="text-sm md:text-base h-9 md:h-10"
						/>
						<p className="text-[10px] md:text-xs text-muted-foreground">
							{t("general_name_description")}
						</p>
					</div>

					<div className="space-y-1.5 md:space-y-2">
						<Label htmlFor="search-space-description" className="text-sm md:text-base font-medium">
							{t("general_description_label")}{" "}
							<span className="text-muted-foreground font-normal">({tCommon("optional")})</span>
						</Label>
						<Input
							id="search-space-description"
							placeholder={t("general_description_placeholder")}
							value={description}
							onChange={(e) => setDescription(e.target.value)}
							className="text-sm md:text-base h-9 md:h-10"
						/>
						<p className="text-[10px] md:text-xs text-muted-foreground">
							{t("general_description_description")}
						</p>
					</div>
				</CardContent>
			</Card>

			{/* Action Buttons */}
			<div className="flex items-center justify-between pt-3 md:pt-4 gap-2">
				<Button
					variant="outline"
					onClick={handleReset}
					disabled={!hasChanges || saving}
					className="flex items-center gap-2 text-xs md:text-sm h-9 md:h-10"
				>
					<RotateCcw className="h-3.5 w-3.5 md:h-4 md:w-4" />
					{t("general_reset")}
				</Button>
				<Button
					onClick={handleSave}
					disabled={!hasChanges || saving || !name.trim()}
					className="flex items-center gap-2 text-xs md:text-sm h-9 md:h-10"
				>
					<Save className="h-3.5 w-3.5 md:h-4 md:w-4" />
					{saving ? t("general_saving") : t("general_save")}
				</Button>
			</div>

			{hasChanges && (
				<Alert
					variant="default"
					className="bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800 py-3 md:py-4"
				>
					<Info className="h-3 w-3 md:h-4 md:w-4 text-blue-600 dark:text-blue-500 shrink-0" />
					<AlertDescription className="text-blue-800 dark:text-blue-300 text-xs md:text-sm">
						{t("general_unsaved_changes")}
					</AlertDescription>
				</Alert>
			)}
		</div>
	);
}
