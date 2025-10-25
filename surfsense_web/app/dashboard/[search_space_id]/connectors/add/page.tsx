"use client";

import {
	IconBrandWindows,
	IconBrandZoom,
	IconChevronDown,
	IconChevronRight,
} from "@tabler/icons-react";
import { AnimatePresence, motion, type Variants } from "motion/react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";

// Define the Connector type
interface Connector {
	id: string;
	title: string;
	description: string;
	icon: React.ReactNode;
	status: "available" | "coming-soon" | "connected";
}

interface ConnectorCategory {
	id: string;
	title: string;
	connectors: Connector[];
}

// Define connector categories and their connectors
const connectorCategories: ConnectorCategory[] = [
	{
		id: "search-engines",
		title: "search_engines",
		connectors: [
			{
				id: "tavily-api",
				title: "Tavily API",
				description: "tavily_desc",
				icon: getConnectorIcon(EnumConnectorName.TAVILY_API, "h-6 w-6"),
				status: "available",
			},
			{
				id: "searxng",
				title: "SearxNG",
				description: "searxng_desc",
				icon: getConnectorIcon(EnumConnectorName.SEARXNG_API, "h-6 w-6"),
				status: "available",
			},
			{
				id: "linkup-api",
				title: "Linkup API",
				description: "linkup_desc",
				icon: getConnectorIcon(EnumConnectorName.LINKUP_API, "h-6 w-6"),
				status: "available",
			},
			{
				id: "elasticsearch-connector",
				title: "Elasticsearch",
				description: "elasticsearch_desc",
				icon: getConnectorIcon(EnumConnectorName.ELASTICSEARCH_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "baidu-search-api",
				title: "Baidu Search",
				description: "baidu_desc",
				icon: getConnectorIcon(EnumConnectorName.BAIDU_SEARCH_API, "h-6 w-6"),
				status: "available",
			},
		],
	},
	{
		id: "team-chats",
		title: "team_chats",
		connectors: [
			{
				id: "slack-connector",
				title: "Slack",
				description: "slack_desc",
				icon: getConnectorIcon(EnumConnectorName.SLACK_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "ms-teams",
				title: "Microsoft Teams",
				description: "teams_desc",
				icon: <IconBrandWindows className="h-6 w-6" />,
				status: "coming-soon",
			},
			{
				id: "discord-connector",
				title: "Discord",
				description: "discord_desc",
				icon: getConnectorIcon(EnumConnectorName.DISCORD_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
		],
	},
	{
		id: "project-management",
		title: "project_management",
		connectors: [
			{
				id: "linear-connector",
				title: "Linear",
				description: "linear_desc",
				icon: getConnectorIcon(EnumConnectorName.LINEAR_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "jira-connector",
				title: "Jira",
				description: "jira_desc",
				icon: getConnectorIcon(EnumConnectorName.JIRA_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "clickup-connector",
				title: "ClickUp",
				description: "clickup_desc",
				icon: getConnectorIcon(EnumConnectorName.CLICKUP_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
		],
	},
	{
		id: "knowledge-bases",
		title: "knowledge_bases",
		connectors: [
			{
				id: "notion-connector",
				title: "Notion",
				description: "notion_desc",
				icon: getConnectorIcon(EnumConnectorName.NOTION_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "github-connector",
				title: "GitHub",
				description: "github_desc",
				icon: getConnectorIcon(EnumConnectorName.GITHUB_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "confluence-connector",
				title: "Confluence",
				description: "confluence_desc",
				icon: getConnectorIcon(EnumConnectorName.CONFLUENCE_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "airtable-connector",
				title: "Airtable",
				description: "airtable_desc",
				icon: getConnectorIcon(EnumConnectorName.AIRTABLE_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "luma-connector",
				title: "Luma",
				description: "luma_desc",
				icon: getConnectorIcon(EnumConnectorName.LUMA_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
		],
	},
	{
		id: "communication",
		title: "communication",
		connectors: [
			{
				id: "google-calendar-connector",
				title: "Google Calendar",
				description: "calendar_desc",
				icon: getConnectorIcon(EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "google-gmail-connector",
				title: "Gmail",
				description: "gmail_desc",
				icon: getConnectorIcon(EnumConnectorName.GOOGLE_GMAIL_CONNECTOR, "h-6 w-6"),
				status: "available",
			},
			{
				id: "zoom",
				title: "Zoom",
				description: "zoom_desc",
				icon: <IconBrandZoom className="h-6 w-6" />,
				status: "coming-soon",
			},
		],
	},
];

// Animation variants
const fadeIn = {
	hidden: { opacity: 0 },
	visible: { opacity: 1, transition: { duration: 0.4 } },
};

const staggerContainer = {
	hidden: { opacity: 0 },
	visible: {
		opacity: 1,
		transition: {
			staggerChildren: 0.1,
		},
	},
};

const cardVariants: Variants = {
	hidden: { opacity: 0, y: 20 },
	visible: {
		opacity: 1,
		y: 0,
		transition: {
			type: "spring",
			stiffness: 260,
			damping: 20,
		},
	},
	hover: {
		scale: 1.02,
		boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
		transition: {
			type: "spring",
			stiffness: 400,
			damping: 10,
		},
	},
};

export default function ConnectorsPage() {
	const t = useTranslations('add_connector');
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [expandedCategories, setExpandedCategories] = useState<string[]>([
		"search-engines",
		"knowledge-bases",
		"project-management",
		"team-chats",
		"communication",
	]);

	const toggleCategory = (categoryId: string) => {
		setExpandedCategories((prev) =>
			prev.includes(categoryId) ? prev.filter((id) => id !== categoryId) : [...prev, categoryId]
		);
	};

	return (
		<div className="container mx-auto py-12 max-w-6xl">
			<motion.div
				initial={{ opacity: 0, y: 30 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{
					duration: 0.6,
					ease: [0.22, 1, 0.36, 1],
				}}
				className="mb-12 text-center"
			>
				<h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-indigo-500 to-purple-500 bg-clip-text text-transparent">
					{t('title')}
				</h1>
				<p className="text-muted-foreground mt-3 text-lg max-w-2xl mx-auto">
					{t('subtitle')}
				</p>
			</motion.div>

			<motion.div
				className="space-y-8"
				initial="hidden"
				animate="visible"
				variants={staggerContainer}
			>
				{connectorCategories.map((category) => (
					<motion.div
						key={category.id}
						variants={fadeIn}
						className="rounded-lg border bg-card text-card-foreground shadow-sm"
					>
						<Collapsible
							open={expandedCategories.includes(category.id)}
							onOpenChange={() => toggleCategory(category.id)}
							className="w-full"
						>
							<div className="flex items-center justify-between space-x-4 p-4">
								<h3 className="text-xl font-semibold">{t(category.title)}</h3>
								<CollapsibleTrigger asChild>
									<Button variant="ghost" size="sm" className="w-9 p-0 hover:bg-muted">
										<motion.div
											animate={{
												rotate: expandedCategories.includes(category.id) ? 180 : 0,
											}}
											transition={{ duration: 0.3, ease: "easeInOut" }}
										>
											<IconChevronDown className="h-5 w-5" />
										</motion.div>
										<span className="sr-only">Toggle</span>
									</Button>
								</CollapsibleTrigger>
							</div>

							<CollapsibleContent>
								<AnimatePresence>
									<motion.div
										className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 p-4"
										variants={staggerContainer}
										initial="hidden"
										animate="visible"
										exit="hidden"
									>
										{category.connectors.map((connector) => (
											<motion.div
												key={connector.id}
												variants={cardVariants}
												whileHover="hover"
												className="col-span-1"
											>
												<Card className="h-full flex flex-col overflow-hidden border-transparent transition-all duration-200 hover:border-primary/50">
													<CardHeader className="flex-row items-center gap-4 pb-2">
														<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 dark:bg-primary/20">
															<motion.div
																whileHover={{ rotate: 5, scale: 1.1 }}
																className="text-primary"
															>
																{connector.icon}
															</motion.div>
														</div>
														<div>
															<div className="flex items-center gap-2">
																<h3 className="font-medium">{connector.title}</h3>
																{connector.status === "coming-soon" && (
																	<Badge
																		variant="outline"
																		className="text-xs bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800"
																	>
																		{t('coming_soon')}
																	</Badge>
																)}
																{connector.status === "connected" && (
																	<Badge
																		variant="outline"
																		className="text-xs bg-green-100 dark:bg-green-950 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800"
																	>
																		{t('connected')}
																	</Badge>
																)}
															</div>
														</div>
													</CardHeader>

													<CardContent className="pb-4">
														<p className="text-sm text-muted-foreground">{t(connector.description)}</p>
													</CardContent>

													<CardFooter className="mt-auto pt-2">
														{connector.status === "available" && (
															<Link
																href={`/dashboard/${searchSpaceId}/connectors/add/${connector.id}`}
																className="w-full"
															>
																<Button variant="default" className="w-full group">
																	<span>{t('connect')}</span>
																	<motion.div
																		className="ml-1"
																		initial={{ x: 0 }}
																		whileHover={{ x: 3 }}
																		transition={{
																			type: "spring",
																			stiffness: 400,
																			damping: 10,
																		}}
																	>
																		<IconChevronRight className="h-4 w-4" />
																	</motion.div>
																</Button>
															</Link>
														)}
														{connector.status === "coming-soon" && (
															<Button variant="outline" disabled className="w-full opacity-70">
																{t('coming_soon')}
															</Button>
														)}
														{connector.status === "connected" && (
															<Button
																variant="outline"
																className="w-full border-green-500 text-green-600 hover:bg-green-50 dark:hover:bg-green-950"
															>
																{t('manage')}
															</Button>
														)}
													</CardFooter>
												</Card>
											</motion.div>
										))}
									</motion.div>
								</AnimatePresence>
							</CollapsibleContent>
						</Collapsible>
					</motion.div>
				))}
			</motion.div>
		</div>
	);
}
