//! Host-owned automatic/fixed tick intent, addressed by persistent axes owner.
use renderer::{Chart, default};
use serde_json::Value;
#[cfg(not(target_arch = "wasm32"))]
use serde_json::json;

fn address(meta: &Value, layer: renderer::LayerRef, side: &str) -> Option<(String, String)> {
    let (panel, overlay) = super::layer_parts(layer);
    let panel = panel.map_or(0, |i| i + 1);
    let panel = &meta["panels"][panel];
    if matches!(side, "right_y" | "y_axis" | "x_axis")
        && let Some(overlay) = overlay
    {
        let key = if side == "x_axis" { side } else { "y_axis" };
        Some((panel["overlays"][overlay].as_str()?.into(), key.into()))
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

#[cfg(not(target_arch = "wasm32"))]
pub(crate) fn paired_axis(config: &Value, side: &str) -> Option<&'static str> {
    let peer = match side {
        "bottom_x" => "top_x",
        "top_x" => "bottom_x",
        "left_y" if config["view_3d"].is_null() => "right_y",
        "right_y" if config["view_3d"].is_null() => "left_y",
        _ => return None,
    };
    let axis = &config[side];
    let opposite = &config[peer];
    (axis.is_object()
        && opposite.is_object()
        && ["min", "max"].into_iter().all(|key| {
            axis[key].as_f64().is_some() && axis[key].as_f64() == opposite[key].as_f64()
        })
        && ["scale", "inverted"]
            .into_iter()
            .all(|key| axis.get(key).is_some() && axis[key] == opposite[key]))
    .then_some(peer)
}

#[cfg(not(target_arch = "wasm32"))]
pub(crate) fn set_mode_at(
    state: &mut Value,
    layer: renderer::LayerRef,
    side: &str,
    mode: Option<bool>,
    paired: bool,
) {
    let Some((owner, key)) = address(&state["identity"], layer, side) else {
        return;
    };
    let cfg = match layer {
        renderer::LayerRef::Subplot(i) | renderer::LayerRef::SubplotOverlay(i, _) => {
            &state["config"]["subplots"][i]["config"]
        }
        _ => &state["config"],
    };
    let peer = paired.then(|| paired_axis(cfg, &key)).flatten();
    for key in std::iter::once(key.as_str()).chain(peer) {
        let ids = owners(&state["identity"], &owner, key);
        let meta = &mut state["identity"];
        for id in ids {
            if let Some(automatic) = mode {
                if !meta["tick_modes"].is_object() {
                    meta["tick_modes"] = json!({});
                }
                if !meta["tick_modes"][&id].is_object() {
                    meta["tick_modes"][&id] = json!({});
                }
                meta["tick_modes"][id][key] = json!(if automatic { "Auto" } else { "Fixed" });
            } else if let Some(modes) = meta["tick_modes"].as_object_mut() {
                if let Some(mode) = modes.get_mut(&id).and_then(Value::as_object_mut) {
                    mode.remove(key);
                    if mode.is_empty() {
                        modes.remove(&id);
                    }
                }
                if modes.is_empty() {
                    meta.as_object_mut().unwrap().remove("tick_modes");
                }
            }
        }
    }
}

/// Carry a spacing-only edit across shared axes before renderer link normalization.
#[cfg(not(target_arch = "wasm32"))]
pub(crate) fn synchronize_spacing_at(state: &mut Value, layer: renderer::LayerRef, side: &str) {
    if !matches!(side, "bottom_x" | "left_y") {
        return;
    }
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

#[cfg(not(target_arch = "wasm32"))]
pub(crate) fn retick_value(axis: &mut Value) {
    if let Ok(mut parsed) = serde_json::from_value::<renderer::config::AxisOptions>(axis.clone()) {
        retick(&mut parsed);
        axis["major_spacing"] = json!(parsed.major_spacing);
    }
}
