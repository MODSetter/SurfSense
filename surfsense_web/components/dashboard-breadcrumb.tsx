"use client";

import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import React from "react";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

interface BreadcrumbItemInterface {
	label: string;
	href?: string;
}

export function DashboardBreadcrumb() {
	const t = useTranslations("breadcrumb");
	const pathname = usePathname();

	// Parse the pathname to create breadcrumb items
	const generateBreadcrumbs = (path: string): BreadcrumbItemInterface[] => {
		const segments = path.split("/").filter(Boolean);
		const breadcrumbs: BreadcrumbItemInterface[] = [];

		// Always start with Dashboard
		breadcrumbs.push({ label: t("dashboard"), href: "/dashboard" });

		// Handle search space
		if (segments[0] === "dashboard" && segments[1]) {
			breadcrumbs.push({
				label: `${t("search_space")} ${segments[1]}`,
				href: `/dashboard/${segments[1]}`,
			});

			// Handle specific sections
			if (segments[2]) {
				const section = segments[2];
				let sectionLabel = section.charAt(0).toUpperCase() + section.slice(1);

				// Map section names to more readable labels
				const sectionLabels: Record<string, string> = {
					researcher: t("researcher"),
					documents: t("documents"),
					connectors: t("connectors"),
					sources: "Sources",
					podcasts: t("podcasts"),
					logs: t("logs"),
					chats: t("chats"),
					settings: t("settings"),
				};

				sectionLabel = sectionLabels[section] || sectionLabel;

				// Handle sub-sections
				if (segments[3]) {
					const subSection = segments[3];
					let subSectionLabel = subSection.charAt(0).toUpperCase() + subSection.slice(1);

					// Handle sources sub-sections
					if (section === "sources") {
						const sourceLabels: Record<string, string> = {
							add: "Add Sources",
						};

						const sourceLabel = sourceLabels[subSection] || subSectionLabel;
						breadcrumbs.push({
							label: "Sources",
							href: `/dashboard/${segments[1]}/sources`,
						});
						breadcrumbs.push({ label: sourceLabel });
						return breadcrumbs;
					}

					// Handle documents sub-sections
					if (section === "documents") {
						const documentLabels: Record<string, string> = {
							upload: t("upload_documents"),
							youtube: t("add_youtube"),
							webpage: t("add_webpages"),
						};

						const documentLabel = documentLabels[subSection] || subSectionLabel;
						breadcrumbs.push({
							label: t("documents"),
							href: `/dashboard/${segments[1]}/documents`,
						});
						breadcrumbs.push({ label: documentLabel });
						return breadcrumbs;
					}

					// Handle connector sub-sections
					if (section === "connectors") {
						// Handle specific connector types
						if (subSection === "add" && segments[4]) {
							const connectorType = segments[4];
							const connectorLabels: Record<string, string> = {
								"github-connector": "GitHub",
								"jira-connector": "Jira",
								"confluence-connector": "Confluence",
								"discord-connector": "Discord",
								"linear-connector": "Linear",
								"clickup-connector": "ClickUp",
								"slack-connector": "Slack",
								"notion-connector": "Notion",
								"tavily-api": "Tavily API",
								"serper-api": "Serper API",
								"linkup-api": "LinkUp API",
								"luma-connector": "Luma",
								"elasticsearch-connector": "Elasticsearch",
							};

							const connectorLabel = connectorLabels[connectorType] || connectorType;
							breadcrumbs.push({
								label: "Connectors",
								href: `/dashboard/${segments[1]}/connectors`,
							});
							breadcrumbs.push({
								label: "Add Connector",
								href: `/dashboard/${segments[1]}/connectors/add`,
							});
							breadcrumbs.push({ label: connectorLabel });
							return breadcrumbs;
						}

						const connectorLabels: Record<string, string> = {
							add: t("add_connector"),
							manage: t("manage_connectors"),
						};

						const connectorLabel = connectorLabels[subSection] || subSectionLabel;
						breadcrumbs.push({
							label: t("connectors"),
							href: `/dashboard/${segments[1]}/connectors`,
						});
						breadcrumbs.push({ label: connectorLabel });
						return breadcrumbs;
					}

					// Handle other sub-sections
					const subSectionLabels: Record<string, string> = {
						upload: t("upload_documents"),
						youtube: t("add_youtube"),
						webpage: t("add_webpages"),
						add: t("add_connector"),
						edit: t("edit_connector"),
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

	if (breadcrumbs.length <= 1) {
		return null; // Don't show breadcrumbs for root dashboard
	}

	return (
		<Breadcrumb>
			<BreadcrumbList>
				{breadcrumbs.map((item, index) => (
					<React.Fragment key={index}>
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
