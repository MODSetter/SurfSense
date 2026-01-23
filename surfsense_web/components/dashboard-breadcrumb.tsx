"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import React, { useEffect, useState } from "react";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { authenticatedFetch, getBearerToken } from "@/lib/auth-utils";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface BreadcrumbItemInterface {
	label: string;
	href?: string;
}

export function DashboardBreadcrumb() {
	const t = useTranslations("breadcrumb");
	const pathname = usePathname();
	// Extract search space ID and chat ID from pathname
	const segments = pathname.split("/").filter(Boolean);
	const searchSpaceId = segments[0] === "dashboard" && segments[1] ? segments[1] : null;

	const { data: searchSpace } = useQuery({
		queryKey: cacheKeys.searchSpaces.detail(searchSpaceId || ""),
		queryFn: () => searchSpacesApiService.getSearchSpace({ id: Number(searchSpaceId) }),
		enabled: !!searchSpaceId,
	});

	// State to store document title for editor breadcrumb
	const [documentTitle, setDocumentTitle] = useState<string | null>(null);

	// Fetch document title when on editor page
	useEffect(() => {
		if (segments[2] === "editor" && segments[3] && searchSpaceId) {
			const documentId = segments[3];

			// Skip fetch for "new" notes
			if (documentId === "new") {
				setDocumentTitle(null);
				return;
			}

			const token = getBearerToken();

			if (token) {
				authenticatedFetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/documents/${documentId}/editor-content`,
					{ method: "GET" }
				)
					.then((res) => res.json())
					.then((data) => {
						if (data.title) {
							setDocumentTitle(data.title);
						}
					})
					.catch(() => {
						// If fetch fails, just use the document ID
						setDocumentTitle(null);
					});
			}
		} else {
			setDocumentTitle(null);
		}
	}, [segments, searchSpaceId]);

	// Parse the pathname to create breadcrumb items
	const generateBreadcrumbs = (path: string): BreadcrumbItemInterface[] => {
		const segments = path.split("/").filter(Boolean);
		const breadcrumbs: BreadcrumbItemInterface[] = [];

		// Handle search space (start directly with search space, skip "Dashboard")
		if (segments[0] === "dashboard" && segments[1]) {
			// Use the actual search space name if available, otherwise fall back to the ID
			const searchSpaceLabel = searchSpace?.name || `${t("search_space")} ${segments[1]}`;
			breadcrumbs.push({
				label: searchSpaceLabel,
				href: `/dashboard/${segments[1]}`,
			});

			// Handle specific sections
			if (segments[2]) {
				const section = segments[2];
				let sectionLabel = section.charAt(0).toUpperCase() + section.slice(1);

				// Map section names to more readable labels
				const sectionLabels: Record<string, string> = {
					"new-chat": t("chat") || "Chat",
					documents: t("documents"),
					logs: t("logs"),
					settings: t("settings"),
					editor: t("editor"),
				};

				sectionLabel = sectionLabels[section] || sectionLabel;

				// Handle sub-sections
				if (segments[3]) {
					const subSection = segments[3];

					// Handle editor sub-sections (document ID)
					if (section === "editor") {
						// Handle special cases for editor
						let documentLabel: string;
						if (subSection === "new") {
							documentLabel = "New Note";
						} else {
							documentLabel = documentTitle || subSection;
						}

						breadcrumbs.push({
							label: t("documents"),
							href: `/dashboard/${segments[1]}/documents`,
						});
						breadcrumbs.push({
							label: sectionLabel,
							href: `/dashboard/${segments[1]}/documents`,
						});
						breadcrumbs.push({ label: documentLabel });
						return breadcrumbs;
					}

					// Handle documents sub-sections
					if (section === "documents") {
						const documentLabels: Record<string, string> = {
							upload: t("upload_documents"),
							webpage: t("add_webpages"),
						};

						const documentLabel = documentLabels[subSection] || subSection;
						breadcrumbs.push({
							label: t("documents"),
							href: `/dashboard/${segments[1]}/documents`,
						});
						breadcrumbs.push({ label: documentLabel });
						return breadcrumbs;
					}

					// Handle new-chat sub-sections (thread IDs)
					// Don't show thread ID in breadcrumb - users identify chats by content, not by ID
					if (section === "new-chat") {
						breadcrumbs.push({
							label: t("chat") || "Chat",
						});
						return breadcrumbs;
					}

					// Handle other sub-sections
					let subSectionLabel = subSection.charAt(0).toUpperCase() + subSection.slice(1);
					const subSectionLabels: Record<string, string> = {
						upload: t("upload_documents"),
						youtube: t("add_youtube"),
						webpage: t("add_webpages"),
						manage: t("manage"),
					};

					subSectionLabel = subSectionLabels[subSection] || subSectionLabel;

					breadcrumbs.push({
						label: sectionLabel,
						href: `/dashboard/${segments[1]}/${section}`,
					});
					breadcrumbs.push({ label: subSectionLabel });
				} else {
					breadcrumbs.push({ label: sectionLabel });
				}
			}
		}

		return breadcrumbs;
	};

	const breadcrumbs = generateBreadcrumbs(pathname);

	if (breadcrumbs.length === 0) {
		return null; // Don't show breadcrumbs for root dashboard
	}

	return (
		<Breadcrumb>
			<BreadcrumbList>
				{breadcrumbs.map((item, index) => (
					<React.Fragment key={`${index}-${item.href || item.label}`}>
						<BreadcrumbItem>
							{index === breadcrumbs.length - 1 ? (
								<BreadcrumbPage>{item.label}</BreadcrumbPage>
							) : (
								<BreadcrumbLink href={item.href}>{item.label}</BreadcrumbLink>
							)}
						</BreadcrumbItem>
						{index < breadcrumbs.length - 1 && <BreadcrumbSeparator />}
					</React.Fragment>
				))}
			</BreadcrumbList>
		</Breadcrumb>
	);
}
