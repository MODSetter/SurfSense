/**
 * Turns a walkthrough's raw recording into the video the site plays: trimmed
 * to the walkthrough, without the frames where the overlay was hidden for a
 * screenshot, and with long waits on the app or a model played faster.
 */

import { runFfmpeg } from "./run-ffmpeg.mjs";

// A wait longer than this plays in about this long; anything shorter plays as it happened.
const LONGEST_WAIT_SECONDS = 2.5;
// The overlay is hidden a little before the screenshot starts and shown a little after.
const SHOT_PAD_SECONDS = 0.15;

/** Splits [start, end] into segments: kept as is, sped up, or cut. */
export function videoSegments(marks) {
	const start = marks.find((mark) => mark.kind === "start")?.at ?? 0;
	const end = marks.findLast((mark) => mark.kind === "end")?.at;
	if (end === undefined) throw new Error("the walkthrough never ended");
	const changes = marks
		.filter((mark) => mark.kind === "wait" || mark.kind === "shot")
		.map((mark) =>
			mark.kind === "shot"
				? { from: mark.from - SHOT_PAD_SECONDS, to: mark.to + SHOT_PAD_SECONDS, speed: null }
				: {
						from: mark.from,
						to: mark.to,
						speed: Math.max(1, (mark.to - mark.from) / LONGEST_WAIT_SECONDS),
					}
		)
		.sort((a, b) => a.from - b.from);

	const segments = [];
	let cursor = start;
	for (const change of changes) {
		const from = Math.max(change.from, cursor);
		const to = Math.min(change.to, end);
		if (to <= from) continue;
		if (from > cursor) segments.push({ from: cursor, to: from, speed: 1 });
		if (change.speed !== null) segments.push({ from, to, speed: change.speed });
		cursor = to;
	}
	if (end > cursor) segments.push({ from: cursor, to: end, speed: 1 });
	return segments.filter((segment) => segment.to - segment.from >= 0.04);
}

export async function editVideo({ raw, marks, mp4 }) {
	const segments = videoSegments(marks);
	const parts = segments.map(
		(segment, index) =>
			`[0:v]trim=start=${segment.from.toFixed(3)}:end=${segment.to.toFixed(3)},setpts=(PTS-STARTPTS)/${segment.speed.toFixed(3)}[v${index}]`
	);
	const joined = `${segments.map((_, index) => `[v${index}]`).join("")}concat=n=${segments.length}:v=1:a=0,fps=25[out]`;
	await runFfmpeg([
		"-i",
		raw,
		"-filter_complex",
		`${parts.join(";")};${joined}`,
		"-map",
		"[out]",
		"-c:v",
		"libx264",
		"-preset",
		"slow",
		"-crf",
		"23",
		"-pix_fmt",
		"yuv420p",
		"-movflags",
		"+faststart",
		mp4,
	]);
	return segments.reduce(
		(total, segment) => total + (segment.to - segment.from) / segment.speed,
		0
	);
}
