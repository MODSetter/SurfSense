// Helper function to get connector type display name
export const getConnectorTypeDisplay = (type: string): string => {
    const typeMap: Record<string, string> = {
        "SERPER_API": "Serper API",
        "TAVILY_API": "Tavily API",
        "SLACK_CONNECTOR": "Slack",
        "NOTION_CONNECTOR": "Notion",
        "GITHUB_CONNECTOR": "GitHub",
        "LINEAR_CONNECTOR": "Linear",
        "DISCORD_CONNECTOR": "Discord",
        "LINKUP_API": "Linkup",
    };
    return typeMap[type] || type;
}; 
