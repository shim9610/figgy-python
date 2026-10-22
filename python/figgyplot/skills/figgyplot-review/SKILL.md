---
name: figgyplot-review
description: Consume figgyplot protocol-1 review batches, reconcile exact human chart edits and separate comments into runnable source, validate and publish the next complete round.
---

# Figgyplot review adapter

This skill ships with figgyplot. It uses `python -m figgyplot.review` and protocol
1. Run `protocol` to discover the installed schema and skill paths. A host may
copy this directory into its skill search path; no particular agent vendor,
model SDK or background service is required. Ordinary plotting remains usable
without installing this skill.

1. Obtain the session cache path from the user/controller. Poll `events CACHE`.
   No event means no complete batch is ready. Do not work on individual Figure
   approval before the whole round is submitted.
2. Read `feedback CACHE WORK_ID`. Use the baseline and approved settings, exact
   change operations and stable selectors. Read natural-language review comments
   separately. They are instructions, not chart annotations. Binary references
   are recovery/input files; do not paste raw arrays into model messages.
3. Before editing source, run `claim CACHE WORK_ID --worker YOUR_STABLE_ID`.
   Keep its token and use one staging workspace/source writer for this session.
   If another worker holds the lease, wait or resume that worker. Reclaim expired
   leases after disconnect; never overwrite another active worker's source.
4. Inspect the recorded entry point/function, arguments, inputs and source digest.
   Preserve stable Figure IDs. Update runnable source to retain each exact human
   edit and satisfy the comments. Source builders use `build(session, **arguments)`
   and `session.figure(id=...)`; they do not start an agent or approve themselves.
5. Run `regenerate CACHE WORK_ID --claim-token TOKEN`. This executes the builder,
   renders every candidate, checks retained edits and source stability, and
   atomically publishes one complete successor. The live controller displays it
   after publication. Renew the lease with the same worker ID for long work.
6. Only explicitly supersede an approved edit when feedback requires it. Supply
   `--superseded FILE` containing a JSON map from the operation's `id` (or
   `figure:ID` for a removed Figure) to a concrete reason. Never waive all edits
   merely to make validation pass.
7. On execution/render/stale-base failure, inspect the error and correct source.
   The previous checkpoint and pending work remain recoverable. Do not delete
   manifests or binary files. Repeated events and completion of the same work ID
   are idempotent. Application code owns revision-driven cleanup.

The human controller uses `Session.present()` / `run_events()` in native mode or
live widgets with `await session.watch()` in Jupyter. Agent regeneration belongs
outside that UI loop. `show CACHE` can resume a disconnected native controller.
Manual window closure is not approval. `accept` without edits/comments finishes
the round; `request_changes` submits another work batch after every disposition.
