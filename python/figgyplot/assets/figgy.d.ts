/* tslint:disable */
/* eslint-disable */

/**
 * JSON text returned by a figgy method: a `string`, not an object. Parse it
 * with `JSON.parse`; the method's documentation names its shape. Lengths
 * in it follow that method's units: `FiggyChart` geometry is in physical
 * canvas pixels (the canvas's `width`/`height` space) unless the method says
 * document logical pixels; `FiggyBoundedChart` geometry is in document
 * logical pixels.
 */
export type FiggyJson = string;

/** Background pipeline compiles of one scope (#299). */
export interface FiggyPipelineCounts {
    total: number;
    ready: number;
    /** Waiting or compiling. */
    compiling: number;
    failed: number;
}

/** `FiggyChart.pipeline_status()`: a plain object, not JSON. */
export interface FiggyPipelineStatus {
    /** What the last frame needed. */
    screen: FiggyPipelineCounts;
    /** Every compile scheduled so far. */
    all: FiggyPipelineCounts;
    /** Whether the last frame drew every series. */
    frame_complete: boolean;
}

/** `FiggyReadiness.status()`: a plain object, not JSON (#315). */
export interface FiggyReadinessStatus {
    screen: FiggyPipelineCounts;
    all: FiggyPipelineCounts;
    /** The chart was freed; the counts are zero then. */
    disposed: boolean;
}

/** One failed background compile, from `FiggyChart.pipeline_failures()`. */
export interface FiggyPipelineFailure {
    label: string;
    kind: "validation" | "internal" | "rejected" | "device_lost" | "cancelled";
    message: string;
}

/**
 * A theme as a plain object (not JSON): the model `Theme`'s fields, colours
 * as `{ r, g, b, a }`. Edit it and pass it to `apply_custom_theme`.
 */
export type FiggyThemeObject = Record<string, unknown>;



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
    Hidden = 5,
    Grotrian = 6,
}

/**
 * Series color rotations (mirror of `model::ColorCycle`). `Balanced` is
 * the default cycle a new series takes. The categorical presets from
 * public palettes (#357) are `Balanced` (D3 category10 / matplotlib
 * tab10), `ColorblindSafe` (Okabe–Ito), `Tableau10`, `Set2` and `Dark2`
 * (ColorBrewer, Apache-2.0), `Plotly` and `HighContrast` (plotly.py
 * Dark24); `crates/renderer/USAGE.md` ("Palette presets") lists each source and
 * licence.
 */
export enum ColorCycle {
    Classic = 0,
    Vivid = 1,
    Balanced = 2,
    ColorblindSafe = 3,
    Monochrome = 4,
    Tableau10 = 5,
    Set2 = 6,
    Dark2 = 7,
    Plotly = 8,
    HighContrast = 9,
}

/**
 * An open column transaction (#334), returned by
 * `FiggyChart.begin_columns_transaction`: several chunked uploads, each
 * with its own mapped GPU staging buffer, and optionally the chart's next
 * Config and Series, installed by `commit(chart)` together or not at all.
 *
 * - `stage(chart, id, length, encoding, source_revision)` begins one
 *   column's upload, as `begin_column_upload` begins one, on the chart that
 *   began the transaction. An id staged twice is refused.
 * - `push(id, offset, values)` writes a chunk into that column's staging,
 *   in index order, with the checks and codes of `ColumnUploadHandle.push`.
 * - `set_state(config_json, series_json?)` stages the next Config and,
 *   when given, the next Series, which may read the staged columns.
 * - `commit(chart)` installs every column, the state and the picker in one
 *   renderer transaction; `cancel()` releases every staging buffer.
 *
 * A refused `stage`, `push` or `set_state` changes nothing and leaves the
 * transaction open. After a commit, a cancel or a commit that failed, the
 * transaction is closed and every call but `cancel` throws with `code`
 * `"upload_closed"`. Every error carries `stage` (`"stage"`, `"push"`,
 * `"state"` or `"commit"`), `column` (the id it concerns, or `null`) and,
 * for a refusal with one, `code`; a memory refusal carries `requested` and
 * `limit` bytes too. The number of staged columns is not limited.
 */
export class ColumnTransaction {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    /**
     * Abandon the transaction and release every staging buffer. Nothing
     * was registered. Calling it on a closed transaction does nothing.
     */
    cancel(): void;
    /**
     * Install every staged column and the staged state on `chart`, the
     * chart that began the transaction, in one commit: the columns, the
     * Config and Series and the picker publish together, or nothing
     * changes — values, revisions, Config, Series, selection and the drawn
     * pixels stay as they were. Refused when a column is not complete
     * (`"invalid_chunk"`) or changed since it was staged (`"stale"`, its
     * `column` named), when the GPU cannot hold the columns
     * (`"budget_exceeded"`, `"pool_space"`, `"device_limit"`,
     * `"allocation_failed"`), or when the state, or without one the
     * chart's own Config and Series, does not hold against the staged
     * columns (`stage` `"state"`, with the code the setters give). A
     * monotonic chart takes no state here (`"monotonic_chart"`). The
     * transaction is closed either way.
     */
    commit(chart: FiggyChart): void;
    /**
     * Whether a state was staged with `set_state`.
     */
    has_state(): boolean;
    /**
     * Whether the transaction is still open.
     */
    is_open(): boolean;
    /**
     * The length in values of staged column `id`; `undefined` for an id
     * that is not staged.
     */
    length(id: string): number | undefined;
    /**
     * Write one chunk of staged column `id` at value `offset`: a
     * `Float32Array` for an `"f32"` column, a `Float64Array` for an `"f64"`
     * one, at most `max_chunk_bytes` bytes, starting at `written(id)`.
     * Refused with `code` `"invalid_chunk"` as `ColumnUploadHandle.push`
     * refuses a chunk, and for an id that is not staged; a refused chunk
     * changes nothing and the transaction stays open. The array is read in
     * place into the mapped staging buffer; nothing is copied on the way.
     */
    push(id: string, offset: number, values: any): void;
    /**
     * Stage the chart's next Config (`config_json`, `get_config` JSON)
     * and, when `series_json` is given, its next Series (`get_series`
     * JSON); without it the chart keeps its series. The commit installs
     * them as `set_config` followed by `set_series` would, legend
     * included, after checking them against the staged columns. A second
     * call replaces the first. JSON that does not parse is refused here
     * and the staged state stays as it was.
     */
    set_state(config_json: string, series_json?: string | null): void;
    /**
     * Stage column `id` on `chart`, the chart that began the transaction:
     * `length` values of `encoding` (`"f32"` or `"f64"`), replacing the
     * column at `source_revision` (`column_revision(id)`, or `null` /
     * `undefined` for an id that is not registered). One GPU staging
     * buffer of the column's size is created and held until the commit or
     * the cancel, as `begin_column_upload` creates one; the codes are its
     * codes (`"stale"`, `"budget_exceeded"`, `"device_limit"`, …). An id
     * already staged is refused (`"registration_failed"`), as are a
     * streamed and a reserved id. The `<figgy-chart>` element passes its
     * chart itself: there it is `stage(id, length, encoding, revision)`.
     */
    stage(chart: FiggyChart, id: string, length: number, encoding: string, source_revision?: number | null): void;
    /**
     * How many columns are staged.
     */
    staged_count(): number;
    /**
     * How many values of staged column `id` were written: the offset of
     * its next chunk. `undefined` for an id that is not staged.
     */
    written(id: string): number | undefined;
}

/**
 * An open chunked column upload (#311), returned by
 * `FiggyChart.begin_column_upload`. It owns a mapped GPU staging buffer the
 * size of the column; `push` writes typed array chunks straight into it in
 * index order, and `commit(chart)` installs the column at once. Nothing is
 * registered before the commit. `cancel` (or dropping the handle with
 * `free()`) releases the staging buffer. After a commit, a cancel or a
 * commit that failed, the handle is closed and every call but `cancel`
 * throws with `code` `"upload_closed"`.
 */
export class ColumnUploadHandle {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    /**
     * Abandon the upload and release its staging buffer. Nothing was
     * registered. Calling it on a closed handle does nothing.
     */
    cancel(): void;
    /**
     * Install the column on `chart`, the chart that began the upload, as
     * one atomic insert or replacement: the series that read it redraw with
     * the new values. Refused, changing nothing, when a value was not
     * written (`"invalid_chunk"`), when `chart` is not the chart that began
     * the upload or the column changed since (`"stale"`), or when the GPU
     * cannot hold the column (the codes of `register_column_f32`:
     * `"budget_exceeded"`, `"pool_space"`, `"device_limit"`,
     * `"allocation_failed"`). The handle is closed either way.
     */
    commit(chart: FiggyChart): void;
    /**
     * Whether the upload is still open.
     */
    is_open(): boolean;
    /**
     * The column's length in values.
     */
    length(): number;
    /**
     * Write one chunk at value `offset`: a `Float32Array` for an `"f32"`
     * upload, a `Float64Array` for an `"f64"` one, at most
     * `max_chunk_bytes` bytes. Chunks arrive in order: `offset` must be
     * `written()`, so a chunk that overlaps written values, leaves a gap
     * or runs past the length is refused (`code` `"invalid_chunk"`), as is
     * one of the other array type. A refused chunk changes nothing; the
     * upload stays open. The array's values are read in place and written
     * into the mapped staging buffer; nothing is copied on the way.
     */
    push(offset: number, values: any): void;
    /**
     * How many values were written: the offset of the next chunk.
     */
    written(): number;
}

/**
 * The browser host of one radial document, exported to JavaScript as
 * `FiggyBoundedChart`.
 *
 * A chart made by [`Self::create`] requests its own adapter and device. A
 * chart made by [`Self::create_on`] draws on a `FiggyChart`'s device and
 * queue instead (#313): its own surface on its own canvas, the same
 * device-loss record, and the same GPU ledger and memory budget. Disposing
 * either chart (`free()`) drops only its own handles: the device lives while
 * the other holds it, and a dispose never destroys a device another chart
 * still draws on. Disposing the last chart on the device destroys it, since
 * figgy requested it, once the work submitted on it completes (#322).
 */
export class FiggyBoundedChart {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    /**
     * The layer that receives pointer interaction, as JSON.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    active_layer(): FiggyJson;
    /**
     * Append an `Annotation` JSON value and return its index.
     */
    add_annotation(json: string): number;
    /**
     * Append a text note at the plot's `corner` (a `NoteAlign` name:
     * `"TopLeft"`, `"Top"`, ..., `"BottomRight"`), its block inside the
     * plot, and return its index (#258). `text` is a `RichText` JSON value;
     * the note owns it. It is an ordinary text annotation.
     */
    add_corner_note(text: string, corner: string): number;
    /**
     * The compass name of the annotation's live handle under a point.
     *
     * `x`, `y` are document logical pixels.
     */
    annotation_handle(index: number, x: number, y: number): string | undefined;
    /**
     * The `id` of every annotation, in index order, as an array of strings
     * (not a JSON string): `""` for an item without one (#315). Like
     * `FiggyChart.annotation_ids`.
     */
    annotation_ids(): string[];
    /**
     * The current index of the annotation whose `id` is `id`, or
     * `undefined` when none has it (#315). An empty id, or one several
     * items share, is an error. Like `FiggyChart.annotation_index`.
     */
    annotation_index(id: string): number | undefined;
    /**
     * Where an annotation that is not part of the document yet would be
     * drawn (#334), with the contract of `FiggyChart.annotation_preview`:
     * placed by the annotation layer's own placement code in the current
     * frame's anchor space, its text measured at the scale the canvas
     * shows the chart at. The document, the selection and the raster stay
     * as they are. `json` is an `Annotation`, the shape `add_annotation`
     * takes, checked like `FiggyChart.annotation_preview` checks it
     * (codes `annotation_json`, `annotation_invalid`).
     *
     * Returns JSON `{ kind, visible, drawn, canvas, document }`. `canvas`
     * is the shape in physical canvas pixels and `document` in document
     * logical pixels (the units of `annotations` and `hit_annotation`),
     * each `{ shape, points | rect, bounds }`: `shape` is `"text"` (`rect`
     * `[x, y, w, h]`), `"arrow"` (`points`, its two ends) or `"polygon"`
     * (a shape's outline), and `bounds` is everything the raster paints for
     * it, labels included. The radial chart has no value axes, so a
     * reference line, a span and a data anchor are never drawn. An item the
     * raster would skip has `drawn: false` and the `reason`
     * `annotation_warnings` would give (`NonFinite`, `NoValueAxis`,
     * `OutOfRange`, `EmptyText`). `visible: false` (a hidden item) is
     * placed as it is drawn once shown.
     * JS: `const p = JSON.parse(chart.annotation_preview(itemJson));`
     */
    annotation_preview(json: string): string;
    /**
     * The vertex handle (`"v<i>"`) of a polygon annotation under a point.
     *
     * `x`, `y` are document logical pixels.
     */
    annotation_vertex(index: number, x: number, y: number): string | undefined;
    /**
     * Annotations the current frame skipped, as `[{index, reason}]`.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    annotation_warnings(): FiggyJson;
    /**
     * The drawn annotations as JSON: `index`, `id`, `kind`, the selection
     * box `rect` and `handles`, and `selected`. Skipped items are listed by
     * `annotation_warnings` instead.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     * Rects are in document logical pixels, not canvas pixels.
     */
    annotations(): FiggyJson;
    /**
     * Apply the radial member of the theme family `name` (#291, #295:
     * `gallery`, `cool-slate`, `midnight` or `warm-paper`, as
     * [`Self::theme_names`] lists them): the background, label look, material, view,
     * slice shape and outline, the palette on the top-level slices and the
     * theme's tint on the slices below them. Values, labels, the slice
     * structure and the kind stay. A name that is not a family changes
     * nothing and throws `code` `"theme_unknown_name"` with the family
     * `names`.
     */
    apply_theme(name: string): void;
    /**
     * [`Self::apply_theme`] with the palette preset `cycle` on the
     * top-level slices instead of the family's colours (#357). Refused,
     * changing nothing, as [`Self::apply_theme`] refuses the name.
     */
    apply_theme_with_palette(name: string, cycle: ColorCycle): void;
    clear_selection(): void;
    /**
     * One GPU surface; no kernel PNG transport is used for interactive frames.
     */
    static create(canvas: HTMLCanvasElement, family: string, value: string, width: number, height: number): Promise<FiggyBoundedChart>;
    /**
     * A radial chart on `parent`'s device and queue (#313), drawn to its
     * own `canvas`: a promise of the `FiggyBoundedChart`, which validates
     * the document as [`Self::create`] does but requests no adapter and no
     * device.
     *
     * Lifetime: the chart holds clones of the parent's handles. Disposing
     * it (`free()`) never destroys the parent's device, and disposing the
     * parent leaves this chart drawing; the device lives while either
     * holds it, and disposing the last of them destroys it (#322). Both share one device-loss record, so a lost device fails
     * the next frame, export or pick of each with the loss, and one GPU
     * ledger and memory budget: the parent's `gpu_memory_status` counts
     * this chart's allocations, and the one budget bounds both charts.
     * Both submit to the one queue in call order; a wait on
     * either (`first_frame_ready`, an export) completes with the work
     * submitted before it, the other chart's included. An async call
     * (an export, a pick) borrows only this chart: while it is pending,
     * `free()` on this chart throws as on every wasm-bindgen object
     * (await it first), and disposing the parent does not cancel it.
     */
    static create_on(parent: FiggyChart, canvas: HTMLCanvasElement, family: string, value: string, width: number, height: number): Promise<any>;
    /**
     * Renderer-measured logical pixel bounds and resize handles.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     * Rects are `[x, y, width, height]` in document logical pixels, not canvas
     * pixels.
     */
    decorations(): FiggyJson;
    drag(target: string, dx: number, dy: number, handle?: string | null): boolean;
    /**
     * Move an annotation, or one of its handles (a compass name or a
     * polygon vertex `"v<i>"`), by a pointer delta. Returns `false` for a
     * rejected move; the document is unchanged then.
     */
    drag_annotation(index: number, dx: number, dy: number, handle?: string | null): boolean;
    /**
     * [`Self::export_svg`] as one-page PDF bytes.
     */
    export_pdf(scale: number): Promise<Uint8Array>;
    export_png(scale: number): Promise<Uint8Array>;
    /**
     * [`Self::export_png`] over another background (#313): `"document"`
     * (the chart's own, as `export_png` draws it), `"transparent"` (no
     * background: only the slices, labels and annotations) or a colour JSON
     * `{"r":..,"g":..,"b":..,"a":..}` (components `0..=1`). The override is
     * the export's alone: the document, its selection and the image on
     * screen are unchanged. Any other value throws `code`
     * `"export_background"` before anything is drawn.
     */
    export_png_with_background(scale: number, background: string): Promise<Uint8Array>;
    /**
     * The chart as an SVG document at `scale ×` resolution: the slices and
     * background as one image, the title, labels, leader lines and
     * annotations as vector content.
     */
    export_svg(scale: number): Promise<string>;
    /**
     * Submit one frame and wait for actual GPU completion. Hosts must await
     * this before publishing Ready; rejected completion (including device
     * loss) is returned to the caller instead of reporting an unusable chart.
     */
    first_frame_ready(): Promise<void>;
    frame(): void;
    /**
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    get_document(): FiggyJson;
    /**
     * Host fence: keep edits serialized independently of GPU completion.
     */
    gpu_ready(): Promise<any>;
    /**
     * The topmost drawn annotation under a point, as its index.
     *
     * `x`, `y` are document logical pixels.
     */
    hit_annotation(x: number, y: number): number | undefined;
    /**
     * The topmost decoration under a point, as its stable id. While the
     * annotation layer is active (and shown) its drawn items sit on top of
     * every decoration and answer as `"annotation_<n>"`; on the base layer
     * they are not registered and clicks pass through them.
     *
     * Asynchronous: over the plot area it asks whether data is drawn
     * there, which the radial chart answers with its GPU pick.
     *
     * `x`, `y` are document logical pixels. Resolves to the plain id string,
     * not JSON.
     */
    hit_decoration(x: number, y: number, edit_area: boolean): Promise<string | undefined>;
    /**
     * Hover the data under a point (`None` leaves the chart) and advance
     * the hover animation by `dt` seconds; resolves to whether the chart
     * changed. Asynchronous: the radial chart picks on the GPU.
     */
    hover(x: number | null | undefined, y: number | null | undefined, dt: number): Promise<boolean>;
    /**
     * Select the data under a point (or toggle it off) and resolve to the
     * selection as JSON. Asynchronous: the radial chart picks on the GPU,
     * like `FiggyChart.pick_point`.
     *
     * Resolves to JSON text (`FiggyJson`), not an object. `x`, `y` are
     * document logical pixels.
     */
    pick(x: number, y: number, toggle: boolean): Promise<FiggyJson>;
    /**
     * The `Anchor` JSON at a point for `"Data"` or `"Ratio"`; `null` when
     * the point has no such position (a radial chart has no data anchors).
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     * `x`, `y` are document logical pixels.
     */
    pointer_to_anchor(x: number, y: number, kind: string): FiggyJson;
    /**
     * Rewrite the automatic slice labels from the document's values and
     * label format (#313): each generated text (`text_generated`) and each
     * missing one, as `RadialChart::regenerate_labels` writes them; a text
     * the host wrote stays. With `rewrite_user_text`, every text is
     * rewritten, the host's included (`RadialChart::format_labels`).
     * `set_document` already regenerates the generated texts of the
     * document it is given; this is the call for an explicit rewrite.
     */
    regenerate_labels(rewrite_user_text: boolean): void;
    /**
     * Remove the annotation at `index`; later indices move down one and the
     * selection follows or clears.
     */
    remove_annotation(index: number): void;
    /**
     * Put the decoration `id` (an id [`Self::decorations`] lists, such as
     * `"chart_title"` or `"radial_label_0_1"`) back where the layout places
     * it (#313): its stored offset is removed, and for `"data_area"` the
     * explicit plot region too (`DecorationLayout::reset`). Not a drag by
     * the negative offset: nothing is left stored. Returns whether the
     * document changed. An unknown id, and an annotation (which has a
     * position of its own, not an offset), throw.
     */
    reset_decoration_position(id: string): boolean;
    resize(width: number, height: number): void;
    /**
     * `x`, `y` are document logical pixels.
     */
    resize_handle(target: string, x: number, y: number): string | undefined;
    /**
     * Select one annotation (`decorations.selected = Annotation(index)`) or
     * none. Clears the data and decoration selections like
     * `select_decoration`.
     */
    select_annotation(index?: number | null): void;
    /**
     * Select the annotation whose `id` is `id`, like `select_annotation`
     * with its index (#315); an error, with the selection unchanged, when
     * no annotation or more than one has it, or `id` is empty.
     */
    select_annotation_by_id(id: string): void;
    /**
     * Select a decoration by the id `hit_decoration` reported, or none.
     * An `"annotation_<n>"` id selects that drawn annotation
     * (`decorations.selected = Annotation(n)`).
     */
    select_decoration(target?: string | null): void;
    /**
     * The index of the selected annotation, or `undefined`. An index is
     * valid until the annotation list changes (see `annotation_index`).
     */
    selected_annotation(): number | undefined;
    /**
     * Set the layer that receives pointer interaction: `"Base"` or
     * `"Annotations"` as JSON (the radial chart has no overlays, so an
     * `{ "Overlay": n }` is stored as `"Base"`). A change clears the
     * decoration selection (`decorations.selected`, an annotation
     * included); the data selection is kept. Returns the stored layer as
     * JSON. Drawn pixels never depend on it.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    set_active_layer(json: string): FiggyJson;
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
    /**
     * The chart families `create` opens, as an array of strings (#315):
     * `["radial"]`. The categorical, box plot and radar families moved to
     * `FiggyChart` (`set_categorical_document`, `set_boxplot_document`,
     * `set_radar_document`); passing one of them to `create` is an error
     * naming that method.
     *
     * JS: `FiggyBoundedChart.supported_families() // ["radial"]`
     */
    static supported_families(): string[];
    /**
     * The theme names (#291, #295), as an array of strings: the four
     * families.
     *
     * Returns an array of strings, not a JSON string.
     */
    theme_names(): string[];
}

export class FiggyChart {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    /**
     * The layer that receives pointer interaction, as JSON, with the
     * out-of-range fallback applied.
     * JS: `JSON.parse(chart.active_layer())`
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    active_layer(): FiggyJson;
    /**
     * Append an `Annotation` (JSON, the same shape as in `get_config`)
     * and return its index.
     */
    add_annotation(json: string): number;
    /**
     * Append a text note at the plot's `corner` (a `NoteAlign` name:
     * `"TopLeft"`, `"Top"`, ..., `"BottomRight"`), its block inside the
     * plot, and return its index (#258). `text` is a `RichText` JSON value,
     * the same shape as in `get_config`; the note owns it, such as the
     * unit of the chart's values. It is an ordinary text annotation: move,
     * hide or edit it as one.
     * JS: `const i = chart.add_corner_note(textJson, "BottomRight");`
     */
    add_corner_note(text: string, corner: string): number;
    /**
     * Register or update a line series over two registered columns.
     *
     * Upsert by `series_id`: a new id takes the next color of the active
     * cycle; an existing id is replaced in place and keeps its color.
     * Non-empty `label` adds/updates the legend row; its `$…$` spans are
     * TeX and `\$` is a dollar sign.
     */
    add_line_series(series_id: string, x_column: string, y_column: string, line_width: number, label: string): void;
    /**
     * The compass name (`"W"`, `"E"`, ...) of the annotation's handle
     * under a point, or none. Only the handles `annotations` lists are
     * live: a span's two edges, a line's two value handles, an arrow's
     * two endpoints.
     *
     * `x`, `y` are physical canvas pixels. Returns a plain string, not JSON.
     */
    annotation_handle(index: number, x: number, y: number): string | undefined;
    /**
     * The `id` of every annotation, in index order, as an array of
     * strings (not a JSON string): `""` for an item without one (#315).
     * An id is the host's free label (`Annotation.id`), kept by every edit
     * and by serialization, so it survives reordering and removal of other
     * items, which shift indices.
     *
     * JS: `const ids = chart.annotation_ids(); // ["peak", "", "note-1"]`
     */
    annotation_ids(): string[];
    /**
     * The current index of the annotation whose `id` is `id`, or
     * `undefined` when none has it (#315). The renderer does not require
     * ids to be unique, so an empty id, or one that several items share,
     * is rejected with an error rather than guessed. Look the index up
     * again after any edit that adds, removes or reorders annotations.
     *
     * JS: `const i = chart.annotation_index("peak"); // undefined when absent`
     */
    annotation_index(id: string): number | undefined;
    /**
     * Where an annotation that is not part of the document yet would be
     * drawn (#312), placed by the annotation layer's own placement code
     * from the document as the canvas shows it: the document, the
     * selection, the undo state and the raster stay as they are. `json` is
     * an `Annotation`, the shape `add_annotation` takes.
     *
     * Returns JSON `{ kind, visible, drawn, canvas, document }`. `canvas`
     * is the shape in physical canvas pixels and `document` in document
     * pixels, each `{ shape, points | rect, bounds }`: `shape` is `"line"`
     * (a reference line's two ends), `"span"` or `"text"` (`rect`
     * `[x, y, w, h]`), `"arrow"` (`from`, `to`) or `"polygon"` (a shape's
     * outline clipped to the plot), and `bounds` is everything the raster
     * paints for it, labels included. A span or a reference line on a
     * broken axis is reported whole, before its gaps are cut out. An item
     * the raster would skip has `drawn: false` and the `reason`
     * `annotation_warnings` would give (`NonFinite`, `NoValueAxis`,
     * `OutOfRange`, `EmptyText`). `visible: false` (a hidden item) is
     * placed as it is drawn once shown.
     * JS: `const p = JSON.parse(chart.annotation_preview(itemJson));`
     */
    annotation_preview(json: string): string;
    /**
     * The vertex handle (`"v<i>"`) of a polygon annotation under a
     * point, or none: a polygon's handles are its vertices.
     *
     * `x`, `y` are physical canvas pixels. Returns a plain string, not JSON.
     */
    annotation_vertex(index: number, x: number, y: number): string | undefined;
    /**
     * Annotations the current raster skipped, as `[{index, reason}]`
     * with `reason` one of `NonFinite`, `NoValueAxis`, `OutOfRange`,
     * `EmptyText`.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    annotation_warnings(): FiggyJson;
    /**
     * The drawn annotations of the current frame as JSON: `index`, `id`,
     * `kind`, the selection box `rect` and its `handles` in physical
     * canvas pixels, and `selected`. Items the raster skipped are
     * absent here and listed by `annotation_warnings`.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    annotations(): FiggyJson;
    /**
     * The append call of monotonic group `group` (#271): `data` holds only
     * the new samples of every channel, in either layout of
     * `set_monotonic`. With `sliding`, the window keeps its length and the
     * chart's x range moves by exactly the new samples' span; the host may
     * drop every sample before the window. Returns the update as JSON.
     * JS: `chart.append_monotonic("daq", [new0, new1], true)`
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    append_monotonic(group: string, data: any, sliding: boolean, stride?: number | null, columns?: Uint32Array | null): FiggyJson;
    /**
     * Apply an axis frame preset to all four axes and every overlay's own
     * axes (decoration-only).
     */
    apply_axis_preset(preset: AxisPreset): void;
    /**
     * Switch the series color rotation: applies the palette to the chart
     * (`Config::apply_palette`, #357), so series `i` takes the cycle's
     * colour `i` in every palette-coloured part (a field, an image, an
     * energy-level or a Feynman diagram keeps its colours), rebuilds the
     * GPU styles, and redraws the legend symbols of the base chart, its
     * overlays and its subplots. Later `add_*_series` calls continue the
     * cycle.
     */
    apply_color_cycle(cycle: ColorCycle): void;
    /**
     * Apply `theme`, an object [`Self::theme`] handed out and the host
     * edited, to the charts of its kind (#295): the chart and every
     * subplot of the theme's kind, or that draws no series yet; charts of
     * another kind are left as they are. Then fit the layout as
     * [`Self::apply_theme`] does. An object that is not a theme throws
     * `code` `"theme_invalid"`; no chart of its kind `"theme_wrong_kind"`;
     * a draw style that cannot draw a series it themes
     * `"theme_draw_style"`. A refusal changes nothing.
     */
    apply_custom_theme(theme: any): void;
    /**
     * [`Self::apply_custom_theme`] to the charts `scope` names (the forms
     * [`Self::apply_theme_to`] takes): `"[0]"` themes subplot 0 alone,
     * whatever the base chart's kind. A chart in scope of another kind
     * than the theme throws `"theme_wrong_kind"`, an index past the
     * subplots `"subplot_index"`.
     */
    apply_custom_theme_to(theme: any, scope: string): void;
    /**
     * Apply the theme family `name` (#291, #295: `gallery`, `cool-slate`,
     * `midnight` or `warm-paper`, as [`Self::theme_names`] lists them) to
     * the whole document: the chart, its overlays, every subplot and the
     * series drawn there, then fit the layout to the theme's text sizes,
     * as Rust's `Chart::apply_theme` does. The chart and every subplot
     * take the family's member for their own kind, so subplots of other
     * kinds take it too (`Theme::apply_named`). Ranges, text, annotations,
     * the layer structure and the selection stay. A name that is not a
     * family (`code` `"theme_unknown_name"`, with the family `names`)
     * changes nothing and errors. A chart with monotonic series keeps its
     * layout (#271): `fit_layout`, which takes the groups' sources, fits
     * it. [`Self::apply_theme_to`] chooses the subplots.
     */
    apply_theme(name: string): void;
    /**
     * [`Self::apply_theme`] to the charts `scope` names, as Rust's
     * `Chart::apply_theme_to` takes a `ThemeScope`: `"all"` (the base chart
     * and every subplot), `"base"` (the base chart alone), a JSON array of
     * indices (those subplots alone, `"[0,2]"`) or a JSON array holding
     * `"base"` (the base chart and those subplots, `"[\"base\",0]"`). A
     * scope of another form (`code` `"subplot_scope"`, with the `accepted`
     * forms) or an index past the subplots (`code` `"subplot_index"`)
     * changes nothing and errors.
     */
    apply_theme_to(name: string, scope: string): void;
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
     * `SubplotOverlay(i, n)` fit that overlay's own axes: its Y axis, and
     * its X axis while its `link_x` is off. An axis fits every series
     * drawn against it (`Config::layer_of_series`). A linked axis
     * (`link_x`, `link_y` of a subplot or an overlay) is one axis shared
     * by its link group: it fits the series of every chart and overlay in
     * the group and the range moves the whole group, whichever member is
     * active. X and Y links are followed separately. By default an overlay
     * follows its chart's X axis and has its own Y axis, so its series
     * count towards that X axis and not towards `left_y`. An axis that is not linked fits its own chart's
     * series only; to fit every layer, set each layer active in turn and
     * call this again.
     *
     * Each series contributes its exact original GPU primitive domain:
     * valid adjacent segments for line-only mode, paired finite points
     * for point-bearing modes, and enabled error endpoints. The reduction
     * is compiled on first fit (`createComputePipelineAsync` on wasm),
     * and the renderer reuses a series' extent while its columns are
     * unchanged (`begin_auto_fit_all`). Matrix-backed series use the same
     * engine to return the
     * exact cell/sample-lattice bounds; only histograms remain a metadata
     * union because their uploaded edge column already is their geometry.
     * Series registration itself does not submit GPU work.
     */
    auto_fit_all(padding: number): Promise<void>;
    /**
     * Fit the shared z axis to every column the colourbar maps: matrix
     * value columns, scatter `point_color_map` columns, vector colour
     * maps and streamline colour columns. A chart without a colourbar is left unchanged.
     */
    auto_fit_colorbar(padding: number): void;
    /**
     * Fit overlay layer `layer`'s own X axis (`OverlayLayer::x_axis`) to a
     * column's cached statistics with proportional padding, the X
     * counterpart of `auto_fit_overlay_y`. With the overlay's `link_x` on
     * it fits the chart's X axes it follows. A layer index past the
     * overlay list is an error.
     * JS: `chart.auto_fit_overlay_x(0, "time_b", 0.05)`
     */
    auto_fit_overlay_x(layer: number, column: string, padding: number): void;
    /**
     * Fit overlay layer `layer`'s Y axis to a column's cached statistics
     * with proportional padding, the overlay counterpart of `auto_fit_y`.
     * With the overlay's `link_y` on it fits the chart's Y axes it
     * follows. A layer index past the overlay list is an error.
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
     * Begin a chunked upload of the resident column `id`: `length` values,
     * `encoding` `"f32"` (chunks are `Float32Array`s) or `"f64"`
     * (`Float64Array`s, kept as GPU `(hi, lo)` pairs). The returned handle
     * takes the chunks (`push`) and installs the column (`commit(chart)`).
     *
     * `source_revision` is the revision of the column the upload replaces,
     * as `column_revision(id)` reports it, or `null` / `undefined` for an id
     * that is not registered; anything else throws with `code` `"stale"`,
     * and so does a commit after the column changed. `max_chunk_bytes`
     * bounds the bytes of each pushed chunk.
     *
     * One GPU staging buffer of the column's size (8 bytes per value) is
     * created here and held until the commit or the cancel; it counts
     * against the memory budget, and a budget or device that cannot hold
     * it throws with the codes of `register_column_f32`. A streamed id or a
     * reserved id is refused.
     *
     * JS: `const up = chart.begin_column_upload("x", n, "f64", chart.column_revision("x"), 1 << 20);`
     */
    begin_column_upload(id: string, length: number, encoding: string, source_revision: number | null | undefined, max_chunk_bytes: number): ColumnUploadHandle;
    /**
     * Begin a column transaction (#334): several columns uploaded in
     * chunks and, optionally, the chart's next Config and Series, installed
     * together by one `commit(chart)` or not at all. `max_chunk_bytes`
     * bounds the bytes of each pushed chunk. Nothing is allocated until a
     * column is staged. See `ColumnTransaction`.
     *
     * JS:
     * ```js
     * const tx = chart.begin_columns_transaction(1 << 20);
     * tx.stage(chart, "x", n, "f64", chart.column_revision("x") ?? null);
     * tx.stage(chart, "y", n, "f64", chart.column_revision("y") ?? null);
     * tx.push("x", 0, xs);
     * tx.push("y", 0, ys);
     * tx.set_state(JSON.stringify(config), JSON.stringify(series));
     * tx.commit(chart);
     * ```
     */
    begin_columns_transaction(max_chunk_bytes: number): ColumnTransaction;
    /**
     * Begin an independent replay of the completed stream. The facade
     * supplies only renderer-requested ranges between these calls.
     */
    begin_stream_export(scale: number, max_primitives_per_chunk: number): StreamingOperationHandle;
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
     * Removes the monotonic chart and shows the general one again (#271).
     */
    clear_monotonic_document(): void;
    /**
     * End every element selection and pointer gesture (#311): the
     * decoration selection (`HitId`), the annotation selection, a value
     * label or Feynman part drag, an element drag or handle resize, a
     * pending plot-area resize proposal and a held subplot display
     * placement. The chart redraws. The active layer, the config, the
     * series and the columns stay as they are, and so does the data
     * highlight (`picked_data`, a value label's typed selection included):
     * clear that with `set_picked_data("null")`.
     *
     * JS: `chart.clear_selection();`
     */
    clear_selection(): void;
    /**
     * The revision of column `id`: what `begin_column_upload` takes as
     * `source_revision`. Every upload of a resident column renews it.
     * `undefined` for an id that is not registered.
     */
    column_revision(id: string): number | undefined;
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
     * `json`, an `Annotation`, with every anchor converted to
     * `anchor_kind` (`"Data"` or `"Ratio"`) at the position it is drawn
     * at now (#312): a text box's anchor, an arrow's and a box shape's
     * two ends, a polygon's vertices. A reference line or a span has no
     * anchor and comes back unchanged. Nothing is installed; pass the
     * result to `add_annotation` or `set_annotation`. An anchor with no
     * position (a data anchor on a chart without value axes, a
     * non-positive value on a logarithmic axis, a non-finite coordinate)
     * is refused with code `anchor_unplaceable`. A ratio anchor is an
     * `f32` fraction of the plot, so a round trip keeps the drawn pixel.
     * JS: `chart.set_annotation(i, chart.convert_annotation_anchor(itemJson, "Ratio"));`
     */
    convert_annotation_anchor(json: string, anchor_kind: string): string;
    /**
     * Bind the low-level chart kernel to `canvas` (uses the canvas's
     * current pixel size). Ordinary web hosts should prefer
     * `figgy-chart.js` and its `<figgy-chart>` Custom Element.
     * JS: `const chart = await FiggyChart.create(canvas);`
     */
    static create(canvas: HTMLCanvasElement): Promise<FiggyChart>;
    /**
     * [`Self::create`] with options (#299), all optional:
     *
     * - `shaders`: `"basic"` (the default) or `"full"`. A chart starts on
     *   the basic shader set, which draws linear and logarithmic
     *   rectangular charts, and moves to the full set by itself when its
     *   config first has an axis break, a probability axis or polar
     *   coordinates. A host that knows it will show such a chart passes
     *   `"full"`, so the basic set is never compiled and discarded.
     * - `on_progress`: the callback of [`Self::create_with_progress`].
     *
     * An unknown option, or a `shaders` value other than those two,
     * rejects the promise with an `Error` that names it; nothing is
     * created.
     * JS: `const chart = await FiggyChart.create_with_options(canvas, { shaders: "full" });`
     */
    static create_with_options(canvas: HTMLCanvasElement, options: any): Promise<FiggyChart>;
    /**
     * Same as [`Self::create`], reporting each init stage to `on_event`
     * as `{ scope, stage, phase }`. Do not call other kernel methods
     * from the callback. An exception the callback throws rejects the
     * returned promise with it; later stages are not reported.
     */
    static create_with_progress(canvas: HTMLCanvasElement, on_event: Function): Promise<FiggyChart>;
    /**
     * The active layer's exact data area (#312), as JSON `{ layer, panel,
     * document, canvas }` with `[x, y, w, h]` rects in document and
     * physical canvas pixels: the rectangle the data is drawn in, not the
     * padded box `decoration_bounds("data_area")` selects. The annotation
     * layer reads the parent chart's. Refused with code `data_area` for a
     * chart without one.
     * JS: `const [x, y, w, h] = JSON.parse(chart.data_area_rect()).canvas;`
     */
    data_area_rect(): string;
    /**
     * Renderer-measured decoration bounds in physical canvas pixels.
     * An `"annotation_<n>"` id that `hit_test` reports resolves to the
     * drawn item's selection box.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     * `{ rect: [x, y, width, height], handles: [[x, y, width, height], …] }`.
     */
    decoration_bounds(target: string): FiggyJson;
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
     * and returns `false`. A handle is a compass name (`"W"`, `"NE"`, ...)
     * or a polygon vertex (`"v3"`).
     */
    drag_annotation(index: number, dx: number, dy: number, handle?: string | null): boolean;
    /**
     * Compile the drawable-series fit-bound engine without drawing. On wasm
     * this uses `createComputePipelineAsync`. Series registration does
     * not do this; `auto_fit_all` does.
     */
    ensure_extent_engine(): Promise<void>;
    /**
     * [`Self::export_svg`] as one-page PDF bytes.
     * JS: `const pdf = await chart.export_pdf(2.0);`
     */
    export_pdf(scale: number): Promise<Uint8Array>;
    /**
     * [`Self::export_pdf`] with the sources of the chart's monotonic
     * groups, as [`Self::export_png_monotonic`] takes them.
     */
    export_pdf_monotonic(scale: number, sources: Array<any>): Promise<Uint8Array>;
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
     * The `<figgy-chart>` facade supplies that gate and rejects competing
     * application calls; raw FiggyChart callers must manage it themselves.
     * Automatic contour placement validates `spacing_px * scale` after the
     * export scale is clamped. Explicit placement does not multiply spacing.
     * Scale-product overflow or an atlas beyond the adapter texture limit
     * rejects the export before contour GPU state changes.
     */
    export_png(scale: number): Promise<Uint8Array>;
    /**
     * [`Self::export_png`] with the sources of the chart's monotonic
     * groups (#271), for an export at another scale than the screen's
     * (which maps the plot to other device pixels): `sources` is an array
     * of `{ group, start, interval, data, stride?, columns? }`, `data` as
     * `set_monotonic` takes it. Each group is reduced for the export alone.
     * The same borrow and gate rules as `export_png`.
     */
    export_png_monotonic(scale: number, sources: Array<any>): Promise<Uint8Array>;
    /**
     * Export the document as an SVG document at `scale ×` resolution: the
     * decorations, annotations and text as vector content (glyphs as
     * outlines) over each panel group's data embedded as a PNG image, with
     * the clear colour as its background.
     * JS: `const svg = await chart.export_svg(2.0);`
     * The same borrow and gate rules as [`Self::export_png`]. A chart with a
     * streamed source is rejected; the `<figgy-chart>` facade rejects it
     * before calling.
     */
    export_svg(scale: number): Promise<string>;
    /**
     * [`Self::export_svg`] with the sources of the chart's monotonic
     * groups, as [`Self::export_png_monotonic`] takes them.
     */
    export_svg_monotonic(scale: number, sources: Array<any>): Promise<string>;
    finish_stream_export(handle: StreamingOperationHandle): Promise<Uint8Array>;
    /**
     * Submit the current chart if it is dirty, then wait until that GPU
     * work has finished. Hosts should keep a loading overlay up until
     * this resolves. The wait does not remove a main-thread Dawn/driver
     * freeze; it only reports first-submit completion. While a series'
     * pipelines still compile in the background its frame leaves it out
     * (#299); this draws again as they resolve and settles with the frame
     * that holds every series.
     *
     * JS: `await chart.first_frame_ready();`
     */
    first_frame_ready(): Promise<void>;
    /**
     * Fit a candidate config without installing it (#312): `config_json`
     * is a whole `Config` (what `get_config` returns, edited); the result
     * is that config as JSON with the ranges of every layer, link and
     * subplot fitted from the resident columns' statistics by the same
     * code as `fit_ranges` (`Renderer::fit_config`), with `padding` (the
     * fraction of the data span left on each side, finite and at least 0)
     * instead of the fixed 5%. The fit uses this chart's registered
     * series. The installed chart, its view and its columns are
     * untouched; install the result with `set_config`.
     *
     * Refused (an exception, nothing changes): JSON that is not a
     * `Config`, a negative or non-finite padding, a candidate whose
     * overlays, subplots or line offsets name a series this chart has not
     * registered (`LayerSeriesUnknown`) or break their rules, a series
     * whose column is not registered or is streamed (rule 8), and a
     * monotonic chart. The call is synchronous, so the columns and series
     * it reads cannot change while it runs.
     * JS: `const fitted = JSON.parse(chart.fit_config(JSON.stringify(cfg), 0.05));`
     */
    fit_config(config_json: string, padding: number): string;
    /**
     * `fit_config` for one layer's chosen axes (#334,
     * `Renderer::fit_config_scoped`): the candidate comes back with only
     * the axes `scope_json` selects fitted, every other axis exactly as
     * given. `scope_json` is `{ "layer": <layer>, "axes": ["x", "y",
     * "z"], "linked": "group" | "target", "keep": [{ "layer": <layer>,
     * "axis": "x" | "y" | "z" }] }`, a layer written as for
     * `set_active_layer` (`"Base"`, `{"Overlay":0}`, `{"Subplot":1}`,
     * `{"SubplotOverlay":[1,0]}`). `"z"` is a 3D chart's z axis (its
     * `right_y`); on a parallel chart the parallel axes are `"y"`. A
     * moved axis that is linked moves its link group. `linked` (default
     * `"group"`) reads every series drawn against a linked axis' group,
     * or with `"target"` only those drawn in the target's panel (the
     * parent chart or one subplot, its overlays included; the group still
     * shares the range). `keep` (default none) names axes that hold their
     * range, and every axis linked to one holds too. Statistics only:
     * error bar ends, heatmap cell half-widths and arrow tips are not
     * included (`auto_fit_all` measures drawn extents). The installed
     * chart is untouched.
     *
     * Refused (an exception, nothing changes): the refusals of
     * `fit_config`, a scope that is not this JSON (an unknown field, axis
     * name or `linked` value), and a `layer` or `keep` layer naming an
     * overlay or subplot the candidate does not have (code
     * `FitScopeLayer`).
     * JS: `chart.fit_config_scoped(JSON.stringify(cfg), JSON.stringify({ layer: "Base", axes: ["x"], linked: "target" }), 0.05)`
     */
    fit_config_scoped(config_json: string, scope_json: string, padding: number): string;
    /**
     * Resolve the renderer's radial-label fit before the host commits the edit.
     */
    fit_host_radial_labels(cells_json?: string | null): Promise<void>;
    /**
     * Fits the chart's layout to its labels and titles and applies it
     * (`Renderer::fit_layout`, #271). It can move the plot's edges, so it
     * takes the sources of the chart's monotonic groups as
     * `resize_monotonic` does. A chart without monotonic series takes no
     * argument: `chart.fit_layout()`; its range links without an exit
     * then get the ones the layout chooses (#357), written by the frame
     * that finds their GPU gather complete.
     */
    fit_layout(sources?: Array<any> | null): void;
    /**
     * Fit series `series_id`'s point size map domain to its size column's
     * native extent, from the column's cached statistics
     * (`PointSizeMap::fit_domain`, #312): only that series' `domain_min`
     * and `domain_max` change, and no column is read back. Refused
     * (an exception, the style unchanged): an unknown series, a series
     * without `point_size_map`, a streamed or unregistered size column,
     * and an extent that is empty, non-finite or a single value.
     * JS: `chart.fit_point_size_domain("bubbles")`
     */
    fit_point_size_domain(series_id: string): void;
    /**
     * Fit every axis the chart's series use to their registered columns,
     * in one call (`Renderer::fit_ranges`, #297): the x and y axes of the
     * base chart, of each overlay and of each subplot and its overlays,
     * and the z axis of a 3D chart, from the columns' cached statistics
     * with 5% padding. A chart starts at a `0..1` placeholder range; this
     * is the call for a first plot. Synchronous, and independent of the
     * active layer. A layer without series keeps its ranges. A fitted
     * linear axis keeps an explicit label format such as `Percent` with
     * its digits; `Decimal` and `Power` become `Auto` (#417). Then the
     * scale of every auto-scaled vector series is fitted to the spacing
     * of its arrows and its `auto_scale` flag consumed (#357), so the
     * stored series say how long the arrows draw. Then each range link
     * without an exit gets the one the layout chooses (#357), written by
     * the frame that finds its GPU gather complete. A streamed source and a
     * monotonic chart are refused, and a refusal changes nothing.
     * `auto_fit_all(padding)` instead measures the active layer's drawn
     * extents (error bar ends included) on the GPU.
     * JS: `chart.fit_ranges()`
     */
    fit_ranges(): void;
    /**
     * Fit vector series `series_id`'s scale so the longest vector its U/V
     * columns' extents allow draws `target` long
     * (`VectorStyle::fit_scale`, #312): logical pixels for a `Pixels`
     * scale, data units for a `Data` scale. Point and grid components
     * both fit (a grid from the union of its columns' statistics), and a
     * point field drawn in 3D fits its `w` column too
     * (`fit_scale_3d`). Only that series' scale value changes, and no
     * column is read back. Refused (an exception, the style unchanged):
     * an unknown or non-vector series, a `target` that is not finite and
     * positive, a streamed or unregistered component column, and
     * components whose extent is empty, non-finite or all zero.
     * JS: `chart.fit_vector_scale("wind", 24)`
     */
    fit_vector_scale(series_id: string, target: number): void;
    /**
     * `fit_config` that moves only Y axes (#312): every X axis of the
     * candidate (`bottom_x`, `top_x`, each overlay's `x_axis`, the same in
     * each subplot) comes back exactly as given, ticks and label format
     * included; the Y axes (`left_y`, `right_y` — the z axis of a 3D
     * chart —, overlay `y_axis` and parallel axes) are fitted. An axis no
     * fit moves (categorical, ternary) keeps its range. The config has no
     * "manual range" flag: a host that holds a Y range by hand restores it
     * in the result. Same refusals as `fit_config`.
     * JS: `chart.fit_y_axes_config(JSON.stringify(cfg), 0.05)`
     */
    fit_y_axes_config(config_json: string, padding: number): string;
    /**
     * Format numerical category/box/radar labels from resident GPU values.
     * The host supplies no retained source arrays; the public model owns formatting.
     */
    format_value_labels(): Promise<string>;
    /**
     * Process pending pool maintenance and draw only when visual state is
     * dirty. A clean rAF tick returns before touching the pool or surface.
     */
    frame(): void;
    /**
     * Whether the last frame drew every series of the chart (#299): false
     * while a series waits for its pipelines' background compile, which
     * the frames that follow draw as they resolve.
     */
    frame_complete(): boolean;
    /**
     * Serialize the full chart option SSoT to a JSON string.
     * JS: `const cfg = JSON.parse(chart.get_config());`
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     * Positions and sizes in it (`chart_area`, margins, decoration offsets)
     * are document logical pixels, not canvas pixels.
     */
    get_config(): FiggyJson;
    /**
     * Serialize the series declarations (columns, render type, styles).
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    get_series(): FiggyJson;
    /**
     * Read-only accounting. These are requested GPU allocations, not a
     * driver VRAM measurement; retired bytes remain charged until the
     * queue completion callback fires.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     * Sizes are in bytes.
     */
    gpu_memory_status(): FiggyJson;
    /**
     * Host fence: does not borrow the chart while GPU work completes.
     */
    gpu_ready(): Promise<any>;
    /**
     * `true` while a chart element or an annotation is selected.
     */
    has_selection(): boolean;
    /**
     * The topmost drawn annotation under a point in physical canvas
     * pixels, as its index.
     *
     * `x`, `y` are physical canvas pixels (the canvas's `width`/`height`
     * space, not CSS pixels).
     */
    hit_annotation(x: number, y: number): number | undefined;
    /**
     * Hit-test the chart chrome at canvas pixel `(x, y)` — returns the
     * stable id of the element under the point (where padded hit regions
     * overlap, the one the pointer is visually on, #272) (`"data_area"`, `"axis_bottom"`,
     * `"tick_labels_left"`, `"axis_title_left"`, `"colorbar"`,
     * `"colorbar_axis"`, `"colorbar_tick_labels"`,
     * `"colorbar_title"`, …) or `null`. Pure geometry, no selection state
     * change: the renderer's own layout answers, so hosts don't have to
     * re-derive box positions for hover cursors / context UI. The set of
     * registered elements follows the active layer: while an overlay is
     * active its own Y axis answers as `"overlay_<n>:axis_right"`,
     * `"overlay_<n>:tick_labels_right"` and `"overlay_<n>:axis_title_right"`
     * (with `link_y` on, the parent's left axis, labels and title answer
     * instead), its own X axis, while `link_x` is off, as
     * `"overlay_<n>:axis_top"`, `"overlay_<n>:tick_labels_top"` and
     * `"overlay_<n>:axis_title_top"` in place of the parent's top axis, and
     * its legend as `"overlay_<n>:legend"`.
     * While the annotation layer is active (and shown) its drawn items
     * sit on top and answer as `"annotation_<n>"`; on every other layer
     * they are not registered and clicks pass through them.
     *
     * `x`, `y` are physical canvas pixels (the canvas's `width`/`height`
     * space, not CSS pixels). Returns the plain id string, not JSON.
     */
    hit_test(x: number, y: number): string | undefined;
    /**
     * The subplots that are insets now (nested in another panel's plot),
     * bottom to top, as a JSON array of indices.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    insets(): FiggyJson;
    /**
     * Metadata-only admission for incoming columns; no payload is read,
     * registered, uploaded, or reserved. Chart-derived buffers are excluded.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     * Sizes are in bytes.
     */
    inspect_column_admission(lengths: Float64Array): FiggyJson;
    /**
     * The displayed geometry of a document and its panels, read-only
     * (#312). Without a config it is the installed document as the canvas
     * shows it; with a `Config` JSON it is that candidate, placed on this
     * canvas the way `set_config` would place it, and nothing is
     * installed. A candidate whose overlays, subplots or line offsets
     * cannot be laid out is refused with code `layout`.
     *
     * `surface_width` and `surface_height` (#334), physical pixels, lay
     * the document (or the candidate) out as a canvas of that size would
     * show it, the way the chart reports it after `resize(width,
     * height)`; the canvas and its surface are not resized. Give both or
     * neither: one alone, or a dimension that is not a whole number of
     * pixels from 1, is refused with code `invalid_size`. Without them the
     * call reads the canvas as before.
     *
     * Returns JSON `{ scale, surface, document_area, active_layer, panels }`:
     * `scale` is canvas pixels per document pixel, `surface` the canvas
     * size, and every rect a `{ document, canvas }` pair of
     * `[x, y, w, h]`, in document and physical canvas pixels. `panels`
     * lists every panel in the order the renderer draws them (base,
     * overlays, line offset members, then each subplot's panels), each
     * `{ index, layer, subplot, member, frame, data_area }`: `layer` as
     * `set_active_layer` takes it, `member` the line offset series a
     * member panel draws, `frame` its chart's `chart_area` and
     * `data_area` its exact data area (`null` without one). An overlay
     * and a member share their chart's frame and data area.
     * JS: `const layout = JSON.parse(chart.inspect_document_layout());`
     */
    inspect_document_layout(config_json?: string | null, surface_width?: number | null, surface_height?: number | null): string;
    /**
     * Whether a candidate document could stream (#311), checked with the
     * renderer's own streaming rules (`Renderer::inspect_streaming_candidate`,
     * the rules `streaming_capabilities` applies to the current chart)
     * without changing anything: no state is read but the two JSON
     * strings, and the candidate need not be valid for this chart's columns.
     * Returns `{ "supported": true, "reason": null }` or
     * `{ "supported": false, "reason": "<the first rule it breaks>" }`.
     * JSON that does not parse as a `Config` or a series list throws.
     *
     * JS: `const { supported, reason } = JSON.parse(chart.inspect_streaming_capabilities(cfg, series));`
     */
    inspect_streaming_capabilities(config_json: string, series_json: string): string;
    /**
     * Queue cancellation only when an automatic stream is active.
     *
     * Returns a plain string, not JSON.
     */
    interrupt_render(): "stream_cancel_queued" | "resident";
    /**
     * One legend row for series `series_id` as the auto legend writes it
     * (#312): its symbol, drawn from the series' style and the chart's
     * colourbar map and naming the series, a space, the `"\t"` column
     * separator and the series' label. Returns the row's `RichSegment`s as
     * a JSON array; append them to `legend.content.segments` (after a
     * `"\n"` segment when the legend has rows) with `set_config`, and the
     * rest of the legend keeps its text. A series without a label gets an
     * empty label. An unknown series is refused with code `series`.
     * JS: `const row = JSON.parse(chart.legend_entry("fit"));`
     */
    legend_entry(series_id: string): string;
    /**
     * Load the bundled demo (sine + RC charge curves) — lets a frontend
     * see a real chart without wiring data first. Repeated calls replace
     * the demo registrations and keep the same series declarations.
     */
    load_demo(): void;
    /**
     * The chart's monotonic groups, each once, as a JSON array of names
     * (#271): the groups whose sources `resize_monotonic`, `fit_layout`
     * and the monotonic exports take. Empty for a chart without them.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    monotonic_groups(): FiggyJson;
    /**
     * The monotonic series that need their group's source before they
     * can be drawn, as JSON `[{ series_id, group, change }]` (#271):
     * series whose group was never supplied, which draw nothing until
     * `set_monotonic` supplies it. A call that moves the mapping takes the
     * source or is refused, so no other series is listed.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    needs_source(): FiggyJson;
    /**
     * Move among source rows represented in the completed packed view.
     * Returns only the original source index; no source or GPU readback.
     *
     * Returns a number, or `undefined`.
     */
    next_view_point_index(source_id: string | null | undefined, series_id: string, current: number, forward: boolean): number | undefined;
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
    /**
     * Pointer release: ends the drag or handle drag, and releases a held
     * display placement so a document a subplot drag grew fits the canvas
     * again (#205).
     */
    on_release(): void;
    /**
     * The panel on top at physical canvas point `(x, y)` (#312), as JSON
     * `{ layer, panel, subplot, active, in_data_area, document }`, or
     * `null` off every frame. Subplot frames win over the parent chart:
     * the one drawn on top (insets in paint order, then subplots of their
     * own, later over earlier), the same rule a base-layer press uses.
     * Where the active layer is an overlay of the chart found, the
     * overlay is reported, since it is drawn over its chart's frame; the
     * annotation layer, while active and shown, is reported on the parent
     * frame outside every subplot. `panel` indexes
     * `inspect_document_layout`'s `panels`, `active` says whether `layer`
     * is the active layer, `in_data_area` whether the point is inside that
     * chart's exact data area, and `document` is the point in document
     * pixels.
     * JS: `const hit = JSON.parse(chart.panel_at(x, y));`
     */
    panel_at(x: number, y: number): string;
    /**
     * Pick at canvas pixel `(x, y)` (#381, #399): the series that owns
     * the drawn ink nearest to the cursor decides. A point-data owner
     * answers its datum nearest to the cursor, a body or fill owner its
     * typed hit; value labels and DataLess series, which draw no ink
     * mask, answer by their typed hit. Unlike `pick_point`, this includes
     * histogram bins, canonical heatmap cells and contour levels.
     * `distance_px` is the distance to the picked datum and can exceed
     * `max_distance_px`. Before the chart's first drawn frame nothing is
     * picked. The tagged result contains only stable
     * source/series indices plus `distance_px`; values and geometry stay
     * in the renderer's GPU-backed SSoT. Resolves to `undefined` on miss.
     *
     * Resolves to JSON text (`FiggyJson`), not an object. `x`, `y` and
     * `max_distance_px` are physical canvas pixels.
     */
    pick_data(x: number, y: number, max_distance_px: number): Promise<FiggyJson | undefined>;
    /**
     * Pick at canvas pixel `(x, y)` (#381): a hit when the chart's drawn
     * data has ink within `max_distance_px` of it and the topmost series
     * that drew the nearest inked pixel has point data, naming that
     * series' datum nearest to the cursor. Ink of a body series (bars,
     * bins, cells) answers no point hit; `pick_data` answers its typed hit.
     * Resolves to a JSON string
     * `{ source_id, series_id, point_index, distance_px, nearest }`:
     * `nearest` lists every pickable series' datum nearest to the cursor
     * (`{ layer, source_id, series_id, point_index, distance_px }`), and
     * when no drawn ink is within `max_distance_px` the point fields are
     * `null` and `nearest` is still filled (#381). A streamed display's
     * pick resolves to `{ source_id, series_id, point_index, distance_px }`
     * or `undefined` on a miss, as before.
     * On a chart that draws value labels a label under the pointer wins
     * (it is drawn over the data): the hit then names the label's series,
     * its category as `point_index`, and its `label_id`
     * (`"series:<series_id>:label:<index>"`), which `press_value_label`
     * takes to drag it.
     * The `<figgy-chart>` facade parses the string and normalizes
     * `undefined` to `null`.
     *
     * Resolves to JSON text (`FiggyJson`), not an object. `x`, `y` and
     * `max_distance_px` are physical canvas pixels.
     */
    pick_point(x: number, y: number, max_distance_px: number): Promise<FiggyJson | undefined>;
    /**
     * Every background compile that failed (#299), in order, as
     * `[{ label, kind, message }]`. `kind` is `"validation"` or
     * `"internal"` (the browser's `GPUPipelineError` reason), `"rejected"`
     * (any other rejection), `"device_lost"` or `"cancelled"`.
     *
     * JS: `for (const { label, kind } of chart.pipeline_failures()) …`
     *
     * Returns an array of plain objects, not a JSON string.
     */
    pipeline_failures(): FiggyPipelineFailure[];
    /**
     * The chart's background pipeline compiles (#299) as an object:
     * `{ screen: { total, ready, compiling, failed }, all: { … },
     * frame_complete }`. `screen` counts what the last frame needed, so a
     * progress bar over it never goes back; `all` grows when a chart first
     * needs a module compiled on demand. `compiling` counts the waiting
     * compiles too.
     *
     * JS: `const { screen, all, frame_complete } = chart.pipeline_status();`
     */
    pipeline_status(): FiggyPipelineStatus;
    /**
     * Resolves once every background compile scheduled so far has ended
     * (#299). It rejects like [`Self::series_ready`] with the first that
     * failed. It draws nothing.
     *
     * JS: `await chart.pipelines_ready();`
     */
    pipelines_ready(): Promise<void>;
    /**
     * Commit the automatic layout of the Feynman series `series_id`
     * (#234): every unplaced vertex gets the place it is drawn at.
     * Returns whether anything was written. The wrapper commits it on
     * registration already; a host that edits the series in place calls
     * this to fix the new vertices.
     */
    place_feynman_vertices(series_id: string): boolean;
    /**
     * The anchor (`Anchor` JSON) at a point in physical canvas pixels,
     * as `"Data"` or `"Ratio"`, for placing a new text box or arrow
     * where the user clicked. `null` when the point has no data
     * position (outside a log axis, or the chart has no value axes).
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    pointer_to_anchor(x: number, y: number, kind: string): FiggyJson;
    /**
     * Refresh the registered chart's data and pick masks without presenting it.
     * A host can probe temporary series without replacing the canvas contents.
     */
    prepare_data_pick(): Promise<void>;
    /**
     * Refresh renderer-owned annotation geometry without submitting a frame.
     */
    prepare_interaction(): void;
    /**
     * Press on an energy-level label (#203): row `index` of the list `part`
     * (`"level"`, `"transition"`, `"limit"` or `"band"`) of series `series_id`, as a
     * `pick_point` hit names it. The label becomes the typed selection and
     * the drag starts, as `press_value_label` does; `on_move` writes the
     * row's `label_offset`. Returns `false` and changes nothing for a row
     * without a label.
     * JS: `if (hit?.kind === "value_label" && hit.part) chart.press_energy_label(hit.series_id, hit.part, hit.category_index);`
     */
    press_energy_label(series_id: string, part: string, index: number): boolean;
    /**
     * Press on a part of a Feynman series (#234), as a `pick_point` hit
     * names it: `kind` is `"feynman_vertex"`, `"feynman_propagator"` or
     * `"feynman_label"` (with `part` `"vertex"`, `"propagator"` or
     * `"momentum"`), `index` its row. The part becomes the typed selection
     * and the drag starts: `on_move` moves a vertex (the first drag commits
     * the layout) or bends a propagator through `Renderer::drag_feynman`,
     * and moves a label through the value-label drag, as
     * `press_value_label` does. Returns `false` and changes nothing for a
     * row that does not exist.
     * JS: `if (hit?.kind?.startsWith("feynman_")) chart.press_feynman(hit.series_id, hit.kind, hit.index, hit.part);`
     */
    press_feynman(series_id: string, kind: string, index: number, part?: string | null): boolean;
    /**
     * Press on a dependency link (#357): link `index` of the range link
     * series `series_id`, as a `pick_data` hit names it (a histogram bin of
     * that series). The link becomes the data selection and the drag
     * starts: `on_move` moves its exit along the predecessor's edge
     * (`drag_link_exit`, moving a shared trunk as one and snapping back to
     * unset within 3 px of `inset`) and `on_release` ends it. `extent_px`
     * is the hit's `extent_px`, the link's predecessor's drawn length in
     * canvas pixels: the exit is stored as a fraction of it (#357), between
     * the bar's start and end, so the drag needs it; without it the drag
     * moves nothing. Returns `false`
     * and changes nothing for an id or index that names no link.
     * JS: `const hit = JSON.parse(await chart.pick_data(x, y, 6));`
     * `if (hit?.kind === "histogram_bin") chart.press_range_link(hit.series_id, hit.bin_index, hit.extent_px);`
     */
    press_range_link(series_id: string, index: number, extent_px?: number | null): boolean;
    /**
     * Press on a value label: the label a `pick_point` or `pick_data` hit
     * names under the pointer, by its `label_id`
     * (`"series:<series_id>:label:<index>"`). The label becomes the typed
     * data selection (`picked_data`, outlined by its frame), any element
     * or annotation selection is cleared, and the drag starts: `on_move`
     * moves the label (writing the series' `labels.offsets`) and
     * `on_release` ends it. Returns `false` and changes nothing for an id
     * that names no value label of the chart's series.
     * JS: `const hit = JSON.parse(await chart.pick_point(x, y, 8));`
     * `if (hit?.label_id) chart.press_value_label(hit.label_id);`
     */
    press_value_label(label_id: string): boolean;
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
     * kernel from the callback. An exception the callback throws rejects
     * the returned promise with it once the prewarm returns; later stages
     * are not reported.
     */
    prewarm_all_with_progress(on_event: Function): Promise<void>;
    /**
     * Compile the GPU picker and prepare it for the current chart.
     * Repeated calls, including retries, reuse renderer-owned state.
     */
    prewarm_gpu_picking(): Promise<void>;
    /**
     * A handle on the chart's background pipeline compiles that does not
     * borrow the chart (#315): see [`FiggyReadiness`]. Its waits leave the
     * chart free for `pipeline_status()`, `frame()`, `resize()` and
     * `free()`; once the chart is freed they reject with a
     * `"chart disposed"` `Error`. `series_ready()`, `pipelines_ready()` and
     * `first_frame_ready()` on the chart keep working as before.
     *
     * JS: `const readiness = chart.readiness(); await readiness.pipelines_ready();`
     */
    readiness(): FiggyReadiness;
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
     * Register or replace the ragged column `id`: `offsets.len() - 1`
     * groups, group `g` being `values[offsets[g]..offsets[g + 1]]`.
     *
     * `offsets` starts at 0, never decreases, holds integers and ends at
     * `values.len()`; anything else is an error and nothing is registered.
     * Both arrays upload as `(hi, lo)` pairs in one batch, through the same
     * borrowed adapters as `register_columns_f64`. Resident only, as
     * `register_record`.
     */
    register_ragged(id: string, values: Float64Array, offsets: Float64Array): void;
    /**
     * Register or replace the box plot record `id` (the schema
     * `renderer::BOX_PLOT_RECORD`).
     *
     * `fields` is an object whose keys are field names and whose values are
     * `Float32Array`s or `Float64Array`s of one length, one row per box:
     * `median`, `q1`, `q3`, `whisker_low` and `whisker_high` are required;
     * `mean`, `sample_count`, `ci_low` and `ci_high` are optional and read as
     * NaN when absent. A missing box is a row of NaN. The arrays are read in
     * place and written straight into one batch upload; nothing is copied.
     * An unknown field, a missing required field or unequal lengths are
     * errors, and nothing is registered. Records are resident only: a
     * streamed id, or an id that is a column or a ragged column, is
     * rejected.
     */
    register_record(id: string, fields: any): void;
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
     * Register or replace the triangle index column `id` (#210): three
     * vertex indices per triangle, triangle `t` being the vertices
     * `indices[3t]`, `indices[3t + 1]` and `indices[3t + 2]`.
     *
     * `indices` is a `Uint32Array` whose length is a non-zero multiple of 3;
     * anything else is an error and nothing is registered. wasm-bindgen
     * copies the JS array into wasm memory for the call; that call-scoped
     * copy is uploaded and dropped when the call returns, and every index up
     * to `u32::MAX` reaches the GPU exactly. Resident only, as
     * `register_record`.
     */
    register_triangles(id: string, indices: Uint32Array): void;
    /**
     * Compact live resident columns, drop the unused pool slab, and wait
     * for the device completion fence before reporting reclaimed bytes.
     * The 16 MiB startup slab remains as the minimum reusable pool.
     *
     * Resolves to JSON text (`FiggyJson`) in the shape of `gpu_memory_status`,
     * not an object.
     */
    release_unused_gpu_memory(): Promise<FiggyJson>;
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
     * Unregister the triangle index column `id` and free its GPU memory.
     * Returns `true` when it existed.
     */
    remove_triangles(id: string): boolean;
    /**
     * Every warning of the last drawn frame (#312), as a JSON array: tick
     * settings the axis raster drew differently from how they were
     * written, on any axis of any panel, and annotations the raster
     * skipped. Each is `{ kind, ..., message }`: `MajorSpacingReplaced`
     * and `LogDecadeStepAdjusted` (`axis`, `requested`, `used`; a
     * replaced spacing also has `reason` and, for `TooManyTicks`,
     * `limit`), `MinorCountClamped` (`axis`, `requested`, `used`) and
     * `AnnotationSkipped` (`index`, `reason`). `axis` is the `Config`
     * field path (`"bottom_x"`, `"overlays[0].y_axis"`,
     * `"subplots[1].config.left_y"`), a non-finite number is `null`, and
     * `message` is one line naming the setting and both values. A later
     * kind has `kind: "Other"`. The list is the one `frame` last
     * rasterized; `annotation_warnings` is its annotation part.
     * JS: `for (const w of JSON.parse(chart.render_warnings())) console.warn(w.message);`
     */
    render_warnings(): string;
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
     * Move this chart to at least the shader set `shaders` (`"basic"` or
     * `"full"`, #299), as its first chart with an axis break, a
     * probability axis or polar coordinates would. A chart never goes
     * back, so `"basic"` and a repeated `"full"` do nothing. Any other
     * value throws an `Error` that names it.
     */
    require_shader_set(shaders: any): void;
    /**
     * Explicitly rebuild the auto legend from `SeriesConfig.label`: every
     * auto legend row from the series' label; a series without one gets no
     * row.
     */
    reset_legend_from_series_labels(): void;
    /**
     * Resize the swap chain viewport. The chart Config keeps its
     * document/export `chart_area`; live rendering scales that logical
     * document into this surface.
     */
    resize(width: number, height: number): void;
    /**
     * Resizes the canvas surface to `width` × `height` device pixels on a
     * chart with monotonic series (#271), and the plot to `plot_area`
     * (`{ x, y, width, height }` in document pixels, as
     * `take_plot_resize_request` proposes it; `undefined` keeps the
     * margins): the resize call that takes the groups' sources,
     * `[{ group, start, interval, data, stride?, columns? }]`, `data` as
     * `set_monotonic` takes it. Each group whose series the resize maps to
     * other device pixels is reduced again in this call. Atomic: without a
     * source a moved group needs, the call is refused with
     * `MonotonicSourceRequired` and changes nothing; `resize` refuses such
     * a chart the same way.
     */
    resize_monotonic(width: number, height: number, sources: Array<any>, plot_area: any): void;
    /**
     * Select one annotation (its box and handles are drawn on the
     * overlay) or none. Selecting an annotation clears the decoration
     * selection; selecting a decoration with `on_press` clears this.
     */
    select_annotation(index?: number | null): void;
    /**
     * Select the annotation whose `id` is `id`, like `select_annotation`
     * with its index (#315). Errors when no annotation, or more than one,
     * has that id, or when `id` is empty; the selection is unchanged then.
     *
     * JS: `chart.select_annotation_by_id("peak");`
     */
    select_annotation_by_id(id: string): void;
    /**
     * The index of the selected annotation, or `undefined`. An index is
     * valid until the annotation list changes (see `annotation_index`).
     */
    selected_annotation(): number | undefined;
    /**
     * Inspect the first resident typed selection as JSON, or `"null"` when
     * none is selected. Only selected GPU samples are read back. Histograms
     * expose `bin_start`, `bin_end`, `value`, and `orientation`; the value
     * is the stored height (also valid for weighted/density histograms).
     * Point and matrix selections expose their coordinates and cell value.
     *
     * Resolves to JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    selection_details(): Promise<FiggyJson>;
    /**
     * Report the effective primitive/grid extent currently drawn.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     * `{ drawn_count, cols, rows, truncated }`: counts, not pixels.
     */
    series_draw_info(series_id: string): FiggyJson;
    /**
     * Resolves once a frame draws every series of the chart (#299),
     * drawing again as the pipelines it waits for compile. It rejects with
     * an `Error` carrying `label`, `kind` and `message` when one of those
     * compiles failed (see [`Self::pipeline_failures`]); the chart still
     * draws that series, and the draw reports the error as usual.
     *
     * JS: `await chart.series_ready();`
     */
    series_ready(): Promise<void>;
    /**
     * Set the layer that receives pointer interaction: `"Base"`,
     * `{ "Overlay": index }`, `"Annotations"`, `{ "Subplot": index }` or
     * `{ "SubplotOverlay": [subplot, overlay] }` as JSON. The hit map is
     * rebuilt for that layer (`HitMap::for_active_layer`) and the
     * element selection is cleared when the layer changes. An overlay
     * index past the overlay list is stored as `"Base"`; the stored
     * layer is returned as JSON. Drawn pixels never depend on it.
     * JS: `chart.set_active_layer(JSON.stringify({ Overlay: 0 }))`
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    set_active_layer(json: string): FiggyJson;
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
     * Fill the chart area with a colour under everything the chart draws
     * (JSON `{"r":1,"g":1,"b":1,"a":1}`), or leave it transparent (`null`)
     * so the page or the export's clear colour shows through (#265).
     */
    set_background(json: string): void;
    /**
     * Open a legacy box plot document (`BoxPlotChart` JSON, what
     * `FiggyBoundedChart` took as the `"boxplot"` family) as this Cartesian
     * chart.
     *
     * `Config::from_boxplot` turns the document into a config with a
     * categorical axis and a grouped `bar_groups`, one `BoxPlot` series per
     * document series and what those read: the category positions
     * (`boxplot.positions`, a registry column), and per series its record
     * of box statistics (`boxplot.record.<series id>`, as `register_record`
     * registers one) and, when it has outliers, its ragged outlier column
     * (`boxplot.outliers.<series id>`, as `register_ragged`). The summaries
     * upload through borrowed adapters; nothing is copied. Without a
     * document `value_range` the value axis is fitted to the records' and
     * outliers' statistics with a tenth of the span as padding and rounded
     * to nice ticks. The chart keeps its chart area, and an explicit
     * `decorations.data_area` (logical pixels, edges rounded to whole
     * pixels) is the data area in it (`Config::fit_legacy_data_area`, #334)
     * unless the layout cannot hold it, which keeps the automatic layout; the series, columns,
     * records and config of a box plot document opened before are
     * replaced, every other column stays. From here on the chart is edited
     * through the Cartesian API.
     *
     * The replace is atomic (#311): see "Document replace" on
     * [`Self::set_radar_document`]. The ids are the documented ones for
     * every document opened.
     *
     * Returns the conversion report and takes the loss policy described
     * in "Review and apply" on [`Self::set_radar_document`] (#334).
     *
     * JS: `const report = JSON.parse(chart.set_boxplot_document(JSON.stringify(doc), JSON.stringify({ refuse: "any" })));`
     */
    set_boxplot_document(json: string, options?: string | null): string;
    /**
     * Open a legacy categorical bar chart document (`CategoricalChart` JSON,
     * what `FiggyBoundedChart` took as the `"categorical"` family) as this
     * Cartesian chart.
     *
     * `Config::from_categorical` turns the document into a config with a
     * categorical axis and `bar_groups`, one `CategoryBars` series per
     * document series and the columns those read: the category positions
     * (`categorical.positions`) and one value column per series
     * (`categorical.values.<series id>`), registered as one batch. The
     * value axis is fitted to the bars from the columns' statistics and
     * rounded to nice ticks. The chart keeps its chart area, and an explicit
     * `decorations.data_area` (logical pixels, edges rounded to whole
     * pixels) is the data area in it (`Config::fit_legacy_data_area`, #334)
     * unless the layout cannot hold it, which keeps the automatic layout; the series,
     * columns and config of a categorical document opened before
     * are replaced, every other column stays. From here on the chart is
     * edited through the Cartesian API (`get_config` / `set_config`,
     * `get_series` / `set_series`, the column registry).
     *
     * The replace is atomic (#311): see "Document replace" on
     * [`Self::set_radar_document`]. The ids are the documented ones for
     * every document opened.
     *
     * Returns the conversion report and takes the loss policy described
     * in "Review and apply" on [`Self::set_radar_document`] (#334).
     *
     * JS: `const report = JSON.parse(chart.set_categorical_document(JSON.stringify(doc), JSON.stringify({ refuse: "any" })));`
     */
    set_categorical_document(json: string, options?: string | null): string;
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
     * Set the colourbar title text, a label with `$…$` spans as TeX, and
     * make it visible. An empty string
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
     * Install coupled chart metadata in one renderer transaction.
     */
    set_host_state(config: string, series: string): void;
    /**
     * Set the exit of link `index` of the range link series `series_id`
     * (#357), a fraction `0..=1` of its predecessor's drawn length from
     * the start; `undefined` or a non-finite value clears it, so the next
     * layout chooses. Returns `false` and changes nothing for an unknown
     * series, an index past its links or a fraction outside `0..=1`.
     */
    set_link_exit_offset(series_id: string, index: number, offset?: number | null): boolean;
    /**
     * The full call of monotonic group `group` (#271): every series of
     * the chart that names the group is reduced in full from `data`, its
     * samples at `x = start + i × interval`. `data` is an `Array` of typed
     * arrays, one per channel (leave `stride` and `columns` undefined), or
     * one interleaved typed array with `stride` values per frame, its
     * channels the frame `columns` (every column by default). Any of
     * `Float64Array`, `Float32Array`, `Int32Array`, `Int16Array`,
     * `Uint16Array` and `Uint8Array`. `range` sets the x range of the
     * group's axes, the only call that does: `[x_min, x_max]`, or
     * `"autoscale"` to fit the x range to the samples' span and each y axis
     * the group draws on to the values every monotonic series on that axis
     * keeps, this group's and any other's (the general auto-fit refuses the
     * chart). Returns `{ len, truncated, dropped, x_range, pixel_offset }`
     * as JSON.
     * JS: `chart.set_monotonic("daq", 0, 1e-3, [ch0, ch1], "autoscale")`
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    set_monotonic(group: string, start: number, interval: number, data: any, range: any, stride?: number | null, columns?: Uint32Array | null): FiggyJson;
    /**
     * Shows a monotonic chart (#271): `config_json` and `series_json`, a
     * document and series as `set_config` and `set_series` take them,
     * registered as a monotonic chart, which alone may hold monotonic line
     * series. Its x range and plot are written only by `set_monotonic`,
     * `append_monotonic`, `resize_monotonic` and `fit_layout`; every other
     * setter edits its document as on any chart and refuses a document
     * that would move them. Its monotonic series draw nothing until their
     * group's first `set_monotonic`. A previous monotonic chart is
     * replaced; `clear_monotonic_document` shows the general chart again.
     */
    set_monotonic_document(config_json: string, series_json: string): void;
    /**
     * Replace the chart's selection (`picked_data`). Passing JSON `null`
     * clears it.
     */
    set_picked_data(json: string): void;
    /**
     * Pool growth on an otherwise out-of-space upload, on by default.
     * Growth remains bounded by the device storage-binding limit and
     * the configured renderer memory budget; `false` keeps the pool's
     * current capacity.
     */
    set_pool_auto_growth(enabled: boolean): void;
    /**
     * Open a legacy radar document (`RadarChart` JSON, what
     * `FiggyBoundedChart` took as the `"radar"` family) as this polar chart.
     *
     * `Config::from_radar` turns the document into a polar config whose
     * angle axis holds the document's categories, one `Radar` series per
     * document series and the columns those read: the category indices
     * (`radar.positions`) and one value column per series
     * (`radar.values.<series id>`). The values upload through borrowed
     * adapters; nothing is copied. Without a document `value_range` the
     * radius axis is fitted to the value columns' statistics, from zero
     * when no value is negative (as the former chart fitted it), and
     * rounded to nice ticks; a document `ring_spacing` is the ring spacing
     * either way. The chart keeps its chart area, and an explicit
     * `decorations.data_area` (logical pixels, edges rounded to whole
     * pixels) is the data area in it (`Config::fit_legacy_data_area`, #334)
     * unless the layout cannot hold it, which keeps the automatic layout; the series, columns and
     * config of a radar document opened before are replaced, every other
     * column stays. From here on the chart is edited through the Cartesian
     * API (`get_config` / `set_config`, `get_series` / `set_series`, the
     * column registry), and its vertices pick, select and step as points.
     *
     * # Review and apply
     *
     * The three document calls convert the document once, on this chart's
     * chart area (`Config::from_*_with_report_in`, #334), and install that
     * conversion. They return its report as JSON, `{config, series,
     * uploads, columns, notes}`, which is what `convert_*_document` returns
     * with `{"chart_area": [x, y, width, height]}` set to this chart's
     * chart area. The report's `config` is the converted one; the
     * installed config also has its value axis fitted (`get_config`).
     * `options` is an optional JSON object `{"refuse"?: ["path", ...] |
     * "any"}`: when a note's path is a listed path or lies under one
     * (followed by `.` or `[`), or with `"any"` when there is any note,
     * the call rejects at `"validate"` with `code` `"conversion_loss"` and
     * the refused notes as `notes`, before anything is installed. Other
     * option fields, or another `refuse`, reject at `"validate"` with
     * `code` `"invalid_options"`.
     *
     * # Document replace
     *
     * The three document calls replace the chart atomically (#311), in
     * one renderer transaction. They prepare the candidate config, series
     * and uploads, check them (styles; each documented id is free or holds
     * what the document uploads under it: a column, a record or a ragged
     * column, and is not streamed), then upload every column, record and
     * ragged column under its documented id (`radar.positions`,
     * `boxplot.record.<series id>`, ...), fit the axes from the candidate
     * columns, and commit the columns, the removal of the previous
     * document's columns and the chart's config and series in one step.
     * The previous document's columns are each id under `categorical.`,
     * `boxplot.` or `radar.` that the replaced series read, of whichever
     * family, that the new document does not upload again; an id it does
     * upload again is replaced in place. The ids are therefore the
     * documented ones for every document opened.
     * On a chart that shows a monotonic document
     * (`set_monotonic_document`), the document replaces the general chart
     * behind it and the monotonic chart ends with the commit, as
     * `clear_monotonic_document` ends it; a failure leaves the monotonic
     * document shown.
     *
     * A failure rejects with an `Error` whose `stage` is `"validate"`
     * (parse, validation, styles, ids), `"upload"` (a column that the GPU or the memory budget cannot hold, with the `code` and byte fields of
     * `register_column_f32`), `"fit"` or `"commit"` (the series checks
     * against the candidate columns, the chart's revisions, the picker)
     * and whose message names the stage and the cause. The chart's
     * config, series, columns, element and data selections, picks and
     * image are then exactly as they were: nothing reaches the chart
     * before the commit, which cannot fail. Only a broken internal
     * invariant after the commit (the monotonic chart or the chart itself
     * gone) rejects then, with an error that names it as internal and no
     * `stage`; the new document is shown in that case.
     *
     * Memory: the transaction builds a complete candidate column pool, so
     * at the peak the GPU holds the live pool slab, the new document's
     * staging (half of it for single-lane columns, plus their transient
     * expansion buffer) and a candidate slab of the pool's capacity — or a
     * grown one, twice the capacity or what the surviving columns and the
     * new document need, when they do not fit. The previous document's
     * columns take no room in the candidate. After the commit the former
     * slab stays as the pool's backup when the capacity did not change.
     * A memory budget that cannot hold the peak refuses the call at the
     * upload stage with `code` `"budget_exceeded"`.
     *
     * JS: `const report = JSON.parse(chart.set_radar_document(JSON.stringify(doc), JSON.stringify({ refuse: "any" })));`
     */
    set_radar_document(json: string, options?: string | null): string;
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
     * unicode sub/superscripts (`₀`, `⁻`, …) map to styled segments;
     * `$…$` spans are TeX and `\$` is a dollar sign.
     * Empty string removes the legend row. Returns `true` when the
     * series exists.
     */
    set_series_label(series_id: string, label: string): boolean;
    /**
     * Hold or release the snap modifier (Alt / Option, #440): while it is
     * held, a decoration or annotation drag follows the pointer exactly
     * and shows no guide; released, the drag snaps again. A host calls
     * it from its key or pointer events (`event.altKey`).
     *
     * JS: `chart.set_snap_modifier(event.altKey);`
     */
    set_snap_modifier(held: boolean): void;
    set_stream_chunk_budget(primitives: number): void;
    set_stream_operation_chunk_budget(handle: StreamingOperationHandle, max_primitives: number): void;
    /**
     * Place subplot `index`'s frame at `(x, y)` with `width` x `height`, in
     * document pixels (the coordinates of `get_config`'s `chart_area`s):
     * anywhere, inside the parent chart (an inset), over another panel or
     * beside every one. The subplot's plot must fit in the frame; an error
     * leaves the document unchanged. A pointer drag on the frame does the
     * same on the base layer. The insets nested in this subplot's plot
     * move with it, and an inset follows later moves and resizes of the
     * plot it is nested in from where it was put (#392).
     * JS: `chart.set_subplot_area(0, 120, 80, 320, 240);`
     */
    set_subplot_area(index: number, x: number, y: number, width: number, height: number): void;
    /**
     * Fill subplot `index`'s plot with a colour (JSON `{"r":1,"g":1,"b":1,
     * "a":1}`) or leave it transparent (`null`): an inset usually covers
     * the parent's data under it.
     */
    set_subplot_background(index: number, json: string): void;
    /**
     * How subplot `index`'s text follows its cell (#292): `"Auto"` (the
     * default) draws its titles, tick labels, legend and colourbar text at
     * the stored sizes times `subplot_text_factor(index)`; `"Fixed"` draws
     * the stored sizes. The stored sizes are never changed;
     * [`Self::subplot_text_scale`] reads the mode back.
     * JS: `chart.set_subplot_text_scale(0, "Fixed");`
     */
    set_subplot_text_scale(index: number, mode: string): void;
    /**
     * Set the title text and grow its band if needed. Like every text
     * setter (`set_x_title`, `set_y_title`, `set_colorbar_title`, and the
     * labels of `add_line_series` and `set_series_label`), it reads the
     * text as matplotlib reads a label: `$…$`, `\(…\)` and `$$…$$` spans
     * are TeX, `\$` is a dollar sign, and text whose TeX does not parse is
     * shown as written. For a text-only edit that keeps the exact margin,
     * use `get_config` / `set_config` and change only `chart_title.text`.
     */
    set_title(text: string): void;
    /**
     * Set the bottom x axis title, a label with `$…$` spans as TeX.
     */
    set_x_title(text: string): void;
    /**
     * Set the left y axis title, a label with `$…$` spans as TeX.
     */
    set_y_title(text: string): void;
    /**
     * The shader set this chart compiles (#299): `"basic"` or `"full"`.
     *
     * Returns a plain string, not JSON.
     */
    shader_set(): "basic" | "full";
    /**
     * Move the resident typed data selection using source indices
     * (`Renderer::step_chart_selection`): `Config::step_selection` over
     * the chart's series and the registered column lengths, and a
     * monotonic series' point over the points its envelope keeps (#271).
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
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    stream_status(): FiggyJson;
    /**
     * Advance at most one renderer-selected chunk. `sources` contains the
     * original replayable typed arrays; only the requested range is read
     * directly into mapped staging, and no owned CPU data mirror is made.
     */
    stream_step(ids: string[], revisions: Float64Array, sources: Array<any>): StreamingStepResult;
    /**
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    streaming_capabilities(): FiggyJson;
    /**
     * Wake after work already submitted to this queue completes. The
     * returned promise owns only its completion receiver, not a chart or
     * renderer borrow. Resolving does not service receipts or draw a frame.
     */
    streaming_gpu_ready(): Promise<void>;
    streaming_usage(): StreamingUsageResult;
    /**
     * Subplot `index`'s frame as JSON `{"x":..,"y":..,"width":..,"height":..}`
     * in document pixels.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    subplot_area(index: number): FiggyJson;
    /**
     * The factor subplot `index` draws its text with now (#292,
     * `Config::subplot_text_factor`): 1 for a `"Fixed"` subplot or a cell
     * as large as the parent chart, down to 0.5 for a small cell. It
     * follows `set_subplot_area`, a frame drag and a resize of the parent
     * chart.
     */
    subplot_text_factor(index: number): number;
    /**
     * Subplot `index`'s text mode (#292, #295), as its setter
     * [`Self::set_subplot_text_scale`] takes it: `"Auto"` or `"Fixed"`.
     *
     * Returns a plain string, not JSON.
     */
    subplot_text_scale(index: number): "Auto" | "Fixed";
    /**
     * The member of the family `name` subplot `index` takes (#295), as
     * [`Self::apply_theme`] gives it there, as a plain object to edit and
     * pass to [`Self::apply_custom_theme`]. Refused as [`Self::theme`]
     * refuses the name, and with `code` `"subplot_index"` for an index
     * past the subplots.
     *
     * Returns a plain object, not a JSON string.
     */
    subplot_theme(index: number, name: string): FiggyThemeObject;
    suspend_stream_selection(): void;
    /**
     * The plot rect the last plot-area resize gesture on a chart with
     * monotonic series proposed, as JSON `{ x, y, width, height }` in
     * document pixels, or `undefined` (#271). Read once: the element emits
     * it as `figgy-plot-resize`, and the host applies it with
     * `resize_monotonic(width, height, sources, plotArea)`.
     *
     * Returns JSON text (`FiggyJson`), not an object: parse it with
     * `JSON.parse`.
     */
    take_plot_resize_request(): FiggyJson | undefined;
    /**
     * The member of the family `name` the chart takes (#295), as a plain
     * object (`Theme`'s fields, colours as `{r, g, b, a}`). Edit it and
     * pass it to [`Self::apply_custom_theme`]. A name that is not a family
     * throws an `Error` with `code` `"theme_unknown_name"` and the family
     * `names`.
     *
     * Returns a plain object, not a JSON string.
     */
    theme(name: string): FiggyThemeObject;
    /**
     * The theme names (#291, #295), as an array of strings: the four
     * families, `gallery`, `cool-slate`, `midnight` and `warm-paper`.
     *
     * Returns an array of strings, not a JSON string.
     */
    theme_names(): string[];
    /**
     * [`Self::theme`] with its series palette replaced by the preset
     * `cycle` (#357): the family's chrome and parts with, say, the
     * Okabe–Ito or ColorBrewer Set2 colours. Pass it to
     * [`Self::apply_custom_theme`]. Refused as [`Self::theme`] refuses the
     * name.
     *
     * Returns a plain object, not a JSON string.
     */
    theme_with_palette(name: string, cycle: ColorCycle): FiggyThemeObject;
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
     * Zoom a 3D chart's camera (`Config.view_3d`): the eye distance is
     * divided by `factor` and clamped (`Config::zoom_view`). Returns whether
     * the view changed; a flat chart never does.
     */
    zoom_view(factor: number): boolean;
}

/**
 * A handle on a chart's background pipeline compiles that does not borrow
 * the chart (#315), from [`FiggyChart::readiness`]. While one of its waits
 * is pending the host keeps full use of the chart: `pipeline_status()`,
 * `frame()`, `resize()` and `free()` all work. It holds the chart's compile
 * queue weakly and keeps nothing alive. Once the chart is freed a pending
 * or later wait rejects with an `Error` whose message starts with
 * `"chart disposed"`, and `status().disposed` is `true`. The handle draws
 * nothing: after `series_ready()` resolves, the host's next `frame()`
 * draws the series (or use `chart.series_ready()`, which draws, but
 * borrows the chart until it settles). Free the handle with `free()` when
 * done; freeing it ends nothing.
 *
 * A chart that compiles no pipeline in the background (one made without
 * the browser's async compile queue) gives a handle with nothing to wait
 * for: its waits resolve at once and `disposed` stays `false`.
 *
 * JS:
 * ```js
 * const readiness = chart.readiness();
 * const ready = readiness.series_ready(); // the chart stays usable
 * overlay.textContent = `${readiness.status().screen.ready} /
 * ${readiness.status().screen.total}`;
 * chart.resize(w, h);
 * await ready;
 * chart.frame();
 * ```
 */
export class FiggyReadiness {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    /**
     * Resolves once every background compile scheduled so far has ended,
     * like `chart.pipelines_ready()` but without borrowing the chart.
     * Rejects like [`Self::series_ready`].
     */
    pipelines_ready(): Promise<void>;
    /**
     * Resolves once every background compile the chart's last frame
     * needed has ended, like `chart.series_ready()` but without drawing
     * and without borrowing the chart. Rejects with an `Error` carrying
     * `label`, `kind` and `message` when one of them failed, or with a
     * `"chart disposed"` `Error` once the chart is freed. The promise owns
     * a clone of the handle; it does not borrow this object.
     */
    series_ready(): Promise<void>;
    /**
     * The chart's background compiles now, as a plain object (not a JSON
     * string): `{ screen: { total, ready, compiling, failed }, all: { … },
     * disposed }`. `screen` and `all` are as in `chart.pipeline_status()`;
     * there is no `frame_complete` (only a frame decides it, so read it on
     * the chart). `disposed` is `true` once the chart is freed; the counts
     * are zero then. Readable at any time, also while a wait is pending.
     */
    status(): FiggyReadinessStatus;
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
 * `layout::auto_layout` (#44) on a config JSON: the config with axis
 * margins, axis title offsets and tick-label formats chosen so its tick
 * labels, titles, legend and colourbar do not overlap, as the renderer
 * draws them. Pure: it reads only the JSON and the text measure and
 * changes no chart; apply the result with `set_config`. Call it again after
 * an auto-fit or a zoom, which reset a linear axis to decimal labels.
 * Errors are JSON errors.
 *
 * JS: `chart.set_config(autoLayout(chart.get_config()));`
 *
 * Returns JSON text (`FiggyJson`), not an object: parse it with `JSON.parse`.
 * Lengths in the config are document logical pixels.
 */
export function autoLayout(config_json: string): FiggyJson;

/**
 * CSS color strings (`"rgb(r g b / a)"`) for a cycle — lets the host UI
 * render swatches / legends with exactly the chart's palette.
 */
export function color_cycle_css(cycle: ColorCycle): string[];

/**
 * A legacy box plot document (`BoxPlotChart` JSON) converted without a
 * chart (`Config::from_boxplot_with_report_in`), in the shape and with the
 * `options` `convert_categorical_document` takes. A record upload is
 * `{column, role: "box_record", rows, fields}` and an outlier upload
 * `{column, role: "box_outliers", len, groups}`.
 *
 * JS: `const converted = JSON.parse(convert_boxplot_document(text));`
 */
export function convert_boxplot_document(json: string, options?: string | null): string;

/**
 * A legacy categorical bar document (`CategoricalChart` JSON) converted
 * without a chart (`Config::from_categorical_with_report_in`): `{config,
 * series, uploads, columns, notes}`. `uploads` describes each column to
 * register (`{column, role, len}`, without the values); `columns` names
 * the document series of each (`{series_id, role, column}`); `notes` lists
 * every field the document set that the chart does not carry
 * (`{path, kind: "dropped" | "changed", reason}`).
 *
 * `options` is an optional JSON object `{"chart_area"?: [x, y, width,
 * height]}` (#334): the chart area in whole logical pixels, as the chart's
 * `chart_area` (`get_config().chart_area`). The conversion places the
 * config on it and fits an explicit `decorations.data_area` to it, so the
 * result is the report `set_categorical_document` returns on a chart of
 * that chart area: the same config, series and notes. Without it, the
 * config keeps the placeholder chart area (1000 x 800) and the data area
 * is fitted to that. A data area the layout cannot hold is noted as
 * dropped with the reason. Options that are not such an object, or that
 * name another field, throw an `Error` with `code` `"invalid_options"`.
 * Throws the JSON error, or the document rule (an `Error` with a `code`),
 * as `set_categorical_document` does.
 *
 * JS: `const { config, series, notes } = JSON.parse(convert_categorical_document(text, JSON.stringify({ chart_area: chart_area_of_the_chart })));`
 */
export function convert_categorical_document(json: string, options?: string | null): string;

/**
 * A legacy radar document (`RadarChart` JSON) converted without a chart
 * (`Config::from_radar_with_report_in`), in the shape and with the
 * `options` `convert_categorical_document` takes.
 *
 * JS: `const converted = JSON.parse(convert_radar_document(text));`
 */
export function convert_radar_document(json: string, options?: string | null): string;

/**
 * The default config (`default::default_config`) as JSON: the document a
 * new chart starts from, for an editor to fill in. Its `chart_area` is a
 * placeholder the host sets.
 *
 * JS: `const config = JSON.parse(default_config());`
 */
export function default_config(): string;

/**
 * The default config for a chart of the series list JSON `series_json`
 * (`default::config_for_series`, #357) as JSON: `default_config()` in the
 * frame the series' family draws by default. A chart that draws a Feynman
 * series has no axes, grid or tick labels (`AxisPreset::Hidden`), one that
 * draws an energy-level series takes the Grotrian frame, one that draws a
 * range link series takes the timeline frame (`default_timeline_config`),
 * and every other list gives `default_config()`. The frame is chosen here, once: an
 * `apply_axis_preset` or `set_config` afterwards keeps the host's choice.
 * Throws for a series list that does not parse.
 *
 * JS: `const config = JSON.parse(default_config_for_series(JSON.stringify(series)));`
 */
export function default_config_for_series(series_json: string): FiggyJson;

/**
 * Every valid `draw_style` mode tag, as a JSON string array.
 *
 * Returns JSON text (`FiggyJson`), not an object: parse it with `JSON.parse`.
 */
export function draw_style_modes(): FiggyJson;

/**
 * Parameter metadata for one `draw_style` mode — a JSON array of
 * `{key, min, max, default, integer}`. Ranges are the RECOMMENDED
 * slider spans (the SSoT accepts values beyond them; the renderer
 * applies only safety guards), and they come from the model crate, so
 * hosts never hardcode them.
 *
 * JS: `const specs = JSON.parse(draw_style_param_specs("constellation"));`
 * Valid modes: `draw_style_modes()`.
 *
 * Returns JSON text (`FiggyJson`), not an object: parse it with `JSON.parse`.
 */
export function draw_style_param_specs(mode: string): FiggyJson;

/**
 * The layout `FiggyChart.inspect_document_layout(configJson)` reports for
 * a candidate `Config` JSON on a canvas whose surface is `surface_width` x
 * `surface_height` physical pixels, without a chart (#334): no renderer,
 * GPU device or surface is created, and the result is the JSON a chart
 * of that surface size reports for the same candidate: a canvas places
 * its document by its surface size alone, and the result's `scale` is
 * that fit. Refused with code `config_json` or `layout` as
 * `inspect_document_layout` refuses a candidate, and with `invalid_size`
 * for a dimension that is not a whole number of pixels from 1.
 *
 * JS: `const layout = JSON.parse(inspect_config_layout(cfg, canvas.width, canvas.height));`
 */
export function inspect_config_layout(config_json: string, surface_width: number, surface_height: number): string;

/**
 * A config JSON in its normalized form: read and written back, so an
 * omitted optional field takes its documented default and a field at its
 * default is written as the renderer writes it. Numbers keep every bit.
 * Throws the JSON error when the text is not a config; a config that
 * parses but breaks a rule is returned as it is (`validate_config` checks
 * it).
 *
 * JS: `const canonical = normalize_config(text);`
 */
export function normalize_config(config_json: string): string;

/**
 * A rich text from TeX (`RichText::from_tex`, #45): text with `$…$` or
 * `\(…\)` math spans, as the JSON of a `RichText` for any title, axis
 * title, legend, label or annotation text of `set_config` / `set_series`.
 * Errors name the TeX byte range.
 *
 * JS: `cfg.chart_title.text = JSON.parse(rich_text_from_tex("$E = mc^2$", 16, "", 0, 0, 0, 1));`
 *
 * Returns JSON text (`FiggyJson`), not an object: parse it with `JSON.parse`.
 */
export function rich_text_from_tex(tex: string, font_size: number, font: string, r: number, g: number, b: number, a: number): FiggyJson;

/**
 * Check a config JSON and, when given, a series list JSON against the
 * chart rules (`Config::validate_chart`, then `Config::validate_series`)
 * without a chart. Returns `{"valid": bool, "errors": [..]}`; it does not
 * throw for a refused document. An error is `{stage, path, field,
 * series_id, series_index, code, message}`: `stage` is `"parse"`,
 * `"chart"` or `"series"`; `path` names the field (`"bottom_x"`,
 * `"colorbar.axis"`, `"series[2]"`, or `"config"` / `"series"` for JSON
 * that does not parse, which adds `line` and `column`); `code` is the
 * rule's code, as on the `Error`s `set_config` throws (`"json"` for a
 * parse error). The rules stop at the first refusal, so `errors` holds at
 * most one. What needs the column pool (registered columns, lengths, GPU
 * limits) is checked by `set_config` / `set_series` only.
 *
 * JS: `const { valid, errors } = JSON.parse(validate_config(JSON.stringify(cfg), JSON.stringify(series)));`
 */
export function validate_config(config_json: string, series_json?: string | null): string;

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly __wbg_autostreamingrangerequestresult_free: (a: number, b: number) => void;
    readonly __wbg_autostreamingrequestresult_free: (a: number, b: number) => void;
    readonly __wbg_columntransaction_free: (a: number, b: number) => void;
    readonly __wbg_columnuploadhandle_free: (a: number, b: number) => void;
    readonly __wbg_figgyboundedchart_free: (a: number, b: number) => void;
    readonly __wbg_figgychart_free: (a: number, b: number) => void;
    readonly __wbg_figgyreadiness_free: (a: number, b: number) => void;
    readonly __wbg_streamingoperationhandle_free: (a: number, b: number) => void;
    readonly __wbg_streamingstepresult_free: (a: number, b: number) => void;
    readonly __wbg_streamingusageresult_free: (a: number, b: number) => void;
    readonly autoLayout: (a: number, b: number) => [number, number, number, number];
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
    readonly columntransaction_cancel: (a: number) => void;
    readonly columntransaction_commit: (a: number, b: number) => [number, number];
    readonly columntransaction_has_state: (a: number) => number;
    readonly columntransaction_is_open: (a: number) => number;
    readonly columntransaction_length: (a: number, b: number, c: number) => [number, number];
    readonly columntransaction_push: (a: number, b: number, c: number, d: number, e: any) => [number, number];
    readonly columntransaction_set_state: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly columntransaction_stage: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number) => [number, number];
    readonly columntransaction_staged_count: (a: number) => number;
    readonly columntransaction_written: (a: number, b: number, c: number) => [number, number];
    readonly columnuploadhandle_cancel: (a: number) => void;
    readonly columnuploadhandle_commit: (a: number, b: number) => [number, number];
    readonly columnuploadhandle_is_open: (a: number) => number;
    readonly columnuploadhandle_length: (a: number) => number;
    readonly columnuploadhandle_push: (a: number, b: number, c: any) => [number, number];
    readonly columnuploadhandle_written: (a: number) => number;
    readonly convert_boxplot_document: (a: number, b: number, c: number, d: number) => [number, number, number, number];
    readonly convert_categorical_document: (a: number, b: number, c: number, d: number) => [number, number, number, number];
    readonly convert_radar_document: (a: number, b: number, c: number, d: number) => [number, number, number, number];
    readonly default_config: () => [number, number, number, number];
    readonly default_config_for_series: (a: number, b: number) => [number, number, number, number];
    readonly draw_style_modes: () => [number, number, number, number];
    readonly draw_style_param_specs: (a: number, b: number) => [number, number, number, number];
    readonly figgyboundedchart_active_layer: (a: number) => [number, number, number, number];
    readonly figgyboundedchart_add_annotation: (a: number, b: number, c: number) => [number, number, number];
    readonly figgyboundedchart_add_corner_note: (a: number, b: number, c: number, d: number, e: number) => [number, number, number];
    readonly figgyboundedchart_annotation_handle: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgyboundedchart_annotation_ids: (a: number) => any;
    readonly figgyboundedchart_annotation_index: (a: number, b: number, c: number) => [number, number, number];
    readonly figgyboundedchart_annotation_preview: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgyboundedchart_annotation_vertex: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgyboundedchart_annotation_warnings: (a: number) => [number, number, number, number];
    readonly figgyboundedchart_annotations: (a: number) => [number, number, number, number];
    readonly figgyboundedchart_apply_theme: (a: number, b: number, c: number) => [number, number];
    readonly figgyboundedchart_apply_theme_with_palette: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgyboundedchart_clear_selection: (a: number) => void;
    readonly figgyboundedchart_create: (a: any, b: number, c: number, d: number, e: number, f: number, g: number) => any;
    readonly figgyboundedchart_create_on: (a: number, b: any, c: number, d: number, e: number, f: number, g: number, h: number) => any;
    readonly figgyboundedchart_decorations: (a: number) => [number, number, number, number];
    readonly figgyboundedchart_drag: (a: number, b: number, c: number, d: number, e: number, f: number, g: number) => [number, number, number];
    readonly figgyboundedchart_drag_annotation: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number, number];
    readonly figgyboundedchart_export_pdf: (a: number, b: number) => any;
    readonly figgyboundedchart_export_png: (a: number, b: number) => any;
    readonly figgyboundedchart_export_png_with_background: (a: number, b: number, c: number, d: number) => any;
    readonly figgyboundedchart_export_svg: (a: number, b: number) => any;
    readonly figgyboundedchart_first_frame_ready: (a: number) => any;
    readonly figgyboundedchart_frame: (a: number) => [number, number];
    readonly figgyboundedchart_get_document: (a: number) => [number, number, number, number];
    readonly figgyboundedchart_gpu_ready: (a: number) => any;
    readonly figgyboundedchart_hit_annotation: (a: number, b: number, c: number) => number;
    readonly figgyboundedchart_hit_decoration: (a: number, b: number, c: number, d: number) => any;
    readonly figgyboundedchart_hover: (a: number, b: number, c: number, d: number) => any;
    readonly figgyboundedchart_pick: (a: number, b: number, c: number, d: number) => any;
    readonly figgyboundedchart_pointer_to_anchor: (a: number, b: number, c: number, d: number, e: number) => [number, number, number, number];
    readonly figgyboundedchart_regenerate_labels: (a: number, b: number) => [number, number];
    readonly figgyboundedchart_remove_annotation: (a: number, b: number) => [number, number];
    readonly figgyboundedchart_reset_decoration_position: (a: number, b: number, c: number) => [number, number, number];
    readonly figgyboundedchart_resize: (a: number, b: number, c: number) => void;
    readonly figgyboundedchart_resize_handle: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgyboundedchart_select_annotation: (a: number, b: number) => [number, number];
    readonly figgyboundedchart_select_annotation_by_id: (a: number, b: number, c: number) => [number, number];
    readonly figgyboundedchart_select_decoration: (a: number, b: number, c: number) => [number, number];
    readonly figgyboundedchart_selected_annotation: (a: number) => number;
    readonly figgyboundedchart_set_active_layer: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgyboundedchart_set_annotation: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgyboundedchart_set_annotations_visible: (a: number, b: number) => [number, number];
    readonly figgyboundedchart_set_document: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgyboundedchart_step_selection: (a: number, b: number) => void;
    readonly figgyboundedchart_supported_families: () => any;
    readonly figgyboundedchart_theme_names: (a: number) => any;
    readonly figgychart_active_layer: (a: number) => [number, number, number, number];
    readonly figgychart_add_annotation: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_add_corner_note: (a: number, b: number, c: number, d: number, e: number) => [number, number, number];
    readonly figgychart_add_line_series: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number, j: number) => [number, number];
    readonly figgychart_annotation_handle: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgychart_annotation_ids: (a: number) => [number, number, number];
    readonly figgychart_annotation_index: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_annotation_preview: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_annotation_vertex: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgychart_annotation_warnings: (a: number) => [number, number, number, number];
    readonly figgychart_annotations: (a: number) => [number, number, number, number];
    readonly figgychart_append_monotonic: (a: number, b: number, c: number, d: any, e: number, f: number, g: number, h: number) => [number, number, number, number];
    readonly figgychart_apply_axis_preset: (a: number, b: number) => [number, number];
    readonly figgychart_apply_color_cycle: (a: number, b: number) => [number, number];
    readonly figgychart_apply_custom_theme: (a: number, b: any) => [number, number];
    readonly figgychart_apply_custom_theme_to: (a: number, b: any, c: number, d: number) => [number, number];
    readonly figgychart_apply_theme: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_apply_theme_to: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_auto_fit_all: (a: number, b: number) => any;
    readonly figgychart_auto_fit_colorbar: (a: number, b: number) => [number, number];
    readonly figgychart_auto_fit_overlay_x: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_auto_fit_overlay_y: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_auto_fit_subplot: (a: number, b: number, c: number, d: number, e: number, f: number, g: number) => [number, number];
    readonly figgychart_auto_fit_x: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgychart_auto_fit_y: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgychart_auto_stream_chart_request_ranges: (a: number) => [number, number, number];
    readonly figgychart_auto_stream_chart_step: (a: number, b: number, c: number, d: number, e: number, f: any) => [number, number, number];
    readonly figgychart_auto_stream_chart_submit_ranges: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number, j: any) => [number, number, number];
    readonly figgychart_begin_column_upload: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number) => [number, number, number];
    readonly figgychart_begin_columns_transaction: (a: number, b: number) => [number, number, number];
    readonly figgychart_begin_stream_export: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_begin_streaming: (a: number, b: number) => [number, number];
    readonly figgychart_cancel_stream_operation_and_wait: (a: number, b: number) => any;
    readonly figgychart_cancel_streaming: (a: number) => [number, number];
    readonly figgychart_cancel_streaming_and_wait: (a: number) => any;
    readonly figgychart_clear_monotonic_document: (a: number) => [number, number];
    readonly figgychart_clear_selection: (a: number) => [number, number];
    readonly figgychart_column_revision: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_configure_auto_residency: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_configure_streaming: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number];
    readonly figgychart_convert_annotation_anchor: (a: number, b: number, c: number, d: number, e: number) => [number, number, number, number];
    readonly figgychart_create: (a: any) => any;
    readonly figgychart_create_with_options: (a: any, b: any) => any;
    readonly figgychart_create_with_progress: (a: any, b: any) => any;
    readonly figgychart_data_area_rect: (a: number) => [number, number, number, number];
    readonly figgychart_decoration_bounds: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_demote_auto_resident_columns: (a: number, b: number, c: number, d: number, e: number, f: any) => [number, number];
    readonly figgychart_discard_stream_selection_request: (a: number, b: number) => [number, number];
    readonly figgychart_drag_annotation: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number, number];
    readonly figgychart_ensure_extent_engine: (a: number) => any;
    readonly figgychart_export_pdf: (a: number, b: number) => any;
    readonly figgychart_export_pdf_monotonic: (a: number, b: number, c: any) => any;
    readonly figgychart_export_png: (a: number, b: number) => any;
    readonly figgychart_export_png_monotonic: (a: number, b: number, c: any) => any;
    readonly figgychart_export_svg: (a: number, b: number) => any;
    readonly figgychart_export_svg_monotonic: (a: number, b: number, c: any) => any;
    readonly figgychart_finish_stream_export: (a: number, b: number) => any;
    readonly figgychart_first_frame_ready: (a: number) => any;
    readonly figgychart_fit_config: (a: number, b: number, c: number, d: number) => [number, number, number, number];
    readonly figgychart_fit_config_scoped: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number, number, number];
    readonly figgychart_fit_host_radial_labels: (a: number, b: number, c: number) => any;
    readonly figgychart_fit_layout: (a: number, b: number) => [number, number];
    readonly figgychart_fit_point_size_domain: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_fit_ranges: (a: number) => [number, number];
    readonly figgychart_fit_vector_scale: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgychart_fit_y_axes_config: (a: number, b: number, c: number, d: number) => [number, number, number, number];
    readonly figgychart_format_value_labels: (a: number) => any;
    readonly figgychart_frame: (a: number) => [number, number];
    readonly figgychart_frame_complete: (a: number) => number;
    readonly figgychart_get_config: (a: number) => [number, number, number, number];
    readonly figgychart_get_series: (a: number) => [number, number, number, number];
    readonly figgychart_gpu_memory_status: (a: number) => [number, number];
    readonly figgychart_gpu_ready: (a: number) => any;
    readonly figgychart_has_selection: (a: number) => [number, number, number];
    readonly figgychart_hit_annotation: (a: number, b: number, c: number) => number;
    readonly figgychart_hit_test: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_insets: (a: number) => [number, number, number, number];
    readonly figgychart_inspect_column_admission: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_inspect_document_layout: (a: number, b: number, c: number, d: number, e: number, f: number, g: number) => [number, number, number, number];
    readonly figgychart_inspect_streaming_capabilities: (a: number, b: number, c: number, d: number, e: number) => [number, number, number, number];
    readonly figgychart_interrupt_render: (a: number) => [number, number, number, number];
    readonly figgychart_legend_entry: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_load_demo: (a: number) => [number, number];
    readonly figgychart_monotonic_groups: (a: number) => [number, number, number, number];
    readonly figgychart_needs_source: (a: number) => [number, number, number, number];
    readonly figgychart_next_view_point_index: (a: number, b: number, c: number, d: number, e: number, f: number, g: number) => [number, number, number];
    readonly figgychart_on_move: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_on_press: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_on_release: (a: number) => [number, number];
    readonly figgychart_panel_at: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_pick_data: (a: number, b: number, c: number, d: number) => any;
    readonly figgychart_pick_point: (a: number, b: number, c: number, d: number) => any;
    readonly figgychart_pipeline_failures: (a: number) => [number, number, number];
    readonly figgychart_pipeline_status: (a: number) => [number, number, number];
    readonly figgychart_pipelines_ready: (a: number) => any;
    readonly figgychart_place_feynman_vertices: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_pointer_to_anchor: (a: number, b: number, c: number, d: number, e: number) => [number, number, number, number];
    readonly figgychart_prepare_data_pick: (a: number) => any;
    readonly figgychart_prepare_interaction: (a: number) => [number, number];
    readonly figgychart_press_energy_label: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number, number];
    readonly figgychart_press_feynman: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number) => [number, number, number];
    readonly figgychart_press_range_link: (a: number, b: number, c: number, d: number, e: number) => [number, number, number];
    readonly figgychart_press_value_label: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_prewarm_all: (a: number) => any;
    readonly figgychart_prewarm_all_with_progress: (a: number, b: any) => any;
    readonly figgychart_prewarm_gpu_picking: (a: number) => any;
    readonly figgychart_readiness: (a: number) => number;
    readonly figgychart_register_column_f32: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_register_column_f64: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_register_columns_f32: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number];
    readonly figgychart_register_columns_f64: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number];
    readonly figgychart_register_font: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_register_ragged: (a: number, b: number, c: number, d: number, e: number, f: number, g: number) => [number, number];
    readonly figgychart_register_record: (a: number, b: number, c: number, d: any) => [number, number];
    readonly figgychart_register_streaming_column_sources: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number) => [number, number];
    readonly figgychart_register_streaming_columns: (a: number, b: number, c: number, d: number, e: number, f: any) => [number, number];
    readonly figgychart_register_triangles: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_release_unused_gpu_memory: (a: number) => any;
    readonly figgychart_remove_annotation: (a: number, b: number) => [number, number];
    readonly figgychart_remove_column: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_remove_series: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_remove_triangles: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_render_warnings: (a: number) => [number, number, number, number];
    readonly figgychart_replace_streaming_column_sources: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number) => [number, number];
    readonly figgychart_replace_streaming_columns: (a: number, b: number, c: number, d: number, e: number, f: any) => [number, number];
    readonly figgychart_request_auto_streaming_chart: (a: number, b: number) => [number, number, number];
    readonly figgychart_request_resident_stream_handoff: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number, j: number) => [number, number, number];
    readonly figgychart_request_stream_auto_fit: (a: number, b: number) => [number, number, number];
    readonly figgychart_require_shader_set: (a: number, b: any) => [number, number];
    readonly figgychart_reset_legend_from_series_labels: (a: number) => [number, number];
    readonly figgychart_resize: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_resize_monotonic: (a: number, b: number, c: number, d: any, e: any) => [number, number];
    readonly figgychart_select_annotation: (a: number, b: number) => [number, number];
    readonly figgychart_select_annotation_by_id: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_selected_annotation: (a: number) => number;
    readonly figgychart_selection_details: (a: number) => any;
    readonly figgychart_series_draw_info: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_series_ready: (a: number) => any;
    readonly figgychart_set_active_layer: (a: number, b: number, c: number) => [number, number, number, number];
    readonly figgychart_set_annotation: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgychart_set_annotations_visible: (a: number, b: number) => [number, number];
    readonly figgychart_set_background: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_boxplot_document: (a: number, b: number, c: number, d: number, e: number) => [number, number, number, number];
    readonly figgychart_set_categorical_document: (a: number, b: number, c: number, d: number, e: number) => [number, number, number, number];
    readonly figgychart_set_clear_color: (a: number, b: number, c: number, d: number, e: number) => void;
    readonly figgychart_set_colorbar_axis: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_colorbar_title: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_config: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_contour_nice_levels: (a: number, b: number, c: number, d: number, e: number) => [number, number, number];
    readonly figgychart_set_host_state: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_set_link_exit_offset: (a: number, b: number, c: number, d: number, e: number) => [number, number, number];
    readonly figgychart_set_monotonic: (a: number, b: number, c: number, d: number, e: number, f: any, g: any, h: number, i: number, j: number) => [number, number, number, number];
    readonly figgychart_set_monotonic_document: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_set_picked_data: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_pool_auto_growth: (a: number, b: number) => void;
    readonly figgychart_set_radar_document: (a: number, b: number, c: number, d: number, e: number) => [number, number, number, number];
    readonly figgychart_set_series: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_series_label: (a: number, b: number, c: number, d: number, e: number) => [number, number, number];
    readonly figgychart_set_snap_modifier: (a: number, b: number) => [number, number];
    readonly figgychart_set_stream_chunk_budget: (a: number, b: number) => [number, number];
    readonly figgychart_set_stream_operation_chunk_budget: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_subplot_area: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number];
    readonly figgychart_set_subplot_background: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgychart_set_subplot_text_scale: (a: number, b: number, c: number, d: number) => [number, number];
    readonly figgychart_set_title: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_x_title: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_set_y_title: (a: number, b: number, c: number) => [number, number];
    readonly figgychart_shader_set: (a: number) => [number, number];
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
    readonly figgychart_subplot_area: (a: number, b: number) => [number, number, number, number];
    readonly figgychart_subplot_text_factor: (a: number, b: number) => [number, number, number];
    readonly figgychart_subplot_text_scale: (a: number, b: number) => [number, number, number, number];
    readonly figgychart_subplot_theme: (a: number, b: number, c: number, d: number) => [number, number, number];
    readonly figgychart_suspend_stream_selection: (a: number) => [number, number];
    readonly figgychart_take_plot_resize_request: (a: number) => [number, number, number, number];
    readonly figgychart_theme: (a: number, b: number, c: number) => [number, number, number];
    readonly figgychart_theme_names: (a: number) => any;
    readonly figgychart_theme_with_palette: (a: number, b: number, c: number, d: number) => [number, number, number];
    readonly figgychart_update_register_column_f32: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_update_register_column_f64: (a: number, b: number, c: number, d: number, e: number) => [number, number];
    readonly figgychart_wait_submitted_work: (a: number) => any;
    readonly figgychart_zoom_view: (a: number, b: number) => [number, number, number];
    readonly figgyreadiness_pipelines_ready: (a: number) => any;
    readonly figgyreadiness_series_ready: (a: number) => any;
    readonly figgyreadiness_status: (a: number) => [number, number, number];
    readonly inspect_config_layout: (a: number, b: number, c: number, d: number) => [number, number, number, number];
    readonly normalize_config: (a: number, b: number) => [number, number, number, number];
    readonly rich_text_from_tex: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number) => [number, number, number, number];
    readonly streamingstepresult_pending_latest: (a: number) => number;
    readonly streamingstepresult_revision: (a: number) => [number, number];
    readonly streamingstepresult_status: (a: number) => [number, number];
    readonly streamingstepresult_submitted_primitives: (a: number) => number;
    readonly streamingstepresult_total_primitives: (a: number) => number;
    readonly streamingusageresult_active_charts: (a: number) => number;
    readonly streamingusageresult_in_flight_chunks: (a: number) => number;
    readonly streamingusageresult_reserved_gpu_bytes: (a: number) => number;
    readonly validate_config: (a: number, b: number, c: number, d: number) => [number, number, number, number];
    readonly wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___js_sys_bd561c7fc2e002d3___Function_fn_wasm_bindgen_54fefb75fc756602___JsValue_____wasm_bindgen_54fefb75fc756602___sys__Undefined___js_sys_bd561c7fc2e002d3___Function_fn_wasm_bindgen_54fefb75fc756602___JsValue_____wasm_bindgen_54fefb75fc756602___sys__Undefined_______true_: (a: number, b: number, c: any, d: any) => void;
    readonly wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___JsValue__core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true_: (a: number, b: number, c: any) => [number, number];
    readonly wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___sys__JsNullable_wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true_: (a: number, b: number, c: any) => [number, number];
    readonly wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___sys__JsNullable_wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true__304: (a: number, b: number, c: any) => [number, number];
    readonly wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___sys__JsNullable_wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true__305: (a: number, b: number, c: any) => [number, number];
    readonly wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___JsValue______true_: (a: number, b: number, c: any) => void;
    readonly wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuDeviceLostInfo__GpuDeviceLostInfo______true_: (a: number, b: number, c: any) => void;
    readonly wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuDeviceLostInfo__GpuDeviceLostInfo______true__303: (a: number, b: number, c: any) => void;
    readonly __wbindgen_malloc: (a: number, b: number) => number;
    readonly __wbindgen_realloc: (a: number, b: number, c: number, d: number) => number;
    readonly __wbindgen_exn_store: (a: number) => void;
    readonly __externref_table_alloc: () => number;
    readonly __wbindgen_externrefs: WebAssembly.Table;
    readonly __wbindgen_free: (a: number, b: number, c: number) => void;
    readonly __wbindgen_destroy_closure: (a: number, b: number) => void;
    readonly __externref_table_dealloc: (a: number) => void;
    readonly __externref_drop_slice: (a: number, b: number) => void;
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
