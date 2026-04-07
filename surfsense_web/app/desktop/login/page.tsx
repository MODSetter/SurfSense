"use client";

import { IconBrandGoogleFilled } from "@tabler/icons-react";
import { useAtom } from "jotai";
import { BrainCog, Eye, EyeOff, Rocket, Zap } from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { loginMutationAtom } from "@/atoms/auth/auth-mutation.atoms";
import { DEFAULT_SHORTCUTS, ShortcutRecorder } from "@/components/desktop/shortcut-recorder";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { useElectronAPI } from "@/hooks/use-platform";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { setBearerToken } from "@/lib/auth-utils";
import { AUTH_TYPE, BACKEND_URL } from "@/lib/env-config";

const isGoogleAuth = AUTH_TYPE === "GOOGLE";

export default function DesktopLoginPage() {
	const router = useRouter();
	const api = useElectronAPI();
	const [{ mutateAsync: login, isPending: isLoggingIn }] = useAtom(loginMutationAtom);

	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [showPassword, setShowPassword] = useState(false);
	const [loginError, setLoginError] = useState<string | null>(null);

	const [shortcuts, setShortcuts] = useState(DEFAULT_SHORTCUTS);
	const [shortcutsLoaded, setShortcutsLoaded] = useState(false);

	useEffect(() => {
		if (!api?.getShortcuts) {
			setShortcutsLoaded(true);
			return;
		}
		api
			.getShortcuts()
			.then((config) => {
				if (config) setShortcuts(config);
				setShortcutsLoaded(true);
			})
			.catch(() => setShortcutsLoaded(true));
	}, [api]);

	const updateShortcut = useCallback(
		(key: "generalAssist" | "quickAsk" | "autocomplete", accelerator: string) => {
			setShortcuts((prev) => {
				const updated = { ...prev, [key]: accelerator };
				api?.setShortcuts?.({ [key]: accelerator }).catch(() => {
					toast.error("Failed to update shortcut");
				});
				return updated;
			});
			toast.success("Shortcut updated");
		},
		[api]
	);

	const resetShortcut = useCallback(
		(key: "generalAssist" | "quickAsk" | "autocomplete") => {
			updateShortcut(key, DEFAULT_SHORTCUTS[key]);
		},
		[updateShortcut]
	);

	const handleGoogleLogin = () => {
		window.location.href = `${BACKEND_URL}/auth/google/authorize-redirect`;
	};

	const autoSetSearchSpace = async () => {
		try {
			const stored = await api?.getActiveSearchSpace?.();
			if (stored) return;
			const spaces = await searchSpacesApiService.getSearchSpaces();
			if (spaces?.length) {
				await api?.setActiveSearchSpace?.(String(spaces[0].id));
			}
		} catch {
			// non-critical — dashboard-sync will catch it later
		}
	};

	const handleLocalLogin = async (e: React.FormEvent) => {
		e.preventDefault();
		setLoginError(null);

		try {
			const data = await login({
				username: email,
				password,
				grant_type: "password",
			});

			if (typeof window !== "undefined") {
				sessionStorage.setItem("login_success_tracked", "true");
			}

			setBearerToken(data.access_token);
			await autoSetSearchSpace();

			setTimeout(() => {
				router.push(`/auth/callback?token=${data.access_token}`);
			}, 300);
		} catch (err) {
			if (err instanceof Error) {
				setLoginError(err.message);
			} else {
				setLoginError("Login failed. Please check your credentials.");
			}
		}
	};

	return (
		<div className="relative flex min-h-svh items-center justify-center bg-background p-4 sm:p-6">
			{/* Subtle radial glow */}
			<div className="pointer-events-none fixed inset-0 overflow-hidden">
				<div
					className="absolute -top-1/2 left-1/2 size-[800px] -translate-x-1/2 rounded-full opacity-[0.03]"
					style={{
						background: "radial-gradient(circle, hsl(var(--primary)) 0%, transparent 70%)",
					}}
				/>
			</div>

			<div className="relative flex w-full max-w-md flex-col overflow-hidden rounded-xl border bg-card shadow-lg">
				{/* Header */}
				<div className="flex flex-col items-center px-6 pt-6 pb-2 text-center">
					<Image
						src="/icon-128.svg"
						className="select-none dark:invert size-12 rounded-lg mb-3"
						alt="SurfSense"
						width={48}
						height={48}
						priority
					/>
					<h1 className="text-lg font-semibold tracking-tight">Welcome to SurfSense Desktop</h1>
					<p className="mt-1 text-sm text-muted-foreground">
						Configure shortcuts, then sign in to get started.
					</p>
				</div>

				{/* Scrollable content */}
				<div className="flex-1 overflow-y-auto px-6 py-4">
					<div className="flex flex-col gap-5">
						{/* ---- Shortcuts ---- */}
						{shortcutsLoaded ? (
							<div className="flex flex-col gap-2">
								<p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
									Keyboard Shortcuts
								</p>
								<div className="flex flex-col gap-1.5">
									<ShortcutRecorder
										value={shortcuts.generalAssist}
										onChange={(accel) => updateShortcut("generalAssist", accel)}
										onReset={() => resetShortcut("generalAssist")}
										defaultValue={DEFAULT_SHORTCUTS.generalAssist}
										label="General Assist"
										description="Launch SurfSense instantly from any application"
										icon={Rocket}
									/>
									<ShortcutRecorder
										value={shortcuts.quickAsk}
										onChange={(accel) => updateShortcut("quickAsk", accel)}
										onReset={() => resetShortcut("quickAsk")}
										defaultValue={DEFAULT_SHORTCUTS.quickAsk}
										label="Quick Assist"
										description="Select text anywhere, then ask AI to explain, rewrite, or act on it"
										icon={Zap}
									/>
									<ShortcutRecorder
										value={shortcuts.autocomplete}
										onChange={(accel) => updateShortcut("autocomplete", accel)}
										onReset={() => resetShortcut("autocomplete")}
										defaultValue={DEFAULT_SHORTCUTS.autocomplete}
										label="Extreme Assist"
										description="AI drafts text using your screen context and knowledge base"
										icon={BrainCog}
									/>
								</div>
								<p className="text-[11px] text-muted-foreground text-center mt-1">
									Click a shortcut and press a new key combination to change it.
								</p>
							</div>
						) : (
							<div className="flex justify-center py-6">
								<Spinner size="sm" />
							</div>
						)}

						<Separator />

						{/* ---- Auth ---- */}
						<div className="flex flex-col gap-3">
							<p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
								Sign In
							</p>

							{isGoogleAuth ? (
								<Button variant="outline" className="w-full gap-2 h-10" onClick={handleGoogleLogin}>
									<IconBrandGoogleFilled className="size-4" />
									Continue with Google
								</Button>
							) : (
								<form onSubmit={handleLocalLogin} className="flex flex-col gap-3">
									{loginError && (
										<div className="rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
											{loginError}
										</div>
									)}

									<div className="flex flex-col gap-1.5">
										<Label htmlFor="email" className="text-xs">
											Email
										</Label>
										<Input
											id="email"
											type="email"
											placeholder="you@example.com"
											required
											value={email}
											onChange={(e) => setEmail(e.target.value)}
											disabled={isLoggingIn}
											autoFocus
											className="h-9"
										/>
									</div>

									<div className="flex flex-col gap-1.5">
										<Label htmlFor="password" className="text-xs">
											Password
										</Label>
										<div className="relative">
											<Input
												id="password"
												type={showPassword ? "text" : "password"}
												placeholder="Enter your password"
												required
												value={password}
												onChange={(e) => setPassword(e.target.value)}
												disabled={isLoggingIn}
												className="h-9 pr-9"
											/>
											<button
												type="button"
												onClick={() => setShowPassword((v) => !v)}
												className="absolute inset-y-0 right-0 flex items-center pr-2.5 text-muted-foreground hover:text-foreground"
												tabIndex={-1}
											>
												{showPassword ? (
													<EyeOff className="size-3.5" />
												) : (
													<Eye className="size-3.5" />
												)}
											</button>
										</div>
									</div>

									<Button type="submit" disabled={isLoggingIn} className="h-9 mt-1">
										{isLoggingIn ? (
											<>
												<Spinner size="sm" className="text-primary-foreground" />
												Signing in…
											</>
										) : (
											"Sign in"
										)}
									</Button>
								</form>
							)}
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
