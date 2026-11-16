# Figures that show how something works

A figure is for a mechanism or a process: how a cache decides, how a queue shares work, how a protocol hands off, how a part of a machine moves. A report, a summary or a reference sheet does not need one; charts and type do that job.

A good figure looks like a small, well-made instrument on a bench: a solid base on feet, rails and posts, a carriage, springs, knobs, a scale with ticks, screws where parts are fixed. The reader understands the idea because they recognise the machine. A few plain boxes on a large empty plate is the failure to avoid.

## The order of work

1. **Pick the object** (below) and say in one sentence what moves and what that means.
2. **Read `isometric.md`** for the helper and its rules, then **the one example in `examples/` closest to your mechanism**:
   - `examples/spring-scale.md`: one part moving in proportion to a value;
   - `examples/pin-tumbler-lock.md`: many parts that must all line up;
   - `examples/job-queue-conveyor.md`: things flowing through stations.
3. **First save:** start from that example's page. Swap in your object with its main parts, about 15 to 25, with the motion, keys and readout working. Save it and look at the screenshot.
4. **Then detail, in edits:** add the parts below a group at a time, saving and looking after each, until the figure has 40 to 80 parts.

Plan in a few lines, then write. Do not work out every part or coordinate before writing code: one reply has a limited budget, and a figure planned whole in thought runs out of it before anything is saved.

## The object is the explanation

Do not draw labelled boxes and arrows. Find a real, well-made thing whose working is the idea:

| The idea | An object that works the same way |
|---|---|
| A cache that skips work when nothing changed | A pin-tumbler lock: only the right key lines up every pin and the plug turns |
| A queue with several workers | A conveyor feeding three stations |
| A rate limit | A turnstile fed by a coin tray that refills at a steady pace |
| A threshold or a trigger | A spring scale whose pointer trips a switch |
| Retries with back-off | A pendulum whose swings grow longer |
| A load balancer | A switchyard sending trains down whichever track is free |

If no object fits, a clean chart is better than a forced figure.

## True numbers

Collect the real values the figure shows: counts, sizes, rates, thresholds. The motion, the readout and the caption all come from the same small model in your script, so they never disagree.

## Parts

Detail is what makes a figure look made. Each part belongs to the mechanism and sits on another part. Work through these groups:

- **Base:** a plate with rounded corners, feet, corner screws, a ruler or groove, a label plate.
- **Structure:** posts, rails, end stops, brackets, a frame or housing.
- **Mechanism:** the moving parts, their pins and bushings, springs, rods.
- **Controls:** a knob with grip lines, a lever, a button, a light.
- **The subject:** the one part the idea is about, in the accent tone.

Then give every visible face its real details: screws where it is fixed, slots or vents on a housing, ticks on a scale, a seam where two parts meet. A bare face or an empty corner is unfinished.

## Compose

- **The mechanism fills the frame.** The base is only as large as what stands on it, and the camera is fitted to the mechanism. Something that leaves the mechanism, a key pulled out, a parcel done, may leave the frame.
- **Ground it** with one soft shadow under the base.
- **Round what is round in life:** `r` on boxes, cylinders for feet, knobs, pins, lights.
- **Paint in layers** where long parts meet small ones (`isometric.md`, Painting order).
- **Tones:** the subject in tints of the page's accent, metal in cool grey, the rest warm neutral; states as tones.

## Frame it

Put the figure in a card: a short title, a hint of what to do ("Click the figure, then use the arrow keys"), and a live readout of the state in true units ("load 4 N · stretch 32 mm"). Words stay out of the drawing.

## Make it live

- The figure answers the keyboard and a button or two, and moves calmly: `ISO.animate` with `ISO.follow`. Parts ease toward a target; nothing snaps.
- Under reduced motion (`ISO.still()`) it shows the end state at once and still answers input. SurfSense takes its screenshots this way, so check the screenshot shows a finished state.

## Access

- The `<svg>` is focusable (`tabindex="0"`) with a role (`slider` for a value, `button` for a single action), an `aria-label` naming the object and the keys, and `aria-valuetext` in words, written when the state settles, not every frame.
- Arrows step, Home and End go to the ends, Enter or Space acts.
- The readout is an `<output role="status">` with the same state in words.

## Check it like a critic

Look at each screenshot the save returns:

- Does the mechanism fill most of the card, or is it lost on an empty plate? Shrink the base and refit.
- Is any region plain? Add the real parts that belong there.
- Is anything painted over a part that should be in front of it? Paint in layers.
- Is anything floating or cut off, is the subject the strongest tone, and does the readout match the drawing?
