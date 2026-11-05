# ADR 0083: ElevenLabs is a connection with its own client

- **Status:** Accepted
- **Date:** 2026-11-05
- **Source:** maintainer decision, 5 Nov 2026, in place of a proposal (no permalink)

## Context

[ADR 0015](0015-openai-compatible-connections.md) makes a connection an endpoint that speaks the OpenAI API, and [Studio](../architecture/studio.md#on-a-server) reached ElevenLabs only through a gateway rather than through an adapter per provider. A gateway cannot do everything: OpenRouter bills its own credits, and it was not shown to voice a user's own account voices. ElevenLabs has no `/audio/speech` and no `/models` envelope, and it signs in with `xi-api-key`.

## Decision

- ElevenLabs is a connection with `auth_kind = 'elevenlabs'`, like a ChatGPT or Claude plan: `provider` stays `openai_compatible`, which the table's check requires, and `auth_kind` says which API it speaks. It fills `audio_gen` alone.
- It has its own client under [`providers/elevenlabs/`](../../surfsense_local/backend/modules/llm/providers/elevenlabs/), written on `httpx`. The official `elevenlabs` SDK is not used: 2,718 files in the frozen app for three calls, and it repeats a request on a 5xx by default, which can bill twice.
- One line per request, through `POST /v1/text-to-speech/{voice_id}` as `wav_24000`, so a pause joins lines as on any other server. Only a 429 is repeated: it comes at once and bills nothing, and Free allows two v4 requests at a time while Studio runs four jobs.
- `detail.message` is what is shown. The API's error shapes differ from its documentation: a missing permission is a 401, not a 403, and not every body has `code`.
- Voice Library voices are hidden from a Free account, because its own list carries them and voicing one is refused with a 402. Without `user_read` the plan is unknown, so they stay, and the refusal explains itself.

## Consequences

- OpenRouter stays. It offers zero data retention, which ElevenLabs keeps for select Enterprise customers, so the two are alternatives rather than a migration.
- Regional hosts are not offered: they are Enterprise-only and take their own key.
- Text to Dialogue is not used. It costs the same per character and may sound more natural, but it runs on v3 and v4 alone, at about 2,000 characters a request, and is a change to how an episode is drafted and voiced.
- Studio podcasts is not used: it writes the script itself, which would bypass the brief and the sources.
- Default voices expire on 31 December 2026, and a Free account created since March 2026 has none, so voices are read live and never named here.
