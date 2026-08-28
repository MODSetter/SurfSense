import { z } from "zod";

export const gitRemote = z.object({
	provider: z.enum(["github", "gitlab"]),
	url: z.string(),
	branch: z.string(),
	last_pushed_revision: z.string().nullable().optional(),
	last_pushed_at: z.string().nullable().optional(),
	last_push_error: z.string().nullable().optional(),
});

export const listGitRemotesResponse = z.array(gitRemote);

export const addGitRemoteRequest = z.discriminatedUnion("provider", [
	z.object({
		provider: z.literal("github"),
		url: z.string().url(),
		installation_id: z.string().min(1),
		branch: z.string().optional(),
	}),
	z.object({
		provider: z.literal("gitlab"),
		url: z.string().url(),
		token: z.string().min(1),
		branch: z.string().optional(),
	}),
]);

export const githubInstallResponse = z.object({
	url: z.string(),
});

export const githubRepo = z.object({
	full_name: z.string(),
	url: z.string(),
});

export const listGithubReposResponse = z.array(githubRepo);

export const retryGitRemotePushResponse = z.object({
	status: z.string(),
});

export type GitRemote = z.infer<typeof gitRemote>;
export type AddGitRemoteRequest = z.infer<typeof addGitRemoteRequest>;
export type GithubRepo = z.infer<typeof githubRepo>;
