import assert from "node:assert/strict";
import test from "node:test";
import { Video } from "lucide-react";
import { Mp4VideoPlayer } from "@/components/tool-ui/video-presentation/mp4-player";
import {
	ARTIFACT_GROUP_ORDER,
	getArtifactFormatMeta,
} from "@/features/artifacts/lib/artifact-format-catalog";
import { MIME_VIEWERS } from "@/features/artifacts/rendering/mime-viewer-registry";

test("Mp4VideoPlayer uses lazy native video playback", () => {
	const player = Mp4VideoPlayer({ src: "/video.mp4", poster: "/poster.jpg" });

	assert.equal(player.type, "video");
	assert.equal(player.props.controls, true);
	assert.equal(player.props.playsInline, true);
	assert.equal(player.props.preload, "none");
	assert.equal(player.props.src, "/video.mp4");
	assert.equal(player.props.poster, "/poster.jpg");
});

test("video artifacts have a dedicated Video identity and group", () => {
	const meta = getArtifactFormatMeta("video");

	assert.equal(meta.label, "Video");
	assert.equal(meta.detailLabel, "MP4");
	assert.equal(meta.groupKey, "videos");
	assert.equal(meta.groupLabel, "Videos");
	assert.equal(meta.viewingMode, "inline-media");
	assert.equal(meta.icon, Video);
	assert.equal(ARTIFACT_GROUP_ORDER.includes("videos"), true);
});

test("artifact viewer registry supports MP4 files", () => {
	assert.ok(MIME_VIEWERS["video/mp4"]);
});
