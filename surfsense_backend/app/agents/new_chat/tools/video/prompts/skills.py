import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_litellm import ChatLiteLLM

from app.agents.new_chat.tools.video.skills.skills import SKILL_NAMES
from app.utils.content_utils import strip_code_fences

logger = logging.getLogger(__name__)

SKILL_DETECTION_PROMPT = """Classify this motion graphics prompt into ALL applicable categories.
A prompt can match multiple categories. Only include categories that are clearly relevant.

Guidance categories (patterns and rules):
- charts: data visualizations, graphs, histograms, bar charts, pie charts, progress bars, statistics, metrics
- typography: kinetic text, typewriter effects, text animations, word carousels, animated titles, text-heavy content
- social-media: Instagram stories, TikTok content, YouTube shorts, social media posts, reels, vertical video
- messaging: chat interfaces, WhatsApp conversations, iMessage, chat bubbles, text messages, DMs, messenger
- 3d: 3D objects, ThreeJS, spatial animations, rotating cubes, 3D scenes
- transitions: scene changes, fades between clips, slide transitions, wipes, multiple scenes
- sequencing: multiple elements appearing at different times, staggered animations, choreographed entrances
- spring-physics: bouncy animations, organic motion, elastic effects, overshoot animations

Code examples (complete working references):
- example-histogram: animated bar chart with spring animations and @remotion/shapes
- example-progress-bar: loading bar animation from 0 to 100%
- example-text-rotation: rotating words with fade/blur transitions
- example-falling-spheres: 3D bouncing spheres with ThreeJS and physics simulation
- example-animated-shapes: bouncing/rotating SVG shapes (circle, triangle, rect, star)
- example-lottie: loading and displaying Lottie animations from URL
- example-gold-price-chart: bar chart with Y-axis labels, monthly data, staggered animations
- example-typewriter-highlight: typewriter effect with cursor blink, pause, and word highlight
- example-word-carousel: rotating words with crossfade and blur transitions

Return a JSON object with a single key "skills" containing an array of matching category names.
Return {"skills": []} if none apply.
Example: {"skills": ["transitions", "example-word-carousel"]}"""


async def detect_skills(llm: ChatLiteLLM, topic: str) -> list[str]:
    messages = [
        SystemMessage(content=SKILL_DETECTION_PROMPT),
        HumanMessage(content=f'User prompt: "{topic}"'),
    ]
    try:
        response = await llm.ainvoke(messages)
        content = strip_code_fences(response.content or "")
        parsed = json.loads(content)
        if isinstance(parsed, list):
            skills = parsed
        elif isinstance(parsed, dict):
            skills = parsed.get("skills", [])
        else:
            return []
        valid = set(SKILL_NAMES)
        return [s for s in skills if isinstance(s, str) and s in valid]
    except Exception:
        logger.exception("Skill detection failed, continuing without skills")
        return []
