"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { Globe, Loader2, Save } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { updateSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { baseApiService } from "@/lib/apis/base-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface WebSearchSettingsManagerProps {
	searchSpaceId: number;
}

interface HealthStatus {
	status: string;
	response_time_ms?: number;
	error?: string;
	circuit_breaker?: string;
}

export function WebSearchSettingsManager({ searchSpaceId }: WebSearchSettingsManagerProps) {
	const t = useTranslations("searchSpaceSettings");
	const {
		data: searchSpace,
		isLoading,
		refetch,
	} = useQuery({
		queryKey: cacheKeys.searchSpaces.detail(searchSpaceId.toString()),
		queryFn: () => searchSpacesApiService.getSearchSpace({ id: searchSpaceId }),
		enabled: !!searchSpaceId,
	});

	const { data: healthData } = useQuery<HealthStatus>({
		queryKey: ["web-search-health"],
		queryFn: async () => {
			const response = await baseApiService.get("/api/v1/platform/web-search/health");
			return response as HealthStatus;
		},
		refetchInterval: 30000,
		staleTime: 10000,
	});

	const { mutateAsync: updateSearchSpace } = useAtomValue(updateSearchSpaceMutationAtom);

	const [enabled, setEnabled] = useState(true);
	const [engines, setEngines] = useState("");
	const [language, setLanguage] = useState("");
	const [safesearch, setSafesearch] = useState<string>("");
	const [saving, setSaving] = useState(false);

	useEffect(() => {
		if (searchSpace) {
			setEnabled(searchSpace.web_search_enabled ?? true);
			const cfg = searchSpace.web_search_config as Record<string, unknown> | null;
			setEngines((cfg?.engines as string) ?? "");
			setLanguage((cfg?.language as string) ?? "");
			const ss = cfg?.safesearch;
			setSafesearch(ss !== null && ss !== undefined ? String(ss) : "");
		}
	}, [searchSpace]);

	const handleSave = useCallback(async () => {
		try {
			setSaving(true);

			const webSearchConfig: Record<string, unknown> = {};
			if (engines.trim()) webSearchConfig.engines = engines.trim();
			if (language.trim()) webSearchConfig.language = language.trim();
			if (safesearch !== "") webSearchConfig.safesearch = Number(safesearch);

			await updateSearchSpace({
				id: searchSpaceId,
				data: {
					web_search_enabled: enabled,
					web_search_config: Object.keys(webSearchConfig).length > 0 ? webSearchConfig : null,
				},
			});

			toast.success(t("web_search_saved"));
			await refetch();
		} catch (error: unknown) {
			console.error("Error saving web search settings:", error);
			const message = error instanceof Error ? error.message : "Failed to save web search settings";
			toast.error(message);
		} finally {
			setSaving(false);
		}
	}, [searchSpaceId, enabled, engines, language, safesearch, updateSearchSpace, refetch, t]);

	if (isLoading) {
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

	const isHealthy = healthData?.status === "healthy";
	const isUnavailable = healthData?.status === "unavailable";

	return (
		<div className="space-y-4 md:space-y-6">
			<Alert className="bg-muted/50 py-3 md:py-4">
				<Globe className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
				<AlertDescription className="text-xs md:text-sm">
					{t("web_search_description")}
				</AlertDescription>
			</Alert>

			{healthData && (
				<div className="flex items-center gap-2 text-xs md:text-sm">
					<span
						className={`inline-block h-2 w-2 rounded-full ${
							isHealthy
								? "bg-green-500"
								: isUnavailable
									? "bg-gray-400"
									: "bg-red-500"
						}`}
					/>
					<span className="text-muted-foreground">
						{isHealthy
							? `${t("web_search_status_healthy")} (${healthData.response_time_ms}ms)`
							: isUnavailable
								? t("web_search_status_not_configured")
								: t("web_search_status_unhealthy")}
					</span>
				</div>
			)}

			<Card>
				<CardHeader className="px-3 md:px-6 pt-3 md:pt-6 pb-2 md:pb-3">
					<CardTitle className="text-base md:text-lg">{t("web_search_title")}</CardTitle>
					<CardDescription className="text-xs md:text-sm">
						{t("web_search_enabled_description")}
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-5 md:space-y-6 px-3 md:px-6 pb-3 md:pb-6">
					<div className="flex items-center justify-between rounded-lg border p-3 md:p-4">
						<div className="space-y-0.5">
							<Label className="text-sm md:text-base font-medium">
								{t("web_search_enabled_label")}
							</Label>
							<p className="text-[10px] md:text-xs text-muted-foreground">
								{t("web_search_enabled_description")}
							</p>
						</div>
						<Switch checked={enabled} onCheckedChange={setEnabled} />
					</div>

					{enabled && (
						<div className="space-y-4 md:space-y-5">
							<div className="space-y-1.5 md:space-y-2">
								<Label className="text-sm md:text-base font-medium">
									{t("web_search_engines_label")}
								</Label>
								<Input
									placeholder={t("web_search_engines_placeholder")}
									value={engines}
									onChange={(e) => setEngines(e.target.value)}
									className="text-sm md:text-base h-9 md:h-10"
								/>
								<p className="text-[10px] md:text-xs text-muted-foreground">
									{t("web_search_engines_description")}
								</p>
							</div>

							<div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
								<div className="space-y-1.5 md:space-y-2">
									<Label className="text-sm md:text-base font-medium">
										{t("web_search_language_label")}
									</Label>
									<Input
										placeholder={t("web_search_language_placeholder")}
										value={language}
										onChange={(e) => setLanguage(e.target.value)}
										className="text-sm md:text-base h-9 md:h-10"
									/>
									<p className="text-[10px] md:text-xs text-muted-foreground">
										{t("web_search_language_description")}
									</p>
								</div>

								<div className="space-y-1.5 md:space-y-2">
									<Label className="text-sm md:text-base font-medium">
										{t("web_search_safesearch_label")}
									</Label>
									<Select value={safesearch} onValueChange={setSafesearch}>
										<SelectTrigger className="h-9 md:h-10 text-sm md:text-base">
											<SelectValue placeholder="Default" />
										</SelectTrigger>
										<SelectContent>
											<SelectItem value="">Default</SelectItem>
											<SelectItem value="0">Off (0)</SelectItem>
											<SelectItem value="1">Moderate (1)</SelectItem>
											<SelectItem value="2">Strict (2)</SelectItem>
										</SelectContent>
									</Select>
									<p className="text-[10px] md:text-xs text-muted-foreground">
										{t("web_search_safesearch_description")}
									</p>
								</div>
							</div>
						</div>
					)}
				</CardContent>
			</Card>

			<div className="flex justify-end pt-3 md:pt-4">
				<Button
					onClick={handleSave}
					disabled={saving}
					className="flex items-center gap-2 text-xs md:text-sm h-9 md:h-10"
				>
					{saving ? (
						<Loader2 className="h-3.5 w-3.5 md:h-4 md:w-4 animate-spin" />
					) : (
						<Save className="h-3.5 w-3.5 md:h-4 md:w-4" />
					)}
					{saving ? t("web_search_saving") : t("web_search_save")}
				</Button>
			</div>
		</div>
	);
}
