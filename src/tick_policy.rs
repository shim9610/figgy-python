//! Host-owned automatic/fixed tick intent, addressed by persistent axes owner.
use super::*;

fn address(meta: &Value, layer: renderer::LayerRef, side: &str) -> Option<(String, String)> {
    let (panel, overlay) = match layer {
        renderer::LayerRef::Subplot(i) => (i + 1, None),
        renderer::LayerRef::SubplotOverlay(i, o) => (i + 1, Some(o)),
        renderer::LayerRef::Overlay(o) => (0, Some(o)),
        _ => (0, None),
    };
    let panel = &meta["panels"][panel];
    if side == "right_y"
        && let Some(overlay) = overlay
    {
        Some((panel["overlays"][overlay].as_str()?.into(), "y_axis".into()))
    } else {
        Some((panel["id"].as_str()?.into(), side.into()))
    }
}

pub(crate) fn automatic(meta: Option<&Value>, layer: renderer::LayerRef, side: &str) -> bool {
    let Some(meta) = meta else {
        return true;
    };
    address(meta, layer, side).is_none_or(|(owner, key)| meta["tick_modes"][owner][key] != "Fixed")
}

pub(crate) fn set_mode(state: &mut Value, side: &str, automatic: bool) {
    let layer = state["config"]
        .get("active_layer")
        .cloned()
        .and_then(|v| serde_json::from_value(v).ok())
        .unwrap_or(renderer::LayerRef::Base);
    let Some((owner, key)) = address(&state["identity"], layer, side) else {
        return;
    };
    let index = match layer {
        renderer::LayerRef::Subplot(i) | renderer::LayerRef::SubplotOverlay(i, _) => Some(i),
        _ => None,
    };
    let cfg = index.map_or(
        &state["config"],
        |i| &state["config"]["subplots"][i]["config"],
    );
    let peer = match key.as_str() {
        "bottom_x" => Some("top_x"),
        "top_x" => Some("bottom_x"),
        "left_y" => Some("right_y"),
        "right_y" => Some("left_y"),
        _ => None,
    };
    let peer = peer.filter(|other| {
        ["min", "max", "scale", "inverted"]
            .iter()
            .all(|field| cfg[&key][field] == cfg[other][field])
    });
    let meta = &mut state["identity"];
    if !meta["tick_modes"].is_object() {
        meta["tick_modes"] = json!({});
    }
    if !meta["tick_modes"][&owner].is_object() {
        meta["tick_modes"][&owner] = json!({});
    }
    if let Some(peer) = peer {
        meta["tick_modes"][&owner][peer] = json!(if automatic { "Auto" } else { "Fixed" });
    }
    meta["tick_modes"][owner][key] = json!(if automatic { "Auto" } else { "Fixed" });
}

/// Use the published renderer's public range helper to derive spacing only.
/// Keep user number formatting, minor divisions and all other axis properties.
pub(crate) fn retick(axis: &mut renderer::config::AxisOptions) {
    let mut config = default::default_config();
    config.bottom_x = axis.clone();
    let mut chart = Chart::new(config);
    chart.set_x_range(axis.min, axis.max);
    axis.major_spacing = chart.config().bottom_x.major_spacing;
}

pub(crate) fn retick_value(axis: &mut Value) {
    if let Ok(mut parsed) = serde_json::from_value::<renderer::config::AxisOptions>(axis.clone()) {
        retick(&mut parsed);
        axis["major_spacing"] = json!(parsed.major_spacing);
    }
}
