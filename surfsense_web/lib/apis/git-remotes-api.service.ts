import {
	type AddGitRemoteRequest,
	addGitRemoteRequest,
	gitRemote,
	githubInstallResponse,
	listGitRemotesResponse,
	listGithubReposResponse,
	retryGitRemotePushResponse,
} from "@/contracts/types/git-remote.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class GitRemotesApiService {
	list = async (workspaceId: number) => {
		return baseApiService.get(
			`/api/v1/workspaces/${workspaceId}/git-remotes`,
			listGitRemotesResponse
		);
	};

	add = async (workspaceId: number, request: AddGitRemoteRequest) => {
		const parsed = addGitRemoteRequest.safeParse(request);
		if (!parsed.success) {
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}
		return baseApiService.post(`/api/v1/workspaces/${workspaceId}/git-remotes`, gitRemote, {
			body: parsed.data,
		});
	};

	remove = async (workspaceId: number) => {
		return baseApiService.delete(`/api/v1/workspaces/${workspaceId}/git-remotes`);
	};

	retryPush = async (workspaceId: number) => {
		return baseApiService.post(
			`/api/v1/workspaces/${workspaceId}/git-remotes/push`,
			retryGitRemotePushResponse
		);
	};

	githubInstallUrl = async (workspaceId: number) => {
		return baseApiService.get(
			`/api/v1/workspaces/${workspaceId}/git-remotes/github/install`,
			githubInstallResponse
		);
	};

	listGithubRepos = async (workspaceId: number, installationId: string) => {
		const qs = new URLSearchParams({ installation_id: installationId }).toString();
		return baseApiService.get(
			`/api/v1/workspaces/${workspaceId}/git-remotes/github/repos?${qs}`,
			listGithubReposResponse
		);
	};
}

export const gitRemotesApiService = new GitRemotesApiService();
