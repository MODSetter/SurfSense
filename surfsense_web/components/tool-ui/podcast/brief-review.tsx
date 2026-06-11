"use client";

import { Loader2, Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
	MAX_SPEAKERS,
	type PodcastSpec,
	type PodcastStyle,
	podcastStyle,
	type SpeakerRole,
	speakerRole,
	type VoiceOption,
} from "@/contracts/types/podcast.types";
import type { LivePodcast } from "@/hooks/use-podcast-live";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";
import { AppError } from "@/lib/error";

// A "*" voice speaks whatever language the text is in (mirrors the backend
// catalog's ANY_LANGUAGE sentinel).
const ANY_LANGUAGE = "*";

function speaks(voice: VoiceOption, language: string): boolean {
	if (voice.language === ANY_LANGUAGE) return true;
	return primary(voice.language) === primary(language);
}

function primary(language: string): string {
	return language.split("-", 1)[0].trim().toLowerCase();
}

interface BriefReviewProps {
	podcast: LivePodcast;
	spec: PodcastSpec;
	onApproved: () => void;
}

/**
 * Gate 1: the pre-filled brief as a near-confirmation. One-click approve is
 * the easy path; every field stays overridable and saves through the
 * version-guarded PATCH so concurrent edits surface instead of clobbering.
 */
export function BriefReview({ podcast, spec, onApproved }: BriefReviewProps) {
	const [draft, setDraft] = useState<PodcastSpec>(spec);
	const [voices, setVoices] = useState<VoiceOption[] | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);

	// A pushed spec change (saved edit or concurrent editor) resets the form to
	// the authoritative version.
	// biome-ignore lint/correctness/useExhaustiveDependencies: reset only when the server version moves
	useEffect(() => {
		setDraft(spec);
	}, [podcast.specVersion]);

	useEffect(() => {
		let cancelled = false;
		podcastsApiService
			.listVoices()
			.then((catalog) => {
				if (!cancelled) setVoices(catalog);
			})
			.catch(() => {
				if (!cancelled) setVoices([]);
			});
		return () => {
			cancelled = true;
		};
	}, []);

	const languages = useMemo(() => {
		const tags = new Set<string>();
		for (const voice of voices ?? []) {
			if (voice.language !== ANY_LANGUAGE) tags.add(voice.language);
		}
		tags.add(draft.language);
		return [...tags].sort();
	}, [voices, draft.language]);

	const voicesForLanguage = useMemo(
		() => (voices ?? []).filter((voice) => speaks(voice, draft.language)),
		[voices, draft.language]
	);

	const isDirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(spec), [draft, spec]);

	const setLanguage = (language: string) => {
		setDraft((current) => {
			const candidates = (voices ?? []).filter((voice) => speaks(voice, language));
			// Voices that can't render the new language are remapped so the saved
			// spec never pairs a language with an incompatible voice.
			const speakers = current.speakers.map((speaker, index) => {
				const stillValid = candidates.some((voice) => voice.voice_id === speaker.voice_id);
				const fallback = candidates[index % Math.max(candidates.length, 1)];
				return stillValid || !fallback ? speaker : { ...speaker, voice_id: fallback.voice_id };
			});
			return { ...current, language, speakers };
		});
	};

	const updateSpeaker = (slot: number, change: Partial<PodcastSpec["speakers"][number]>) => {
		setDraft((current) => ({
			...current,
			speakers: current.speakers.map((speaker) =>
				speaker.slot === slot ? { ...speaker, ...change } : speaker
			),
		}));
	};

	const addSpeaker = () => {
		setDraft((current) => {
			if (current.speakers.length >= MAX_SPEAKERS) return current;
			const slot = Math.max(...current.speakers.map((s) => s.slot)) + 1;
			const voice =
				voicesForLanguage[current.speakers.length % Math.max(voicesForLanguage.length, 1)];
			return {
				...current,
				speakers: [
					...current.speakers,
					{
						slot,
						name: `Speaker ${current.speakers.length + 1}`,
						role: "guest" as SpeakerRole,
						voice_id: voice?.voice_id ?? current.speakers[0].voice_id,
					},
				],
			};
		});
	};

	const removeSpeaker = (slot: number) => {
		setDraft((current) => {
			if (current.speakers.length <= 1) return current;
			return {
				...current,
				speakers: current.speakers.filter((speaker) => speaker.slot !== slot),
			};
		});
	};

	const saveIfDirty = async (): Promise<boolean> => {
		if (!isDirty) return true;
		try {
			await podcastsApiService.updateSpec(podcast.id, draft, podcast.specVersion);
			return true;
		} catch (error) {
			if (error instanceof AppError && error.status === 409) {
				toast.warning("The brief changed elsewhere — reloaded the latest version.");
				setDraft(spec);
			} else {
				toast.error(error instanceof Error ? error.message : "Failed to save the brief");
			}
			return false;
		}
	};

	const handleSave = async () => {
		setIsSubmitting(true);
		try {
			if (await saveIfDirty()) {
				toast.success("Brief saved.");
			}
		} finally {
			setIsSubmitting(false);
		}
	};

	const handleApprove = async () => {
		setIsSubmitting(true);
		try {
			if (!(await saveIfDirty())) return;
			await podcastsApiService.approveBrief(podcast.id);
			onApproved();
		} catch (error) {
			toast.error(error instanceof Error ? error.message : "Failed to approve the brief");
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<div className="flex flex-col gap-6">
			<div className="grid grid-cols-2 gap-4">
				<div className="flex flex-col gap-2">
					<Label htmlFor="podcast-language">Language</Label>
					<Select value={draft.language} onValueChange={setLanguage}>
						<SelectTrigger id="podcast-language">
							<SelectValue placeholder="Language" />
						</SelectTrigger>
						<SelectContent>
							{languages.map((tag) => (
								<SelectItem key={tag} value={tag}>
									{languageLabel(tag)}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>
				<div className="flex flex-col gap-2">
					<Label htmlFor="podcast-style">Style</Label>
					<Select
						value={draft.style}
						onValueChange={(value) =>
							setDraft((current) => ({ ...current, style: value as PodcastStyle }))
						}
					>
						<SelectTrigger id="podcast-style">
							<SelectValue placeholder="Style" />
						</SelectTrigger>
						<SelectContent>
							{podcastStyle.options.map((style) => (
								<SelectItem key={style} value={style}>
									{capitalize(style)}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>
			</div>

			<div className="flex flex-col gap-3">
				<div className="flex items-center justify-between">
					<Label>Speakers</Label>
					<Button
						type="button"
						variant="ghost"
						size="sm"
						onClick={addSpeaker}
						disabled={draft.speakers.length >= MAX_SPEAKERS}
					>
						<Plus className="size-4" /> Add speaker
					</Button>
				</div>
				{draft.speakers.map((speaker) => (
					<div key={speaker.slot} className="flex items-end gap-2 rounded-lg border p-3">
						<div className="flex flex-1 flex-col gap-1.5">
							<Label htmlFor={`speaker-name-${speaker.slot}`} className="text-xs">
								Name
							</Label>
							<Input
								id={`speaker-name-${speaker.slot}`}
								value={speaker.name}
								maxLength={120}
								onChange={(e) => updateSpeaker(speaker.slot, { name: e.target.value })}
							/>
						</div>
						<div className="flex w-28 flex-col gap-1.5">
							<Label className="text-xs">Role</Label>
							<Select
								value={speaker.role}
								onValueChange={(value) =>
									updateSpeaker(speaker.slot, { role: value as SpeakerRole })
								}
							>
								<SelectTrigger>
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									{speakerRole.options.map((role) => (
										<SelectItem key={role} value={role}>
											{capitalize(role)}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</div>
						<div className="flex w-44 flex-col gap-1.5">
							<Label className="text-xs">Voice</Label>
							<Select
								value={speaker.voice_id}
								onValueChange={(value) => updateSpeaker(speaker.slot, { voice_id: value })}
							>
								<SelectTrigger>
									<SelectValue placeholder={voices === null ? "Loading…" : "Voice"} />
								</SelectTrigger>
								<SelectContent>
									{voiceItems(voicesForLanguage, speaker.voice_id).map((voice) => (
										<SelectItem key={voice.voice_id} value={voice.voice_id}>
											{voice.display_name} ({voice.gender})
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</div>
						<Button
							type="button"
							variant="ghost"
							size="icon"
							aria-label={`Remove ${speaker.name}`}
							onClick={() => removeSpeaker(speaker.slot)}
							disabled={draft.speakers.length <= 1}
						>
							<Trash2 className="size-4" />
						</Button>
					</div>
				))}
			</div>

			<div className="grid grid-cols-2 gap-4">
				<div className="flex flex-col gap-2">
					<Label htmlFor="podcast-min-minutes">Min length (minutes)</Label>
					<Input
						id="podcast-min-minutes"
						type="number"
						min={1}
						value={draft.duration.min_minutes}
						onChange={(e) =>
							setDraft((current) => ({
								...current,
								duration: { ...current.duration, min_minutes: Number(e.target.value) || 1 },
							}))
						}
					/>
				</div>
				<div className="flex flex-col gap-2">
					<Label htmlFor="podcast-max-minutes">Max length (minutes)</Label>
					<Input
						id="podcast-max-minutes"
						type="number"
						min={draft.duration.min_minutes}
						value={draft.duration.max_minutes}
						onChange={(e) =>
							setDraft((current) => ({
								...current,
								duration: {
									...current.duration,
									max_minutes: Number(e.target.value) || current.duration.min_minutes,
								},
							}))
						}
					/>
				</div>
			</div>

			<div className="flex flex-col gap-2">
				<Label htmlFor="podcast-focus">Focus (optional)</Label>
				<Textarea
					id="podcast-focus"
					placeholder="What should the episode emphasise?"
					maxLength={2000}
					value={draft.focus ?? ""}
					onChange={(e) => setDraft((current) => ({ ...current, focus: e.target.value || null }))}
				/>
			</div>

			<div className="flex justify-end gap-2">
				{isDirty ? (
					<Button type="button" variant="outline" onClick={handleSave} disabled={isSubmitting}>
						Save changes
					</Button>
				) : null}
				<Button
					type="button"
					onClick={handleApprove}
					disabled={isSubmitting || draft.duration.max_minutes < draft.duration.min_minutes}
				>
					{isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
					Approve &amp; draft transcript
				</Button>
			</div>
		</div>
	);
}

/** The current selection stays listed even when it no longer matches the
 * language filter, so the Select never renders an orphaned value. */
function voiceItems(candidates: VoiceOption[], selectedId: string): VoiceOption[] {
	if (candidates.some((voice) => voice.voice_id === selectedId)) return candidates;
	return [
		{ voice_id: selectedId, display_name: selectedId, language: "", gender: "unknown" },
		...candidates,
	];
}

function languageLabel(tag: string): string {
	try {
		const label = new Intl.DisplayNames(["en"], { type: "language" }).of(tag);
		return label && label !== tag ? `${label} (${tag})` : tag;
	} catch {
		return tag;
	}
}

function capitalize(value: string): string {
	return value.charAt(0).toUpperCase() + value.slice(1);
}
