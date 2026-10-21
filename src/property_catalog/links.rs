//! Axis membership changes update renderer links and host intent together.
use super::*;
fn index(layer: renderer::LayerRef) -> usize {
    match layer {
        renderer::LayerRef::Subplot(i) | renderer::LayerRef::SubplotOverlay(i, _) => i + 1,
        _ => 0,
    }
}
fn panel(index: usize) -> String {
    if index == 0 {
        "/config".into()
    } else {
        format!("/config/subplots/{}/config", index - 1)
    }
}
fn components(state: &Value, axis: &str) -> Vec<Vec<usize>> {
    let count = state["identity"]["panels"].as_array().map_or(0, Vec::len);
    let mut sets: Vec<Vec<usize>> = (0..count).map(|i| vec![i]).collect();
    for i in 1..count {
        let link = &state["config"]["subplots"][i - 1][format!("link_{axis}")];
        let target = if link == "Parent" {
            Some(0)
        } else {
            link["Subplot"].as_u64().map(|j| j as usize + 1)
        };
        if let Some(target) = target.filter(|j| *j < count) {
            let a = sets.iter().position(|s| s.contains(&i)).unwrap();
            let b = sets.iter().position(|s| s.contains(&target)).unwrap();
            if a != b {
                let merged = sets.remove(a);
                let b = sets.iter().position(|s| s.contains(&target)).unwrap();
                sets[b].extend(merged);
            }
        }
    }
    sets
}
pub(super) fn fields(out: &mut Vec<Field>, state: &Value, layer: renderer::LayerRef) {
    let Some(panels) = state["identity"]["panels"]
        .as_array()
        .filter(|v| v.len() > 1)
    else {
        return;
    };
    let here = index(layer);
    for axis in ["x", "y"] {
        let peer = components(state, axis)
            .into_iter()
            .find(|s| s.contains(&here))
            .and_then(|s| s.into_iter().find(|i| *i != here));
        let mut choices = vec![json!("")];
        choices.extend(
            panels
                .iter()
                .enumerate()
                .filter(|(i, _)| *i != here)
                .map(|(_, p)| p["id"].clone()),
        );
        optional::choice(
            out,
            &format!("Shared axes/{axis}"),
            "/identity/groups",
            "Shared axes",
            &format!("{} axis follows chart", axis.to_uppercase()),
            peer.map_or(json!(""), |i| panels[i]["id"].clone()),
            choices,
        );
    }
}
pub(super) fn apply(
    state: &mut Value,
    layer: renderer::LayerRef,
    id: &str,
    value: &Value,
) -> PyResult<()> {
    let axis = id.rsplit('/').next().unwrap();
    let here = index(layer);
    let panels = state["identity"]["panels"].as_array().unwrap().clone();
    let previous_groups = state["identity"]["groups"].as_object().unwrap().clone();
    let mut sets = components(state, axis);
    for members in &mut sets {
        members.retain(|i| *i != here);
    }
    if value != "" {
        let target = panels
            .iter()
            .position(|p| &p["id"] == value)
            .ok_or_else(|| invalid("shared axis target no longer exists"))?;
        let members = sets.iter_mut().find(|s| s.contains(&target)).unwrap();
        members.push(here);
        let side = if axis == "x" { "bottom_x" } else { "left_y" };
        let reference = state.pointer(&panel(target)).unwrap()[side].clone();
        let mode =
            state["identity"]["tick_modes"][panels[target]["id"].as_str().unwrap()][side].clone();
        for i in members.iter().copied() {
            let cfg = state.pointer_mut(&panel(i)).unwrap();
            for key in [
                "min",
                "max",
                "scale",
                "inverted",
                "major_spacing",
                "minor_spacing",
            ] {
                if let Some(value) = reference.get(key) {
                    cfg[side][key] = value.clone();
                }
            }
            if state["identity"].get("tick_modes").is_none() {
                state["identity"]["tick_modes"] = json!({});
            }
            let modes = state["identity"]["tick_modes"]
                .as_object_mut()
                .unwrap()
                .entry(panels[i]["id"].as_str().unwrap())
                .or_insert(json!({}));
            modes[side] = if mode.is_null() {
                json!("Auto")
            } else {
                mode.clone()
            };
        }
    }
    for i in 1..panels.len() {
        state["config"]["subplots"][i - 1][format!("link_{axis}")] = Value::Null;
    }
    state["identity"]["groups"]
        .as_object_mut()
        .unwrap()
        .retain(|_, v| v["axis"] != axis);
    let mut used: std::collections::HashSet<String> = state["identity"]["groups"]
        .as_object()
        .unwrap()
        .keys()
        .cloned()
        .collect();
    for mut members in sets.into_iter().filter(|s| s.len() > 1) {
        members.sort();
        let root = members[0];
        for i in members.iter().copied().skip(1) {
            state["config"]["subplots"][i - 1][format!("link_{axis}")] = if root == 0 {
                json!("Parent")
            } else {
                json!({"Subplot":root-1})
            };
        }
        let ids: Vec<_> = members.iter().map(|i| panels[*i]["id"].clone()).collect();
        let existing = previous_groups
            .iter()
            .filter(|(name, group)| group["axis"] == axis && !used.contains(*name))
            .filter_map(|(name, group)| {
                let overlap = group["members"]
                    .as_array()?
                    .iter()
                    .filter(|id| ids.contains(id))
                    .count();
                (overlap > 0).then_some((name, overlap))
            })
            .max_by_key(|(_, overlap)| *overlap)
            .map(|(name, _)| name.clone());
        let base = format!("editor/{axis}/{}", panels[root]["id"].as_str().unwrap());
        let mut name = existing.unwrap_or_else(|| base.clone());
        let mut suffix = 2;
        while used.contains(&name) {
            name = format!("{base}/{suffix}");
            suffix += 1;
        }
        used.insert(name.clone());
        state["identity"]["groups"][name] = json!({"axis":axis,"members":members.iter().map(|i|panels[*i]["id"].clone()).collect::<Vec<_>>()});
    }
    Ok(())
}
