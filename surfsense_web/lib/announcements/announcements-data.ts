import type { Announcement } from "@/contracts/types/announcement.types";

/**
 * Static announcements data.
 *
 * To add a new announcement, append an entry to this array.
 * Each announcement requires `startTime` and `endTime` (ISO datetime strings)
 * to define its visibility window, and `audience` to control who sees it.
 * Current possible audiences are "all", "users", and "web_visitors".
 * Current possible categories are "feature", "update", "maintenance", and "info".
 * Set `isImportant: true` to trigger a toast notification for the user.
 *
 * This file can be replaced with an API call in the future.
 */
export const announcements: Announcement[] = [
	{
		id: "announcement-1",
		title: "Introducing Announcements",
		description: "All major announcements will be posted here.",
		category: "feature",
		date: "2026-02-17T00:00:00Z",
		startTime: "2026-02-17T00:00:00Z",
		endTime: "2026-02-20T00:00:00Z",
		audience: "all",
		isImportant: false,
	},
	{
		id: "announcement-6",
		title: "Past Test Announcement",
		description: "This should be seen by nobody, because it's in the past.",
		category: "maintenance",
		date: "2026-02-17T00:00:00Z",
		startTime: "2026-02-15T23:23:00Z",
		endTime: "2026-02-16T00:00:00Z",
		audience: "users",
		isImportant: true,
	},
	// {
	// 	id: "2026-02-10-podcast-improvements",
	// 	title: "Podcast Generation Improvements",
	// 	description:
	// 		"We've improved podcast generation with faster processing, better audio quality, and support for longer documents. Try it out in any search space.",
	// 	category: "update",
	// 	date: "2026-02-10T00:00:00Z",
	// 	startTime: "2026-02-10T00:00:00Z",
	// 	endTime: "2026-03-10T00:00:00Z",
	// 	audience: "all",
	// 	isImportant: false,
	// },
	// {
	// 	id: "2026-02-08-scheduled-maintenance",
	// 	title: "Scheduled Maintenance — Feb 15",
	// 	description:
	// 		"SurfSense will undergo scheduled maintenance on February 15, 2026 from 2:00 AM to 4:00 AM UTC. During this window, the service may be temporarily unavailable. We apologize for any inconvenience.",
	// 	category: "maintenance",
	// 	date: "2026-02-08T00:00:00Z",
	// 	startTime: "2026-02-08T00:00:00Z",
	// 	endTime: "2026-02-16T00:00:00Z",
	// 	audience: "all",
	// 	isImportant: true,
	// },
	// {
	// 	id: "2026-02-05-new-connectors",
	// 	title: "New Connectors Available",
	// 	description:
	// 		"We've added support for new connectors including Linear, Jira, and Confluence. Connect your project management tools and start chatting with your data.",
	// 	category: "feature",
	// 	date: "2026-02-05T00:00:00Z",
	// 	startTime: "2026-02-05T00:00:00Z",
	// 	endTime: "2026-03-05T00:00:00Z",
	// 	audience: "users",
	// 	isImportant: false,
	// 	link: {
	// 		label: "View connectors",
	// 		url: "#connectors",
	// 	},
	// },
	// {
	// 	id: "2026-01-28-team-collaboration",
	// 	title: "Enhanced Team Collaboration",
	// 	description:
	// 		"Shared search spaces now support real-time mentions, comment threads, and role-based access control. Invite your team and collaborate more effectively.",
	// 	category: "feature",
	// 	date: "2026-01-28T00:00:00Z",
	// 	startTime: "2026-01-28T00:00:00Z",
	// 	endTime: "2026-02-28T00:00:00Z",
	// 	audience: "users",
	// 	isImportant: false,
	// },
];
