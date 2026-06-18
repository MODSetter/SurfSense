"use client";

import { Check, ChevronDown, Loader2, Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Command,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
} from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
	type LanguageOptions,
	MAX_DURATION_SECONDS,
	MAX_SPEAKERS,
	MIN_DURATION_SECONDS,
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
import { VoicePreviewButton } from "./voice-preview-button";

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
}

/**
 * The brief gate, rendered inline in the chat card: a pre-filled
 * near-confirmation. One-click approve is the easy path; every field stays
 * overridable and saves through the version-guarded PATCH so concurrent edits
 * surface instead of clobbering. Approval needs no local follow-up — the
 * pushed status flips the card to its drafting state.
 */
export function BriefReview({ podcast, spec }: BriefReviewProps) {
	const [draft, setDraft] = useState<PodcastSpec>(spec);
	const [durationUnit, setDurationUnit] = useState<DurationUnit>(() =>
		defaultDurationUnit(spec.duration.max_seconds)
	);
	const [voices, setVoices] = useState<VoiceOption[] | null>(null);
	const [offering, setOffering] = useState<LanguageOptions | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);

	// A pushed spec change (saved edit or concurrent editor) resets the form to
	// the authoritative version.
	// biome-ignore lint/correctness/useExhaustiveDependencies: reset only when the server version moves
	useEffect(() => {
		setDraft(spec);
		setDurationUnit(defaultDurationUnit(spec.duration.max_seconds));
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
		podcastsApiService
			.listLanguages()
			.then((options) => {
				if (!cancelled) setOffering(options);
			})
			.catch(() => {
				if (!cancelled) setOffering({ languages: [], allows_custom: false });
			});
		return () => {
			cancelled = true;
		};
	}, []);

	// The backend owns the offering; the draft's language stays listed even
	// when it falls outside it (e.g. a custom tag entered earlier).
	const languages = useMemo(() => {
		const tags = new Set(offering?.languages ?? []);
		tags.add(draft.language);
		return [...tags].sort();
	}, [offering, draft.language]);

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

	const setStyle = (style: PodcastStyle) => {
		setDraft((current) => ({
			...current,
			style,
			// A monologue has exactly one speaker, so extra speakers are dropped
			// rather than letting approval fail validation.
			speakers: style === "monologue" ? current.speakers.slice(0, 1) : current.speakers,
		}));
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

	const handleApprove = async () => {
		setIsSubmitting(true);
		try {
			if (!(await saveIfDirty())) return;
			await podcastsApiService.approveBrief(podcast.id);
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
					{offering?.allows_custom ? (
						<LanguageCombobox value={draft.language} languages={languages} onSelect={setLanguage} />
					) : (
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
					)}
				</div>
				<div className="flex flex-col gap-2">
					<Label htmlFor="podcast-style">Style</Label>
					<Select value={draft.style} onValueChange={(value) => setStyle(value as PodcastStyle)}>
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
						disabled={draft.style === "monologue" || draft.speakers.length >= MAX_SPEAKERS}
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
						<div className="flex w-52 flex-col gap-1.5">
							<Label className="text-xs">Voice</Label>
							<div className="flex items-center gap-1">
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
								<VoicePreviewButton voiceId={speaker.voice_id} />
							</div>
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

			<div className="flex flex-col gap-2">
				<div className="flex items-center justify-between gap-3">
					<Label>Target length</Label>
					<Select
						value={durationUnit}
						onValueChange={(value) => setDurationUnit(value as DurationUnit)}
					>
						<SelectTrigger className="w-[7.5rem]" aria-label="Length unit">
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							<SelectItem value="seconds">Seconds</SelectItem>
							<SelectItem value="minutes">Minutes</SelectItem>
							<SelectItem value="hours">Hours</SelectItem>
						</SelectContent>
					</Select>
				</div>
				<div className="grid grid-cols-2 gap-4">
					<div className="flex flex-col gap-2">
						<Label htmlFor="podcast-min-length">Min</Label>
						<Input
							id="podcast-min-length"
							type="number"
							min={durationUnitBounds(durationUnit).min}
							max={durationUnitBounds(durationUnit).max}
							step={durationInputStep(durationUnit)}
							value={formatDurationForUnit(draft.duration.min_seconds, durationUnit)}
							onChange={(e) => {
								const seconds = clampDurationSeconds(
									fromUnitValue(Number(e.target.value), durationUnit)
								);
								setDraft((current) => ({
									...current,
									duration: { ...current.duration, min_seconds: seconds },
								}));
							}}
						/>
					</div>
					<div className="flex flex-col gap-2">
						<Label htmlFor="podcast-max-length">Max</Label>
						<Input
							id="podcast-max-length"
							type="number"
							min={secondsToUnitValue(draft.duration.min_seconds, durationUnit)}
							max={durationUnitBounds(durationUnit).max}
							step={durationInputStep(durationUnit)}
							value={formatDurationForUnit(draft.duration.max_seconds, durationUnit)}
							onChange={(e) => {
								const parsed = Number(e.target.value);
								const fallback = secondsToUnitValue(draft.duration.min_seconds, durationUnit);
								const seconds = clampDurationSeconds(
									fromUnitValue(Number.isFinite(parsed) ? parsed : fallback, durationUnit)
								);
								setDraft((current) => ({
									...current,
									duration: { ...current.duration, max_seconds: seconds },
								}));
							}}
						/>
					</div>
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
					<Button
						type="button"
						variant="ghost"
						onClick={() => setDraft(spec)}
						disabled={isSubmitting}
					>
						Discard
					</Button>
				) : null}
				<Button
					type="button"
					onClick={handleApprove}
					disabled={isSubmitting || draft.duration.max_seconds < draft.duration.min_seconds}
				>
					{isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
					{isDirty ? "Approve changes & draft transcript" : "Approve & draft transcript"}
				</Button>
			</div>
		</div>
	);
}

/** A searchable language picker for providers whose voices speak anything:
 * the offered list comes from the backend, and any BCP-47 tag may be typed
 * when none of them fits. */
function LanguageCombobox({
	value,
	languages,
	onSelect,
}: {
	value: string;
	languages: string[];
	onSelect: (language: string) => void;
}) {
	const [open, setOpen] = useState(false);
	const [query, setQuery] = useState("");

	const pick = (tag: string) => {
		onSelect(tag);
		setOpen(false);
		setQuery("");
	};

	const customTag = query.trim();
	const isNewTag =
		customTag.length > 0 && !languages.some((tag) => tag.toLowerCase() === customTag.toLowerCase());

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<button
					type="button"
					role="combobox"
					aria-expanded={open}
					id="podcast-language"
					className="border-popover-border flex h-9 w-full items-center justify-between gap-2 rounded-md border bg-transparent px-3 py-2 text-sm whitespace-nowrap shadow-xs outline-none transition-[color,box-shadow] disabled:cursor-not-allowed disabled:opacity-50"
				>
					<span className="line-clamp-1 text-left">{languageLabel(value)}</span>
					<ChevronDown className="size-4 shrink-0 opacity-50" />
				</button>
			</PopoverTrigger>
			<PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
				<Command>
					<CommandInput
						placeholder="Search or type a language tag…"
						value={query}
						onValueChange={setQuery}
					/>
					<CommandList>
						<CommandEmpty>No matching language.</CommandEmpty>
						<CommandGroup>
							{languages.map((tag) => (
								<CommandItem
									key={tag}
									value={tag}
									keywords={[languageLabel(tag)]}
									onSelect={() => pick(tag)}
								>
									<Check className={tag === value ? "size-4" : "size-4 opacity-0"} />
									{languageLabel(tag)}
								</CommandItem>
							))}
							{isNewTag ? (
								<CommandItem value={customTag} onSelect={() => pick(customTag)}>
									<Plus className="size-4" />
									Use “{customTag}”
								</CommandItem>
							) : null}
						</CommandGroup>
					</CommandList>
				</Command>
			</PopoverContent>
		</Popover>
	);
}

/** The current selection stays listed even when it no longer matches the
 * language filter, so the Select never renders an orphaned value. */
type DurationUnit = "seconds" | "minutes" | "hours";

function defaultDurationUnit(maxSeconds: number): DurationUnit {
	if (maxSeconds >= 3600) return "hours";
	if (maxSeconds >= 60) return "minutes";
	return "seconds";
}

function secondsToUnitValue(seconds: number, unit: DurationUnit): number {
	if (unit === "minutes") return seconds / 60;
	if (unit === "hours") return seconds / 3600;
	return seconds;
}

function fromUnitValue(value: number, unit: DurationUnit): number {
	if (!Number.isFinite(value)) return MIN_DURATION_SECONDS;
	if (unit === "minutes") return value * 60;
	if (unit === "hours") return value * 3600;
	return value;
}

function formatDurationForUnit(seconds: number, unit: DurationUnit): number {
	const raw = secondsToUnitValue(seconds, unit);
	if (unit === "seconds") return Math.round(raw);
	return Math.round(raw * 100) / 100;
}

function durationInputStep(unit: DurationUnit): number {
	if (unit === "hours") return 0.1;
	return 1;
}

function durationUnitBounds(unit: DurationUnit): { min: number; max: number } {
	return {
		min: formatDurationForUnit(MIN_DURATION_SECONDS, unit),
		max: formatDurationForUnit(MAX_DURATION_SECONDS, unit),
	};
}

function clampDurationSeconds(value: number): number {
	if (!Number.isFinite(value)) return MIN_DURATION_SECONDS;
	return Math.min(MAX_DURATION_SECONDS, Math.max(MIN_DURATION_SECONDS, Math.round(value)));
}

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
