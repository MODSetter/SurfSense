"use client";

import { useTranslations } from "next-intl";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";

export default function DashboardLoading() {
	const t = useTranslations("common");

	// Use global loading - spinner animation won't reset when page transitions
	useGlobalLoadingEffect(true, t("loading"), "default");

	// Return null - the GlobalLoadingProvider handles the loading UI
	return null;
}
