# Guides

The app links to the step-by-step guides on `surfsense.com` (`/docs/v2/guides`): short silent videos and a screenshot for each step, one page per task. Nothing is bundled or fetched: installers have size budgets, the screenshots are of the English app, and the app fetches no media on its own. Each link opens in the OS browser on a click, like every other `surfsense.com` link ([about](about.md#links)).

**Code:** [`surfsense_local/frontend/src/features/guides/`](../../surfsense_local/frontend/src/features/guides/), [`surfsense_local/electron/src/main/menu/help-menu.ts`](../../surfsense_local/electron/src/main/menu/help-menu.ts). The pages and how they are captured: [`www/scripts/guides/`](../../www/scripts/guides/) and [`plans/community-local/tutorials.md`](../../plans/community-local/tutorials.md).

## Where they open from

| Place | Opens | `utm_content` |
|---|---|---|
| Help › Guides and Videos (the application menu, English like its other items) | the guides hub | `help_menu` |
| Settings › About › Links › Guides and videos | the guides hub | `about_guides` |
| The sidebar footer's Guides and videos row | a dialog listing every guide by area, in the app's language; each title opens its page | `guides_dialog` |
| The empty Sources list | Add files and folders | `sources_empty` |
| Studio's empty artifact list | Make a Word document, deck or PDF in Studio | `studio_empty` |
| No plugins connected | Connect a plugin and use it in a chat | `plugins_empty` |
| Jobs with no runs | Fill in a security questionnaire from your policies | `jobs_runs_empty` |
| Add from the web, before the first search | Add web pages and YouTube videos | `web_search_start` |
| The speech setup box, while it asks (from the composer's mic or a waiting recording) | Turn a recording into a source, which sets up speech recognition | `speech_setup` |
| An empty chat or speech recognition model section in Settings | Run a model on your computer, or Turn a recording into a source | `models_empty` |

## The catalog

`guide-catalog.ts` mirrors the hub's groups and order in `www/content/docs/v2/guides/meta.json`, and `GuideSlug` names every page. A guide added on the site is added here too, with its title in every catalog ([localization](localization.md)), or the dialog leaves it out. The pages themselves are English only, which the dialog says.
