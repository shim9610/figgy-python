/* @ts-self-types="./figgy.d.ts" */

/**
 * Exact range selected by the renderer-owned automatic cursor.
 */
export class AutoStreamingRangeRequestResult {
    static __wrap(ptr) {
        const obj = Object.create(AutoStreamingRangeRequestResult.prototype);
        obj.__wbg_ptr = ptr;
        AutoStreamingRangeRequestResultFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
    }
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        AutoStreamingRangeRequestResultFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_autostreamingrangerequestresult_free(ptr, 0);
    }
    /**
     * @returns {string[]}
     */
    get encodings() {
        const ret = wasm.autostreamingrangerequestresult_encodings(this.__wbg_ptr);
        var v1 = getArrayJsValueFromWasm0(ret[0], ret[1]);
        wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
        return v1;
    }
    /**
     * @returns {Float64Array}
     */
    get lengths() {
        const ret = wasm.autostreamingrangerequestresult_lengths(this.__wbg_ptr);
        var v1 = getArrayF64FromWasm0(ret[0], ret[1]).slice();
        wasm.__wbindgen_free(ret[0], ret[1] * 8, 8);
        return v1;
    }
    /**
     * @returns {Float64Array}
     */
    get offsets() {
        const ret = wasm.autostreamingrangerequestresult_offsets(this.__wbg_ptr);
        var v1 = getArrayF64FromWasm0(ret[0], ret[1]).slice();
        wasm.__wbindgen_free(ret[0], ret[1] * 8, 8);
        return v1;
    }
    /**
     * @returns {boolean}
     */
    get pending_latest() {
        const ret = wasm.autostreamingrangerequestresult_pending_latest(this.__wbg_ptr);
        return ret !== 0;
    }
    /**
     * @returns {string}
     */
    get revision() {
        let deferred1_0;
        let deferred1_1;
        try {
            const ret = wasm.autostreamingrangerequestresult_revision(this.__wbg_ptr);
            deferred1_0 = ret[0];
            deferred1_1 = ret[1];
            return getStringFromWasm0(ret[0], ret[1]);
        } finally {
            wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
        }
    }
    /**
     * @param {AutoStreamingRangeRequestResult} other
     * @returns {boolean}
     */
    same_selection_request(other) {
        _assertClass(other, AutoStreamingRangeRequestResult);
        const ret = wasm.autostreamingrangerequestresult_same_selection_request(this.__wbg_ptr, other.__wbg_ptr);
        return ret !== 0;
    }
    /**
     * @returns {string[]}
     */
    get source_ids() {
        const ret = wasm.autostreamingrangerequestresult_source_ids(this.__wbg_ptr);
        var v1 = getArrayJsValueFromWasm0(ret[0], ret[1]);
        wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
        return v1;
    }
    /**
     * @returns {Float64Array}
     */
    get source_lengths() {
        const ret = wasm.autostreamingrangerequestresult_source_lengths(this.__wbg_ptr);
        var v1 = getArrayF64FromWasm0(ret[0], ret[1]).slice();
        wasm.__wbindgen_free(ret[0], ret[1] * 8, 8);
        return v1;
    }
    /**
     * @returns {Float64Array}
     */
    get source_revisions() {
        const ret = wasm.autostreamingrangerequestresult_source_revisions(this.__wbg_ptr);
        var v1 = getArrayF64FromWasm0(ret[0], ret[1]).slice();
        wasm.__wbindgen_free(ret[0], ret[1] * 8, 8);
        return v1;
    }
    /**
     * @returns {string}
     */
    get status() {
        let deferred1_0;
        let deferred1_1;
        try {
            const ret = wasm.autostreamingrangerequestresult_status(this.__wbg_ptr);
            deferred1_0 = ret[0];
            deferred1_1 = ret[1];
            return getStringFromWasm0(ret[0], ret[1]);
        } finally {
            wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
        }
    }
    /**
     * @returns {number}
     */
    get submitted_primitives() {
        const ret = wasm.autostreamingrangerequestresult_submitted_primitives(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get total_primitives() {
        const ret = wasm.autostreamingrangerequestresult_total_primitives(this.__wbg_ptr);
        return ret;
    }
}
if (Symbol.dispose) AutoStreamingRangeRequestResult.prototype[Symbol.dispose] = AutoStreamingRangeRequestResult.prototype.free;

/**
 * Result of asking the renderer to start or coalesce one automatic draw.
 */
export class AutoStreamingRequestResult {
    static __wrap(ptr) {
        const obj = Object.create(AutoStreamingRequestResult.prototype);
        obj.__wbg_ptr = ptr;
        AutoStreamingRequestResultFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
    }
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        AutoStreamingRequestResultFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_autostreamingrequestresult_free(ptr, 0);
    }
    /**
     * @returns {string | undefined}
     */
    get job_id() {
        const ret = wasm.autostreamingrequestresult_job_id(this.__wbg_ptr);
        let v1;
        if (ret[0] !== 0) {
            v1 = getStringFromWasm0(ret[0], ret[1]);
            wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
        }
        return v1;
    }
    /**
     * @returns {boolean}
     */
    get pending_latest() {
        const ret = wasm.autostreamingrequestresult_pending_latest(this.__wbg_ptr);
        return ret !== 0;
    }
    /**
     * @returns {string}
     */
    get revision() {
        let deferred1_0;
        let deferred1_1;
        try {
            const ret = wasm.autostreamingrequestresult_revision(this.__wbg_ptr);
            deferred1_0 = ret[0];
            deferred1_1 = ret[1];
            return getStringFromWasm0(ret[0], ret[1]);
        } finally {
            wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
        }
    }
    /**
     * @returns {string[]}
     */
    get source_ids() {
        const ret = wasm.autostreamingrequestresult_source_ids(this.__wbg_ptr);
        var v1 = getArrayJsValueFromWasm0(ret[0], ret[1]);
        wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
        return v1;
    }
    /**
     * @returns {Float64Array}
     */
    get source_revisions() {
        const ret = wasm.autostreamingrequestresult_source_revisions(this.__wbg_ptr);
        var v1 = getArrayF64FromWasm0(ret[0], ret[1]).slice();
        wasm.__wbindgen_free(ret[0], ret[1] * 8, 8);
        return v1;
    }
    /**
     * @returns {string}
     */
    get status() {
        let deferred1_0;
        let deferred1_1;
        try {
            const ret = wasm.autostreamingrequestresult_status(this.__wbg_ptr);
            deferred1_0 = ret[0];
            deferred1_1 = ret[1];
            return getStringFromWasm0(ret[0], ret[1]);
        } finally {
            wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
        }
    }
    /**
     * @returns {number}
     */
    get submitted_primitives() {
        const ret = wasm.autostreamingrequestresult_submitted_primitives(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get total_primitives() {
        const ret = wasm.autostreamingrequestresult_total_primitives(this.__wbg_ptr);
        return ret;
    }
}
if (Symbol.dispose) AutoStreamingRequestResult.prototype[Symbol.dispose] = AutoStreamingRequestResult.prototype.free;

/**
 * Axis frame presets (mirror of `model::AxisPreset`).
 * @enum {0 | 1 | 2 | 3 | 4 | 5 | 6}
 */
export const AxisPreset = Object.freeze({
    BoxedInward: 0, "0": "BoxedInward",
    BoxedOutward: 1, "1": "BoxedOutward",
    OpenOutward: 2, "2": "OpenOutward",
    OpenInward: 3, "3": "OpenInward",
    Minimal: 4, "4": "Minimal",
    Hidden: 5, "5": "Hidden",
    Grotrian: 6, "6": "Grotrian",
});

/**
 * Series color rotations (mirror of `model::ColorCycle`).
 * @enum {0 | 1 | 2 | 3 | 4}
 */
export const ColorCycle = Object.freeze({
    Classic: 0, "0": "Classic",
    Vivid: 1, "1": "Vivid",
    Balanced: 2, "2": "Balanced",
    ColorblindSafe: 3, "3": "ColorblindSafe",
    Monochrome: 4, "4": "Monochrome",
});

/**
 * The browser host of one radial document, exported to JavaScript as
 * `FiggyBoundedChart`.
 */
export class FiggyBoundedChart {
    static __wrap(ptr) {
        const obj = Object.create(FiggyBoundedChart.prototype);
        obj.__wbg_ptr = ptr;
        FiggyBoundedChartFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
    }
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        FiggyBoundedChartFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_figgyboundedchart_free(ptr, 0);
    }
    /**
     * The layer that receives pointer interaction, as JSON.
     * @returns {string}
     */
    active_layer() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgyboundedchart_active_layer(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * Append an `Annotation` JSON value and return its index.
     * @param {string} json
     * @returns {number}
     */
    add_annotation(json) {
        const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgyboundedchart_add_annotation(this.__wbg_ptr, ptr0, len0);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] >>> 0;
    }
    /**
     * Append a text note at the plot's `corner` (a `NoteAlign` name:
     * `"TopLeft"`, `"Top"`, ..., `"BottomRight"`), its block inside the
     * plot, and return its index (#258). `text` is a `RichText` JSON value;
     * the note owns it. It is an ordinary text annotation.
     * @param {string} text
     * @param {string} corner
     * @returns {number}
     */
    add_corner_note(text, corner) {
        const ptr0 = passStringToWasm0(text, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passStringToWasm0(corner, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgyboundedchart_add_corner_note(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] >>> 0;
    }
    /**
     * The compass name of the annotation's live handle under a point.
     * @param {number} index
     * @param {number} x
     * @param {number} y
     * @returns {string | undefined}
     */
    annotation_handle(index, x, y) {
        const ret = wasm.figgyboundedchart_annotation_handle(this.__wbg_ptr, index, x, y);
        let v1;
        if (ret[0] !== 0) {
            v1 = getStringFromWasm0(ret[0], ret[1]);
            wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
        }
        return v1;
    }
    /**
     * The vertex handle (`"v<i>"`) of a polygon annotation under a point.
     * @param {number} index
     * @param {number} x
     * @param {number} y
     * @returns {string | undefined}
     */
    annotation_vertex(index, x, y) {
        const ret = wasm.figgyboundedchart_annotation_vertex(this.__wbg_ptr, index, x, y);
        let v1;
        if (ret[0] !== 0) {
            v1 = getStringFromWasm0(ret[0], ret[1]);
            wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
        }
        return v1;
    }
    /**
     * Annotations the current frame skipped, as `[{index, reason}]`.
     * @returns {string}
     */
    annotation_warnings() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgyboundedchart_annotation_warnings(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * The drawn annotations as JSON: `index`, `id`, `kind`, the selection
     * box `rect` and `handles`, and `selected`. Skipped items are listed by
     * `annotation_warnings` instead.
     * @returns {string}
     */
    annotations() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgyboundedchart_annotations(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * Apply the radial member of the theme family `name` (#291, #295:
     * `gallery`, `cool-slate`, `midnight` or `warm-paper`, as
     * [`Self::theme_names`] lists them): the background, label look, material, view,
     * slice shape and outline, the palette on the top-level slices and the
     * theme's tint on the slices below them. Values, labels, the slice
     * structure and the kind stay. A name that is not a family changes
     * nothing and throws `code` `"theme_unknown_name"` with the family
     * `names`.
     * @param {string} name
     */
    apply_theme(name) {
        const ptr0 = passStringToWasm0(name, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgyboundedchart_apply_theme(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    clear_selection() {
        wasm.figgyboundedchart_clear_selection(this.__wbg_ptr);
    }
    /**
     * One GPU surface; no kernel PNG transport is used for interactive frames.
     * @param {HTMLCanvasElement} canvas
     * @param {string} family
     * @param {string} value
     * @param {number} width
     * @param {number} height
     * @returns {Promise<FiggyBoundedChart>}
     */
    static create(canvas, family, value, width, height) {
        const ptr0 = passStringToWasm0(family, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passStringToWasm0(value, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgyboundedchart_create(canvas, ptr0, len0, ptr1, len1, width, height);
        return ret;
    }
    /**
     * Renderer-measured logical pixel bounds and resize handles.
     * @returns {string}
     */
    decorations() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgyboundedchart_decorations(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * @param {string} target
     * @param {number} dx
     * @param {number} dy
     * @param {string | null} [handle]
     * @returns {boolean}
     */
    drag(target, dx, dy, handle) {
        const ptr0 = passStringToWasm0(target, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        var ptr1 = isLikeNone(handle) ? 0 : passStringToWasm0(handle, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        var len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgyboundedchart_drag(this.__wbg_ptr, ptr0, len0, dx, dy, ptr1, len1);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
    /**
     * Move an annotation, or one of its handles (a compass name or a
     * polygon vertex `"v<i>"`), by a pointer delta. Returns `false` for a
     * rejected move; the document is unchanged then.
     * @param {number} index
     * @param {number} dx
     * @param {number} dy
     * @param {string | null} [handle]
     * @returns {boolean}
     */
    drag_annotation(index, dx, dy, handle) {
        var ptr0 = isLikeNone(handle) ? 0 : passStringToWasm0(handle, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        var len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgyboundedchart_drag_annotation(this.__wbg_ptr, index, dx, dy, ptr0, len0);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
    /**
     * [`Self::export_svg`] as one-page PDF bytes.
     * @param {number} scale
     * @returns {Promise<Uint8Array>}
     */
    export_pdf(scale) {
        const ret = wasm.figgyboundedchart_export_pdf(this.__wbg_ptr, scale);
        return ret;
    }
    /**
     * @param {number} scale
     * @returns {Promise<Uint8Array>}
     */
    export_png(scale) {
        const ret = wasm.figgyboundedchart_export_png(this.__wbg_ptr, scale);
        return ret;
    }
    /**
     * The chart as an SVG document at `scale ×` resolution: the slices and
     * background as one image, the title, labels, leader lines and
     * annotations as vector content.
     * @param {number} scale
     * @returns {Promise<string>}
     */
    export_svg(scale) {
        const ret = wasm.figgyboundedchart_export_svg(this.__wbg_ptr, scale);
        return ret;
    }
    /**
     * Submit one frame and wait for actual GPU completion. Hosts must await
     * this before publishing Ready; rejected completion (including device
     * loss) is returned to the caller instead of reporting an unusable chart.
     * @returns {Promise<void>}
     */
    first_frame_ready() {
        const ret = wasm.figgyboundedchart_first_frame_ready(this.__wbg_ptr);
        return ret;
    }
    frame() {
        const ret = wasm.figgyboundedchart_frame(this.__wbg_ptr);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * @returns {string}
     */
    get_document() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgyboundedchart_get_document(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * Host fence: keep edits serialized independently of GPU completion.
     * @returns {Promise<any>}
     */
    gpu_ready() {
        const ret = wasm.figgyboundedchart_gpu_ready(this.__wbg_ptr);
        return ret;
    }
    /**
     * The topmost drawn annotation under a point, as its index.
     * @param {number} x
     * @param {number} y
     * @returns {number | undefined}
     */
    hit_annotation(x, y) {
        const ret = wasm.figgyboundedchart_hit_annotation(this.__wbg_ptr, x, y);
        return ret === Number.MAX_SAFE_INTEGER ? undefined : ret;
    }
    /**
     * The topmost decoration under a point, as its stable id. While the
     * annotation layer is active (and shown) its drawn items sit on top of
     * every decoration and answer as `"annotation_<n>"`; on the base layer
     * they are not registered and clicks pass through them.
     *
     * Asynchronous: over the plot area it asks whether data is drawn
     * there, which the radial chart answers with its GPU pick.
     * @param {number} x
     * @param {number} y
     * @param {boolean} edit_area
     * @returns {Promise<string | undefined>}
     */
    hit_decoration(x, y, edit_area) {
        const ret = wasm.figgyboundedchart_hit_decoration(this.__wbg_ptr, x, y, edit_area);
        return ret;
    }
    /**
     * Hover the data under a point (`None` leaves the chart) and advance
     * the hover animation by `dt` seconds; resolves to whether the chart
     * changed. Asynchronous: the radial chart picks on the GPU.
     * @param {number | null | undefined} x
     * @param {number | null | undefined} y
     * @param {number} dt
     * @returns {Promise<boolean>}
     */
    hover(x, y, dt) {
        const ret = wasm.figgyboundedchart_hover(this.__wbg_ptr, isLikeNone(x) ? Number.MAX_SAFE_INTEGER : Math.fround(x), isLikeNone(y) ? Number.MAX_SAFE_INTEGER : Math.fround(y), dt);
        return ret;
    }
    /**
     * Select the data under a point (or toggle it off) and resolve to the
     * selection as JSON. Asynchronous: the radial chart picks on the GPU,
     * like `FiggyChart.pick_point`.
     * @param {number} x
     * @param {number} y
     * @param {boolean} toggle
     * @returns {Promise<string>}
     */
    pick(x, y, toggle) {
        const ret = wasm.figgyboundedchart_pick(this.__wbg_ptr, x, y, toggle);
        return ret;
    }
    /**
     * The `Anchor` JSON at a point for `"Data"` or `"Ratio"`; `null` when
     * the point has no such position (a radial chart has no data anchors).
     * @param {number} x
     * @param {number} y
     * @param {string} kind
     * @returns {string}
     */
    pointer_to_anchor(x, y, kind) {
        let deferred3_0;
        let deferred3_1;
        try {
            const ptr0 = passStringToWasm0(kind, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ret = wasm.figgyboundedchart_pointer_to_anchor(this.__wbg_ptr, x, y, ptr0, len0);
            var ptr2 = ret[0];
            var len2 = ret[1];
            if (ret[3]) {
                ptr2 = 0; len2 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred3_0 = ptr2;
            deferred3_1 = len2;
            return getStringFromWasm0(ptr2, len2);
        } finally {
            wasm.__wbindgen_free(deferred3_0, deferred3_1, 1);
        }
    }
    /**
     * Remove the annotation at `index`; later indices move down one and the
     * selection follows or clears.
     * @param {number} index
     */
    remove_annotation(index) {
        const ret = wasm.figgyboundedchart_remove_annotation(this.__wbg_ptr, index);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * @param {number} width
     * @param {number} height
     */
    resize(width, height) {
        wasm.figgyboundedchart_resize(this.__wbg_ptr, width, height);
    }
    /**
     * @param {string} target
     * @param {number} x
     * @param {number} y
     * @returns {string | undefined}
     */
    resize_handle(target, x, y) {
        const ptr0 = passStringToWasm0(target, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgyboundedchart_resize_handle(this.__wbg_ptr, ptr0, len0, x, y);
        let v2;
        if (ret[0] !== 0) {
            v2 = getStringFromWasm0(ret[0], ret[1]);
            wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
        }
        return v2;
    }
    /**
     * Select one annotation (`decorations.selected = Annotation(index)`) or
     * none. Clears the data and decoration selections like
     * `select_decoration`.
     * @param {number | null} [index]
     */
    select_annotation(index) {
        const ret = wasm.figgyboundedchart_select_annotation(this.__wbg_ptr, isLikeNone(index) ? Number.MAX_SAFE_INTEGER : (index) >>> 0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Select a decoration by the id `hit_decoration` reported, or none.
     * An `"annotation_<n>"` id selects that drawn annotation
     * (`decorations.selected = Annotation(n)`).
     * @param {string | null} [target]
     */
    select_decoration(target) {
        var ptr0 = isLikeNone(target) ? 0 : passStringToWasm0(target, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        var len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgyboundedchart_select_decoration(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * @returns {number | undefined}
     */
    selected_annotation() {
        const ret = wasm.figgyboundedchart_selected_annotation(this.__wbg_ptr);
        return ret === Number.MAX_SAFE_INTEGER ? undefined : ret;
    }
    /**
     * Set the layer that receives pointer interaction: `"Base"` or
     * `"Annotations"` as JSON (the radial chart has no overlays, so an
     * `{ "Overlay": n }` is stored as `"Base"`). A change clears the
     * decoration selection (`decorations.selected`, an annotation
     * included); the data selection is kept. Returns the stored layer as
     * JSON. Drawn pixels never depend on it.
     * @param {string} json
     * @returns {string}
     */
    set_active_layer(json) {
        let deferred3_0;
        let deferred3_1;
        try {
            const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ret = wasm.figgyboundedchart_set_active_layer(this.__wbg_ptr, ptr0, len0);
            var ptr2 = ret[0];
            var len2 = ret[1];
            if (ret[3]) {
                ptr2 = 0; len2 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred3_0 = ptr2;
            deferred3_1 = len2;
            return getStringFromWasm0(ptr2, len2);
        } finally {
            wasm.__wbindgen_free(deferred3_0, deferred3_1, 1);
        }
    }
    /**
     * Replace the annotation at `index`.
     * @param {number} index
     * @param {string} json
     */
    set_annotation(index, json) {
        const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgyboundedchart_set_annotation(this.__wbg_ptr, index, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Show or hide the whole annotation layer without re-rasterizing it.
     * @param {boolean} visible
     */
    set_annotations_visible(visible) {
        const ret = wasm.figgyboundedchart_set_annotations_visible(this.__wbg_ptr, visible);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Validate and prepare before replacing the SSOT, retaining the old chart on failure.
     * @param {string} value
     * @param {number} width
     * @param {number} height
     */
    set_document(value, width, height) {
        const ptr0 = passStringToWasm0(value, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgyboundedchart_set_document(this.__wbg_ptr, ptr0, len0, width, height);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * @param {boolean} backwards
     */
    step_selection(backwards) {
        wasm.figgyboundedchart_step_selection(this.__wbg_ptr, backwards);
    }
    /**
     * The theme names (#291, #295), as an array of strings: the four
     * families.
     * @returns {Array<any>}
     */
    theme_names() {
        const ret = wasm.figgyboundedchart_theme_names(this.__wbg_ptr);
        return ret;
    }
}
if (Symbol.dispose) FiggyBoundedChart.prototype[Symbol.dispose] = FiggyBoundedChart.prototype.free;

export class FiggyChart {
    static __wrap(ptr) {
        const obj = Object.create(FiggyChart.prototype);
        obj.__wbg_ptr = ptr;
        FiggyChartFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
    }
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        FiggyChartFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_figgychart_free(ptr, 0);
    }
    /**
     * The layer that receives pointer interaction, as JSON, with the
     * out-of-range fallback applied.
     * JS: `JSON.parse(chart.active_layer())`
     * @returns {string}
     */
    active_layer() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgychart_active_layer(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * Append an `Annotation` (JSON, the same shape as in `get_config`)
     * and return its index.
     * @param {string} json
     * @returns {number}
     */
    add_annotation(json) {
        const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_add_annotation(this.__wbg_ptr, ptr0, len0);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] >>> 0;
    }
    /**
     * Append a text note at the plot's `corner` (a `NoteAlign` name:
     * `"TopLeft"`, `"Top"`, ..., `"BottomRight"`), its block inside the
     * plot, and return its index (#258). `text` is a `RichText` JSON value,
     * the same shape as in `get_config`; the note owns it, such as the
     * unit of the chart's values. It is an ordinary text annotation: move,
     * hide or edit it as one.
     * JS: `const i = chart.add_corner_note(textJson, "BottomRight");`
     * @param {string} text
     * @param {string} corner
     * @returns {number}
     */
    add_corner_note(text, corner) {
        const ptr0 = passStringToWasm0(text, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passStringToWasm0(corner, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_add_corner_note(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] >>> 0;
    }
    /**
     * Register or update a line series over two registered columns.
     *
     * Upsert by `series_id`: a new id takes the next color of the active
     * cycle; an existing id is replaced in place and keeps its color.
     * Non-empty `label` adds/updates the legend row; its `$…$` spans are
     * TeX and `\$` is a dollar sign.
     * @param {string} series_id
     * @param {string} x_column
     * @param {string} y_column
     * @param {number} line_width
     * @param {string} label
     */
    add_line_series(series_id, x_column, y_column, line_width, label) {
        const ptr0 = passStringToWasm0(series_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passStringToWasm0(x_column, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        const ptr2 = passStringToWasm0(y_column, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len2 = WASM_VECTOR_LEN;
        const ptr3 = passStringToWasm0(label, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len3 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_add_line_series(this.__wbg_ptr, ptr0, len0, ptr1, len1, ptr2, len2, line_width, ptr3, len3);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * The compass name (`"W"`, `"E"`, ...) of the annotation's handle
     * under a point, or none. Only the handles `annotations` lists are
     * live: a span's two edges, a line's two value handles, an arrow's
     * two endpoints.
     * @param {number} index
     * @param {number} x
     * @param {number} y
     * @returns {string | undefined}
     */
    annotation_handle(index, x, y) {
        const ret = wasm.figgychart_annotation_handle(this.__wbg_ptr, index, x, y);
        let v1;
        if (ret[0] !== 0) {
            v1 = getStringFromWasm0(ret[0], ret[1]);
            wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
        }
        return v1;
    }
    /**
     * The vertex handle (`"v<i>"`) of a polygon annotation under a
     * point, or none: a polygon's handles are its vertices.
     * @param {number} index
     * @param {number} x
     * @param {number} y
     * @returns {string | undefined}
     */
    annotation_vertex(index, x, y) {
        const ret = wasm.figgychart_annotation_vertex(this.__wbg_ptr, index, x, y);
        let v1;
        if (ret[0] !== 0) {
            v1 = getStringFromWasm0(ret[0], ret[1]);
            wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
        }
        return v1;
    }
    /**
     * Annotations the current raster skipped, as `[{index, reason}]`
     * with `reason` one of `NonFinite`, `NoValueAxis`, `OutOfRange`,
     * `EmptyText`.
     * @returns {string}
     */
    annotation_warnings() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgychart_annotation_warnings(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * The drawn annotations of the current frame as JSON: `index`, `id`,
     * `kind`, the selection box `rect` and its `handles` in physical
     * canvas pixels, and `selected`. Items the raster skipped are
     * absent here and listed by `annotation_warnings`.
     * @returns {string}
     */
    annotations() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgychart_annotations(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * The append call of monotonic group `group` (#271): `data` holds only
     * the new samples of every channel, in either layout of
     * `set_monotonic`. With `sliding`, the window keeps its length and the
     * chart's x range moves by exactly the new samples' span; the host may
     * drop every sample before the window. Returns the update as JSON.
     * JS: `chart.append_monotonic("daq", [new0, new1], true)`
     * @param {string} group
     * @param {any} data
     * @param {boolean} sliding
     * @param {number | null} [stride]
     * @param {Uint32Array | null} [columns]
     * @returns {string}
     */
    append_monotonic(group, data, sliding, stride, columns) {
        let deferred4_0;
        let deferred4_1;
        try {
            const ptr0 = passStringToWasm0(group, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            var ptr1 = isLikeNone(columns) ? 0 : passArray32ToWasm0(columns, wasm.__wbindgen_malloc);
            var len1 = WASM_VECTOR_LEN;
            const ret = wasm.figgychart_append_monotonic(this.__wbg_ptr, ptr0, len0, data, sliding, isLikeNone(stride) ? Number.MAX_SAFE_INTEGER : (stride) >>> 0, ptr1, len1);
            var ptr3 = ret[0];
            var len3 = ret[1];
            if (ret[3]) {
                ptr3 = 0; len3 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred4_0 = ptr3;
            deferred4_1 = len3;
            return getStringFromWasm0(ptr3, len3);
        } finally {
            wasm.__wbindgen_free(deferred4_0, deferred4_1, 1);
        }
    }
    /**
     * Apply an axis frame preset to all four axes and every overlay's own
     * axes (decoration-only).
     * @param {AxisPreset} preset
     */
    apply_axis_preset(preset) {
        const ret = wasm.figgychart_apply_axis_preset(this.__wbg_ptr, preset);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Switch the series color rotation: recolors every series in order,
     * rebuilds their GPU styles, and keeps legend swatches in sync.
     * @param {ColorCycle} cycle
     */
    apply_color_cycle(cycle) {
        const ret = wasm.figgychart_apply_color_cycle(this.__wbg_ptr, cycle);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Apply `theme`, an object [`Self::theme`] handed out and the host
     * edited, to the charts of its kind (#295): the chart and every
     * subplot of the theme's kind, or that draws no series yet; charts of
     * another kind are left as they are. Then fit the layout as
     * [`Self::apply_theme`] does. An object that is not a theme throws
     * `code` `"theme_invalid"`; no chart of its kind `"theme_wrong_kind"`;
     * a draw style that cannot draw a series it themes
     * `"theme_draw_style"`. A refusal changes nothing.
     * @param {any} theme
     */
    apply_custom_theme(theme) {
        const ret = wasm.figgychart_apply_custom_theme(this.__wbg_ptr, theme);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * [`Self::apply_custom_theme`] to the charts `scope` names (the forms
     * [`Self::apply_theme_to`] takes): `"[0]"` themes subplot 0 alone,
     * whatever the base chart's kind. A chart in scope of another kind
     * than the theme throws `"theme_wrong_kind"`, an index past the
     * subplots `"subplot_index"`.
     * @param {any} theme
     * @param {string} scope
     */
    apply_custom_theme_to(theme, scope) {
        const ptr0 = passStringToWasm0(scope, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_apply_custom_theme_to(this.__wbg_ptr, theme, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
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
     * @param {string} name
     */
    apply_theme(name) {
        const ptr0 = passStringToWasm0(name, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_apply_theme(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * [`Self::apply_theme`] to the charts `scope` names, as Rust's
     * `Chart::apply_theme_to` takes a `ThemeScope`: `"all"` (the base chart
     * and every subplot), `"base"` (the base chart alone), a JSON array of
     * indices (those subplots alone, `"[0,2]"`) or a JSON array holding
     * `"base"` (the base chart and those subplots, `"[\"base\",0]"`). A
     * scope of another form (`code` `"subplot_scope"`, with the `accepted`
     * forms) or an index past the subplots (`code` `"subplot_index"`)
     * changes nothing and errors.
     * @param {string} name
     * @param {string} scope
     */
    apply_theme_to(name, scope) {
        const ptr0 = passStringToWasm0(name, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passStringToWasm0(scope, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_apply_theme_to(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
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
     * @param {number} padding
     * @returns {Promise<void>}
     */
    auto_fit_all(padding) {
        const ret = wasm.figgychart_auto_fit_all(this.__wbg_ptr, padding);
        return ret;
    }
    /**
     * Fit the shared z axis to every column the colourbar maps: matrix
     * value columns, scatter `point_color_map` columns, vector colour
     * maps and streamline colour columns. A chart without a colourbar is left unchanged.
     * @param {number} padding
     */
    auto_fit_colorbar(padding) {
        const ret = wasm.figgychart_auto_fit_colorbar(this.__wbg_ptr, padding);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Fit overlay layer `layer`'s own X axis (`OverlayLayer::x_axis`) to a
     * column's cached statistics with proportional padding, the X
     * counterpart of `auto_fit_overlay_y`. With the overlay's `link_x` on
     * it fits the chart's X axes it follows. A layer index past the
     * overlay list is an error.
     * JS: `chart.auto_fit_overlay_x(0, "time_b", 0.05)`
     * @param {number} layer
     * @param {string} column
     * @param {number} padding
     */
    auto_fit_overlay_x(layer, column, padding) {
        const ptr0 = passStringToWasm0(column, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_auto_fit_overlay_x(this.__wbg_ptr, layer, ptr0, len0, padding);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Fit overlay layer `layer`'s Y axis to a column's cached statistics
     * with proportional padding, the overlay counterpart of `auto_fit_y`.
     * With the overlay's `link_y` on it fits the chart's Y axes it
     * follows. A layer index past the overlay list is an error.
     * JS: `chart.auto_fit_overlay_y(0, "pressure", 0.05)`
     * @param {number} layer
     * @param {string} column
     * @param {number} padding
     */
    auto_fit_overlay_y(layer, column, padding) {
        const ptr0 = passStringToWasm0(column, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_auto_fit_overlay_y(this.__wbg_ptr, layer, ptr0, len0, padding);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Fit subplot `index`'s X (`axis = "x"`) or Y (`axis = "y"`) axis to
     * the union of the given columns' cached statistics with
     * proportional padding. A linked axis moves its whole link group.
     * An index past the subplot list or another axis name is an error.
     * JS: `chart.auto_fit_subplot(0, "y", ["flow"], 0.05)`
     * @param {number} index
     * @param {string} axis
     * @param {string[]} columns
     * @param {number} padding
     */
    auto_fit_subplot(index, axis, columns, padding) {
        const ptr0 = passStringToWasm0(axis, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayJsValueToWasm0(columns, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_auto_fit_subplot(this.__wbg_ptr, index, ptr0, len0, ptr1, len1, padding);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Fit the x axis to a column's range with proportional padding.
     * @param {string} column
     * @param {number} padding
     */
    auto_fit_x(column, padding) {
        const ptr0 = passStringToWasm0(column, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_auto_fit_x(this.__wbg_ptr, ptr0, len0, padding);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * @param {string} column
     * @param {number} padding
     */
    auto_fit_y(column, padding) {
        const ptr0 = passStringToWasm0(column, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_auto_fit_y(this.__wbg_ptr, ptr0, len0, padding);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Reserve or inspect the next exact range request. Repeated calls
     * return the same ranges until `auto_stream_chart_submit_ranges`.
     * @returns {AutoStreamingRangeRequestResult}
     */
    auto_stream_chart_request_ranges() {
        const ret = wasm.figgychart_auto_stream_chart_request_ranges(this.__wbg_ptr);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return AutoStreamingRangeRequestResult.__wrap(ret[0]);
    }
    /**
     * Advance at most one renderer-selected automatic chunk. The typed
     * arrays are borrowed only for this call.
     * @param {string[]} ids
     * @param {Float64Array} revisions
     * @param {Array<any>} sources
     * @returns {StreamingStepResult}
     */
    auto_stream_chart_step(ids, revisions, sources) {
        const ptr0 = passArrayJsValueToWasm0(ids, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(revisions, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_auto_stream_chart_step(this.__wbg_ptr, ptr0, len0, ptr1, len1, sources);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return StreamingStepResult.__wrap(ret[0]);
    }
    /**
     * Submit exactly the typed-array chunks named by the pending range
     * request. The arrays are borrowed for this call only.
     * @param {string[]} ids
     * @param {Float64Array} revisions
     * @param {Float64Array} source_lengths
     * @param {Float64Array} offsets
     * @param {Array<any>} sources
     * @returns {StreamingStepResult}
     */
    auto_stream_chart_submit_ranges(ids, revisions, source_lengths, offsets, sources) {
        const ptr0 = passArrayJsValueToWasm0(ids, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(revisions, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ptr2 = passArrayF64ToWasm0(source_lengths, wasm.__wbindgen_malloc);
        const len2 = WASM_VECTOR_LEN;
        const ptr3 = passArrayF64ToWasm0(offsets, wasm.__wbindgen_malloc);
        const len3 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_auto_stream_chart_submit_ranges(this.__wbg_ptr, ptr0, len0, ptr1, len1, ptr2, len2, ptr3, len3, sources);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return StreamingStepResult.__wrap(ret[0]);
    }
    /**
     * Begin an independent replay of the completed stream. The facade
     * supplies only renderer-requested ranges between these calls.
     * @param {number} scale
     * @param {number} max_primitives_per_chunk
     * @returns {StreamingOperationHandle}
     */
    begin_stream_export(scale, max_primitives_per_chunk) {
        const ret = wasm.figgychart_begin_stream_export(this.__wbg_ptr, scale, max_primitives_per_chunk);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return StreamingOperationHandle.__wrap(ret[0]);
    }
    /**
     * Compatibility entry point; always rejects without requesting ranges.
     * @param {number} _x
     * @param {number} _y
     * @param {number} _max_distance_px
     * @param {number} _max_primitives_per_chunk
     * @returns {Promise<StreamingOperationHandle>}
     */
    begin_stream_pick_data(_x, _y, _max_distance_px, _max_primitives_per_chunk) {
        const ret = wasm.figgychart_begin_stream_pick_data(this.__wbg_ptr, _x, _y, _max_distance_px, _max_primitives_per_chunk);
        return ret;
    }
    /**
     * Compatibility entry point. Nonresident picking is disabled because
     * exact source replay can take as long as the original render.
     * @param {number} _x
     * @param {number} _y
     * @param {number} _max_distance_px
     * @param {number} _max_primitives_per_chunk
     * @returns {Promise<StreamingOperationHandle>}
     */
    begin_stream_pick_point(_x, _y, _max_distance_px, _max_primitives_per_chunk) {
        const ret = wasm.figgychart_begin_stream_pick_point(this.__wbg_ptr, _x, _y, _max_distance_px, _max_primitives_per_chunk);
        return ret;
    }
    /**
     * Start or restart this chart's exact streaming surface and renderer-
     * owned CPU cursor. No LOD or downsampling is performed.
     * @param {number} max_primitives_per_chunk
     */
    begin_streaming(max_primitives_per_chunk) {
        const ret = wasm.figgychart_begin_streaming(this.__wbg_ptr, max_primitives_per_chunk);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * @param {StreamingOperationHandle} handle
     * @returns {Promise<void>}
     */
    cancel_stream_operation_and_wait(handle) {
        _assertClass(handle, StreamingOperationHandle);
        const ret = wasm.figgychart_cancel_stream_operation_and_wait(this.__wbg_ptr, handle.__wbg_ptr);
        return ret;
    }
    cancel_streaming() {
        const ret = wasm.figgychart_cancel_streaming(this.__wbg_ptr);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Cancel this chart and resolve only after its submitted work and
     * retired renderer-owned surfaces have crossed the completion fence.
     * @returns {Promise<void>}
     */
    cancel_streaming_and_wait() {
        const ret = wasm.figgychart_cancel_streaming_and_wait(this.__wbg_ptr);
        return ret;
    }
    /**
     * Removes the monotonic chart and shows the general one again (#271).
     */
    clear_monotonic_document() {
        const ret = wasm.figgychart_clear_monotonic_document(this.__wbg_ptr);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Configure the total GPU budget and chart-local packed-view limit.
     * Automatic streaming keeps original sources nonresident, then caches
     * only source rows whose geometry reaches the current view when the
     * completed packed view fits both limits.
     * @param {number} memory_budget_bytes
     * @param {number} working_set_limit_bytes
     */
    configure_auto_residency(memory_budget_bytes, working_set_limit_bytes) {
        const ret = wasm.figgychart_configure_auto_residency(this.__wbg_ptr, memory_budget_bytes, working_set_limit_bytes);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Install the renderer's bounded streaming resources once.
     * Byte limits are JavaScript safe integers; no source payload is retained.
     * @param {number} max_active_charts
     * @param {number} max_in_flight_chunks
     * @param {number} max_columns_per_chunk
     * @param {number} max_chunk_input_bytes
     * @param {number} max_in_flight_gpu_bytes
     */
    configure_streaming(max_active_charts, max_in_flight_chunks, max_columns_per_chunk, max_chunk_input_bytes, max_in_flight_gpu_bytes) {
        const ret = wasm.figgychart_configure_streaming(this.__wbg_ptr, max_active_charts, max_in_flight_chunks, max_columns_per_chunk, max_chunk_input_bytes, max_in_flight_gpu_bytes);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Bind the low-level chart kernel to `canvas` (uses the canvas's
     * current pixel size). Ordinary web hosts should prefer
     * `figgy-chart.js` and its `<figgy-chart>` Custom Element.
     * JS: `const chart = await FiggyChart.create(canvas);`
     * @param {HTMLCanvasElement} canvas
     * @returns {Promise<FiggyChart>}
     */
    static create(canvas) {
        const ret = wasm.figgychart_create(canvas);
        return ret;
    }
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
     * @param {HTMLCanvasElement} canvas
     * @param {any} options
     * @returns {Promise<FiggyChart>}
     */
    static create_with_options(canvas, options) {
        const ret = wasm.figgychart_create_with_options(canvas, options);
        return ret;
    }
    /**
     * Same as [`Self::create`], reporting each init stage to `on_event`
     * as `{ scope, stage, phase }`. Do not call other kernel methods
     * from the callback. An exception the callback throws rejects the
     * returned promise with it; later stages are not reported.
     * @param {HTMLCanvasElement} canvas
     * @param {Function} on_event
     * @returns {Promise<FiggyChart>}
     */
    static create_with_progress(canvas, on_event) {
        const ret = wasm.figgychart_create_with_progress(canvas, on_event);
        return ret;
    }
    /**
     * Renderer-measured decoration bounds in physical canvas pixels.
     * An `"annotation_<n>"` id that `hit_test` reports resolves to the
     * drawn item's selection box.
     * @param {string} target
     * @returns {string}
     */
    decoration_bounds(target) {
        let deferred3_0;
        let deferred3_1;
        try {
            const ptr0 = passStringToWasm0(target, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ret = wasm.figgychart_decoration_bounds(this.__wbg_ptr, ptr0, len0);
            var ptr2 = ret[0];
            var len2 = ret[1];
            if (ret[3]) {
                ptr2 = 0; len2 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred3_0 = ptr2;
            deferred3_1 = len2;
            return getStringFromWasm0(ptr2, len2);
        } finally {
            wasm.__wbindgen_free(deferred3_0, deferred3_1, 1);
        }
    }
    /**
     * Normalize a complete referenced-column closure from resident or
     * mixed authority to exact streamed metadata. The typed arrays are
     * borrowed only for the atomic transition and are not retained by
     * Rust; the high-level JS executor keeps the replayable references.
     * @param {string[]} ids
     * @param {Float64Array} revisions
     * @param {Array<any>} sources
     */
    demote_auto_resident_columns(ids, revisions, sources) {
        const ptr0 = passArrayJsValueToWasm0(ids, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(revisions, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_demote_auto_resident_columns(this.__wbg_ptr, ptr0, len0, ptr1, len1, sources);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * @param {AutoStreamingRangeRequestResult} request
     */
    discard_stream_selection_request(request) {
        _assertClass(request, AutoStreamingRangeRequestResult);
        const ret = wasm.figgychart_discard_stream_selection_request(this.__wbg_ptr, request.__wbg_ptr);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Move an annotation, or one of its handles, by a pointer delta in
     * physical canvas pixels. The delta is converted back into the
     * item's anchors through the frame's anchor space and written to
     * the config; a move that would leave the plot or panel is rejected
     * and returns `false`. A handle is a compass name (`"W"`, `"NE"`, ...)
     * or a polygon vertex (`"v3"`).
     * @param {number} index
     * @param {number} dx
     * @param {number} dy
     * @param {string | null} [handle]
     * @returns {boolean}
     */
    drag_annotation(index, dx, dy, handle) {
        var ptr0 = isLikeNone(handle) ? 0 : passStringToWasm0(handle, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        var len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_drag_annotation(this.__wbg_ptr, index, dx, dy, ptr0, len0);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
    /**
     * Compile the drawable-series fit-bound engine without drawing. On wasm
     * this uses `createComputePipelineAsync`. Series registration does
     * not do this; `auto_fit_all` does.
     * @returns {Promise<void>}
     */
    ensure_extent_engine() {
        const ret = wasm.figgychart_ensure_extent_engine(this.__wbg_ptr);
        return ret;
    }
    /**
     * [`Self::export_svg`] as one-page PDF bytes.
     * JS: `const pdf = await chart.export_pdf(2.0);`
     * @param {number} scale
     * @returns {Promise<Uint8Array>}
     */
    export_pdf(scale) {
        const ret = wasm.figgychart_export_pdf(this.__wbg_ptr, scale);
        return ret;
    }
    /**
     * [`Self::export_pdf`] with the sources of the chart's monotonic
     * groups, as [`Self::export_png_monotonic`] takes them.
     * @param {number} scale
     * @param {Array<any>} sources
     * @returns {Promise<Uint8Array>}
     */
    export_pdf_monotonic(scale, sources) {
        const ret = wasm.figgychart_export_pdf_monotonic(this.__wbg_ptr, scale, sources);
        return ret;
    }
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
     * @param {number} scale
     * @returns {Promise<Uint8Array>}
     */
    export_png(scale) {
        const ret = wasm.figgychart_export_png(this.__wbg_ptr, scale);
        return ret;
    }
    /**
     * [`Self::export_png`] with the sources of the chart's monotonic
     * groups (#271), for an export at another scale than the screen's
     * (which maps the plot to other device pixels): `sources` is an array
     * of `{ group, start, interval, data, stride?, columns? }`, `data` as
     * `set_monotonic` takes it. Each group is reduced for the export alone.
     * The same borrow and gate rules as `export_png`.
     * @param {number} scale
     * @param {Array<any>} sources
     * @returns {Promise<Uint8Array>}
     */
    export_png_monotonic(scale, sources) {
        const ret = wasm.figgychart_export_png_monotonic(this.__wbg_ptr, scale, sources);
        return ret;
    }
    /**
     * Export the document as an SVG document at `scale ×` resolution: the
     * decorations, annotations and text as vector content (glyphs as
     * outlines) over each panel group's data embedded as a PNG image, with
     * the clear colour as its background.
     * JS: `const svg = await chart.export_svg(2.0);`
     * The same borrow and gate rules as [`Self::export_png`]. A chart with a
     * streamed source is rejected; the `<figgy-chart>` facade rejects it
     * before calling.
     * @param {number} scale
     * @returns {Promise<string>}
     */
    export_svg(scale) {
        const ret = wasm.figgychart_export_svg(this.__wbg_ptr, scale);
        return ret;
    }
    /**
     * [`Self::export_svg`] with the sources of the chart's monotonic
     * groups, as [`Self::export_png_monotonic`] takes them.
     * @param {number} scale
     * @param {Array<any>} sources
     * @returns {Promise<string>}
     */
    export_svg_monotonic(scale, sources) {
        const ret = wasm.figgychart_export_svg_monotonic(this.__wbg_ptr, scale, sources);
        return ret;
    }
    /**
     * @param {StreamingOperationHandle} handle
     * @returns {Promise<Uint8Array>}
     */
    finish_stream_export(handle) {
        _assertClass(handle, StreamingOperationHandle);
        const ret = wasm.figgychart_finish_stream_export(this.__wbg_ptr, handle.__wbg_ptr);
        return ret;
    }
    /**
     * Compatibility entry point; no streamed pick operation can start.
     * @param {StreamingOperationHandle} _handle
     * @returns {Promise<any>}
     */
    finish_stream_pick_data(_handle) {
        _assertClass(_handle, StreamingOperationHandle);
        const ret = wasm.figgychart_finish_stream_pick_data(this.__wbg_ptr, _handle.__wbg_ptr);
        return ret;
    }
    /**
     * Compatibility entry point; no streamed pick operation can start.
     * @param {StreamingOperationHandle} _handle
     * @returns {Promise<any>}
     */
    finish_stream_pick_point(_handle) {
        _assertClass(_handle, StreamingOperationHandle);
        const ret = wasm.figgychart_finish_stream_pick_point(this.__wbg_ptr, _handle.__wbg_ptr);
        return ret;
    }
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
     * @returns {Promise<void>}
     */
    first_frame_ready() {
        const ret = wasm.figgychart_first_frame_ready(this.__wbg_ptr);
        return ret;
    }
    /**
     * Fits the chart's layout to its labels and titles and applies it
     * (`Renderer::fit_layout`, #271). It can move the plot's edges, so it
     * takes the sources of the chart's monotonic groups as
     * `resize_monotonic` does. A chart without monotonic series takes no
     * argument: `chart.fit_layout()`.
     * @param {Array<any> | null} [sources]
     */
    fit_layout(sources) {
        const ret = wasm.figgychart_fit_layout(this.__wbg_ptr, isLikeNone(sources) ? 0 : addToExternrefTable0(sources));
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Fit every axis the chart's series use to their registered columns,
     * in one call (`Renderer::fit_ranges`, #297): the x and y axes of the
     * base chart, of each overlay and of each subplot and its overlays,
     * and the z axis of a 3D chart, from the columns' cached statistics
     * with 5% padding. A chart starts at a `0..1` placeholder range; this
     * is the call for a first plot. Synchronous, and independent of the
     * active layer. A layer without series keeps its ranges. A streamed
     * source and a monotonic chart are refused, and a refusal changes
     * nothing. `auto_fit_all(padding)` instead measures the active
     * layer's drawn extents (error bar ends included) on the GPU.
     * JS: `chart.fit_ranges()`
     */
    fit_ranges() {
        const ret = wasm.figgychart_fit_ranges(this.__wbg_ptr);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Process pending pool maintenance and draw only when visual state is
     * dirty. A clean rAF tick returns before touching the pool or surface.
     * Format numerical category/box/radar labels from resident GPU values.
     * The host supplies no retained source arrays; the public model owns formatting.
     * @returns {Promise<string>}
     */
    format_value_labels() {
        const ret = wasm.figgychart_format_value_labels(this.__wbg_ptr);
        return ret;
    }
    frame() {
        const ret = wasm.figgychart_frame(this.__wbg_ptr);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Whether the last frame drew every series of the chart (#299): false
     * while a series waits for its pipelines' background compile, which
     * the frames that follow draw as they resolve.
     * @returns {boolean}
     */
    frame_complete() {
        const ret = wasm.figgychart_frame_complete(this.__wbg_ptr);
        return ret !== 0;
    }
    /**
     * Serialize the full chart option SSoT to a JSON string.
     * JS: `const cfg = JSON.parse(chart.get_config());`
     * @returns {string}
     */
    get_config() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgychart_get_config(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * Serialize the series declarations (columns, render type, styles).
     * @returns {string}
     */
    get_series() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgychart_get_series(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * Read-only accounting. These are requested GPU allocations, not a
     * driver VRAM measurement; retired bytes remain charged until the
     * queue completion callback fires.
     * @returns {string}
     */
    gpu_memory_status() {
        let deferred1_0;
        let deferred1_1;
        try {
            const ret = wasm.figgychart_gpu_memory_status(this.__wbg_ptr);
            deferred1_0 = ret[0];
            deferred1_1 = ret[1];
            return getStringFromWasm0(ret[0], ret[1]);
        } finally {
            wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
        }
    }
    /**
     * Host fence: does not borrow the chart while GPU work completes.
     * @returns {Promise<any>}
     */
    gpu_ready() {
        const ret = wasm.figgychart_gpu_ready(this.__wbg_ptr);
        return ret;
    }
    /**
     * `true` while a chart element or an annotation is selected.
     * @returns {boolean}
     */
    has_selection() {
        const ret = wasm.figgychart_has_selection(this.__wbg_ptr);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
    /**
     * The topmost drawn annotation under a point in physical canvas
     * pixels, as its index.
     * @param {number} x
     * @param {number} y
     * @returns {number | undefined}
     */
    hit_annotation(x, y) {
        const ret = wasm.figgychart_hit_annotation(this.__wbg_ptr, x, y);
        return ret === Number.MAX_SAFE_INTEGER ? undefined : ret;
    }
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
     * @param {number} x
     * @param {number} y
     * @returns {string | undefined}
     */
    hit_test(x, y) {
        const ret = wasm.figgychart_hit_test(this.__wbg_ptr, x, y);
        if (ret[3]) {
            throw takeFromExternrefTable0(ret[2]);
        }
        let v1;
        if (ret[0] !== 0) {
            v1 = getStringFromWasm0(ret[0], ret[1]);
            wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
        }
        return v1;
    }
    /**
     * The subplots that are insets now (nested in another panel's plot),
     * bottom to top, as a JSON array of indices.
     * @returns {string}
     */
    insets() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgychart_insets(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * Metadata-only admission for incoming columns; no payload is read,
     * registered, uploaded, or reserved. Chart-derived buffers are excluded.
     * @param {Float64Array} lengths
     * @returns {string}
     */
    inspect_column_admission(lengths) {
        let deferred3_0;
        let deferred3_1;
        try {
            const ptr0 = passArrayF64ToWasm0(lengths, wasm.__wbindgen_malloc);
            const len0 = WASM_VECTOR_LEN;
            const ret = wasm.figgychart_inspect_column_admission(this.__wbg_ptr, ptr0, len0);
            var ptr2 = ret[0];
            var len2 = ret[1];
            if (ret[3]) {
                ptr2 = 0; len2 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred3_0 = ptr2;
            deferred3_1 = len2;
            return getStringFromWasm0(ptr2, len2);
        } finally {
            wasm.__wbindgen_free(deferred3_0, deferred3_1, 1);
        }
    }
    /**
     * Queue cancellation only when an automatic stream is active.
     * @returns {string}
     */
    interrupt_render() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgychart_interrupt_render(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * Load the bundled demo (sine + RC charge curves) — lets a frontend
     * see a real chart without wiring data first. Repeated calls replace
     * the demo registrations and keep the same series declarations.
     */
    load_demo() {
        const ret = wasm.figgychart_load_demo(this.__wbg_ptr);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * The chart's monotonic groups, each once, as a JSON array of names
     * (#271): the groups whose sources `resize_monotonic`, `fit_layout`
     * and the monotonic exports take. Empty for a chart without them.
     * @returns {string}
     */
    monotonic_groups() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgychart_monotonic_groups(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * The monotonic series that need their group's source before they
     * can be drawn, as JSON `[{ series_id, group, change }]` (#271):
     * series whose group was never supplied, which draw nothing until
     * `set_monotonic` supplies it. A call that moves the mapping takes the
     * source or is refused, so no other series is listed.
     * @returns {string}
     */
    needs_source() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgychart_needs_source(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * Move among source rows represented in the completed packed view.
     * Returns only the original source index; no source or GPU readback.
     * @param {string | null | undefined} source_id
     * @param {string} series_id
     * @param {number} current
     * @param {boolean} forward
     * @returns {any}
     */
    next_view_point_index(source_id, series_id, current, forward) {
        var ptr0 = isLikeNone(source_id) ? 0 : passStringToWasm0(source_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        var len0 = WASM_VECTOR_LEN;
        const ptr1 = passStringToWasm0(series_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_next_view_point_index(this.__wbg_ptr, ptr0, len0, ptr1, len1, current, forward);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return takeFromExternrefTable0(ret[0]);
    }
    /**
     * Pointer move with frame delta — drags or resizes the selection.
     * After a press on an annotation the delta moves that item (or the
     * pressed handle) through the frame's anchor space.
     * @param {number} dx
     * @param {number} dy
     */
    on_move(dx, dy) {
        const ret = wasm.figgychart_on_move(this.__wbg_ptr, dx, dy);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
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
     * @param {number} x
     * @param {number} y
     * @returns {boolean}
     */
    on_press(x, y) {
        const ret = wasm.figgychart_on_press(this.__wbg_ptr, x, y);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
    /**
     * Pointer release: ends the drag or handle drag, and releases a held
     * display placement so a document a subplot drag grew fits the canvas
     * again (#205).
     */
    on_release() {
        const ret = wasm.figgychart_on_release(this.__wbg_ptr);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Pick the nearest visible data primitive at canvas pixel `(x, y)`;
     * equal-distance hits follow chart paint order.
     * Unlike `pick_point`, this includes histogram bins, canonical heatmap
     * cells and contour levels. The tagged result contains only stable
     * source/series indices plus `distance_px`; values and geometry stay
     * in the renderer's GPU-backed SSoT. Resolves to `undefined` on miss.
     * @param {number} x
     * @param {number} y
     * @param {number} max_distance_px
     * @returns {Promise<any>}
     */
    pick_data(x, y, max_distance_px) {
        const ret = wasm.figgychart_pick_data(this.__wbg_ptr, x, y, max_distance_px);
        return ret;
    }
    /**
     * Pick the nearest visible data primitive to canvas pixel `(x, y)`.
     * Scatter hits use the visible marker size, including per-point style
     * mapping; error-bar stems and caps name their point; line strokes and
     * the inside of a line's fill snap to the nearest endpoint data point on
     * the hit segment.
     * Resolves to a JSON string
     * `{ source_id, series_id, point_index, distance_px }`, or
     * `undefined` when no visible primitive is within `max_distance_px`.
     * On a chart that draws value labels a label under the pointer wins
     * (it is drawn over the data): the hit then names the label's series,
     * its category as `point_index`, and its `label_id`
     * (`"series:<series_id>:label:<index>"`), which `press_value_label`
     * takes to drag it.
     * The `<figgy-chart>` facade parses the string and normalizes
     * `undefined` to `null`.
     * @param {number} x
     * @param {number} y
     * @param {number} max_distance_px
     * @returns {Promise<any>}
     */
    pick_point(x, y, max_distance_px) {
        const ret = wasm.figgychart_pick_point(this.__wbg_ptr, x, y, max_distance_px);
        return ret;
    }
    /**
     * Every background compile that failed (#299), in order, as
     * `[{ label, kind, message }]`. `kind` is `"validation"` or
     * `"internal"` (the browser's `GPUPipelineError` reason), `"rejected"`
     * (any other rejection), `"device_lost"` or `"cancelled"`.
     *
     * JS: `for (const { label, kind } of chart.pipeline_failures()) …`
     * @returns {Array<any>}
     */
    pipeline_failures() {
        const ret = wasm.figgychart_pipeline_failures(this.__wbg_ptr);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return takeFromExternrefTable0(ret[0]);
    }
    /**
     * The chart's background pipeline compiles (#299) as an object:
     * `{ screen: { total, ready, compiling, failed }, all: { … },
     * frame_complete }`. `screen` counts what the last frame needed, so a
     * progress bar over it never goes back; `all` grows when a chart first
     * needs a module compiled on demand. `compiling` counts the waiting
     * compiles too.
     *
     * JS: `const { screen, all, frame_complete } = chart.pipeline_status();`
     * @returns {any}
     */
    pipeline_status() {
        const ret = wasm.figgychart_pipeline_status(this.__wbg_ptr);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return takeFromExternrefTable0(ret[0]);
    }
    /**
     * Resolves once every background compile scheduled so far has ended
     * (#299). It rejects like [`Self::series_ready`] with the first that
     * failed. It draws nothing.
     *
     * JS: `await chart.pipelines_ready();`
     * @returns {Promise<void>}
     */
    pipelines_ready() {
        const ret = wasm.figgychart_pipelines_ready(this.__wbg_ptr);
        return ret;
    }
    /**
     * Commit the automatic layout of the Feynman series `series_id`
     * (#234): every unplaced vertex gets the place it is drawn at.
     * Returns whether anything was written. The wrapper commits it on
     * registration already; a host that edits the series in place calls
     * this to fix the new vertices.
     * @param {string} series_id
     * @returns {boolean}
     */
    place_feynman_vertices(series_id) {
        const ptr0 = passStringToWasm0(series_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_place_feynman_vertices(this.__wbg_ptr, ptr0, len0);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
    /**
     * The anchor (`Anchor` JSON) at a point in physical canvas pixels,
     * as `"Data"` or `"Ratio"`, for placing a new text box or arrow
     * where the user clicked. `null` when the point has no data
     * position (outside a log axis, or the chart has no value axes).
     * @param {number} x
     * @param {number} y
     * @param {string} kind
     * @returns {string}
     */
    pointer_to_anchor(x, y, kind) {
        let deferred3_0;
        let deferred3_1;
        try {
            const ptr0 = passStringToWasm0(kind, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ret = wasm.figgychart_pointer_to_anchor(this.__wbg_ptr, x, y, ptr0, len0);
            var ptr2 = ret[0];
            var len2 = ret[1];
            if (ret[3]) {
                ptr2 = 0; len2 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred3_0 = ptr2;
            deferred3_1 = len2;
            return getStringFromWasm0(ptr2, len2);
        } finally {
            wasm.__wbindgen_free(deferred3_0, deferred3_1, 1);
        }
    }
    /**
     * Refresh renderer-owned annotation geometry without submitting a frame.
     */
    prepare_interaction() {
        const ret = wasm.figgychart_prepare_interaction(this.__wbg_ptr);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Press on an energy-level label (#203): row `index` of the list `part`
     * (`"level"`, `"transition"`, `"limit"` or `"band"`) of series `series_id`, as a
     * `pick_point` hit names it. The label becomes the typed selection and
     * the drag starts, as `press_value_label` does; `on_move` writes the
     * row's `label_offset`. Returns `false` and changes nothing for a row
     * without a label.
     * JS: `if (hit?.kind === "value_label" && hit.part) chart.press_energy_label(hit.series_id, hit.part, hit.category_index);`
     * @param {string} series_id
     * @param {string} part
     * @param {number} index
     * @returns {boolean}
     */
    press_energy_label(series_id, part, index) {
        const ptr0 = passStringToWasm0(series_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passStringToWasm0(part, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_press_energy_label(this.__wbg_ptr, ptr0, len0, ptr1, len1, index);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
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
     * @param {string} series_id
     * @param {string} kind
     * @param {number} index
     * @param {string | null} [part]
     * @returns {boolean}
     */
    press_feynman(series_id, kind, index, part) {
        const ptr0 = passStringToWasm0(series_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passStringToWasm0(kind, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        var ptr2 = isLikeNone(part) ? 0 : passStringToWasm0(part, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        var len2 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_press_feynman(this.__wbg_ptr, ptr0, len0, ptr1, len1, index, ptr2, len2);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
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
     * @param {string} label_id
     * @returns {boolean}
     */
    press_value_label(label_id) {
        const ptr0 = passStringToWasm0(label_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_press_value_label(this.__wbg_ptr, ptr0, len0);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
    /**
     * Prepare the same resident Cartesian groups as prewarm_all_with_progress,
     * without a progress callback. The host must prevent other calls on this
     * kernel until the Promise settles; wasm-bindgen does not queue them.
     * @returns {Promise<void>}
     */
    prewarm_all() {
        const ret = wasm.figgychart_prewarm_all(this.__wbg_ptr);
        return ret;
    }
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
     * @param {Function} on_event
     * @returns {Promise<void>}
     */
    prewarm_all_with_progress(on_event) {
        const ret = wasm.figgychart_prewarm_all_with_progress(this.__wbg_ptr, on_event);
        return ret;
    }
    /**
     * Compile the exact GPU picker and prepare it for the current chart.
     * Repeated calls, including retries, reuse renderer-owned state.
     * @returns {Promise<void>}
     */
    prewarm_gpu_picking() {
        const ret = wasm.figgychart_prewarm_gpu_picking(this.__wbg_ptr);
        return ret;
    }
    /**
     * Register a new `Float32Array` column. Existing ids are rejected.
     * @param {string} id
     * @param {Float32Array} data
     */
    register_column_f32(id, data) {
        const ptr0 = passStringToWasm0(id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF32ToWasm0(data, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_register_column_f32(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Register a new `Float64Array` column as GPU `(hi, lo)` pairs.
     * Existing ids are rejected.
     * @param {string} id
     * @param {Float64Array} data
     */
    register_column_f64(id, data) {
        const ptr0 = passStringToWasm0(id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(data, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_register_column_f64(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
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
     * @param {string[]} ids
     * @param {Float32Array} data
     * @param {number} values_per_column
     */
    register_columns_f32(ids, data, values_per_column) {
        const ptr0 = passArrayJsValueToWasm0(ids, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF32ToWasm0(data, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_register_columns_f32(this.__wbg_ptr, ptr0, len0, ptr1, len1, values_per_column);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Register many new columns from **one** flat `Float64Array`.
     *
     * The f64 counterpart of [`Self::register_columns_f32`], and it keeps the
     * same precision the single-column `register_column_f64` does: values are
     * uploaded as the `(hi, lo)` f32 pair, not cast to f32.
     * @param {string[]} ids
     * @param {Float64Array} data
     * @param {number} values_per_column
     */
    register_columns_f64(ids, data, values_per_column) {
        const ptr0 = passArrayJsValueToWasm0(ids, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(data, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_register_columns_f64(this.__wbg_ptr, ptr0, len0, ptr1, len1, values_per_column);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
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
     * @param {Uint8Array} bytes
     * @returns {string[]}
     */
    register_font(bytes) {
        const ptr0 = passArray8ToWasm0(bytes, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_register_font(this.__wbg_ptr, ptr0, len0);
        if (ret[3]) {
            throw takeFromExternrefTable0(ret[2]);
        }
        var v2 = getArrayJsValueFromWasm0(ret[0], ret[1]);
        wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
        return v2;
    }
    /**
     * Register or replace the ragged column `id`: `offsets.len() - 1`
     * groups, group `g` being `values[offsets[g]..offsets[g + 1]]`.
     *
     * `offsets` starts at 0, never decreases, holds integers and ends at
     * `values.len()`; anything else is an error and nothing is registered.
     * Both arrays upload as `(hi, lo)` pairs in one batch, through the same
     * borrowed adapters as `register_columns_f64`. Resident only, as
     * `register_record`.
     * @param {string} id
     * @param {Float64Array} values
     * @param {Float64Array} offsets
     */
    register_ragged(id, values, offsets) {
        const ptr0 = passStringToWasm0(id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(values, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ptr2 = passArrayF64ToWasm0(offsets, wasm.__wbindgen_malloc);
        const len2 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_register_ragged(this.__wbg_ptr, ptr0, len0, ptr1, len1, ptr2, len2);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
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
     * @param {string} id
     * @param {any} fields
     */
    register_record(id, fields) {
        const ptr0 = passStringToWasm0(id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_register_record(this.__wbg_ptr, ptr0, len0, fields);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Register replayable stream metadata without requiring a complete
     * typed array at the wasm boundary. Payload ranges are supplied only
     * after the renderer requests them.
     * @param {string[]} ids
     * @param {Float64Array} revisions
     * @param {Float64Array} lengths
     * @param {string[]} encodings
     */
    register_streaming_column_sources(ids, revisions, lengths, encodings) {
        const ptr0 = passArrayJsValueToWasm0(ids, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(revisions, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ptr2 = passArrayF64ToWasm0(lengths, wasm.__wbindgen_malloc);
        const len2 = WASM_VECTOR_LEN;
        const ptr3 = passArrayJsValueToWasm0(encodings, wasm.__wbindgen_malloc);
        const len3 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_register_streaming_column_sources(this.__wbg_ptr, ptr0, len0, ptr1, len1, ptr2, len2, ptr3, len3);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Register N replayable typed-array columns without uploading or
     * retaining their contents. Each source must be a `Float32Array` or
     * `Float64Array`; the latter uses the renderer's hi/lo encoding.
     * @param {string[]} ids
     * @param {Float64Array} revisions
     * @param {Array<any>} sources
     */
    register_streaming_columns(ids, revisions, sources) {
        const ptr0 = passArrayJsValueToWasm0(ids, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(revisions, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_register_streaming_columns(this.__wbg_ptr, ptr0, len0, ptr1, len1, sources);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Register or replace the triangle index column `id` (#210): three
     * vertex indices per triangle, triangle `t` being the vertices
     * `indices[3t]`, `indices[3t + 1]` and `indices[3t + 2]`.
     *
     * `indices` is a `Uint32Array` whose length is a non-zero multiple of 3;
     * anything else is an error and nothing is registered. The array is
     * borrowed for the upload, not copied, and every index up to
     * `u32::MAX` reaches the GPU exactly. Resident only, as
     * `register_record`.
     * @param {string} id
     * @param {Uint32Array} indices
     */
    register_triangles(id, indices) {
        const ptr0 = passStringToWasm0(id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArray32ToWasm0(indices, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_register_triangles(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Compact live resident columns, drop the unused pool slab, and wait
     * for the device completion fence before reporting reclaimed bytes.
     * The 16 MiB startup slab remains as the minimum reusable pool.
     * @returns {Promise<string>}
     */
    release_unused_gpu_memory() {
        const ret = wasm.figgychart_release_unused_gpu_memory(this.__wbg_ptr);
        return ret;
    }
    /**
     * Remove the annotation at `index`. Later items move down one
     * index; the selection follows or clears.
     * @param {number} index
     */
    remove_annotation(index) {
        const ret = wasm.figgychart_remove_annotation(this.__wbg_ptr, index);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Unregister a column. Series referencing it are removed too so the
     * chart can never point at freed data. Auto-managed legends remove
     * the corresponding rows; freely edited legends preserve their text
     * and only synchronize recognized series symbols.
     * Returns `true` when the column existed.
     * @param {string} id
     * @returns {boolean}
     */
    remove_column(id) {
        const ptr0 = passStringToWasm0(id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_remove_column(this.__wbg_ptr, ptr0, len0);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
    /**
     * Unregister a series. Columns stay registered. Auto-managed legends
     * remove its row; freely edited legends preserve their text and only
     * synchronize recognized series symbols.
     * Returns `true` when the series existed.
     * @param {string} series_id
     * @returns {boolean}
     */
    remove_series(series_id) {
        const ptr0 = passStringToWasm0(series_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_remove_series(this.__wbg_ptr, ptr0, len0);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
    /**
     * Unregister the triangle index column `id` and free its GPU memory.
     * Returns `true` when it existed.
     * @param {string} id
     * @returns {boolean}
     */
    remove_triangles(id) {
        const ptr0 = passStringToWasm0(id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_remove_triangles(this.__wbg_ptr, ptr0, len0);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
    /**
     * Replace existing stream metadata. The new revision becomes live
     * only after the renderer accepts the whole batch.
     * @param {string[]} ids
     * @param {Float64Array} revisions
     * @param {Float64Array} lengths
     * @param {string[]} encodings
     */
    replace_streaming_column_sources(ids, revisions, lengths, encodings) {
        const ptr0 = passArrayJsValueToWasm0(ids, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(revisions, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ptr2 = passArrayF64ToWasm0(lengths, wasm.__wbindgen_malloc);
        const len2 = WASM_VECTOR_LEN;
        const ptr3 = passArrayJsValueToWasm0(encodings, wasm.__wbindgen_malloc);
        const len3 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_replace_streaming_column_sources(this.__wbg_ptr, ptr0, len0, ptr1, len1, ptr2, len2, ptr3, len3);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Atomically publish newer revisions for existing streamed columns.
     * The renderer still retains no JavaScript typed-array reference.
     * @param {string[]} ids
     * @param {Float64Array} revisions
     * @param {Array<any>} sources
     */
    replace_streaming_columns(ids, revisions, sources) {
        const ptr0 = passArrayJsValueToWasm0(ids, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(revisions, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_replace_streaming_columns(this.__wbg_ptr, ptr0, len0, ptr1, len1, sources);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Ask the renderer to draw the latest chart state. Decoration-only
     * changes reuse the active accumulation; data, series, view, target,
     * and chunk-budget changes replace it after successful preflight.
     * @param {number} max_primitives_per_chunk
     * @returns {AutoStreamingRequestResult}
     */
    request_auto_streaming_chart(max_primitives_per_chunk) {
        const ret = wasm.figgychart_request_auto_streaming_chart(this.__wbg_ptr, max_primitives_per_chunk);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return AutoStreamingRequestResult.__wrap(ret[0]);
    }
    /**
     * Start a two-phase resident or mixed closure replacement. Existing
     * authority remains live until the range cursor completes.
     * @param {string[]} ids
     * @param {Float64Array} revisions
     * @param {Float64Array} lengths
     * @param {string[]} encodings
     * @param {number} max_primitives_per_chunk
     * @returns {AutoStreamingRequestResult}
     */
    request_resident_stream_handoff(ids, revisions, lengths, encodings, max_primitives_per_chunk) {
        const ptr0 = passArrayJsValueToWasm0(ids, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(revisions, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ptr2 = passArrayF64ToWasm0(lengths, wasm.__wbindgen_malloc);
        const len2 = WASM_VECTOR_LEN;
        const ptr3 = passArrayJsValueToWasm0(encodings, wasm.__wbindgen_malloc);
        const len3 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_request_resident_stream_handoff(this.__wbg_ptr, ptr0, len0, ptr1, len1, ptr2, len2, ptr3, len3, max_primitives_per_chunk);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return AutoStreamingRequestResult.__wrap(ret[0]);
    }
    /**
     * Synchronous fit request routing, allowing the facade to wait for
     * renderer progress without holding a wasm mutable borrow.
     * @param {number} padding
     * @returns {boolean}
     */
    request_stream_auto_fit(padding) {
        const ret = wasm.figgychart_request_stream_auto_fit(this.__wbg_ptr, padding);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
    /**
     * Move this chart to at least the shader set `shaders` (`"basic"` or
     * `"full"`, #299), as its first chart with an axis break, a
     * probability axis or polar coordinates would. A chart never goes
     * back, so `"basic"` and a repeated `"full"` do nothing. Any other
     * value throws an `Error` that names it.
     * @param {any} shaders
     */
    require_shader_set(shaders) {
        const ret = wasm.figgychart_require_shader_set(this.__wbg_ptr, shaders);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Explicitly rebuild the auto legend from `SeriesConfig.label`.
     * Legacy string labels are used only when a series has no rich label.
     */
    reset_legend_from_series_labels() {
        const ret = wasm.figgychart_reset_legend_from_series_labels(this.__wbg_ptr);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Resize the swap chain viewport. The chart Config keeps its
     * document/export `chart_area`; live rendering scales that logical
     * document into this surface.
     * @param {number} width
     * @param {number} height
     */
    resize(width, height) {
        const ret = wasm.figgychart_resize(this.__wbg_ptr, width, height);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
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
     * @param {number} width
     * @param {number} height
     * @param {Array<any>} sources
     * @param {any} plot_area
     */
    resize_monotonic(width, height, sources, plot_area) {
        const ret = wasm.figgychart_resize_monotonic(this.__wbg_ptr, width, height, sources, plot_area);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Select one annotation (its box and handles are drawn on the
     * overlay) or none. Selecting an annotation clears the decoration
     * selection; selecting a decoration with `on_press` clears this.
     * @param {number | null} [index]
     */
    select_annotation(index) {
        const ret = wasm.figgychart_select_annotation(this.__wbg_ptr, isLikeNone(index) ? Number.MAX_SAFE_INTEGER : (index) >>> 0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * @returns {number | undefined}
     */
    selected_annotation() {
        const ret = wasm.figgychart_selected_annotation(this.__wbg_ptr);
        return ret === Number.MAX_SAFE_INTEGER ? undefined : ret;
    }
    /**
     * Inspect the first resident typed selection as JSON, or `"null"` when
     * none is selected. Only selected GPU samples are read back. Histograms
     * expose `bin_start`, `bin_end`, `value`, and `orientation`; the value
     * is the stored height (also valid for weighted/density histograms).
     * Point and matrix selections expose their coordinates and cell value.
     * @returns {Promise<string>}
     */
    selection_details() {
        const ret = wasm.figgychart_selection_details(this.__wbg_ptr);
        return ret;
    }
    /**
     * Report the effective primitive/grid extent currently drawn.
     * @param {string} series_id
     * @returns {string}
     */
    series_draw_info(series_id) {
        let deferred3_0;
        let deferred3_1;
        try {
            const ptr0 = passStringToWasm0(series_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ret = wasm.figgychart_series_draw_info(this.__wbg_ptr, ptr0, len0);
            var ptr2 = ret[0];
            var len2 = ret[1];
            if (ret[3]) {
                ptr2 = 0; len2 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred3_0 = ptr2;
            deferred3_1 = len2;
            return getStringFromWasm0(ptr2, len2);
        } finally {
            wasm.__wbindgen_free(deferred3_0, deferred3_1, 1);
        }
    }
    /**
     * Resolves once a frame draws every series of the chart (#299),
     * drawing again as the pipelines it waits for compile. It rejects with
     * an `Error` carrying `label`, `kind` and `message` when one of those
     * compiles failed (see [`Self::pipeline_failures`]); the chart still
     * draws that series, and the draw reports the error as usual.
     *
     * JS: `await chart.series_ready();`
     * @returns {Promise<void>}
     */
    series_ready() {
        const ret = wasm.figgychart_series_ready(this.__wbg_ptr);
        return ret;
    }
    /**
     * Set the layer that receives pointer interaction: `"Base"`,
     * `{ "Overlay": index }`, `"Annotations"`, `{ "Subplot": index }` or
     * `{ "SubplotOverlay": [subplot, overlay] }` as JSON. The hit map is
     * rebuilt for that layer (`HitMap::for_active_layer`) and the
     * element selection is cleared when the layer changes. An overlay
     * index past the overlay list is stored as `"Base"`; the stored
     * layer is returned as JSON. Drawn pixels never depend on it.
     * JS: `chart.set_active_layer(JSON.stringify({ Overlay: 0 }))`
     * @param {string} json
     * @returns {string}
     */
    set_active_layer(json) {
        let deferred3_0;
        let deferred3_1;
        try {
            const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ret = wasm.figgychart_set_active_layer(this.__wbg_ptr, ptr0, len0);
            var ptr2 = ret[0];
            var len2 = ret[1];
            if (ret[3]) {
                ptr2 = 0; len2 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred3_0 = ptr2;
            deferred3_1 = len2;
            return getStringFromWasm0(ptr2, len2);
        } finally {
            wasm.__wbindgen_free(deferred3_0, deferred3_1, 1);
        }
    }
    /**
     * Replace the annotation at `index` with an `Annotation` JSON value.
     * @param {number} index
     * @param {string} json
     */
    set_annotation(index, json) {
        const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_annotation(this.__wbg_ptr, index, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Show or hide the whole annotation layer. Hiding skips the two
     * composite draws and re-rasterizes nothing.
     * @param {boolean} visible
     */
    set_annotations_visible(visible) {
        const ret = wasm.figgychart_set_annotations_visible(this.__wbg_ptr, visible);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Fill the chart area with a colour under everything the chart draws
     * (JSON `{"r":1,"g":1,"b":1,"a":1}`), or leave it transparent (`null`)
     * so the page or the export's clear colour shows through (#265).
     * @param {string} json
     */
    set_background(json) {
        const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_background(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
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
     * to nice ticks. The chart keeps its chart area; the series, columns,
     * records and config of a box plot document opened before are
     * replaced, every other column stays. From here on the chart is edited
     * through the Cartesian API.
     *
     * A document that does not parse or validate, or whose series styles
     * cannot be created, is rejected with the previous chart unchanged. A
     * failure while the new columns upload or the axis fits from them
     * rejects with a chart that has no series: the previous document's
     * series and columns are retired by then.
     *
     * JS: `chart.set_boxplot_document(JSON.stringify(doc));`
     * @param {string} json
     */
    set_boxplot_document(json) {
        const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_boxplot_document(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
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
     * rounded to nice ticks. The chart keeps its chart area; the series,
     * columns and config of a categorical document opened before
     * are replaced, every other column stays. From here on the chart is
     * edited through the Cartesian API (`get_config` / `set_config`,
     * `get_series` / `set_series`, the column registry).
     *
     * A document that does not parse or validate, or whose series styles
     * cannot be created, is rejected with the previous chart unchanged. A
     * failure while the new columns upload or the axis fits from them
     * rejects with a chart that has no series: the previous document's
     * series and columns are retired by then.
     *
     * JS: `chart.set_categorical_document(JSON.stringify(doc));`
     * @param {string} json
     */
    set_categorical_document(json) {
        const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_categorical_document(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Set the WebGPU surface clear color used behind the chart panel.
     * Components are linear 0..1 RGBA floats. This is host/app state:
     * it does not change the chart Config JSON.
     * @param {number} r
     * @param {number} g
     * @param {number} b
     * @param {number} a
     */
    set_clear_color(r, g, b, a) {
        wasm.figgychart_set_clear_color(this.__wbg_ptr, r, g, b, a);
    }
    /**
     * Replace the colourbar's z-axis options as one SSoT value. This is
     * the focused edit boundary for tick direction/style/length, value
     * direction, tick-label style/offsets, and title options.
     * @param {string} json
     */
    set_colorbar_axis(json) {
        const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_colorbar_axis(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Set the colourbar title text, a label with `$…$` spans as TeX, and
     * make it visible. An empty string
     * hides it. The full rich-text/title offsets remain available through
     * `set_colorbar_axis` or the chart Config SSoT.
     * @param {string} text
     */
    set_colorbar_title(text) {
        const ptr0 = passStringToWasm0(text, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_colorbar_title(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
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
     * @param {string} json
     */
    set_config(json) {
        const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_config(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Replace one contour series' levels with axis-native nice levels.
     * The resulting explicit values remain the series SSoT.
     * @param {string} series_id
     * @param {number} target_count
     * @param {boolean} use_colormap_colors
     * @returns {number}
     */
    set_contour_nice_levels(series_id, target_count, use_colormap_colors) {
        const ptr0 = passStringToWasm0(series_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_contour_nice_levels(this.__wbg_ptr, ptr0, len0, target_count, use_colormap_colors);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] >>> 0;
    }
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
     * @param {string} group
     * @param {number} start
     * @param {number} interval
     * @param {any} data
     * @param {any} range
     * @param {number | null} [stride]
     * @param {Uint32Array | null} [columns]
     * @returns {string}
     */
    set_monotonic(group, start, interval, data, range, stride, columns) {
        let deferred4_0;
        let deferred4_1;
        try {
            const ptr0 = passStringToWasm0(group, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            var ptr1 = isLikeNone(columns) ? 0 : passArray32ToWasm0(columns, wasm.__wbindgen_malloc);
            var len1 = WASM_VECTOR_LEN;
            const ret = wasm.figgychart_set_monotonic(this.__wbg_ptr, ptr0, len0, start, interval, data, range, isLikeNone(stride) ? Number.MAX_SAFE_INTEGER : (stride) >>> 0, ptr1, len1);
            var ptr3 = ret[0];
            var len3 = ret[1];
            if (ret[3]) {
                ptr3 = 0; len3 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred4_0 = ptr3;
            deferred4_1 = len3;
            return getStringFromWasm0(ptr3, len3);
        } finally {
            wasm.__wbindgen_free(deferred4_0, deferred4_1, 1);
        }
    }
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
     * @param {string} config_json
     * @param {string} series_json
     */
    set_monotonic_document(config_json, series_json) {
        const ptr0 = passStringToWasm0(config_json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passStringToWasm0(series_json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_monotonic_document(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Replace the chart's selection (`picked_data`). Passing JSON `null`
     * clears it.
     * @param {string} json
     */
    set_picked_data(json) {
        const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_picked_data(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Pool growth on an otherwise out-of-space upload, on by default.
     * Growth remains bounded by the device storage-binding limit and
     * the configured renderer memory budget; `false` keeps the pool's
     * current capacity.
     * @param {boolean} enabled
     */
    set_pool_auto_growth(enabled) {
        wasm.figgychart_set_pool_auto_growth(this.__wbg_ptr, enabled);
    }
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
     * either way. The chart keeps its chart area; the series, columns and
     * config of a radar document opened before are replaced, every other
     * column stays. From here on the chart is edited through the Cartesian
     * API (`get_config` / `set_config`, `get_series` / `set_series`, the
     * column registry), and its vertices pick, select and step as points.
     *
     * A document that does not parse or validate, or whose series styles
     * cannot be created, is rejected with the previous chart unchanged. A
     * failure while the new columns upload or the axis fits from them
     * rejects with a chart that has no series: the previous document's
     * series and columns are retired by then.
     *
     * JS: `chart.set_radar_document(JSON.stringify(doc));`
     * @param {string} json
     */
    set_radar_document(json) {
        const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_radar_document(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
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
     * @param {string} json
     */
    set_series(json) {
        const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_series(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Set / change / remove a series' legend label. `'\n'` breaks lines;
     * unicode sub/superscripts (`₀`, `⁻`, …) map to styled segments;
     * `$…$` spans are TeX and `\$` is a dollar sign.
     * Empty string removes the legend row. Returns `true` when the
     * series exists.
     * @param {string} series_id
     * @param {string} label
     * @returns {boolean}
     */
    set_series_label(series_id, label) {
        const ptr0 = passStringToWasm0(series_id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passStringToWasm0(label, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_series_label(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
    /**
     * @param {number} primitives
     */
    set_stream_chunk_budget(primitives) {
        const ret = wasm.figgychart_set_stream_chunk_budget(this.__wbg_ptr, primitives);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * @param {StreamingOperationHandle} handle
     * @param {number} max_primitives
     */
    set_stream_operation_chunk_budget(handle, max_primitives) {
        _assertClass(handle, StreamingOperationHandle);
        const ret = wasm.figgychart_set_stream_operation_chunk_budget(this.__wbg_ptr, handle.__wbg_ptr, max_primitives);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Place subplot `index`'s frame at `(x, y)` with `width` x `height`, in
     * document pixels (the coordinates of `get_config`'s `chart_area`s):
     * anywhere, inside the parent chart (an inset), over another panel or
     * beside every one. The subplot's plot must fit in the frame; an error
     * leaves the document unchanged. A pointer drag on the frame does the
     * same on the base layer.
     * JS: `chart.set_subplot_area(0, 120, 80, 320, 240);`
     * @param {number} index
     * @param {number} x
     * @param {number} y
     * @param {number} width
     * @param {number} height
     */
    set_subplot_area(index, x, y, width, height) {
        const ret = wasm.figgychart_set_subplot_area(this.__wbg_ptr, index, x, y, width, height);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Fill subplot `index`'s plot with a colour (JSON `{"r":1,"g":1,"b":1,
     * "a":1}`) or leave it transparent (`null`): an inset usually covers
     * the parent's data under it.
     * @param {number} index
     * @param {string} json
     */
    set_subplot_background(index, json) {
        const ptr0 = passStringToWasm0(json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_subplot_background(this.__wbg_ptr, index, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * How subplot `index`'s text follows its cell (#292): `"Auto"` (the
     * default) draws its titles, tick labels, legend and colourbar text at
     * the stored sizes times `subplot_text_factor(index)`; `"Fixed"` draws
     * the stored sizes. The stored sizes are never changed;
     * [`Self::subplot_text_scale`] reads the mode back.
     * JS: `chart.set_subplot_text_scale(0, "Fixed");`
     * @param {number} index
     * @param {string} mode
     */
    set_subplot_text_scale(index, mode) {
        const ptr0 = passStringToWasm0(mode, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_subplot_text_scale(this.__wbg_ptr, index, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Set the title text and grow its band if needed. Like every text
     * setter (`set_x_title`, `set_y_title`, `set_colorbar_title`, and the
     * labels of `add_line_series` and `set_series_label`), it reads the
     * text as matplotlib reads a label: `$…$`, `\(…\)` and `$$…$$` spans
     * are TeX, `\$` is a dollar sign, and text whose TeX does not parse is
     * shown as written. For a text-only edit that keeps the exact margin,
     * use `get_config` / `set_config` and change only `chart_title.text`.
     * @param {string} text
     */
    set_title(text) {
        const ptr0 = passStringToWasm0(text, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_title(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Set the bottom x axis title, a label with `$…$` spans as TeX.
     * @param {string} text
     */
    set_x_title(text) {
        const ptr0 = passStringToWasm0(text, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_x_title(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Set the left y axis title, a label with `$…$` spans as TeX.
     * @param {string} text
     */
    set_y_title(text) {
        const ptr0 = passStringToWasm0(text, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_set_y_title(this.__wbg_ptr, ptr0, len0);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * The shader set this chart compiles (#299): `"basic"` or `"full"`.
     * @returns {string}
     */
    shader_set() {
        let deferred1_0;
        let deferred1_1;
        try {
            const ret = wasm.figgychart_shader_set(this.__wbg_ptr);
            deferred1_0 = ret[0];
            deferred1_1 = ret[1];
            return getStringFromWasm0(ret[0], ret[1]);
        } finally {
            wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
        }
    }
    /**
     * Move the resident typed data selection using source indices
     * (`Renderer::step_chart_selection`): `Config::step_selection` over
     * the chart's series and the registered column lengths, and a
     * monotonic series' point over the points its envelope keeps (#271).
     * @param {number} dx
     * @param {number} dy
     * @returns {boolean}
     */
    step_selection(dx, dy) {
        const ret = wasm.figgychart_step_selection(this.__wbg_ptr, dx, dy);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
    /**
     * @param {StreamingOperationHandle} handle
     * @returns {AutoStreamingRangeRequestResult}
     */
    stream_operation_request_ranges(handle) {
        _assertClass(handle, StreamingOperationHandle);
        const ret = wasm.figgychart_stream_operation_request_ranges(this.__wbg_ptr, handle.__wbg_ptr);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return AutoStreamingRangeRequestResult.__wrap(ret[0]);
    }
    /**
     * @param {StreamingOperationHandle} handle
     * @param {string[]} ids
     * @param {Float64Array} revisions
     * @param {Float64Array} source_lengths
     * @param {Float64Array} offsets
     * @param {Array<any>} sources
     * @returns {StreamingStepResult}
     */
    stream_operation_submit_ranges(handle, ids, revisions, source_lengths, offsets, sources) {
        _assertClass(handle, StreamingOperationHandle);
        const ptr0 = passArrayJsValueToWasm0(ids, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(revisions, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ptr2 = passArrayF64ToWasm0(source_lengths, wasm.__wbindgen_malloc);
        const len2 = WASM_VECTOR_LEN;
        const ptr3 = passArrayF64ToWasm0(offsets, wasm.__wbindgen_malloc);
        const len3 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_stream_operation_submit_ranges(this.__wbg_ptr, handle.__wbg_ptr, ptr0, len0, ptr1, len1, ptr2, len2, ptr3, len3, sources);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return StreamingStepResult.__wrap(ret[0]);
    }
    /**
     * Independent selected-row request; it never advances the data cursor.
     * @returns {AutoStreamingRangeRequestResult}
     */
    stream_selection_request_ranges() {
        const ret = wasm.figgychart_stream_selection_request_ranges(this.__wbg_ptr);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return AutoStreamingRangeRequestResult.__wrap(ret[0]);
    }
    /**
     * @param {AutoStreamingRangeRequestResult} request
     * @param {string[]} ids
     * @param {Float64Array} revisions
     * @param {Float64Array} source_lengths
     * @param {Float64Array} offsets
     * @param {Array<any>} sources
     */
    stream_selection_submit_ranges(request, ids, revisions, source_lengths, offsets, sources) {
        _assertClass(request, AutoStreamingRangeRequestResult);
        const ptr0 = passArrayJsValueToWasm0(ids, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(revisions, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ptr2 = passArrayF64ToWasm0(source_lengths, wasm.__wbindgen_malloc);
        const len2 = WASM_VECTOR_LEN;
        const ptr3 = passArrayF64ToWasm0(offsets, wasm.__wbindgen_malloc);
        const len3 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_stream_selection_submit_ranges(this.__wbg_ptr, request.__wbg_ptr, ptr0, len0, ptr1, len1, ptr2, len2, ptr3, len3, sources);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Pure metadata inspection; does not poll, reserve a range, or draw.
     * @returns {string}
     */
    stream_status() {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgychart_stream_status(this.__wbg_ptr);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * Advance at most one renderer-selected chunk. `sources` contains the
     * original replayable typed arrays; only the requested range is read
     * directly into mapped staging, and no owned CPU data mirror is made.
     * @param {string[]} ids
     * @param {Float64Array} revisions
     * @param {Array<any>} sources
     * @returns {StreamingStepResult}
     */
    stream_step(ids, revisions, sources) {
        const ptr0 = passArrayJsValueToWasm0(ids, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(revisions, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_stream_step(this.__wbg_ptr, ptr0, len0, ptr1, len1, sources);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return StreamingStepResult.__wrap(ret[0]);
    }
    /**
     * @returns {string}
     */
    streaming_capabilities() {
        let deferred1_0;
        let deferred1_1;
        try {
            const ret = wasm.figgychart_streaming_capabilities(this.__wbg_ptr);
            deferred1_0 = ret[0];
            deferred1_1 = ret[1];
            return getStringFromWasm0(ret[0], ret[1]);
        } finally {
            wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
        }
    }
    /**
     * Wake after work already submitted to this queue completes. The
     * returned promise owns only its completion receiver, not a chart or
     * renderer borrow. Resolving does not service receipts or draw a frame.
     * @returns {Promise<any>}
     */
    streaming_gpu_ready() {
        const ret = wasm.figgychart_streaming_gpu_ready(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {StreamingUsageResult}
     */
    streaming_usage() {
        const ret = wasm.figgychart_streaming_usage(this.__wbg_ptr);
        return StreamingUsageResult.__wrap(ret);
    }
    /**
     * Subplot `index`'s frame as JSON `{"x":..,"y":..,"width":..,"height":..}`
     * in document pixels.
     * @param {number} index
     * @returns {string}
     */
    subplot_area(index) {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgychart_subplot_area(this.__wbg_ptr, index);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * The factor subplot `index` draws its text with now (#292,
     * `Config::subplot_text_factor`): 1 for a `"Fixed"` subplot or a cell
     * as large as the parent chart, down to 0.5 for a small cell. It
     * follows `set_subplot_area`, a frame drag and a resize of the parent
     * chart.
     * @param {number} index
     * @returns {number}
     */
    subplot_text_factor(index) {
        const ret = wasm.figgychart_subplot_text_factor(this.__wbg_ptr, index);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0];
    }
    /**
     * Subplot `index`'s text mode (#292, #295), as its setter
     * [`Self::set_subplot_text_scale`] takes it: `"Auto"` or `"Fixed"`.
     * @param {number} index
     * @returns {string}
     */
    subplot_text_scale(index) {
        let deferred2_0;
        let deferred2_1;
        try {
            const ret = wasm.figgychart_subplot_text_scale(this.__wbg_ptr, index);
            var ptr1 = ret[0];
            var len1 = ret[1];
            if (ret[3]) {
                ptr1 = 0; len1 = 0;
                throw takeFromExternrefTable0(ret[2]);
            }
            deferred2_0 = ptr1;
            deferred2_1 = len1;
            return getStringFromWasm0(ptr1, len1);
        } finally {
            wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
        }
    }
    /**
     * The member of the family `name` subplot `index` takes (#295), as
     * [`Self::apply_theme`] gives it there, as a plain object to edit and
     * pass to [`Self::apply_custom_theme`]. Refused as [`Self::theme`]
     * refuses the name, and with `code` `"subplot_index"` for an index
     * past the subplots.
     * @param {number} index
     * @param {string} name
     * @returns {any}
     */
    subplot_theme(index, name) {
        const ptr0 = passStringToWasm0(name, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_subplot_theme(this.__wbg_ptr, index, ptr0, len0);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return takeFromExternrefTable0(ret[0]);
    }
    suspend_stream_selection() {
        const ret = wasm.figgychart_suspend_stream_selection(this.__wbg_ptr);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * The plot rect the last plot-area resize gesture on a chart with
     * monotonic series proposed, as JSON `{ x, y, width, height }` in
     * document pixels, or `undefined` (#271). Read once: the element emits
     * it as `figgy-plot-resize`, and the host applies it with
     * `resize_monotonic(width, height, sources, plotArea)`.
     * @returns {string | undefined}
     */
    take_plot_resize_request() {
        const ret = wasm.figgychart_take_plot_resize_request(this.__wbg_ptr);
        if (ret[3]) {
            throw takeFromExternrefTable0(ret[2]);
        }
        let v1;
        if (ret[0] !== 0) {
            v1 = getStringFromWasm0(ret[0], ret[1]);
            wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
        }
        return v1;
    }
    /**
     * The member of the family `name` the chart takes (#295), as a plain
     * object (`Theme`'s fields, colours as `{r, g, b, a}`). Edit it and
     * pass it to [`Self::apply_custom_theme`]. A name that is not a family
     * throws an `Error` with `code` `"theme_unknown_name"` and the family
     * `names`.
     * @param {string} name
     * @returns {any}
     */
    theme(name) {
        const ptr0 = passStringToWasm0(name, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_theme(this.__wbg_ptr, ptr0, len0);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return takeFromExternrefTable0(ret[0]);
    }
    /**
     * The theme names (#291, #295), as an array of strings: the four
     * families, `gallery`, `cool-slate`, `midnight` and `warm-paper`.
     * @returns {Array<any>}
     */
    theme_names() {
        const ret = wasm.figgychart_theme_names(this.__wbg_ptr);
        return ret;
    }
    /**
     * Atomically replace an existing column from a `Float32Array`.
     * Missing ids are rejected; every accepted call performs an upload.
     * @param {string} id
     * @param {Float32Array} data
     */
    update_register_column_f32(id, data) {
        const ptr0 = passStringToWasm0(id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF32ToWasm0(data, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_update_register_column_f32(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Atomically replace an existing column from a `Float64Array` as
     * GPU `(hi, lo)` pairs. Every accepted call performs an upload.
     * @param {string} id
     * @param {Float64Array} data
     */
    update_register_column_f64(id, data) {
        const ptr0 = passStringToWasm0(id, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF64ToWasm0(data, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.figgychart_update_register_column_f64(this.__wbg_ptr, ptr0, len0, ptr1, len1);
        if (ret[1]) {
            throw takeFromExternrefTable0(ret[0]);
        }
    }
    /**
     * Wait until previously submitted GPU work has finished. Does not
     * draw. Used to separate an earlier compute submit from the next
     * render submit when measuring startup.
     * @returns {Promise<void>}
     */
    wait_submitted_work() {
        const ret = wasm.figgychart_wait_submitted_work(this.__wbg_ptr);
        return ret;
    }
    /**
     * Alias for [`Self::first_frame_ready`].
     * @returns {Promise<void>}
     */
    warm_up() {
        const ret = wasm.figgychart_warm_up(this.__wbg_ptr);
        return ret;
    }
    /**
     * Zoom a 3D chart's camera (`Config.view_3d`): the eye distance is
     * divided by `factor` and clamped (`Config::zoom_view`). Returns whether
     * the view changed; a flat chart never does.
     * @param {number} factor
     * @returns {boolean}
     */
    zoom_view(factor) {
        const ret = wasm.figgychart_zoom_view(this.__wbg_ptr, factor);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return ret[0] !== 0;
    }
}
if (Symbol.dispose) FiggyChart.prototype[Symbol.dispose] = FiggyChart.prototype.free;

/**
 * Opaque renderer-issued replay operation. Contains no column payload.
 */
export class StreamingOperationHandle {
    static __wrap(ptr) {
        const obj = Object.create(StreamingOperationHandle.prototype);
        obj.__wbg_ptr = ptr;
        StreamingOperationHandleFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
    }
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        StreamingOperationHandleFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_streamingoperationhandle_free(ptr, 0);
    }
}
if (Symbol.dispose) StreamingOperationHandle.prototype[Symbol.dispose] = StreamingOperationHandle.prototype.free;

/**
 * Result of one non-blocking exact streaming step.
 */
export class StreamingStepResult {
    static __wrap(ptr) {
        const obj = Object.create(StreamingStepResult.prototype);
        obj.__wbg_ptr = ptr;
        StreamingStepResultFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
    }
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        StreamingStepResultFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_streamingstepresult_free(ptr, 0);
    }
    /**
     * @returns {boolean}
     */
    get pending_latest() {
        const ret = wasm.streamingstepresult_pending_latest(this.__wbg_ptr);
        return ret !== 0;
    }
    /**
     * @returns {string}
     */
    get revision() {
        let deferred1_0;
        let deferred1_1;
        try {
            const ret = wasm.streamingstepresult_revision(this.__wbg_ptr);
            deferred1_0 = ret[0];
            deferred1_1 = ret[1];
            return getStringFromWasm0(ret[0], ret[1]);
        } finally {
            wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
        }
    }
    /**
     * @returns {string}
     */
    get status() {
        let deferred1_0;
        let deferred1_1;
        try {
            const ret = wasm.streamingstepresult_status(this.__wbg_ptr);
            deferred1_0 = ret[0];
            deferred1_1 = ret[1];
            return getStringFromWasm0(ret[0], ret[1]);
        } finally {
            wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
        }
    }
    /**
     * @returns {number}
     */
    get submitted_primitives() {
        const ret = wasm.streamingstepresult_submitted_primitives(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get total_primitives() {
        const ret = wasm.streamingstepresult_total_primitives(this.__wbg_ptr);
        return ret;
    }
}
if (Symbol.dispose) StreamingStepResult.prototype[Symbol.dispose] = StreamingStepResult.prototype.free;

/**
 * Current bounded renderer-owned streaming reservations.
 */
export class StreamingUsageResult {
    static __wrap(ptr) {
        const obj = Object.create(StreamingUsageResult.prototype);
        obj.__wbg_ptr = ptr;
        StreamingUsageResultFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
    }
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        StreamingUsageResultFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_streamingusageresult_free(ptr, 0);
    }
    /**
     * @returns {number}
     */
    get active_charts() {
        const ret = wasm.streamingusageresult_active_charts(this.__wbg_ptr);
        return ret >>> 0;
    }
    /**
     * @returns {number}
     */
    get in_flight_chunks() {
        const ret = wasm.streamingusageresult_in_flight_chunks(this.__wbg_ptr);
        return ret >>> 0;
    }
    /**
     * @returns {number}
     */
    get reserved_gpu_bytes() {
        const ret = wasm.streamingusageresult_reserved_gpu_bytes(this.__wbg_ptr);
        return ret;
    }
}
if (Symbol.dispose) StreamingUsageResult.prototype[Symbol.dispose] = StreamingUsageResult.prototype.free;

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
 * @param {string} config_json
 * @returns {string}
 */
export function autoLayout(config_json) {
    let deferred3_0;
    let deferred3_1;
    try {
        const ptr0 = passStringToWasm0(config_json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.autoLayout(ptr0, len0);
        var ptr2 = ret[0];
        var len2 = ret[1];
        if (ret[3]) {
            ptr2 = 0; len2 = 0;
            throw takeFromExternrefTable0(ret[2]);
        }
        deferred3_0 = ptr2;
        deferred3_1 = len2;
        return getStringFromWasm0(ptr2, len2);
    } finally {
        wasm.__wbindgen_free(deferred3_0, deferred3_1, 1);
    }
}

/**
 * CSS color strings (`"rgb(r g b / a)"`) for a cycle — lets the host UI
 * render swatches / legends with exactly the chart's palette.
 * @param {ColorCycle} cycle
 * @returns {string[]}
 */
export function color_cycle_css(cycle) {
    const ret = wasm.color_cycle_css(cycle);
    var v1 = getArrayJsValueFromWasm0(ret[0], ret[1]);
    wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
    return v1;
}

/**
 * Every valid `draw_style` mode tag, as a JSON string array.
 * @returns {string}
 */
export function draw_style_modes() {
    let deferred2_0;
    let deferred2_1;
    try {
        const ret = wasm.draw_style_modes();
        var ptr1 = ret[0];
        var len1 = ret[1];
        if (ret[3]) {
            ptr1 = 0; len1 = 0;
            throw takeFromExternrefTable0(ret[2]);
        }
        deferred2_0 = ptr1;
        deferred2_1 = len1;
        return getStringFromWasm0(ptr1, len1);
    } finally {
        wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
    }
}

/**
 * Parameter metadata for one `draw_style` mode — a JSON array of
 * `{key, min, max, default, integer}`. Ranges are the RECOMMENDED
 * slider spans (the SSoT accepts values beyond them; the renderer
 * applies only safety guards), and they come from the model crate, so
 * hosts never hardcode them.
 *
 * JS: `const specs = JSON.parse(draw_style_param_specs("constellation"));`
 * Valid modes: `draw_style_modes()`.
 * @param {string} mode
 * @returns {string}
 */
export function draw_style_param_specs(mode) {
    let deferred3_0;
    let deferred3_1;
    try {
        const ptr0 = passStringToWasm0(mode, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.draw_style_param_specs(ptr0, len0);
        var ptr2 = ret[0];
        var len2 = ret[1];
        if (ret[3]) {
            ptr2 = 0; len2 = 0;
            throw takeFromExternrefTable0(ret[2]);
        }
        deferred3_0 = ptr2;
        deferred3_1 = len2;
        return getStringFromWasm0(ptr2, len2);
    } finally {
        wasm.__wbindgen_free(deferred3_0, deferred3_1, 1);
    }
}

/**
 * A rich text from TeX (`RichText::from_tex`, #45): text with `$…$` or
 * `\(…\)` math spans, as the JSON of a `RichText` for any title, axis
 * title, legend, label or annotation text of `set_config` / `set_series`.
 * Errors name the TeX byte range.
 *
 * JS: `cfg.chart_title.text = JSON.parse(rich_text_from_tex("$E = mc^2$", 16, "", 0, 0, 0, 1));`
 * @param {string} tex
 * @param {number} font_size
 * @param {string} font
 * @param {number} r
 * @param {number} g
 * @param {number} b
 * @param {number} a
 * @returns {string}
 */
export function rich_text_from_tex(tex, font_size, font, r, g, b, a) {
    let deferred4_0;
    let deferred4_1;
    try {
        const ptr0 = passStringToWasm0(tex, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passStringToWasm0(font, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len1 = WASM_VECTOR_LEN;
        const ret = wasm.rich_text_from_tex(ptr0, len0, font_size, ptr1, len1, r, g, b, a);
        var ptr3 = ret[0];
        var len3 = ret[1];
        if (ret[3]) {
            ptr3 = 0; len3 = 0;
            throw takeFromExternrefTable0(ret[2]);
        }
        deferred4_0 = ptr3;
        deferred4_1 = len3;
        return getStringFromWasm0(ptr3, len3);
    } finally {
        wasm.__wbindgen_free(deferred4_0, deferred4_1, 1);
    }
}
function __wbg_get_imports() {
    const import0 = {
        __proto__: null,
        __wbg_Window_a2a6c4d665047b14: function(arg0) {
            const ret = arg0.Window;
            return ret;
        },
        __wbg_WorkerGlobalScope_2664448a7c667d67: function(arg0) {
            const ret = arg0.WorkerGlobalScope;
            return ret;
        },
        __wbg___wbindgen_debug_string_4687d8d8c2017d52: function(arg0, arg1) {
            const ret = debugString(arg1);
            const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len1 = WASM_VECTOR_LEN;
            getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
            getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
        },
        __wbg___wbindgen_is_function_1f9d30630b8b1d3d: function(arg0) {
            const ret = typeof(arg0) === 'function';
            return ret;
        },
        __wbg___wbindgen_is_null_e343b7d08827ba72: function(arg0) {
            const ret = arg0 === null;
            return ret;
        },
        __wbg___wbindgen_is_object_3c45d4f2dde4e749: function(arg0) {
            const val = arg0;
            const ret = typeof(val) === 'object' && val !== null;
            return ret;
        },
        __wbg___wbindgen_is_string_90b56bc79aad6f6c: function(arg0) {
            const ret = typeof(arg0) === 'string';
            return ret;
        },
        __wbg___wbindgen_is_undefined_8865fb403f8fe9d8: function(arg0) {
            const ret = arg0 === undefined;
            return ret;
        },
        __wbg___wbindgen_number_get_2e0e7dee9f701a71: function(arg0, arg1) {
            const obj = arg1;
            const ret = typeof(obj) === 'number' ? obj : undefined;
            getDataViewMemory0().setFloat64(arg0 + 8 * 1, isLikeNone(ret) ? 0 : ret, true);
            getDataViewMemory0().setInt32(arg0 + 4 * 0, !isLikeNone(ret), true);
        },
        __wbg___wbindgen_string_get_0380ccaa2f57f0d9: function(arg0, arg1) {
            const obj = arg1;
            const ret = typeof(obj) === 'string' ? obj : undefined;
            var ptr1 = isLikeNone(ret) ? 0 : passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            var len1 = WASM_VECTOR_LEN;
            getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
            getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
        },
        __wbg___wbindgen_throw_41e9ee4f547fc59a: function(arg0, arg1) {
            throw new Error(getStringFromWasm0(arg0, arg1));
        },
        __wbg__wbg_cb_unref_dcc1a90847f04c41: function(arg0) {
            arg0._wbg_cb_unref();
        },
        __wbg_allSettled_f26c6af8232ba69f: function(arg0) {
            const ret = Promise.allSettled(arg0);
            return ret;
        },
        __wbg_all_196ab373185536a2: function(arg0) {
            const ret = Promise.all(arg0);
            return ret;
        },
        __wbg_beginComputePass_b9a325184985e6ff: function(arg0, arg1) {
            const ret = arg0.beginComputePass(arg1);
            return ret;
        },
        __wbg_beginRenderPass_3c53642423af50dc: function() { return handleError(function (arg0, arg1) {
            const ret = arg0.beginRenderPass(arg1);
            return ret;
        }, arguments); },
        __wbg_call_187d372bd5fdd4aa: function() { return handleError(function (arg0, arg1, arg2) {
            const ret = arg0.call(arg1, arg2);
            return ret;
        }, arguments); },
        __wbg_call_6137034ef55c9d0f: function() { return handleError(function (arg0, arg1) {
            const ret = arg0.call(arg1);
            return ret;
        }, arguments); },
        __wbg_clearBuffer_3d5a3057c3c8a9bf: function(arg0, arg1, arg2, arg3) {
            arg0.clearBuffer(arg1, arg2, arg3);
        },
        __wbg_clearBuffer_82ba999c294f42fb: function(arg0, arg1, arg2) {
            arg0.clearBuffer(arg1, arg2);
        },
        __wbg_configure_1e2c1c9edad07d26: function() { return handleError(function (arg0, arg1) {
            arg0.configure(arg1);
        }, arguments); },
        __wbg_copyBufferToBuffer_01766818654a9868: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4) {
            arg0.copyBufferToBuffer(arg1, arg2, arg3, arg4);
        }, arguments); },
        __wbg_copyBufferToBuffer_9c174b96fb08d551: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5) {
            arg0.copyBufferToBuffer(arg1, arg2, arg3, arg4, arg5);
        }, arguments); },
        __wbg_copyTextureToBuffer_1234b3210431ad05: function() { return handleError(function (arg0, arg1, arg2, arg3) {
            arg0.copyTextureToBuffer(arg1, arg2, arg3);
        }, arguments); },
        __wbg_createBindGroupLayout_b1bd63b4e88459d8: function() { return handleError(function (arg0, arg1) {
            const ret = arg0.createBindGroupLayout(arg1);
            return ret;
        }, arguments); },
        __wbg_createBindGroup_f539b26ca341308f: function(arg0, arg1) {
            const ret = arg0.createBindGroup(arg1);
            return ret;
        },
        __wbg_createBuffer_d800e9b1d41b2ee5: function() { return handleError(function (arg0, arg1) {
            const ret = arg0.createBuffer(arg1);
            return ret;
        }, arguments); },
        __wbg_createCommandEncoder_3352d1ffc36c6fc0: function(arg0, arg1) {
            const ret = arg0.createCommandEncoder(arg1);
            return ret;
        },
        __wbg_createComputePipeline_224fa2618d9948a0: function(arg0, arg1) {
            const ret = arg0.createComputePipeline(arg1);
            return ret;
        },
        __wbg_createPipelineLayout_6eab52c327118937: function(arg0, arg1) {
            const ret = arg0.createPipelineLayout(arg1);
            return ret;
        },
        __wbg_createRenderPipeline_0ebb7ebc653e9207: function() { return handleError(function (arg0, arg1) {
            const ret = arg0.createRenderPipeline(arg1);
            return ret;
        }, arguments); },
        __wbg_createSampler_9bd91d7e928c0060: function(arg0, arg1) {
            const ret = arg0.createSampler(arg1);
            return ret;
        },
        __wbg_createShaderModule_cefa51336cb288ae: function(arg0, arg1) {
            const ret = arg0.createShaderModule(arg1);
            return ret;
        },
        __wbg_createTexture_ed7e9fc04dd54d84: function() { return handleError(function (arg0, arg1) {
            const ret = arg0.createTexture(arg1);
            return ret;
        }, arguments); },
        __wbg_createView_da41c2d2cb212715: function() { return handleError(function (arg0, arg1) {
            const ret = arg0.createView(arg1);
            return ret;
        }, arguments); },
        __wbg_destroy_249478e98a7943d5: function(arg0) {
            arg0.destroy();
        },
        __wbg_destroy_637537007d9eaa44: function(arg0) {
            arg0.destroy();
        },
        __wbg_dispatchWorkgroups_56b943172790add0: function(arg0, arg1, arg2, arg3) {
            arg0.dispatchWorkgroups(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0);
        },
        __wbg_document_9854e03c05fc8834: function(arg0) {
            const ret = arg0.document;
            return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
        },
        __wbg_drawIndirect_269c8a4880a070c8: function(arg0, arg1, arg2) {
            arg0.drawIndirect(arg1, arg2);
        },
        __wbg_draw_086a9578fc9898c2: function(arg0, arg1, arg2, arg3, arg4) {
            arg0.draw(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0, arg4 >>> 0);
        },
        __wbg_end_82fd0c12ba185009: function(arg0) {
            arg0.end();
        },
        __wbg_end_b57473834b877409: function(arg0) {
            arg0.end();
        },
        __wbg_error_757e9472f8410341: function(arg0, arg1) {
            let deferred0_0;
            let deferred0_1;
            try {
                deferred0_0 = arg0;
                deferred0_1 = arg1;
                console.error(getStringFromWasm0(arg0, arg1));
            } finally {
                wasm.__wbindgen_free(deferred0_0, deferred0_1, 1);
            }
        },
        __wbg_error_8c8dff942c7c4f11: function(arg0) {
            const ret = arg0.error;
            return ret;
        },
        __wbg_features_5cac120c28ba0475: function(arg0) {
            const ret = arg0.features;
            return ret;
        },
        __wbg_figgyboundedchart_new: function(arg0) {
            const ret = FiggyBoundedChart.__wrap(arg0);
            return ret;
        },
        __wbg_figgychart_new: function(arg0) {
            const ret = FiggyChart.__wrap(arg0);
            return ret;
        },
        __wbg_finish_09ec094c10f41e7b: function(arg0) {
            const ret = arg0.finish();
            return ret;
        },
        __wbg_finish_ec1c191f66a895b1: function(arg0, arg1) {
            const ret = arg0.finish(arg1);
            return ret;
        },
        __wbg_from_296ca31f8d0f1c52: function(arg0) {
            const ret = Array.from(arg0);
            return ret;
        },
        __wbg_getBindGroupLayout_349f9101ad6d4d76: function(arg0, arg1) {
            const ret = arg0.getBindGroupLayout(arg1 >>> 0);
            return ret;
        },
        __wbg_getBindGroupLayout_fb40c3b93d37f466: function(arg0, arg1) {
            const ret = arg0.getBindGroupLayout(arg1 >>> 0);
            return ret;
        },
        __wbg_getContext_635e36719cad2623: function() { return handleError(function (arg0, arg1, arg2) {
            const ret = arg0.getContext(getStringFromWasm0(arg1, arg2));
            return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
        }, arguments); },
        __wbg_getContext_e567868594d2e0c6: function() { return handleError(function (arg0, arg1, arg2) {
            const ret = arg0.getContext(getStringFromWasm0(arg1, arg2));
            return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
        }, arguments); },
        __wbg_getCurrentTexture_9f3b84d0eaa6cd95: function() { return handleError(function (arg0) {
            const ret = arg0.getCurrentTexture();
            return ret;
        }, arguments); },
        __wbg_getMappedRange_fb54c6327b2d8d20: function() { return handleError(function (arg0, arg1, arg2) {
            const ret = arg0.getMappedRange(arg1, arg2);
            return ret;
        }, arguments); },
        __wbg_getPreferredCanvasFormat_0ef5034c8902201b: function(arg0) {
            const ret = arg0.getPreferredCanvasFormat();
            return (__wbindgen_enum_GpuTextureFormat.indexOf(ret) + 1 || 102) - 1;
        },
        __wbg_get_31af05bd4842a84f: function() { return handleError(function (arg0, arg1) {
            const ret = Reflect.get(arg0, arg1);
            return ret;
        }, arguments); },
        __wbg_get_6c896e0571ddae51: function(arg0, arg1) {
            const ret = arg0[arg1 >>> 0];
            return ret;
        },
        __wbg_get_fd12a9100976c296: function(arg0, arg1) {
            const ret = arg0[arg1 >>> 0];
            return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
        },
        __wbg_get_index_161596655339f7e1: function(arg0, arg1) {
            const ret = arg0[arg1 >>> 0];
            return ret;
        },
        __wbg_get_index_f4750150bb3083b3: function(arg0, arg1) {
            const ret = arg0[arg1 >>> 0];
            return ret;
        },
        __wbg_get_unchecked_288889d017702237: function(arg0, arg1) {
            const ret = arg0[arg1 >>> 0];
            return ret;
        },
        __wbg_gpu_afdd4387c7afe5f9: function(arg0) {
            const ret = arg0.gpu;
            return ret;
        },
        __wbg_has_eafa12e457ea88fb: function(arg0, arg1, arg2) {
            const ret = arg0.has(getStringFromWasm0(arg1, arg2));
            return ret;
        },
        __wbg_height_fc97e1a0c2e7331f: function(arg0) {
            const ret = arg0.height;
            return ret;
        },
        __wbg_instanceof_Float32Array_595afb0f28b828c9: function(arg0) {
            let result;
            try {
                result = arg0 instanceof Float32Array;
            } catch (_) {
                result = false;
            }
            const ret = result;
            return ret;
        },
        __wbg_instanceof_Float64Array_8a59377f9eec1b8b: function(arg0) {
            let result;
            try {
                result = arg0 instanceof Float64Array;
            } catch (_) {
                result = false;
            }
            const ret = result;
            return ret;
        },
        __wbg_instanceof_GpuOutOfMemoryError_5c3b8a2499f59adb: function(arg0) {
            let result;
            try {
                result = arg0 instanceof GPUOutOfMemoryError;
            } catch (_) {
                result = false;
            }
            const ret = result;
            return ret;
        },
        __wbg_instanceof_GpuValidationError_7659e07b12d4e184: function(arg0) {
            let result;
            try {
                result = arg0 instanceof GPUValidationError;
            } catch (_) {
                result = false;
            }
            const ret = result;
            return ret;
        },
        __wbg_instanceof_Int16Array_dc79388a406d1748: function(arg0) {
            let result;
            try {
                result = arg0 instanceof Int16Array;
            } catch (_) {
                result = false;
            }
            const ret = result;
            return ret;
        },
        __wbg_instanceof_Int32Array_4b9a86620726269b: function(arg0) {
            let result;
            try {
                result = arg0 instanceof Int32Array;
            } catch (_) {
                result = false;
            }
            const ret = result;
            return ret;
        },
        __wbg_instanceof_Object_67a83cdc00c5d141: function(arg0) {
            let result;
            try {
                result = arg0 instanceof Object;
            } catch (_) {
                result = false;
            }
            const ret = result;
            return ret;
        },
        __wbg_instanceof_Promise_e1dc6893aa1ece28: function(arg0) {
            let result;
            try {
                result = arg0 instanceof Promise;
            } catch (_) {
                result = false;
            }
            const ret = result;
            return ret;
        },
        __wbg_instanceof_Uint16Array_eff85aa31096af44: function(arg0) {
            let result;
            try {
                result = arg0 instanceof Uint16Array;
            } catch (_) {
                result = false;
            }
            const ret = result;
            return ret;
        },
        __wbg_instanceof_Uint8Array_828cef2aaacafc31: function(arg0) {
            let result;
            try {
                result = arg0 instanceof Uint8Array;
            } catch (_) {
                result = false;
            }
            const ret = result;
            return ret;
        },
        __wbg_instanceof_Window_82d71df4eddf88bc: function(arg0) {
            let result;
            try {
                result = arg0 instanceof Window;
            } catch (_) {
                result = false;
            }
            const ret = result;
            return ret;
        },
        __wbg_isArray_e15a2ff68ffdbef2: function(arg0) {
            const ret = Array.isArray(arg0);
            return ret;
        },
        __wbg_keys_440be172f17c0265: function(arg0) {
            const ret = Object.keys(arg0);
            return ret;
        },
        __wbg_label_7add8cb37a6ef98f: function(arg0, arg1) {
            const ret = arg1.label;
            const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len1 = WASM_VECTOR_LEN;
            getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
            getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
        },
        __wbg_length_0acba72356589f9c: function(arg0) {
            const ret = arg0.length;
            return ret;
        },
        __wbg_length_3035e53132b7a991: function(arg0) {
            const ret = arg0.length;
            return ret;
        },
        __wbg_length_511b1f84719d3462: function(arg0) {
            const ret = arg0.length;
            return ret;
        },
        __wbg_length_58572db4c38f3c3e: function(arg0) {
            const ret = arg0.length;
            return ret;
        },
        __wbg_length_7f3c00c40364105e: function(arg0) {
            const ret = arg0.length;
            return ret;
        },
        __wbg_length_b5f0008bbf60cf59: function(arg0) {
            const ret = arg0.length;
            return ret;
        },
        __wbg_length_d4bdea10311bd9cf: function(arg0) {
            const ret = arg0.length;
            return ret;
        },
        __wbg_length_e5fdd54468b9e6ed: function(arg0) {
            const ret = arg0.length;
            return ret;
        },
        __wbg_limits_06bcb36c8409843b: function(arg0) {
            const ret = arg0.limits;
            return ret;
        },
        __wbg_limits_601ad2e086ef8141: function(arg0) {
            const ret = arg0.limits;
            return ret;
        },
        __wbg_lost_bb454eb62101af1a: function(arg0) {
            const ret = arg0.lost;
            return ret;
        },
        __wbg_mapAsync_b0597127f5037286: function(arg0, arg1, arg2, arg3) {
            const ret = arg0.mapAsync(arg1 >>> 0, arg2, arg3);
            return ret;
        },
        __wbg_maxBindGroupsPlusVertexBuffers_52369f089736ef9d: function(arg0) {
            const ret = arg0.maxBindGroupsPlusVertexBuffers;
            return ret;
        },
        __wbg_maxBindGroups_4e424afe6ce86ca2: function(arg0) {
            const ret = arg0.maxBindGroups;
            return ret;
        },
        __wbg_maxBindingsPerBindGroup_7d035da36821c44f: function(arg0) {
            const ret = arg0.maxBindingsPerBindGroup;
            return ret;
        },
        __wbg_maxBufferSize_423f4a084e32a195: function(arg0) {
            const ret = arg0.maxBufferSize;
            return ret;
        },
        __wbg_maxColorAttachmentBytesPerSample_c4cd9126f6d287c6: function(arg0) {
            const ret = arg0.maxColorAttachmentBytesPerSample;
            return ret;
        },
        __wbg_maxColorAttachments_d924670762b9e250: function(arg0) {
            const ret = arg0.maxColorAttachments;
            return ret;
        },
        __wbg_maxComputeInvocationsPerWorkgroup_707a3868f7cebb59: function(arg0) {
            const ret = arg0.maxComputeInvocationsPerWorkgroup;
            return ret;
        },
        __wbg_maxComputeWorkgroupSizeX_0a4d99463cbd6e5e: function(arg0) {
            const ret = arg0.maxComputeWorkgroupSizeX;
            return ret;
        },
        __wbg_maxComputeWorkgroupSizeY_85123ea0587f7558: function(arg0) {
            const ret = arg0.maxComputeWorkgroupSizeY;
            return ret;
        },
        __wbg_maxComputeWorkgroupSizeZ_a3186b4c5267d44f: function(arg0) {
            const ret = arg0.maxComputeWorkgroupSizeZ;
            return ret;
        },
        __wbg_maxComputeWorkgroupStorageSize_57b297355cfb6204: function(arg0) {
            const ret = arg0.maxComputeWorkgroupStorageSize;
            return ret;
        },
        __wbg_maxComputeWorkgroupsPerDimension_4158f95e673d54c4: function(arg0) {
            const ret = arg0.maxComputeWorkgroupsPerDimension;
            return ret;
        },
        __wbg_maxDynamicStorageBuffersPerPipelineLayout_226b0b70910aa16c: function(arg0) {
            const ret = arg0.maxDynamicStorageBuffersPerPipelineLayout;
            return ret;
        },
        __wbg_maxDynamicUniformBuffersPerPipelineLayout_0e835fda711fc7e6: function(arg0) {
            const ret = arg0.maxDynamicUniformBuffersPerPipelineLayout;
            return ret;
        },
        __wbg_maxInterStageShaderVariables_8c4a1d727e2aa35a: function(arg0) {
            const ret = arg0.maxInterStageShaderVariables;
            return ret;
        },
        __wbg_maxSampledTexturesPerShaderStage_6675f5e91d9a728a: function(arg0) {
            const ret = arg0.maxSampledTexturesPerShaderStage;
            return ret;
        },
        __wbg_maxSamplersPerShaderStage_1910fa38a6ed1e1f: function(arg0) {
            const ret = arg0.maxSamplersPerShaderStage;
            return ret;
        },
        __wbg_maxStorageBufferBindingSize_2e244bded070b18d: function(arg0) {
            const ret = arg0.maxStorageBufferBindingSize;
            return ret;
        },
        __wbg_maxStorageBuffersPerShaderStage_a285f3ebca51ca0d: function(arg0) {
            const ret = arg0.maxStorageBuffersPerShaderStage;
            return ret;
        },
        __wbg_maxStorageTexturesPerShaderStage_7aa946f0fc322a2b: function(arg0) {
            const ret = arg0.maxStorageTexturesPerShaderStage;
            return ret;
        },
        __wbg_maxTextureArrayLayers_0e699147ad00502d: function(arg0) {
            const ret = arg0.maxTextureArrayLayers;
            return ret;
        },
        __wbg_maxTextureDimension1D_aabf6add54decfe2: function(arg0) {
            const ret = arg0.maxTextureDimension1D;
            return ret;
        },
        __wbg_maxTextureDimension2D_dd598b27e9c0c1c4: function(arg0) {
            const ret = arg0.maxTextureDimension2D;
            return ret;
        },
        __wbg_maxTextureDimension3D_f944266c65dfd1a9: function(arg0) {
            const ret = arg0.maxTextureDimension3D;
            return ret;
        },
        __wbg_maxUniformBufferBindingSize_59fa6be7cfbeeb53: function(arg0) {
            const ret = arg0.maxUniformBufferBindingSize;
            return ret;
        },
        __wbg_maxUniformBuffersPerShaderStage_bee5f00a4d706c7f: function(arg0) {
            const ret = arg0.maxUniformBuffersPerShaderStage;
            return ret;
        },
        __wbg_maxVertexAttributes_5cf6392c4e9033fe: function(arg0) {
            const ret = arg0.maxVertexAttributes;
            return ret;
        },
        __wbg_maxVertexBufferArrayStride_548baa887375d865: function(arg0) {
            const ret = arg0.maxVertexBufferArrayStride;
            return ret;
        },
        __wbg_maxVertexBuffers_75d881156591f5da: function(arg0) {
            const ret = arg0.maxVertexBuffers;
            return ret;
        },
        __wbg_message_2aad50368e15e8f1: function(arg0, arg1) {
            const ret = arg1.message;
            const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len1 = WASM_VECTOR_LEN;
            getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
            getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
        },
        __wbg_message_ab4cad9eeb386607: function(arg0, arg1) {
            const ret = arg1.message;
            const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len1 = WASM_VECTOR_LEN;
            getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
            getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
        },
        __wbg_minStorageBufferOffsetAlignment_5ba9b77792bdadb3: function(arg0) {
            const ret = arg0.minStorageBufferOffsetAlignment;
            return ret;
        },
        __wbg_minUniformBufferOffsetAlignment_ab7d52a5293b22bd: function(arg0) {
            const ret = arg0.minUniformBufferOffsetAlignment;
            return ret;
        },
        __wbg_navigator_2156486643462a87: function(arg0) {
            const ret = arg0.navigator;
            return ret;
        },
        __wbg_navigator_c9bce48d4b578c9c: function(arg0) {
            const ret = arg0.navigator;
            return ret;
        },
        __wbg_new_227d7c05414eb861: function() {
            const ret = new Error();
            return ret;
        },
        __wbg_new_343a093a3c2ffb4e: function(arg0, arg1) {
            const ret = new Error(getStringFromWasm0(arg0, arg1));
            return ret;
        },
        __wbg_new_5502aad30c185fc8: function(arg0, arg1) {
            try {
                var state0 = {a: arg0, b: arg1};
                var cb0 = (arg0, arg1) => {
                    const a = state0.a;
                    state0.a = 0;
                    try {
                        return wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___js_sys_bd561c7fc2e002d3___Function_fn_wasm_bindgen_54fefb75fc756602___JsValue_____wasm_bindgen_54fefb75fc756602___sys__Undefined___js_sys_bd561c7fc2e002d3___Function_fn_wasm_bindgen_54fefb75fc756602___JsValue_____wasm_bindgen_54fefb75fc756602___sys__Undefined_______true_(a, state0.b, arg0, arg1);
                    } finally {
                        state0.a = a;
                    }
                };
                const ret = new Promise(cb0);
                return ret;
            } finally {
                state0.a = 0;
            }
        },
        __wbg_new_617a8cdb8bb1130e: function() {
            const ret = new Object();
            return ret;
        },
        __wbg_new_74cd12440f4b8e4e: function(arg0) {
            const ret = new Uint32Array(arg0);
            return ret;
        },
        __wbg_new_a217df4351db4b9b: function() { return handleError(function (arg0, arg1) {
            const ret = new OffscreenCanvas(arg0 >>> 0, arg1 >>> 0);
            return ret;
        }, arguments); },
        __wbg_new_ee2291f50781bf1d: function() {
            const ret = new Array();
            return ret;
        },
        __wbg_new_from_slice_9a868026ffa4208a: function(arg0, arg1) {
            const ret = new Uint8Array(getArrayU8FromWasm0(arg0, arg1));
            return ret;
        },
        __wbg_new_no_args_549db978c37d28cc: function(arg0, arg1) {
            const ret = new Function(getStringFromWasm0(arg0, arg1));
            return ret;
        },
        __wbg_new_typed_689a3a281a8d4da6: function() {
            const ret = new Object();
            return ret;
        },
        __wbg_new_typed_b01cb72a8af741a3: function(arg0, arg1) {
            try {
                var state0 = {a: arg0, b: arg1};
                var cb0 = (arg0, arg1) => {
                    const a = state0.a;
                    state0.a = 0;
                    try {
                        return wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___js_sys_bd561c7fc2e002d3___Function_fn_wasm_bindgen_54fefb75fc756602___JsValue_____wasm_bindgen_54fefb75fc756602___sys__Undefined___js_sys_bd561c7fc2e002d3___Function_fn_wasm_bindgen_54fefb75fc756602___JsValue_____wasm_bindgen_54fefb75fc756602___sys__Undefined_______true_(a, state0.b, arg0, arg1);
                    } finally {
                        state0.a = a;
                    }
                };
                const ret = new Promise(cb0);
                return ret;
            } finally {
                state0.a = 0;
            }
        },
        __wbg_new_with_byte_offset_and_length_2f5d7fc2a828b74d: function(arg0, arg1, arg2) {
            const ret = new Uint8Array(arg0, arg1 >>> 0, arg2 >>> 0);
            return ret;
        },
        __wbg_onSubmittedWorkDone_1190213cee1ecf7e: function(arg0) {
            const ret = arg0.onSubmittedWorkDone();
            return ret;
        },
        __wbg_parse_0fc53dead14b3b42: function() { return handleError(function (arg0, arg1) {
            const ret = JSON.parse(getStringFromWasm0(arg0, arg1));
            return ret;
        }, arguments); },
        __wbg_prototypesetcall_06eb15da165dee8f: function(arg0, arg1, arg2) {
            Uint32Array.prototype.set.call(getArrayU32FromWasm0(arg0, arg1), arg2);
        },
        __wbg_prototypesetcall_13adbfb002dee200: function(arg0, arg1, arg2) {
            Int32Array.prototype.set.call(getArrayI32FromWasm0(arg0, arg1), arg2);
        },
        __wbg_prototypesetcall_2ee09b855e324444: function(arg0, arg1, arg2) {
            Uint16Array.prototype.set.call(getArrayU16FromWasm0(arg0, arg1), arg2);
        },
        __wbg_prototypesetcall_8b03c01e2c0f8066: function(arg0, arg1, arg2) {
            Float32Array.prototype.set.call(getArrayF32FromWasm0(arg0, arg1), arg2);
        },
        __wbg_prototypesetcall_bc27214492979395: function(arg0, arg1, arg2) {
            Uint8Array.prototype.set.call(getArrayU8FromWasm0(arg0, arg1), arg2);
        },
        __wbg_prototypesetcall_d49a4fab5ca427bc: function(arg0, arg1, arg2) {
            Float64Array.prototype.set.call(getArrayF64FromWasm0(arg0, arg1), arg2);
        },
        __wbg_prototypesetcall_f8d32a400a944612: function(arg0, arg1, arg2) {
            Int16Array.prototype.set.call(getArrayI16FromWasm0(arg0, arg1), arg2);
        },
        __wbg_push_2baf45db356cf468: function(arg0, arg1) {
            const ret = arg0.push(arg1);
            return ret;
        },
        __wbg_querySelectorAll_6aebfe3df1fb2014: function() { return handleError(function (arg0, arg1, arg2) {
            const ret = arg0.querySelectorAll(getStringFromWasm0(arg1, arg2));
            return ret;
        }, arguments); },
        __wbg_queueMicrotask_9833f9a49df95a49: function(arg0) {
            const ret = arg0.queueMicrotask;
            return ret;
        },
        __wbg_queueMicrotask_a72f977e97f23c5f: function(arg0) {
            queueMicrotask(arg0);
        },
        __wbg_queue_7b62c28143d44293: function(arg0) {
            const ret = arg0.queue;
            return ret;
        },
        __wbg_reason_b4fa3af867fc4430: function(arg0) {
            const ret = arg0.reason;
            return (__wbindgen_enum_GpuDeviceLostReason.indexOf(ret) + 1 || 3) - 1;
        },
        __wbg_requestAdapter_a539af006419f2e9: function(arg0, arg1) {
            const ret = arg0.requestAdapter(arg1);
            return ret;
        },
        __wbg_requestAnimationFrame_7b526ab7aa550c74: function() { return handleError(function (arg0, arg1) {
            const ret = arg0.requestAnimationFrame(arg1);
            return ret;
        }, arguments); },
        __wbg_requestDevice_5cb8a582e55d08cb: function(arg0, arg1) {
            const ret = arg0.requestDevice(arg1);
            return ret;
        },
        __wbg_resolve_0076e10020304ede: function(arg0) {
            const ret = Promise.resolve(arg0);
            return ret;
        },
        __wbg_setBindGroup_0b7c2a055ef1f314: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6) {
            arg0.setBindGroup(arg1 >>> 0, arg2, getArrayU32FromWasm0(arg3, arg4), arg5, arg6 >>> 0);
        }, arguments); },
        __wbg_setBindGroup_11bdbb60cc8b54b9: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6) {
            arg0.setBindGroup(arg1 >>> 0, arg2, getArrayU32FromWasm0(arg3, arg4), arg5, arg6 >>> 0);
        }, arguments); },
        __wbg_setBindGroup_418c3e0eb6943ce0: function(arg0, arg1, arg2) {
            arg0.setBindGroup(arg1 >>> 0, arg2);
        },
        __wbg_setBindGroup_c83391351ce68826: function(arg0, arg1, arg2) {
            arg0.setBindGroup(arg1 >>> 0, arg2);
        },
        __wbg_setPipeline_5146f7b8d2b4af5c: function(arg0, arg1) {
            arg0.setPipeline(arg1);
        },
        __wbg_setPipeline_b6f981027e02cd16: function(arg0, arg1) {
            arg0.setPipeline(arg1);
        },
        __wbg_setScissorRect_889235eeb784732b: function(arg0, arg1, arg2, arg3, arg4) {
            arg0.setScissorRect(arg1 >>> 0, arg2 >>> 0, arg3 >>> 0, arg4 >>> 0);
        },
        __wbg_setStencilReference_48705a9a2cceae02: function(arg0, arg1) {
            arg0.setStencilReference(arg1 >>> 0);
        },
        __wbg_setVertexBuffer_6db3b60e99280744: function(arg0, arg1, arg2, arg3) {
            arg0.setVertexBuffer(arg1 >>> 0, arg2, arg3);
        },
        __wbg_setVertexBuffer_cbf4ca1627c02f4c: function(arg0, arg1, arg2, arg3, arg4) {
            arg0.setVertexBuffer(arg1 >>> 0, arg2, arg3, arg4);
        },
        __wbg_setViewport_c0be08dcc8965ccf: function(arg0, arg1, arg2, arg3, arg4, arg5, arg6) {
            arg0.setViewport(arg1, arg2, arg3, arg4, arg5, arg6);
        },
        __wbg_set_145a351398b48c65: function() { return handleError(function (arg0, arg1, arg2) {
            const ret = Reflect.set(arg0, arg1, arg2);
            return ret;
        }, arguments); },
        __wbg_set_34d08fd992d43d61: function(arg0, arg1, arg2) {
            arg0.set(arg1, arg2 >>> 0);
        },
        __wbg_set_a_82818effc94f6256: function(arg0, arg1) {
            arg0.a = arg1;
        },
        __wbg_set_access_a099cfbbeec9b96f: function(arg0, arg1) {
            arg0.access = __wbindgen_enum_GpuStorageTextureAccess[arg1];
        },
        __wbg_set_address_mode_u_a68737cf5d288f95: function(arg0, arg1) {
            arg0.addressModeU = __wbindgen_enum_GpuAddressMode[arg1];
        },
        __wbg_set_address_mode_v_b1c3c45933f540d1: function(arg0, arg1) {
            arg0.addressModeV = __wbindgen_enum_GpuAddressMode[arg1];
        },
        __wbg_set_address_mode_w_889c31cf7022c764: function(arg0, arg1) {
            arg0.addressModeW = __wbindgen_enum_GpuAddressMode[arg1];
        },
        __wbg_set_alpha_106f21a936a85eba: function(arg0, arg1) {
            arg0.alpha = arg1;
        },
        __wbg_set_alpha_mode_5544568dbac50280: function(arg0, arg1) {
            arg0.alphaMode = __wbindgen_enum_GpuCanvasAlphaMode[arg1];
        },
        __wbg_set_alpha_to_coverage_enabled_3372ce329447b8f1: function(arg0, arg1) {
            arg0.alphaToCoverageEnabled = arg1 !== 0;
        },
        __wbg_set_array_layer_count_22afa0a979e4ad55: function(arg0, arg1) {
            arg0.arrayLayerCount = arg1 >>> 0;
        },
        __wbg_set_array_stride_f64_6816040e5e7598c3: function(arg0, arg1) {
            arg0.arrayStride = arg1;
        },
        __wbg_set_aspect_a48d046965270281: function(arg0, arg1) {
            arg0.aspect = __wbindgen_enum_GpuTextureAspect[arg1];
        },
        __wbg_set_aspect_b1a9909bf315433f: function(arg0, arg1) {
            arg0.aspect = __wbindgen_enum_GpuTextureAspect[arg1];
        },
        __wbg_set_attributes_9e38cb1dde387a5b: function(arg0, arg1, arg2) {
            arg0.attributes = getArrayJsValueViewFromWasm0(arg1, arg2);
        },
        __wbg_set_b_a3297ee7e7cac3a8: function(arg0, arg1) {
            arg0.b = arg1;
        },
        __wbg_set_base_array_layer_2435ba92c80346ae: function(arg0, arg1) {
            arg0.baseArrayLayer = arg1 >>> 0;
        },
        __wbg_set_base_mip_level_8b6093e875e7c65d: function(arg0, arg1) {
            arg0.baseMipLevel = arg1 >>> 0;
        },
        __wbg_set_beginning_of_pass_write_index_e552c5e8b8bbf52f: function(arg0, arg1) {
            arg0.beginningOfPassWriteIndex = arg1 >>> 0;
        },
        __wbg_set_beginning_of_pass_write_index_fa9ae10d5d2804ce: function(arg0, arg1) {
            arg0.beginningOfPassWriteIndex = arg1 >>> 0;
        },
        __wbg_set_bind_group_layouts_458c44ba55100b82: function(arg0, arg1, arg2) {
            arg0.bindGroupLayouts = getArrayJsValueViewFromWasm0(arg1, arg2);
        },
        __wbg_set_binding_81b3fac7f7acaf8d: function(arg0, arg1) {
            arg0.binding = arg1 >>> 0;
        },
        __wbg_set_binding_b6cee57f35ac5190: function(arg0, arg1) {
            arg0.binding = arg1 >>> 0;
        },
        __wbg_set_blend_1a801617945f7945: function(arg0, arg1) {
            arg0.blend = arg1;
        },
        __wbg_set_buffer_1548ae88a9188037: function(arg0, arg1) {
            arg0.buffer = arg1;
        },
        __wbg_set_buffer_8d0ac64ad20dfc84: function(arg0, arg1) {
            arg0.buffer = arg1;
        },
        __wbg_set_buffer_910a40a90f97cfca: function(arg0, arg1) {
            arg0.buffer = arg1;
        },
        __wbg_set_buffers_5d0e0c50791f710e: function(arg0, arg1, arg2) {
            arg0.buffers = getArrayJsValueViewFromWasm0(arg1, arg2);
        },
        __wbg_set_bytes_per_row_1e824a5502b54b3d: function(arg0, arg1) {
            arg0.bytesPerRow = arg1 >>> 0;
        },
        __wbg_set_bytes_per_row_c28583f0063160f1: function(arg0, arg1) {
            arg0.bytesPerRow = arg1 >>> 0;
        },
        __wbg_set_clear_value_gpu_color_dict_a9f763e8372ac1de: function(arg0, arg1) {
            arg0.clearValue = arg1;
        },
        __wbg_set_code_5d5b0b9e2fd0dca7: function(arg0, arg1, arg2) {
            arg0.code = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_color_8ecace4011f47d2e: function(arg0, arg1) {
            arg0.color = arg1;
        },
        __wbg_set_color_attachments_622fe2d5997fda7a: function(arg0, arg1, arg2) {
            arg0.colorAttachments = getArrayJsValueViewFromWasm0(arg1, arg2);
        },
        __wbg_set_compare_080c9e492ff36990: function(arg0, arg1) {
            arg0.compare = __wbindgen_enum_GpuCompareFunction[arg1];
        },
        __wbg_set_compare_817cf3695599eaa6: function(arg0, arg1) {
            arg0.compare = __wbindgen_enum_GpuCompareFunction[arg1];
        },
        __wbg_set_compute_bc754d9e37f6e4c9: function(arg0, arg1) {
            arg0.compute = arg1;
        },
        __wbg_set_count_8ff0c9474e39a849: function(arg0, arg1) {
            arg0.count = arg1 >>> 0;
        },
        __wbg_set_cull_mode_85d2b4ab0ce3a564: function(arg0, arg1) {
            arg0.cullMode = __wbindgen_enum_GpuCullMode[arg1];
        },
        __wbg_set_depth_bias_95abf479cae3f3cd: function(arg0, arg1) {
            arg0.depthBias = arg1;
        },
        __wbg_set_depth_bias_clamp_ba3d0b8348151350: function(arg0, arg1) {
            arg0.depthBiasClamp = arg1;
        },
        __wbg_set_depth_bias_slope_scale_6b2584d93f5b9cd2: function(arg0, arg1) {
            arg0.depthBiasSlopeScale = arg1;
        },
        __wbg_set_depth_clear_value_e30a4c754c6b3b26: function(arg0, arg1) {
            arg0.depthClearValue = arg1;
        },
        __wbg_set_depth_compare_a90de4e3714397ab: function(arg0, arg1) {
            arg0.depthCompare = __wbindgen_enum_GpuCompareFunction[arg1];
        },
        __wbg_set_depth_fail_op_b5c64541d1b6b482: function(arg0, arg1) {
            arg0.depthFailOp = __wbindgen_enum_GpuStencilOperation[arg1];
        },
        __wbg_set_depth_load_op_932888016d762d3e: function(arg0, arg1) {
            arg0.depthLoadOp = __wbindgen_enum_GpuLoadOp[arg1];
        },
        __wbg_set_depth_or_array_layers_e2f074a0284e4806: function(arg0, arg1) {
            arg0.depthOrArrayLayers = arg1 >>> 0;
        },
        __wbg_set_depth_read_only_be790175a1c2db9a: function(arg0, arg1) {
            arg0.depthReadOnly = arg1 !== 0;
        },
        __wbg_set_depth_stencil_attachment_54a8922f5fbe08bf: function(arg0, arg1) {
            arg0.depthStencilAttachment = arg1;
        },
        __wbg_set_depth_stencil_b7cffc59ad4da529: function(arg0, arg1) {
            arg0.depthStencil = arg1;
        },
        __wbg_set_depth_store_op_9054814f164ab55d: function(arg0, arg1) {
            arg0.depthStoreOp = __wbindgen_enum_GpuStoreOp[arg1];
        },
        __wbg_set_depth_write_enabled_31a821ee1fb3b0b3: function(arg0, arg1) {
            arg0.depthWriteEnabled = arg1 !== 0;
        },
        __wbg_set_device_210484a77b675c9c: function(arg0, arg1) {
            arg0.device = arg1;
        },
        __wbg_set_dimension_3da9d03131a9f446: function(arg0, arg1) {
            arg0.dimension = __wbindgen_enum_GpuTextureDimension[arg1];
        },
        __wbg_set_dimension_56332450afa3e0c0: function(arg0, arg1) {
            arg0.dimension = __wbindgen_enum_GpuTextureViewDimension[arg1];
        },
        __wbg_set_dst_factor_865ba9aaf187890c: function(arg0, arg1) {
            arg0.dstFactor = __wbindgen_enum_GpuBlendFactor[arg1];
        },
        __wbg_set_end_of_pass_write_index_8f164f9e60d4ad16: function(arg0, arg1) {
            arg0.endOfPassWriteIndex = arg1 >>> 0;
        },
        __wbg_set_end_of_pass_write_index_b54a8e3802b9ae0d: function(arg0, arg1) {
            arg0.endOfPassWriteIndex = arg1 >>> 0;
        },
        __wbg_set_entries_6f866302103b81e9: function(arg0, arg1, arg2) {
            arg0.entries = getArrayJsValueViewFromWasm0(arg1, arg2);
        },
        __wbg_set_entries_f26b77ab9548e906: function(arg0, arg1, arg2) {
            arg0.entries = getArrayJsValueViewFromWasm0(arg1, arg2);
        },
        __wbg_set_entry_point_71cef95c137b5774: function(arg0, arg1, arg2) {
            arg0.entryPoint = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_entry_point_ac8db535971761fe: function(arg0, arg1, arg2) {
            arg0.entryPoint = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_entry_point_b70f98f5025a114d: function(arg0, arg1, arg2) {
            arg0.entryPoint = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_external_texture_7f966c604c4f8098: function(arg0, arg1) {
            arg0.externalTexture = arg1;
        },
        __wbg_set_fail_op_d59d0187e4111dfe: function(arg0, arg1) {
            arg0.failOp = __wbindgen_enum_GpuStencilOperation[arg1];
        },
        __wbg_set_format_23f7f32549751d43: function(arg0, arg1) {
            arg0.format = __wbindgen_enum_GpuTextureFormat[arg1];
        },
        __wbg_set_format_283dca56552f07a3: function(arg0, arg1) {
            arg0.format = __wbindgen_enum_GpuTextureFormat[arg1];
        },
        __wbg_set_format_5080a858117ad2c1: function(arg0, arg1) {
            arg0.format = __wbindgen_enum_GpuVertexFormat[arg1];
        },
        __wbg_set_format_66735b94bd868ba2: function(arg0, arg1) {
            arg0.format = __wbindgen_enum_GpuTextureFormat[arg1];
        },
        __wbg_set_format_7f2bdbfb101b1ae1: function(arg0, arg1) {
            arg0.format = __wbindgen_enum_GpuTextureFormat[arg1];
        },
        __wbg_set_format_92732ea75d3b79f5: function(arg0, arg1) {
            arg0.format = __wbindgen_enum_GpuTextureFormat[arg1];
        },
        __wbg_set_format_f009e603f7d4c28e: function(arg0, arg1) {
            arg0.format = __wbindgen_enum_GpuTextureFormat[arg1];
        },
        __wbg_set_fragment_d2b0ec97d7cf8d47: function(arg0, arg1) {
            arg0.fragment = arg1;
        },
        __wbg_set_front_face_d3f8a2e07e7b25dd: function(arg0, arg1) {
            arg0.frontFace = __wbindgen_enum_GpuFrontFace[arg1];
        },
        __wbg_set_g_b527ee8a9bed553d: function(arg0, arg1) {
            arg0.g = arg1;
        },
        __wbg_set_has_dynamic_offset_0c72ffa900c5a269: function(arg0, arg1) {
            arg0.hasDynamicOffset = arg1 !== 0;
        },
        __wbg_set_height_c9789c1c77eaedff: function(arg0, arg1) {
            arg0.height = arg1 >>> 0;
        },
        __wbg_set_height_f6619158e5735877: function(arg0, arg1) {
            arg0.height = arg1 >>> 0;
        },
        __wbg_set_height_fde391767df1ce27: function(arg0, arg1) {
            arg0.height = arg1 >>> 0;
        },
        __wbg_set_label_09e2da5f8522dbe8: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_17202740051e9722: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_17b4858e1eef23dd: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_2fefb39c0e0dbbe8: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_3cb2322e6f6db14c: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_3f2ccaafef5ff7c9: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_612add98a4398f92: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_70a09ee68d6b1b26: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_92cd3811e96b487c: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_9c2a186152427ee0: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_c3eaf136aa464cba: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_c7987704d29f284b: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_cfe64bca8945ee30: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_e02179cf97e95763: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_label_ee172cd5f6a96961: function(arg0, arg1, arg2) {
            arg0.label = getStringFromWasm0(arg1, arg2);
        },
        __wbg_set_layout_454e3a091b390cd4: function(arg0, arg1) {
            arg0.layout = arg1;
        },
        __wbg_set_layout_4b5d5b12fbb72a76: function(arg0, arg1) {
            arg0.layout = arg1;
        },
        __wbg_set_layout_75dc1ca3f2421cff: function(arg0, arg1) {
            arg0.layout = arg1;
        },
        __wbg_set_layout_gpu_auto_layout_mode_06a2b95af1043098: function(arg0, arg1) {
            arg0.layout = __wbindgen_enum_GpuAutoLayoutMode[arg1];
        },
        __wbg_set_layout_gpu_auto_layout_mode_ee432e515c357fa8: function(arg0, arg1) {
            arg0.layout = __wbindgen_enum_GpuAutoLayoutMode[arg1];
        },
        __wbg_set_load_op_c56b1269acc2d51f: function(arg0, arg1) {
            arg0.loadOp = __wbindgen_enum_GpuLoadOp[arg1];
        },
        __wbg_set_lod_max_clamp_db24179f67f3aa31: function(arg0, arg1) {
            arg0.lodMaxClamp = arg1;
        },
        __wbg_set_lod_min_clamp_2bbce566e9fefa04: function(arg0, arg1) {
            arg0.lodMinClamp = arg1;
        },
        __wbg_set_mag_filter_db8e6b42d4f8846d: function(arg0, arg1) {
            arg0.magFilter = __wbindgen_enum_GpuFilterMode[arg1];
        },
        __wbg_set_mapped_at_creation_3f320fef6761b02c: function(arg0, arg1) {
            arg0.mappedAtCreation = arg1 !== 0;
        },
        __wbg_set_mask_c1079e551ec360dc: function(arg0, arg1) {
            arg0.mask = arg1 >>> 0;
        },
        __wbg_set_max_anisotropy_84749fdcec362dc4: function(arg0, arg1) {
            arg0.maxAnisotropy = arg1;
        },
        __wbg_set_min_binding_size_f64_897e3cd4496ddec9: function(arg0, arg1) {
            arg0.minBindingSize = arg1;
        },
        __wbg_set_min_filter_d435bbfc5a637757: function(arg0, arg1) {
            arg0.minFilter = __wbindgen_enum_GpuFilterMode[arg1];
        },
        __wbg_set_mip_level_count_047936c630acee7b: function(arg0, arg1) {
            arg0.mipLevelCount = arg1 >>> 0;
        },
        __wbg_set_mip_level_count_44bc46a1ae6f6daa: function(arg0, arg1) {
            arg0.mipLevelCount = arg1 >>> 0;
        },
        __wbg_set_mip_level_f3745730372683d5: function(arg0, arg1) {
            arg0.mipLevel = arg1 >>> 0;
        },
        __wbg_set_mipmap_filter_62fb49a84b0747ff: function(arg0, arg1) {
            arg0.mipmapFilter = __wbindgen_enum_GpuMipmapFilterMode[arg1];
        },
        __wbg_set_mode_7edfbc344ef9c650: function(arg0, arg1) {
            arg0.mode = __wbindgen_enum_GpuCanvasToneMappingMode[arg1];
        },
        __wbg_set_module_392eeaa269f203b0: function(arg0, arg1) {
            arg0.module = arg1;
        },
        __wbg_set_module_715d37652c4998ec: function(arg0, arg1) {
            arg0.module = arg1;
        },
        __wbg_set_module_c9946af218d23b53: function(arg0, arg1) {
            arg0.module = arg1;
        },
        __wbg_set_multisample_ff72a7a5456cbeb7: function(arg0, arg1) {
            arg0.multisample = arg1;
        },
        __wbg_set_multisampled_039f032dc4b67367: function(arg0, arg1) {
            arg0.multisampled = arg1 !== 0;
        },
        __wbg_set_offset_f64_127e8a0aa5c5485a: function(arg0, arg1) {
            arg0.offset = arg1;
        },
        __wbg_set_offset_f64_457756429ede426d: function(arg0, arg1) {
            arg0.offset = arg1;
        },
        __wbg_set_offset_f64_a903425d5a8e5815: function(arg0, arg1) {
            arg0.offset = arg1;
        },
        __wbg_set_offset_f64_d1d115dd438165b5: function(arg0, arg1) {
            arg0.offset = arg1;
        },
        __wbg_set_onuncapturederror_bb813f1102da2296: function(arg0, arg1) {
            arg0.onuncapturederror = arg1;
        },
        __wbg_set_operation_00a77386523b88f9: function(arg0, arg1) {
            arg0.operation = __wbindgen_enum_GpuBlendOperation[arg1];
        },
        __wbg_set_origin_gpu_origin_3d_dict_0619d4860adb4eb6: function(arg0, arg1) {
            arg0.origin = arg1;
        },
        __wbg_set_pass_op_3cf10feb3d76ab97: function(arg0, arg1) {
            arg0.passOp = __wbindgen_enum_GpuStencilOperation[arg1];
        },
        __wbg_set_power_preference_b42d00a8facfbade: function(arg0, arg1) {
            arg0.powerPreference = __wbindgen_enum_GpuPowerPreference[arg1];
        },
        __wbg_set_primitive_e796cf76f0ff89f3: function(arg0, arg1) {
            arg0.primitive = arg1;
        },
        __wbg_set_query_set_f030702f1b69199f: function(arg0, arg1) {
            arg0.querySet = arg1;
        },
        __wbg_set_query_set_f9a94586851fdba2: function(arg0, arg1) {
            arg0.querySet = arg1;
        },
        __wbg_set_r_6ece4d74af63364f: function(arg0, arg1) {
            arg0.r = arg1;
        },
        __wbg_set_required_features_bbab71414c45e621: function(arg0, arg1, arg2) {
            arg0.requiredFeatures = getArrayJsValueViewFromWasm0(arg1, arg2);
        },
        __wbg_set_required_limits_837f62d865e7cfac: function(arg0, arg1) {
            arg0.requiredLimits = arg1;
        },
        __wbg_set_resolve_target_gpu_texture_view_e4c1e3bbb8c27d87: function(arg0, arg1) {
            arg0.resolveTarget = arg1;
        },
        __wbg_set_resource_8fd8658b30d86ecf: function(arg0, arg1) {
            arg0.resource = arg1;
        },
        __wbg_set_resource_gpu_buffer_binding_33099b25da65b610: function(arg0, arg1) {
            arg0.resource = arg1;
        },
        __wbg_set_resource_gpu_texture_view_4cffe7bc7c8e5cbe: function(arg0, arg1) {
            arg0.resource = arg1;
        },
        __wbg_set_rows_per_image_c6d50d227e634379: function(arg0, arg1) {
            arg0.rowsPerImage = arg1 >>> 0;
        },
        __wbg_set_rows_per_image_deb456502f23c260: function(arg0, arg1) {
            arg0.rowsPerImage = arg1 >>> 0;
        },
        __wbg_set_sample_count_481c255a12054e1d: function(arg0, arg1) {
            arg0.sampleCount = arg1 >>> 0;
        },
        __wbg_set_sample_type_ebc5fcd029513bda: function(arg0, arg1) {
            arg0.sampleType = __wbindgen_enum_GpuTextureSampleType[arg1];
        },
        __wbg_set_sampler_89cb4a7efcfc6005: function(arg0, arg1) {
            arg0.sampler = arg1;
        },
        __wbg_set_shader_location_3fb9f6a012eba494: function(arg0, arg1) {
            arg0.shaderLocation = arg1 >>> 0;
        },
        __wbg_set_size_f64_2f591b0654540477: function(arg0, arg1) {
            arg0.size = arg1;
        },
        __wbg_set_size_f64_e844c985b8f95261: function(arg0, arg1) {
            arg0.size = arg1;
        },
        __wbg_set_size_gpu_extent_3d_dict_adf57388ab1d4f18: function(arg0, arg1) {
            arg0.size = arg1;
        },
        __wbg_set_src_factor_6f2c9ec8e4d3d979: function(arg0, arg1) {
            arg0.srcFactor = __wbindgen_enum_GpuBlendFactor[arg1];
        },
        __wbg_set_stencil_back_c54d0443b8b6a957: function(arg0, arg1) {
            arg0.stencilBack = arg1;
        },
        __wbg_set_stencil_clear_value_a321b0e045bfd8c2: function(arg0, arg1) {
            arg0.stencilClearValue = arg1 >>> 0;
        },
        __wbg_set_stencil_front_3ff3f8385852efff: function(arg0, arg1) {
            arg0.stencilFront = arg1;
        },
        __wbg_set_stencil_load_op_37d20deccb26a0f1: function(arg0, arg1) {
            arg0.stencilLoadOp = __wbindgen_enum_GpuLoadOp[arg1];
        },
        __wbg_set_stencil_read_mask_021ef4271b24352c: function(arg0, arg1) {
            arg0.stencilReadMask = arg1 >>> 0;
        },
        __wbg_set_stencil_read_only_75fe66a2356d6e92: function(arg0, arg1) {
            arg0.stencilReadOnly = arg1 !== 0;
        },
        __wbg_set_stencil_store_op_501f91638dd386e6: function(arg0, arg1) {
            arg0.stencilStoreOp = __wbindgen_enum_GpuStoreOp[arg1];
        },
        __wbg_set_stencil_write_mask_ec1c12237e094bdd: function(arg0, arg1) {
            arg0.stencilWriteMask = arg1 >>> 0;
        },
        __wbg_set_step_mode_3cbbdeba1e5dfd62: function(arg0, arg1) {
            arg0.stepMode = __wbindgen_enum_GpuVertexStepMode[arg1];
        },
        __wbg_set_storage_texture_786aea7c5773b6c1: function(arg0, arg1) {
            arg0.storageTexture = arg1;
        },
        __wbg_set_store_op_678f33376d741711: function(arg0, arg1) {
            arg0.storeOp = __wbindgen_enum_GpuStoreOp[arg1];
        },
        __wbg_set_strip_index_format_70313df755145d5e: function(arg0, arg1) {
            arg0.stripIndexFormat = __wbindgen_enum_GpuIndexFormat[arg1];
        },
        __wbg_set_targets_674b33931e512fb1: function(arg0, arg1, arg2) {
            arg0.targets = getArrayJsValueViewFromWasm0(arg1, arg2);
        },
        __wbg_set_texture_95f2bfdf7767e76f: function(arg0, arg1) {
            arg0.texture = arg1;
        },
        __wbg_set_texture_a33be3fe02ac6264: function(arg0, arg1) {
            arg0.texture = arg1;
        },
        __wbg_set_timestamp_writes_5f240bbaad97fcaf: function(arg0, arg1) {
            arg0.timestampWrites = arg1;
        },
        __wbg_set_timestamp_writes_de6a09f299b71b76: function(arg0, arg1) {
            arg0.timestampWrites = arg1;
        },
        __wbg_set_tone_mapping_320c1aad31db2e7f: function(arg0, arg1) {
            arg0.toneMapping = arg1;
        },
        __wbg_set_topology_b92cfe523bd9653b: function(arg0, arg1) {
            arg0.topology = __wbindgen_enum_GpuPrimitiveTopology[arg1];
        },
        __wbg_set_type_43e0092f16775979: function(arg0, arg1) {
            arg0.type = __wbindgen_enum_GpuSamplerBindingType[arg1];
        },
        __wbg_set_type_79cec55caf4cdb6d: function(arg0, arg1) {
            arg0.type = __wbindgen_enum_GpuBufferBindingType[arg1];
        },
        __wbg_set_unclipped_depth_32b7caf29fa5633d: function(arg0, arg1) {
            arg0.unclippedDepth = arg1 !== 0;
        },
        __wbg_set_usage_1ee33d98267e787d: function(arg0, arg1) {
            arg0.usage = arg1 >>> 0;
        },
        __wbg_set_usage_2365e2704b1fdb10: function(arg0, arg1) {
            arg0.usage = arg1 >>> 0;
        },
        __wbg_set_usage_d53ee6f0c7aedbfa: function(arg0, arg1) {
            arg0.usage = arg1 >>> 0;
        },
        __wbg_set_usage_f3e34822998d2147: function(arg0, arg1) {
            arg0.usage = arg1 >>> 0;
        },
        __wbg_set_vertex_77ed7a1229239b5a: function(arg0, arg1) {
            arg0.vertex = arg1;
        },
        __wbg_set_view_dimension_893e2d16561e56e8: function(arg0, arg1) {
            arg0.viewDimension = __wbindgen_enum_GpuTextureViewDimension[arg1];
        },
        __wbg_set_view_dimension_f2c5fe4bf927c3fe: function(arg0, arg1) {
            arg0.viewDimension = __wbindgen_enum_GpuTextureViewDimension[arg1];
        },
        __wbg_set_view_formats_427069064d8b7139: function(arg0, arg1, arg2) {
            arg0.viewFormats = getArrayJsValueViewFromWasm0(arg1, arg2);
        },
        __wbg_set_view_formats_9c2f01a6f3b365c7: function(arg0, arg1, arg2) {
            arg0.viewFormats = getArrayJsValueViewFromWasm0(arg1, arg2);
        },
        __wbg_set_view_gpu_texture_view_35f4655788535c4d: function(arg0, arg1) {
            arg0.view = arg1;
        },
        __wbg_set_view_gpu_texture_view_a532c825c52042c0: function(arg0, arg1) {
            arg0.view = arg1;
        },
        __wbg_set_visibility_d8a6821789538c25: function(arg0, arg1) {
            arg0.visibility = arg1 >>> 0;
        },
        __wbg_set_width_0ca908d167690992: function(arg0, arg1) {
            arg0.width = arg1 >>> 0;
        },
        __wbg_set_width_b0e1267db4b196b5: function(arg0, arg1) {
            arg0.width = arg1 >>> 0;
        },
        __wbg_set_width_b20525f5f4df4eb8: function(arg0, arg1) {
            arg0.width = arg1 >>> 0;
        },
        __wbg_set_write_mask_42d89f182ade6b2d: function(arg0, arg1) {
            arg0.writeMask = arg1 >>> 0;
        },
        __wbg_set_x_f470b03dd54724cd: function(arg0, arg1) {
            arg0.x = arg1 >>> 0;
        },
        __wbg_set_y_4c44eb40ebca5bfc: function(arg0, arg1) {
            arg0.y = arg1 >>> 0;
        },
        __wbg_set_z_2e6820ef0f5821ed: function(arg0, arg1) {
            arg0.z = arg1 >>> 0;
        },
        __wbg_stack_3b0d974bbf31e44f: function(arg0, arg1) {
            const ret = arg1.stack;
            const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len1 = WASM_VECTOR_LEN;
            getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
            getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
        },
        __wbg_static_accessor_GLOBAL_266715b9d96ba635: function() {
            const ret = typeof global === 'undefined' ? null : global;
            return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
        },
        __wbg_static_accessor_GLOBAL_THIS_10fb7dc1ae063179: function() {
            const ret = typeof globalThis === 'undefined' ? null : globalThis;
            return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
        },
        __wbg_static_accessor_SELF_0b583911f537483a: function() {
            const ret = typeof self === 'undefined' ? null : self;
            return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
        },
        __wbg_static_accessor_WINDOW_d7f903d1508cbdc4: function() {
            const ret = typeof window === 'undefined' ? null : window;
            return isLikeNone(ret) ? 0 : addToExternrefTable0(ret);
        },
        __wbg_stringify_52ff602c1cc4fbb6: function() { return handleError(function (arg0) {
            const ret = JSON.stringify(arg0);
            return ret;
        }, arguments); },
        __wbg_subarray_002b94d5e13d1411: function(arg0, arg1, arg2) {
            const ret = arg0.subarray(arg1 >>> 0, arg2 >>> 0);
            return ret;
        },
        __wbg_subarray_054dd444c5222d66: function(arg0, arg1, arg2) {
            const ret = arg0.subarray(arg1 >>> 0, arg2 >>> 0);
            return ret;
        },
        __wbg_subarray_7c5c40a247c2bfd6: function(arg0, arg1, arg2) {
            const ret = arg0.subarray(arg1 >>> 0, arg2 >>> 0);
            return ret;
        },
        __wbg_subarray_8a56c92643c071e0: function(arg0, arg1, arg2) {
            const ret = arg0.subarray(arg1 >>> 0, arg2 >>> 0);
            return ret;
        },
        __wbg_subarray_945e4188b94230e0: function(arg0, arg1, arg2) {
            const ret = arg0.subarray(arg1 >>> 0, arg2 >>> 0);
            return ret;
        },
        __wbg_subarray_bc806d0bca615ffa: function(arg0, arg1, arg2) {
            const ret = arg0.subarray(arg1 >>> 0, arg2 >>> 0);
            return ret;
        },
        __wbg_submit_077c85cc28e36892: function(arg0, arg1, arg2) {
            arg0.submit(getArrayJsValueViewFromWasm0(arg1, arg2));
        },
        __wbg_then_c8a35d4ad59c6b8e: function(arg0, arg1) {
            const ret = arg0.then(arg1);
            return ret;
        },
        __wbg_then_c949d5a25a4e78f8: function(arg0, arg1, arg2) {
            const ret = arg0.then(arg1, arg2);
            return ret;
        },
        __wbg_then_e71170d78fcf8954: function(arg0, arg1) {
            const ret = arg0.then(arg1);
            return ret;
        },
        __wbg_unconfigure_835307f58dc68d80: function(arg0) {
            arg0.unconfigure();
        },
        __wbg_unmap_6a96b14c9ef5f7f5: function(arg0) {
            arg0.unmap();
        },
        __wbg_valueOf_02fd4d101b7553c7: function(arg0) {
            const ret = arg0.valueOf();
            return ret;
        },
        __wbg_width_3d0dce3d9892e35e: function(arg0) {
            const ret = arg0.width;
            return ret;
        },
        __wbg_writeBuffer_f4bb3f54adfe1330: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5, arg6) {
            arg0.writeBuffer(arg1, arg2, getArrayU8FromWasm0(arg3, arg4), arg5, arg6);
        }, arguments); },
        __wbg_writeTexture_30e592e8c061c3d9: function() { return handleError(function (arg0, arg1, arg2, arg3, arg4, arg5) {
            arg0.writeTexture(arg1, getArrayU8FromWasm0(arg2, arg3), arg4, arg5);
        }, arguments); },
        __wbindgen_generic_0000000000000001: function(arg0, arg1) {
            // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [Externref], shim_idx: 1207, ret: Unit, inner_ret: Some(Unit) }, mutable: true }) -> Externref`.
            const ret = makeMutClosure(arg0, arg1, wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___JsValue______true_);
            return ret;
        },
        __wbindgen_generic_0000000000000002: function(arg0, arg1) {
            // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [Externref], shim_idx: 1677, ret: Result(Unit), inner_ret: Some(Result(Unit)) }, mutable: true }) -> Externref`.
            const ret = makeMutClosure(arg0, arg1, wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___JsValue__core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true_);
            return ret;
        },
        __wbindgen_generic_0000000000000003: function(arg0, arg1) {
            // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("GPUDevice")], shim_idx: 1625, ret: Result(Unit), inner_ret: Some(Result(Unit)) }, mutable: true }) -> Externref`.
            const ret = makeMutClosure(arg0, arg1, wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___sys__JsNullable_wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true_);
            return ret;
        },
        __wbindgen_generic_0000000000000004: function(arg0, arg1) {
            // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("GPUDeviceLostInfo")], shim_idx: 1630, ret: Unit, inner_ret: Some(Unit) }, mutable: true }) -> Externref`.
            const ret = makeMutClosure(arg0, arg1, wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuDeviceLostInfo__GpuDeviceLostInfo______true_);
            return ret;
        },
        __wbindgen_generic_0000000000000005: function(arg0, arg1) {
            // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("GPUUncapturedErrorEvent")], shim_idx: 1630, ret: Unit, inner_ret: Some(Unit) }, mutable: true }) -> Externref`.
            const ret = makeMutClosure(arg0, arg1, wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuDeviceLostInfo__GpuDeviceLostInfo______true__243);
            return ret;
        },
        __wbindgen_generic_0000000000000006: function(arg0, arg1) {
            // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("any")], shim_idx: 1625, ret: Result(Unit), inner_ret: Some(Result(Unit)) }, mutable: true }) -> Externref`.
            const ret = makeMutClosure(arg0, arg1, wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___sys__JsNullable_wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true__244);
            return ret;
        },
        __wbindgen_generic_0000000000000007: function(arg0, arg1) {
            // Cast intrinsic for `Closure(Closure { owned: true, function: Function { arguments: [NamedExternref("undefined")], shim_idx: 1625, ret: Result(Unit), inner_ret: Some(Result(Unit)) }, mutable: true }) -> Externref`.
            const ret = makeMutClosure(arg0, arg1, wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___sys__JsNullable_wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true__245);
            return ret;
        },
        __wbindgen_generic_0000000000000008: function(arg0) {
            // Cast intrinsic for `F64 -> Externref`.
            const ret = arg0;
            return ret;
        },
        __wbindgen_generic_0000000000000009: function(arg0, arg1) {
            // Cast intrinsic for `Ref(Slice(U8)) -> NamedExternref("Uint8Array")`.
            const ret = getArrayU8FromWasm0(arg0, arg1);
            return ret;
        },
        __wbindgen_generic_000000000000000a: function(arg0, arg1) {
            // Cast intrinsic for `Ref(String) -> Externref`.
            const ret = getStringFromWasm0(arg0, arg1);
            return ret;
        },
        __wbindgen_init_externref_table: function() {
            const table = wasm.__wbindgen_externrefs;
            const offset = table.grow(4);
            table.set(0, undefined);
            table.set(offset + 0, undefined);
            table.set(offset + 1, null);
            table.set(offset + 2, true);
            table.set(offset + 3, false);
        },
    };
    return {
        __proto__: null,
        "./figgy_bg.js": import0,
    };
}

function wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___JsValue______true_(arg0, arg1, arg2) {
    wasm.wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___JsValue______true_(arg0, arg1, arg2);
}

function wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuDeviceLostInfo__GpuDeviceLostInfo______true_(arg0, arg1, arg2) {
    wasm.wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuDeviceLostInfo__GpuDeviceLostInfo______true_(arg0, arg1, arg2);
}

function wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuDeviceLostInfo__GpuDeviceLostInfo______true__243(arg0, arg1, arg2) {
    wasm.wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuDeviceLostInfo__GpuDeviceLostInfo______true__243(arg0, arg1, arg2);
}

function wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___JsValue__core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true_(arg0, arg1, arg2) {
    const ret = wasm.wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___JsValue__core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true_(arg0, arg1, arg2);
    if (ret[1]) {
        throw takeFromExternrefTable0(ret[0]);
    }
}

function wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___sys__JsNullable_wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true_(arg0, arg1, arg2) {
    const ret = wasm.wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___sys__JsNullable_wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true_(arg0, arg1, arg2);
    if (ret[1]) {
        throw takeFromExternrefTable0(ret[0]);
    }
}

function wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___sys__JsNullable_wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true__244(arg0, arg1, arg2) {
    const ret = wasm.wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___sys__JsNullable_wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true__244(arg0, arg1, arg2);
    if (ret[1]) {
        throw takeFromExternrefTable0(ret[0]);
    }
}

function wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___sys__JsNullable_wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true__245(arg0, arg1, arg2) {
    const ret = wasm.wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___wasm_bindgen_54fefb75fc756602___sys__JsNullable_wgpu_385621373fd3597f___backend__webgpu__webgpu_sys__gen_GpuError__GpuError___core_608f92abc48d28da___result__Result_____wasm_bindgen_54fefb75fc756602___JsError___true__245(arg0, arg1, arg2);
    if (ret[1]) {
        throw takeFromExternrefTable0(ret[0]);
    }
}

function wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___js_sys_bd561c7fc2e002d3___Function_fn_wasm_bindgen_54fefb75fc756602___JsValue_____wasm_bindgen_54fefb75fc756602___sys__Undefined___js_sys_bd561c7fc2e002d3___Function_fn_wasm_bindgen_54fefb75fc756602___JsValue_____wasm_bindgen_54fefb75fc756602___sys__Undefined_______true_(arg0, arg1, arg2, arg3) {
    wasm.wasm_bindgen_54fefb75fc756602___convert__closures_____invoke___js_sys_bd561c7fc2e002d3___Function_fn_wasm_bindgen_54fefb75fc756602___JsValue_____wasm_bindgen_54fefb75fc756602___sys__Undefined___js_sys_bd561c7fc2e002d3___Function_fn_wasm_bindgen_54fefb75fc756602___JsValue_____wasm_bindgen_54fefb75fc756602___sys__Undefined_______true_(arg0, arg1, arg2, arg3);
}


const __wbindgen_enum_GpuAddressMode = ["clamp-to-edge", "repeat", "mirror-repeat"];


const __wbindgen_enum_GpuAutoLayoutMode = ["auto"];


const __wbindgen_enum_GpuBlendFactor = ["zero", "one", "src", "one-minus-src", "src-alpha", "one-minus-src-alpha", "dst", "one-minus-dst", "dst-alpha", "one-minus-dst-alpha", "src-alpha-saturated", "constant", "one-minus-constant", "src1", "one-minus-src1", "src1-alpha", "one-minus-src1-alpha"];


const __wbindgen_enum_GpuBlendOperation = ["add", "subtract", "reverse-subtract", "min", "max"];


const __wbindgen_enum_GpuBufferBindingType = ["uniform", "storage", "read-only-storage"];


const __wbindgen_enum_GpuCanvasAlphaMode = ["opaque", "premultiplied"];


const __wbindgen_enum_GpuCanvasToneMappingMode = ["standard", "extended"];


const __wbindgen_enum_GpuCompareFunction = ["never", "less", "equal", "less-equal", "greater", "not-equal", "greater-equal", "always"];


const __wbindgen_enum_GpuCullMode = ["none", "front", "back"];


const __wbindgen_enum_GpuDeviceLostReason = ["unknown", "destroyed"];


const __wbindgen_enum_GpuFilterMode = ["nearest", "linear"];


const __wbindgen_enum_GpuFrontFace = ["ccw", "cw"];


const __wbindgen_enum_GpuIndexFormat = ["uint16", "uint32"];


const __wbindgen_enum_GpuLoadOp = ["load", "clear"];


const __wbindgen_enum_GpuMipmapFilterMode = ["nearest", "linear"];


const __wbindgen_enum_GpuPowerPreference = ["low-power", "high-performance"];


const __wbindgen_enum_GpuPrimitiveTopology = ["point-list", "line-list", "line-strip", "triangle-list", "triangle-strip"];


const __wbindgen_enum_GpuSamplerBindingType = ["filtering", "non-filtering", "comparison"];


const __wbindgen_enum_GpuStencilOperation = ["keep", "zero", "replace", "invert", "increment-clamp", "decrement-clamp", "increment-wrap", "decrement-wrap"];


const __wbindgen_enum_GpuStorageTextureAccess = ["write-only", "read-only", "read-write"];


const __wbindgen_enum_GpuStoreOp = ["store", "discard"];


const __wbindgen_enum_GpuTextureAspect = ["all", "stencil-only", "depth-only"];


const __wbindgen_enum_GpuTextureDimension = ["1d", "2d", "3d"];


const __wbindgen_enum_GpuTextureFormat = ["r8unorm", "r8snorm", "r8uint", "r8sint", "r16unorm", "r16snorm", "r16uint", "r16sint", "r16float", "rg8unorm", "rg8snorm", "rg8uint", "rg8sint", "r32uint", "r32sint", "r32float", "rg16unorm", "rg16snorm", "rg16uint", "rg16sint", "rg16float", "rgba8unorm", "rgba8unorm-srgb", "rgba8snorm", "rgba8uint", "rgba8sint", "bgra8unorm", "bgra8unorm-srgb", "rgb9e5ufloat", "rgb10a2uint", "rgb10a2unorm", "rg11b10ufloat", "rg32uint", "rg32sint", "rg32float", "rgba16unorm", "rgba16snorm", "rgba16uint", "rgba16sint", "rgba16float", "rgba32uint", "rgba32sint", "rgba32float", "stencil8", "depth16unorm", "depth24plus", "depth24plus-stencil8", "depth32float", "depth32float-stencil8", "bc1-rgba-unorm", "bc1-rgba-unorm-srgb", "bc2-rgba-unorm", "bc2-rgba-unorm-srgb", "bc3-rgba-unorm", "bc3-rgba-unorm-srgb", "bc4-r-unorm", "bc4-r-snorm", "bc5-rg-unorm", "bc5-rg-snorm", "bc6h-rgb-ufloat", "bc6h-rgb-float", "bc7-rgba-unorm", "bc7-rgba-unorm-srgb", "etc2-rgb8unorm", "etc2-rgb8unorm-srgb", "etc2-rgb8a1unorm", "etc2-rgb8a1unorm-srgb", "etc2-rgba8unorm", "etc2-rgba8unorm-srgb", "eac-r11unorm", "eac-r11snorm", "eac-rg11unorm", "eac-rg11snorm", "astc-4x4-unorm", "astc-4x4-unorm-srgb", "astc-5x4-unorm", "astc-5x4-unorm-srgb", "astc-5x5-unorm", "astc-5x5-unorm-srgb", "astc-6x5-unorm", "astc-6x5-unorm-srgb", "astc-6x6-unorm", "astc-6x6-unorm-srgb", "astc-8x5-unorm", "astc-8x5-unorm-srgb", "astc-8x6-unorm", "astc-8x6-unorm-srgb", "astc-8x8-unorm", "astc-8x8-unorm-srgb", "astc-10x5-unorm", "astc-10x5-unorm-srgb", "astc-10x6-unorm", "astc-10x6-unorm-srgb", "astc-10x8-unorm", "astc-10x8-unorm-srgb", "astc-10x10-unorm", "astc-10x10-unorm-srgb", "astc-12x10-unorm", "astc-12x10-unorm-srgb", "astc-12x12-unorm", "astc-12x12-unorm-srgb"];


const __wbindgen_enum_GpuTextureSampleType = ["float", "unfilterable-float", "depth", "sint", "uint"];


const __wbindgen_enum_GpuTextureViewDimension = ["1d", "2d", "2d-array", "cube", "cube-array", "3d"];


const __wbindgen_enum_GpuVertexFormat = ["uint8", "uint8x2", "uint8x4", "sint8", "sint8x2", "sint8x4", "unorm8", "unorm8x2", "unorm8x4", "snorm8", "snorm8x2", "snorm8x4", "uint16", "uint16x2", "uint16x4", "sint16", "sint16x2", "sint16x4", "unorm16", "unorm16x2", "unorm16x4", "snorm16", "snorm16x2", "snorm16x4", "float16", "float16x2", "float16x4", "float32", "float32x2", "float32x3", "float32x4", "uint32", "uint32x2", "uint32x3", "uint32x4", "sint32", "sint32x2", "sint32x3", "sint32x4", "unorm10-10-10-2", "unorm8x4-bgra"];


const __wbindgen_enum_GpuVertexStepMode = ["vertex", "instance"];
const AutoStreamingRangeRequestResultFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_autostreamingrangerequestresult_free(ptr, 1));
const AutoStreamingRequestResultFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_autostreamingrequestresult_free(ptr, 1));
const FiggyBoundedChartFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_figgyboundedchart_free(ptr, 1));
const FiggyChartFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_figgychart_free(ptr, 1));
const StreamingOperationHandleFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_streamingoperationhandle_free(ptr, 1));
const StreamingStepResultFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_streamingstepresult_free(ptr, 1));
const StreamingUsageResultFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_streamingusageresult_free(ptr, 1));

function addToExternrefTable0(obj) {
    const idx = wasm.__externref_table_alloc();
    wasm.__wbindgen_externrefs.set(idx, obj);
    return idx;
}

function _assertClass(instance, klass) {
    if (!(instance instanceof klass)) {
        throw new Error(`expected instance of ${klass.name}`);
    }
}

const CLOSURE_DTORS = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(state => wasm.__wbindgen_destroy_closure(state.a, state.b));

function debugString(val) {
    // primitive types
    const type = typeof val;
    if (type == 'number' || type == 'boolean' || val == null) {
        return  `${val}`;
    }
    if (type == 'string') {
        return `"${val}"`;
    }
    if (type == 'symbol') {
        const description = val.description;
        if (description == null) {
            return 'Symbol';
        } else {
            return `Symbol(${description})`;
        }
    }
    if (type == 'function') {
        const name = val.name;
        if (typeof name == 'string' && name.length > 0) {
            return `Function(${name})`;
        } else {
            return 'Function';
        }
    }
    // objects
    if (Array.isArray(val)) {
        const length = val.length;
        let debug = '[';
        if (length > 0) {
            debug += debugString(val[0]);
        }
        for(let i = 1; i < length; i++) {
            debug += ', ' + debugString(val[i]);
        }
        debug += ']';
        return debug;
    }
    // Test for built-in
    const builtInMatches = /\[object ([^\]]+)\]/.exec(toString.call(val));
    let className;
    if (builtInMatches && builtInMatches.length > 1) {
        className = builtInMatches[1];
    } else {
        // Failed to match the standard '[object ClassName]'
        return toString.call(val);
    }
    if (className == 'Object') {
        // we're a user defined class or Object
        // JSON.stringify avoids problems with cycles, and is generally much
        // easier than looping through ownProperties of `val`.
        try {
            return 'Object(' + JSON.stringify(val) + ')';
        } catch (_) {
            return 'Object';
        }
    }
    // errors
    if (val instanceof Error) {
        return `${val.name}: ${val.message}\n${val.stack}`;
    }
    // TODO we could test for more things here, like `Set`s and `Map`s.
    return className;
}

function getArrayF32FromWasm0(ptr, len) {
    ptr = ptr >>> 0;
    return getFloat32ArrayMemory0().subarray(ptr / 4, ptr / 4 + len);
}

function getArrayF64FromWasm0(ptr, len) {
    ptr = ptr >>> 0;
    return getFloat64ArrayMemory0().subarray(ptr / 8, ptr / 8 + len);
}

function getArrayI16FromWasm0(ptr, len) {
    ptr = ptr >>> 0;
    return getInt16ArrayMemory0().subarray(ptr / 2, ptr / 2 + len);
}

function getArrayI32FromWasm0(ptr, len) {
    ptr = ptr >>> 0;
    return getInt32ArrayMemory0().subarray(ptr / 4, ptr / 4 + len);
}

function getArrayJsValueFromWasm0(ptr, len) {
    ptr = ptr >>> 0;
    const mem = getDataViewMemory0();
    const result = [];
    for (let i = ptr; i < ptr + 4 * len; i += 4) {
        result.push(wasm.__wbindgen_externrefs.get(mem.getUint32(i, true)));
    }
    wasm.__externref_drop_slice(ptr, len);
    return result;
}

function getArrayJsValueViewFromWasm0(ptr, len) {
    ptr = ptr >>> 0;
    const mem = getDataViewMemory0();
    const result = [];
    for (let i = ptr; i < ptr + 4 * len; i += 4) {
        result.push(wasm.__wbindgen_externrefs.get(mem.getUint32(i, true)));
    }
    return result;
}

function getArrayU16FromWasm0(ptr, len) {
    ptr = ptr >>> 0;
    return getUint16ArrayMemory0().subarray(ptr / 2, ptr / 2 + len);
}

function getArrayU32FromWasm0(ptr, len) {
    ptr = ptr >>> 0;
    return getUint32ArrayMemory0().subarray(ptr / 4, ptr / 4 + len);
}

function getArrayU8FromWasm0(ptr, len) {
    ptr = ptr >>> 0;
    return getUint8ArrayMemory0().subarray(ptr / 1, ptr / 1 + len);
}

let cachedDataViewMemory0 = null;
function getDataViewMemory0() {
    if (cachedDataViewMemory0 === null || cachedDataViewMemory0.buffer.detached === true || (cachedDataViewMemory0.buffer.detached === undefined && cachedDataViewMemory0.buffer !== wasm.memory.buffer)) {
        cachedDataViewMemory0 = new DataView(wasm.memory.buffer);
    }
    return cachedDataViewMemory0;
}

let cachedFloat32ArrayMemory0 = null;
function getFloat32ArrayMemory0() {
    if (cachedFloat32ArrayMemory0 === null || cachedFloat32ArrayMemory0.byteLength === 0) {
        cachedFloat32ArrayMemory0 = new Float32Array(wasm.memory.buffer);
    }
    return cachedFloat32ArrayMemory0;
}

let cachedFloat64ArrayMemory0 = null;
function getFloat64ArrayMemory0() {
    if (cachedFloat64ArrayMemory0 === null || cachedFloat64ArrayMemory0.byteLength === 0) {
        cachedFloat64ArrayMemory0 = new Float64Array(wasm.memory.buffer);
    }
    return cachedFloat64ArrayMemory0;
}

let cachedInt16ArrayMemory0 = null;
function getInt16ArrayMemory0() {
    if (cachedInt16ArrayMemory0 === null || cachedInt16ArrayMemory0.byteLength === 0) {
        cachedInt16ArrayMemory0 = new Int16Array(wasm.memory.buffer);
    }
    return cachedInt16ArrayMemory0;
}

let cachedInt32ArrayMemory0 = null;
function getInt32ArrayMemory0() {
    if (cachedInt32ArrayMemory0 === null || cachedInt32ArrayMemory0.byteLength === 0) {
        cachedInt32ArrayMemory0 = new Int32Array(wasm.memory.buffer);
    }
    return cachedInt32ArrayMemory0;
}

function getStringFromWasm0(ptr, len) {
    return decodeText(ptr >>> 0, len);
}

let cachedUint16ArrayMemory0 = null;
function getUint16ArrayMemory0() {
    if (cachedUint16ArrayMemory0 === null || cachedUint16ArrayMemory0.byteLength === 0) {
        cachedUint16ArrayMemory0 = new Uint16Array(wasm.memory.buffer);
    }
    return cachedUint16ArrayMemory0;
}

let cachedUint32ArrayMemory0 = null;
function getUint32ArrayMemory0() {
    if (cachedUint32ArrayMemory0 === null || cachedUint32ArrayMemory0.byteLength === 0) {
        cachedUint32ArrayMemory0 = new Uint32Array(wasm.memory.buffer);
    }
    return cachedUint32ArrayMemory0;
}

let cachedUint8ArrayMemory0 = null;
function getUint8ArrayMemory0() {
    if (cachedUint8ArrayMemory0 === null || cachedUint8ArrayMemory0.byteLength === 0) {
        cachedUint8ArrayMemory0 = new Uint8Array(wasm.memory.buffer);
    }
    return cachedUint8ArrayMemory0;
}

function handleError(f, args) {
    try {
        return f.apply(this, args);
    } catch (e) {
        const idx = addToExternrefTable0(e);
        wasm.__wbindgen_exn_store(idx);
    }
}

function isLikeNone(x) {
    return x === undefined || x === null;
}

function makeMutClosure(arg0, arg1, f) {
    const state = { a: arg0, b: arg1, cnt: 1 };
    const real = (...args) => {

        // First up with a closure we increment the internal reference
        // count. This ensures that the Rust closure environment won't
        // be deallocated while we're invoking it.
        state.cnt++;
        const a = state.a;
        state.a = 0;
        try {
            return f(a, state.b, ...args);
        } finally {
            state.a = a;
            real._wbg_cb_unref();
        }
    };
    real._wbg_cb_unref = () => {
        if (--state.cnt === 0) {
            wasm.__wbindgen_destroy_closure(state.a, state.b);
            state.a = 0;
            CLOSURE_DTORS.unregister(state);
        }
    };
    CLOSURE_DTORS.register(real, state, state);
    return real;
}

function passArray32ToWasm0(arg, malloc) {
    const ptr = malloc(arg.length * 4, 4) >>> 0;
    getUint32ArrayMemory0().set(arg, ptr / 4);
    WASM_VECTOR_LEN = arg.length;
    return ptr;
}

function passArray8ToWasm0(arg, malloc) {
    const ptr = malloc(arg.length * 1, 1) >>> 0;
    getUint8ArrayMemory0().set(arg, ptr / 1);
    WASM_VECTOR_LEN = arg.length;
    return ptr;
}

function passArrayF32ToWasm0(arg, malloc) {
    const ptr = malloc(arg.length * 4, 4) >>> 0;
    getFloat32ArrayMemory0().set(arg, ptr / 4);
    WASM_VECTOR_LEN = arg.length;
    return ptr;
}

function passArrayF64ToWasm0(arg, malloc) {
    const ptr = malloc(arg.length * 8, 8) >>> 0;
    getFloat64ArrayMemory0().set(arg, ptr / 8);
    WASM_VECTOR_LEN = arg.length;
    return ptr;
}

function passArrayJsValueToWasm0(array, malloc) {
    const ptr = malloc(array.length * 4, 4) >>> 0;
    for (let i = 0; i < array.length; i++) {
        const add = addToExternrefTable0(array[i]);
        getDataViewMemory0().setUint32(ptr + 4 * i, add, true);
    }
    WASM_VECTOR_LEN = array.length;
    return ptr;
}

function passStringToWasm0(arg, malloc, realloc) {
    if (realloc === undefined) {
        const buf = cachedTextEncoder.encode(arg);
        const ptr = malloc(buf.length, 1) >>> 0;
        getUint8ArrayMemory0().subarray(ptr, ptr + buf.length).set(buf);
        WASM_VECTOR_LEN = buf.length;
        return ptr;
    }

    let len = arg.length;
    let ptr = malloc(len, 1) >>> 0;

    const mem = getUint8ArrayMemory0();

    let offset = 0;

    for (; offset < len; offset++) {
        const code = arg.charCodeAt(offset);
        if (code > 0x7F) break;
        mem[ptr + offset] = code;
    }
    if (offset !== len) {
        if (offset !== 0) {
            arg = arg.slice(offset);
        }
        ptr = realloc(ptr, len, len = offset + arg.length * 3, 1) >>> 0;
        const view = getUint8ArrayMemory0().subarray(ptr + offset, ptr + len);
        const ret = cachedTextEncoder.encodeInto(arg, view);

        offset += ret.written;
        ptr = realloc(ptr, len, offset, 1) >>> 0;
    }

    WASM_VECTOR_LEN = offset;
    return ptr;
}

function takeFromExternrefTable0(idx) {
    const value = wasm.__wbindgen_externrefs.get(idx);
    wasm.__externref_table_dealloc(idx);
    return value;
}

let cachedTextDecoder = new TextDecoder('utf-8', { ignoreBOM: true, fatal: true });
cachedTextDecoder.decode();
const MAX_SAFARI_DECODE_BYTES = 2146435072;
let numBytesDecoded = 0;
function decodeText(ptr, len) {
    numBytesDecoded += len;
    if (numBytesDecoded >= MAX_SAFARI_DECODE_BYTES) {
        cachedTextDecoder = new TextDecoder('utf-8', { ignoreBOM: true, fatal: true });
        cachedTextDecoder.decode();
        numBytesDecoded = len;
    }
    return cachedTextDecoder.decode(getUint8ArrayMemory0().subarray(ptr, ptr + len));
}

const cachedTextEncoder = new TextEncoder();

if (!('encodeInto' in cachedTextEncoder)) {
    cachedTextEncoder.encodeInto = function (arg, view) {
        const buf = cachedTextEncoder.encode(arg);
        view.set(buf);
        return {
            read: arg.length,
            written: buf.length
        };
    };
}

let WASM_VECTOR_LEN = 0;

let wasmModule, wasmInstance, wasm;
function __wbg_finalize_init(instance, module) {
    wasmInstance = instance;
    wasm = instance.exports;
    wasmModule = module;
    cachedDataViewMemory0 = null;
    cachedFloat32ArrayMemory0 = null;
    cachedFloat64ArrayMemory0 = null;
    cachedInt16ArrayMemory0 = null;
    cachedInt32ArrayMemory0 = null;
    cachedUint16ArrayMemory0 = null;
    cachedUint32ArrayMemory0 = null;
    cachedUint8ArrayMemory0 = null;
    wasm.__wbindgen_start();
    return wasm;
}

async function __wbg_load(module, imports) {
    if (typeof Response === 'function' && module instanceof Response) {
        if (!module.ok) {
            throw new Error(`failed to fetch Wasm: ${module.status} ${module.statusText} fetching '${module.url}'`);
        }

        if (typeof WebAssembly.instantiateStreaming === 'function') {
            try {
                return await WebAssembly.instantiateStreaming(module, imports);
            } catch (e) {
                const validResponse = expectedResponseType(module.type);

                if (validResponse && module.headers.get('Content-Type') !== 'application/wasm') {
                    console.warn("`WebAssembly.instantiateStreaming` failed because your server does not serve Wasm with `application/wasm` MIME type. Falling back to `WebAssembly.instantiate` which is slower. Original error:\n", e);

                } else { throw e; }
            }
        }

        const bytes = await module.arrayBuffer();
        return await WebAssembly.instantiate(bytes, imports);
    } else {
        const instance = await WebAssembly.instantiate(module, imports);

        if (instance instanceof WebAssembly.Instance) {
            return { instance, module };
        } else {
            return instance;
        }
    }

    function expectedResponseType(type) {
        switch (type) {
            case 'basic': case 'cors': case 'default': return true;
        }
        return false;
    }
}

function initSync(module) {
    if (wasm !== undefined) return wasm;


    if (module !== undefined) {
        if (Object.getPrototypeOf(module) === Object.prototype) {
            ({module} = module)
        } else {
            console.warn('using deprecated parameters for `initSync()`; pass a single object instead')
        }
    }

    const imports = __wbg_get_imports();
    if (!(module instanceof WebAssembly.Module)) {
        module = new WebAssembly.Module(module);
    }
    const instance = new WebAssembly.Instance(module, imports);
    return __wbg_finalize_init(instance, module);
}

async function __wbg_init(module_or_path) {
    if (wasm !== undefined) return wasm;


    if (module_or_path !== undefined) {
        if (Object.getPrototypeOf(module_or_path) === Object.prototype) {
            ({module_or_path} = module_or_path)
        } else {
            console.warn('using deprecated parameters for the initialization function; pass a single object instead')
        }
    }

    if (module_or_path === undefined) {
        module_or_path = new URL('figgy_bg.wasm', import.meta.url);
    }
    const imports = __wbg_get_imports();

    if (typeof module_or_path === 'string' || (typeof Request === 'function' && module_or_path instanceof Request) || (typeof URL === 'function' && module_or_path instanceof URL)) {
        module_or_path = fetch(module_or_path);
    }

    const { instance, module } = await __wbg_load(await module_or_path, imports);

    return __wbg_finalize_init(instance, module);
}

export { initSync, __wbg_init as default };
