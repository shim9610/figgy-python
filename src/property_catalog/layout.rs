//! One accepted-state path for document, panel and plot geometry.
use super::*;

pub(super) fn fields(out: &mut Vec<Field>, state: &Value, node: &navigation::Node) {
    let bounded = ["radial", "categorical", "boxplot", "radar"]
        .into_iter()
        .find(|k| state[*k].is_object());
    if node.kind == "figure" {
        let config: Config = serde_json::from_value(state["config"].clone()).unwrap();
        let area = config.document_area();
        for (key, value) in [("width", area.width), ("height", area.height)] {
            field(
                out,
                json!(value),
                &format!("/config/chart_area/{key}"),
                "Figure size",
                key,
                if key == "width" {
                    "Width (logical px)"
                } else {
                    "Height (logical px)"
                },
            );
        }
    }
    if node.kind != "panel" {
        return;
    }
    let path = bounded.map_or_else(
        || panel_path(node.layer),
        |kind| format!("/{kind}/decorations"),
    );
    let value = if bounded.is_some() {
        let a = &state.pointer(&path).unwrap()["data_area"];
        if a.is_object() {
            json!([a["x"], a["y"], a["width"], a["height"]])
        } else {
            json!([])
        }
    } else {
        let config: Config = serde_json::from_value(state.pointer(&path).unwrap().clone()).unwrap();
        match config.data_area() {
            Ok(a) => json!([
                a.0.x as f64 - config.chart_area.0.x as f64,
                a.0.y as f64 - config.chart_area.0.y as f64,
                a.0.width,
                a.0.height
            ]),
            Err(_) => json!([]),
        }
    };
    out.push(Field {
        id: "Plot area/bounds".into(),
        path: format!("{path}/data_area"),
        group: "Plot area".into(),
        label: "Position and size (logical px)".into(),
        kind: "rectangle".into(),
        value,
        choices: vec![],
        integer: false,
    });
    if bounded.is_some() {
        out.push(Field {
            id: "Plot area/automatic".into(),
            path: format!("{path}/data_area"),
            group: "Plot area".into(),
            label: "Use automatic plot layout".into(),
            kind: "action".into(),
            value: json!(true),
            choices: vec![],
            integer: false,
        });
    }
}

pub(super) fn apply(
    result: &mut Value,
    object: &Object,
    field: &Field,
    value: &Value,
) -> PyResult<bool> {
    if field.group == "Figure size" {
        let size = value
            .as_u64()
            .filter(|v| (100..=16384).contains(v))
            .ok_or_else(|| {
                invalid("Figure dimensions must be integers from 100 to 16384 logical pixels")
            })?;
        let key = field.path.rsplit('/').next().unwrap();
        let dimension = if key == "width" { 0 } else { 1 };
        if result["identity"]["layout"].is_object() {
            result["identity"]["layout"]["size"][dimension] = json!(size);
            reflow_grid(result)?;
        } else {
            let old = field.value.as_f64().unwrap();
            for config in std::iter::once(&mut result["config"]) {
                let scale = size as f64 / old;
                for name in [if dimension == 0 { "x" } else { "y" }, key] {
                    let v = config["chart_area"][name].as_f64().unwrap();
                    config["chart_area"][name] = json!((v * scale).round() as u32);
                }
                if let Some(panels) = config.get_mut("subplots").and_then(Value::as_array_mut) {
                    for panel in panels {
                        for name in [if dimension == 0 { "x" } else { "y" }, key] {
                            let v = panel["config"]["chart_area"][name].as_f64().unwrap();
                            panel["config"]["chart_area"][name] = json!((v * scale).round() as u32);
                        }
                    }
                }
            }
        }
        return Ok(true);
    }
    if field.id == "Plot area/automatic" {
        let (parent, key) = field.path.rsplit_once('/').unwrap();
        result
            .pointer_mut(parent)
            .ok_or_else(|| invalid("plot layout is unavailable"))?[key] = Value::Null;
        return Ok(true);
    }
    if field.id != "Plot area/bounds" {
        return Ok(false);
    }
    let a = value
        .as_array()
        .filter(|a| a.len() == 4)
        .ok_or_else(|| invalid("Plot bounds require x, y, width and height"))?;
    let a = a
        .iter()
        .map(|v| {
            v.as_f64()
                .filter(|v| v.is_finite())
                .ok_or_else(|| invalid("Plot bounds must be finite"))
        })
        .collect::<PyResult<Vec<_>>>()?;
    if a[2] < 1. || a[3] < 1. {
        return Err(invalid("Plot dimensions must be positive"));
    }
    if field.path.starts_with("/config") {
        let path = panel_path(object.layer);
        let mut config: Config =
            serde_json::from_value(result.pointer(&path).unwrap().clone()).map_err(invalid)?;
        let current = config.data_area().map_err(|e| invalid(format!("{e:?}")))?.0;
        let ca = config.chart_area.0;
        let changes = [
            (a[0] + ca.x as f64 - current.x as f64, "left_y"),
            (
                current.x as f64 + current.width as f64 - ca.x as f64 - a[0] - a[2],
                "right_y",
            ),
            (a[1] + ca.y as f64 - current.y as f64, "top_x"),
            (
                current.y as f64 + current.height as f64 - ca.y as f64 - a[1] - a[3],
                "bottom_x",
            ),
        ];
        for (delta, key) in changes {
            let axis = match key {
                "left_y" => &mut config.left_y,
                "right_y" => &mut config.right_y,
                "top_x" => &mut config.top_x,
                _ => &mut config.bottom_x,
            };
            axis.out_margin += delta as f32;
            if key == "right_y" {
                for overlay in &mut config.overlays {
                    overlay.y_axis.out_margin += delta as f32;
                }
            }
        }
        config.validate().map_err(|e| invalid(format!("{e:?}")))?;
        *result.pointer_mut(&path).unwrap() = serde_json::to_value(config).unwrap();
    } else {
        let (parent, key) = field.path.rsplit_once('/').unwrap();
        result.pointer_mut(parent).unwrap()[key] =
            json!({"x":a[0],"y":a[1],"width":a[2],"height":a[3]});
    }
    Ok(true)
}
