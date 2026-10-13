// Shared UI for anywidget and the desktop QWebChannel transport.
// Geometry, data picking and accepted settings belong to the Rust renderer.
export function render({ model, el }) {
  const root = document.createElement("div"); root.className = "figgy-editor";
  root.innerHTML = `<div class="figgy-toolbar"><button data-fit>Fit</button>
    <label><input type="checkbox" data-area> Edit plot area</label>
    <button data-copy>Copy Python</button><button data-save>Save PNG</button>
    <span data-status></span></div><div class="figgy-body">
    <div class="figgy-stage"><canvas></canvas></div><div class="figgy-properties">
    <label>Object <select data-target></select></label><div data-fields></div>
    <details><summary>SSOT settings</summary><textarea data-settings spellcheck="false"></textarea>
    <button data-apply>Apply settings</button></details>
    <details data-code-panel><summary>Python code</summary><textarea data-code readonly></textarea></details>
    </div></div><div class="figgy-error" role="alert"></div>`;
  el.append(root);
  const canvas = root.querySelector("canvas"), ctx = canvas.getContext("2d");
  const target = root.querySelector("[data-target]"), fields = root.querySelector("[data-fields]");
  const status = root.querySelector("[data-status]"), error = root.querySelector(".figgy-error");
  let disposed = false, current = null, bitmap = null, imageRef = null, imageURL = null;
  let request = 0, pending = null, queue = [], decode = 0, frame = null;
  let pointer = null, dragTimer = null, dragDelta = [0, 0], handle = null;
  let localTarget = null;
  const finite = value => Number.isFinite(Number(value));
  const richText = rich => rich?.segments?.map(s => s.text).join("") ?? "";
  const hex = c => "#" + [c.r, c.g, c.b].map(v => Math.round(v * 255).toString(16).padStart(2, "0")).join("");
  const sideKey = {bottom: "bottom_x", top: "top_x", left: "left_y", right: "right_y"};

  function dispatch(message) {
    queue.push(message); pump();
  }
  function pump() {
    if (disposed || pending || !current || !queue.length) return;
    const message = queue.shift();
    pending = ++request;
    model.send({...message, request_id: pending, revision: current.revision});
    status.textContent = "Rendering…";
  }
  function draw() {
    if (!current || !bitmap) return;
    canvas.width = current.width; canvas.height = current.height;
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    if (current.bounds && current.image_revision === current.revision) {
      const [x, y, w, h] = current.bounds.rect;
      ctx.strokeStyle = "#2278ee"; ctx.lineWidth = 1.5; ctx.strokeRect(x, y, w, h);
      ctx.fillStyle = "#2278ee";
      for (const [x, y, w, h] of current.bounds.handles) ctx.fillRect(x, y, w, h);
    }
  }
  function input(label, type, value, property) {
    const row = document.createElement("label"); row.textContent = label;
    const control = document.createElement("input"); control.type = type;
    if (type === "checkbox") control.checked = value; else control.value = value;
    if (type === "number") control.step = "any";
    control.addEventListener("change", () => {
      let value = type === "checkbox" ? control.checked : type === "number" ? Number(control.value) : control.value;
      if (type === "number" && !finite(control.value)) { error.textContent = "Enter a finite number"; return; }
      dispatch({action: "update", target: target.value, properties: {[property]: value}});
    });
    row.append(control); fields.append(row);
  }
  function properties() {
    fields.replaceChildren();
    const cfg = current.settings.config, selected = target.value;
    const series = current.settings.series.find(s => s.series_id === selected);
    if (series) {
      const style = Object.values(series.render_type)[0];
      input("Label", "text", richText(series.label), "label");
      if (style.line) { input("Color", "color", hex(style.line.line_color), "color"); input("Line width (pt)", "number", style.line.line_width * 72 / current.dpi, "linewidth"); }
      if (style.scatter) { if (!style.line) input("Color", "color", hex(style.scatter.point_color), "color"); input("Marker size (pt)", "number", style.scatter.point_size * 144 / current.dpi, "markersize"); }
      if (style.matrix && cfg.colorbar) { input("Minimum", "number", cfg.colorbar.axis.min, "vmin"); input("Maximum", "number", cfg.colorbar.axis.max, "vmax"); }
      return;
    }
    let node, rich;
    if (selected === "chart_title") { node = cfg.chart_title; rich = node.text; }
    else if (selected === "legend") { node = cfg.legend; rich = node.content; }
    else if (selected.startsWith("axis_title_")) { node = cfg[sideKey[selected.slice(11)]]?.title_option; rich = node?.text; }
    else if (selected.startsWith("tick_labels_")) node = cfg[sideKey[selected.slice(12)]]?.label_style;
    else if (selected.startsWith("axis_")) node = cfg[sideKey[selected.slice(5)]];
    if (!node) { fields.textContent = "Select a title, axis, legend or data object. Drag selected decorations; use handles to resize the plot area."; return; }
    if (rich) { input("Text", "text", richText(rich), "text"); input("Font size (pt)", "number", rich.font_size * 72 / current.dpi, "fontsize"); input("Color", "color", hex(rich.color), "color"); }
    if ("visible" in node) input("Visible", "checkbox", node.visible, "visible");
    if ("line_width" in node) input("Line width", "number", node.line_width, "line_width");
  }
  function refresh() {
    if (disposed) return;
    current = model.get("state");
    if (!current?.settings) return;
    if (pending === current.last_request) {
      pending = null; handle = current.handle;
      if (pointer) pointer.target = current.selection;
      pump();
    }
    status.textContent = pending ? "Rendering…" : `Revision ${current.revision}`;
    error.textContent = current.error || "";
    const choices = ["chart_title", "axis_title_bottom", "axis_title_left", "axis_bottom", "axis_left", "tick_labels_bottom", "tick_labels_left", "legend", "data_area", ...current.settings.series.map(s => s.series_id)];
    localTarget = current.selection || localTarget || choices[0];
    target.replaceChildren(...choices.map(id => { const option = document.createElement("option"); option.value = id; option.textContent = id; return option; }));
    target.value = localTarget;
    properties();
    root.querySelector("[data-code]").value = current.code;
    const settings = root.querySelector("[data-settings]");
    if (document.activeElement !== settings) settings.value = JSON.stringify(current.settings, null, 2);
    const image = model.get("image");
    if (image && image.byteLength !== 0 && image !== imageRef) {
      imageRef = image; const token = ++decode;
      const blob = new Blob([image instanceof DataView ? image.buffer.slice(image.byteOffset, image.byteOffset + image.byteLength) : image], {type: "image/png"});
      if (imageURL) URL.revokeObjectURL(imageURL); imageURL = URL.createObjectURL(blob);
      createImageBitmap(blob).then(next => {
        if (disposed || token !== decode) { next.close(); return; }
        bitmap?.close(); bitmap = next; draw();
      }).catch(e => { error.textContent = e.message; });
    } else draw();
  }
  function schedule() { if (frame === null) frame = requestAnimationFrame(() => { frame = null; refresh(); }); }
  function xy(event) {
    const rect = canvas.getBoundingClientRect();
    return [(event.clientX - rect.left) * current.width / rect.width, (event.clientY - rect.top) * current.height / rect.height];
  }
  function flushDrag() {
    dragTimer = null;
    if (pending) { dragTimer = setTimeout(flushDrag, 100); return; }
    if (current.selection && (dragDelta[0] || dragDelta[1])) {
      dispatch({action: "drag", target: current.selection, dx: dragDelta[0], dy: dragDelta[1], handle});
    }
    dragDelta = [0, 0];
  }
  canvas.addEventListener("pointerdown", event => {
    if (!current || pending || current.image_revision !== current.revision) return;
    const [x, y] = xy(event); pointer = {x, y, target: current.selection}; dragDelta = [0, 0]; handle = null;
    canvas.setPointerCapture(event.pointerId);
    dispatch({action: "pick", x, y, edit_area: root.querySelector("[data-area]").checked});
  });
  canvas.addEventListener("pointermove", event => {
    if (!pointer) return;
    const [x, y] = xy(event); dragDelta[0] += x - pointer.x; dragDelta[1] += y - pointer.y;
    pointer.x = x; pointer.y = y;
    if (!dragTimer) dragTimer = setTimeout(flushDrag, 100);
  });
  const stop = () => { pointer = null; if (dragTimer) clearTimeout(dragTimer); flushDrag(); };
  canvas.addEventListener("pointerup", stop); canvas.addEventListener("pointercancel", stop);
  target.addEventListener("change", () => { localTarget = target.value; properties(); dispatch({action: "select", target: localTarget}); });
  root.querySelector("[data-fit]").addEventListener("click", () => dispatch({action: "fit"}));
  root.querySelector("[data-apply]").addEventListener("click", () => {
    try { dispatch({action: "settings", settings: JSON.parse(root.querySelector("[data-settings]").value)}); }
    catch (e) { error.textContent = e.message; }
  });
  root.querySelector("[data-copy]").addEventListener("click", async () => {
    const code = root.querySelector("[data-code]");
    try {
      if (globalThis.figgyDesktopCopy) globalThis.figgyDesktopCopy(code.value);
      else await navigator.clipboard.writeText(code.value);
      status.textContent = "Python code copied";
    } catch {
      root.querySelector("[data-code-panel]").open = true; code.focus(); code.select();
      status.textContent = "Press Ctrl/Cmd+C to copy Python code";
    }
  });
  root.querySelector("[data-save]").addEventListener("click", () => {
    if (globalThis.figgyDesktopSave) { globalThis.figgyDesktopSave(); return; }
    if (imageURL) { const link = document.createElement("a"); link.href = imageURL; link.download = "figure.png"; link.click(); }
  });
  model.on("change:state", schedule); model.on("change:image", schedule); refresh();
  return () => {
    disposed = true; ++decode; if (frame !== null) cancelAnimationFrame(frame);
    if (dragTimer) clearTimeout(dragTimer); bitmap?.close(); if (imageURL) URL.revokeObjectURL(imageURL);
    model.off("change:state", schedule); model.off("change:image", schedule); root.remove();
  };
}

export default { render };
