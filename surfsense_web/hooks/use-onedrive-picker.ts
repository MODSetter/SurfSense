"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { authenticatedFetch } from "@/lib/auth-utils";

export interface OneDrivePickerItem {
	id: string;
	name: string;
	isFolder: boolean;
	driveId?: string;
}

export interface OneDrivePickerResult {
	folders: OneDrivePickerItem[];
	files: OneDrivePickerItem[];
}

interface UseOneDrivePickerOptions {
	connectorId: number;
	onPicked: (result: OneDrivePickerResult) => void;
}

export const ONEDRIVE_PICKER_OPEN_EVENT = "onedrive-picker-open";
export const ONEDRIVE_PICKER_CLOSE_EVENT = "onedrive-picker-close";

async function fetchPickerToken(
	connectorId: number,
	resource?: string,
): Promise<{ access_token: string; base_url: string }> {
	const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
	const params = new URLSearchParams();
	if (resource) params.set("resource", resource);
	const qs = params.toString();
	const url = `${backendUrl}/api/v1/connectors/${connectorId}/onedrive/picker-token${qs ? `?${qs}` : ""}`;
	const response = await authenticatedFetch(url);
	if (!response.ok) {
		const data = await response.json().catch(() => ({}));
		throw new Error(data.detail || `Failed to get picker token (${response.status})`);
	}
	return response.json();
}

export function useOneDrivePicker({ connectorId, onPicked }: UseOneDrivePickerOptions) {
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const onPickedRef = useRef(onPicked);
	onPickedRef.current = onPicked;
	const openingRef = useRef(false);
	const winRef = useRef<Window | null>(null);
	const portRef = useRef<MessagePort | null>(null);
	const messageHandlerRef = useRef<((e: MessageEvent) => void) | null>(null);
	const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

	const closePicker = useCallback(() => {
		window.dispatchEvent(new Event(ONEDRIVE_PICKER_CLOSE_EVENT));
		if (pollRef.current) {
			clearInterval(pollRef.current);
			pollRef.current = null;
		}
		if (messageHandlerRef.current) {
			window.removeEventListener("message", messageHandlerRef.current);
			messageHandlerRef.current = null;
		}
		if (winRef.current && !winRef.current.closed) {
			winRef.current.close();
		}
		winRef.current = null;
		portRef.current = null;
		openingRef.current = false;
	}, []);

	useEffect(() => {
		const onEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape" && winRef.current) {
				closePicker();
			}
		};
		window.addEventListener("keydown", onEscape);
		return () => {
			window.removeEventListener("keydown", onEscape);
			closePicker();
		};
	}, [closePicker]);

	const openPicker = useCallback(async () => {
		if (openingRef.current) return;
		openingRef.current = true;
		setLoading(true);
		setError(null);

		try {
			const { access_token, base_url } = await fetchPickerToken(connectorId);

			const win = window.open("", "OneDrivePicker", "width=1080,height=680");
			if (!win) {
				throw new Error("Popup blocked. Please allow popups for this site.");
			}
			winRef.current = win;

			const channelId = crypto.randomUUID();

			const pickerConfig = {
				sdk: "8.0",
				entry: { oneDrive: { files: {} } },
				authentication: {},
				messaging: {
					origin: window.location.origin,
					channelId,
				},
				selection: { mode: "multiple" },
				typesAndSources: {
					mode: "all" as const,
					pivots: { oneDrive: true, recent: true },
				},
			};

			const qs = new URLSearchParams({
				filePicker: JSON.stringify(pickerConfig),
				locale: navigator.language || "en-us",
			});
			const pickerUrl = `${base_url}/_layouts/15/FilePicker.aspx?${qs}`;

			const form = win.document.createElement("form");
			form.setAttribute("action", pickerUrl);
			form.setAttribute("method", "POST");
			const input = win.document.createElement("input");
			input.setAttribute("type", "hidden");
			input.setAttribute("name", "access_token");
			input.setAttribute("value", access_token);
			form.appendChild(input);
			win.document.body.append(form);
			form.submit();

			const handleMessage = (event: MessageEvent) => {
				if (event.source !== win) return;
				const msg = event.data;
				if (msg?.type !== "initialize" || msg.channelId !== channelId) return;

				const port = event.ports[0];
				portRef.current = port;

				port.addEventListener("message", async (portEvent: MessageEvent) => {
					const payload = portEvent.data;
					if (payload.type !== "command") return;

					port.postMessage({ type: "acknowledge", id: payload.id });

					const cmd = payload.data;
					switch (cmd.command) {
						case "authenticate": {
							try {
								const result = await fetchPickerToken(connectorId, cmd.resource);
								port.postMessage({
									type: "result",
									id: payload.id,
									data: { result: "token", token: result.access_token },
								});
							} catch (err) {
								port.postMessage({
									type: "result",
									id: payload.id,
									data: {
										result: "error",
										error: {
											code: "unableToObtainToken",
											message: err instanceof Error ? err.message : "Token error",
										},
									},
								});
							}
							break;
						}
						case "pick": {
							const items: Record<string, unknown>[] = cmd.items || [];
							const folders: OneDrivePickerItem[] = [];
							const files: OneDrivePickerItem[] = [];

							for (const item of items) {
								const isFolder =
									item.folder != null ||
									(typeof item["@odata.type"] === "string" &&
										(item["@odata.type"] as string).includes("folder"));
								const parentRef = item.parentReference as
									| { driveId?: string }
									| undefined;
								const pickerItem: OneDrivePickerItem = {
									id: item.id as string,
									name: (item.name as string) || "Untitled",
									isFolder,
									driveId: parentRef?.driveId,
								};
								if (isFolder) {
									folders.push(pickerItem);
								} else {
									files.push(pickerItem);
								}
							}

							onPickedRef.current({ folders, files });
							port.postMessage({
								type: "result",
								id: payload.id,
								data: { result: "success" },
							});
							closePicker();
							break;
						}
						case "close": {
							closePicker();
							break;
						}
						default: {
							port.postMessage({
								type: "result",
								id: payload.id,
								data: {
									result: "error",
									error: { code: "unsupportedCommand", message: cmd.command },
								},
							});
							break;
						}
					}
				});

				port.start();
				port.postMessage({ type: "activate" });
			};

			messageHandlerRef.current = handleMessage;
			window.addEventListener("message", handleMessage);

			pollRef.current = setInterval(() => {
				if (win.closed) {
					closePicker();
				}
			}, 500);

			window.dispatchEvent(new Event(ONEDRIVE_PICKER_OPEN_EVENT));
		} catch (err) {
			openingRef.current = false;
			const msg = err instanceof Error ? err.message : "Failed to open OneDrive Picker";
			setError(msg);
			toast.error("OneDrive Picker failed", { description: msg });
			console.error("OneDrive Picker error:", err);
			window.dispatchEvent(new Event(ONEDRIVE_PICKER_CLOSE_EVENT));
		} finally {
			setLoading(false);
		}
	}, [connectorId, closePicker]);

	return { openPicker, closePicker, loading, error };
}
