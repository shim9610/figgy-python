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

1. Initialize the controller with a review font that supports the user's primary
   language. Inspect installed fonts and glyph coverage; do not assume the default
   Latin UI face can display the user's text. For Korean, an installed
   `Noto Sans CJK KR` is one suitable choice. Pass the actual family name through
   `Session(..., review_font="Noto Sans CJK KR", review_font_size=14)` before
   presenting any window/widget. Use the user's language for review text. The
   chosen face is loaded into native review inputs and transferred to notebook
   browsers; an unavailable family is an initialization error. Do not replace
   document typography merely to configure the review UI.
2. Obtain the session cache path from the controller. Keep the controller running
   on its rendering host and subscribe using
   `python -m figgyplot.review subscribe CACHE --timeout 50`. After a delivered
   work ID, use `--after WORK_ID` on later subscriptions. Keep the execution-tool
   call pending so completion of the human review returns the feedback signal
   directly to the agent. A timeout or finished session returns `null`; check
   `status CACHE`, stop for `completed`/`cancelled`, otherwise subscribe again
   without treating it as approval. `events CACHE` remains available for manual lookup.
   No event means no complete batch is ready. Individual Figure approval does
   not start source modification: the final disposition publishes the whole
   batch and wakes the subscription. Do not ask the user to copy feedback back
   into the conversation.
3. Read `feedback CACHE WORK_ID`. Use the baseline and approved settings, exact
   change operations and stable selectors. Read natural-language review comments
   separately, including right-click element comments addressed by stable object
   ID. They are instructions, not chart annotations. Binary references
   are recovery/input files; do not paste raw arrays into model messages.
4. Before editing source, run `claim CACHE WORK_ID --worker YOUR_STABLE_ID`.
   Keep its token and use one staging workspace/source writer for this session.
   If another worker holds the lease, wait or resume that worker. Reclaim expired
   leases after disconnect; never overwrite another active worker's source.
5. Inspect the recorded entry point/function, arguments, inputs and source digest.
   Preserve stable Figure IDs. Update runnable source to retain each exact human
   edit and satisfy the comments. Source builders use `build(session, **arguments)`
   and `session.figure(id=...)`; they do not start an agent or approve themselves.
6. Run `regenerate CACHE WORK_ID --claim-token TOKEN`. This executes the builder,
   renders every candidate, checks retained edits and source stability, and
   atomically publishes one complete successor. The live controller displays it
   after publication. Renew the lease with the same worker ID for long work.
7. Only explicitly supersede an approved edit when feedback requires it. Supply
   `--superseded FILE` containing a JSON map from the operation's `id` (or
   `figure:ID` for a removed Figure) to a concrete reason. Never waive all edits
   merely to make validation pass.
8. On execution/render/stale-base failure, inspect the error and correct source.
   The previous checkpoint and pending work remain recoverable. Do not delete
   manifests or binary files. Repeated events and completion of the same work ID
   are idempotent. Application code owns revision-driven cleanup.

The human controller uses `Session.present()` / `run_events()` in native mode or
live widgets with `await session.watch()` in Jupyter. Agent regeneration belongs
outside that UI loop. `show CACHE` can resume a disconnected native controller.
Manual window closure is not approval. `accept` without edits/comments finishes
the round; `request_changes` submits another work batch after every disposition.


After publishing a successor, immediately return to the subscription step.
The controller presents the complete next round. No vendor SDK is invoked by
subscription, and the agent must remain attached through its execution tools.
Closing an execution-tool connection does not discard pending durable feedback;
resume from the cache and last delivered work ID.
