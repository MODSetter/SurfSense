import { Storage } from "@plasmohq/storage";
import { getRenderedHtml, initQueues, initWebHistory } from "~utils/commons";
import type { WebHistory } from "~utils/interfaces";

// Configure side panel to open when extension icon is clicked
chrome.sidePanel
	.setPanelBehavior({ openPanelOnActionClick: true })
	.catch((error) => console.error("Failed to set side panel behavior:", error));

// ============================================
// Context Menu Setup (Epic 4.3)
// ============================================

// Create context menus on extension install
chrome.runtime.onInstalled.addListener(() => {
	// Parent menu for SurfSense
	chrome.contextMenus.create({
		id: "surfsense-parent",
		title: "🧠 SurfSense",
		contexts: ["selection", "page", "link"],
	});

	// Analyze Token - for selected text (token address or symbol)
	chrome.contextMenus.create({
		id: "analyze-token",
		parentId: "surfsense-parent",
		title: "🔍 Analyze Token",
		contexts: ["selection"],
	});

	// Check Safety - for selected text
	chrome.contextMenus.create({
		id: "check-safety",
		parentId: "surfsense-parent",
		title: "🛡️ Check Safety",
		contexts: ["selection"],
	});

	// Add to Watchlist - for selected text
	chrome.contextMenus.create({
		id: "add-watchlist",
		parentId: "surfsense-parent",
		title: "⭐ Add to Watchlist",
		contexts: ["selection"],
	});

	// Separator
	chrome.contextMenus.create({
		id: "separator-1",
		parentId: "surfsense-parent",
		type: "separator",
		contexts: ["selection", "page", "link"],
	});

	// Copy Address - for selected text
	chrome.contextMenus.create({
		id: "copy-address",
		parentId: "surfsense-parent",
		title: "📋 Copy Address",
		contexts: ["selection"],
	});

	// View on Explorer - for selected text
	chrome.contextMenus.create({
		id: "view-explorer",
		parentId: "surfsense-parent",
		title: "🔗 View on Explorer",
		contexts: ["selection"],
	});

	// Separator
	chrome.contextMenus.create({
		id: "separator-2",
		parentId: "surfsense-parent",
		type: "separator",
		contexts: ["selection", "page", "link"],
	});

	// Capture Page - for page context
	chrome.contextMenus.create({
		id: "capture-page",
		parentId: "surfsense-parent",
		title: "📸 Capture This Page",
		contexts: ["page"],
	});

	// Ask AI about this page
	chrome.contextMenus.create({
		id: "ask-ai-page",
		parentId: "surfsense-parent",
		title: "💬 Ask AI About This Page",
		contexts: ["page"],
	});
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
	const selectedText = info.selectionText?.trim() || "";
	const storage = new Storage({ area: "local" });

	// Store the action for sidepanel to pick up
	const contextAction = {
		action: info.menuItemId,
		text: selectedText,
		pageUrl: info.pageUrl,
		linkUrl: info.linkUrl,
		timestamp: Date.now(),
	};

	await storage.set("pendingContextAction", contextAction);

	// Open sidepanel to handle the action
	if (tab?.id) {
		try {
			await chrome.sidePanel.open({ tabId: tab.id });
		} catch (error) {
			console.error("Failed to open side panel:", error);
		}
	}
});

// ============================================
// Message Listeners
// ============================================

// Listen for messages from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
	if (message.type === "OPEN_SIDEPANEL") {
		// Open sidepanel for the current tab
		if (sender.tab?.id) {
			chrome.sidePanel.open({ tabId: sender.tab.id })
				.catch((error) => console.error("Failed to open side panel:", error));
		}
	}

	// Handle context action from sidepanel
	if (message.type === "GET_CONTEXT_ACTION") {
		const storage = new Storage({ area: "local" });
		storage.get("pendingContextAction").then((action) => {
			sendResponse(action);
			// Clear the pending action
			storage.remove("pendingContextAction");
		});
		return true; // Keep channel open for async response
	}
});

// ============================================
// Keyboard Shortcuts (Epic 4.5)
// ============================================

chrome.commands.onCommand.addListener(async (command) => {
	const storage = new Storage({ area: "local" });
	const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

	if (!tab?.id) return;

	// Store the keyboard command for sidepanel to pick up
	const keyboardAction = {
		action: command,
		timestamp: Date.now(),
	};

	await storage.set("pendingKeyboardAction", keyboardAction);

	// Open sidepanel for all commands
	try {
		await chrome.sidePanel.open({ tabId: tab.id });
	} catch (error) {
		console.error("Failed to open side panel:", error);
	}
});

chrome.tabs.onCreated.addListener(async (tab: any) => {
	try {
		await initWebHistory(tab.id);
		await initQueues(tab.id);
	} catch (error) {
		console.log(error);
	}
});

chrome.tabs.onUpdated.addListener(async (tabId: number, changeInfo: any, tab: any) => {
	if (changeInfo.status === "complete" && tab.url) {
		const storage = new Storage({ area: "local" });
		await initWebHistory(tab.id);
		await initQueues(tab.id);

		const result = await chrome.scripting.executeScript({
			// @ts-ignore
			target: { tabId: tab.id },
			// @ts-ignore
			func: getRenderedHtml,
		});

		const toPushInTabHistory: any = result[0].result; // const { renderedHtml, title, url, entryTime } = result[0].result;

		const urlQueueListObj: any = await storage.get("urlQueueList");
		const timeQueueListObj: any = await storage.get("timeQueueList");

		urlQueueListObj.urlQueueList
			.find((data: WebHistory) => data.tabsessionId === tabId)
			.urlQueue.push(toPushInTabHistory.url);
		timeQueueListObj.timeQueueList
			.find((data: WebHistory) => data.tabsessionId === tabId)
			.timeQueue.push(toPushInTabHistory.entryTime);

		await storage.set("urlQueueList", {
			urlQueueList: urlQueueListObj.urlQueueList,
		});
		await storage.set("timeQueueList", {
			timeQueueList: timeQueueListObj.timeQueueList,
		});
	}
});

chrome.tabs.onRemoved.addListener(async (tabId: number, removeInfo: object) => {
	const storage = new Storage({ area: "local" });
	const urlQueueListObj: any = await storage.get("urlQueueList");
	const timeQueueListObj: any = await storage.get("timeQueueList");
	if (urlQueueListObj.urlQueueList && timeQueueListObj.timeQueueList) {
		const urlQueueListToSave = urlQueueListObj.urlQueueList.map((element: WebHistory) => {
			if (element.tabsessionId !== tabId) {
				return element;
			}
		});
		const timeQueueListSave = timeQueueListObj.timeQueueList.map((element: WebHistory) => {
			if (element.tabsessionId !== tabId) {
				return element;
			}
		});
		await storage.set("urlQueueList", {
			urlQueueList: urlQueueListToSave.filter((item: any) => item),
		});
		await storage.set("timeQueueList", {
			timeQueueList: timeQueueListSave.filter((item: any) => item),
		});
	}
});
