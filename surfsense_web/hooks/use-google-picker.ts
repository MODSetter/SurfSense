"use client";

import { useCallback, useRef, useState } from "react";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";

export interface PickerItem {
	id: string;
	name: string;
	mimeType: string;
}

export interface PickerResult {
	folders: PickerItem[];
	files: PickerItem[];
}

interface UseGooglePickerOptions {
	connectorId: number;
	onPicked: (result: PickerResult) => void;
}

const PICKER_SCRIPT_URL = "https://apis.google.com/js/api.js";
const FOLDER_MIME = "application/vnd.google-apps.folder";

let scriptLoadPromise: Promise<void> | null = null;
let pickerApiPromise: Promise<void> | null = null;

function loadPickerScript(): Promise<void> {
	if (scriptLoadPromise) return scriptLoadPromise;
	if (typeof window !== "undefined" && window.gapi) {
		scriptLoadPromise = Promise.resolve();
		return scriptLoadPromise;
	}

	scriptLoadPromise = new Promise<void>((resolve, reject) => {
		const script = document.createElement("script");
		script.src = PICKER_SCRIPT_URL;
		script.async = true;
		script.defer = true;
		script.onload = () => resolve();
		script.onerror = () => {
			scriptLoadPromise = null;
			reject(new Error("Failed to load Google Picker script"));
		};
		document.head.appendChild(script);
	});
	return scriptLoadPromise;
}

function loadPickerApi(): Promise<void> {
	if (pickerApiPromise) return pickerApiPromise;

	pickerApiPromise = new Promise<void>((resolve, reject) => {
		gapi.load("picker", {
			callback: () => resolve(),
			onerror: () => {
				pickerApiPromise = null;
				reject(new Error("Failed to load Google Picker API"));
			},
		});
	});
	return pickerApiPromise;
}

export function useGooglePicker({ connectorId, onPicked }: UseGooglePickerOptions) {
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const onPickedRef = useRef(onPicked);
	onPickedRef.current = onPicked;
	const openingRef = useRef(false);

	const openPicker = useCallback(async () => {
		if (openingRef.current) return;
		openingRef.current = true;
		setLoading(true);
		setError(null);

		try {
			const [tokenData] = await Promise.all([
				connectorsApiService.getDrivePickerToken(connectorId),
				loadPickerScript().then(() => loadPickerApi()),
			]);

			const { access_token, picker_api_key } = tokenData;

			const docsView = new google.picker.DocsView(google.picker.ViewId.DOCS)
				.setIncludeFolders(true)
				.setSelectFolderEnabled(true);

			let pickerInstance: google.picker.Picker | null = null;

			const picker = new google.picker.PickerBuilder()
				.addView(docsView)
				.enableFeature(google.picker.Feature.MULTISELECT_ENABLED)
				.setOAuthToken(access_token)
				.setDeveloperKey(picker_api_key)
				.setOrigin(window.location.protocol + "//" + window.location.host)
				.setTitle("Select files and folders to index")
				.setCallback((data: google.picker.ResponseObject) => {
					const action = data[google.picker.Response.ACTION];

					if (action === google.picker.Action.PICKED) {
						const docs = data[google.picker.Response.DOCUMENTS];
						if (docs) {
							const folders: PickerItem[] = [];
							const files: PickerItem[] = [];

							for (const doc of docs) {
								const mimeType = doc[google.picker.Document.MIME_TYPE] ?? "";
								const item: PickerItem = {
									id: doc[google.picker.Document.ID],
									name: doc[google.picker.Document.NAME] ?? "Untitled",
									mimeType,
								};
								if (mimeType === FOLDER_MIME) {
									folders.push(item);
								} else {
									files.push(item);
								}
							}

							onPickedRef.current({ folders, files });
						}
					}

					if (
						action === google.picker.Action.PICKED ||
						action === google.picker.Action.CANCEL ||
						action === google.picker.Action.ERROR
					) {
						pickerInstance?.dispose();
						pickerInstance = null;
						openingRef.current = false;
					}
				})
				.build();

			pickerInstance = picker;
			picker.setVisible(true);
		} catch (err) {
			openingRef.current = false;
			const msg = err instanceof Error ? err.message : "Failed to open Google Picker";
			setError(msg);
			console.error("Google Picker error:", err);
		} finally {
			setLoading(false);
		}
	}, [connectorId]);

	return { openPicker, loading, error };
}
