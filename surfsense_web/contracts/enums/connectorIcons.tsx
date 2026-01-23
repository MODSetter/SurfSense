import { IconLinkPlus, IconUsersGroup } from "@tabler/icons-react";
import {
	BookOpen,
	File,
	FileText,
	Globe,
	Microscope,
	Search,
	Sparkles,
	Telescope,
	Webhook,
} from "lucide-react";
import Image from "next/image";
import { EnumConnectorName } from "./connector";

export const getConnectorIcon = (connectorType: EnumConnectorName | string, className?: string) => {
	const iconProps = { className: className || "h-4 w-4" };
	const imgProps = { className: className || "h-5 w-5", width: 20, height: 20 };

	switch (connectorType) {
		case EnumConnectorName.LINKUP_API:
			return <IconLinkPlus {...iconProps} />;
		case EnumConnectorName.LINEAR_CONNECTOR:
			return <Image src="/connectors/linear.svg" alt="Linear" {...imgProps} />;
		case EnumConnectorName.GITHUB_CONNECTOR:
			return <Image src="/connectors/github.svg" alt="GitHub" {...imgProps} />;
		case EnumConnectorName.TAVILY_API:
			return <Image src="/connectors/tavily.svg" alt="Tavily" {...imgProps} />;
		case EnumConnectorName.SEARXNG_API:
			return <Image src="/connectors/searxng.svg" alt="SearXNG" {...imgProps} />;
		case EnumConnectorName.BAIDU_SEARCH_API:
			return <Image src="/connectors/baidu-search.svg" alt="Baidu" {...imgProps} />;
		case EnumConnectorName.SLACK_CONNECTOR:
			return <Image src="/connectors/slack.svg" alt="Slack" {...imgProps} />;
		case EnumConnectorName.TEAMS_CONNECTOR:
			return <Image src="/connectors/microsoft-teams.svg" alt="Microsoft Teams" {...imgProps} />;
		case EnumConnectorName.NOTION_CONNECTOR:
			return <Image src="/connectors/notion.svg" alt="Notion" {...imgProps} />;
		case EnumConnectorName.DISCORD_CONNECTOR:
			return <Image src="/connectors/discord.svg" alt="Discord" {...imgProps} />;
		case EnumConnectorName.JIRA_CONNECTOR:
			return <Image src="/connectors/jira.svg" alt="Jira" {...imgProps} />;
		case EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR:
			return <Image src="/connectors/google-calendar.svg" alt="Google Calendar" {...imgProps} />;
		case EnumConnectorName.GOOGLE_GMAIL_CONNECTOR:
			return <Image src="/connectors/google-gmail.svg" alt="Gmail" {...imgProps} />;
		case EnumConnectorName.GOOGLE_DRIVE_CONNECTOR:
			return <Image src="/connectors/google-drive.svg" alt="Google Drive" {...imgProps} />;
		case EnumConnectorName.AIRTABLE_CONNECTOR:
			return <Image src="/connectors/airtable.svg" alt="Airtable" {...imgProps} />;
		case EnumConnectorName.CONFLUENCE_CONNECTOR:
			return <Image src="/connectors/confluence.svg" alt="Confluence" {...imgProps} />;
		case EnumConnectorName.BOOKSTACK_CONNECTOR:
			return <Image src="/connectors/bookstack.svg" alt="BookStack" {...imgProps} />;
		case EnumConnectorName.CLICKUP_CONNECTOR:
			return <Image src="/connectors/clickup.svg" alt="ClickUp" {...imgProps} />;
		case EnumConnectorName.LUMA_CONNECTOR:
			return <Image src="/connectors/luma.svg" alt="Luma" {...imgProps} />;
		case EnumConnectorName.ELASTICSEARCH_CONNECTOR:
			return <Image src="/connectors/elasticsearch.svg" alt="Elasticsearch" {...imgProps} />;
		case EnumConnectorName.WEBCRAWLER_CONNECTOR:
			return <Globe {...iconProps} />;
		case EnumConnectorName.YOUTUBE_CONNECTOR:
			return <Image src="/connectors/youtube.svg" alt="YouTube" {...imgProps} />;
		case EnumConnectorName.CIRCLEBACK_CONNECTOR:
			return <IconUsersGroup {...iconProps} />;
		case EnumConnectorName.MCP_CONNECTOR:
			return <Image src="/connectors/modelcontextprotocol.svg" alt="MCP" {...imgProps} />;
		case EnumConnectorName.OBSIDIAN_CONNECTOR:
			return <Image src="/connectors/obsidian.svg" alt="Obsidian" {...imgProps} />;
		case EnumConnectorName.COMPOSIO_GOOGLE_DRIVE_CONNECTOR:
			return <Image src="/connectors/google-drive.svg" alt="Google Drive" {...imgProps} />;
		case EnumConnectorName.COMPOSIO_GMAIL_CONNECTOR:
			return <Image src="/connectors/google-gmail.svg" alt="Gmail" {...imgProps} />;
		case EnumConnectorName.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR:
			return <Image src="/connectors/google-calendar.svg" alt="Google Calendar" {...imgProps} />;
		// Additional cases for non-enum connector types
		case "YOUTUBE_CONNECTOR":
			return <Image src="/connectors/youtube.svg" alt="YouTube" {...imgProps} />;
		case "CIRCLEBACK":
			return <IconUsersGroup {...iconProps} />;
		case "CRAWLED_URL":
			return <Globe {...iconProps} />;
		case "YOUTUBE_VIDEO":
			return <Image src="/connectors/youtube.svg" alt="YouTube" {...imgProps} />;
		case "MICROSOFT_TEAMS":
		case "ms-teams":
			return <Image src="/connectors/microsoft-teams.svg" alt="Microsoft Teams" {...imgProps} />;
		case "ZOOM":
		case "zoom":
			return <Image src="/connectors/zoom.svg" alt="Zoom" {...imgProps} />;
		case "FILE":
			return <File {...iconProps} />;
		case "GOOGLE_DRIVE_FILE":
			return <File {...iconProps} />;
		case "COMPOSIO_GOOGLE_DRIVE_CONNECTOR":
			return <Image src="/connectors/google-drive.svg" alt="Google Drive" {...imgProps} />;
		case "COMPOSIO_GMAIL_CONNECTOR":
			return <Image src="/connectors/google-gmail.svg" alt="Gmail" {...imgProps} />;
		case "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR":
			return <Image src="/connectors/google-calendar.svg" alt="Google Calendar" {...imgProps} />;
		case "NOTE":
			return <FileText {...iconProps} />;
		case "EXTENSION":
			return <Webhook {...iconProps} />;
		case "SURFSENSE_DOCS":
			return <BookOpen {...iconProps} />;
		case "DEEP":
			return <Sparkles {...iconProps} />;
		case "DEEPER":
			return <Microscope {...iconProps} />;
		case "DEEPEST":
			return <Telescope {...iconProps} />;
		default:
			return <Search {...iconProps} />;
	}
};
