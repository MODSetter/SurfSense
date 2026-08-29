import {execFile} from "node:child_process";
import {existsSync} from "node:fs";
import {
  access,
  readFile,
  mkdir,
  mkdtemp,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import {tmpdir} from "node:os";
import path from "node:path";
import {fileURLToPath, pathToFileURL} from "node:url";
import {promisify} from "node:util";
import {bundle} from "@remotion/bundler";
import {
  makeCancelSignal,
  renderMedia,
  renderStill,
  selectComposition,
} from "@remotion/renderer";
import {
  assertDurationLimit,
  atomicWriteJson,
  cleanupSceneModules,
  inputHash,
  scenePreviewFrames,
  validateInputProps,
  validateSceneModules,
  writeSceneModules,
} from "./render-utils.mjs";

const rootDir = path.dirname(fileURLToPath(import.meta.url));
const entryPoint = path.join(rootDir, "src", "index.ts");
const publicDir = path.join(rootDir, "public");
const configuredTimeout = Number(
  process.env.VIDEO_SANDBOX_RENDER_FRAME_TIMEOUT_MS ?? 7000,
);
const maxFramesPerSegment = Number(
  process.env.VIDEO_SANDBOX_MAX_FRAMES_PER_SEGMENT ?? 1800,
);
const maxDurationSeconds = 180;
const cacheDir = path.join(rootDir, ".remotion-cache");
const progressPath = path.join(rootDir, "progress.json");
const cancelMarkerPath = path.join(rootDir, "cancel");
const execFileAsync = promisify(execFile);

if (!Number.isFinite(configuredTimeout) || configuredTimeout < 7000) {
  throw new Error(
    "VIDEO_SANDBOX_RENDER_FRAME_TIMEOUT_MS must be at least 7000",
  );
}
if (!Number.isInteger(maxFramesPerSegment) || maxFramesPerSegment <= 0) {
  throw new Error(
    "VIDEO_SANDBOX_MAX_FRAMES_PER_SEGMENT must be a positive integer",
  );
}

function createProgressWriter() {
  let writes = Promise.resolve();
  return {
    write(snapshot) {
      writes = writes.then(() =>
        atomicWriteJson(progressPath, {
          ...snapshot,
          updated_at: new Date().toISOString(),
        }),
      );
    },
    flush() {
      return writes;
    },
  };
}

function createCancellation() {
  let requested = false;
  let activeCancel;
  const request = () => {
    requested = true;
    activeCancel?.();
  };
  const poll = () => {
    if (existsSync(cancelMarkerPath)) request();
    return requested;
  };
  const assertActive = () => {
    if (!poll()) return;
    const error = new Error("Render cancelled");
    error.code = "cancelled";
    throw error;
  };
  const withSignal = async (operation) => {
    assertActive();
    const {cancelSignal, cancel} = makeCancelSignal();
    activeCancel = cancel;
    if (poll()) cancel();
    try {
      return await operation(cancelSignal);
    } catch (error) {
      if (requested || String(error?.message).includes("got cancelled")) {
        const cancellationError = new Error("Render cancelled");
        cancellationError.code = "cancelled";
        throw cancellationError;
      }
      throw error;
    } finally {
      activeCancel = undefined;
    }
  };
  process.on("SIGTERM", request);
  process.on("SIGINT", request);
  return {
    assertActive,
    poll,
    withSignal,
    dispose() {
      process.off("SIGTERM", request);
      process.off("SIGINT", request);
    },
  };
}

async function ensureBundle(hash) {
  const bundleDir = path.join(cacheDir, hash, "bundle");
  const completeMarker = path.join(cacheDir, hash, "complete");
  try {
    await Promise.all([access(completeMarker), access(bundleDir)]);
    return {serveUrl: bundleDir, reused: true};
  } catch {
    await rm(path.dirname(bundleDir), {recursive: true, force: true});
  }
  await mkdir(path.dirname(bundleDir), {recursive: true});
  try {
    const serveUrl = await bundle({entryPoint, publicDir, outDir: bundleDir});
    await writeFile(completeMarker, `${hash}\n`, "utf8");
    return {serveUrl, reused: false};
  } catch (error) {
    await rm(path.dirname(bundleDir), {recursive: true, force: true});
    throw error;
  }
}

function structuredDiagnostic(error, inputProps, phase) {
  const message = error instanceof Error ? error.message : String(error);
  const index = inputProps.scenes.findIndex((_, sceneIndex) =>
    message.includes(`scene-${sceneIndex}.tsx`),
  );
  return {
    ok: false,
    phase,
    code: error?.code ?? "remotion_error",
    message,
    ...(index === -1
      ? {}
      : {
          scene: inputProps.scenes[index].slide_number,
          file: `src/scenes/scene-${index}.tsx`,
        }),
  };
}

async function renderVideo({
  cancellation,
  composition,
  serveUrl,
  inputProps,
  outputPath,
  progress,
  workDir,
}) {
  const segmentCount = Math.ceil(
    composition.durationInFrames / maxFramesPerSegment,
  );
  const segmentPaths = [];
  const segmentDurations = [];
  for (let index = 0; index < segmentCount; index += 1) {
    const start = index * maxFramesPerSegment;
    const end = Math.min(
      composition.durationInFrames - 1,
      start + maxFramesPerSegment - 1,
    );
    const segmentPath = path.join(workDir, `segment-${index}.mp4`);
    const segmentStartedAt = Date.now();
    await cancellation.withSignal((cancelSignal) =>
      renderMedia({
        composition,
        serveUrl,
        codec: "h264",
        outputLocation: segmentPath,
        inputProps,
        frameRange: [start, end],
        chromiumOptions: {enableMultiProcessOnLinux: true},
        timeoutInMilliseconds: configuredTimeout,
        cancelSignal,
        onProgress: ({progress: segmentProgress}) => {
          cancellation.poll();
          progress.write({
            phase: "render",
            progress: (index + segmentProgress) / segmentCount,
            segment: index + 1,
            segment_count: segmentCount,
          });
        },
      }),
    );
    console.log(
      `SURFSENSE_SEGMENT_SECONDS=${(Date.now() - segmentStartedAt) / 1000}`,
    );
    segmentPaths.push(segmentPath);
    segmentDurations.push((end - start + 1) / composition.fps);
  }

  if (segmentPaths.length === 1) {
    await execFileAsync("ffmpeg", [
      "-y",
      "-v",
      "error",
      "-i",
      segmentPaths[0],
      "-c",
      "copy",
      "-movflags",
      "+faststart",
      outputPath,
    ]);
  } else {
    const manifestPath = path.join(workDir, "segments.txt");
    await writeFile(
      manifestPath,
      segmentPaths.map((segment) => `file '${segment}'`).join("\n"),
      "utf8",
    );
    await execFileAsync("ffmpeg", [
      "-y",
      "-v",
      "error",
      "-f",
      "concat",
      "-safe",
      "0",
      "-i",
      manifestPath,
      "-c",
      "copy",
      "-movflags",
      "+faststart",
      outputPath,
    ]);
  }
  await writeFile(
    `${outputPath}.segments.json`,
    JSON.stringify({
      expected_duration_seconds:
        composition.durationInFrames / composition.fps,
      segment_durations_seconds: segmentDurations,
      render_workdir: rootDir,
    }),
    "utf8",
  );
  console.log(`SURFSENSE_SEGMENT_COUNT=${segmentCount}`);
}

export async function render(argv = process.argv.slice(2)) {
  const mode =
    argv[0] === "--preflight"
      ? "preflight"
      : argv[0] === "--stills"
        ? "stills"
        : "render";
  const propsArg = mode === "render" ? argv[0] : argv[1];
  const outputArg = mode === "render" ? argv[1] : argv[2];
  const expectedArguments = mode === "preflight" ? 2 : mode === "stills" ? 3 : 2;
  if (
    !propsArg ||
    (mode !== "preflight" && !outputArg) ||
    argv.length !== expectedArguments
  ) {
    throw new Error(
      "Usage: node render.mjs --preflight props.json | --stills props.json outdir | props.json out.mp4",
    );
  }

  const propsPath = path.resolve(propsArg);
  const outputPath = outputArg ? path.resolve(outputArg) : undefined;
  let propsSource;
  let inputProps;
  try {
    propsSource = await readFile(propsPath, "utf8");
    inputProps = validateInputProps(JSON.parse(propsSource));
  } catch (error) {
    const diagnostic = {
      ok: false,
      phase: "validate",
      code: error?.code ?? "invalid_props",
      message: error instanceof Error ? error.message : String(error),
    };
    if (error && typeof error === "object") error.diagnostic = diagnostic;
    throw error;
  }
  const temporaryDir = await mkdtemp(path.join(tmpdir(), "surfsense-remotion-"));
  const progress = createProgressWriter();
  const cancellation = createCancellation();
  let phase = "write";

  try {
    progress.write({phase, progress: 0});
    cancellation.assertActive();
    await writeSceneModules(rootDir, inputProps.scenes);
    phase = "bundle";
    progress.write({phase, progress: 0});
    await validateSceneModules(rootDir);
    const hash = inputHash(propsSource);
    const {serveUrl, reused} = await ensureBundle(hash);
    phase = "select_composition";
    progress.write({phase, progress: 0});
    const composition = await selectComposition({
      serveUrl,
      id: "Main",
      inputProps,
    });
    const durationSeconds = assertDurationLimit(
      composition,
      maxDurationSeconds,
    );
    progress.write({phase, progress: 1, duration_seconds: durationSeconds});

    if (mode === "preflight") {
      const result = {
        ok: true,
        phase: "preflight",
        bundle_hash: hash,
        bundle_reused: reused,
        duration_seconds: durationSeconds,
        duration_in_frames: composition.durationInFrames,
        fps: composition.fps,
      };
      progress.write({phase: "preflight", progress: 1, ...result});
      await progress.flush();
      console.log(JSON.stringify(result));
      return result;
    }

    if (mode === "stills") {
      phase = "stills";
      const sceneDurations = composition.props.sceneDurations;
      if (!Array.isArray(sceneDurations)) {
        throw new Error("calculateMetadata did not return sceneDurations");
      }
      const frames = scenePreviewFrames(sceneDurations);
      await mkdir(path.dirname(outputPath), {recursive: true});
      const stagingDir = await mkdtemp(
        path.join(path.dirname(outputPath), ".remotion-stills-"),
      );
      try {
        const labels = ["start", "middle", "end"];
        const totalStills = inputProps.scenes.length * labels.length;
        let completedStills = 0;
        progress.write({phase, progress: 0});
        for (const [index, scene] of inputProps.scenes.entries()) {
          for (const [frameIndex, frame] of frames[index].entries()) {
            await cancellation.withSignal((cancelSignal) =>
              renderStill({
                composition,
                serveUrl,
                output: path.join(
                  stagingDir,
                  `scene-${String(index + 1).padStart(2, "0")}-slide-${scene.slide_number}-${frameIndex + 1}-${labels[frameIndex]}.png`,
                ),
                frame,
                inputProps,
                timeoutInMilliseconds: configuredTimeout,
                cancelSignal,
              }),
            );
            completedStills += 1;
            progress.write({
              phase,
              progress: completedStills / (totalStills + 1),
              scene: scene.slide_number,
              frame,
            });
          }
        }
        cancellation.assertActive();
        await execFileAsync("ffmpeg", [
          "-y",
          "-v",
          "error",
          "-pattern_type",
          "glob",
          "-i",
          path.join(stagingDir, "scene-*.png"),
          "-vf",
          `scale=480:270,tile=3x${inputProps.scenes.length}:padding=8:margin=8`,
          "-frames:v",
          "1",
          path.join(stagingDir, "contact-sheet.png"),
        ]);
        progress.write({phase, progress: 1});
        await rm(outputPath, {recursive: true, force: true});
        await rename(stagingDir, outputPath);
      } catch (error) {
        await rm(stagingDir, {recursive: true, force: true});
        throw error;
      }
      await progress.flush();
      return;
    }

    phase = "render";
    await mkdir(path.dirname(outputPath), {recursive: true});
    const outputExtension = path.extname(outputPath) || ".mp4";
    const outputStem = outputPath.slice(0, -outputExtension.length);
    const stagedOutputPath =
      `${outputStem}.partial-${process.pid}-${Date.now()}${outputExtension}`;
    let metadataPublished = false;
    try {
      await renderVideo({
        cancellation,
        composition,
        serveUrl,
        inputProps,
        outputPath: stagedOutputPath,
        progress,
        workDir: temporaryDir,
      });
      cancellation.assertActive();
      await rename(
        `${stagedOutputPath}.segments.json`,
        `${outputPath}.segments.json`,
      );
      metadataPublished = true;
      await rename(stagedOutputPath, outputPath);
    } catch (error) {
      await Promise.allSettled([
        rm(stagedOutputPath, {force: true}),
        rm(`${stagedOutputPath}.segments.json`, {force: true}),
        ...(metadataPublished
          ? [rm(`${outputPath}.segments.json`, {force: true})]
          : []),
      ]);
      throw error;
    }
    progress.write({phase, progress: 1});
    await progress.flush();
  } catch (error) {
    progress.write({
      phase,
      progress: 0,
      error: structuredDiagnostic(error, inputProps, phase),
    });
    await progress.flush();
    if (error && typeof error === "object") {
      error.diagnostic = structuredDiagnostic(error, inputProps, phase);
    }
    throw error;
  } finally {
    cancellation.dispose();
    await Promise.allSettled([
      cleanupSceneModules(rootDir),
      rm(temporaryDir, {recursive: true, force: true}),
    ]);
  }
}

const invokedPath = process.argv[1]
  ? pathToFileURL(path.resolve(process.argv[1])).href
  : undefined;
if (invokedPath === import.meta.url) {
  render().catch((error) => {
    console.error(
      JSON.stringify(
        error?.diagnostic ?? {
          ok: false,
          phase: "arguments",
          code: error?.code ?? "remotion_error",
          message: error instanceof Error ? error.message : String(error),
        },
      ),
    );
    process.exitCode = 1;
  });
}
