# Humanizer

[![skills.sh installs](https://skills.sh/b/blader/humanizer)](https://skills.sh/blader/humanizer)

Humanizer rewrites AI-sounding text so it reads like a person wrote it, without changing what it says. Because it is just Markdown, it works with any agent that supports skills.

## How it works

Humanizer uses 35 patterns from Wikipedia's ["Signs of AI writing"](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup. It makes a first pass without treating the original structure as fixed. Then it checks the draft against those patterns and the original claims before rewriting whatever still needs work.

> "LLMs use statistical algorithms to guess what should come next. The result tends toward the most statistically likely result that applies to the widest variety of cases."

It does not make things up. A name, number, date, quote, citation, or other factual detail must come from the source or the writer. For personal writing, Humanizer keeps the writer's style. Technical and reference prose stays neutral and plain. If you provide a writing sample, Humanizer follows that sample instead of its default style rules.

When you paste text, Humanizer shows its work before giving you the final version. You see the first rewrite and a short critique of anything that still sounds artificial. Point it at a file and it changes only the prose, leaving code, data, frontmatter, and link targets alone.

## Usage

Call the skill directly:

```
/humanizer

[paste your text here]
```

Or ask in plain language:

```
Please humanize this text: [your text]
```

To rewrite a file, give Humanizer its path:

```
Humanize the prose in docs/launch-post.md
```

### Match your voice

If you want the rewrite to sound more like you, include a sample:

```
/humanizer

Here's a sample of my writing for voice matching:
[paste 2-3 paragraphs of your own writing]

Now humanize this text:
[paste AI text to humanize]
```

Humanizer follows the sample's rhythm, word choice, punctuation, and deliberate quirks.

## The 35 patterns

### Content patterns

| # | Pattern | Before | After |
|---|---------|--------|-------|
| 1 | **Inflated importance and legacy** | "marking a pivotal moment in the evolution of..." | "was established in 1989 as part of a wider decentralization" |
| 2 | **Name-dropping to prove importance** | "cited in NYT, BBC, FT, and The Hindu" | Keep only useful, sourced context |
| 3 | **Shallow -ing analysis** | "symbolizing... reflecting... showcasing..." | Keep only what the source supports |
| 4 | **Sales language** | "nestled within the breathtaking region" | "is a town in the Gonder region" |
| 5 | **Vague sources** | "Experts believe it plays a crucial role" | Name a real source or remove the claim |
| 6 | **Formulaic challenges and outlook** | "Despite challenges... continues to thrive" | Keep the facts and remove the sales pitch |

### Language and grammar patterns

| # | Pattern | Before | After |
|---|---------|--------|-------|
| 7 | **Overused AI words** | "Actually... additionally... gated on... quietly... testament... landscape... showcasing" | "also... needs... remain common" |
| 8 | **Avoiding is and are** | "serves as... features... boasts" | "is... has" |
| 9 | **Not X but Y and clipped endings** | "It's not just X, it's Y", "..., no guessing" | State the point directly |
| 10 | **Forced groups of three** | "innovation, inspiration, and insights" | Use the number of items the meaning needs |
| 11 | **Changing names and repeated openings** | "protagonist... main character... hero" or "She noted... She noted... She filed..." | Use one name or merge the repeated sentences |
| 12 | **False from X to Y ranges** | "from the Big Bang to dark matter" | List the topics directly |
| 13 | **Passive voice and missing subjects** | "No configuration file needed" | Name the actor when that helps |

### Style patterns

| # | Pattern | Before | After |
|---|---------|--------|-------|
| 14 | **Em/en dashes** | "institutions—not the people—yet this continues—" | Cut them: periods, commas, colons, or parentheses |
| 15 | **Too much bold text** | "**OKRs**, **KPIs**, **BMC**" | "OKRs, KPIs, BMC" |
| 16 | **Lists with bold mini-headings** | "**Performance:** Performance improved" | Use prose when a list adds no value |
| 17 | **Title case in headings** | "Strategic Negotiations And Partnerships" | "Strategic negotiations and partnerships" |
| 18 | **Emojis** | "🚀 Launch Phase: 💡 Key Insight:" | Remove emojis |
| 19 | **Curly quotes** | `said “the project”` | `said "the project"` |
| 26 | **Too many hyphenated word pairs** | “cross-functional, data-driven, client-facing” | Keep only the hyphens grammar needs |
| 27 | **A fake deeper truth** | "At its core, what matters is..." | State the point directly |
| 28 | **Announcing the next point** | "Let's dive in", or "one thing that bit me" | Start with the content |
| 29 | **A heading repeated below itself** | "## Performance" + "Speed matters." | Let the heading do the work |
| 30 | **Writing about the old version** | "This function was added to replace..." | Describe what it does now |
| 31 | **Forced punchlines and fragments** | "It had no preference. No prior. No nostalgia." | Use natural sentence lengths and specific claims |
| 32 | **Formulaic sayings** | "Symmetry is the language of trust" | State the specific claim |
| 33 | **Fake-candid openings** | "Honestly? It depends..." | State the answer directly |
| 34 | **Answering objections no one raised** | "This isn't mainly about prompt length..." | Remove the unsupported defense and keep any real claim |
| 35 | **Rejecting fake alternatives** | "A tempting option would be to..., but" | Remove the fake option and keep real choices |

### Chatbot patterns

| # | Pattern | Before | After |
|---|---------|--------|-------|
| 20 | **Chatbot text left in the answer** | "I hope this helps! Let me know if..." | Remove it |
| 21 | **Knowledge-limit disclaimers and guesses** | "While details are limited in available sources..." | State what is known or remove the claim |
| 22 | **Overly agreeable tone** | "Great question! You're absolutely right!" | Answer directly |

### Filler and hedging

| # | Pattern | Before | After |
|---|---------|--------|-------|
| 23 | **Filler phrases** | "In order to", "Due to the fact that" | "To", "Because" |
| 24 | **Too many qualifiers** | "could potentially possibly" | "may" |
| 25 | **Generic positive endings** | "The future looks bright" | End with a fact or a sourced plan |

## Full example

*Details such as the month and neighborhood need to come from the writer. If they are missing, Humanizer should ask instead of making them up.*

**Before (AI-sounding):**
> I recently spent five unforgettable days in Lisbon, and let me tell you — this city completely stole my heart. From the moment I arrived, I knew I was somewhere truly special.
>
> Nestled along the banks of the Tagus River, Lisbon stands as a vibrant testament to Portugal's enduring spirit, where rich history and modern energy intertwine at every turn. Yes, the famous hills are challenging — my legs certainly felt it! — but every climb rewards you with breathtaking, panoramic views that make it all worthwhile.
>
> No trip would be complete without riding the iconic Tram 28, winding through the city's most historic neighborhoods. And the food? Simply divine. The original pastéis de nata at Pastéis de Belém are a beloved national treasure, and savoring one still warm was a moment I will never forget.
>
> But what truly makes Lisbon special isn't just the sights — it's the feeling. Wander a few steps off the main squares and you'll discover a quieter, more authentic side: sun-drenched alleys, charming tiled facades, and friendly locals going about their daily lives, inviting you to slow down and savor every moment.
>
> Of course, the must-see São Jorge Castle offers stunning views over the rooftops below. The queues can be long, but the experience is absolutely worth it for any history buff or curious traveler.
>
> Would I go back? Absolutely. Lisbon isn't just a place to visit — it's a place to fall in love with, again and again. If you're dreaming of your next getaway, this is one destination that promises memories to last a lifetime. ✨

**After:**
> I spent five days in Lisbon last October and still have mixed feelings about it. Beautiful, yes. Also harder on the knees than anyone warned me.
>
> The hills are the whole story and somehow never make the brochures. My hotel was up in Alfama, which photographs beautifully and translates, in practice, to climbing what felt like a six-story staircase every time I wanted coffee. By the second day my calves had opinions. I started planning each walk around which way was downhill, which is a strange way to see a city but probably an honest one.
>
> Everyone says to ride Tram 28, so I did, wedged against a stranger's backpack for forty minutes while three tour groups filmed the same corner. I would walk the route next time, or go before breakfast. The custard tarts, though, earn the fuss. I had one at a plain little place in Graça, still warm, and for about thirty seconds I understood why people build trips around pastry.
>
> What I did not expect was how quiet the city gets away from the main squares. Two blocks uphill from any plaza it turns into laundry lines, chipped tile, open windows, and old men watching football with the sound turned up. That is the Lisbon I keep thinking about, not the castle.
>
> The castle is fine. The view is great, the queue is long, and I spent more time shuffling toward the entrance than looking at anything once I got inside. If I had only two days, I would trade it for an afternoon of getting lost.
>
> I would go back, but in spring and with better shoes. Lisbon does not bend over backward to make things easy for you. I think I liked that, even when my legs disagreed.

## Sources

- [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) is the source for the pattern list.
- [WikiProject AI Cleanup](https://en.wikipedia.org/wiki/Wikipedia:WikiProject_AI_Cleanup) maintains the page.

## Version history

<details>
<summary>Show release notes</summary>

- **2.11.2** - Removed the plugin symlink and separate Claude Desktop package. Current Claude Code loads the root `SKILL.md` directly, so GitHub's source ZIP now works in Claude Desktop. No change to the 35 patterns.
- **2.11.1** - Added a Claude Desktop-ready release package with one regular `humanizer/SKILL.md` file. GitHub's source archive still keeps the plugin symlink (fixes #224). No change to the 35 patterns.
- **2.11.0** - Rewrote all repo guidance, descriptions, checks, and skill instructions in Plain Language. Kept all 35 patterns and their behavior.
- **2.10.2** - Added the standard `skills/humanizer/` plugin path for Claude Desktop and older loaders. The path links to the root skill, so there is still one prompt (fixes #202).
- **2.10.1** - Added figurative uses of `gate`, `gated`, and `gating` to §7. Kept real technical uses, such as feature gating and CI quality gates.
- **2.10.0** - Added patterns #34 and #35 for old drafting ideas left in final text. Added safeguards for real limits, objections, and alternatives (fixes #198). Also improved §24 and the final rewrite step. 35 patterns total.
- **2.9.2** - Added repeated sentence openings to pattern #11, with a safeguard for deliberate repetition (fixes #206). Expanded §28 to cover casual announcements. 33 patterns total.
- **2.9.1** - Improved installation and package checks. Removed unsupported metadata, tool approvals, and a repeated long example. 33 patterns total.
- **2.9.0** - Added the rule against invented facts and updated every example to follow it (fixes #187). Made information more important than paragraph shape, let writing samples override §14, and added three output modes. 33 patterns total.
- **2.8.3** - Moved the version to `metadata.version` for Agent Skills compatibility. 33 patterns total.
- **2.8.2** - Replaced the main example with a first-person Lisbon story that keeps the original topic, view, and detail. 33 patterns total.
- **2.8.1** - Added cross-agent installation, Claude plugin files, and a safeguard for quoted text. 33 patterns total.
- **2.8.0** - Added patterns #31-33 and expanded pattern #20 to catch chatbot offers. 33 patterns total.
- **2.7.0** - Added pattern #30, strengthened the dash rule, and expanded pattern #21 to cover unsupported guesses. 30 patterns total.
- **2.6.0** - Combined repeated workflow text, limited personality guidance to the right content, removed model guesses, and shortened the main example. 29 patterns total.
- **2.5.1** - Added passive voice and missing subjects. 29 patterns total.
- **2.5.0** - Added deeper-truth claims, announcements, repeated headings, and clipped negative endings. Tightened the dash rule and corrected the frontmatter. 28 patterns total.
- **2.4.0** - Added writing-sample matching.
- **2.3.0** - Added hyphenated word pairs.
- **2.2.0** - Added a draft check and second rewrite.
- **2.1.1** - Corrected the curly-quote example.
- **2.1.0** - Added before/after examples for all 24 patterns.
- **2.0.0** - Rewrote the skill from the Wikipedia source.
- **1.0.0** - First release.

</details>

## License

MIT

## Installation

Install Humanizer with the Skills CLI:

```bash
npx skills add blader/humanizer --global
```

Leave off `--global` to install Humanizer only in the current project. Add `--agent <name>` or `--agent '*'` to choose which agents receive it, then reload their skills.

Claude Code 2.1.142 or newer can install the plugin instead:

```text
/plugin marketplace add blader/humanizer
/plugin install humanizer@humanizer
```

The plugin command is `/humanizer:humanizer`.

In Claude Desktop, download this repository as a ZIP and upload it as a skill.

For a manual install, copy `SKILL.md` into the agent's skill folder.
