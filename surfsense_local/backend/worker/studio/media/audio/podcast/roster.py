from modules.artifacts.podcast.brief import PodcastBrief


def roster(brief: PodcastBrief) -> str:
    """The cast as the prompts name it: the model attributes lines by number."""
    return "\n".join(
        f"{slot}. {speaker.name} ({speaker.role.value})"
        for slot, speaker in enumerate(brief.speakers, start=1)
    )
