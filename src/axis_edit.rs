//! Binding/UI convenience edits for opposite axes sharing one coordinate range.
use super::*;

pub(crate) struct AxisAddress {
    pub panel: String,
    pub path: String,
    pub side: &'static str,
    pub dimension: &'static str,
    pub layer: renderer::LayerRef,
}

pub(crate) fn address(
    state: &Value,
    target: &str,
    layer: renderer::LayerRef,
) -> Option<AxisAddress> {
    use renderer::LayerRef;
    let target = target.rsplit(':').next()?;
    let side = target
        .strip_prefix("tick_labels_")
        .or_else(|| target.strip_prefix("axis_"))?;
    let side = match side {
        "bottom" => "bottom_x",
        "top" => "top_x",
        "left" => "left_y",
        "right" => "right_y",
        _ => return None,
    };
    let (subplot, overlay) = crate::view_gesture::layer_parts(layer);
    let panel = subplot.map_or_else(
        || "/config".into(),
        |i| format!("/config/subplots/{i}/config"),
    );
    let cfg = state.pointer(&panel)?;
    let dimension = match side {
        "bottom_x" | "top_x" => "x",
        "right_y" if cfg["view_3d"].is_object() => "height",
        _ => "y",
    };
    if let Some(index) = overlay {
        let overlay = cfg["overlays"].get(index)?;
        let key = match side {
            "top_x" if overlay["link_x"] == false => Some("x_axis"),
            "right_y" if overlay["link_y"] != true => Some("y_axis"),
            _ => None,
        };
        if let Some(key) = key {
            return Some(AxisAddress {
                path: format!("{panel}/overlays/{index}/{key}"),
                panel,
                side: if key == "y_axis" { "right_y" } else { key },
                dimension,
                layer,
            });
        }
    }
    Some(AxisAddress {
        path: format!("{panel}/{side}"),
        panel,
        side,
        dimension,
        layer: subplot.map_or(LayerRef::Base, LayerRef::Subplot),
    })
}

pub(crate) fn apply_scale(
    axis: &mut Value,
    bounds: impl FnOnce() -> PyResult<(f64, f64)>,
    keep_spacing: bool,
) -> PyResult<()> {
    let logarithmic = axis["scale"] == "Logarithmic";
    if logarithmic && axis["min"].as_f64().is_some_and(|v| v <= 0.) {
        let (min, max) = bounds()?;
        axis["min"] = json!(min);
        axis["max"] = json!(max);
    }
    if !keep_spacing {
        let span = || -> PyResult<f64> {
            let limit = |name: &str| {
                axis[name]
                    .as_f64()
                    .ok_or_else(|| invalid("axis limits must be numeric"))
            };
            Ok(limit("max")? - limit("min")?)
        };
        axis["major_spacing"] = json!(if logarithmic { 1. } else { span()? / 5. });
    }
    Ok(())
}

/// Apply an axis form to the renderer document, resolving ownership from that document.
pub(crate) fn apply(
    state: &mut Value,
    address: &AxisAddress,
    axis: Value,
    tick_mode: Option<bool>,
    bounds: impl FnOnce() -> PyResult<(f64, f64)>,
) -> PyResult<()> {
    // JSON sent by the browser has one numeric type. Compare renderer-typed
    // documents so a number such as 18 and 18.0 cannot create a style edit.
    let candidate: renderer::config::AxisOptions = serde_json::from_value(axis).map_err(invalid)?;
    let mut axis = serde_json::to_value(candidate).map_err(runtime)?;
    let previous = state
        .pointer(&address.path)
        .ok_or_else(|| invalid("axis owner changed"))?;
    let changed_scale = axis["scale"] != previous["scale"];
    let changed_range = ["min", "max"]
        .into_iter()
        .any(|key| axis[key] != previous[key]);
    let explicit_spacing = tick_mode == Some(false);
    let before = state.pointer(&address.panel).unwrap().clone();
    if let Some(automatic) = tick_mode {
        tick_policy::set_mode_at(state, address.layer, address.side, Some(automatic), true);
    }
    if changed_scale {
        apply_scale(&mut axis, bounds, explicit_spacing)?;
    } else if tick_mode == Some(true)
        || (changed_range
            && !explicit_spacing
            && tick_policy::automatic(state.get("identity"), address.layer, address.side))
    {
        tick_policy::retick_value(&mut axis);
    }
    *state.pointer_mut(&address.path).unwrap() = axis;
    if !matches!(
        address.layer,
        renderer::LayerRef::Overlay(_) | renderer::LayerRef::SubplotOverlay(_, _)
    ) {
        sync_linked_axis_edit(
            &before,
            state.pointer_mut(&address.panel).unwrap(),
            address.side,
        );
        for side in ["bottom_x", "left_y"] {
            tick_policy::synchronize_spacing_at(state, address.layer, side);
        }
    }
    Ok(())
}

/// Synchronize only the edited axis fields, using the pre-edit coordinate tuple.
/// Raw SSOT application deliberately does not call this helper.
fn sync_linked_axis_edit(before: &Value, after: &mut Value, source: &str) {
    let Some(opposite) = tick_policy::paired_axis(before, source) else {
        return;
    };
    let old = &before[source];
    let mut changes = Vec::new();
    for key in [
        "min",
        "max",
        "scale",
        "inverted",
        "major_spacing",
        "minor_count",
        "tick",
        "major_tick_length",
        "minor_tick_length",
        "line_color",
        "line_width",
        "line_style",
    ] {
        if let Some(value) = after[source].get(key)
            && old.get(key) != Some(value)
        {
            changes.push((key, value.clone()));
        }
    }
    let mut labels = Vec::new();
    if let Some(style) = after[source]["label_style"].as_object() {
        for (key, value) in style {
            if !matches!(key.as_str(), "label_offset_x" | "label_offset_y")
                && old["label_style"].get(key) != Some(value)
            {
                labels.push((key.clone(), value.clone()));
            }
        }
    }
    if let Some(peer) = after[opposite].as_object_mut() {
        for (key, value) in changes {
            peer.insert(key.into(), value);
        }
        if let Some(style) = peer.get_mut("label_style").and_then(Value::as_object_mut) {
            for (key, value) in labels {
                style.insert(key, value);
            }
        }
    }
}

#[pyfunction]
pub(crate) fn tick_mode_json(
    settings: &str,
    layer: &str,
    side: &str,
    mode: Option<bool>,
    paired: bool,
    spacing: Option<f64>,
) -> PyResult<String> {
    let mut state: Value = serde_json::from_str(settings).map_err(invalid)?;
    let layer = serde_json::from_str(layer).map_err(invalid)?;
    let is_x = matches!(side, "bottom_x" | "top_x" | "x_axis");
    let probe = if is_x { "axis_top" } else { "axis_right" };
    let axis = address(&state, probe, layer).ok_or_else(|| invalid("unknown axis owner"))?;
    let key = match axis.layer {
        renderer::LayerRef::Overlay(_) | renderer::LayerRef::SubplotOverlay(_, _) => axis.side,
        _ => match side {
            "x_axis" => "bottom_x",
            "y_axis" => "left_y",
            _ => side,
        },
    };
    tick_policy::set_mode_at(&mut state, axis.layer, key, mode, paired);
    if let Some(step) = spacing
        && matches!(key, "bottom_x" | "left_y")
    {
        state.pointer_mut(&axis.panel).unwrap()[key]["major_spacing"] = json!(step);
        tick_policy::synchronize_spacing_at(&mut state, axis.layer, key);
    }
    Ok(state.to_string())
}

#[pyfunction]
pub(crate) fn axis_address_json(settings: &str, layer: &str, target: &str) -> PyResult<String> {
    let state: Value = serde_json::from_str(settings).map_err(invalid)?;
    let layer = serde_json::from_str(layer).map_err(invalid)?;
    let axis = address(&state, target, layer).ok_or_else(|| invalid("unknown axis owner"))?;
    Ok(json!({"path":axis.path,"layer":axis.layer,"dimension":axis.dimension}).to_string())
}

#[pyfunction]
pub(crate) fn complete_axis_edit_json(
    settings: &str,
    layer: &str,
    target: &str,
    candidate: &str,
    tick_mode: Option<bool>,
    positive: Option<(f64, f64)>,
) -> PyResult<String> {
    let mut state: Value = serde_json::from_str(settings).map_err(invalid)?;
    let layer = serde_json::from_str(layer).map_err(invalid)?;
    let axis = address(&state, target, layer).ok_or_else(|| invalid("unknown axis owner"))?;
    let candidate = serde_json::from_str(candidate).map_err(invalid)?;
    apply(&mut state, &axis, candidate, tick_mode, || {
        positive.ok_or_else(|| invalid("positive data limits are required for a logarithmic axis"))
    })?;
    Ok(state.to_string())
}

#[pyfunction]
pub(crate) fn scale_axes_json(
    axes: &str,
    scale: &str,
    positive: Option<(f64, f64)>,
) -> PyResult<String> {
    let mut axes: Vec<Value> = serde_json::from_str(axes).map_err(invalid)?;
    for axis in &mut axes {
        axis["scale"] = json!(scale);
        apply_scale(
            axis,
            || {
                positive.ok_or_else(|| {
                    invalid("positive data limits are required for a logarithmic axis")
                })
            },
            false,
        )?;
    }
    serde_json::to_string(&axes).map_err(runtime)
}
