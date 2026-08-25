"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { gitRemotesApiService } from "@/lib/apis/git-remotes-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { Spinner } from "../ui/spinner";

interface GitRemoteSettingsProps {
	workspaceId: number;
	githubInstallationId?: string;
}

export function GitRemoteSettings({
	workspaceId,
	githubInstallationId,
}: GitRemoteSettingsProps) {
	const router = useRouter();
	const queryClient = useQueryClient();
	const remotesQuery = useQuery({
		queryKey: cacheKeys.workspaces.gitRemotes(workspaceId),
		queryFn: () => gitRemotesApiService.list(workspaceId),
	});
	const reposQuery = useQuery({
		queryKey: cacheKeys.workspaces.githubRepos(workspaceId, githubInstallationId ?? ""),
		queryFn: () => gitRemotesApiService.listGithubRepos(workspaceId, githubInstallationId ?? ""),
		enabled: !!githubInstallationId,
	});

	const [gitlabUrl, setGitlabUrl] = useState("");
	const [gitlabBranch, setGitlabBranch] = useState("main");
	const [gitlabToken, setGitlabToken] = useState("");
	const [busy, setBusy] = useState(false);

	const remote = remotesQuery.data?.[0];
	const clearGithubQuery = () => {
		router.replace(`/dashboard/${workspaceId}/workspace-settings/general`);
	};

	const refresh = () =>
		queryClient.invalidateQueries({ queryKey: cacheKeys.workspaces.gitRemotes(workspaceId) });

	const onGithubConnect = async () => {
		setBusy(true);
		try {
			const { url } = await gitRemotesApiService.githubInstallUrl(workspaceId);
			window.location.href = url;
		} catch (err) {
			toast.error(err instanceof Error ? err.message : "Could not start GitHub install");
			setBusy(false);
		}
	};

	const onPickGithubRepo = async (url: string) => {
		if (!githubInstallationId) return;
		setBusy(true);
		try {
			await gitRemotesApiService.add(workspaceId, {
				provider: "github",
				url,
				branch: "main",
				installation_id: githubInstallationId,
			});
			toast.success("GitHub remote connected");
			await refresh();
			clearGithubQuery();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : "Could not add GitHub remote");
		} finally {
			setBusy(false);
		}
	};

	const onGitlabConnect = async (e: FormEvent) => {
		e.preventDefault();
		setBusy(true);
		try {
			await gitRemotesApiService.add(workspaceId, {
				provider: "gitlab",
				url: gitlabUrl.trim(),
				branch: gitlabBranch.trim() || "main",
				token: gitlabToken.trim(),
			});
			toast.success("GitLab remote connected");
			setGitlabToken("");
			await refresh();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : "Could not add GitLab remote");
		} finally {
			setBusy(false);
		}
	};

	const onDisconnect = async () => {
		setBusy(true);
		try {
			await gitRemotesApiService.remove(workspaceId);
			toast.success("Remote disconnected");
			await refresh();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : "Could not disconnect");
		} finally {
			setBusy(false);
		}
	};

	const onRetry = async () => {
		setBusy(true);
		try {
			await gitRemotesApiService.retryPush(workspaceId);
			toast.success("Push queued");
			await refresh();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : "Could not retry push");
		} finally {
			setBusy(false);
		}
	};

	return (
		<div className="border-t pt-6 space-y-4">
			<div className="space-y-1">
				<Label>Git remote</Label>
				<p className="text-xs text-muted-foreground">
					Push this workspace&apos;s markdown history to a GitHub or GitLab repo you own. The
					remote must start empty.
				</p>
			</div>

			{remotesQuery.isLoading ? (
				<div className="h-10 w-40 rounded-md bg-muted animate-pulse" />
			) : remote ? (
				<div className="space-y-3">
					<p className="text-sm break-all">
						{remote.provider}: {remote.url} ({remote.branch})
					</p>
					{remote.last_pushed_revision ? (
						<p className="text-xs text-muted-foreground font-mono">
							last pushed {remote.last_pushed_revision.slice(0, 12)}
							{remote.last_pushed_at
								? ` · ${new Date(remote.last_pushed_at).toLocaleString()}`
								: ""}
						</p>
					) : (
						<p className="text-xs text-muted-foreground">Not pushed yet</p>
					)}
					{remote.last_push_error ? (
						<p className="text-xs text-destructive">{remote.last_push_error}</p>
					) : null}
					<div className="flex flex-wrap gap-2">
						<Button type="button" variant="secondary" size="sm" disabled={busy} onClick={onRetry}>
							{busy ? <Spinner size="sm" /> : "Retry push"}
						</Button>
						<Button
							type="button"
							variant="outline"
							size="sm"
							disabled={busy}
							onClick={onDisconnect}
						>
							Disconnect
						</Button>
					</div>
				</div>
			) : githubInstallationId ? (
				<div className="space-y-2">
					<p className="text-sm">Choose a repository to push to. It must have no commits on main.</p>
					{reposQuery.isLoading ? (
						<div className="h-10 w-full rounded-md bg-muted animate-pulse" />
					) : (reposQuery.data ?? []).length === 0 ? (
						<p className="text-xs text-muted-foreground">No repositories on this installation.</p>
					) : (
						<ul className="space-y-1">
							{(reposQuery.data ?? []).map((repo) => (
								<li key={repo.full_name}>
									<Button
										type="button"
										variant="outline"
										size="sm"
										disabled={busy}
										onClick={() => onPickGithubRepo(repo.url)}
									>
										{repo.full_name}
									</Button>
								</li>
							))}
						</ul>
					)}
					<Button type="button" variant="ghost" size="sm" onClick={clearGithubQuery}>
						Cancel
					</Button>
				</div>
			) : (
				<div className="space-y-6">
					<div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
						<p className="text-sm">GitHub App install, then pick a repo.</p>
						<Button
							type="button"
							variant="secondary"
							size="sm"
							disabled={busy}
							onClick={onGithubConnect}
							className="w-fit"
						>
							Connect GitHub
						</Button>
					</div>
					<form onSubmit={onGitlabConnect} className="space-y-3">
						<p className="text-sm">Or paste a GitLab.com HTTPS URL and a PAT with write_repository.</p>
						<div className="space-y-2">
							<Label htmlFor="gitlab-url">GitLab clone URL</Label>
							<Input
								id="gitlab-url"
								type="url"
								placeholder="https://gitlab.com/group/project.git"
								value={gitlabUrl}
								onChange={(e) => setGitlabUrl(e.target.value)}
								required
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="gitlab-branch">Branch</Label>
							<Input
								id="gitlab-branch"
								value={gitlabBranch}
								onChange={(e) => setGitlabBranch(e.target.value)}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="gitlab-token">Personal access token</Label>
							<Input
								id="gitlab-token"
								type="password"
								autoComplete="off"
								value={gitlabToken}
								onChange={(e) => setGitlabToken(e.target.value)}
								required
							/>
						</div>
						<Button type="submit" variant="secondary" size="sm" disabled={busy} className="w-fit">
							{busy ? <Spinner size="sm" /> : "Connect GitLab"}
						</Button>
					</form>
				</div>
			)}
		</div>
	);
}
