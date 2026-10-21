# Renderer 0.18 Python integration design

Status: implementation design for issue #16 in draft PR #19, incorporating
architecture review feedback. The ordinary plotting implementation is described
in [the feature guide](RENDERER_018_FEATURES.md); local validation is recorded
in [host verification](HOST_VALIDATION.md#renderer-018-feature-integration-2026-10-20).
Review-session APIs, the feedback protocol and binary recovery cache remain
design requirements for #18 and are not implemented in this PR.
Compatibility work for #15 is the existing implementation baseline.

## Scope and existing constraints

Expose all supported 0.18 capabilities through Python, native windows and
Jupyter WebGPU, including configuration, interaction, complete-document export
and reproducible settings code. Comprehensive editor control coverage belongs
to #17; the opt-in LLM review controller and companion skill belong to #18.
Basic editing and interaction needed to use each new feature remain part of #16.

Ordinary plotting must continue without a review session, LLM, agent or approval
step. The review controller will use a separate API and lifecycle. Human review
comments must remain separate from both chart annotations and settings diffs.

Reuse the pinned upstream model and public renderer APIs. Preserve resident GPU
data, binary notebook transfers and existing source-array lifetime guarantees.
Do not add a second chart engine, permanent native CPU data copies or streaming.

Before this integration, each Figure had one `Axes(self)`. Axes setters mutated
the root configuration, `subplots` rejected multiple panels, settings-to-code
started from `fig.axes[0]`, and one scaled export path called a panel-only exporter.
Schema 1 carried renderer settings without persistent host identities for panels
or overlays. The integration replaces these assumptions together.

## Accepted decisions

### 1. Figure owns subplots; subplots own their local axes

Expose Figure -> Subplot -> Axes ownership. Each subplot owns its local
coordinate system, axes, title, legend and series membership. Figure owns the
document layout, shared-axis groups and data resources. A shared-axis group
owns the linked range/scale/direction/tick state; member-specific axis text and
visual style remain local. A secondary Y axis belongs to its parent subplot.

Map that logical ownership onto upstream's one global series list, Figure-local
data namespace and index-based links. Axes handles resolve stable targets; they
do not create separate renderers or duplicate authoritative chart config. The
root configuration remains the first visible panel, and additional panels use
upstream subplots. The adapter must not expose that storage asymmetry as a
different ownership model for the first panel.

An explicit Axes receiver always determines a Python mutation target. Changing
the selected panel in a window must not redirect a later `ax.plot(...)` call.
Keep existing pyplot behavior compatible; explicit current-Axes selection can
be added for multiple panels without binding it to transient pointer selection.

Reason: this follows upstream ownership, preserves GPU sharing and prevents
edits to a second panel from silently changing the first panel.

### 2. Persist identity independently of array position

Give each document a persistent logical Figure ID, independent of its process
GPU allocation ID. Give panels and overlays opaque Figure-local IDs; retain
existing series IDs and use upstream annotation IDs. Accept explicit IDs for
replay, assign missing IDs once, reject duplicates and never recycle IDs after
deletion. Category/series IDs already used by bounded families remain stable.

Store only address/identity metadata alongside the upstream model. Resolve IDs
to current `LayerRef`/`CellRef` indices at the renderer boundary. Reordering a
panel must preserve its identity and rewrite index references atomically;
deletion must invalidate its old Python handles. Reject ambiguous structural
replacement instead of guessing identity from a title, style or array index.

Series IDs remain unique within a Figure, including across panels. Human labels
may repeat. Reference fills must name an existing compatible series in the same
coordinate layer; removal of a referenced object fails unless dependencies are
explicitly resolved in the same transaction.

Reason: saved edits and future LLM feedback must continue to refer to the same
object after reordering. Visible names and renderer indices cannot guarantee it.

### 3. Extend the existing settings API with an explicit schema version

Keep one `get_settings` / `apply_settings` API for the complete document. Extend
its versioned schema with persistent Figure/object identities, layout slots,
placement and shared-axis relationships. Do not introduce a second document
API merely to preserve the exact shape of the initial package's settings.
Schema-1 inputs from renderer 0.17/0.18 should migrate where practical; write
the new canonical schema after migration. Document structural changes explicitly.

The upstream settings payload remains the sole owner of visual properties and
data references. Host metadata must not duplicate axis ranges, series styles
or annotation geometry into another authoritative tree. Logical shared-axis
ownership resolves to upstream's canonical linked values at the adapter boundary.

Automatic/fixed tick intent uses optional `identity.tick_modes` entries keyed
by persistent panel or overlay IDs. The upstream model stores numeric spacing,
but does not retain that intent; axis values therefore remain in the upstream
configuration. Named shared-axis groups share primary tick intent and spacing.
A spacing-only member edit is applied to the shared root before upstream link
synchronization, which otherwise restores the root spacing. Opposite-edge
styling and secondary axes keep their existing local ownership.

Keep runtime revisions outside the persistent payload. Loading a saved document
into an existing Figure is a new mutation, not a reset of its revision counter.
Validate the payload and identity metadata together before accepting either.
Unknown required versions fail explicitly; never silently downgrade or drop
new fields. Legacy structural edits without identity metadata need a defined,
conservative handle invalidation policy before release.

Reason: this early release can adopt a coherent schema without maintaining two
overlapping public APIs indefinitely. Migration support is useful, but preserving
every initial field shape is not a reason to fragment document persistence.
The extended settings API is ordinary document I/O, not the future LLM review API.

### 4. Expose ID-addressed grid slots and explicit capability guards

Make an ID-addressed grid the primary layout abstraction. Expose subplots through
a mapping keyed by stable subplot ID; expose slot placement through a mapping
from stable slot ID to subplot ID. Slot identity and subplot identity are
distinct, so moving a subplot preserves its series, links and replay targets.
Repeated slot labels may describe rectangular spans. Validate missing IDs,
duplicate placements, nonrectangular spans and invalid row/column weights before
mutation. Support empty slots, spacing and explicit panel rectangles. Resolve
grid geometry on layout changes, not per data sample or by reuploading arrays.

Extend `subplots` with grid construction, shared axes and `squeeze` behavior:
1x1 still returns a scalar Axes; one-dimensional grids return a one-dimensional
Axes array and general grids a two-dimensional array. `squeeze=False` always
returns a two-dimensional array. `fig.axes` stays a flat ordered sequence.
Keep deterministic initial grid spacing. Do not introduce an automatic
constrained-layout solver here.

Propose polar construction through an Axes projection option and secondary Y
through `ax.twinx()`. The latter shares the parent X mapping and plot rectangle;
it is not an independent overlapping panel. Proposed feature entry points include
`quiver`, mapped `scatter`, `step`, fill configuration, radar construction and
annotation constructors. Exact keyword names need mapping to upstream validation
and existing Figgy units before implementation; resemblance to Matplotlib must
not imply complete Matplotlib compatibility.

Upstream subplot documents contain Cartesian/polar panels only. Bounded pie,
bar, boxplot and radar documents cannot be inserted into that subplot list.
Polar restrictions on vectors, fields, errorbars and overlays remain explicit.
Publish a feature/combination matrix and reject unsupported requests before
uploads or mutation. Do not silently convert a family or discard a panel.

The upstream document has one annotation layer in the parent panel's area;
subplot-local annotation layers are explicitly unsupported. Polar annotation
spaces support ratio anchors, but not Cartesian data anchors/reference lines/
spans. Expose these limits accurately. Independent data-anchored annotations
on every subplot require an upstream extension, not a Python-side substitute.

Reason: existing Python conventions reduce learning effort, while explicit
limits avoid promising combinations that the renderer cannot represent.

### 5. Let the upstream model resolve links and composition

Maintain shared-axis groups with upstream link synchronization. An accepted
range edit to any linked member propagates through its root; axis text and
other unlinked styling remain local. Translate stable link references to valid
upstream parent/earlier-subplot references without cycles. Fit must consider
the relevant linked group, not accidentally fit only the root series.

Use complete-document native rendering/export APIs and upstream panel expansion
for display. Audit precise/stylized rendering, non-unit scale, DPI, background,
surface clipping, pointer mapping, fit, picking and warnings together. Browser
rendering/export must use the same document meaning. A whole-document export
must include every panel and overlay regardless of the active interaction layer.

Persist chart panel geometry in the document. OS window placement, monitor and
window size are view/session metadata; moving a window must not mutate the
chart's exported layout. Keep logical document dimensions separate from display
scale and viewport resizing.

Reason: merely looping over existing single-panel paths can clip the canvas,
misroute input or erase the GPU residency/cache improvements of 0.18.

The 0.18 registry validates mapped series against the root colorbar before
expanding subplots. When only a child has a colorbar, both hosts derive an
invisible root validation context from it at the GPU/WASM boundary. The context
is excluded from saved settings; the child's colorbar remains authoritative.
Config-only browser edits retain the registered series so resident body caches
remain usable. The root-polar registry restriction on non-polar series is guarded
explicitly, as documented in the feature guide.

### 6. Separate manual mutations from turn-based review approval

Route Python calls and both manual editors through the same validation and
commit contract. One accepted logical operation commits settings, series
references and identity changes together, advances the existing Figure revision
and notifies all hosts. Rejected operations preserve settings, identities,
revision and visible data; new uploads must be rolled back on failure.

Keep optimistic `expected_revision` checks. Conflicting edits fail with the
current revision and affected target information; do not automatically merge
overlapping changes. In Jupyter, local interaction remains responsive and
coalesced; synchronize accepted state through the existing acknowledgement
protocol. Flush pending local edits before taking a review/export snapshot.

Inline annotation text is a normal manual edit with a host-local input buffer.
Native and notebook hosts own focus, IME/keyboard handling, confirmation and
cancellation; the renderer supplies anchor transforms, hit testing and geometry.
Typing does not create an annotation or a document revision. Confirmation applies
one edit against the current document, preserving unrelated properties and
checking the original annotation by stable ID. A changed or deleted target is
rejected. Browser text hit testing waits for current prepared geometry after state
acknowledgements rather than querying a cleared or outdated annotation map.

Ordinary manual mode retains immediate accepted mutations. In review mode,
edits update a draft shown in the window; approval seals the accepted turn.
Flush edits, durably checkpoint the approved state, then close that window.
Trigger the LLM once all required windows in the batch have approved. Keep the
original turn's baseline and separate review comments in the checkpoint. The
LLM's next result is a new turn, not a concurrent writer into a closed window.

Do not promise one revision per pointer gesture or change existing revision
semantics solely for review. Review diffs compare approved snapshots and can
coalesce intermediate drag updates. Ordinary host synchronization still needs
stale-acknowledgement and deleted-target tests; it must not dictate a permanently
live, concurrently edited LLM session.

Reason: a style change and its referenced colorbar or series cannot be exposed
as invalid intermediate states. Revision checks prevent delayed browser or
agent responses from overwriting newer manual work.

### 7. Define the future review diff without implementing its controller

Reserve a change representation containing document ID, baseline and resulting
revision, stable target ID, property path, operation and before/after values.
Represent create/delete/reorder/link changes explicitly, rather than replacing
the whole array whenever one item moves. Separate authored changes from
derived link/fit values. Keep hover, pointer position, temporary selection chrome
and active-tool changes out of the default review diff; preserve them in the
renderer state wherever required for normal host operation.

Diffs reference resident source columns and their metadata; they do not include
entire source arrays. Retain exact accepted SSOT values and deterministic paths,
not only a natural-language summary. A schema-backed example of changing a
panel Y range is: target panel ID, path `left_y.max`, old value, new value and
the revisions of the compared snapshots. Concrete diff serialization remains
part of #18 and must not be advertised as implemented by #16.

The future review controller owns review comments, per-window approval,
multi-window batch completion, agent code regeneration and redisplay. Its
companion skill should consume a documented versioned protocol, not inspect
private Python objects or control the UI by coordinates. No review metadata or
agent dependency is required to show an ordinary Figure.

Reason: raw renderer JSON diffs use unstable indices and contain transient UI
noise. Stable targets plus a known baseline make feedback usable by an LLM,
while separate comments preserve the distinction between instructions and
edits that already happened.

### 8. Persist review data in a program-managed temporary binary cache

The opt-in review mode writes source data to temporary binary storage at input
time, while the original buffers are available. Preserve dtype, shape and column
identity, and record file sizes/integrity information in the manifest. Native
rendering still retains no permanent CPU array copies; settings-only edits reuse
immutable cached data instead of serializing the same arrays on every revision.
Bounded-family values, layouts, stable IDs and all data needed to restore a
document must be covered, not only plotted X/Y columns. Review-mode notebook
transfer release must not remove the durable cache needed for recovery.

Approval creates a checkpoint with session/batch/document/turn IDs, baseline and
accepted settings, diff, separate comments and references to binary data. Write
and flush payloads first; atomically publish a complete manifest last. Keep the
window open if publication fails. Only after that publication may the window
close and a ready signal be delivered. Signals identify the manifest and turn;
the LLM reads the structured feedback, without receiving raw arrays in its text
context. Duplicate delivery uses the same work ID and must not trigger a second
independent turn. Resume pending work by scanning durable manifests after a
disconnect; delivery must not depend on a single in-memory event.

Cache maintenance belongs to application code, never to LLM cleanup commands.
After publishing a complete higher revision in the same document lineage, the
program reclaims superseded checkpoints and unreferenced data. Run maintenance
also on restart and cache access, so a missed cleanup is repaired automatically.
An unfinished higher revision is not a replacement for the last valid one.

Keep the newest complete recoverable revision, every file it references and
any approved feedback still needed by an unfinished turn. New checkpoints must
contain or retain the baseline required to interpret their diffs; they cannot
depend on deleted revision deltas. Never compare unrelated Figures' revision
counters. Coordinate publication, readers and reclamation so maintenance cannot
remove an active read or a file being committed. Shared immutable data is removed
only when no retained checkpoint needs it. No LLM acknowledgement is required
to reclaim genuinely superseded, unreferenced files.

Reason: durable binary caching makes recovery independent of Python process
memory, live GPU allocations and agent connectivity. Revision-driven cleanup
also recovers from missed explicit finalization without deleting the latest
recoverable work or arrays reused by the next turn.

This checkpoint/review lifecycle belongs to #18. #16 must establish stable
settings and data-reference boundaries that permit it, without making temporary
review persistence mandatory for ordinary manual plotting.

### 9. Distinguish settings replay from source-data reconstruction

Extend current Copy Python to address all panels and layers by stable ID and
apply a validated whole-document change to an existing compatible Figure.
Do not sequentially reset a dependent model into an invalid intermediate state.
Generate readable calls where practical and preserve remaining supported SSOT
fields through a validated configuration payload. Reject missing/mismatched
objects instead of applying a partial result. Define whether transient selection
is restored separately from visual/style equivalence.

Settings replay does not reconstruct unavailable NumPy arrays. Complete standalone
code requires the caller's plotting/data recipe or an explicit data source, which
may be the review mode's binary cache while it exists. Cache-backed recovery must
not be described as a permanently portable standalone script. Never recover all
arrays by GPU readback or permanent native CPU caching. For LLM regeneration,
explicit user-provided stable IDs reconnect new code to review targets; labels
are not a substitute.

Reason: the current native data lifetime deliberately does not retain source
arrays, and claiming standalone reproducibility from settings alone would be
incorrect. Existing manual Copy Python remains useful and compatible.

### 10. Make CI prove complete feature paths

Keep both existing required check names. Increase the Linux integration job's
time budget before expanding coverage, and measure build/setup/test duration
separately. At baseline commit `05b42a4`, workflow run `39413027581` logged
`350 passed in 1072.38s`, but the job ended cancelled at its 30-minute boundary
after setup/build and an additional priority test pass. This is not a successful
required check. Prefer caching and splitting independent test groups with an
aggregate required gate if suite growth justifies it; do not remove host tests,
make missing prerequisites pass, or equate local success with green CI.

For each supported feature, verify construction, native and browser rendering,
configuration, relevant picking/editing, settings/document round trips and
generated-code replay. Add mixed-document cases, linked edits, same-ID isolation
between Figures, active-layer routing and invalid-combination rollback. Test
whole-document exports at multiple scales. Extend shared interaction parity
scenarios for behavior changes in both hosts in the same PR.

Linux CI software GPUs are the initial automated gate. Record physical GPU and
Windows/macOS validation separately; a Linux pass does not establish it.

## Implementation sequence

1. Finalize the document/identity and compatibility contracts, then implement
   stable Axes addressing and transactional settings/document operations.
2. Add whole-document native/browser display, export, fit and code replay with
   multi-panel and secondary-Y ownership tests.
3. Integrate feature groups: mapped points and vectors; fills and steps; polar
   and radar; annotations and bounded titles; legend behavior and capability
   errors. Include both hosts and examples in each group.
4. Run full CI, complete the published capability matrix and update the draft
   PR description around its final scope. Keep it draft until explicitly
   approved for review readiness. No release or merge is part of this work.

Feature groups are not complete until their full supported host/export/replay
path passes. This design does not mark any new public API as shipped.
