import {
	type AddGitRemoteRequest,
	addGitRemoteRequest,
	githubInstallResponse,
	gitRemote,
	listGithubBranchesResponse,
	listGithubFoldersResponse,
	listGithubReposResponse,
	listGitlabReposResponse,
	listGitRemotesResponse,
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
			`/api/v1/workspaces/${workspaceId}/git-remotes/sync`,
			retryGitRemotePushResponse
		);
	};

	resolve = async (workspaceId: number, direction: "from_remote" | "from_local") => {
		return baseApiService.post(
			`/api/v1/workspaces/${workspaceId}/git-remotes/resolve`,
			retryGitRemotePushResponse,
			{ body: { direction } }
		);
	};

	githubInstallUrl = async (workspaceId: number) => {
		return baseApiService.get(
			`/api/v1/workspaces/${workspaceId}/git-remotes/github/install`,
			githubInstallResponse
		);
	};

	githubAuthorizeUrl = async (workspaceId: number) => {
		return baseApiService.get(
			`/api/v1/workspaces/${workspaceId}/git-remotes/github/authorize`,
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

	listGithubFolders = async (
		workspaceId: number,
		params: { installationId: string; fullName: string; branch: string }
	) => {
		const qs = new URLSearchParams({
			installation_id: params.installationId,
			full_name: params.fullName,
			branch: params.branch,
		}).toString();
		return baseApiService.get(
			`/api/v1/workspaces/${workspaceId}/git-remotes/github/folders?${qs}`,
			listGithubFoldersResponse
		);
	};

	listGithubBranches = async (
		workspaceId: number,
		params: { installationId: string; fullName: string }
	) => {
		const qs = new URLSearchParams({
			installation_id: params.installationId,
			full_name: params.fullName,
		}).toString();
		return baseApiService.get(
			`/api/v1/workspaces/${workspaceId}/git-remotes/github/branches?${qs}`,
			listGithubBranchesResponse
		);
	};

	// GitLab lists take the PAT in the body (a secret), so they are POST, not GET.
	listGitlabRepos = async (workspaceId: number, token: string) => {
		return baseApiService.post(
			`/api/v1/workspaces/${workspaceId}/git-remotes/gitlab/repos`,
			listGitlabReposResponse,
			{ body: { token } }
		);
	};

	listGitlabBranches = async (
		workspaceId: number,
		params: { token: string; projectId: string }
	) => {
		return baseApiService.post(
			`/api/v1/workspaces/${workspaceId}/git-remotes/gitlab/branches`,
			listGithubBranchesResponse,
			{ body: { token: params.token, project_id: params.projectId } }
		);
	};

	listGitlabFolders = async (
		workspaceId: number,
		params: { token: string; projectId: string; branch: string }
	) => {
		return baseApiService.post(
			`/api/v1/workspaces/${workspaceId}/git-remotes/gitlab/folders`,
			listGithubFoldersResponse,
			{ body: { token: params.token, project_id: params.projectId, branch: params.branch } }
		);
	};
}

export const gitRemotesApiService = new GitRemotesApiService();
