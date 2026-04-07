"use client";

import { IconBrandGoogleFilled } from "@tabler/icons-react";
import { useAtom } from "jotai";
import {
	Eye,
	EyeOff,
	Keyboard,
	Clipboard,
	Sparkles,
} from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { loginMutationAtom } from "@/atoms/auth/auth-mutation.atoms";
import {
	DEFAULT_SHORTCUTS,
	ShortcutRecorder,
} from "@/components/desktop/shortcut-recorder";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { useElectronAPI } from "@/hooks/use-platform";
import { AUTH_TYPE, BACKEND_URL } from "@/lib/env-config";

const isGoogleAuth = AUTH_TYPE === "GOOGLE";

export default function DesktopLoginPage() {
	const router = useRouter();
	const api = useElectronAPI();
	const [{ mutateAsync: login, isPending: isLoggingIn }] =
		useAtom(loginMutationAtom);

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
		api.getShortcuts().then((config) => {
			if (config) setShortcuts(config);
			setShortcutsLoaded(true);
		}).catch(() => setShortcutsLoaded(true));
	}, [api]);

	const updateShortcut = useCallback(
		(key: "quickAsk" | "autocomplete", accelerator: string) => {
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
		(key: "quickAsk" | "autocomplete") => {
			updateShortcut(key, DEFAULT_SHORTCUTS[key]);
		},
		[updateShortcut]
	);

	const handleGoogleLogin = () => {
		window.location.href = `${BACKEND_URL}/auth/google/authorize-redirect`;
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
		<div className="relative flex min-h-screen items-center justify-center bg-background p-4">
			<div className="pointer-events-none absolute inset-0 overflow-hidden">
				<div
					className="absolute -top-1/2 left-1/2 size-[800px] -translate-x-1/2 rounded-full opacity-[0.03]"
					style={{
						background:
							"radial-gradient(circle, hsl(var(--primary)) 0%, transparent 70%)",
					}}
				/>
			</div>

			<Card className="relative w-full max-w-md shadow-lg">
				<CardHeader className="items-center text-center pb-4">
					<Image
						src="/icon-128.svg"
						className="select-none dark:invert size-14 rounded-md mb-2"
						alt="SurfSense"
						width={56}
						height={56}
						priority
					/>
					<CardTitle className="text-xl">Welcome to SurfSense Desktop App</CardTitle>
					<CardDescription>
						Configure your shortcuts, then sign in to get started.
					</CardDescription>
				</CardHeader>

				<CardContent className="flex flex-col gap-6">
					{/* ---- Shortcuts Section (first) ---- */}
					{shortcutsLoaded ? (
						<div className="flex flex-col gap-3">
							<div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground mb-1">
								<Keyboard className="size-3" />
								Keyboard Shortcuts
							</div>
							<ShortcutRecorder
								value={shortcuts.quickAsk}
								onChange={(accel) => updateShortcut("quickAsk", accel)}
								onReset={() => resetShortcut("quickAsk")}
								defaultValue={DEFAULT_SHORTCUTS.quickAsk}
								label="Quick Ask"
								description="Copy selected text and ask AI about it"
								icon={Clipboard}
							/>
							<ShortcutRecorder
								value={shortcuts.autocomplete}
								onChange={(accel) => updateShortcut("autocomplete", accel)}
								onReset={() => resetShortcut("autocomplete")}
								defaultValue={DEFAULT_SHORTCUTS.autocomplete}
								label="Autocomplete"
								description="Get AI writing suggestions from a screenshot"
								icon={Sparkles}
							/>
							<p className="text-[11px] text-muted-foreground text-center">
								Click a shortcut and press a new key combination to change it.
							</p>
						</div>
					) : (
						<div className="flex justify-center py-4">
							<Spinner size="sm" />
						</div>
					)}

					{/* ---- Divider ---- */}
					<Separator />

					{/* ---- Auth Section (second) ---- */}
					{isGoogleAuth ? (
						<Button
							variant="outline"
							className="w-full gap-2 py-5"
							onClick={handleGoogleLogin}
						>
							<IconBrandGoogleFilled className="size-5" />
							Continue with Google
						</Button>
					) : (
						<form onSubmit={handleLocalLogin} className="flex flex-col gap-4">
							{loginError && (
								<div className="rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
									{loginError}
								</div>
							)}

							<div className="flex flex-col gap-2">
								<Label htmlFor="email">Email</Label>
								<Input
									id="email"
									type="email"
									placeholder="you@example.com"
									required
									value={email}
									onChange={(e) => setEmail(e.target.value)}
									disabled={isLoggingIn}
									autoFocus
								/>
							</div>

							<div className="flex flex-col gap-2">
								<Label htmlFor="password">Password</Label>
								<div className="relative">
									<Input
										id="password"
										type={showPassword ? "text" : "password"}
										placeholder="Enter your password"
										required
										value={password}
										onChange={(e) => setPassword(e.target.value)}
										disabled={isLoggingIn}
										className="pr-10"
									/>
									<button
										type="button"
										onClick={() => setShowPassword((v) => !v)}
										className="absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground hover:text-foreground"
										tabIndex={-1}
									>
										{showPassword ? (
											<EyeOff className="size-4" />
										) : (
											<Eye className="size-4" />
										)}
									</button>
								</div>
							</div>

							<Button type="submit" disabled={isLoggingIn} className="mt-1">
								{isLoggingIn ? (
									<>
										<Spinner size="sm" className="text-primary-foreground" />
										Signing in...
									</>
								) : (
									"Sign in"
								)}
							</Button>
						</form>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
