"use client";

import { useTranslations } from "next-intl";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";

export default function AuthCallbackLoading() {
	const t = useTranslations("auth");

	// Use global loading - spinner animation won't reset when page transitions
	useGlobalLoadingEffect(true, t("processing_authentication"), "default");

	// Return null - the GlobalLoadingProvider handles the loading UI
	return null;
}
