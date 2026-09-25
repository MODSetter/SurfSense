---
status: in-progress
code:
  - surfsense_local/backend/modules/llm/catalog/local/
  - surfsense_local/backend/modules/llm/providers/sdcpp/
  - surfsense_local/backend/modules/artifacts/
  - surfsense_local/backend/worker/studio/media/visual/
  - surfsense_local/backend/scripts/local_manifest/
  - surfsense_local/backend/alembic/versions/
  - surfsense_local/electron/src/main/
  - surfsense_local/electron/scripts/
  - .github/workflows/
  - surfsense_local/frontend/src/features/models/
  - surfsense_local/frontend/src/features/onboarding/
  - surfsense_local/frontend/src/features/settings/
  - surfsense_local/frontend/src/features/studio/
---

# Local image, image editing and video models

> Studio edits an image and renders a short video clip on this computer, as it already paints images, all through stable-diffusion.cpp's `sd-server`. The image catalog gains current models, every curated model allows commercial use, and onboarding asks for a model of each kind in five steps: text, image, image editing, video, audio.

This extends the local catalog ([`catalog.md`](../architecture/local-models/catalog.md)) and the [model catalog proposal](model-catalog.md), which already made `image_edit` and `video_gen` selectable slots that nothing reads. It changes Studio's image path ([`studio.md`](../architecture/studio.md)) and packaging ([`packaging.md`](../architecture/packaging.md)). It follows the [local audio models](local-audio-models.md) layout: sd.cpp stays one slice under [`engines/sdcpp/`](../../surfsense_local/backend/modules/llm/catalog/local/engines/sdcpp/), and becomes the engine for three types instead of one.

Audio's catalog grows too, on the plan in [local audio models](local-audio-models.md#order-of-work), under the licence rule below.

## What changes

| | Today | With this |
|---|---|---|
| In the installer | only in a local `pnpm dist`, which runs `build:sdcpp`; release CI never stages `sd-server`, so no published release offers a local image model | Windows from upstream's archive with its runtime; Linux and macOS compiled in release CI |
| Image models | SD 1.5, SDXL and SDXL Turbo, one self-contained file each | FLUX.2 klein 4B, Z-Image Turbo and ERNIE-Image Turbo first; SD 1.5 and SDXL kept; SDXL Turbo removed |
| Image editing | a slot nothing reads, with no local runtime | FLUX.2 klein 4B from the same files, and LongCat-Image-Edit, chosen in Settings and onboarding; which feature reads the slot is not decided |
| Video | the same | Wan2.1 T2V 1.3B and Wan2.2 TI2V 5B, chosen in Settings and onboarding; which feature reads the slot is not decided |
| A build | one GGUF, or weights and a projector | weights, VAE, text encoder and projector; a file two models share is downloaded once |
| `sd-server` | runs from start with the image selection, and keeps it resident after the first image | runs for the job that needs it, one model at a time, stopped 5 minutes after the last job |
| Generation settings | sd-server's own defaults; the manifest's `image` defaults are read by nothing | each model's reviewed defaults, passed at launch |
| A second download | refused with `409` while one runs | waits its turn |
| Onboarding | chat, image, audio | chat, image, image editing, video, audio |
| Settings | Chat, Image, Audio | Chat, Image, Image editing, Video, Audio |

## The licence rule

A curated model, and every file its build downloads, must allow commercial use with no revenue cap, registration, membership or excluded territory. Apache-2.0, MIT and the OpenRAIL family pass; an OpenRAIL licence's use restrictions pass on to the user, as Supertonic's do. Audio already applied this when it left NeuTTS out; this writes it down for every engine.

The refresh script enforces it: it refuses, before reading anything, an entry whose licence tag is not on a reviewed allowlist in [`licence.py`](../../surfsense_local/backend/scripts/local_manifest/licence.py), and a unit test holds the committed manifest to the same rule. Once builds carry companion files, it checks each file's repo tag the same way. A custom licence joins the allowlist only after a person has read it and cited the clause in the pull request. The other apps that label licences only display them: InvokeAI shows a "Non-Commercial License" popover on FLUX.1 dev, Klein 9B and Ideogram 4, and LocalAI tags 38 entries `non-commercial`. None filters, and LocalAI labels FLUX.2 klein 9B `apache-2.0`, which it is not, so a label is no substitute for a check.

**SDXL Turbo leaves the manifest.** Its tag is `sai-nc-community`, and its repo's `LICENSE.md` is now the Stability AI Community License, which requires registration and ends at USD 1M yearly revenue. No published release could have downloaded it, since none carries `sd-server`, so it is removed outright, with its line in [`legacy.py`](../../surfsense_local/backend/modules/llm/catalog/local/engines/sdcpp/images_folder/legacy.py). A copy on a machine that ran a local build becomes an unrecognised file.

Families sd.cpp runs that fail the rule:

| Family | Why |
|---|---|
| FLUX.1 dev, FLUX.1 Kontext dev, FLUX.2 dev | FLUX Non-Commercial License |
| FLUX.2 klein 9B | FLUX Non-Commercial License; only the 4B pair is Apache-2.0 |
| SD 3 and 3.5 | Stability AI Community License: registration, USD 1M cap |
| Qwen-Image 2.1 | Qwen Research License, non-commercial |
| LTX-Video, LTX-2.x | USD 10M revenue threshold |
| HunyuanVideo 1.5 | excludes the EU, the UK and South Korea |
| MiniMax-H3 | excludes the EU, UK, Korea and the USA; USD 20M threshold |
| Krea 2, Ideogram 4, Anima, PiD, SeFi | a revenue cap or a non-commercial licence |

## Which models

Every size is the default build's, from Hugging Face's listings on 25 Sep 2026, in decimal gigabytes. Position is preference within each type ([ADR 0026](../adr/0026-curated-order-is-list-position.md)). No model here has been run for this proposal yet; each ships only after the measurement under [Measurements](#measurements).

### Image generation

| Model | Licence | Default build | Download | Steps |
|---|---|---|---|---|
| **FLUX.2 klein 4B** | Apache-2.0 | diffusion Q4_0 2.46 + Qwen3-4B Q4_0 2.38 + FLUX.2 VAE 0.34 | 5.17 GB | 4 |
| **Z-Image Turbo** | Apache-2.0 | diffusion Q4_0 3.68 + Qwen3-4B + FLUX.1 VAE 0.34 | 6.39 GB; 4.02 after klein | 8 |
| **ERNIE-Image Turbo** | Apache-2.0 | diffusion Q4_0 4.76 + Ministral 3 3B Q4_0 2.05 + its own FLUX.2 VAE 0.34 | 7.15 GB | 8 |
| **LongCat-Image** | Apache-2.0 | diffusion Q4_0 3.59 + Qwen2.5-VL-7B Q4_0 4.44 + FLUX.1 VAE 0.34 | 8.37 GB; 8.03 after Z-Image | 50 |
| Stable Diffusion XL | OpenRAIL++ | one file, Q4_0 | 2.71 GB | |
| Stable Diffusion 1.5 | CreativeML OpenRAIL-M | one file, Q4_0 | 3.05 GB | |
| Qwen-Image 2512 | Apache-2.0 | diffusion Q4_0 11.85 + Qwen2.5-VL-7B Q4_0 4.44 + Qwen-Image VAE 0.25 | 16.55 GB; 12.1 after LongCat | 50 |

- **FLUX.2 klein 4B leads.** It is the smallest complete build of a current model, four steps, and the same files edit images, so one download fills two slots.
- **Z-Image Turbo** shares klein's text encoder byte for byte (Comfy's `qwen_3_4b.safetensors` is identical in both repos, and Z-Image's shards match `Qwen/Qwen3-4B`). sd.cpp's docs say it runs in 4 GB of VRAM.
- **ERNIE-Image Turbo** is the one for lettering and posters. sd.cpp's docs pair it with `Comfy-Org/ERNIE-Image`'s copy of the FLUX.2 VAE, which is not byte-identical to klein's, so nothing is shared.
- **LongCat-Image** renders exact lettering in English or Chinese. It takes 50 steps, the slowest here, and its text encoder is the one Qwen-Image and LongCat-Image-Edit take.
- **SDXL and SD 1.5 stay** as the light choices: one file each, and they run where the others do not.
- **Qwen-Image 2512** is for 32 GB machines. It ships after a measurement on one.

Considered and not curated:

- **FLUX.1 schnell** (Apache-2.0): 10.4 GB, a gated vendor repo, and a T5 and CLIP-L stack no other curated model shares; CLIP-L's weights carry no licence tag.
- **Chroma1-HD** (8.7 GB) needs T5 too.
- **Z-Image base, FLUX.2 klein base**: 20 to 50 steps. The distilled builds are what a laptop can wait for.
- **Ovis-Image 7B**: its 5.1 GB text encoder has no GGUF. **HiDream-O1, Boogu**: no GGUF.
- **LLaDA-Image**: newer than the pinned sd.cpp, and its text encoder alone is 9.7 GB. **MiniT2I, SenseNova U1.5**: research-scale, or a whole directory of weights.

### Image editing

| Model | Licence | Default build | Download | Steps |
|---|---|---|---|---|
| **FLUX.2 klein 4B** | Apache-2.0 | the image model's files | 0 after the image model | 4 |
| **LongCat-Image-Edit Turbo** | Apache-2.0 | diffusion Q4_0 3.82 + Qwen2.5-VL-7B Q4_0 4.44 + its projector F16 1.35 + FLUX.1 VAE 0.34 | 9.96 GB | 8 |
| Qwen-Image-Edit-2511 | Apache-2.0 | diffusion Q4_0 11.85 + Qwen2.5-VL-7B + projector + Qwen-Image VAE | 17.90 GB; 13.2 after Qwen-Image 2512 | 40 |

- **An edit model is shown the image**, not asked to repaint around it: sd.cpp passes it as a reference image. Qwen and LongCat read it through their text encoder's vision projector (`--llm_vision`); klein does not need one.
- **LongCat's Turbo GGUF is not the one sd.cpp's docs cite.** It ships if it edits correctly on the pinned sd.cpp. If not, LongCat-Image-Edit is not curated: the cited model takes 50 steps, too slow for a laptop, and klein already edits there.
- **Qwen-Image-Edit-2511** needs `--model-args qwen_image_zero_cond_t=true`, and is for 32 GB machines, like Qwen-Image.

Not curated: FLUX.1 Kontext dev (licence); Z-Image-Edit, not released (its README says "To be released"; sd.cpp's `z_image_omni` preset is waiting for it); Boogu Edit (no GGUF); Step1X-Edit, OmniGen2, HiDream-E1 (sd.cpp cannot run them); Qwen-Image-Edit and 2509, which 2511 supersedes.

### Video

| Model | Licence | Default build | Download | Output |
|---|---|---|---|---|
| **Wan2.2 TI2V 5B** | Apache-2.0 | diffusion Q4_0 3.03 + umt5-xxl Q4_K_M 3.66 + Wan2.2 VAE 1.41 | 8.09 GB | text or an image in, 24 fps |
| **Wan2.1 T2V 1.3B** | Apache-2.0 | diffusion Q8_0 1.59 + umt5-xxl + Wan2.1 VAE 0.25 | 5.50 GB; 1.84 after the 5B | text in, 16 fps, 832×480 |

- **Which leads is a measurement.** The 5B leads if it renders a 33-frame clip at 832×480 in under 10 minutes on the reference laptop; otherwise the 1.3B leads. Until that is measured, the 1.3B leads in the manifest, as the one sure to fit a laptop. Draw Things calls the 1.3B "the better option for low-spec devices".
- **The 1.3B's GGUF is not one sd.cpp's docs cite** (sd.cpp cites only the fp16 safetensors, 2.84 GB); it is validated like LongCat-Image-Edit Turbo's.
- **umt5-xxl has no Q4_0**, and a 1.3B model is small enough at Q8_0, so a build's companions and quantization are named by its entry, not by one preference order ([Builds of several files](#builds-of-several-files)).

Not curated: Wan2.1 14B and Wan2.2 A14B (13 to 21 GB); LingBot-Video 1.3B (no GGUF, and it expects JSON prompts); LTX, HunyuanVideo, MiniMax-H3 (licence); Mochi, Kandinsky 5, Cosmos (sd.cpp cannot run them).

### Files models share

| File | Size | Used by |
|---|---|---|
| Qwen3-4B Q4_0, `unsloth/Qwen3-4B-GGUF` | 2.38 GB | FLUX.2 klein 4B, Z-Image Turbo |
| FLUX.2 VAE, `Comfy-Org/vae-text-encorder-for-flux-klein-4b` (formerly `flux2-klein-4B`) | 0.34 GB | FLUX.2 klein 4B |
| FLUX.1 VAE, `Comfy-Org/z_image_turbo` | 0.34 GB | Z-Image Turbo, LongCat-Image, LongCat-Image-Edit |
| Qwen2.5-VL-7B Q4_0 and its projector, `unsloth/Qwen2.5-VL-7B-Instruct-GGUF` | 4.44 + 1.35 GB | LongCat-Image and Qwen-Image 2512 (without the projector), LongCat-Image-Edit, Qwen-Image-Edit-2511 |
| Qwen-Image VAE, `Comfy-Org/Qwen-Image_ComfyUI` | 0.25 GB | Qwen-Image 2512, Qwen-Image-Edit-2511 |
| umt5-xxl Q4_K_M, `city96/umt5-xxl-encoder-gguf` | 3.66 GB | both Wan models |

A VAE comes from Comfy-Org's ungated copy when the vendor's repo is gated, as BFL's are, with the vendor recorded as `upstream_repo`. The Wan2.2 5B has its own 1.41 GB VAE; the 1.3B uses Wan2.1's.

## Builds of several files

- **Roles.** `FileRole` gains `vae` and `text_encoder`. `projector` also names a text encoder's vision projector, which is what it is: the file llama.cpp calls `mmproj`. A build is runnable when its engine runs every role it lists.
- **A file is a GGUF or a SafeTensors file**, pinned to a commit and a sha256 like every file today.
- **Which flag a file goes to is its family's.** The text encoder is `--llm` for klein, Z-Image, ERNIE, Qwen and LongCat, and `--t5xxl` for Wan. sd.cpp's slice maps a family and a role to a flag in `engines/sdcpp/launch.py`; a single-file SD model keeps `-m`. Adding a model of a known family is a manifest entry. Adding a family is code: its flags, and its name in [`evidence.py`](../../surfsense_local/backend/modules/llm/catalog/local/engines/sdcpp/evidence.py), read from `general.architecture` where the converter wrote one and from tensor names where it did not, as for SD 1 and SDXL.
- **An entry names its builds in order**, as an audio entry does, and the first is the default. `Q4_0` as the only pinned build stops fitting once a companion has no `Q4_0` and a 1.3B model is better at `Q8_0`.

### Shared files

- **A file is known by its sha256.** Two builds that pin the same hash download it once. It lands in the images folder's `shared/` as `<first 12 hex of the hash>-<its name>`, so two different files both called `ae.safetensors` never collide, and one file listed under two names is one file.
- **The install record names every file a build uses**, in place of today's `weights` and `projector` pair.
- **Deleting a model removes the files no other installed build's record names**, worked out at delete time by reading the record, with no stored count. LocalAI (`DeleteModelFromSystem` skips "part of another model") and Ollama (`RemoveLayers` deletes only digests no other manifest uses) do the same; they are the only apps checked that delete a shared file safely.
- **A row states what a download will fetch.** Each build gains `download_bytes` beside `footprint_bytes`: "4.0 GB to download, 2.4 GB already on this computer". The install stream counts only the files it fetches.
- **Free disk is checked before a download**, against the files it will fetch plus 1 GiB, and a shortfall refuses with how much is needed. This closes the gap in [`catalog.md`](../architecture/local-models/catalog.md#known-gaps); at 5 to 18 GB a model, it can no longer wait.

## The runtime

`sd-server` holds one set of model files, named at launch. No route loads, switches or unloads one, and the `model` field of a request is ignored. It reads the weights on the first request and keeps them until it exits. Today Electron keeps it running with the image selection, so after the first image the model stays resident beside the chat model for the rest of the session. At 3 GB that went unnoticed; at 5 to 17 GB it would not.

### One model, for the job that needs it

- **The runtime route answers from Studio's jobs.** `GET /llm/image/local/runtime` answers with the model set for the slot that the oldest running sd.cpp job needs, whether `image_gen`, `image_edit` or `video_gen`. With none running, it keeps the last one for 5 minutes after the last job ended, and then answers none. Electron's existing poll starts, restarts or stops `sd-server` to match ([`index.ts`](../../surfsense_local/electron/src/main/index.ts)).
- **Jobs that need the same model share it**; sd-server runs requests one at a time. A job that needs another model waits until it is the oldest. Studio runs four jobs at once ([ADR 0008](../adr/0008-two-job-queues.md)), so without this two jobs could each hold a model.
- **A job checks the model before it posts.** `GET /sdapi/v1/sd-models` names the file sd-server was launched with, since `/v1/models` always answers `sd-cpp-local`. There is no health route; `GET /` answers once the server is listening.
- **5 minutes** is the same backstop audio uses, and Ollama's default; SwarmUI clears VRAM after 10. It keeps a second image or an edit right after the first from reloading.
- **Cancelling ends the idle window at once.** A generating job cannot be cancelled over HTTP (`409`), so a cancelled job's model is answered none, and Electron stops the process on its next poll.

### Launch flags

sd-server's default generation settings come from its launch flags, so each model's reviewed defaults become flags: `--steps`, `--cfg-scale`, `--sampling-method`, `--flow-shift`, `-W` and `-H`, and the family's flags such as Qwen-Image-Edit-2511's `--model-args`. The client keeps posting only a prompt. This closes the gap that the manifest's `image` defaults are committed and read by nothing ([`catalog.md`](../architecture/local-models/catalog.md#known-gaps)).

### Routes

| Task | Route | Why this one |
|---|---|---|
| Generate | `POST /v1/images/generations` | unchanged |
| Edit, once a feature reads the slot | `POST /sdcpp/v1/img_gen` with `ref_images`, polled at `/sdcpp/v1/jobs/{id}` | `/v1/images/edits` also makes the first image the `init_image`, which runs image-to-image at a strength of 0.75, not the reference edit these models are trained for |
| Video | `POST /sdcpp/v1/vid_gen`, polled at `/sdcpp/v1/jobs/{id}` | the only video route. `video_frames` defaults to 1, so the client sends it, a multiple of four plus one for Wan. A finished result is kept 600 s |

**A clip is WebM (VP8)**, sd-server's default container, which Electron's Chromium plays. Every app checked that writes MP4 ships or finds ffmpeg (InvokeAI through `imageio-ffmpeg`, SwarmUI and Wan2GP likewise, LocalAI from `PATH`); WebM needs nothing added. The artifact is `video/webm`.

### Memory

- **sd.cpp places weights itself.** Its auto-fit puts them on the GPU first, then in RAM, then on disk, reading live free memory, so it takes what the chat model left and slows rather than fails. `--offload-to-cpu` turns auto-fit off and is not used.
- **The GPU is shared with the chat model.** sd.cpp runs on Vulkan on Windows and Linux and Metal on macOS, because a diffusion model on the CPU takes minutes an image; audio could leave the GPU to chat, and this cannot. Whether a video render should unload the chat model first is an [open question](#open-questions).
- **Each curated model commits what it took**, as an audio model commits `peak_mb`: memory at its peak and time per image or clip, measured on the default build on the reference laptop. The row states the memory ("9.1 GB while generating"). Before it starts, a job compares the available memory, RAM and free GPU memory together, with that peak. Short of it, the job refuses and names the first lighter curated model that fits, as a podcast does. Only physics refuses.

## The manifest

An sd.cpp entry keeps its `image` block, or has a `video` block instead, and either names the tasks it takes. Hugging Face's one pipeline tag cannot say "both": FLUX.2 klein 4B's own repo is tagged `image-to-image`, and the GGUF repo it is downloaded from `text-to-image`. So the tasks are reviewed, with the card as `origin`, like an audio model's voices.

```jsonc
"image": {
  "origin": "black-forest-labs/FLUX.2-klein-4B model card; sd.cpp docs/flux2.md",
  "tasks": ["generate", "edit"],
  "resolution": 1024, "steps": 4, "cfg": 1.0, "sampler": "euler",
  "measured": { "peak_mb": 0, "seconds": 0, "on": "…", "sd_cpp": "master-…" }   // filled by the measurement
}

"video": {                                        // values illustrative; the reviewed ones come from the card
  "origin": "Wan-AI/Wan2.2-TI2V-5B model card; sd.cpp docs/wan.md",
  "tasks": ["text", "image"],                     // text-to-video, image-to-video
  "width": 832, "height": 480, "frames": 33, "fps": 24,   // the card's 1280×704 and 121 frames are a desktop's
  "steps": 20, "cfg": 5.0, "flow_shift": 5.0,
  "measured": { … }
}
```

The classifier reads them: `generate` is `IMAGE_GEN`, `edit` is `IMAGE_EDIT`, and a `video` block is `VIDEO_GEN`. The registry gives sd.cpp all three types.

## Selection

- **sd.cpp fills three slots.** Revision `0017` lets `sdcpp` hold `image_gen`, `image_edit` and `video_gen` ([`selection.md`](../architecture/local-models/selection.md)).
- **A model fills the slots of its tasks.** klein's row is `image_gen` and `image_edit`. Chosen for both, one sd-server serves both, since editing is generation with a reference image on the same weights. Krita AI Diffusion, InvokeAI, Draw Things and SwarmUI all treat editing as a property of the model, and a model that does both as one download with two modes.
- **The engine seam's `model_type` becomes `model_types`**, and an install's `select` names the slot it fills, so onboarding's editing step selects for `image_edit`.
- **Deleting a model clears every slot that named it.** The confirmation says so when there are two.

## Studio

- **Image and Infographic** keep their path, now at each model's own defaults.
- **Editing has no Studio feature yet.** The editing slot can be filled, in Settings and onboarding, but what reads it, and whether an edit replaces an image or makes a new one, is a product decision still to take. A Studio Edit that made a new artifact per edit was built and taken out for that reason.
- **Video has no Studio feature yet.** The video slot can be filled, in Settings and onboarding, but what reads it, such as a Studio format that renders a clip from the sources, is a product decision still to take.
- **Neither is retried** after a failure, like an image: a retry would render again.

## Onboarding

Five steps: chat, image, image editing, video, audio. Chat is required; the other four have Skip, as image and audio do today, and the dots count five.

- **Image editing leads with the image model when it edits too**: "FLUX.2 klein 4B edits images too", with Use and nothing to download. Otherwise it lists the curated edit models like any step.
- **Video** lists its models with their size and says a clip takes minutes on a laptop.
- **Every row states what its download fetches**, less what an earlier step already did, so klein's text encoder is never counted twice.
- **Downloads queue.** A second install waits instead of failing: its stream opens with a `queued` frame naming the one ahead, and starts when that one ends. Onboarding moves on while a download runs, as it does today, so choosing an image model and then a video model no longer fails.
- **A server is offered only where a remote client exists**: chat, image and image editing. Video and audio have none.

The apps checked that ask for models at first run ask once, show the size of each choice, and let each be skipped (Comfy-Desktop's starter templates with a tab per kind, Krita's workloads, SwarmUI's checkboxes, Jan). Comfy-Desktop also blocks a choice there is no disk space for. The five steps are this team's decision; the evidence is why every step past chat can be skipped, and states its size and the disk it needs.

## Settings

Five sections: **Chat**, **Image**, **Image editing**, **Video** and **Audio**, headed **Text generation models**, **Image generation models**, **Image editing models**, **Video generation models** and **Audio generation models**, each the same [`model-slot-settings.tsx`](../../surfsense_local/frontend/src/features/settings/models/model-slot-settings.tsx). A model that does both lists in Image and in Image editing; an image or video row reads "Q4_0 · 5.2 GB · 9.1 GB while generating".

## Packaging

A local `pnpm dist` already packages `sd-server`, since it runs `build:sdcpp`; [`release-local.yml`](../../.github/workflows/release-local.yml) runs its own steps and never does, so v2.0.1 and v2.0.2 carry no `sdcpp` folder. Release CI stages it, which closes the gap in [`packaging.md`](../architecture/packaging.md#known-gaps):

- **Windows takes upstream's Vulkan archive, with its runtime.** Unlike audio.cpp's, its `sd-server.exe` and `stable-diffusion.dll` carry no AVX-512 instructions. The 5,600 to 5,900 in the archive sit only in the Skylake-X, Cannon Lake, Cascade Lake and Ice Lake ggml libraries, which ggml loads only on a CPU that has them (counted with `objdump` on `master-869-07a85c7` and `master-913-b167b94`). It imports `VCRUNTIME140`, `MSVCP140` and, for OpenMP, `VCOMP140`, and carries none of them, so the stage copies them beside it, as audio.cpp's does.
- **macOS compiles.** Upstream's archive is a universal binary whose every slice targets macOS 26.0 (`LC_BUILD_VERSION`), so it would not start on the macOS 13.3 that llama.cpp's and audio.cpp's builds target. The build uses llama.cpp's macOS flags: Metal with its shaders embedded, arm64, 13.3.
- **Linux compiles**, on `ubuntu-22.04` in release CI, as audio.cpp does ([`build-audiocpp.yml`](../../.github/workflows/build-audiocpp.yml)). Upstream's `sd-server` and `libstable-diffusion.so` need `GLIBC_2.38` and `GLIBCXX_3.4.32`, so they do not start on 22.04. 22.04 packages no `glslc`, so the job takes LunarG's Vulkan SDK, as llama.cpp's 22.04 release does. The build has the Vulkan backend and WebM and WebP output, and passes the same `objdump` gate.
- **[`build-sdcpp.yml`](../../.github/workflows/build-sdcpp.yml)** compiles Linux and macOS with `scripts/sdcpp/stage.mjs --strict`, checks each against its floor, and hands it to the release as an artifact, cached by its scripts. The release job stages Windows itself.
- **The pin moves** from `master-869-07a85c7` (14 Sep 2026) to the tag the measurements run on. Nothing is published as a release of this repository.

## Order of work

Each step ships alone and leaves the app working.

1. **`sd-server` in the installer.** The Linux and macOS compiles and the Windows archive with its runtime in release CI, SDXL Turbo removed, the licence allowlist in the refresh script. Local images work in a published release for the first time, on Linux older than Ubuntu 24.04 and on macOS before 26.
2. **Builds of several files, and sd-server per job.** Roles, shared files, delete by record, `download_bytes`, the free-disk check, queued installs, launch flags from the manifest, the runtime route from Studio's jobs, the measured block. FLUX.2 klein 4B, Z-Image Turbo and ERNIE-Image Turbo join.
3. **Image editing models.** Revision `0017`, `tasks`, the engine's types, the Image editing section and its onboarding step. klein as an editor, then LongCat. The feature that reads the slot comes once it is decided.
4. **Video models.** Both Wan models, the `video` block, the Video section and its onboarding step. The `vid_gen` client and the feature that reads the slot come once that feature is decided.
5. **Later, each its own step:** Qwen-Image 2512 and Qwen-Image-Edit-2511 once measured on a 32 GB machine; **Animate** an image with Wan2.2 5B; Z-Image-Edit when it is released; a remote video client; LingBot-Video once a GGUF exists; reading the Qwen3-4B text encoder from the chat model's own files when both are installed.

## How others do it

Verified in each app's source on 25 Sep 2026.

| App | Shared files | Deleting one model | Editing | Video out | Unloading |
|---|---|---|---|---|---|
| [Krita AI Diffusion](https://github.com/Acly/krita-ai-diffusion/blob/1b32a3f9a4/ai_diffusion/backend/resources.py) | one resource with several ids: Qwen3 4B for Klein and Z-Image; skipped when present; sha256 | no per-model delete | a property of the architecture; Klein switches Generate and Edit | none | |
| [InvokeAI](https://github.com/invoke-ai/InvokeAI/blob/910aec8409/invokeai/backend/model_manager/starter_models.py) | explicit `dependencies`, installed ones skipped | deletes without checking dependents | a variant of the model | MP4, bundled ffmpeg | cached, no timeout |
| [SwarmUI](https://github.com/mcmonkeyprojects/SwarmUI/blob/e2c35f354d/src/BuiltinExtensions/ComfyUIBackend/WorkflowGeneratorModelSupport.cs) | fetched on first use by name, sha256 checked | no tracking | same list, image in the prompt | H.264 MP4, ffmpeg | VRAM after 10 min |
| [LocalAI](https://github.com/mudler/LocalAI/blob/543fb4bd24/core/gallery/models.go) (sd.cpp) | every file listed with a sha256; shared by name | skips files another model lists | separate entries | MP4, ffmpeg on `PATH` | one process per model, LRU, idle watchdog |
| [Ollama](https://github.com/ollama/ollama/blob/7af393188d/manifest/manifest.go) | content-addressed blobs | deletes only unreferenced blobs | | | 5 min; image generation removed on 28 Jul 2026 |
| [Draw Things](https://github.com/drawthingsai/draw-things-community/blob/9fa43e373d/Libraries/ModelZoo/Sources/ModelZoo.swift) | component fields, one umt5 for every Wan | | a modifier on the model | ProRes or H.264 | |
| [ComfyUI](https://github.com/Comfy-Org/workflow_templates/blob/a7acaf8cee/templates/index.json) | the same file name in several templates, no hash | | a separate template over the same files | MP4 through PyAV | to CPU after use |

What this takes from them: shared files known by content and deleted by reading what still needs them (LocalAI, Ollama); editing as a property of the model, one download for both (Krita, InvokeAI, Draw Things, SwarmUI); an idle unload (Ollama, SwarmUI) with one heavy model at a time (Wan2GP, LM Studio's auto-evict). Where it differs: every file is pinned to a commit, which almost none do; the catalog filters by licence where the others only label; and a clip is WebM from sd.cpp rather than MP4 through ffmpeg.

## Decided here

- `sd-server` is the one runtime for image generation, editing and video. Windows takes upstream's archive with the MSVC and OpenMP runtimes; Linux and macOS compile in release CI. Nothing is published as a release of this repository.
- A curated model and each of its files allow commercial use with no cap, registration or excluded territory, enforced by the refresh script. SDXL Turbo leaves.
- Image: FLUX.2 klein 4B, Z-Image Turbo, ERNIE-Image Turbo, LongCat-Image, SD 1.5, SDXL, then Qwen-Image 2512 once measured. Editing: klein, LongCat-Image-Edit Turbo if it validates, then Qwen-Image-Edit-2511 once measured. Video: Wan2.2 TI2V 5B and Wan2.1 T2V 1.3B, ordered by a measurement.
- A build lists every file it runs from. A file two builds pin is downloaded once, known by its sha256, and deleted when no installed build's record names it.
- A model's tasks are reviewed in its entry and map to its types. A model with two tasks fills two slots from one download.
- One sd.cpp model runs at a time, for the Studio job that needs it, and stops 5 minutes after the last job; a cancel stops it at once. Each model's defaults are launch flags.
- An edit, once a feature reads the slot, sends the image as a reference on sd-server's native route. A clip is WebM.
- Each curated model commits its measured peak memory and time, and a job refuses below that peak, naming a lighter model.
- Onboarding has five steps, all but chat skippable, each stating what its downloads fetch. A second download queues.

## Open questions

Each is a measurement with its rule set above, or set here:

- **Wan 5B or 1.3B first**: the 5B leads if a 33-frame clip at 832×480 renders in under 10 minutes on the reference laptop.
- **LongCat-Image-Edit Turbo**: curated if it edits correctly from the uncited GGUF; otherwise it is not curated.
- **Unloading the chat model during a video render**: measured with it resident and unloaded; unload if the clip is at least 1.3× faster, the same bar audio set for Metal.
- **Vulkan per family**: klein's VAE decode can run out of memory and return a grey image (sd.cpp [#1220](https://github.com/leejet/stable-diffusion.cpp/issues/1220); `--vae-tiling` or the small decoder); Wan2.2 has open Vulkan failures on Windows ([#942](https://github.com/leejet/stable-diffusion.cpp/issues/942)) and macOS ([#860](https://github.com/leejet/stable-diffusion.cpp/issues/860)); `--diffusion-fa`, passed to every model today, is listed in sd.cpp's docs only for the CPU, CUDA and Metal. A model ships on a platform once it has generated there.

## Measurements

None yet. For each curated default build, on the laptop audio was measured on (12th-gen Core i5-1235U, Iris Xe) and on Windows and macOS, at the pinned sd.cpp: peak memory, time to the first image or clip with the load, time for the next, and whether the output is right. Qwen-Image 2512 and Qwen-Image-Edit-2511 also on a 32 GB machine. What each measurement finds goes into the entry's `measured` block and this section.

Sources for the facts above: sd.cpp's docs and server at [`b167b94`](https://github.com/leejet/stable-diffusion.cpp/tree/b167b94) (`docs/flux2.md`, `docs/z_image.md`, `docs/qwen_image_edit.md`, `docs/wan.md`, `docs/backend.md`, `examples/server/`), its `master-913-b167b94` release archives, and each model's Hugging Face listing and licence text.
