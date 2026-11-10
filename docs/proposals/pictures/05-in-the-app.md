# In the app

> Edit works on every picture. Settings marks the image models that can edit, with a small label and a three-word tooltip. Nothing in Studio or chat sends the user to Settings for pictures, and a model that cannot do something is described in a neutral line, never a warning.

## Studio's Edit

- **The Edit box shows over every ready picture**, as it does over a document's Refine ([`artifact-panel.tsx`](../../../surfsense_local/frontend/src/features/studio/artifact-panel.tsx)). It no longer checks the `image_edit` slot ([`edit-model.ts`](../../../surfsense_local/frontend/src/features/studio/edit-model.ts)): every picture can be edited or redrawn ([edits and redraws](../pictures/01-image-models.md#edits-and-redraws)).
- **Its placeholder** says what will happen: "Describe a change" when the model edits, "Describe a change: the picture is drawn again" when it redraws. The box reads `pictures_in` from the API to choose.
- **A redrawn version** shows its body's first line, "Drawn again with your change.", in the viewer's normal text.
- **`needs_image_edit` goes**, with its message "Needs an image editing model." and its link to Settings › Image editing models. Only an image picture with no image model at all says "Needs an image model.", as today.

## Settings

- **The label.** In Settings › Image models, each model that takes pictures in carries a small **Edits** label beside its name, in the list of a server's models and in the list of local models to download ([`server-models.tsx`](../../../surfsense_local/frontend/src/features/models/remote/models/server-models.tsx), [`download-image-models.tsx`](../../../surfsense_local/frontend/src/features/models/local/image/download-image-models.tsx)). It is information only: choosing a model without it works.
- **The tooltip** on the label: "Can edit pictures". The label is focusable, so the tooltip opens on keyboard focus as on hover, and a screen reader reads the same words. It uses the app's own tooltip, as the rest of Settings does.
- **Image editing models** ([`image-edit-models-settings.tsx`](../../../surfsense_local/frontend/src/features/settings/models/image-edit-models-settings.tsx)) becomes an optional override, collapsed under the image models, titled "Use a different model for edits". Its summary reads "Same as the image model" when nothing is chosen there, in place of "No image editing model chosen" ([`in-use-summary.tsx`](../../../surfsense_local/frontend/src/features/models/your-models/in-use-summary.tsx)).

## Words

Every new or changed string goes through the `translate` skill, into every language the app ships, short enough not to overflow:

| Where | Text |
|---|---|
| Label | Edits |
| Tooltip | Can edit pictures |
| Edit placeholder, a model that edits | Describe a change |
| Edit placeholder, a redraw | Describe a change: the picture is drawn again |
| A redrawn version | Drawn again with your change. |
| The override's title | Use a different model for edits |
| The override's summary, unset | Same as the image model |

## The user docs

[`guides/images.mdx`](../../../www/content/docs/v2/guides/images.mdx) gains making a comic and what Edit does on each kind of model; [`studio.mdx`](../../../www/content/docs/v2/studio.mdx) the redraw; the image model pages under `models/` the label and the optional edit model; and the models that letter well for comics are named there.

## Checks

- The Edit box over a picture with each of `pictures_in`'s three answers: its placeholder, and that it sends.
- No `needs_image_edit` and no link to the edit settings anywhere in Studio.
- The label shows only on models that take pictures in; its tooltip opens on hover and on focus.
- The override collapsed and summarised as "Same as the image model" when unset.
