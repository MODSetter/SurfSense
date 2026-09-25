# avatar

2026-09-25, golden pair. Direct mapping.

## Changed

- `src/components/ui/avatar.tsx`: parts retyped to `AvatarPrimitive.*.Props`; classes unchanged.
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- `workspace-rail.tsx` renders avatars; no call-site props changed (`delayMs` unused).

## Behavior changes



## Verify by hand

- Workspace rail: avatars and initials fallbacks render as before.
