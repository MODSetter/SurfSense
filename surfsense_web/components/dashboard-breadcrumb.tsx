"use client";

import { usePathname } from "next/navigation";
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
	const pathname = usePathname();

	// Parse the pathname to create breadcrumb items
	const generateBreadcrumbs = (path: string): BreadcrumbItemInterface[] => {
		const segments = path.split("/").filter(Boolean);
		const breadcrumbs: BreadcrumbItemInterface[] = [];

		// Always start with Dashboard
		breadcrumbs.push({ label: "Dashboard", href: "/dashboard" });

		// Handle search space
		if (segments[0] === "dashboard" && segments[1]) {
			breadcrumbs.push({ label: `Search Space ${segments[1]}`, href: `/dashboard/${segments[1]}` });

			// Handle specific sections
			if (segments[2]) {
				const section = segments[2];
				let sectionLabel = section.charAt(0).toUpperCase() + section.slice(1);

				// Map section names to more readable labels
				const sectionLabels: Record<string, string> = {
					researcher: "Researcher",
					documents: "Documents",
					connectors: "Connectors",
					podcasts: "Podcasts",
					logs: "Logs",
					chats: "Chats",
				};

				sectionLabel = sectionLabels[section] || sectionLabel;

				// Handle sub-sections
				if (segments[3]) {
					const subSection = segments[3];
					let subSectionLabel = subSection.charAt(0).toUpperCase() + subSection.slice(1);

					// Handle documents sub-sections
					if (section === "documents") {
						const documentLabels: Record<string, string> = {
							upload: "Upload Documents",
							youtube: "Add YouTube Videos",
							webpage: "Add Webpages",
						};

						const documentLabel = documentLabels[subSection] || subSectionLabel;
						breadcrumbs.push({
							label: "Documents",
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
							add: "Add Connector",
							manage: "Manage Connectors",
						};

						const connectorLabel = connectorLabels[subSection] || subSectionLabel;
						breadcrumbs.push({
							label: "Connectors",
							href: `/dashboard/${segments[1]}/connectors`,
						});
						breadcrumbs.push({ label: connectorLabel });
						return breadcrumbs;
					}

					// Handle other sub-sections
					const subSectionLabels: Record<string, string> = {
						upload: "Upload Documents",
						youtube: "Add YouTube Videos",
						webpage: "Add Webpages",
						add: "Add Connector",
						edit: "Edit Connector",
						manage: "Manage",
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
