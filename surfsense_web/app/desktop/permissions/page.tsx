"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

type PermissionStatus = "authorized" | "denied" | "not determined" | "restricted" | "limited";

interface PermissionsStatus {
	accessibility: PermissionStatus;
	inputMonitoring: PermissionStatus;
}

const STEPS = [
	{
		id: "input-monitoring",
		title: "Input Monitoring",
		description: "Helps you write faster by enriching your text with suggestions from your knowledge base.",
		action: "requestInputMonitoring",
		field: "inputMonitoring" as const,
	},
	{
		id: "accessibility",
		title: "Accessibility",
		description: "Lets you accept suggestions seamlessly, right where you're typing.",
		action: "requestAccessibility",
		field: "accessibility" as const,
	},
];

function StatusBadge({ status }: { status: PermissionStatus }) {
	if (status === "authorized") {
		return (
			<span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-700 dark:text-green-400">
				<span className="h-2 w-2 rounded-full bg-green-500" />
				Granted
			</span>
		);
	}
	if (status === "denied") {
		return (
			<span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-700 dark:text-amber-400">
				<span className="h-2 w-2 rounded-full bg-amber-500" />
				Denied
			</span>
		);
	}
	return (
		<span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
			<span className="h-2 w-2 rounded-full bg-muted-foreground/40" />
			Pending
		</span>
	);
}

export default function DesktopPermissionsPage() {
	const router = useRouter();
	const [permissions, setPermissions] = useState<PermissionsStatus | null>(null);
	const [isElectron, setIsElectron] = useState(false);

	useEffect(() => {
		if (!window.electronAPI) return;
		setIsElectron(true);

		let interval: ReturnType<typeof setInterval> | null = null;

		const isResolved = (s: string) => s === "authorized" || s === "restricted";

		const poll = async () => {
			const status = await window.electronAPI!.getPermissionsStatus();
			setPermissions(status);

			if (isResolved(status.accessibility) && isResolved(status.inputMonitoring)) {
				if (interval) clearInterval(interval);
			}
		};

		poll();
		interval = setInterval(poll, 2000);
		return () => { if (interval) clearInterval(interval); };
	}, []);

	if (!isElectron) {
		return (
			<div className="h-screen flex items-center justify-center bg-background">
				<p className="text-muted-foreground">This page is only available in the desktop app.</p>
			</div>
		);
	}

	if (!permissions) {
		return (
			<div className="h-screen flex items-center justify-center bg-background">
				<Spinner size="lg" />
			</div>
		);
	}

	const allGranted = permissions.accessibility === "authorized" && permissions.inputMonitoring === "authorized";

	const handleRequest = async (action: string) => {
		if (action === "requestInputMonitoring") {
			await window.electronAPI!.requestInputMonitoring();
		} else if (action === "requestAccessibility") {
			await window.electronAPI!.requestAccessibility();
		}
	};

	const handleContinue = () => {
		if (allGranted) {
			window.electronAPI!.restartApp();
		}
	};

	const handleSkip = () => {
		router.push("/dashboard");
	};

	return (
		<div className="h-screen flex flex-col items-center p-4 bg-background dark:bg-neutral-900 select-none overflow-hidden">
			<div className="w-full max-w-lg flex flex-col min-h-0 h-full gap-6 py-8">
				{/* Header */}
				<div className="text-center space-y-3 shrink-0">
					<Logo className="w-12 h-12 mx-auto" />
					<div className="space-y-1">
						<h1 className="text-2xl font-semibold tracking-tight">System Permissions</h1>
						<p className="text-sm text-muted-foreground">
							SurfSense needs two macOS permissions to provide system-wide autocomplete.
						</p>
					</div>
				</div>

				{/* Steps */}
				<div className="rounded-xl border bg-background dark:bg-neutral-900 flex-1 min-h-0 overflow-y-auto px-6 py-6 space-y-6">
					{STEPS.map((step, index) => {
						const status = permissions[step.field];
						const isGranted = status === "authorized";

						return (
							<div
								key={step.id}
								className={`rounded-lg border p-4 transition-colors ${
									isGranted
										? "border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/20"
										: "border-border"
								}`}
							>
								<div className="flex items-start justify-between gap-3">
									<div className="flex items-start gap-3">
										<span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-medium text-primary">
											{isGranted ? "✓" : index + 1}
										</span>
										<div className="space-y-1">
											<h3 className="text-sm font-medium">{step.title}</h3>
											<p className="text-xs text-muted-foreground">{step.description}</p>
										</div>
									</div>
									<StatusBadge status={status} />
								</div>
								{!isGranted && (
									<div className="mt-3 pl-10 space-y-2">
										<Button
											size="sm"
											variant="outline"
											onClick={() => handleRequest(step.action)}
											className="text-xs"
										>
											Open System Settings
										</Button>
									{status === "denied" && (
										<p className="text-xs text-amber-700 dark:text-amber-400">
											Toggle SurfSense on in System Settings to continue.
										</p>
									)}
									<p className="text-xs text-muted-foreground">
										If SurfSense doesn&apos;t appear in the list, click <strong>+</strong> and select it from Applications.
									</p>
									</div>
								)}
							</div>
						);
					})}
				</div>

				{/* Footer */}
				<div className="text-center space-y-3 shrink-0">
					{allGranted ? (
						<>
							<Button onClick={handleContinue} className="text-sm h-9 min-w-[180px]">
								Restart &amp; Get Started
							</Button>
							<p className="text-xs text-muted-foreground">
								A restart is needed for permissions to take effect.
							</p>
						</>
					) : (
						<>
							<Button disabled className="text-sm h-9 min-w-[180px]">
								Grant permissions to continue
							</Button>
							<button
								onClick={handleSkip}
								className="block mx-auto text-xs text-muted-foreground hover:text-foreground transition-colors"
							>
								Skip for now
							</button>
						</>
					)}
				</div>
			</div>
		</div>
	);
}
