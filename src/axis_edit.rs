//! Binding/UI convenience edits for opposite axes sharing one coordinate range.
use super::*;

/// Synchronize only the edited axis fields, using the pre-edit coordinate tuple.
/// Raw SSOT application deliberately does not call this helper.
pub(crate) fn sync_linked_axis_edit(before: &Value, after: &mut Value, target: &str) {
    let side = target
        .strip_prefix("tick_labels_")
        .or_else(|| target.strip_prefix("axis_"));
    let (source, opposite) = match side {
        Some("bottom") => ("bottom_x", "top_x"),
        Some("top") => ("top_x", "bottom_x"),
        Some("left") => ("left_y", "right_y"),
        Some("right") => ("right_y", "left_y"),
        _ => return,
    };
    let old = &before[source];
    let peer = &before[opposite];
    if !old.is_object()
        || !peer.is_object()
        || ["min", "max"]
            .iter()
            .any(|key| old[*key].as_f64().is_none() || old[*key].as_f64() != peer[*key].as_f64())
        || ["scale", "inverted"]
            .iter()
            .any(|key| old.get(*key).is_none() || old[*key] != peer[*key])
    {
        return;
    }
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
pub(crate) fn sync_linked_axis_edit_json(
    before_config: &str,
    after_config: &str,
    target: &str,
) -> PyResult<String> {
    let before: Value = serde_json::from_str(before_config).map_err(invalid)?;
    let mut after: Value = serde_json::from_str(after_config).map_err(invalid)?;
    sync_linked_axis_edit(&before, &mut after, target);
    serde_json::to_string(&after).map_err(runtime)
}
