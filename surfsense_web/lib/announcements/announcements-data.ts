import type { Announcement } from "@/contracts/types/announcement.types";

/**
 * Static announcements data.
 *
 * To add a new announcement, append an entry to this array.
 * Set `isImportant: true` to trigger a toast notification for the user.
 *
 * This file can be replaced with an API call in the future.
 */
export const announcements: Announcement[] = [
	{
		id: "2026-02-12-announcement-syste",
		title: "Introducing Announcements",
		description:
			"Stay up to date with the latest SurfSense news! Important announcements will appear as toast notifications so you never miss critical updates. Visit the Announcements page from the sidebar to browse all past announcements.",
		category: "feature",
		date: "2026-02-12T00:00:00Z",
		isImportant: true,
		link: {
			label: "Learn more",
			url: "/changelog",
		},
	},
	// {
	// 	id: "2026-02-10-podcast-improvements",
	// 	title: "Podcast Generation Improvements",
	// 	description:
	// 		"We've improved podcast generation with faster processing, better audio quality, and support for longer documents. Try it out in any search space.",
	// 	category: "update",
	// 	date: "2026-02-10T00:00:00Z",
	// 	isImportant: false,
	// },
	// {
	// 	id: "2026-02-08-scheduled-maintenance",
	// 	title: "Scheduled Maintenance — Feb 15",
	// 	description:
	// 		"SurfSense will undergo scheduled maintenance on February 15, 2026 from 2:00 AM to 4:00 AM UTC. During this window, the service may be temporarily unavailable. We apologize for any inconvenience.",
	// 	category: "maintenance",
	// 	date: "2026-02-08T00:00:00Z",
	// 	isImportant: true,
	// },
	// {
	// 	id: "2026-02-05-new-connectors",
	// 	title: "New Connectors Available",
	// 	description:
	// 		"We've added support for new connectors including Linear, Jira, and Confluence. Connect your project management tools and start chatting with your data.",
	// 	category: "feature",
	// 	date: "2026-02-05T00:00:00Z",
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
	// 	isImportant: false,
	// },
];
