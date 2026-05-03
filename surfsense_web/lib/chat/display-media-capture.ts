/** `getDisplayMedia` → single PNG frame (data URL). */
function getImageCaptureCtor():
	| (new (
			track: MediaStreamTrack
	  ) => { grabFrame: () => Promise<ImageBitmap> })
	| undefined {
	if (typeof window === "undefined") return undefined;
	const IC = (
		window as unknown as {
			ImageCapture?: new (track: MediaStreamTrack) => { grabFrame: () => Promise<ImageBitmap> };
		}
	).ImageCapture;
	return typeof IC === "function" ? IC : undefined;
}

function stopAllTracks(stream: MediaStream): void {
	for (const t of stream.getTracks()) {
		t.stop();
	}
}

async function captureTrackToPngDataUrl(
	track: MediaStreamTrack,
	stream: MediaStream
): Promise<string | null> {
	const ImageCtor = getImageCaptureCtor();
	if (ImageCtor !== undefined) {
		try {
			const ic = new ImageCtor(track);
			const bitmap = await ic.grabFrame();
			try {
				const canvas = document.createElement("canvas");
				canvas.width = bitmap.width;
				canvas.height = bitmap.height;
				const ctx = canvas.getContext("2d");
				if (!ctx) {
					stopAllTracks(stream);
					return null;
				}
				ctx.drawImage(bitmap, 0, 0);
				stopAllTracks(stream);
				return canvas.toDataURL("image/png");
			} finally {
				if ("close" in bitmap && typeof bitmap.close === "function") {
					bitmap.close();
				}
			}
		} catch {
			/* fall through to <video> */
		}
	}

	const videoEl = document.createElement("video");
	videoEl.srcObject = stream;
	videoEl.muted = true;
	const haveCurrentData = 2;
	const dataReady = new Promise<void>((resolve) => {
		if (videoEl.readyState >= haveCurrentData) {
			resolve();
			return;
		}
		videoEl.addEventListener("loadeddata", () => resolve(), { once: true });
	});
	await videoEl.play();
	await Promise.race([
		dataReady,
		new Promise<void>((resolve) => {
			setTimeout(resolve, 500);
		}),
	]);
	const w = videoEl.videoWidth;
	const h = videoEl.videoHeight;
	if (!w || !h) {
		stopAllTracks(stream);
		return null;
	}
	const canvas = document.createElement("canvas");
	canvas.width = w;
	canvas.height = h;
	const ctx = canvas.getContext("2d");
	if (!ctx) {
		stopAllTracks(stream);
		return null;
	}
	ctx.drawImage(videoEl, 0, 0);
	stopAllTracks(stream);
	return canvas.toDataURL("image/png");
}

export async function captureDisplayToPngDataUrl(): Promise<string | null> {
	if (typeof navigator === "undefined" || !navigator.mediaDevices?.getDisplayMedia) {
		return null;
	}
	let stream: MediaStream | null = null;
	try {
		stream = await navigator.mediaDevices.getDisplayMedia({
			video: { frameRate: { ideal: 1, max: 5 } },
			audio: false,
			selfBrowserSurface: "exclude",
		} as Parameters<MediaDevices["getDisplayMedia"]>[0]);

		const track = stream.getVideoTracks()[0];
		if (!track) {
			stopAllTracks(stream);
			return null;
		}

		const dataUrl = await captureTrackToPngDataUrl(track, stream);
		stream = null;
		return dataUrl;
	} catch (e) {
		if (typeof process !== "undefined" && process.env?.NODE_ENV !== "production") {
			console.warn("[captureDisplayToPngDataUrl]", e);
		}
		if (stream) {
			stopAllTracks(stream);
		}
		return null;
	}
}
