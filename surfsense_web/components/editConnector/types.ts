import * as z from "zod";

// Types
export interface GithubRepo {
    id: number;
    name: string;
    full_name: string;
    private: boolean;
    url: string;
    description: string | null;
    last_updated: string | null;
}

export type EditMode = 'viewing' | 'editing_repos';

// Schemas
export const githubPatSchema = z.object({
    github_pat: z.string()
        .min(20, { message: "GitHub Personal Access Token seems too short." })
        .refine(pat => pat.startsWith('ghp_') || pat.startsWith('github_pat_'), {
            message: "GitHub PAT should start with 'ghp_' or 'github_pat_'",
        }),
});
export type GithubPatFormValues = z.infer<typeof githubPatSchema>;

export const editConnectorSchema = z.object({
    name: z.string().min(3, { message: "Connector name must be at least 3 characters." }),
    SLACK_BOT_TOKEN: z.string().optional(),
    NOTION_INTEGRATION_TOKEN: z.string().optional(),
    SERPER_API_KEY: z.string().optional(),
    TAVILY_API_KEY: z.string().optional(),
    LINEAR_API_KEY: z.string().optional(),
    LINKUP_API_KEY: z.string().optional(),
    DISCORD_BOT_TOKEN: z.string().optional(),
});
export type EditConnectorFormValues = z.infer<typeof editConnectorSchema>; 
