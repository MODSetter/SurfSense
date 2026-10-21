# Figures that show how something works

A figure is for a mechanism or a process: how a cache decides, how a pipeline moves work, how a protocol hands off, how a part of a machine moves. A report, a summary or a dashboard does not need one; charts and type do that job.

## The object is the explanation

Do not draw labelled boxes and arrows. Find a real, well-made physical thing whose working is the idea, and draw that:

| The idea | An object that works the same way |
|---|---|
| A cache that skips work when nothing changed | A pin-tumbler lock: only the right key lines the pins up and the plug turns |
| A queue with several workers | A sorting conveyor feeding three stations |
| A rate limit | A turnstile that lets one through per tick |
| Retries with back-off | A pendulum whose swings grow longer |
| A load balancer | A switchyard sending trains down whichever track is free |

Say in one sentence what moves and what that motion means, before you draw anything. If no object fits, a clean diagram is better than a forced one.

## Plan, then draw

1. **The true numbers.** Collect the real values the figure shows: sizes, counts, thresholds, timings. The readout and the motion use the same numbers.
2. **Parts.** List the parts, grouped: a base it stands on, the structure that holds things, the mechanism that moves, the controls, and the subject, the one part in the accent tone. A good figure has enough parts to look made: feet, screws, rails, a label plate. Every part sits on another part.
3. **The world.** World units of about one pixel, x and y on the floor, z up. Lay parts out on the floor as boxes and circles. Keep the camera at the kit's 45° and 30° unless a long side needs showing.
4. **Order.** Paint back to front. `Fig.svg` sorts solids by depth; a part that wraps another (a frame around a carriage) is two solids, a back half and a front half.
5. **Frame.** Put the figure in a card: a short title, a hint of what to do ("Drag the key"), and a live readout of the state in true units ("pins 5 of 5 · turns"). Words stay out of the drawing.
6. **Live.** The figure answers pointer and keyboard and moves calmly (`Fig.animate`, `Fig.follow`, `Fig.spring`). When no one touches it, it may play a short loop that shows the point. Under reduced motion it shows its end state and still answers input.

## Access

- The `<svg>` has `role="img"` and an `aria-label` saying what the figure shows.
- The control is focusable (`tabindex="0"`) with a role (`slider`, or a group of buttons for discrete choices), an `aria-label` that names the keys, and `aria-valuetext` in words, written when the reader's choice changes, not every frame.
- Arrows step, Shift steps further, Home and End go to the ends.
- The readout is the same state as text; screen readers get it from a `role="status"` element.

## Check

Look at the screenshot: every part visible, nothing floating, the subject the strongest tone, the readout true. Then check it works with the keyboard alone.
