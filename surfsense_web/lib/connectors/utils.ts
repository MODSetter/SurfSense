// Helper function to get connector type display name
export const getConnectorTypeDisplay = (type: string): string => {
    const typeMap: Record<string, string> = {
        "SERPER_API": "Serper API",
        "TAVILY_API": "Tavily API",
        "SLACK_CONNECTOR": "Slack",
        "NOTION_CONNECTOR": "Notion",
        "GITHUB_CONNECTOR": "GitHub",
    };
    return typeMap[type] || type;
}; 
