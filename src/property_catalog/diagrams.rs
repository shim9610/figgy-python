//! Inspector defaults come from public model defaults, including serde-omitted values.
use super::*;

pub(super) fn expanded(kind: &str, body: &Value, rich: &Value) -> Value {
    let mut out = body.clone();
    let defaults = match kind {
        "EnergyLevels" => {
            let d = renderer::energy_levels::EnergyLevelSeries::default();
            json!({"style": d.style, "show": d.show})
        }
        "Feynman" => {
            let d = renderer::feynman::FeynmanSeries::default();
            json!({"style": d.style, "layout": d.layout})
        }
        _ => return out,
    };
    fn fill(value: &mut Value, defaults: &Value) {
        if let (Some(value), Some(defaults)) = (value.as_object_mut(), defaults.as_object()) {
            for (key, default) in defaults {
                if let Some(current) = value.get_mut(key) {
                    fill(current, default);
                } else {
                    value.insert(key.clone(), default.clone());
                }
            }
        }
    }
    fill(&mut out, &defaults);
    if kind == "EnergyLevels"
        && out["style"]["transition"]
            .get("color_by_wavelength")
            .is_none()
    {
        out["style"]["transition"]["color_by_wavelength"] = Value::Null;
    }
    let momentum: renderer::feynman::MomentumArrow =
        serde_json::from_value(json!({"label": rich})).unwrap();
    let momentum_defaults = json!({"side":momentum.side,"reversed":momentum.reversed,"label_offset":momentum.label_offset});
    for list in [
        "levels",
        "transitions",
        "limits",
        "bands",
        "vertices",
        "propagators",
    ] {
        if let Some(rows) = out.get_mut(list).and_then(Value::as_array_mut) {
            for row in rows {
                if kind == "Feynman" && list == "vertices" {
                    let vertex: renderer::feynman::FeynmanVertex =
                        serde_json::from_value(json!({"id":row["id"]})).unwrap();
                    if row.get("role").is_none() {
                        row["role"] = json!(vertex.role);
                    }
                    if row.get("marker").is_none() {
                        row["marker"] = Value::Null;
                    }
                    if let Some(blob) = row.pointer_mut("/marker/Blob") {
                        if blob.get("fill").is_none() {
                            blob["fill"] = Value::Null;
                        }
                    }
                }
                if kind == "Feynman" && list == "propagators" {
                    for key in ["momentum", "color", "width_px", "bend"] {
                        if row.get(key).is_none() {
                            row[key] = Value::Null;
                        }
                    }
                    if row["momentum"].is_object() {
                        fill(&mut row["momentum"], &momentum_defaults);
                    }
                }
                if kind == "EnergyLevels" && list == "transitions" && row.get("color").is_none() {
                    row["color"] = Value::Null;
                }
                if row.get("label").is_none_or(Value::is_null) {
                    let mut label = rich.clone();
                    label["segments"] = json!([]);
                    row["label"] = label;
                }
                if row.get("label_offset").is_none() {
                    row["label_offset"] = json!([0., 0.]);
                }
            }
        }
    }
    out
}

// Only the missing owner of the edited field is materialised. Other rows keep
// omitted labels/defaults and numerical records remain byte-for-byte unchanged.
pub(super) fn prepare_edit(
    state: &mut Value,
    path: &str,
    layer: renderer::LayerRef,
) -> PyResult<()> {
    let parts: Vec<_> = path.split('/').skip(1).collect();
    if parts.len() < 5
        || parts[0] != "series"
        || parts[2] != "render_type"
        || !matches!(parts[3], "EnergyLevels" | "Feynman")
    {
        return Ok(());
    }
    let root = format!("/series/{}/render_type/{}", parts[1], parts[3]);
    let body = expanded(
        parts[3],
        state.pointer(&root).unwrap(),
        state
            .pointer(&format!("{}/legend/content", panel_path(layer)))
            .unwrap(),
    );
    for end in 5..parts.len() {
        let prefix = format!("/{}", parts[..end].join("/"));
        if state.pointer(&prefix).is_none_or(Value::is_null) {
            let suffix = format!("/{}", parts[4..end].join("/"));
            let value = body
                .pointer(&suffix)
                .ok_or_else(|| invalid("diagram property owner changed"))?
                .clone();
            if let Some(node) = state.pointer_mut(&prefix) {
                *node = value;
            } else {
                let parent = format!("/{}", parts[..end - 1].join("/"));
                state
                    .pointer_mut(&parent)
                    .and_then(Value::as_object_mut)
                    .ok_or_else(|| invalid("diagram property owner changed"))?
                    .insert(parts[end - 1].into(), value);
            }
        }
    }
    Ok(())
}

/// Optional record styles retain their inherited/automatic meaning until edited.
pub(super) fn fields(
    out: &mut Vec<Field>,
    value: &Value,
    path: &str,
    group: &str,
    relative: &str,
) -> bool {
    if energy_optional(path) {
        let spectral = path.ends_with("/color_by_wavelength");
        field(
            out,
            json!(!value.is_null()),
            path,
            group,
            &format!("{relative}/enabled"),
            if spectral {
                "Color arrows by wavelength"
            } else {
                "Override transition color"
            },
        );
        if !value.is_null() {
            if spectral {
                optional::choice(
                    out,
                    &format!("{group}/{relative}/unit"),
                    &format!("{path}/unit"),
                    group,
                    "Wavelength unit",
                    value["unit"].clone(),
                    vec![json!("Nm"), json!("Angstrom"), json!("Um")],
                );
                for region in ["ultraviolet", "infrared"] {
                    field(
                        out,
                        value[region].clone(),
                        &format!("{path}/{region}"),
                        group,
                        &format!("{relative}/{region}"),
                        &human(region),
                    );
                }
            } else {
                field(
                    out,
                    value.clone(),
                    path,
                    group,
                    relative,
                    "Transition color",
                );
            }
        }
        return true;
    }
    if !path.contains("/Feynman/") {
        return false;
    }
    if path.contains("/vertices/") && path.ends_with("/marker") {
        let name = value.as_str().unwrap_or(if value.get("Blob").is_some() {
            "Blob"
        } else {
            "Inherit"
        });
        optional::choice(
            out,
            &format!("{group}/{relative}"),
            path,
            group,
            "Vertex marker",
            json!(name),
            ["Inherit", "Hidden", "Dot", "Cross", "CircledCross", "Blob"]
                .map(|v| json!(v))
                .to_vec(),
        );
        if let Some(blob) = value.get("Blob") {
            walk(
                out,
                blob,
                &format!("{path}/Blob"),
                group,
                &format!("{relative}/Blob"),
            );
        }
        return true;
    }
    let propagator_field = path
        .split_once("/propagators/")
        .is_some_and(|(_, tail)| tail.split('/').count() == 2);
    let momentum = propagator_field && path.ends_with("/momentum");
    let override_field = propagator_field
        && ["/color", "/width_px", "/bend"]
            .iter()
            .any(|suffix| path.ends_with(suffix))
        || path.contains("/marker/Blob/") && path.ends_with("/fill");
    if !momentum && !override_field {
        return false;
    }
    field(
        out,
        json!(!value.is_null()),
        path,
        group,
        &format!("{relative}/enabled"),
        if momentum {
            "Momentum arrow"
        } else if path.ends_with("/bend") {
            "Manual bend"
        } else if path.ends_with("/width_px") {
            "Override line width"
        } else {
            "Override color"
        },
    );
    if !value.is_null() {
        if momentum {
            for (key, child) in value.as_object().unwrap() {
                walk(
                    out,
                    child,
                    &format!("{path}/{key}"),
                    group,
                    &format!("{relative}/{key}"),
                );
            }
        } else {
            field(
                out,
                value.clone(),
                path,
                group,
                &format!("{relative}/value"),
                if path.ends_with("/bend") {
                    "Bend (degrees)"
                } else if path.ends_with("/width_px") {
                    "Width (px)"
                } else {
                    "Color"
                },
            );
        }
    }
    true
}

fn energy_optional(path: &str) -> bool {
    path.ends_with("/EnergyLevels/style/transition/color_by_wavelength")
        || path
            .split_once("/EnergyLevels/transitions/")
            .is_some_and(|(_, tail)| tail.split_once('/').is_some_and(|(_, key)| key == "color"))
}

#[pyfunction]
pub(crate) fn spectral_colors_json() -> PyResult<String> {
    serde_json::to_string(&renderer::energy_levels::SpectralColors::default()).map_err(runtime)
}

pub(super) fn apply(
    state: &mut Value,
    field: &Field,
    value: &Value,
    layer: renderer::LayerRef,
) -> PyResult<bool> {
    if field.id.ends_with("/enabled") && energy_optional(&field.path) {
        prepare_edit(state, &field.path, layer)?;
        let (parent, key) = field.path.rsplit_once('/').unwrap();
        let next = if !value
            .as_bool()
            .ok_or_else(|| invalid("override must be boolean"))?
        {
            Value::Null
        } else if key == "color_by_wavelength" {
            json!(renderer::energy_levels::SpectralColors::default())
        } else {
            let (root, _) = field.path.split_once("/transitions/").unwrap();
            state
                .pointer(&format!("{root}/style/transition/color"))
                .cloned()
                .unwrap_or_else(|| {
                    json!(
                        renderer::energy_levels::EnergyLevelSeries::default()
                            .style
                            .transition
                            .color
                    )
                })
        };
        state
            .pointer_mut(parent)
            .ok_or_else(|| invalid("transition style changed"))?[key] = next;
        return Ok(true);
    }
    if !field.path.contains("/Feynman/") {
        return Ok(false);
    }
    let marker = field.path.contains("/vertices/") && field.path.ends_with("/marker");
    let enabled = field.id.ends_with("/enabled")
        && (field.path.contains("/propagators/") || field.path.contains("/marker/Blob/"));
    if !marker && !enabled {
        return Ok(false);
    }
    let style = renderer::feynman::FeynmanSeries::default().style;
    let next = if marker {
        match value
            .as_str()
            .ok_or_else(|| invalid("marker must be a choice"))?
        {
            "Inherit" => Value::Null,
            "Blob" => json!({"Blob":{"radius_px":style.dot_radius,"fill":null}}),
            _ => value.clone(),
        }
    } else if !value
        .as_bool()
        .ok_or_else(|| invalid("override must be a boolean"))?
    {
        Value::Null
    } else if field.path.ends_with("/momentum") {
        let mut rich = state
            .pointer(&format!("{}/legend/content", panel_path(layer)))
            .unwrap()
            .clone();
        rich["segments"] = json!([]);
        serde_json::to_value(
            serde_json::from_value::<renderer::feynman::MomentumArrow>(json!({"label":rich}))
                .map_err(runtime)?,
        )
        .map_err(runtime)?
    } else if field.path.ends_with("/bend") {
        json!(0.)
    } else {
        let root = field.path.split("/Feynman/").next().unwrap().to_owned() + "/Feynman/style";
        let key = if field.path.ends_with("/width_px") {
            "width"
        } else {
            "color"
        };
        state
            .pointer(&format!("{root}/{key}"))
            .cloned()
            .unwrap_or(if key == "width" {
                json!(style.width)
            } else {
                json!(style.color)
            })
    };
    let (parent, key) = field.path.rsplit_once('/').unwrap();
    state
        .pointer_mut(parent)
        .and_then(Value::as_object_mut)
        .ok_or_else(|| invalid("diagram record changed"))?
        .insert(key.into(), next);
    Ok(true)
}
