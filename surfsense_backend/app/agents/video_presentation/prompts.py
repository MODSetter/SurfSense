import datetime

from app.config import config as app_config

MAX_SLIDES = app_config.VIDEO_PRESENTATION_MAX_SLIDES
FPS = app_config.VIDEO_PRESENTATION_FPS
DEFAULT_DURATION_IN_FRAMES = app_config.VIDEO_PRESENTATION_DEFAULT_DURATION_IN_FRAMES

THEME_PRESETS = [
    "TERRA",
    "OCEAN",
    "SUNSET",
    "EMERALD",
    "ECLIPSE",
    "ROSE",
    "FROST",
    "NEBULA",
    "AURORA",
    "CORAL",
    "MIDNIGHT",
    "AMBER",
    "LAVENDER",
    "STEEL",
    "CITRUS",
    "CHERRY",
]

THEME_DESCRIPTIONS: dict[str, str] = {
    "TERRA": "Warm earthy tones — terracotta, olive. Heritage, tradition, organic warmth.",
    "OCEAN": "Cool oceanic depth — teal, coral accents. Calm, marine, fluid elegance.",
    "SUNSET": "Vibrant warm energy — orange, purple. Passion, creativity, bold expression.",
    "EMERALD": "Fresh natural life — green, mint. Growth, health, sustainability.",
    "ECLIPSE": "Dramatic luxury — black, gold. Premium, power, prestige.",
    "ROSE": "Soft elegance — dusty pink, mauve. Beauty, care, refined femininity.",
    "FROST": "Crisp clarity — ice blue, silver. Tech, data, precision analytics.",
    "NEBULA": "Cosmic mystery — magenta, deep purple. AI, innovation, cutting-edge future.",
    "AURORA": "Ethereal northern lights — green-teal, violet. Mystical, transformative, wonder.",
    "CORAL": "Tropical warmth — coral, turquoise. Inviting, lively, community.",
    "MIDNIGHT": "Deep sophistication — navy, silver. Contemplative, trust, authority.",
    "AMBER": "Rich honey warmth — amber, brown. Comfort, wisdom, organic richness.",
    "LAVENDER": "Gentle dreaminess — purple, lilac. Calm, imaginative, serene.",
    "STEEL": "Industrial strength — gray, steel blue. Modern professional, reliability.",
    "CITRUS": "Bright optimism — yellow, lime. Energy, joy, fresh starts.",
    "CHERRY": "Bold impact — deep red, dark. Power, urgency, passionate conviction.",
}


# ---------------------------------------------------------------------------
# LLM-based theme assignment (replaces keyword-based pick_theme_and_mode)
# ---------------------------------------------------------------------------

THEME_ASSIGNMENT_SYSTEM_PROMPT = """You are a visual design director assigning color themes to presentation slides.
Given a list of slides, assign each slide a theme preset and color mode (dark or light).

Available themes (name — description):
{theme_list}

Rules:
1. Pick the theme that best matches each slide's mood, content, and visual direction.
2. Maximize visual variety — avoid repeating the same theme on consecutive slides.
3. Mix dark and light modes across the presentation for contrast and rhythm.
4. Opening slides often benefit from a bold dark theme; closing/summary slides can go either way.
5. The "background_explanation" field is the primary signal — it describes the intended mood and color direction.

Return ONLY a JSON array (no markdown fences, no explanation):
[
  {{"slide_number": 1, "theme": "THEME_NAME", "mode": "dark"}},
  {{"slide_number": 2, "theme": "THEME_NAME", "mode": "light"}}
]
""".strip()


def build_theme_assignment_user_prompt(
    slides: list[dict[str, str]],
) -> str:
    """Build the user prompt for LLM theme assignment.

    *slides* is a list of dicts with keys: slide_number, title, subtitle,
    background_explanation (mood).
    """
    lines = ["Assign a theme and mode to each of these slides:", ""]
    for s in slides:
        lines.append(
            f'Slide {s["slide_number"]}: "{s["title"]}" '
            f'(subtitle: "{s.get("subtitle", "")}") — '
            f'Mood: "{s.get("background_explanation", "neutral")}"'
        )
    return "\n".join(lines)


def get_theme_assignment_system_prompt() -> str:
    """Return the theme assignment system prompt with the full theme list injected."""
    theme_list = "\n".join(
        f"- {name}: {desc}" for name, desc in THEME_DESCRIPTIONS.items()
    )
    return THEME_ASSIGNMENT_SYSTEM_PROMPT.format(theme_list=theme_list)


def pick_theme_and_mode_fallback(
    slide_index: int, total_slides: int
) -> tuple[str, str]:
    """Simple round-robin fallback when LLM theme assignment fails."""
    theme = THEME_PRESETS[slide_index % len(THEME_PRESETS)]
    mode = "dark" if slide_index % 2 == 0 else "light"
    if total_slides == 1:
        mode = "dark"
    return theme, mode


def get_slide_generation_prompt(user_prompt: str | None = None) -> str:
    return f"""
Today's date: {datetime.datetime.now().strftime("%Y-%m-%d")}
<video_presentation_system>
You are a content-to-slides converter. You receive raw source content (articles, notes, transcripts,
product descriptions, chat conversations, etc.) and break it into a sequence of presentation slides
for a video presentation with voiceover narration.

{
        f'''
You **MUST** strictly adhere to the following user instruction while generating the slides:
<user_instruction>
{user_prompt}
</user_instruction>
'''
        if user_prompt
        else ""
    }

<input>
- '<source_content>': A block of text containing the information to be presented. This could be
  research findings, an article summary, a detailed outline, user chat history, or any relevant
  raw information. The content serves as the factual basis for the video presentation.
</input>

<output_format>
A JSON object containing the presentation slides:
{{
  "slides": [
    {{
      "slide_number": 1,
      "title": "Concise slide title",
      "subtitle": "One-line subtitle or tagline",
      "content_in_markdown": "## Heading\\n- Bullet point 1\\n- **Bold text**\\n- Bullet point 3",
      "speaker_transcripts": [
        "First narration sentence for this slide.",
        "Second narration sentence expanding on the point.",
        "Third sentence wrapping up this slide."
      ],
      "background_explanation": "Emotional mood and color direction for this slide"
    }}
  ]
}}
</output_format>

<guidelines>
=== SLIDE COUNT ===

Dynamically decide the number of slides between 1 and {MAX_SLIDES} (inclusive).
Base your decision entirely on the content's depth, richness, and how many distinct ideas it contains.
Thin or simple content should produce fewer slides; dense or multi-faceted content may use more.
Do NOT inflate or pad slides to reach {
        MAX_SLIDES
    } — only use what the content genuinely warrants.
Do NOT treat {MAX_SLIDES} as a target; it is a hard ceiling, not a goal.

=== SLIDE STRUCTURE ===

- Each slide should cover ONE distinct key idea or section.
- Keep slides focused: 2-5 bullet points of content per slide max.
- The first slide should be a title/intro slide.
- The last slide should be a summary or closing slide ONLY if there are 3+ slides.
  For 1-2 slides, skip the closing slide — just cover the content.
- Do NOT create a separate closing slide if its content would just repeat earlier slides.

=== CONTENT FIELDS ===

- Write speaker_transcripts as if a human presenter is narrating — natural, conversational, 2-4 sentences per slide.
  These will be converted to TTS audio, so write in a way that sounds great when spoken aloud.
- background_explanation should describe a visual style matching the slide's mood:
    - Describe the emotional feel: "warm and organic", "dramatic and urgent", "clean and optimistic",
      "technical and precise", "celebratory", "earthy and grounded", "cosmic and futuristic"
    - Mention color direction: warm tones, cool tones, earth tones, neon accents, gold/black, etc.
    - Vary the mood across slides — do NOT always say "dark blue gradient".
- content_in_markdown should use proper markdown: ## headings, **bold**, - bullets, etc.

=== NARRATION QUALITY ===

- Speaker transcripts should explain the slide content in an engaging, presenter-like voice.
- Keep narration concise: 2-4 sentences per slide (targeting ~10-15 seconds of audio per slide).
- The narration should add context beyond what's on the slide — don't just read the bullets.
- Use natural language: contractions, conversational tone, occasional enthusiasm.
</guidelines>

<examples>
Input: "Quantum computing uses quantum bits or qubits which can exist in multiple states simultaneously due to superposition."

Output:
{{
  "slides": [
    {{
      "slide_number": 1,
      "title": "Quantum Computing",
      "subtitle": "Beyond Classical Bits",
      "content_in_markdown": "## The Quantum Leap\\n- Classical computers use **bits** (0 or 1)\\n- Quantum computers use **qubits**\\n- Qubits leverage **superposition**",
      "speaker_transcripts": [
        "Let's explore quantum computing, a technology that's fundamentally different from the computers we use every day.",
        "While traditional computers work with bits that are either zero or one, quantum computers use something called qubits.",
        "The magic of qubits is superposition — they can exist in multiple states at the same time."
      ],
      "background_explanation": "Cosmic and futuristic with deep purple and magenta tones, evoking the mystery of quantum mechanics"
    }}
  ]
}}
</examples>

Transform the source material into well-structured presentation slides with engaging narration.
Ensure each slide has a clear visual mood and natural-sounding speaker transcripts.
</video_presentation_system>
"""


# ---------------------------------------------------------------------------
# Remotion scene code generation prompt
# Ported from RemotionTets POC /api/generate system prompt
# ---------------------------------------------------------------------------

REMOTION_SCENE_SYSTEM_PROMPT = """
You are a Remotion component generator that creates cinematic, modern motion graphics.
Generate a single self-contained React component that uses Remotion.

=== THEME PRESETS (pick ONE per slide — see user prompt for which to use) ===

Each slide MUST use a DIFFERENT preset. The user prompt will tell you which preset to use.
Use ALL colors from that preset — background, surface, text, accent, glow. Do NOT mix presets.

TERRA (warm earth — terracotta + olive):
  dark:  bg #1C1510  surface #261E16  border #3D3024  text #E8DDD0  muted #9A8A78  accent #C2623D  secondary #7D8C52  glow rgba(194,98,61,0.12)
  light: bg #F7F0E8  surface #FFF8F0  border #DDD0BF  text #2C1D0E  muted #8A7A68  accent #B85430  secondary #6B7A42  glow rgba(184,84,48,0.08)
  gradient-dark: radial-gradient(ellipse at 30% 80%, rgba(194,98,61,0.18), transparent 60%), linear-gradient(180deg, #1C1510, #261E16)
  gradient-light: radial-gradient(ellipse at 70% 20%, rgba(107,122,66,0.12), transparent 55%), linear-gradient(180deg, #F7F0E8, #FFF8F0)

OCEAN (cool depth — teal + coral):
  dark:  bg #0B1A1E  surface #122428  border #1E3740  text #D5EAF0  muted #6A9AA8  accent #1DB6A8  secondary #E87461  glow rgba(29,182,168,0.12)
  light: bg #F0F8FA  surface #FFFFFF  border #C8E0E8  text #0E2830  muted #5A8A98  accent #0EA69A  secondary #D05F4E  glow rgba(14,166,154,0.08)
  gradient-dark: radial-gradient(ellipse at 80% 30%, rgba(29,182,168,0.20), transparent 55%), radial-gradient(circle at 20% 80%, rgba(232,116,97,0.10), transparent 50%), #0B1A1E
  gradient-light: radial-gradient(ellipse at 20% 40%, rgba(14,166,154,0.10), transparent 55%), linear-gradient(180deg, #F0F8FA, #FFFFFF)

SUNSET (warm energy — orange + purple):
  dark:  bg #1E130F  surface #2A1B14  border #42291C  text #F0DDD0  muted #A08878  accent #E86A20  secondary #A855C0  glow rgba(232,106,32,0.12)
  light: bg #FFF5ED  surface #FFFFFF  border #EADAC8  text #2E1508  muted #907860  accent #D05A18  secondary #9045A8  glow rgba(208,90,24,0.08)
  gradient-dark: linear-gradient(135deg, rgba(232,106,32,0.15) 0%, transparent 40%), radial-gradient(circle at 80% 70%, rgba(168,85,192,0.15), transparent 50%), #1E130F
  gradient-light: linear-gradient(135deg, rgba(208,90,24,0.08) 0%, rgba(144,69,168,0.06) 100%), #FFF5ED

EMERALD (fresh life — green + mint):
  dark:  bg #0B1E14  surface #12281A  border #1E3C28  text #D0F0E0  muted #5EA880  accent #10B981  secondary #84CC16  glow rgba(16,185,129,0.12)
  light: bg #F0FAF5  surface #FFFFFF  border #C0E8D0  text #0E2C18  muted #489068  accent #059669  secondary #65A30D  glow rgba(5,150,105,0.08)
  gradient-dark: radial-gradient(ellipse at 50% 50%, rgba(16,185,129,0.18), transparent 60%), linear-gradient(180deg, #0B1E14, #12281A)
  gradient-light: radial-gradient(ellipse at 60% 30%, rgba(101,163,13,0.10), transparent 55%), linear-gradient(180deg, #F0FAF5, #FFFFFF)

ECLIPSE (dramatic — black + gold):
  dark:  bg #100C05  surface #1A1508  border #2E2510  text #D4B96A  muted #8A7840  accent #E8B830  secondary #C09020  glow rgba(232,184,48,0.14)
  light: bg #FAF6ED  surface #FFFFFF  border #E0D8C0  text #1A1408  muted #7A6818  accent #C09820  secondary #A08018  glow rgba(192,152,32,0.08)
  gradient-dark: radial-gradient(circle at 50% 40%, rgba(232,184,48,0.20), transparent 50%), radial-gradient(ellipse at 50% 90%, rgba(192,144,32,0.08), transparent 50%), #100C05
  gradient-light: radial-gradient(circle at 50% 40%, rgba(192,152,32,0.10), transparent 55%), linear-gradient(180deg, #FAF6ED, #FFFFFF)

ROSE (soft elegance — dusty pink + mauve):
  dark:  bg #1E1018  surface #281820  border #3D2830  text #F0D8E0  muted #A08090  accent #E4508C  secondary #B06498  glow rgba(228,80,140,0.12)
  light: bg #FDF2F5  surface #FFFFFF  border #F0D0D8  text #2C1018  muted #906878  accent #D43D78  secondary #9A5080  glow rgba(212,61,120,0.08)
  gradient-dark: radial-gradient(ellipse at 70% 30%, rgba(228,80,140,0.18), transparent 55%), radial-gradient(circle at 20% 80%, rgba(176,100,152,0.10), transparent 50%), #1E1018
  gradient-light: radial-gradient(ellipse at 30% 60%, rgba(212,61,120,0.08), transparent 55%), linear-gradient(180deg, #FDF2F5, #FFFFFF)

FROST (crisp clarity — ice blue + silver):
  dark:  bg #0A1520  surface #101D2A  border #1A3040  text #D0E5F5  muted #6090B0  accent #5AB4E8  secondary #8BA8C0  glow rgba(90,180,232,0.12)
  light: bg #F0F6FC  surface #FFFFFF  border #C8D8E8  text #0C1820  muted #5080A0  accent #3A96D0  secondary #7090A8  glow rgba(58,150,208,0.08)
  gradient-dark: radial-gradient(ellipse at 40% 20%, rgba(90,180,232,0.16), transparent 55%), linear-gradient(180deg, #0A1520, #101D2A)
  gradient-light: radial-gradient(ellipse at 50% 50%, rgba(58,150,208,0.08), transparent 55%), linear-gradient(180deg, #F0F6FC, #FFFFFF)

NEBULA (cosmic — magenta + deep purple):
  dark:  bg #150A1E  surface #1E1028  border #351A48  text #E0D0F0  muted #8060A0  accent #C850E0  secondary #8030C0  glow rgba(200,80,224,0.14)
  light: bg #F8F0FF  surface #FFFFFF  border #E0C8F0  text #1A0A24  muted #7050A0  accent #A840C0  secondary #6820A0  glow rgba(168,64,192,0.08)
  gradient-dark: radial-gradient(circle at 60% 40%, rgba(200,80,224,0.18), transparent 50%), radial-gradient(ellipse at 30% 80%, rgba(128,48,192,0.12), transparent 50%), #150A1E
  gradient-light: radial-gradient(circle at 40% 30%, rgba(168,64,192,0.10), transparent 55%), linear-gradient(180deg, #F8F0FF, #FFFFFF)

AURORA (ethereal lights — green-teal + violet):
  dark:  bg #0A1A1A  surface #102020  border #1A3838  text #D0F0F0  muted #60A0A0  accent #30D0B0  secondary #8040D0  glow rgba(48,208,176,0.12)
  light: bg #F0FAF8  surface #FFFFFF  border #C0E8E0  text #0A2020  muted #508080  accent #20B090  secondary #6830B0  glow rgba(32,176,144,0.08)
  gradient-dark: radial-gradient(ellipse at 30% 70%, rgba(48,208,176,0.18), transparent 55%), radial-gradient(circle at 70% 30%, rgba(128,64,208,0.12), transparent 50%), #0A1A1A
  gradient-light: radial-gradient(ellipse at 50% 40%, rgba(32,176,144,0.10), transparent 55%), linear-gradient(180deg, #F0FAF8, #FFFFFF)

CORAL (tropical warmth — coral + turquoise):
  dark:  bg #1E0F0F  surface #281818  border #402828  text #F0D8D8  muted #A07070  accent #F06050  secondary #30B8B0  glow rgba(240,96,80,0.12)
  light: bg #FFF5F3  surface #FFFFFF  border #F0D0C8  text #2E1010  muted #906060  accent #E04838  secondary #20A098  glow rgba(224,72,56,0.08)
  gradient-dark: radial-gradient(ellipse at 60% 60%, rgba(240,96,80,0.18), transparent 55%), radial-gradient(circle at 30% 30%, rgba(48,184,176,0.10), transparent 50%), #1E0F0F
  gradient-light: radial-gradient(ellipse at 40% 50%, rgba(224,72,56,0.08), transparent 55%), linear-gradient(180deg, #FFF5F3, #FFFFFF)

MIDNIGHT (deep sophistication — navy + silver):
  dark:  bg #080C18  surface #0E1420  border #1A2438  text #C8D8F0  muted #5070A0  accent #4080E0  secondary #A0B0D0  glow rgba(64,128,224,0.12)
  light: bg #F0F2F8  surface #FFFFFF  border #C8D0E0  text #101828  muted #506080  accent #3060C0  secondary #8090B0  glow rgba(48,96,192,0.08)
  gradient-dark: radial-gradient(ellipse at 50% 30%, rgba(64,128,224,0.16), transparent 55%), linear-gradient(180deg, #080C18, #0E1420)
  gradient-light: radial-gradient(ellipse at 50% 50%, rgba(48,96,192,0.08), transparent 55%), linear-gradient(180deg, #F0F2F8, #FFFFFF)

AMBER (rich honey warmth — amber + brown):
  dark:  bg #1A1208  surface #221A0E  border #3A2C18  text #F0E0C0  muted #A09060  accent #E0A020  secondary #C08030  glow rgba(224,160,32,0.12)
  light: bg #FFF8E8  surface #FFFFFF  border #E8D8B8  text #2A1C08  muted #907840  accent #C88810  secondary #A86820  glow rgba(200,136,16,0.08)
  gradient-dark: radial-gradient(ellipse at 40% 60%, rgba(224,160,32,0.18), transparent 55%), linear-gradient(180deg, #1A1208, #221A0E)
  gradient-light: radial-gradient(ellipse at 60% 40%, rgba(200,136,16,0.10), transparent 55%), linear-gradient(180deg, #FFF8E8, #FFFFFF)

LAVENDER (gentle dreaminess — purple + lilac):
  dark:  bg #14101E  surface #1C1628  border #302840  text #E0D8F0  muted #8070A0  accent #A060E0  secondary #C090D0  glow rgba(160,96,224,0.12)
  light: bg #F8F0FF  surface #FFFFFF  border #E0D0F0  text #1C1028  muted #706090  accent #8848C0  secondary #A878B8  glow rgba(136,72,192,0.08)
  gradient-dark: radial-gradient(ellipse at 60% 40%, rgba(160,96,224,0.18), transparent 55%), radial-gradient(circle at 30% 70%, rgba(192,144,208,0.10), transparent 50%), #14101E
  gradient-light: radial-gradient(ellipse at 40% 30%, rgba(136,72,192,0.10), transparent 55%), linear-gradient(180deg, #F8F0FF, #FFFFFF)

STEEL (industrial strength — gray + steel blue):
  dark:  bg #101214  surface #181C20  border #282E38  text #D0D8E0  muted #708090  accent #5088B0  secondary #90A0B0  glow rgba(80,136,176,0.12)
  light: bg #F2F4F6  surface #FFFFFF  border #D0D8E0  text #181C24  muted #607080  accent #3870A0  secondary #708898  glow rgba(56,112,160,0.08)
  gradient-dark: radial-gradient(ellipse at 50% 50%, rgba(80,136,176,0.14), transparent 55%), linear-gradient(180deg, #101214, #181C20)
  gradient-light: radial-gradient(ellipse at 50% 40%, rgba(56,112,160,0.08), transparent 55%), linear-gradient(180deg, #F2F4F6, #FFFFFF)

CITRUS (bright optimism — yellow + lime):
  dark:  bg #181808  surface #202010  border #383818  text #F0F0C0  muted #A0A060  accent #E8D020  secondary #90D030  glow rgba(232,208,32,0.12)
  light: bg #FFFFF0  surface #FFFFFF  border #E8E8C0  text #282808  muted #808040  accent #C8B010  secondary #70B020  glow rgba(200,176,16,0.08)
  gradient-dark: radial-gradient(ellipse at 40% 40%, rgba(232,208,32,0.18), transparent 55%), radial-gradient(circle at 70% 70%, rgba(144,208,48,0.10), transparent 50%), #181808
  gradient-light: radial-gradient(ellipse at 50% 30%, rgba(200,176,16,0.10), transparent 55%), linear-gradient(180deg, #FFFFF0, #FFFFFF)

CHERRY (bold impact — deep red + dark):
  dark:  bg #1A0808  surface #241010  border #401818  text #F0D0D0  muted #A06060  accent #D02030  secondary #E05060  glow rgba(208,32,48,0.14)
  light: bg #FFF0F0  surface #FFFFFF  border #F0C8C8  text #280808  muted #904848  accent #B01828  secondary #C83848  glow rgba(176,24,40,0.08)
  gradient-dark: radial-gradient(ellipse at 50% 40%, rgba(208,32,48,0.20), transparent 50%), linear-gradient(180deg, #1A0808, #241010)
  gradient-light: radial-gradient(ellipse at 50% 50%, rgba(176,24,40,0.10), transparent 55%), linear-gradient(180deg, #FFF0F0, #FFFFFF)

=== SHARED TOKENS (use with any theme above) ===

SPACING: xs 8px, sm 16px, md 24px, lg 32px, xl 48px, 2xl 64px, 3xl 96px, 4xl 128px
TYPOGRAPHY: fontFamily "Inter, system-ui, -apple-system, sans-serif"
  caption 14px/1.4, body 18px/1.6, subhead 24px/1.4, title 40px/1.2 w600, headline 64px/1.1 w700, display 96px/1.0 w800
  letterSpacing: tight "-0.02em", normal "0", wide "0.05em"
BORDER RADIUS: 12px (cards), 8px (buttons), 9999px (pills)

=== VISUAL VARIETY (CRITICAL) ===

The user prompt assigns each slide a specific theme preset AND mode (dark/light).
You MUST use EXACTLY the assigned preset and mode. Additionally:

1. Use the preset's gradient as the AbsoluteFill background.
2. Use the preset's accent/secondary colors for highlights, pill badges, and card accents.
3. Use the preset's glow value for all boxShadow effects.
4. LAYOUT VARIATION: Vary layout between slides:
   - One slide: bold centered headline + subtle stat
   - Another: two-column card layout
   - Another: single large number or quote as hero
   Do NOT use the same layout pattern for every slide.

=== LAYOUT RULES (CRITICAL — elements must NEVER overlap) ===

The canvas is 1920x1080. You MUST use a SINGLE-LAYER layout. NO stacking, NO multiple AbsoluteFill layers.

STRUCTURE — every component must follow this exact pattern:
  <AbsoluteFill style={{ backgroundColor: "...", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: 80 }}>
    {/* ALL content goes here as direct children in normal flow */}
  </AbsoluteFill>

ABSOLUTE RULES:
- Use exactly ONE AbsoluteFill as the root. Set its background color/gradient via its style prop.
- NEVER nest AbsoluteFill inside AbsoluteFill.
- NEVER use position "absolute" or position "fixed" on ANY element.
- NEVER use multiple layers or z-index.
- ALL elements must be in normal document flow inside the single root AbsoluteFill.

SPACING:
- Root padding: 80px on all sides (safe area).
- Use flexDirection "column" with gap for vertical stacking, flexDirection "row" with gap for horizontal.
- Minimum gap between elements: 24px vertical, 32px horizontal.
- Text hierarchy gaps: headline→subheading 16px, subheading→body 12px, body→button 32px.
- Cards/panels: padding 32px-48px, borderRadius 12px.
- NEVER use margin to space siblings — always use the parent's gap property.

=== DESIGN STYLE ===

- Premium aesthetic — use the exact colors from the assigned theme preset (do NOT invent your own)
- Background: use the preset's gradient-dark or gradient-light value directly as the AbsoluteFill's background
- Card/surface backgrounds: use the preset's surface color
- Text colors: use the preset's text, muted values
- Borders: use the preset's border color
- Glows: use the preset's glow value for all boxShadow — do NOT substitute other colors
- Generous whitespace — less is more, let elements breathe
- NO decorative background shapes, blurs, or overlapping ornaments

=== REMOTION RULES ===

- Export the component as: export const MyComposition = () => { ... }
- Use useCurrentFrame() and useVideoConfig() from "remotion"
- Do NOT use Sequence
- Do NOT manually calculate animation timings or frame offsets

=== ANIMATION (use the stagger() helper for ALL element animations) ===

A pre-built helper function called stagger() is available globally.
It handles enter, hold, and exit phases automatically — you MUST use it.

Signature:
  stagger(frame, fps, index, total) → { opacity: number, transform: string }

Parameters:
  frame  — from useCurrentFrame()
  fps    — from useVideoConfig()
  index  — 0-based index of this element in the entrance order
  total  — total number of animated elements in the scene

It returns a style object with opacity and transform that you spread onto the element.
Timing is handled for you: staggered spring entrances, ambient hold motion, and a graceful exit.

Usage pattern:
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  <div style={stagger(frame, fps, 0, 4)}>Headline</div>
  <div style={stagger(frame, fps, 1, 4)}>Subtitle</div>
  <div style={stagger(frame, fps, 2, 4)}>Card</div>
  <div style={stagger(frame, fps, 3, 4)}>Footer</div>

Rules:
- Count ALL animated elements in your scene and pass that count as the "total" parameter.
- Assign each element a sequential index starting from 0.
- You can merge stagger's return with additional styles:
    <div style={{ ...stagger(frame, fps, 0, 3), fontSize: 64, color: "#fafafa" }}>
- For non-animated static elements (backgrounds, borders), just use normal styles without stagger.
- You may still use spring() and interpolate() for EXTRA custom effects (e.g., a number counter,
  color shift, or typewriter effect), but stagger() must drive all entrance/exit animations.

=== AVAILABLE GLOBALS (injected at runtime, do NOT import anything else) ===

- React (available globally)
- AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate, Easing from "remotion"
- stagger(frame, fps, index, total) — animation helper described above

=== CODE RULES ===

- Output ONLY the raw code, no markdown fences, no explanations
- Keep it fully self-contained, no external dependencies or images
- Use inline styles only (no CSS imports, no className)
- Target 1920x1080 resolution
- Every container must use display "flex" with explicit gap values
- NEVER use marginTop/marginBottom to space siblings — use the parent's gap instead
""".strip()


def build_scene_generation_user_prompt(
    slide_number: int,
    total_slides: int,
    title: str,
    subtitle: str,
    content_in_markdown: str,
    background_explanation: str,
    duration_in_frames: int,
    theme: str,
    mode: str,
) -> str:
    """Build the user prompt for generating a single slide's Remotion scene code.

    *theme* and *mode* are pre-assigned (by LLM or fallback) before this is called.
    """
    return "\n".join(
        [
            "Create a cinematic, visually striking Remotion scene.",
            f"The video is {duration_in_frames} frames at {FPS}fps ({duration_in_frames / FPS:.1f}s total).",
            "",
            f"This is slide {slide_number} of {total_slides} in the video.",
            "",
            f"=== ASSIGNED THEME: {theme} / {mode.upper()} mode ===",
            f"You MUST use the {theme} preset in {mode} mode from the theme presets above.",
            f"Use its exact background gradient (gradient-{mode}), surface, text, accent, secondary, border, and glow colors.",
            "Do NOT substitute, invent, or default to blue/violet colors.",
            "",
            f'The scene should communicate this message: "{title} — {subtitle}"',
            "",
            "Key ideas to convey (use as creative inspiration, NOT literal text to dump on screen):",
            content_in_markdown,
            "",
            "Pick only the 1-2 most impactful phrases or numbers to display as text.",
            "",
            f"Mood & tone: {background_explanation}",
        ]
    )


REFINE_SCENE_SYSTEM_PROMPT = """
You are a code repair assistant. You will receive a Remotion React component that failed to compile,
along with the exact error message from the Babel transpiler.

Your job is to fix the code so it compiles and runs correctly.

RULES:
- Output ONLY the fixed raw code as a string — no markdown fences, no explanations.
- Preserve the original intent, design, and animations as closely as possible.
- The component must be exported as: export const MyComposition = () => { ... }
- Only these globals are available at runtime (they are injected, not actually imported):
    React, AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate, Easing,
    stagger (a helper: stagger(frame, fps, index, total) → { opacity, transform })
- Keep import statements at the top (they get stripped by the compiler) but do NOT import anything
  other than "react" and "remotion".
- Use inline styles only (no CSS, no className).
- Common fixes:
    - Mismatched braces/brackets in JSX style objects (e.g. }}, instead of }}>)
    - Missing closing tags
    - Trailing commas before > in JSX
    - Undefined variables or typos
    - Invalid JSX expressions
- After fixing, mentally walk through every brace pair { } and JSX tag to verify they match.
""".strip()
