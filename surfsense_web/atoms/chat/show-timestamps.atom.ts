import { atomWithStorage } from "jotai/utils";

/**
 * Per-device preference: show a timestamp under each chat message.
 *
 * Off by default to match streaming-AI chat convention (ChatGPT/Claude keep
 * the message stream clean and put time in the conversation list). Persisted
 * in localStorage, so it does not sync across devices — acceptable for a
 * cosmetic display toggle.
 */
export const showMessageTimestampsAtom = atomWithStorage<boolean>("chat-show-timestamps:v1", false);
