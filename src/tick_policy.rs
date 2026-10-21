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

// Primary axes linked by a named group share navigation and tick intent.
fn owners(meta: &Value, owner: &str, key: &str) -> Vec<String> {
    let mut ids = vec![owner.to_owned()];
    let dimension = match key {
        "bottom_x" => "x",
        "left_y" => "y",
        _ => return ids,
    };
    loop {
        let before = ids.len();
        for group in meta["groups"]
            .as_object()
            .into_iter()
            .flat_map(|g| g.values())
        {
            if group["axis"] != dimension {
                continue;
            }
            let members: Vec<_> = group["members"]
                .as_array()
                .into_iter()
                .flatten()
                .filter_map(Value::as_str)
                .collect();
            if members.iter().any(|id| ids.iter().any(|v| v == id)) {
                for id in members {
                    if !ids.iter().any(|v| v == id) {
                        ids.push(id.to_owned());
                    }
                }
            }
        }
        if ids.len() == before {
            return ids;
        }
    }
}

pub(crate) fn automatic(meta: Option<&Value>, layer: renderer::LayerRef, side: &str) -> bool {
    let Some(meta) = meta else {
        return true;
    };
    address(meta, layer, side).is_none_or(|(owner, key)| {
        owners(meta, &owner, &key)
            .iter()
            .all(|id| meta["tick_modes"][id][&key] != "Fixed")
    })
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
    let mut targets = vec![key.as_str()];
    if let Some(peer) = peer {
        targets.push(peer);
    }
    for key in targets {
        let ids = owners(&state["identity"], &owner, key);
        let meta = &mut state["identity"];
        if !meta["tick_modes"].is_object() {
            meta["tick_modes"] = json!({});
        }
        for id in ids {
            if !meta["tick_modes"][&id].is_object() {
                meta["tick_modes"][&id] = json!({});
            }
            meta["tick_modes"][id][key] = json!(if automatic { "Auto" } else { "Fixed" });
        }
    }
}

/// The upstream link helper carries spacing with range edits, but resets a
/// spacing-only member edit to its root. Apply shared spacing before that step.
pub(crate) fn synchronize_spacing(state: &mut Value, side: &str) {
    if !matches!(side, "bottom_x" | "left_y") {
        return;
    }
    let layer = state["config"]
        .get("active_layer")
        .cloned()
        .and_then(|v| serde_json::from_value(v).ok())
        .unwrap_or(renderer::LayerRef::Base);
    let Some((owner, key)) = address(&state["identity"], layer, side) else {
        return;
    };
    let panels = state["identity"]["panels"].as_array().unwrap();
    let indices: Vec<_> = owners(&state["identity"], &owner, &key)
        .iter()
        .filter_map(|id| panels.iter().position(|p| p["id"] == *id))
        .collect();
    let Some(source) = panels.iter().position(|p| p["id"] == owner) else {
        return;
    };
    let spacing = if source == 0 {
        &state["config"][&key]
    } else {
        &state["config"]["subplots"][source - 1]["config"][&key]
    }["major_spacing"]
        .clone();
    for index in indices {
        let cfg = if index == 0 {
            &mut state["config"]
        } else {
            &mut state["config"]["subplots"][index - 1]["config"]
        };
        cfg[&key]["major_spacing"] = spacing.clone();
    }
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
