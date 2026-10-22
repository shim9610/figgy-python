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
2. Connect feedback before asking the user to review. For a native session,
   seal the builder's complete Figure set with `session.start()` before handing
   its cache to a separate command, then
   use `python -m figgyplot.review connect CACHE` as the default entry point.
   Keep that execution-tool call pending: it hosts the native windows and returns
   the complete feedback signal, so the user need not start a separate subscriber
   or controller. It waits indefinitely by default; `--timeout SECONDS` is optional.
   After regeneration, call `connect CACHE --after WORK_ID` again immediately.
   For an already running controller, or notebook review with `watch()`, subscribe using
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
3. Start with `feedback CACHE WORK_ID --summary`. This groups the final difference
   between the opening and submitted SSOT snapshots by the same stable object
   IDs used by element comments. It is a derived view, not a replacement for the
   exact changes. It lists every Figure, and groups objects with changes or
   comments. Read all Figure-level and object-level comments. Accepted Figures
   can still contain human edits that must be reproduced in source.
   If `data_changed` is true, inspect the full Figure checkpoint's binary
   references as well; equal axis bounds do not imply equal source arrays.
   For an object's exact operation list and before/after snapshots, use
   `feedback CACHE WORK_ID --figure FIGURE_ID --target OBJECT_ID`.
   Every summary property's `operation_ids` links to the original operations;
   inspect one with `--figure FIGURE_ID --change CHANGE_ID`. Keep IDs unchanged.
   The summary/detail object `target` is the editor/comment address. Raw diff
   `object_id` is a legacy grouping hint; use the explicit `target` for queries.
   Rich text character/style operations appear as one summary property. Read
   `formatting_changed` even when its displayed text is identical. A preview with
   `truncated: true` requires exact detail before reproducing that value. Unknown
   or shared ownership remains at Figure/panel scope; do not guess another target.
   `feedback CACHE WORK_ID` still returns the complete protocol-1 checkpoint
   when recovery or complete-state inspection requires it. Avoid dumping the
   full manifest or unchanged snapshots into the model context routinely.
   Read natural-language review comments
   separately, including right-click element comments addressed by stable object
   ID. They are instructions, not chart annotations. Binary references
   are recovery/input files; do not paste raw arrays into model messages.
   Check the event's `intent` before classifying any comment as a plot edit.
   `finish` requests saving and termination, not another review iteration.
   If the complete batch only asks to save/close/finish, route it to the same
   finish action even when submitted through the older Request changes button.
   A finish request on one Figure does not override another Figure's request
   for chart changes; resolve that complete batch before terminating.
   Do not infer a plot modification merely because a comment is nonempty.
4. Before editing source, run `claim CACHE WORK_ID --worker YOUR_STABLE_ID`.
   Keep its token and use one staging workspace/source writer for this session.
   If another worker holds the lease, wait or resume that worker. Reclaim expired
   leases after disconnect; never overwrite another active worker's source.
5. Inspect the recorded entry point/function, arguments, inputs and source digest.
   Preserve stable Figure IDs. Update runnable source to retain each exact human
   edit and satisfy the comments. Source builders use `build(session, **arguments)`
   and `session.figure(id=...)`; they do not start an agent or approve themselves.
   For finish-only feedback, save requested exports from the accepted checkpoint
   and reconcile any exact human edits into source. Then run
   `finish CACHE WORK_ID --claim-token TOKEN`. A recorded builder is rendered and
   checked against the exact accepted settings and binary data, without opening
   another review round. Do not call ordinary `regenerate` for an explicit finish
   request. Verify terminal `status`, then stop subscribing.
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
The controller presents only charts that still require approval. An accepted
chart whose persistent settings, DPI and source payloads are identical keeps
its approval; changed arrays require approval even if axis ranges are unchanged.
No vendor SDK is invoked by
subscription, and the agent must remain attached through its execution tools.
Closing an execution-tool connection does not discard pending durable feedback;
resume from the cache and last delivered work ID.
