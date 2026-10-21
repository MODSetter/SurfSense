# Figures that show how something works

A figure is for a mechanism or a process: how a cache decides, how a pipeline moves work, how a protocol hands off, how a part of a machine moves. A report, a summary or a reference sheet does not need one; charts and type do that job.

A good figure looks like a small, well-made instrument on a bench: a solid base on feet, rails and posts, a carriage, springs, knobs, a scale with ticks, screws where parts are fixed. The reader understands the idea because they recognise the machine. A few plain boxes on a large empty plate is the failure to avoid.

## 1. The object is the explanation

Do not draw labelled boxes and arrows. Find a real, well-made physical thing whose working is the idea, and say in one sentence what moves and what that motion means.

| The idea | An object that works the same way |
|---|---|
| A cache that skips work when nothing changed | A pin-tumbler lock: only the right key lines up every pin and the plug turns |
| A queue with several workers | A sorting conveyor feeding three stations |
| A rate limit | A turnstile fed by a coin tray that refills at a steady pace |
| Retries with back-off | A pendulum whose swings grow longer |
| A load balancer | A switchyard sending trains down whichever track is free |
| A threshold or a trigger | A spring scale whose pointer trips a switch |

If no object fits, a clean chart is better than a forced figure.

## 2. True numbers

Collect the real values the figure shows: counts, sizes, rates, thresholds. The motion, the readout and the caption all come from the same small model in your script, so they never disagree.

## 3. A parts list before any drawing

Write the list first, grouped, and aim for **40 to 80 parts**. Detail is what makes a figure look made; each part belongs to the mechanism and sits on another part.

- **Base:** a plate with rounded corners, feet, corner screws, a groove or a ruler strip, a label plate.
- **Structure:** posts, rails, end stops, brackets, a frame.
- **Mechanism:** the moving parts, their bushings and pins, springs, rods, gears.
- **Controls:** a knob (knurled), a lever, a button, a dial with ticks.
- **The subject:** the one part the idea is about, in the accent tone.

Then give every visible face its real details: screws where it is fixed, vents or slots on a housing, ticks on a scale, a seam where two parts meet, an engraved plate. Every region of the drawing should have something true to find; a bare face or an empty corner is unfinished.

## 4. Compose

- **The mechanism fills the frame.** Make the base only as large as what stands on it, with a small margin, and fit the camera to the mechanism (`Fig.fit` with `Fig.corners` of the base and the tallest part). The figure should take most of its card.
- **Keep the true isometric camera** (the kit's default) unless a long side needs showing.
- **World units of about a pixel of the real thing:** a base of 300 to 400 units, parts of 10 to 60, screws of 2.
- **Ground it:** one soft `Fig.shadow` under the base, painted first.
- **Round what is round in life:** `r` on boxes, cylinders for feet, knobs, pins and coins.
- **Order:** paint back to front. List the parts yourself and pass `{ sort: false }` when parts overlap; split a spring that wraps a rod into its back and front halves.
- **Tones:** the subject in tints of the page's accent, metal in cool grey, everything else neutral.

## 5. Frame it

Put the figure in a card: a short title, a hint of what to do ("Click the figure, then use the arrow keys"), and a live readout of the state in true units ("load 4 N · stretch 32 mm"). Words stay out of the drawing, except at most one engraved label plate.

## 6. Make it live

- The figure answers pointer or keyboard and moves calmly: `Fig.animate`, with `Fig.follow` or `Fig.spring`. Parts ease toward a target; nothing snaps.
- When no one touches it, it may play one short loop that shows the point, then settle.
- Under reduced motion it shows the end state at once and still answers input.

## 7. Access

- The `<svg>` is focusable (`tabindex="0"`) with a role (`slider`, or `button` for a single action), an `aria-label` that names the object and the keys, and `aria-valuetext` in words, written when the reader's choice changes, not every frame.
- Arrows step, Shift steps further, Home and End go to the ends; Enter or Space acts.
- The readout is the same state as text, in a `role="status"` element.

## 8. Check it like a critic

Look at the screenshot the save returns:

- Does the mechanism fill most of the card, or is it lost on an empty plate? Shrink the base and refit.
- Is any region plain? Add the real parts that belong there.
- Is anything floating, cut off or painted in front of a part that should hide it?
- Is the subject the strongest tone, and does the readout match what the drawing shows?

Then check it works with the keyboard alone, and save again until it passes.
