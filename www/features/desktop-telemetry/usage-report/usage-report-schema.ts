import { z } from "zod";
import { APP_VERSION, DESKTOP_PLATFORMS, isDesktopOs } from "../desktop-dimensions";

const ISO_WEEK = /^20[0-9]{2}-W(0[1-9]|[1-4][0-9]|5[0-3])$/;
const TURNS = z.enum(["0", "1-9", "10-49", "50+", "unknown"]);

/**
 * Usage report schema 1, revision 1.1 (docs/contracts/05-desktop-telemetry.md,
 * part B). Strict all the way down: every value is an enum, flag or fixed
 * format, so an unknown key or value is refused rather than stored. Which
 * report carries `hardware` and `week` is the app's rule, not the route's.
 */
export const usageReportSchema = z.strictObject({
	schema: z.literal(1),
	app_version: z.string().regex(APP_VERSION),
	platform: z.enum(DESKTOP_PLATFORMS),
	os: z.string().refine(isDesktopOs),
	ui_language: z.enum(["en", "ja", "de", "other"]),
	install_week: z.string().regex(ISO_WEEK),
	// Absent from 2.2.4, whose every report is a daily one.
	trigger: z.enum(["daily", "setup"]).optional(),
	active: z.strictObject({
		first: z.boolean(),
		week: z.boolean(),
		month: z.boolean(),
	}),
	hardware: z
		.strictObject({
			ram_gb: z.enum(["<8", "8-15", "16-31", "32-63", "64+"]),
			gpu: z.enum(["nvidia", "amd", "intel", "apple", "none", "unknown"]),
			vram_gb: z.enum(["0", "<4", "4-7", "8-11", "12-23", "24+", "unknown"]),
			gpu_runtime: z.enum(["reachable", "unreachable", "none", "unknown"]).optional(),
		})
		.nullable(),
	week: z
		.strictObject({
			chat_turns: TURNS,
			agent_turns: TURNS,
			model_source: z.enum(["none", "local", "remote", "both", "unknown"]),
			sources: z.enum(["0", "1-9", "10-99", "100-999", "1000+", "unknown"]),
			studio_outputs: z.enum(["0", "1-4", "5+", "unknown"]),
			plugin_calls: z.enum(["0", "1-9", "10+", "unknown"]),
			onboarding: z.enum([
				"not_started",
				"model_chosen",
				"model_ready",
				"first_source",
				"first_answer",
				"unknown",
			]),
		})
		.nullable(),
});

export type UsageReport = z.infer<typeof usageReportSchema>;
