import {
	IconBook,
	IconBrandDiscord,
	IconBrandElastic,
	IconBrandGithub,
	IconBrandNotion,
	IconBrandSlack,
	IconBrandYoutube,
	IconCalendar,
	IconChecklist,
	IconLayoutKanban,
	IconLinkPlus,
	IconMail,
	IconSparkles,
	IconTable,
	IconTicket,
	IconWorldWww,
} from "@tabler/icons-react";
import { File, Globe, Link, Microscope, Search, Sparkles, Telescope, Webhook } from "lucide-react";
import { EnumConnectorName } from "./connector";

export const getConnectorIcon = (connectorType: EnumConnectorName | string, className?: string) => {
	const iconProps = { className: className || "h-4 w-4" };

	switch (connectorType) {
		case EnumConnectorName.LINKUP_API:
			return <IconLinkPlus {...iconProps} />;
		case EnumConnectorName.LINEAR_CONNECTOR:
			return <IconLayoutKanban {...iconProps} />;
		case EnumConnectorName.GITHUB_CONNECTOR:
			return <IconBrandGithub {...iconProps} />;
		case EnumConnectorName.SERPER_API:
			return <Link {...iconProps} />;
		case EnumConnectorName.TAVILY_API:
			return <IconWorldWww {...iconProps} />;
		case EnumConnectorName.SEARXNG_API:
			return <Globe {...iconProps} />;
		case EnumConnectorName.BAIDU_SEARCH_API:
			return <Search {...iconProps} />;
		case EnumConnectorName.SLACK_CONNECTOR:
			return <IconBrandSlack {...iconProps} />;
		case EnumConnectorName.NOTION_CONNECTOR:
			return <IconBrandNotion {...iconProps} />;
		case EnumConnectorName.DISCORD_CONNECTOR:
			return <IconBrandDiscord {...iconProps} />;
		case EnumConnectorName.JIRA_CONNECTOR:
			return <IconTicket {...iconProps} />;
		case EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR:
			return <IconCalendar {...iconProps} />;
		case EnumConnectorName.GOOGLE_GMAIL_CONNECTOR:
			return <IconMail {...iconProps} />;
		case EnumConnectorName.AIRTABLE_CONNECTOR:
			return <IconTable {...iconProps} />;
		case EnumConnectorName.CONFLUENCE_CONNECTOR:
			return <IconBook {...iconProps} />;
		case EnumConnectorName.CLICKUP_CONNECTOR:
			return <IconChecklist {...iconProps} />;
		case EnumConnectorName.LUMA_CONNECTOR:
			return <IconSparkles {...iconProps} />;
		case EnumConnectorName.ELASTICSEARCH_CONNECTOR:
			return <IconBrandElastic {...iconProps} />;
		// Additional cases for non-enum connector types
		case "YOUTUBE_VIDEO":
			return <IconBrandYoutube {...iconProps} />;
		case "CRAWLED_URL":
			return <Globe {...iconProps} />;
		case "FILE":
			return <File {...iconProps} />;
		case "EXTENSION":
			return <Webhook {...iconProps} />;
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
