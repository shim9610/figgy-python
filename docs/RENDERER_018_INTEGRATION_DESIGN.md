# Renderer 0.18 Python integration design

Status: implementation proposal for issue #16 in draft PR #19. Public API names
and the document envelope below are proposed contracts, not implemented APIs.
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

The current implementation has one `Axes(self)` per Figure. Axes setters mutate
the root configuration, `subplots` rejects multiple panels, settings-to-code
starts from `fig.axes[0]`, and one scaled export path calls a panel-only exporter.
The existing settings schema carries renderer settings but no persistent host
identities for panels or overlays. These assumptions must be removed together.

## Recommended decisions

### 1. One Figure owns one upstream document

Keep one global series list and one Figure-local data namespace, as upstream
requires. An Axes is a lightweight stable handle to a base panel, subplot or
secondary-Y layer; it does not own a separate renderer or duplicate config.
The root configuration remains the first visible panel. Additional panels use
upstream subplots; their overlays reference the same global series list.

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

### 3. Preserve legacy settings; add a versioned document envelope

Keep `get_settings` / `apply_settings` as compatibility APIs for renderer-shaped
settings. They must preserve the complete supported renderer document, including
subplots, overlays and annotations; they are not a base-panel-only projection.
Continue reading supported schema-1 settings from renderer 0.17 and 0.18.

Propose `get_document` / `apply_document` for a version-2 host envelope containing
the existing settings payload, persistent Figure/object identities and an
explicit envelope version. The settings payload is the sole owner of visual
properties and data references. Identity metadata must not copy axis settings,
series styles or annotation geometry into another authoritative tree.

Keep runtime revisions outside the persistent payload. Loading a saved document
into an existing Figure is a new mutation, not a reset of its revision counter.
Validate the payload and identity metadata together before accepting either.
Unknown required versions fail explicitly; never silently downgrade or drop
new fields. Legacy structural edits without identity metadata need a defined,
conservative handle invalidation policy before release.

Reason: changing the existing settings result unconditionally would break saved
scripts. A host envelope adds durable addressing without modifying upstream
types or duplicating their SSOT. This API is ordinary document I/O, not the
future LLM review API.

### 4. Use familiar constructors with explicit unsupported combinations

Extend `subplots` with grid construction, shared axes and `squeeze` behavior:
1x1 still returns a scalar Axes; one-dimensional grids return a one-dimensional
Axes array and general grids a two-dimensional array. `squeeze=False` always
returns a two-dimensional array. `fig.axes` stays a flat ordered sequence.
Provide explicit panel rectangles for manual layout, with deterministic initial
grid spacing. Do not introduce an automatic constrained-layout solver here.

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

### 6. Commit edits atomically with revision checks

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

Do not promise one revision per pointer gesture or change existing revision
semantics solely for review. Review diffs compare committed snapshots and can
coalesce many intermediate drag updates. Concurrent edits from two views must
be tested, including stale acknowledgements and deleted targets.

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

### 8. Distinguish settings replay from source-data reconstruction

Extend current Copy Python to address all panels and layers by stable ID and
apply a validated whole-document change to an existing compatible Figure.
Do not sequentially reset a dependent model into an invalid intermediate state.
Generate readable calls where practical and preserve remaining supported SSOT
fields through a validated configuration payload. Reject missing/mismatched
objects instead of applying a partial result. Define whether transient selection
is restored separately from visual/style equivalence.

Settings replay does not reconstruct unavailable NumPy arrays. Complete standalone
code requires the caller's original plotting/data recipe or an explicitly
supplied data source; never recover all arrays by GPU readback or permanent
native CPU caching. For future LLM regeneration, explicit user-provided stable
IDs reconnect new code to review targets; labels are not a substitute.

Reason: the current native data lifetime deliberately does not retain source
arrays, and claiming standalone reproducibility from settings alone would be
incorrect. Existing manual Copy Python remains useful and compatible.

### 9. Make CI prove complete feature paths

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
