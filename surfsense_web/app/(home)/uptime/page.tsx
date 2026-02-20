import Link from "next/link";
import { UPTIME_REPORT_URL } from "@/lib/env-config";

type UptimeStatus = "up" | "down";

interface LocationStat {
	uptime_status: UptimeStatus;
	response_time: number | null;
	last_check: number;
}

interface UptimeMonitor {
	id: string;
	name: string;
	type: string;
	target: string;
	last_check: number;
	uptime_status: UptimeStatus;
	monitor_status: string;
	uptime: number;
	locations?: Record<string, LocationStat>;
}

interface UptimeMonitorsApiResponse {
	monitors?: unknown[];
}

const HETRIXTOOLS_API_BASE = "https://api.hetrixtools.com/v3";

function formatTimestamp(timestamp: number) {
	if (!Number.isFinite(timestamp) || timestamp <= 0) return "n/a";
	return new Date(timestamp * 1000).toLocaleString();
}

function formatLocationName(location: string) {
	return location
		.replaceAll("_", " ")
		.split(" ")
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(" ");
}

function toNumber(value: unknown, fallback = 0) {
	if (typeof value === "number" && Number.isFinite(value)) return value;
	if (typeof value === "string") {
		const parsed = Number.parseFloat(value);
		if (Number.isFinite(parsed)) return parsed;
	}
	return fallback;
}

function normalizeUptimeStatus(value: unknown): UptimeStatus {
	return value === "down" ? "down" : "up";
}

function normalizeMonitor(rawMonitor: unknown): UptimeMonitor | null {
	if (!rawMonitor || typeof rawMonitor !== "object") return null;

	const monitor = rawMonitor as Record<string, unknown>;
	const rawLocations =
		monitor.locations && typeof monitor.locations === "object"
			? (monitor.locations as Record<string, unknown>)
			: {};

	const locations: Record<string, LocationStat> = {};
	for (const [locationName, rawLocation] of Object.entries(rawLocations)) {
		if (!rawLocation || typeof rawLocation !== "object") continue;
		const location = rawLocation as Record<string, unknown>;
		locations[locationName] = {
			uptime_status: normalizeUptimeStatus(location.uptime_status),
			response_time:
				location.response_time === null ? null : toNumber(location.response_time, 0),
			last_check: toNumber(location.last_check, 0),
		};
	}

	return {
		id: String(monitor.id ?? ""),
		name: String(monitor.name ?? "Unnamed monitor"),
		type: String(monitor.type ?? ""),
		target: String(monitor.target ?? ""),
		last_check: toNumber(monitor.last_check, 0),
		uptime_status: normalizeUptimeStatus(monitor.uptime_status),
		monitor_status: String(monitor.monitor_status ?? "unknown"),
		uptime: toNumber(monitor.uptime, 0),
		locations,
	};
}

async function fetchUptimeMonitors(): Promise<{
	monitors: UptimeMonitor[];
	error?: string;
}> {
	const apiKey = process.env.HETRIXTOOLS_API_KEY;
	const monitorId = process.env.HETRIXTOOLS_MONITOR_ID;

	if (!apiKey) {
		return {
			monitors: [],
			error:
				"Missing HETRIXTOOLS_API_KEY. Add it to your server environment to enable custom uptime UI.",
		};
	}

	const query = monitorId
		? `id=${encodeURIComponent(monitorId)}`
		: "per_page=20&page=1&order_by=last_check&order=desc";

	try {
		const response = await fetch(`${HETRIXTOOLS_API_BASE}/uptime-monitors?${query}`, {
			method: "GET",
			headers: {
				Authorization: `Bearer ${apiKey}`,
			},
			next: { revalidate: 60 },
		});

		if (!response.ok) {
			return {
				monitors: [],
				error: `HetrixTools API request failed (${response.status}).`,
			};
		}

		const data = (await response.json()) as UptimeMonitorsApiResponse;
		const monitors = (data.monitors ?? [])
			.map((monitor) => normalizeMonitor(monitor))
			.filter((monitor): monitor is UptimeMonitor => monitor !== null);
		return { monitors };
	} catch {
		return {
			monitors: [],
			error: "Could not reach HetrixTools API from the server.",
		};
	}
}

export default async function UptimePage() {
	const { monitors, error } = await fetchUptimeMonitors();

	return (
		<section className="min-h-screen pt-24 pb-16">
			<div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 sm:px-6 lg:px-8">
				<div className="rounded-2xl border border-neutral-200/70 bg-white/80 p-6 shadow-sm backdrop-blur-sm dark:border-neutral-800 dark:bg-neutral-950/70">
					<p className="text-sm font-medium uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
						System Status
					</p>
					<h1 className="mt-2 text-3xl font-bold tracking-tight text-neutral-900 dark:text-neutral-100">
						SurfSense uptime dashboard
					</h1>
					<div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
						<Link
							href={UPTIME_REPORT_URL}
							target="_blank"
							rel="noopener noreferrer"
							className="inline-flex items-center rounded-full border border-neutral-300 px-4 py-2 font-medium text-neutral-700 transition-colors hover:bg-neutral-100 dark:border-neutral-700 dark:text-neutral-200 dark:hover:bg-neutral-900"
						>
							Open original report
						</Link>
						<span className="text-xs text-neutral-500 dark:text-neutral-400">
							Source: HetrixTools v3 API (`/uptime-monitors`).
						</span>
					</div>
				</div>

				{error ? (
					<div className="rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-900 dark:border-amber-700/70 dark:bg-amber-950/30 dark:text-amber-200">
						<p className="font-semibold">Unable to load custom uptime data</p>
						<p className="mt-1 text-sm">{error}</p>
					</div>
				) : monitors.length === 0 ? (
					<div className="rounded-2xl border border-neutral-200/70 bg-white p-5 text-neutral-700 shadow-sm dark:border-neutral-800 dark:bg-neutral-950 dark:text-neutral-300">
						No uptime monitors returned by HetrixTools API.
					</div>
				) : (
					<div className="grid gap-4">
						{monitors.map((monitor) => {
							const locations = Object.entries(monitor.locations ?? {});
							const isUp = monitor.uptime_status === "up";

							return (
								<div
									key={monitor.id}
									className="rounded-2xl border border-neutral-200/70 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-950"
								>
									<div className="flex flex-wrap items-start justify-between gap-4">
										<div>
											<p className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
												{monitor.name}
											</p>
											<p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
												{monitor.target || "No target shown"}
											</p>
										</div>
										<div
											className={`rounded-full px-3 py-1 text-xs font-semibold ${
												isUp
													? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
													: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300"
											}`}
										>
											{isUp ? "Operational" : "Outage"}
										</div>
									</div>

									<div className="mt-4 grid gap-3 sm:grid-cols-3">
										<div className="rounded-xl border border-neutral-200/70 p-3 dark:border-neutral-800">
											<p className="text-xs text-neutral-500 dark:text-neutral-400">Uptime</p>
											<p className="mt-1 text-lg font-semibold text-neutral-900 dark:text-neutral-100">
												{monitor.uptime.toFixed(4)}%
											</p>
										</div>
										<div className="rounded-xl border border-neutral-200/70 p-3 dark:border-neutral-800">
											<p className="text-xs text-neutral-500 dark:text-neutral-400">
												Last check
											</p>
											<p className="mt-1 text-sm font-medium text-neutral-900 dark:text-neutral-100">
												{formatTimestamp(monitor.last_check)}
											</p>
										</div>
										<div className="rounded-xl border border-neutral-200/70 p-3 dark:border-neutral-800">
											<p className="text-xs text-neutral-500 dark:text-neutral-400">
												Monitor status
											</p>
											<p className="mt-1 text-sm font-medium capitalize text-neutral-900 dark:text-neutral-100">
												{monitor.monitor_status.replaceAll("_", " ")}
											</p>
										</div>
									</div>

									{locations.length > 0 && (
										<div className="mt-4">
											<p className="text-xs font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
												Locations
											</p>
											<div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
												{locations.map(([locationName, locationData]) => (
													<div
														key={`${monitor.id}-${locationName}`}
														className="rounded-xl border border-neutral-200/70 p-3 dark:border-neutral-800"
													>
														<p className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
															{formatLocationName(locationName)}
														</p>
														<p className="mt-1 text-xs text-neutral-600 dark:text-neutral-400">
															{locationData.uptime_status === "up" ? "Up" : "Down"} ·{" "}
															{locationData.response_time ?? "n/a"} ms
														</p>
													</div>
												))}
											</div>
										</div>
									)}
								</div>
							);
						})}
					</div>
				)}
			</div>
		</section>
	);
}
