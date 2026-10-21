/* tslint:disable */
/* eslint-disable */

/**
 * Exact range selected by the renderer-owned automatic cursor.
 */
export class AutoStreamingRangeRequestResult {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    same_selection_request(other: AutoStreamingRangeRequestResult): boolean;
    readonly encodings: string[];
    readonly lengths: Float64Array;
    readonly offsets: Float64Array;
    readonly pending_latest: boolean;
    readonly revision: string;
    readonly source_ids: string[];
    readonly source_lengths: Float64Array;
    readonly source_revisions: Float64Array;
    readonly status: string;
    readonly submitted_primitives: number;
    readonly total_primitives: number;
}

/**
 * Result of asking the renderer to start or coalesce one automatic draw.
 */
export class AutoStreamingRequestResult {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    readonly job_id: string | undefined;
    readonly pending_latest: boolean;
    readonly revision: string;
    readonly source_ids: string[];
    readonly source_revisions: Float64Array;
    readonly status: string;
    readonly submitted_primitives: number;
    readonly total_primitives: number;
}

/**
 * Axis frame presets (mirror of `model::AxisPreset`).
 */
export enum AxisPreset {
    BoxedInward = 0,
    BoxedOutward = 1,
    OpenOutward = 2,
    OpenInward = 3,
    Minimal = 4,
}

/**
 * Series color rotations (mirror of `model::ColorCycle`).
 */
export enum ColorCycle {
    Classic = 0,
    Vivid = 1,
    Balanced = 2,
    ColorblindSafe = 3,
    Monochrome = 4,
}

export class FiggyBoundedChart {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    /**
     * The layer that receives pointer interaction, as JSON.
     */
    active_layer(): string;
    /**
     * Append an `Annotation` JSON value and return its index.
     */
    add_annotation(json: string): number;
    /**
     * The compass name of the annotation's live handle under a point.
     */
    annotation_handle(index: number, x: number, y: number): string | undefined;
    /**
     * Annotations the current frame skipped, as `[{index, reason}]`.
     */
    annotation_warnings(): string;
    /**
     * The drawn annotations as JSON: `index`, `id`, `kind`, the selection
     * box `rect` and `handles`, and `selected`. Skipped items are listed by
     * `annotation_warnings` instead.
     */
    annotations(): string;
    clear_selection(): void;
    /**
     * One GPU surface; no kernel PNG transport is used for interactive frames.
     */
    static create(canvas: HTMLCanvasElement, family: string, value: string, width: number, height: number): Promise<FiggyBoundedChart>;
    /**
     * Renderer-measured logical pixel bounds and resize handles.
     */
    decorations(): string;
    drag(target: string, dx: number, dy: number, handle?: string | null): boolean;
    /**
     * Move an annotation, or one of its handles, by a pointer delta.
     * Returns `false` for a rejected move; the document is unchanged then.
     */
    drag_annotation(index: number, dx: number, dy: number, handle?: string | null): boolean;
    export_png(scale: number): Promise<Uint8Array>;
    /**
     * Submit one frame and wait for actual GPU completion. Hosts must await
     * this before publishing Ready; rejected completion (including device
     * loss) is returned to the caller instead of reporting an unusable chart.
     */
    first_frame_ready(): Promise<void>;
    frame(): void;
    get_document(): string;
    /**
     * Observe completion of work already submitted to this chart's GPU queue.
     * The returned Promise owns a queue clone, not a borrow of this chart.
     * Hosts may keep processing edits while waiting, and should coalesce
     * display submissions until it settles. Device loss rejects the Promise.
     */
    gpu_ready(): Promise<any>;
    /**
     * The topmost drawn annotation under a point, as its index.
     */
    hit_annotation(x: number, y: number): number | undefined;
    /**
     * The topmost decoration under a point, as its stable id. While the
     * annotation layer is active (and shown) its drawn items sit on top of
     * every decoration and answer as `"annotation_<n>"`; on the base layer
     * they are not registered and clicks pass through them.
     */
    hit_decoration(x: number, y: number, edit_area: boolean): string | undefined;
    hover(x: number | null | undefined, y: number | null | undefined, dt: number): boolean;
    pick(x: number, y: number, toggle: boolean): string;
    /**
     * The `Anchor` JSON at a point for `"Data"` or `"Ratio"`; `null` when
     * the point has no such position (a radial chart has no data anchors).
     */
    pointer_to_anchor(x: number, y: number, kind: string): string;
    /**
     * Remove the annotation at `index`; later indices move down one and the
     * selection follows or clears.
     */
    remove_annotation(index: number): void;
    resize(width: number, height: number): void;
    resize_handle(target: string, x: number, y: number): string | undefined;
    /**
     * Select one annotation (`decorations.selected = Annotation(index)`) or
     * none. Clears the data and decoration selections like
     * `select_decoration`.
     */
    select_annotation(index?: number | null): void;
    /**
     * Select a decoration by the id `hit_decoration` reported, or none.
     * An `"annotation_<n>"` id selects that drawn annotation
     * (`decorations.selected = Annotation(n)`).
     */
    select_decoration(target?: string | null): void;
    selected_annotation(): number | undefined;
    /**
     * Set the layer that receives pointer interaction: `"Base"` or
     * `"Annotations"` as JSON (bounded charts have no overlays, so an
     * `{ "Overlay": n }` is stored as `"Base"`). A change clears the
     * decoration selection (`decorations.selected`, an annotation
     * included); the data selection is kept. Returns the stored layer as
     * JSON. Drawn pixels never depend on it.
     */
    set_active_layer(json: string): string;
    /**
     * Replace the annotation at `index`.
     */
    set_annotation(index: number, json: string): void;
    /**
     * Show or hide the whole annotation layer without re-rasterizing it.
     */
    set_annotations_visible(visible: boolean): void;
    /**
     * Validate and prepare before replacing the SSOT, retaining the old chart on failure.
     */
    set_document(value: string, width: number, height: number): void;
    step_selection(backwards: boolean): void;
}

export class FiggyChart {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    /**
     * The layer that receives pointer interaction, as JSON, with the
     * out-of-range fallback applied.
     * JS: `JSON.parse(chart.active_layer())`
     */
    active_layer(): string;
    /**
     * Append an `Annotation` (JSON, the same shape as in `get_config`)
     * and return its index.
     */
    add_annotation(json: string): number;
    /**
     * Register or update a line series over two registered columns.
     *
     * Upsert by `series_id`: a new id takes the next color of the active
     * cycle; an existing id is replaced in place and keeps its color.
     * Non-empty `label` adds/updates the legend row.
     */
    add_line_series(series_id: string, x_column: string, y_column: string, line_width: number, label: string): void;
    /**
     * The compass name (`"W"`, `"E"`, ...) of the annotation's handle
     * under a point, or none. Only the handles `annotations` lists are
     * live: a span's two edges, a line's two value handles, an arrow's
     * two endpoints.
     */
    annotation_handle(index: number, x: number, y: number): string | undefined;
    /**
     * Annotations the current raster skipped, as `[{index, reason}]`
     * with `reason` one of `NonFinite`, `NoValueAxis`, `OutOfRange`,
     * `EmptyText`.
     */
    annotation_warnings(): string;
    /**
     * The drawn annotations of the current frame as JSON: `index`, `id`,
     * `kind`, the selection box `rect` and its `handles` in physical
     * canvas pixels, and `selected`. Items the raster skipped are
     * absent here and listed by `annotation_warnings`.
     */
    annotations(): string;
    /**
     * Apply an axis frame preset to all four axes (decoration-only).
     */
    apply_axis_preset(preset: AxisPreset): void;
    /**
     * Switch the series color rotation: recolors every series in order,
     * rebuilds their GPU styles, and keeps legend swatches in sync.
     */
    apply_color_cycle(cycle: ColorCycle): void;
    /**
     * Fit the axes of the active layer to the union of that layer's
     * series, leaving a uniform `padding` fraction of the data span as
     * margin on each side (`0.0` = no padding, `0.05` = 5%
     * top/bottom/left/right). This is the whole fit policy — no rounding
     * of the range ends; ticks land on nice values inside the range by
     * themselves. Hosts should call this instead of re-deriving ranges.
     *
     * The active layer (`set_active_layer`) decides which axes move:
     * `Base` and `Annotations` fit the parent's `bottom_x` and `left_y`,
     * `Subplot(i)` fits subplot `i`'s, and `Overlay(n)` /
     * `SubplotOverlay(i, n)` fit that overlay's Y axis only. An axis fits
     * every series drawn against it (`Config::layer_of_series`). A linked
     * axis (`link_x`, `link_y`) is one axis shared by its link group: it
     * fits the series of every chart in the group and the range moves
     * the whole group, whichever member is active. X and Y links are
     * followed separately. An overlay shares its chart's X axis and has
     * its own Y axis, so its series count towards that X axis and not
     * towards `left_y`. An axis that is not linked fits its own chart's
     * series only; to fit every layer, set each layer active in turn and
     * call this again.
     *
     * Each series contributes its exact original GPU primitive domain:
     * valid adjacent segments for line-only mode, paired finite points
     * for point-bearing modes, and enabled error endpoints. The reduction
     * is compiled on first fit (`createComputePipelineAsync` on wasm)
     * and cached by the normalized mode plus role-specific column
     * revisions. Matrix-backed series use the same engine to return the
     * exact cell/sample-lattice bounds; only histograms remain a metadata
     * union because their uploaded edge column already is their geometry.
     * Series registration itself does not submit GPU work.
     */
    auto_fit_all(padding: number): Promise<void>;
    /**
     * Fit the shared z axis to every column the colourbar maps: matrix
     * value columns, scatter `point_color_map` columns and vector colour
     * maps. A chart without a colourbar is left unchanged.
     */
    auto_fit_colorbar(padding: number): void;
    /**
     * Fit overlay layer `layer`'s Y axis to a column's cached statistics
     * with proportional padding, the overlay counterpart of `auto_fit_y`.
     * A layer index past the overlay list is an error.
     * JS: `chart.auto_fit_overlay_y(0, "pressure", 0.05)`
     */
    auto_fit_overlay_y(layer: number, column: string, padding: number): void;
    /**
     * Fit subplot `index`'s X (`axis = "x"`) or Y (`axis = "y"`) axis to
     * the union of the given columns' cached statistics with
     * proportional padding. A linked axis moves its whole link group.
     * An index past the subplot list or another axis name is an error.
     * JS: `chart.auto_fit_subplot(0, "y", ["flow"], 0.05)`
     */
    auto_fit_subplot(index: number, axis: string, columns: string[], padding: number): void;
    /**
     * Fit the x axis to a column's range with proportional padding.
     */
    auto_fit_x(column: string, padding: number): void;
    auto_fit_y(column: string, padding: number): void;
    /**
     * Reserve or inspect the next exact range request. Repeated calls
     * return the same ranges until `auto_stream_chart_submit_ranges`.
     */
    auto_stream_chart_request_ranges(): AutoStreamingRangeRequestResult;
    /**
     * Advance at most one renderer-selected automatic chunk. The typed
     * arrays are borrowed only for this call.
     */
    auto_stream_chart_step(ids: string[], revisions: Float64Array, sources: Array<any>): StreamingStepResult;
    /**
     * Submit exactly the typed-array chunks named by the pending range
     * request. The arrays are borrowed for this call only.
     */
    auto_stream_chart_submit_ranges(ids: string[], revisions: Float64Array, source_lengths: Float64Array, offsets: Float64Array, sources: Array<any>): StreamingStepResult;
    /**
     * Begin an independent replay of the completed stream. The facade
     * supplies only renderer-requested ranges between these calls.
     */
    begin_stream_export(scale: number, max_primitives_per_chunk: number): StreamingOperationHandle;
    /**
     * Compatibility entry point; always rejects without requesting ranges.
     */
    begin_stream_pick_data(_x: number, _y: number, _max_distance_px: number, _max_primitives_per_chunk: number): Promise<StreamingOperationHandle>;
    /**
     * Compatibility entry point. Nonresident picking is disabled because
     * exact source replay can take as long as the original render.
     */
    begin_stream_pick_point(_x: number, _y: number, _max_distance_px: number, _max_primitives_per_chunk: number): Promise<StreamingOperationHandle>;
    /**
     * Start or restart this chart's exact streaming surface and renderer-
     * owned CPU cursor. No LOD or downsampling is performed.
     */
    begin_streaming(max_primitives_per_chunk: number): void;
    cancel_stream_operation_and_wait(handle: StreamingOperationHandle): Promise<void>;
    cancel_streaming(): void;
    /**
     * Cancel this chart and resolve only after its submitted work and
     * retired renderer-owned surfaces have crossed the completion fence.
     */
    cancel_streaming_and_wait(): Promise<void>;
    /**
     * Configure the total GPU budget and chart-local packed-view limit.
     * Automatic streaming keeps original sources nonresident, then caches
     * only source rows whose geometry reaches the current view when the
     * completed packed view fits both limits.
     */
    configure_auto_residency(memory_budget_bytes: number, working_set_limit_bytes: number): void;
    /**
     * Install the renderer's bounded streaming resources once.
     * Byte limits are JavaScript safe integers; no source payload is retained.
     */
    configure_streaming(max_active_charts: number, max_in_flight_chunks: number, max_columns_per_chunk: number, max_chunk_input_bytes: number, max_in_flight_gpu_bytes: number): void;
    /**
     * Bind the low-level chart kernel to `canvas` (uses the canvas's
     * current pixel size). Ordinary web hosts should prefer
     * `figgy-chart.js` and its `<figgy-chart>` Custom Element.
     * JS: `const chart = await FiggyChart.create(canvas);`
     */
    static create(canvas: HTMLCanvasElement): Promise<FiggyChart>;
    /**
     * Same as [`Self::create`], reporting each init stage to `on_event`
     * as `{ scope, stage, phase }`. Do not call other kernel methods
     * from the callback.
     */
    static create_with_progress(canvas: HTMLCanvasElement, on_event: Function): Promise<FiggyChart>;
    /**
     * Renderer-measured decoration bounds in physical canvas pixels.
     * An `"annotation_<n>"` id that `hit_test` reports resolves to the
     * drawn item's selection box.
     */
    decoration_bounds(target: string): string;
    /**
     * Normalize a complete referenced-column closure from resident or
     * mixed authority to exact streamed metadata. The typed arrays are
     * borrowed only for the atomic transition and are not retained by
     * Rust; the high-level JS executor keeps the replayable references.
     */
    demote_auto_resident_columns(ids: string[], revisions: Float64Array, sources: Array<any>): void;
    discard_stream_selection_request(request: AutoStreamingRangeRequestResult): void;
    /**
     * Move an annotation, or one of its handles, by a pointer delta in
     * physical canvas pixels. The delta is converted back into the
     * item's anchors through the frame's anchor space and written to
     * the config; a move that would leave the plot or panel is rejected
     * and returns `false`.
     */
    drag_annotation(index: number, dx: number, dy: number, handle?: string | null): boolean;
    /**
     * Compile the drawable-series fit-bound engine without drawing. On wasm
     * this uses `createComputePipelineAsync`. Series registration does
     * not do this; `auto_fit_all` does.
     */
    ensure_extent_engine(): Promise<void>;
    /**
     * Export the document as PNG bytes at `scale ×` resolution: the base
     * layer and every overlay layer composited into one image, exactly
     * as the canvas shows them. A document without overlays exports the
     * same bytes as the per-panel renderer export.
     * JS: `const png = await chart.export_png(2.0);`
     * Holds a mutable borrow of this WASM object until the Promise settles.
     * wasm-bindgen checks borrows; it does not queue concurrent calls.
     * While awaiting export, the host must prevent every other call on the
     * same object, including frame(), getters, edits, resize, picking and free().
     * Overlapping access can throw "recursive use of an object". Release the
     * host's per-instance operation gate in finally on success or rejection.
     * The example `<figgy-chart>` facade supplies that gate and rejects competing
     * application calls; raw FiggyChart callers must manage it themselves.
     * Automatic contour placement validates `spacing_px * scale` after the
     * export scale is clamped. Explicit placement does not multiply spacing.
     * Scale-product overflow or an atlas beyond the adapter texture limit
     * rejects the export before contour GPU state changes.
     */
    export_png(scale: number): Promise<Uint8Array>;
    finish_stream_export(handle: StreamingOperationHandle): Promise<Uint8Array>;
    /**
     * Compatibility entry point; no streamed pick operation can start.
     */
    finish_stream_pick_data(_handle: StreamingOperationHandle): Promise<any>;
    /**
     * Compatibility entry point; no streamed pick operation can start.
     */
    finish_stream_pick_point(_handle: StreamingOperationHandle): Promise<any>;
    /**
     * Submit the current chart if it is dirty, then wait until that GPU
     * work has finished. Hosts should keep a loading overlay up until
     * this resolves. The wait does not remove a main-thread Dawn/driver
     * freeze; it only reports first-submit completion.
     *
     * JS: `await chart.first_frame_ready();`
     */
    first_frame_ready(): Promise<void>;
    /**
     * Process pending pool maintenance and draw only when visual state is
     * dirty. A clean rAF tick returns before touching the pool or surface.
     */
    frame(): void;
    /**
     * Serialize the full chart option SSoT to a JSON string.
     * JS: `const cfg = JSON.parse(chart.get_config());`
     */
    get_config(): string;
    /**
     * Serialize the series declarations (columns, render type, styles).
     */
    get_series(): string;
    /**
     * Read-only accounting. These are requested GPU allocations, not a
     * driver VRAM measurement; retired bytes remain charged until the
     * queue completion callback fires.
     */
    gpu_memory_status(): string;
    /**
     * Observe completion of work already submitted to this chart's GPU queue.
     * The returned Promise owns a queue clone, not a borrow of this chart.
     * Hosts may keep processing edits while waiting, and should coalesce
     * display submissions until it settles. Device loss rejects the Promise.
     */
    gpu_ready(): Promise<any>;
    /**
     * `true` while a chart element or an annotation is selected.
     */
    has_selection(): boolean;
    /**
     * The topmost drawn annotation under a point in physical canvas
     * pixels, as its index.
     */
    hit_annotation(x: number, y: number): number | undefined;
    /**
     * Hit-test the chart chrome at canvas pixel `(x, y)` — returns the
     * topmost element's stable id (`"data_area"`, `"axis_bottom"`,
     * `"tick_labels_left"`, `"axis_title_left"`, `"colorbar"`,
     * `"colorbar_axis"`, `"colorbar_tick_labels"`,
     * `"colorbar_title"`, …) or `null`. Pure geometry, no selection state
     * change: the renderer's own layout answers, so hosts don't have to
     * re-derive box positions for hover cursors / context UI. The set of
     * registered elements follows the active layer: while an overlay is
     * active its elements answer as `"overlay_<n>:axis_right"`,
     * `"overlay_<n>:tick_labels_right"`, `"overlay_<n>:axis_title_right"`
     * and `"overlay_<n>:legend"`, and the base Y axes do not answer.
     * While the annotation layer is active (and shown) its drawn items
     * sit on top and answer as `"annotation_<n>"`; on every other layer
     * they are not registered and clicks pass through them.
     */
    hit_test(x: number, y: number): string | undefined;
    /**
     * Metadata-only admission for incoming columns; no payload is read,
     * registered, uploaded, or reserved. Chart-derived buffers are excluded.
     */
    inspect_column_admission(lengths: Float64Array): string;
    /**
     * Queue cancellation only when an automatic stream is active.
     */
    interrupt_render(): string;
    /**
     * Load the bundled demo (sine + RC charge curves) — lets a frontend
     * see a real chart without wiring data first. Repeated calls replace
     * the demo registrations and keep the same series declarations.
     */
    load_demo(): void;
    /**
     * Move among source rows represented in the completed packed view.
     * Returns only the original source index; no source or GPU readback.
     */
    next_view_point_index(source_id: string | null | undefined, series_id: string, current: number, forward: boolean): any;
    /**
     * Pointer move with frame delta — drags or resizes the selection.
     * After a press on an annotation the delta moves that item (or the
     * pressed handle) through the frame's anchor space.
     */
    on_move(dx: number, dy: number): void;
    /**
     * Pointer press. Returns `true` while something is selected.
     * The host can mirror that state in its own UI.
     *
     * The press follows the active layer's route: while the annotation
     * layer is active (and shown), the selected annotation's handles win
     * first, then a drawn item under the point is selected (clearing
     * the element selection) and dragged by `on_move`; a press that
     * misses every item falls through to the shared elements below and
     * clears the annotation selection. On every other layer the items
     * are not part of the route.
     */
    on_press(x: number, y: number): boolean;
    on_release(): void;
    /**
     * Pick the nearest visible data primitive at canvas pixel `(x, y)`;
     * equal-distance hits follow chart paint order.
     * Unlike `pick_point`, this includes histogram bins, canonical heatmap
     * cells and contour levels. The tagged result contains only stable
     * source/series indices plus `distance_px`; values and geometry stay
     * in the renderer's GPU-backed SSoT. Resolves to `undefined` on miss.
     */
    pick_data(x: number, y: number, max_distance_px: number): Promise<any>;
    /**
     * Pick the nearest visible data primitive to canvas pixel `(x, y)`.
     * Scatter hits use the visible marker size, including per-point style
     * mapping; line strokes snap to the nearest endpoint data point on
     * the hit segment. Errorbar stems/caps are not pick targets.
     * Resolves to a JSON string
     * `{ source_id, series_id, point_index, distance_px }`, or
     * `undefined` when no visible primitive is within `max_distance_px`.
     * The `<figgy-chart>` facade parses the string and normalizes
     * `undefined` to `null`.
     */
    pick_point(x: number, y: number, max_distance_px: number): Promise<any>;
    /**
     * The anchor (`Anchor` JSON) at a point in physical canvas pixels,
     * as `"Data"` or `"Ratio"`, for placing a new text box or arrow
     * where the user clicked. `null` when the point has no data
     * position (outside a log axis, or the chart has no value axes).
     */
    pointer_to_anchor(x: number, y: number, kind: string): string;
    /**
     * Prepare current annotation geometry without submitting a display frame
     * or awaiting GPU completion. Uses the renderer's canonical display
     * config and annotation raster path, preserving resident source data.
     */
    prepare_interaction(): void;
    /**
     * Prepare the same resident Cartesian groups as prewarm_all_with_progress,
     * without a progress callback. The host must prevent other calls on this
     * kernel until the Promise settles; wasm-bindgen does not queue them.
     */
    prewarm_all(): Promise<void>;
    /**
     * Prepare the resident Cartesian pipeline groups while reporting the
     * current stage as `{ scope, stage, phase }` objects. Separate bounded
     * renderers, nonresident matrix/tile pipelines and future chart-specific
     * allocations are outside this scope. The chart is mutably
     * borrowed until the Promise settles; hosts must keep their normal
     * async busy gate active and queue chart work rather than calling the
     * kernel from the callback.
     */
    prewarm_all_with_progress(on_event: Function): Promise<void>;
    /**
     * Compile the exact GPU picker and prepare it for the current chart.
     * Repeated calls, including retries, reuse renderer-owned state.
     */
    prewarm_gpu_picking(): Promise<void>;
    /**
     * Register a new `Float32Array` column. Existing ids are rejected.
     */
    register_column_f32(id: string, data: Float32Array): void;
    /**
     * Register a new `Float64Array` column as GPU `(hi, lo)` pairs.
     * Existing ids are rejected.
     */
    register_column_f64(id: string, data: Float64Array): void;
    /**
     * Register many new columns from **one** flat `Float32Array`.
     *
     * `data` holds `ids.len()` columns of `values_per_column` values each, in
     * id order — the memory layout a matrix already has. This is the wasm
     * counterpart of `Renderer::add_columns`: one staging buffer and one
     * submit for the whole batch, so a 5000-column grid costs one upload
     * rather than 5000 (design B.8).
     *
     * Nothing is copied: each column is a borrowed slice of `data` written
     * straight into the staging buffer.
     *
     * All-or-nothing. A rejected batch registers no ids and uploads nothing.
     * Ragged batches are not supported — a matrix is rectangular by
     * definition, and unequal lengths still work through
     * `register_column_f32` one at a time.
     */
    register_columns_f32(ids: string[], data: Float32Array, values_per_column: number): void;
    /**
     * Register many new columns from **one** flat `Float64Array`.
     *
     * The f64 counterpart of [`Self::register_columns_f32`], and it keeps the
     * same precision the single-column `register_column_f64` does: values are
     * uploaded as the `(hi, lo)` f32 pair, not cast to f32.
     */
    register_columns_f64(ids: string[], data: Float64Array, values_per_column: number): void;
    /**
     * Register a font (TTF/OTF/TTC bytes) for SSoT `font` family names.
     * Returns the family names the file declares — use them verbatim in
     * `content.font` / label styles. Registered fonts win over native
     * system fonts. A character the chosen face cannot draw falls back
     * per character to registered fonts (in registration order), then
     * the bundled Liberation Sans, then, on desktop only, installed
     * system fonts. Resolution through registered and bundled faces is
     * therefore identical on web and desktop; installed system fonts
     * are a desktop-only fallback. Already-drawn text re-rasterizes on
     * the next `frame()`.
     *
     * JS: `chart.register_font(new Uint8Array(await (await fetch(url)).arrayBuffer()))`
     */
    register_font(bytes: Uint8Array): string[];
    /**
     * Register replayable stream metadata without requiring a complete
     * typed array at the wasm boundary. Payload ranges are supplied only
     * after the renderer requests them.
     */
    register_streaming_column_sources(ids: string[], revisions: Float64Array, lengths: Float64Array, encodings: string[]): void;
    /**
     * Register N replayable typed-array columns without uploading or
     * retaining their contents. Each source must be a `Float32Array` or
     * `Float64Array`; the latter uses the renderer's hi/lo encoding.
     */
    register_streaming_columns(ids: string[], revisions: Float64Array, sources: Array<any>): void;
    /**
     * Compact live resident columns, drop the unused pool slab, and wait
     * for the device completion fence before reporting reclaimed bytes.
     * The 16 MiB startup slab remains as the minimum reusable pool.
     */
    release_unused_gpu_memory(): Promise<string>;
    /**
     * Remove the annotation at `index`. Later items move down one
     * index; the selection follows or clears.
     */
    remove_annotation(index: number): void;
    /**
     * Unregister a column. Series referencing it are removed too so the
     * chart can never point at freed data. Auto-managed legends remove
     * the corresponding rows; freely edited legends preserve their text
     * and only synchronize recognized series symbols.
     * Returns `true` when the column existed.
     */
    remove_column(id: string): boolean;
    /**
     * Unregister a series. Columns stay registered. Auto-managed legends
     * remove its row; freely edited legends preserve their text and only
     * synchronize recognized series symbols.
     * Returns `true` when the series existed.
     */
    remove_series(series_id: string): boolean;
    /**
     * Replace existing stream metadata. The new revision becomes live
     * only after the renderer accepts the whole batch.
     */
    replace_streaming_column_sources(ids: string[], revisions: Float64Array, lengths: Float64Array, encodings: string[]): void;
    /**
     * Atomically publish newer revisions for existing streamed columns.
     * The renderer still retains no JavaScript typed-array reference.
     */
    replace_streaming_columns(ids: string[], revisions: Float64Array, sources: Array<any>): void;
    /**
     * Ask the renderer to draw the latest chart state. Decoration-only
     * changes reuse the active accumulation; data, series, view, target,
     * and chunk-budget changes replace it after successful preflight.
     */
    request_auto_streaming_chart(max_primitives_per_chunk: number): AutoStreamingRequestResult;
    /**
     * Start a two-phase resident or mixed closure replacement. Existing
     * authority remains live until the range cursor completes.
     */
    request_resident_stream_handoff(ids: string[], revisions: Float64Array, lengths: Float64Array, encodings: string[], max_primitives_per_chunk: number): AutoStreamingRequestResult;
    /**
     * Synchronous fit request routing, allowing the facade to wait for
     * renderer progress without holding a wasm mutable borrow.
     */
    request_stream_auto_fit(padding: number): boolean;
    /**
     * Explicitly rebuild the auto legend from `SeriesConfig.label`.
     * Legacy string labels are used only when a series has no rich label.
     */
    reset_legend_from_series_labels(): void;
    /**
     * Resize the swap chain viewport. The chart Config keeps its
     * document/export `chart_area`; live rendering scales that logical
     * document into this surface.
     */
    resize(width: number, height: number): void;
    /**
     * Select one annotation (its box and handles are drawn on the
     * overlay) or none. Selecting an annotation clears the decoration
     * selection; selecting a decoration with `on_press` clears this.
     */
    select_annotation(index?: number | null): void;
    selected_annotation(): number | undefined;
    /**
     * Inspect the first resident typed selection as JSON, or `"null"` when
     * none is selected. Only selected GPU samples are read back. Histograms
     * expose `bin_start`, `bin_end`, `value`, and `orientation`; the value
     * is the stored height (also valid for weighted/density histograms).
     * Point and matrix selections expose their coordinates and cell value.
     */
    selection_details(): Promise<string>;
    /**
     * Report the effective primitive/grid extent currently drawn.
     */
    series_draw_info(series_id: string): string;
    /**
     * Set the layer that receives pointer interaction: `"Base"`,
     * `{ "Overlay": index }`, `"Annotations"`, `{ "Subplot": index }` or
     * `{ "SubplotOverlay": [subplot, overlay] }` as JSON. The hit map is
     * rebuilt for that layer (`HitMap::for_active_layer`) and the
     * element selection is cleared when the layer changes. An overlay
     * index past the overlay list is stored as `"Base"`; the stored
     * layer is returned as JSON. Drawn pixels never depend on it.
     * JS: `chart.set_active_layer(JSON.stringify({ Overlay: 0 }))`
     */
    set_active_layer(json: string): string;
    /**
     * Replace the annotation at `index` with an `Annotation` JSON value.
     */
    set_annotation(index: number, json: string): void;
    /**
     * Show or hide the whole annotation layer. Hiding skips the two
     * composite draws and re-rasterizes nothing.
     */
    set_annotations_visible(visible: boolean): void;
    /**
     * Set the WebGPU surface clear color used behind the chart panel.
     * Components are linear 0..1 RGBA floats. This is host/app state:
     * it does not change the chart Config JSON.
     */
    set_clear_color(r: number, g: number, b: number, a: number): void;
    /**
     * Replace the colourbar's z-axis options as one SSoT value. This is
     * the focused edit boundary for tick direction/style/length, value
     * direction, tick-label style/offsets, and title options.
     */
    set_colorbar_axis(json: string): void;
    /**
     * Set the colourbar title text and make it visible. An empty string
     * hides it. The full rich-text/title offsets remain available through
     * `set_colorbar_axis` or the chart Config SSoT.
     */
    set_colorbar_title(text: string): void;
    /**
     * Replace the whole option SSoT from JSON. Marks everything dirty —
     * the next `frame()` re-rasters the chrome and refreshes the
     * transform, exactly like any other config edit.
     * Use `get_config`, edit only the desired fields, then submit the
     * complete config here for selective control. For example, writing
     * only axis `min` / `max` preserves tick and label settings, whereas
     * the auto-fit helpers derive those settings along with the range.
     * This call does not auto-fit ranges or fit the title band.
     * JS: `chart.set_config(JSON.stringify(cfg));`
     */
    set_config(json: string): void;
    /**
     * Replace one contour series' levels with axis-native nice levels.
     * The resulting explicit values remain the series SSoT.
     */
    set_contour_nice_levels(series_id: string, target_count: number, use_colormap_colors: boolean): number;
    /**
     * Replace the typed data-selection overlay config. Passing JSON
     * `null` clears it. This is independent of the legacy point-only
     * overlay so existing hosts keep their current behavior.
     */
    set_picked_data(json: string): void;
    /**
     * Replace the picked-point overlay config. Passing JSON `null`
     * clears it.
     */
    set_picked_points(json: string): void;
    /**
     * Opt in to pool growth on an otherwise out-of-space upload. Growth
     * remains bounded by the device storage-binding limit and the
     * configured renderer memory budget.
     */
    set_pool_auto_growth(enabled: boolean): void;
    /**
     * Replace the series declarations from JSON. Column references must
     * already be registered; GPU styles are rebuilt, legend labels are
     * kept for series ids that survive.
     *
     * `Contour` and `HeatmapContour` accept `contour.levels` lists with
     * 0 through 1024 entries. A list with 1025 or more entries rejects the
     * JSON call with a JavaScript exception; the previously committed
     * chart config, series declarations, and GPU styles remain active.
     * The WASM facade neither adds a smaller limit nor truncates levels.
     * Contour labels use the same 1024 capacity for automatic and explicit
     * placement. `spacing_px` must be finite and positive even for hidden
     * labels or explicit anchors; rejection preserves the prior state.
     */
    set_series(json: string): void;
    /**
     * Set / change / remove a series' legend label. `'\n'` breaks lines;
     * unicode sub/superscripts (`₀`, `⁻`, …) map to styled segments.
     * Empty string removes the legend row. Returns `true` when the
     * series exists.
     */
    set_series_label(series_id: string, label: string): boolean;
    set_stream_chunk_budget(primitives: number): void;
    set_stream_operation_chunk_budget(handle: StreamingOperationHandle, max_primitives: number): void;
    /**
     * Set plain title text and grow its band if needed. For a text-only
     * edit that keeps the exact margin, use `get_config` / `set_config`
     * and change only `chart_title.text`.
     */
    set_title(text: string): void;
    set_x_title(text: string): void;
    set_y_title(text: string): void;
    /**
     * Move the resident typed data selection using source indices.
     */
    step_selection(dx: number, dy: number): boolean;
    stream_operation_request_ranges(handle: StreamingOperationHandle): AutoStreamingRangeRequestResult;
    stream_operation_submit_ranges(handle: StreamingOperationHandle, ids: string[], revisions: Float64Array, source_lengths: Float64Array, offsets: Float64Array, sources: Array<any>): StreamingStepResult;
    /**
     * Independent selected-row request; it never advances the data cursor.
     */
    stream_selection_request_ranges(): AutoStreamingRangeRequestResult;
    stream_selection_submit_ranges(request: AutoStreamingRangeRequestResult, ids: string[], revisions: Float64Array, source_lengths: Float64Array, offsets: Float64Array, sources: Array<any>): void;
    /**
     * Pure metadata inspection; does not poll, reserve a range, or draw.
     */
    stream_status(): string;
    /**
     * Advance at most one renderer-selected chunk. `sources` contains the
     * original replayable typed arrays; only the requested range is read
     * directly into mapped staging, and no owned CPU data mirror is made.
     */
    stream_step(ids: string[], revisions: Float64Array, sources: Array<any>): StreamingStepResult;
    streaming_capabilities(): string;
    /**
     * Wake after work already submitted to this queue completes. The
     * returned promise owns only its completion receiver, not a chart or
     * renderer borrow. Resolving does not service receipts or draw a frame.
     */
    streaming_gpu_ready(): Promise<any>;
    streaming_usage(): StreamingUsageResult;
    suspend_stream_selection(): void;
    /**
     * Atomically replace an existing column from a `Float32Array`.
     * Missing ids are rejected; every accepted call performs an upload.
     */
    update_register_column_f32(id: string, data: Float32Array): void;
    /**
     * Atomically replace an existing column from a `Float64Array` as
     * GPU `(hi, lo)` pairs. Every accepted call performs an upload.
     */
    update_register_column_f64(id: string, data: Float64Array): void;
    /**
     * Wait until previously submitted GPU work has finished. Does not
     * draw. Used to separate an earlier compute submit from the next
     * render submit when measuring startup.
     */
    wait_submitted_work(): Promise<void>;
    /**
     * Alias for [`Self::first_frame_ready`].
     */
    warm_up(): Promise<void>;
}

/**
 * Opaque renderer-issued replay operation. Contains no column payload.
 */
export class StreamingOperationHandle {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
}

/**
 * Result of one non-blocking exact streaming step.
 */
export class StreamingStepResult {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    readonly pending_latest: boolean;
    readonly revision: string;
    readonly status: string;
    readonly submitted_primitives: number;
    readonly total_primitives: number;
}

/**
 * Current bounded renderer-owned streaming reservations.
 */
export class StreamingUsageResult {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    readonly active_charts: number;
    readonly in_flight_chunks: number;
    readonly reserved_gpu_bytes: number;
}

/**
 * CSS color strings (`"rgb(r g b / a)"`) for a cycle — lets the host UI
 * render swatches / legends with exactly the chart's palette.
 */
export function color_cycle_css(cycle: ColorCycle): string[];

/**
 * Every valid `draw_style` mode tag, as a JSON string array.
 */
export function draw_style_modes(): string;

/**
 * Parameter metadata for one `draw_style` mode — a JSON array of
 * `{key, min, max, default, integer}`. Ranges are the RECOMMENDED
 * slider spans (the SSoT accepts values beyond them; the renderer
 * applies only safety guards), and they come from the model crate, so
 * hosts never hardcode them.
 *
 * JS: `const specs = JSON.parse(draw_style_param_specs("constellation"));`
 * Valid modes: `draw_style_modes()`.
 */
export function draw_style_param_specs(mode: string): string;

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly __wbg_autostreamingrangerequestresult_free: (a: number, b: number) => void;
    readonly __wbg_autostreamingrequestresult_free: (a: number, b: number) => void;
    readonly __wbg_figgyboundedchart_free: (a: number, b: number) => void;
    readonly __wbg_figgychart_free: (a: number, b: number) => void;
    readonly __wbg_streamingoperationhandle_free: (a: number, b: number) => void;
    readonly __wbg_streamingstepresult_free: (a: number, b: number) => void;
    readonly __wbg_streamingusageresult_free: (a: number, b: number) => void;
    readonly autostreamingrangerequestresult_encodings: (a: number) => [number, number];
    readonly autostreamingrangerequestresult_lengths: (a: number) => [number, number];
    readonly autostreamingrangerequestresult_offsets: (a: number) => [number, number];
    readonly autostreamingrangerequestresult_pending_latest: (a: number) => number;
    readonly autostreamingrangerequestresult_revision: (a: number) => [number, number];
    readonly autostreamingrangerequestresult_same_selection_request: (a: number, b: number) => number;
    readonly autostreamingrangerequestresult_source_ids: (a: number) => [number, number];
    readonly autostreamingrangerequestresult_source_lengths: (a: number) => [number, number];
    readonly autostreamingrangerequestresult_source_revisions: (a: number) => [number, number];
    readonly autostreamingrangerequestresult_status: (a: number) => [number, number];
    readonly autostreamingrangerequestresult_submitted_primitives: (a: number) => number;
    readonly autostreamingrangerequestresult_total_primitives: (a: number) => number;
    readonly autostreamingrequestresult_job_id: (a: number) => [number, number];
    readonly autostreamingrequestresult_pending_latest: (a: number) => number;
    readonly autostreamingrequestresult_revision: (a: number) => [number, number];
    readonly autostreamingrequestresult_source_ids: (a: number) => [number, number];
    readonly autostreamingrequestresult_source_revisions: (a: number) => [number, number];
    readonly autostreamingrequestresult_status: (a: number) => [number, number];
    readonly autostreamingrequestresult_submitted_primitives: (a: number) => number;
    readonly autostreamingrequestresult_total_primitives: (a: number) => number;
    readonly color_cycle_css: (a: number) => [number, number];
    readonly draw_style_modes: () => [number, number, number, number];
    readonly draw_style_param_specs: (a: number, b: number) => [number, number, number, number];
    readonly figgyboundedchart_active_layer: (a: number) => [number, number, number, number];
    readonly figgyboundedchart_add_annotation: (a: number, b: number, c: number) => [number, number, number];
    readonly figgyboundedchart_annotation_handle: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgyboundedchart_annotation_warnings: (a: number) => [number, number, number, number];
    readonly figgyboundedchart_annotations: (a: number) => [number, number, number, number];
    readonly figgyboundedchart_clear_selection: (a: number) => void;
    readonly figgyboundedchart_create: (a: any, b: number, c: number, d: number, e: number, f: number, g: number) => any;
    readonly figgyboundedchart_decorations: (a: number) => [number, number, number, number];
    readonly figgyboundedchart_drag: (a: number, b: number, c: number, d: number, e: number, f: number, g: number) => [number, number, number];
    readonly figgyboundedchart_drag_annotation: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number, number];
    readonly figgyboundedchart_export_png: (a: number, b: number) => any;
    readonly figgyboundedchart_first_frame_ready: (a: number) => any;
    readonly figgyboundedchart_frame: (a: number) => [number, number];
    readonly figgyboundedchart_get_document: (a: number) => [number, number, number, number];
    readonly figgyboundedchart_gpu_ready: (a: number) => any;
    readonly figgyboundedchart_hit_annotation: (a: number, b: number, c: number) => number;
    readonly figgyboundedchart_hit_decoration: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgyboundedchart_hover: (a: number, b: number, c: number, d: number) => number;
    readonly figgyboundedchart_pick: (a: number, b: number, c: number, d: number) => [number, number, number, number];
    readonly figgyboundedchart_pointer_to_anchor: (a: number, b: number, c: number, d: number, e: number) => [number, number, number, number];
    readonly figgyboundedchart_remove_annotation: (a: number, b: number) => [number, number];
    readonly figgyboundedchart_resize: (a: number, b: number, c: number) => void;
    readonly figgyboundedchart_resize_handle: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgyboundedchart_select_annotation: (a: number, b: number) => [number, number];
    readonly figgyboundedchart_select_decoration: (a: number, b: number, c: number) => [number, number];
    readonly figgyboundedchart_selected_annotation: (a: number) => number;
    readonly figgyboundedchart_set_active_layer: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgyboundedchart_set_annotation: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgyboundedchart_set_annotations_visible: (a: number, b: number) => [number, number];
    readonly figgyboundedchart_set_document: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgyboundedchart_step_selection: (a: number, b: number) => void;
    readonly figgychart_active_layer: (a: number) => [number, number, number, number];
    readonly figgychart_add_annotation: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_add_line_series: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number, j: number) => [number, number];
    readonly figgychart_annotation_handle: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgychart_annotation_warnings: (a: number) => [number, number, number, number];
    readonly figgychart_annotations: (a: number) => [number, number, number, number];
    readonly figgychart_apply_axis_preset: (a: number, b: number) => [number, number];
    readonly figgychart_apply_color_cycle: (a: number, b: number) => [number, number];
    readonly figgychart_auto_fit_all: (a: number, b: number) => any;
    readonly figgychart_auto_fit_colorbar: (a: number, b: number) => [number, number];
    readonly figgychart_auto_fit_overlay_y: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_auto_fit_subplot: (a: number, b: number, c: number, d: number, e: number, f: number, g: number) => [number, number];
    readonly figgychart_auto_fit_x: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgychart_auto_fit_y: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgychart_auto_stream_chart_request_ranges: (a: number) => [number, number, number];
    readonly figgychart_auto_stream_chart_step: (a: number, b: number, c: number, d: number, e: number, f: any) => [number, number, number];
    readonly figgychart_auto_stream_chart_submit_ranges: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number, j: any) => [number, number, number];
    readonly figgychart_begin_stream_export: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_begin_stream_pick_data: (a: number, b: number, c: number, d: number, e: number) => any;
    readonly figgychart_begin_stream_pick_point: (a: number, b: number, c: number, d: number, e: number) => any;
    readonly figgychart_begin_streaming: (a: number, b: number) => [number, number];
    readonly figgychart_cancel_stream_operation_and_wait: (a: number, b: number) => any;
    readonly figgychart_cancel_streaming: (a: number) => [number, number];
    readonly figgychart_cancel_streaming_and_wait: (a: number) => any;
    readonly figgychart_configure_auto_residency: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_configure_streaming: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number];
    readonly figgychart_create: (a: any) => any;
    readonly figgychart_create_with_progress: (a: any, b: any) => any;
    readonly figgychart_decoration_bounds: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_demote_auto_resident_columns: (a: number, b: number, c: number, d: number, e: number, f: any) => [number, number];
    readonly figgychart_discard_stream_selection_request: (a: number, b: number) => [number, number];
    readonly figgychart_drag_annotation: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number, number];
    readonly figgychart_ensure_extent_engine: (a: number) => any;
    readonly figgychart_export_png: (a: number, b: number) => any;
    readonly figgychart_finish_stream_export: (a: number, b: number) => any;
    readonly figgychart_finish_stream_pick_data: (a: number, b: number) => any;
    readonly figgychart_finish_stream_pick_point: (a: number, b: number) => any;
    readonly figgychart_first_frame_ready: (a: number) => any;
    readonly figgychart_frame: (a: number) => [number, number];
    readonly figgychart_get_config: (a: number) => [number, number, number, number];
    readonly figgychart_get_series: (a: number) => [number, number, number, number];
    readonly figgychart_gpu_memory_status: (a: number) => [number, number];
    readonly figgychart_gpu_ready: (a: number) => any;
    readonly figgychart_has_selection: (a: number) => number;
    readonly figgychart_hit_annotation: (a: number, b: number, c: number) => number;
    readonly figgychart_hit_test: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_inspect_column_admission: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_interrupt_render: (a: number) => [number, number, number, number];
    readonly figgychart_load_demo: (a: number) => [number, number];
    readonly figgychart_next_view_point_index: (a: number, b: number, c: number, d: number, e: number, f: number, g: number) => [number, number, number];
    readonly figgychart_on_move: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_on_press: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_on_release: (a: number) => void;
    readonly figgychart_pick_data: (a: number, b: number, c: number, d: number) => any;
    readonly figgychart_pick_point: (a: number, b: number, c: number, d: number) => any;
    readonly figgychart_pointer_to_anchor: (a: number, b: number, c: number, d: number, e: number) => [number, number, number, number];
    readonly figgychart_prepare_interaction: (a: number) => [number, number];
    readonly figgychart_prewarm_all: (a: number) => any;
    readonly figgychart_prewarm_all_with_progress: (a: number, b: any) => any;
    readonly figgychart_prewarm_gpu_picking: (a: number) => any;
    readonly figgychart_register_column_f32: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_register_column_f64: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_register_columns_f32: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number];
    readonly figgychart_register_columns_f64: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number];
    readonly figgychart_register_font: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_register_streaming_column_sources: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number) => [number, number];
    readonly figgychart_register_streaming_columns: (a: number, b: number, c: number, d: number, e: number, f: any) => [number, number];
    readonly figgychart_release_unused_gpu_memory: (a: number) => any;
    readonly figgychart_remove_annotation: (a: number, b: number) => [number, number];
    readonly figgychart_remove_column: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_remove_series: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_replace_streaming_column_sources: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number) => [number, number];
    readonly figgychart_replace_streaming_columns: (a: number, b: number, c: number, d: number, e: number, f: any) => [number, number];
    readonly figgychart_request_auto_streaming_chart: (a: number, b: number) => [number, number, number];
    readonly figgychart_request_resident_stream_handoff: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number, j: number) => [number, number, number];
    readonly figgychart_request_stream_auto_fit: (a: number, b: number) => [number, number, number];
    readonly figgychart_reset_legend_from_series_labels: (a: number) => [number, number];
    readonly figgychart_resize: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_select_annotation: (a: number, b: number) => [number, number];
    readonly figgychart_selected_annotation: (a: number) => number;
    readonly figgychart_selection_details: (a: number) => any;
    readonly figgychart_series_draw_info: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_set_active_layer: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_set_annotation: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgychart_set_annotations_visible: (a: number, b: number) => [number, number];
    readonly figgychart_set_clear_color: (a: number, b: number, c: number, d: number, e: number) => void;
    readonly figgychart_set_colorbar_axis: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_colorbar_title: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_config: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_contour_nice_levels: (a: number, b: number, c: number, d: number, e: number) => [number, number, number];
    readonly figgychart_set_picked_data: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_picked_points: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_pool_auto_growth: (a: number, b: number) => void;
    readonly figgychart_set_series: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_series_label: (a: number, b: number, c: number, d: number, e: number) => [number, number, number];
    readonly figgychart_set_stream_chunk_budget: (a: number, b: number) => [number, number];
    readonly figgychart_set_stream_operation_chunk_budget: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_title: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_x_title: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_y_title: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_step_selection: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_stream_operation_request_ranges: (a: number, b: number) => [number, number, number];
    readonly figgychart_stream_operation_submit_ranges: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number, j: number, k: any) => [number, number, number];
    readonly figgychart_stream_selection_request_ranges: (a: number) => [number, number, number];
    readonly figgychart_stream_selection_submit_ranges: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number, j: number, k: any) => [number, number];
    readonly figgychart_stream_status: (a: number) => [number, number, number, number];
    readonly figgychart_stream_step: (a: number, b: number, c: number, d: number, e: number, f: any) => [number, number, number];
    readonly figgychart_streaming_capabilities: (a: number) => [number, number];
    readonly figgychart_streaming_gpu_ready: (a: number) => any;
    readonly figgychart_streaming_usage: (a: number) => number;
    readonly figgychart_suspend_stream_selection: (a: number) => [number, number];
    readonly figgychart_update_register_column_f32: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_update_register_column_f64: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_wait_submitted_work: (a: number) => any;
    readonly figgychart_warm_up: (a: number) => any;
    readonly streamingstepresult_pending_latest: (a: number) => number;
    readonly streamingstepresult_revision: (a: number) => [number, number];
    readonly streamingstepresult_status: (a: number) => [number, number];
    readonly streamingstepresult_submitted_primitives: (a: number) => number;
    readonly streamingstepresult_total_primitives: (a: number) => number;
    readonly streamingusageresult_active_charts: (a: number) => number;
    readonly streamingusageresult_in_flight_chunks: (a: number) => number;
    readonly streamingusageresult_reserved_gpu_bytes: (a: number) => number;
    readonly wasm_bindgen_828f888c0d3e13b9___convert__closures_____invoke___js_sys_9d9a0597b9bb8a15___Function_fn_wasm_bindgen_828f888c0d3e13b9___JsValue_____wasm_bindgen_828f888c0d3e13b9___sys__Undefined___js_sys_9d9a0597b9bb8a15___Function_fn_wasm_bindgen_828f888c0d3e13b9___JsValue_____wasm_bindgen_828f888c0d3e13b9___sys__Undefined_______true_: (a: number, b: number, c: any, d: any) => void;
    readonly wasm_bindgen_828f888c0d3e13b9___convert__closures_____invoke___wasm_bindgen_828f888c0d3e13b9___JsValue__core_608f92abc48d28da___result__Result_____wasm_bindgen_828f888c0d3e13b9___JsError___true_: (a: number, b: number, c: any) => [number, number];
    readonly wasm_bindgen_828f888c0d3e13b9___convert__closures_____invoke___wasm_bindgen_828f888c0d3e13b9___sys__JsNullable_wgpu_634d2c566364ae16___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_828f888c0d3e13b9___JsError___true_: (a: number, b: number, c: any) => [number, number];
    readonly wasm_bindgen_828f888c0d3e13b9___convert__closures_____invoke___wasm_bindgen_828f888c0d3e13b9___sys__JsNullable_wgpu_634d2c566364ae16___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_828f888c0d3e13b9___JsError___true__180: (a: number, b: number, c: any) => [number, number];
    readonly wasm_bindgen_828f888c0d3e13b9___convert__closures_____invoke___wasm_bindgen_828f888c0d3e13b9___sys__JsNullable_wgpu_634d2c566364ae16___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_828f888c0d3e13b9___JsError___true__181: (a: number, b: number, c: any) => [number, number];
    readonly __wbindgen_malloc: (a: number, b: number) => number;
    readonly __wbindgen_realloc: (a: number, b: number, c: number, d: number) => number;
    readonly __wbindgen_exn_store: (a: number) => void;
    readonly __externref_table_alloc: () => number;
    readonly __wbindgen_externrefs: WebAssembly.Table;
    readonly __wbindgen_free: (a: number, b: number, c: number) => void;
    readonly __wbindgen_destroy_closure: (a: number, b: number) => void;
    readonly __externref_drop_slice: (a: number, b: number) => void;
    readonly __externref_table_dealloc: (a: number) => void;
    readonly __wbindgen_start: () => void;
}

export type SyncInitInput = BufferSource | WebAssembly.Module;

/**
 * Instantiates the given `module`, which can either be bytes or
 * a precompiled `WebAssembly.Module`.
 *
 * @param {{ module: SyncInitInput }} module - Passing `SyncInitInput` directly is deprecated.
 *
 * @returns {InitOutput}
 */
export function initSync(module: { module: SyncInitInput } | SyncInitInput): InitOutput;

/**
 * If `module_or_path` is {RequestInfo} or {URL}, makes a request and
 * for everything else, calls `WebAssembly.instantiate` directly.
 *
 * @param {{ module_or_path: InitInput | Promise<InitInput> }} module_or_path - Passing `InitInput` directly is deprecated.
 *
 * @returns {Promise<InitOutput>}
 */
export default function __wbg_init (module_or_path?: { module_or_path: InitInput | Promise<InitInput> } | InitInput | Promise<InitInput>): Promise<InitOutput>;
