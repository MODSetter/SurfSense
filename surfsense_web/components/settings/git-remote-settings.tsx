"use client";

import { IconBrandGithub, IconBrandGitlab } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronsUpDown, Folder } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Command, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import type { GitlabRepo } from "@/contracts/types/git-remote.types";
import { gitRemotesApiService } from "@/lib/apis/git-remotes-api.service";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { Spinner } from "../ui/spinner";

/** Cap rendered folder rows; deep repos can list thousands of directories. */
const MAX_FOLDER_OPTIONS = 200;

interface GitRemoteSettingsProps {
	workspaceId: number;
	githubInstallationId?: string;
	githubInstallations?: string;
	githubError?: string;
}

export function GitRemoteSettings({
	workspaceId,
	githubInstallationId,
	githubInstallations,
	githubError,
}: GitRemoteSettingsProps) {
	const t = useTranslations("workspaceSettings");
	const router = useRouter();
	const queryClient = useQueryClient();
	const workspaceQuery = useQuery({
		queryKey: cacheKeys.workspaces.detail(workspaceId.toString()),
		queryFn: () => workspacesApiService.getWorkspace({ id: workspaceId }),
		enabled: !!workspaceId,
	});
	const gitNative = workspaceQuery.data?.knowledge_store_enabled === true;
	const remotesQuery = useQuery({
		queryKey: cacheKeys.workspaces.gitRemotes(workspaceId),
		queryFn: () => gitRemotesApiService.list(workspaceId),
		enabled: gitNative,
	});
	const reposQuery = useQuery({
		queryKey: cacheKeys.workspaces.githubRepos(workspaceId, githubInstallationId ?? ""),
		queryFn: () => gitRemotesApiService.listGithubRepos(workspaceId, githubInstallationId ?? ""),
		enabled: gitNative && !!githubInstallationId,
	});

	const [gitlabBranch, setGitlabBranch] = useState("main");
	const [gitlabToken, setGitlabToken] = useState("");
	// Bumped by "Load projects"; keeps the PAT out of the react-query cache key.
	const [gitlabLoadNonce, setGitlabLoadNonce] = useState(0);
	const [gitlabSelectedRepo, setGitlabSelectedRepo] = useState<GitlabRepo | null>(null);
	const [sourcepath, setSourcepath] = useState("docs");
	const [busy, setBusy] = useState(false);
	const [selectedRepo, setSelectedRepo] = useState<{
		full_name: string;
		url: string;
		default_branch?: string;
	} | null>(null);
	const [branch, setBranch] = useState("main");

	const branchesQuery = useQuery({
		queryKey: cacheKeys.workspaces.githubBranches(
			workspaceId,
			githubInstallationId ?? "",
			selectedRepo?.full_name ?? ""
		),
		queryFn: () =>
			gitRemotesApiService.listGithubBranches(workspaceId, {
				installationId: githubInstallationId ?? "",
				fullName: selectedRepo?.full_name ?? "",
			}),
		enabled: gitNative && !!githubInstallationId && !!selectedRepo,
	});

	const foldersQuery = useQuery({
		queryKey: cacheKeys.workspaces.githubFolders(
			workspaceId,
			githubInstallationId ?? "",
			selectedRepo?.full_name ?? "",
			branch
		),
		queryFn: () =>
			gitRemotesApiService.listGithubFolders(workspaceId, {
				installationId: githubInstallationId ?? "",
				fullName: selectedRepo?.full_name ?? "",
				branch,
			}),
		enabled: gitNative && !!githubInstallationId && !!selectedRepo,
	});

	const gitlabTokenTrimmed = gitlabToken.trim();
	const gitlabReposQuery = useQuery({
		queryKey: cacheKeys.workspaces.gitlabRepos(workspaceId, gitlabLoadNonce),
		queryFn: () => gitRemotesApiService.listGitlabRepos(workspaceId, gitlabTokenTrimmed),
		enabled: gitNative && gitlabLoadNonce > 0 && !!gitlabTokenTrimmed,
	});

	const gitlabBranchesQuery = useQuery({
		queryKey: cacheKeys.workspaces.gitlabBranches(workspaceId, gitlabSelectedRepo?.id ?? ""),
		queryFn: () =>
			gitRemotesApiService.listGitlabBranches(workspaceId, {
				token: gitlabTokenTrimmed,
				projectId: gitlabSelectedRepo?.id ?? "",
			}),
		enabled: gitNative && !!gitlabSelectedRepo && !!gitlabTokenTrimmed,
	});

	const gitlabFoldersQuery = useQuery({
		queryKey: cacheKeys.workspaces.gitlabFolders(
			workspaceId,
			gitlabSelectedRepo?.id ?? "",
			gitlabBranch
		),
		queryFn: () =>
			gitRemotesApiService.listGitlabFolders(workspaceId, {
				token: gitlabTokenTrimmed,
				projectId: gitlabSelectedRepo?.id ?? "",
				branch: gitlabBranch,
			}),
		enabled: gitNative && !!gitlabSelectedRepo && !!gitlabTokenTrimmed,
	});

	const installations = (githubInstallations ?? "")
		.split(",")
		.filter(Boolean)
		.map((pair) => {
			const [id, ...rest] = pair.split(":");
			return { id, account: rest.join(":") };
		});

	useEffect(() => {
		if (githubError === "oauth_failed") {
			toast.error(t("connected_repo_github_error"));
		}
	}, [githubError, t]);

	const remote = remotesQuery.data?.[0];
	const settingsPath = `/dashboard/${workspaceId}/workspace-settings/git-remote`;
	const clearGithubQuery = () => {
		router.replace(settingsPath);
	};

	const refresh = () =>
		queryClient.invalidateQueries({ queryKey: cacheKeys.workspaces.gitRemotes(workspaceId) });

	const onGithubConnect = async () => {
		setBusy(true);
		try {
			const { url } = await gitRemotesApiService.githubAuthorizeUrl(workspaceId);
			window.location.href = url;
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_github_error"));
			setBusy(false);
		}
	};

	const onGithubInstall = async () => {
		setBusy(true);
		try {
			const { url } = await gitRemotesApiService.githubInstallUrl(workspaceId);
			window.location.href = url;
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_github_error"));
			setBusy(false);
		}
	};

	const onConfirmGithub = async () => {
		if (!githubInstallationId || !selectedRepo) return;
		setBusy(true);
		try {
			const created = await gitRemotesApiService.add(workspaceId, {
				provider: "github",
				url: selectedRepo.url,
				branch: branch.trim() || "main",
				installation_id: githubInstallationId,
				sourcepath: sourcepath.trim(),
			});
			if (created.last_error_code === "need_direction") {
				toast.info(t("connected_repo_need_direction"));
			} else {
				toast.success(t("connected_repo_github_connected"));
			}
			await refresh();
			clearGithubQuery();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_github_add_error"));
		} finally {
			setBusy(false);
		}
	};

	const onGitlabConnect = async () => {
		if (!gitlabSelectedRepo) return;
		setBusy(true);
		try {
			const created = await gitRemotesApiService.add(workspaceId, {
				provider: "gitlab",
				url: gitlabSelectedRepo.url,
				branch: gitlabBranch.trim() || "main",
				token: gitlabTokenTrimmed,
				sourcepath: sourcepath.trim(),
			});
			if (created.last_error_code === "need_direction") {
				toast.info(t("connected_repo_need_direction"));
			} else {
				toast.success(t("connected_repo_gitlab_connected"));
			}
			setGitlabToken("");
			setGitlabSelectedRepo(null);
			await refresh();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_gitlab_add_error"));
		} finally {
			setBusy(false);
		}
	};

	const onDisconnect = async () => {
		setBusy(true);
		try {
			await gitRemotesApiService.remove(workspaceId);
			toast.success(t("connected_repo_disconnected"));
			await refresh();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_disconnect_error"));
		} finally {
			setBusy(false);
		}
	};

	const onRetry = async () => {
		setBusy(true);
		try {
			await gitRemotesApiService.retryPush(workspaceId);
			toast.success(t("connected_repo_push_queued"));
			await refresh();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_retry_error"));
		} finally {
			setBusy(false);
		}
	};

	const onResolve = async (direction: "from_remote" | "from_local") => {
		setBusy(true);
		try {
			await gitRemotesApiService.resolve(workspaceId, direction);
			toast.success(t("connected_repo_push_queued"));
			await refresh();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_resolve_error"));
		} finally {
			setBusy(false);
		}
	};

	if (workspaceQuery.isLoading) {
		return (
			<div className="flex flex-col gap-4">
				<Skeleton className="h-4 w-2/3" />
				<Skeleton className="h-10 w-40" />
			</div>
		);
	}

	if (!gitNative) {
		return <p className="text-sm text-muted-foreground">{t("connected_repo_not_native")}</p>;
	}

	return (
		<div className="flex flex-col gap-6">
			<p className="text-sm text-muted-foreground">{t("connected_repo_description")}</p>

			{remotesQuery.isLoading ? (
				<Skeleton className="h-24 w-full" />
			) : remote ? (
				<div className="flex flex-col gap-4 rounded-lg border p-4">
					<div className="flex items-center justify-between gap-3">
						<span className="inline-flex items-center gap-1.5 text-sm font-medium">
							{remote.provider === "github" ? (
								<IconBrandGithub size={15} />
							) : (
								<IconBrandGitlab size={15} />
							)}
							{remote.provider === "github" ? "GitHub" : "GitLab"}
						</span>
						{remote.last_error_code || remote.last_push_error ? (
							<Badge variant="destructive">{t("connected_repo_status_error")}</Badge>
						) : remote.last_pushed_revision ? (
							<Badge variant="secondary">{t("connected_repo_status_synced")}</Badge>
						) : (
							<Badge variant="outline" className="text-muted-foreground">
								{t("connected_repo_not_pushed")}
							</Badge>
						)}
					</div>
					<a
						href={remote.url}
						target="_blank"
						rel="noreferrer"
						className="font-mono text-sm break-all text-foreground hover:underline"
					>
						{remote.url}
					</a>
					<dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
						<dt className="text-muted-foreground">{t("connected_repo_branch_label")}</dt>
						<dd className="font-medium">{remote.branch}</dd>
						{remote.sourcepath != null ? (
							<>
								<dt className="text-muted-foreground">{t("connected_repo_sourcepath_label")}</dt>
								<dd className="font-mono">{remote.sourcepath || "/"}</dd>
							</>
						) : null}
						{remote.last_pushed_revision ? (
							<>
								<dt className="text-muted-foreground">{t("connected_repo_last_synced_label")}</dt>
								<dd className="font-mono text-xs">
									{remote.last_pushed_revision.slice(0, 12)}
									{remote.last_pushed_at
										? ` · ${new Date(remote.last_pushed_at).toLocaleString()}`
										: ""}
								</dd>
							</>
						) : null}
					</dl>
					{remote.last_error_code === "conflict" || remote.last_error_code === "need_direction" ? (
						<p className="text-xs text-destructive">
							{remote.last_error_code === "need_direction"
								? t("connected_repo_need_direction")
								: t("connected_repo_conflict")}
							{remote.last_conflict_paths ? ` ${remote.last_conflict_paths}` : ""}
						</p>
					) : remote.last_error_code ? (
						<p className="text-xs text-destructive">{remote.last_error_code}</p>
					) : remote.last_push_error ? (
						<p className="text-xs text-destructive">{remote.last_push_error}</p>
					) : null}
					<div className="flex flex-wrap gap-2">
						{remote.last_error_code === "conflict" ||
						remote.last_error_code === "need_direction" ? (
							<>
								<Button
									type="button"
									variant="secondary"
									size="sm"
									disabled={busy}
									onClick={() => onResolve("from_remote")}
								>
									{busy ? <Spinner size="sm" /> : t("connected_repo_use_remote")}
								</Button>
								<Button
									type="button"
									variant="secondary"
									size="sm"
									disabled={busy}
									onClick={() => onResolve("from_local")}
								>
									{busy ? <Spinner size="sm" /> : t("connected_repo_use_local")}
								</Button>
							</>
						) : (
							<Button type="button" variant="secondary" size="sm" disabled={busy} onClick={onRetry}>
								{busy ? <Spinner size="sm" /> : t("connected_repo_retry")}
							</Button>
						)}
						<Button
							type="button"
							variant="outline"
							size="sm"
							disabled={busy}
							onClick={onDisconnect}
						>
							{t("connected_repo_disconnect")}
						</Button>
					</div>
				</div>
			) : githubInstallationId && selectedRepo ? (
				<div className="flex flex-col gap-3 rounded-lg border p-4">
					<p className="text-sm font-medium">{selectedRepo.full_name}</p>
					<div className="flex flex-col gap-2">
						<Label htmlFor="github-branch">{t("connected_repo_branch_label")}</Label>
						<Select value={branch} onValueChange={setBranch}>
							<SelectTrigger id="github-branch">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{((branchesQuery.data ?? []).includes(branch)
									? (branchesQuery.data ?? [])
									: [branch, ...(branchesQuery.data ?? [])]
								).map((name) => (
									<SelectItem key={name} value={name}>
										{name}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</div>
					<div className="flex flex-col gap-2">
						<Label htmlFor="github-sourcepath">{t("connected_repo_sourcepath_label")}</Label>
						<FolderPicker
							value={sourcepath}
							onChange={setSourcepath}
							folders={foldersQuery.data ?? []}
							loading={foldersQuery.isLoading}
							error={foldersQuery.isError}
						/>
						<p className="text-xs text-muted-foreground">{t("connected_repo_folder_hint")}</p>
					</div>
					<div className="flex gap-2">
						<Button type="button" size="sm" disabled={busy} onClick={onConfirmGithub}>
							{busy ? <Spinner size="sm" /> : t("connected_repo_connect_cta")}
						</Button>
						<Button
							type="button"
							variant="ghost"
							size="sm"
							disabled={busy}
							onClick={() => setSelectedRepo(null)}
						>
							{t("connected_repo_cancel")}
						</Button>
					</div>
				</div>
			) : githubInstallationId ? (
				<div className="flex flex-col gap-3 rounded-lg border p-4">
					<p className="text-sm">{t("connected_repo_pick")}</p>
					{reposQuery.isLoading ? (
						<Skeleton className="h-10 w-full" />
					) : (reposQuery.data ?? []).length === 0 ? (
						<p className="text-xs text-muted-foreground">{t("connected_repo_no_repos")}</p>
					) : (
						<ul className="flex max-h-64 flex-col gap-1 overflow-y-auto">
							{(reposQuery.data ?? []).map((repo) => (
								<li key={repo.full_name}>
									<Button
										type="button"
										variant="outline"
										size="sm"
										disabled={busy}
										onClick={() => {
											setSelectedRepo(repo);
											setBranch(repo.default_branch || "main");
										}}
										className="w-full justify-start gap-2 font-normal"
									>
										<IconBrandGithub size={14} className="shrink-0 text-muted-foreground" />
										<span className="truncate">{repo.full_name}</span>
									</Button>
								</li>
							))}
						</ul>
					)}
					<Button
						type="button"
						variant="ghost"
						size="sm"
						onClick={clearGithubQuery}
						className="w-fit"
					>
						{t("connected_repo_cancel")}
					</Button>
				</div>
			) : installations.length > 0 ? (
				<div className="flex flex-col gap-3 rounded-lg border p-4">
					<p className="text-sm">{t("connected_repo_choose_installation")}</p>
					<ul className="flex flex-col gap-1">
						{installations.map((inst) => (
							<li key={inst.id}>
								<Button
									type="button"
									variant="outline"
									size="sm"
									className="gap-1.5"
									onClick={() =>
										router.replace(`${settingsPath}?github_installation_id=${inst.id}`)
									}
								>
									<IconBrandGithub size={14} />
									{inst.account || inst.id}
								</Button>
							</li>
						))}
					</ul>
					<Button
						type="button"
						variant="ghost"
						size="sm"
						onClick={clearGithubQuery}
						className="w-fit"
					>
						{t("connected_repo_cancel")}
					</Button>
				</div>
			) : githubError === "no_installation" ? (
				<div className="flex flex-col gap-3 rounded-lg border p-4">
					<p className="text-sm text-muted-foreground">{t("connected_repo_no_installation")}</p>
					<Button
						type="button"
						variant="secondary"
						size="sm"
						disabled={busy}
						onClick={onGithubInstall}
						className="w-fit"
					>
						{busy ? <Spinner size="sm" /> : t("connected_repo_install_cta")}
					</Button>
				</div>
			) : (
				<Accordion type="single" collapsible defaultValue="github" className="rounded-lg border">
					<AccordionItem value="github" className="px-4">
						<AccordionTrigger className="hover:no-underline">
							<span className="flex items-center gap-2">
								<IconBrandGithub />
								GitHub
							</span>
						</AccordionTrigger>
						<AccordionContent>
							<div className="flex flex-col gap-3">
								<p className="text-muted-foreground">{t("connected_repo_github_blurb")}</p>
								<Button
									type="button"
									variant="secondary"
									size="sm"
									disabled={busy}
									onClick={onGithubConnect}
									className="w-fit"
								>
									{busy ? <Spinner size="sm" /> : t("connected_repo_github_cta")}
								</Button>
							</div>
						</AccordionContent>
					</AccordionItem>
					<AccordionItem value="gitlab" className="px-4">
						<AccordionTrigger className="hover:no-underline">
							<span className="flex items-center gap-2">
								<IconBrandGitlab />
								GitLab
							</span>
						</AccordionTrigger>
						<AccordionContent>
							<div className="flex flex-col gap-3">
								<p className="text-muted-foreground">{t("connected_repo_gitlab_blurb")}</p>
								<div className="flex flex-col gap-2">
									<Label htmlFor="gitlab-token">{t("connected_repo_gitlab_token")}</Label>
									<Input
										id="gitlab-token"
										type="password"
										autoComplete="off"
										value={gitlabToken}
										onChange={(e) => setGitlabToken(e.target.value)}
									/>
									<p className="text-xs text-muted-foreground">
										{t("connected_repo_gitlab_token_hint")}
									</p>
								</div>
								{gitlabSelectedRepo ? (
									<>
										<p className="text-sm font-medium">{gitlabSelectedRepo.full_name}</p>
										<div className="flex flex-col gap-2">
											<Label htmlFor="gitlab-branch">{t("connected_repo_branch_label")}</Label>
											<Select value={gitlabBranch} onValueChange={setGitlabBranch}>
												<SelectTrigger id="gitlab-branch">
													<SelectValue />
												</SelectTrigger>
												<SelectContent>
													{((gitlabBranchesQuery.data ?? []).includes(gitlabBranch)
														? (gitlabBranchesQuery.data ?? [])
														: [gitlabBranch, ...(gitlabBranchesQuery.data ?? [])]
													).map((name) => (
														<SelectItem key={name} value={name}>
															{name}
														</SelectItem>
													))}
												</SelectContent>
											</Select>
										</div>
										<div className="flex flex-col gap-2">
											<Label htmlFor="gitlab-sourcepath">
												{t("connected_repo_sourcepath_label")}
											</Label>
											<FolderPicker
												id="gitlab-sourcepath"
												value={sourcepath}
												onChange={setSourcepath}
												folders={gitlabFoldersQuery.data ?? []}
												loading={gitlabFoldersQuery.isLoading}
												error={gitlabFoldersQuery.isError}
											/>
											<p className="text-xs text-muted-foreground">
												{t("connected_repo_folder_hint")}
											</p>
										</div>
										<div className="flex gap-2">
											<Button type="button" size="sm" disabled={busy} onClick={onGitlabConnect}>
												{busy ? <Spinner size="sm" /> : t("connected_repo_connect_cta")}
											</Button>
											<Button
												type="button"
												variant="ghost"
												size="sm"
												disabled={busy}
												onClick={() => setGitlabSelectedRepo(null)}
											>
												{t("connected_repo_cancel")}
											</Button>
										</div>
									</>
								) : (
									<>
										<Button
											type="button"
											variant="secondary"
											size="sm"
											disabled={busy || !gitlabTokenTrimmed}
											onClick={() => setGitlabLoadNonce((n) => n + 1)}
											className="w-fit"
										>
											{t("connected_repo_gitlab_load")}
										</Button>
										{gitlabLoadNonce > 0 ? (
											gitlabReposQuery.isLoading ? (
												<Skeleton className="h-10 w-full" />
											) : gitlabReposQuery.isError ? (
												<p className="text-xs text-destructive">
													{t("connected_repo_gitlab_add_error")}
												</p>
											) : (gitlabReposQuery.data ?? []).length === 0 ? (
												<p className="text-xs text-muted-foreground">
													{t("connected_repo_no_repos")}
												</p>
											) : (
												<ul className="flex max-h-64 flex-col gap-1 overflow-y-auto">
													{(gitlabReposQuery.data ?? []).map((repo) => (
														<li key={repo.id}>
															<Button
																type="button"
																variant="outline"
																size="sm"
																disabled={busy}
																onClick={() => {
																	setGitlabSelectedRepo(repo);
																	setGitlabBranch(repo.default_branch || "main");
																}}
																className="w-full justify-start gap-2 font-normal"
															>
																<IconBrandGitlab size={14} className="shrink-0 text-muted-foreground" />
																<span className="truncate">{repo.full_name}</span>
															</Button>
														</li>
													))}
												</ul>
											)
										) : null}
									</>
								)}
							</div>
						</AccordionContent>
					</AccordionItem>
				</Accordion>
			)}
		</div>
	);
}

function FolderPicker({
	id = "github-sourcepath",
	value,
	onChange,
	folders,
	loading,
	error,
}: {
	id?: string;
	value: string;
	onChange: (value: string) => void;
	folders: string[];
	loading: boolean;
	error: boolean;
}) {
	const t = useTranslations("workspaceSettings");
	const [open, setOpen] = useState(false);
	const [query, setQuery] = useState("");

	const trimmed = query.trim();
	const matches = useMemo(() => {
		const q = trimmed.toLowerCase();
		return q ? folders.filter((folder) => folder.toLowerCase().includes(q)) : folders;
	}, [folders, trimmed]);
	const shown = matches.slice(0, MAX_FOLDER_OPTIONS);
	const hiddenCount = matches.length - shown.length;
	const showCustom = trimmed.length > 0 && !folders.includes(trimmed);

	const choose = (next: string) => {
		onChange(next);
		setQuery("");
		setOpen(false);
	};

	return (
		<Popover
			open={open}
			onOpenChange={(next) => {
				setOpen(next);
				if (!next) setQuery("");
			}}
		>
			<PopoverTrigger asChild>
				<Button
					id={id}
					type="button"
					variant="outline"
					role="combobox"
					aria-expanded={open}
					className="h-9 w-full justify-between gap-2 font-normal"
				>
					<span className="flex min-w-0 items-center gap-2">
						<Folder size={14} className="shrink-0 text-muted-foreground" />
						<span className="truncate">{value || t("connected_repo_folder_root")}</span>
					</span>
					<ChevronsUpDown size={14} className="shrink-0 opacity-50" />
				</Button>
			</PopoverTrigger>
			<PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] p-0">
				<Command shouldFilter={false}>
					<CommandInput
						value={query}
						onValueChange={setQuery}
						placeholder={t("connected_repo_folder_search")}
					/>
					<CommandList>
						{loading ? (
							<div className="flex items-center justify-center py-6">
								<Spinner size="sm" />
							</div>
						) : error ? (
							<div className="px-3 py-6 text-center text-xs text-destructive">
								{t("connected_repo_folders_error")}
							</div>
						) : (
							<>
								<CommandItem value="__root__" onSelect={() => choose("")}>
									<Folder size={14} className="text-muted-foreground" />
									<span className="truncate">{t("connected_repo_folder_root")}</span>
									{value === "" ? <Check size={14} className="ml-auto shrink-0" /> : null}
								</CommandItem>
								{shown.map((folder) => (
									<CommandItem key={folder} value={folder} onSelect={() => choose(folder)}>
										<Folder size={14} className="text-muted-foreground" />
										<span className="truncate">{folder}</span>
										{value === folder ? <Check size={14} className="ml-auto shrink-0" /> : null}
									</CommandItem>
								))}
								{showCustom ? (
									<CommandItem value={`__custom__${trimmed}`} onSelect={() => choose(trimmed)}>
										<span className="truncate">
											{t("connected_repo_folder_use")} “{trimmed}”
										</span>
									</CommandItem>
								) : null}
								{hiddenCount > 0 ? (
									<p className="px-3 py-2 text-center text-[11px] text-muted-foreground">
										{hiddenCount} {t("connected_repo_folder_more")}
									</p>
								) : null}
							</>
						)}
					</CommandList>
				</Command>
			</PopoverContent>
		</Popover>
	);
}
