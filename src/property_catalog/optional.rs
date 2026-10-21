//! Materialise optional style structures through ordinary contextual controls.
use super::*;

pub(super) fn choice(
    out: &mut Vec<Field>,
    id: &str,
    path: &str,
    group: &str,
    label: &str,
    value: Value,
    choices: Vec<Value>,
) {
    out.push(Field {
        id: id.into(),
        path: path.into(),
        group: group.into(),
        label: label.into(),
        kind: "choice".into(),
        value,
        choices,
        integer: false,
    });
}
fn button(
    out: &mut Vec<Field>,
    id: String,
    path: &str,
    group: &str,
    label: String,
    payload: Value,
) {
    out.push(Field {
        id,
        path: path.into(),
        group: group.into(),
        label,
        kind: "action".into(),
        value: payload,
        choices: vec![],
        integer: false,
    });
}
fn collection(
    out: &mut Vec<Field>,
    value: &Value,
    path: &str,
    group: &str,
    template: Value,
    sparse: bool,
) {
    // Empty structured arrays must not become comma-separated numeric inputs.
    out.retain(|v| v.path != path && !v.path.starts_with(&format!("{path}/")));
    let rows = value.as_array().cloned().unwrap_or_default();
    let mut template = template;
    if sparse {
        let mut index = 0;
        while rows.iter().any(|v| v["index"] == index) {
            index += 1;
        }
        template["index"] = json!(index);
    }
    let optional_style = group.starts_with("Marker ") || group.starts_with("Error-bar ");
    let added = if optional_style {
        if sparse {
            json!({"index":template["index"]})
        } else {
            json!({})
        }
    } else {
        template.clone()
    };
    button(
        out,
        format!("{group}/add"),
        path,
        group,
        format!("Add {}", if sparse { "point override" } else { "entry" }),
        json!({"append":added}),
    );
    for (i, row) in rows.iter().enumerate() {
        if !optional_style {
            walk(
                out,
                row,
                &format!("{path}/{i}"),
                group,
                &format!("entry/{}", i + 1),
            );
        }
        if let Some(defaults) = template.as_object() {
            for (key, value) in defaults {
                if optional_style && key != "index" {
                    field(
                        out,
                        json!(!row[key].is_null()),
                        &format!("{path}/{i}/{key}"),
                        group,
                        &format!("entry/{}/override/{key}", i + 1),
                        &format!(
                            "Entry {} · {} {}",
                            i + 1,
                            if sparse { "Override" } else { "Set" },
                            human(key)
                        ),
                    );
                    if let Some(actual) = row.get(key).filter(|v| !v.is_null()) {
                        walk(
                            out,
                            actual,
                            &format!("{path}/{i}/{key}"),
                            group,
                            &format!("entry/{}/{key}", i + 1),
                        );
                    }
                } else if optional_style && row.get(key).is_some() {
                    walk(
                        out,
                        &row[key],
                        &format!("{path}/{i}/{key}"),
                        group,
                        &format!("entry/{}/{key}", i + 1),
                    );
                } else if row.get(key).is_none() {
                    field(
                        out,
                        value.clone(),
                        &format!("{path}/{i}/{key}"),
                        group,
                        &format!("entry/{}/{key}", i + 1),
                        &format!("Entry {} · {}", i + 1, human(key)),
                    );
                }
            }
        }
        button(
            out,
            format!("{group}/remove/{i}"),
            path,
            group,
            format!("Remove entry {}", i + 1),
            json!({"remove":i,"entry":row}),
        );
    }
}
pub(super) fn style_lists(
    out: &mut Vec<Field>,
    _state: &Value,
    style: &Value,
    path: &str,
    error: bool,
    sources: &[Value],
) {
    let prefix = if error { "error_bar" } else { "point" };
    let group = if error {
        "Error-bar palette"
    } else {
        "Marker palette"
    };
    let template = if error {
        json!({"error_bar_color":style["error_bar_color"],"error_bar_width":style["error_bar_width"],"error_bar_cap_size":style["error_bar_cap_size"],"cap_width":style["cap_width"]})
    } else {
        json!({"point_color":style["point_color"],"point_size":style["point_size"],"point_shape":style["point_shape"]})
    };
    let table = format!("{prefix}_style_table");
    collection(
        out,
        &style[&table],
        &format!("{path}/{table}"),
        group,
        template.clone(),
        false,
    );
    let source = format!("{prefix}_style_index_column");
    let mut choices = vec![json!("None")];
    choices.extend_from_slice(sources);
    choice(
        out,
        &format!("{group}/source"),
        &format!("{path}/{source}"),
        group,
        "Style-index values (None disables palette)",
        style.get(&source).cloned().unwrap_or(json!("None")),
        choices,
    );
    let overrides = format!("{prefix}_style_overrides");
    collection(
        out,
        &style[&overrides],
        &format!("{path}/{overrides}"),
        if error {
            "Error-bar point overrides"
        } else {
            "Marker point overrides"
        },
        template,
        true,
    );
}
pub(super) fn contours(out: &mut Vec<Field>, _state: &Value, style: &Value, path: &str) {
    let colors = &style["per_level_color"];
    field(
        out,
        json!(colors.is_array()),
        &format!("{path}/per_level_color"),
        "Contours",
        "level_colors",
        "Use individual level colors",
    );
    if let Some(labels) = style.get("labels").filter(|v| v.is_object()) {
        field(
            out,
            json!(labels.get("bg_color").is_some()),
            &format!("{path}/labels/bg_color"),
            "Contour labels",
            "background",
            "Fill behind labels",
        );
        collection(
            out,
            &labels["anchors"],
            &format!("{path}/labels/anchors"),
            "Label positions",
            json!({"level_index":0,"x":0.,"y":0.,"tx":1.,"ty":0.}),
            false,
        );
    }
}
pub(super) fn bounded_series(
    out: &mut Vec<Field>,
    state: &Value,
    family: &str,
    item: &Value,
    path: &str,
) {
    let chart = &state[family];
    field(
        out,
        json!(item["style"].is_object()),
        &format!("{path}/style"),
        "Series style",
        "custom",
        "Use independent series style",
    );
    if family == "radial" {
        for key in ["label", "value", "explode", "color"] {
            walk(out, &item[key], &format!("{path}/{key}"), "Slice", key);
        }
        if item["style"].is_object() {
            walk(
                out,
                &item["style"],
                &format!("{path}/style"),
                "Series style",
                "style",
            );
        }
        for key in ["labels", "label_format", "label_color"] {
            field(
                out,
                json!(!item[key].is_null()),
                &format!("{path}/{key}"),
                "Slice labels",
                &format!("custom_{key}"),
                &format!("Override {}", human(key)),
            );
            if !item[key].is_null() {
                walk(
                    out,
                    &item[key],
                    &format!("{path}/{key}"),
                    "Slice labels",
                    key,
                );
            }
        }
    }
    if family == "boxplot" {
        walk(
            out,
            &item["values"],
            &format!("{path}/values"),
            "Summary statistics",
            "",
        );
    }
    if matches!(family, "categorical" | "boxplot")
        && chart["selected"]["series_id"] == item["id"]
        && !chart["selected"]["category_id"].is_null()
    {
        let selected = &chart["selected"];
        let current = chart["overrides"]
            .as_array()
            .unwrap()
            .iter()
            .enumerate()
            .find(|(_, v)| &v["target"] == selected);
        field(
            out,
            json!(current.is_some()),
            &format!("/{family}/overrides"),
            "Selected item",
            "custom",
            "Use independent item style",
        );
        if let Some((index, value)) = current {
            walk(
                out,
                value,
                &format!("/{family}/overrides/{index}"),
                "Selected item",
                "",
            );
        }
    }
}
pub(super) fn apply(result: &mut Value, field: &Field, value: &Value) -> PyResult<bool> {
    let timestamp = field.path.contains("/Timestamp/") && field.id.ends_with("/mode");
    let entry_override = field.id.contains("/override/")
        && (field.group.starts_with("Marker ") || field.group.starts_with("Error-bar "));
    let special = timestamp
        || entry_override
        || field.kind == "action"
        || field.id == "Series style/custom"
        || field.id.starts_with("Slice labels/custom_")
        || field.id == "Selected item/custom"
        || matches!(
            field.id.as_str(),
            "Pie / donut/mode"
                | "Detail shape/mode"
                | "Polar coordinates/interpolation_mode"
                | "Polar coordinates/limit_sector"
                | "Contours/level_colors"
                | "Contour labels/background"
        )
        || field.id == "Marker palette/source"
        || field.id == "Error-bar palette/source";
    if !special {
        return Ok(false);
    }
    let (parent, key) = field.path.rsplit_once('/').unwrap();
    let accepted = if entry_override {
        if value
            .as_bool()
            .ok_or_else(|| invalid("entry override control must be boolean"))?
        {
            let root = parent
                .rsplit_once('/')
                .unwrap()
                .0
                .rsplit_once('/')
                .unwrap()
                .0;
            result
                .pointer(root)
                .and_then(|v| v.get(key))
                .cloned()
                .ok_or_else(|| invalid("base series style changed"))?
        } else {
            Value::Null
        }
    } else if timestamp {
        match value.as_str().unwrap_or("") {
            "FixedOffsetMinutes" => json!({"FixedOffsetMinutes":0}),
            "Pattern" => json!({"Pattern":"%Y-%m-%d"}),
            "Fixed" => json!({"Fixed":3}),
            _ => value.clone(),
        }
    } else if field.id == "Selected item/custom" {
        let family = field.path.split('/').nth(1).unwrap();
        let target = result[family]["selected"].clone();
        let mut entries = result[family]["overrides"].as_array().unwrap().clone();
        entries.retain(|v| v["target"] != target);
        if value
            .as_bool()
            .ok_or_else(|| invalid("item style control must be boolean"))?
        {
            let chart = &result[family];
            let series = chart["series"]
                .as_array()
                .unwrap()
                .iter()
                .find(|v| v["id"] == target["series_id"])
                .ok_or_else(|| invalid("selected series no longer exists"))?;
            let mut item = json!({"target":target,"color":series["color"],"style":series.get("style").filter(|v|v.is_object()).unwrap_or(&chart["style"]),"labels":chart["labels"]});
            if family == "categorical" {
                item["label_format"] = chart["label_format"].clone();
            }
            entries.push(item);
        }
        json!(entries)
    } else if field.id == "Series style/custom" || field.id.starts_with("Slice labels/custom_") {
        let enabled = value
            .as_bool()
            .ok_or_else(|| invalid("override control must be boolean"))?;
        if !enabled {
            Value::Null
        } else {
            let family = field.path.split('/').nth(1).unwrap();
            let chart = &result[family];
            if field.id == "Series style/custom" && family == "radar" {
                let item = result.pointer(parent).unwrap();
                let mut fill = item["color"].clone();
                fill["a"] = chart["style"]["fill_opacity"].clone();
                json!({"line_width_px":chart["style"]["line_width_px"],"fill":fill,"marker":chart["style"]["marker"],"marker_size_px":chart["style"]["marker_size_px"]})
            } else if key == "label_color" && chart[key].is_null() {
                chart
                    .get("text_color")
                    .filter(|v| v.is_object())
                    .cloned()
                    .unwrap_or(json!({"r":0.,"g":0.,"b":0.,"a":1.}))
            } else {
                chart[key].clone()
            }
        }
    } else if field.kind == "action" {
        if value != &json!(true) {
            return Err(invalid("activate collection actions with true"));
        }
        let mut items = result
            .pointer(&field.path)
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        if let Some(item) = field.value.get("append") {
            items.push(item.clone());
        } else if let Some(index) = field.value["remove"].as_u64() {
            if index as usize >= items.len() {
                return Err(invalid("entry no longer exists"));
            }
            items.remove(index as usize);
        }
        json!(items)
    } else if field.id == "Pie / donut/mode" || field.id == "Detail shape/mode" {
        if value == "Pie" {
            json!("Pie")
        } else {
            json!({"Donut":{"inner_radius":0.5}})
        }
    } else if field.id == "Polar coordinates/interpolation_mode" {
        if value == "Chord" {
            json!("Chord")
        } else {
            json!({"Arc":{"pieces":16}})
        }
    } else if field.id.ends_with("palette/source") {
        if value == "None" {
            Value::Null
        } else {
            value.clone()
        }
    } else {
        let enabled = value
            .as_bool()
            .ok_or_else(|| invalid("enable control must be boolean"))?;
        if !enabled {
            Value::Null
        } else {
            match field.id.as_str() {
                "Polar coordinates/limit_sector" => json!([
                    0.,
                    if result.pointer(parent).unwrap()["angle_unit"] == "Radians" {
                        std::f64::consts::TAU
                    } else {
                        360.
                    }
                ]),
                "Contours/level_colors" => {
                    json!(vec![
                        result.pointer(parent).unwrap()["line"]["line_color"]
                            .clone();
                        result.pointer(parent).unwrap()["levels"]
                            .as_array()
                            .unwrap()
                            .len()
                    ])
                }
                _ => json!({"r":1.,"g":1.,"b":1.,"a":1.}),
            }
        }
    };
    result
        .pointer_mut(parent)
        .and_then(Value::as_object_mut)
        .ok_or_else(|| invalid("property owner changed"))?
        .insert(key.into(), accepted);
    Ok(true)
}
