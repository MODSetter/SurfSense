# ADR 0093: A GGUF another app downloaded is found in that app's folder and used where it lies, never copied

- **Status:** Accepted
- **Date:** 2026-11-21

## Context

A person who already runs local models keeps them in Ollama, LM Studio, Jan, GPT4All or the Hugging Face cache. Onboarding offered only downloads, so they fetched gigabytes they already had, on the weak hardware and slow connections the local path exists for. The catalog already read a file's header and priced it ([ADR 0013](0013-fit-from-the-allocator.md), [ADR 0014](0014-two-tier-model-catalog.md)); what it lacked was the file. Those folders are other apps', so SurfSense must not change, copy or move anything in them; reading outside its own data folder must be disclosed; and nothing may reach the network ([ADR 0017](0017-egress-off-by-default.md)). llama-server reads per-model arguments only from the preset, at startup ([ADR 0011](0011-llama-cpp-local-runtime.md)).

Measured at b11050 on Windows: a preset section whose `model` names a file outside `--models-dir` is listed by the router and loads in place, an Ollama blob with no `.gguf` extension included, and chats. The preset's parser ends a value at `#` or `;`, quoted or not, so a path holding either loads nothing. Header reads on this machine's real files took 20 to 220 ms each, and a first look at four places 0.4 s.

## Decision

- **Look in known places, locally.** The API reads Ollama's manifests (`OLLAMA_MODELS`, else `~/.ollama/models`, and the Linux service's `/usr/share/ollama/.ollama/models`); LM Studio's models folder (its home pointer, else `~/.lmstudio`, and the older `~/.cache/lm-studio`); the Hugging Face hub cache, which `hf download`, Unsloth's instructions and current llama.cpp's `-hf` all fill (`HF_HUB_CACHE`, then `HF_HOME`, then the XDG cache); llama.cpp's older cache (`LLAMA_CACHE`, else its per-system default); Jan (its `data_folder` setting); GPT4All (its `modelPath`, else its per-system folder); and any folder the person adds. KoboldCpp keeps a model beside its executable, wherever that was unpacked, so its folder is one a person adds. Only folder listings, these apps' own small settings files and GGUF headers are read, nothing is written there, and nothing is sent.
- **Offer only what the bundled runtime can chat with.** A found file is offered when its header says it is a model (not a projector, adapter, imatrix or a later part of a split), the classifier makes it a chat model, its architecture is one llama.cpp's own table names (the pinned `gguf` package's `MODEL_ARCH_NAMES`), it holds no projector tensors (`v.`, `a.`, `mm.`) inside its weights, which is Ollama's own multimodal format and fails llama.cpp's tensor count, and its path holds no `#` or `;`. Unlike a file in SurfSense's own folder, an unknown architecture fails closed: these files were not chosen for SurfSense, and Ollama names some architectures its own way (`gptoss`, `qwen25vl`, `mllama`). A file the person picks is judged the same way. What is skipped is counted, each with its reason.
- **Found is not installed.** Nothing enters the preset until the person chooses a model. Use is an install job: it records the file in `elsewhere.json` in the models folder (the runtime's name for it, the path, every part, the projector, whose folder it was in) and runs the steps after a download, the preset rewrite, the router's restart, the warm load and the selection, and none of the steps before one. The job asks about no host. A change in another app's folder never restarts the runtime.
- **The file stays the other app's.** Removing a model used in place forgets its record and rewrites the preset; no route unlinks it, and the screen says Stop using, not Delete. A recorded file that went away, or stopped being one the runtime can chat with, leaves the preset at the next rewrite and keeps its record, so a drive that comes back brings it back.
- **A projector goes with a model only on the other app's evidence:** the projector layer Ollama's manifest records; elsewhere, a folder holding one repo's files (a hub snapshot, LM Studio's `publisher/repo`, a Jan model folder) gives its projector to each build in it, as a searched repo does, once both headers state the same width.
- **On by default, said where it shows, with a switch.** The scan runs when a screen asks for it (onboarding's chat step, Settings' Add model page), never on a timer. Its section names the apps it found folders for and says files are used where they are, never changed, and that nothing leaves the computer. Settings turns looking in other apps' folders off; added folders and picked files are the person's own act and are read either way.
- **The admin policy is not extended.** `policy.json` governs what leaves the computer ([contract 05](../contracts/05-desktop-telemetry.md), part C). This sends nothing and reads only the person's own files, which they could already copy into the models folder by hand; an administrator who wants to limit local models needs an allowlist that covers downloads too.
- **The fallback is the system's own dialog.** Electron opens it for a `.gguf` file or a folder and hands back only the path the person chose; the API reads it as the scan would and refuses with the reason. The Docker image reads nothing outside its folders: its browser cannot name a path on the server, and the container holds no other app's folder.

## Consequences

- A person with Ollama, LM Studio, Jan, GPT4All or Hugging Face downloads is offered those models in onboarding, priced for the machine, with nothing to download.
- A model is called what the person recognises: an Ollama tag, else the file's own name less its build, else the header's `general.name`. Its parameters, quantization and window come from its header.
- Each header is read once per process for a path, size and modification time; asking again costs a folder listing.
- A model another app deletes or replaces, as an Ollama pull does when it prunes the old blob, is missing until chosen again from the new file. A curated row never claims a file used in place, so such a model runs on llama-server's defaults rather than a curated entry's sampling.
- In a strictly confined snap the home interface hides dot folders, so only the non-hidden places and added folders can be read there.

## Where the code stands

- The macOS privacy prompts (TCC) for a picked file in Documents or Downloads, and the snap's confinement, are reasoned from the platforms' rules, not measured.
- A models folder moved to a path holding `#` or `;` breaks every model the same way; the storage move does not refuse such a folder yet ([storage location](../architecture/storage-location.md)).
