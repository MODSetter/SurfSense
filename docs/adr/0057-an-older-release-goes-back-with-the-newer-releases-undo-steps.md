# ADR 0057: An older release goes back by running the undo steps a newer release left in the data folder

- **Status:** Accepted
- **Date:** 2026-10-15
- **Source:** [data model, Known gaps L399](https://github.com/MODSetter/SurfSense/blob/b17b3e9e0c13670dac85dcd1079082d8142bab54/docs/architecture/data-model.md#L399)

## Context

A release cannot open a database a later release migrated: the revision is unknown to it, so its API did not start and the app closed with no message. The only way back was replacing `surfsense.db` with the snapshot in `backups/` by hand, which loses everything added since the update.

Every revision has a `downgrade`, but it ships in the newer release, and installing the older release removes it. An older release cannot carry the undo steps of revisions written after it was built. Re-releasing older versions with them would have to happen on every release, and the installer a user kept would still fail. Having the newer release undo itself before it is replaced needs the user to plan ahead.

## Decision

- Every API start copies the release's migration scripts to `<data>/migrations/`, and keeps the files a later release left there.
- A migration imports only the standard library, `sqlalchemy` and `alembic`, and its `downgrade` works on a database holding rows back to `0011`, 2.0.0's head. Tests enforce both.
- An API that finds a revision it does not know exits with code 3 before serving. Electron stops every sidecar and asks first; nothing changes on Quit.
- Going back runs the saved downgrades to this release's head, after copying the database to `backups/set-aside/`. If those cannot run, or one fails, the fallback is the newest backup this release can open, again after setting the database aside.

## Consequences

- Going back keeps what the user added after the update, except what a downgrade drops because the older release has no place for it.
- An older release runs code it did not ship. That code is the app's own migrations, from the user's own data folder.
- A downgrade that does not work now breaks going back for users, so every revision's `downgrade` is held to the same bar as its `upgrade`.
- It works only when going back to a release that has this code: going back to 2.2.1 or earlier still needs the hand restore.
- Each time the app goes back, it keeps a set-aside copy of the database that is never pruned.
