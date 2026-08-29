import {createHash} from "node:crypto";
import {mkdir, readdir, rename, rm, writeFile} from "node:fs/promises";
import path from "node:path";
import {build} from "esbuild";

const EMPTY_GENERATED_MODULE =
  "// Replaced by render.mjs before bundling and restored during cleanup.\nexport const sceneComponents = [];\n";

export function validateInputProps(input) {
  if (!input || typeof input !== "object") {
    throw new Error("props.json must contain an object");
  }
  if (!Number.isInteger(input.fps) || input.fps <= 0) {
    throw new Error("fps must be a positive integer");
  }
  if (
    !Number.isInteger(input.min_duration_in_frames) ||
    input.min_duration_in_frames <= 0
  ) {
    throw new Error("min_duration_in_frames must be a positive integer");
  }
  if (!Array.isArray(input.scenes) || input.scenes.length === 0) {
    throw new Error("scenes must be a non-empty array");
  }
  if (input.scenes.length > 12) {
    throw new Error("scenes must contain at most 12 entries");
  }

  const slideNumbers = new Set();
  for (const [index, scene] of input.scenes.entries()) {
    if (!scene || typeof scene !== "object") {
      throw new Error(`scenes[${index}] must be an object`);
    }
    if (!Number.isInteger(scene.slide_number) || scene.slide_number <= 0) {
      throw new Error(`scenes[${index}].slide_number must be a positive integer`);
    }
    if (slideNumbers.has(scene.slide_number)) {
      throw new Error(`Duplicate slide_number ${scene.slide_number}`);
    }
    slideNumbers.add(scene.slide_number);
    if (typeof scene.code !== "string" || !scene.code.trim()) {
      throw new Error(`scenes[${index}].code must be non-empty`);
    }
    if (scene.audio !== undefined) {
      if (
        typeof scene.audio !== "string" ||
        !scene.audio ||
        path.posix.isAbsolute(scene.audio) ||
        path.posix.normalize(scene.audio).startsWith("../")
      ) {
        throw new Error(`scenes[${index}].audio must be a public-relative path`);
      }
    }
  }

  return input;
}

export function cumulativeStartFrames(durations) {
  let offset = 0;
  return durations.map((duration) => {
    const start = offset;
    offset += duration;
    return start;
  });
}

export function scenePreviewFrames(durations) {
  const starts = cumulativeStartFrames(durations);
  return durations.map((duration, index) => {
    if (!Number.isInteger(duration) || duration <= 0) {
      throw new Error(`sceneDurations[${index}] must be a positive integer`);
    }
    const start = starts[index];
    const end = start + duration - 1;
    return [start, start + Math.floor((duration - 1) / 2), end];
  });
}

export function assertDurationLimit(composition, maxDurationSeconds = 180) {
  const durationSeconds = composition.durationInFrames / composition.fps;
  if (durationSeconds > maxDurationSeconds) {
    const error = new Error(
      `Composition duration ${durationSeconds.toFixed(3)}s exceeds ${maxDurationSeconds}s`,
    );
    error.code = "duration_limit";
    throw error;
  }
  return durationSeconds;
}

export function inputHash(source) {
  return createHash("sha256").update(source).digest("hex");
}

export async function atomicWriteJson(filePath, value) {
  await mkdir(path.dirname(filePath), {recursive: true});
  const temporaryPath = `${filePath}.${process.pid}.${Date.now()}.tmp`;
  await writeFile(temporaryPath, `${JSON.stringify(value)}\n`, "utf8");
  await rename(temporaryPath, filePath);
}

export async function writeSceneModules(rootDir, scenes) {
  const scenesDir = path.join(rootDir, "src", "scenes");
  await mkdir(scenesDir, {recursive: true});
  await cleanupSceneModules(rootDir);

  await Promise.all(
    scenes.map((scene, index) =>
      writeFile(
        path.join(scenesDir, `scene-${index}.tsx`),
        scene.code,
        "utf8",
      ),
    ),
  );

  const imports = scenes
    .map((_, index) => `import Scene${index} from "./scene-${index}";`)
    .join("\n");
  const components = scenes.map((_, index) => `Scene${index}`).join(", ");
  await writeFile(
    path.join(scenesDir, "generated.ts"),
    `${imports}\n\nexport const sceneComponents = [${components}];\n`,
    "utf8",
  );
}

export async function validateSceneModules(rootDir) {
  await build({
    absWorkingDir: rootDir,
    bundle: true,
    entryPoints: ["src/scenes/generated.ts"],
    jsx: "automatic",
    logLevel: "silent",
    packages: "external",
    platform: "browser",
    tsconfig: path.join(rootDir, "tsconfig.json"),
    write: false,
  });
}

export async function cleanupSceneModules(rootDir) {
  const scenesDir = path.join(rootDir, "src", "scenes");
  let entries;
  try {
    entries = await readdir(scenesDir);
  } catch (error) {
    if (error?.code === "ENOENT") return;
    throw error;
  }

  await Promise.all(
    entries
      .filter((name) => /^scene-\d+\.tsx$/.test(name))
      .map((name) => rm(path.join(scenesDir, name), {force: true})),
  );
  await writeFile(path.join(scenesDir, "generated.ts"), EMPTY_GENERATED_MODULE, "utf8");
}
