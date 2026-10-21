//! Shared property descriptions and stable-object commands for both editors.
//! Descriptions are derived from accepted SSOT; they are not a second model.
use super::*;

#[derive(Clone, Serialize)]
pub(crate) struct Field {
    pub id: String,
    pub path: String,
    pub group: String,
    pub label: String,
    pub kind: String,
    pub value: Value,
    pub choices: Vec<Value>,
    pub integer: bool,
}
#[derive(Serialize)]
pub(crate) struct Object {
    pub id: String,
    pub target: Option<String>,
    pub layer: renderer::LayerRef,
    pub fields: Vec<Field>,
    pub notices: Vec<String>,
}
fn human(key: &str) -> String {
    let friendly = match key {
        "ToBaseline" => Some("Baseline (data units)"),
        "StepPre" => Some("Step at start"),
        "StepPost" => Some("Step at end"),
        "StepMid" => Some("Step at midpoint"),
        "point_size" => Some("Marker radius (px)"),
        "width_px" => Some("Width (px)"),
        "head_length_px" => Some("Arrowhead length (px)"),
        "head_width_px" => Some("Arrowhead width (px)"),
        "min_length_px" => Some("Minimum arrow length (px)"),
        _ => None,
    };
    if let Some(value) = friendly {
        return value.into();
    }
    let value = key.replace('_', " ");
    let mut chars = value.chars();
    chars
        .next()
        .map(|c| c.to_uppercase().collect::<String>() + chars.as_str())
        .unwrap_or_default()
}
fn pointer(key: &str) -> String {
    key.replace('~', "~0").replace('/', "~1")
}
fn control_key(field: &Field) -> &str {
    match field.id.as_str() {
        "Color scale/axis/scale" => "color_scale",
        "Color scale/axis/min" => "vmin",
        "Color scale/axis/max" => "vmax",
        _ => field.path.rsplit('/').next().unwrap_or(""),
    }
}
fn choices(path: &str, value: &Value) -> Vec<Value> {
    let key = path.rsplit('/').next().unwrap_or("");
    let values: &[&str] = match key {
        "material" if path.starts_with("/radial/") => &[
            "Flat",
            "Matte",
            "Ceramic",
            "BrushedMetal",
            "Paper",
            "Wood",
            "SatinMetal",
            "Toon",
            "Enamel",
            "Hatch",
            "Pearl",
        ],
        "material" if path.starts_with("/boxplot/") => &["Flat", "Matte", "SatinMetal"],
        "material" => &["Flat", "Matte", "SatinMetal", "Enamel", "Paper"],
        "labels" if path.starts_with("/radial/") => &["None", "Inside", "Outside"],
        "labels" if path.starts_with("/boxplot/") => &["None", "Median", "MedianAndCount"],
        "labels" if path.starts_with("/radar/") => &["None", "Values", "Emphasized"],
        "labels" if value.is_string() => &["None", "Inside", "Outside", "Auto"],
        "label_format" if path.starts_with("/radial/") => &[
            "Name",
            "Value",
            "Percent",
            "NamePercent",
            "NameValue",
            "ValuePercent",
            "NameValuePercent",
        ],
        "label_format" => &["Value", "Percent", "ValuePercent", "CategoryValue"],
        "mode" if path.starts_with("/categorical/") => &["Grouped", "Stacked", "PercentStacked"],
        "outlier_shape" => &["Circle", "Square"],
        "marker" => &["None", "Circle", "Square"],
        "grid_layout" => &["Centers", "Edges"],
        "orientation" if value == "ColumnsAreY" || value == "ColumnsAreX" => {
            &["ColumnsAreY", "ColumnsAreX"]
        }
        "interpolation" if path.contains("/polar/") => &["Chord", "Arc"],
        "line_style" => &[
            "Solid",
            "Dash",
            "Dot",
            "DashDot",
            "DashDotDot",
            "ShortDash",
            "ShortDot",
            "ShortDashDot",
            "LongDash",
            "LongDashDot",
            "LongDashDotDot",
        ],
        "interpolation" if value.is_string() => &["Linear", "StepPre", "StepPost", "StepMid"],
        "point_shape" => &[
            "Circle",
            "Square",
            "Triangle",
            "Diamond",
            "Cross",
            "CircleFilled",
            "SquareFilled",
            "TriangleFilled",
            "DiamondFilled",
            "TriangleDown",
            "TriangleLeft",
            "TriangleRight",
            "Plus",
            "Pentagon",
            "Hexagon",
            "Octagon",
            "Star",
            "TriangleDownFilled",
            "TriangleLeftFilled",
            "TriangleRightFilled",
            "PlusFilled",
            "CrossFilled",
            "PentagonFilled",
            "HexagonFilled",
            "OctagonFilled",
            "StarFilled",
        ],
        "pivot" => &["Tail", "Middle", "Tip"],
        "orientation" | "direction" if value == "Vertical" || value == "Horizontal" => {
            &["Vertical", "Horizontal"]
        }
        "scale" if value == "Area" || value == "Radius" => &["Area", "Radius"],
        "scale" if value == "Linear" || value == "Logarithmic" => &["Linear", "Logarithmic"],
        "colormap" => &["Viridis", "Magma", "Turbo", "GrayScale", "RdBu"],
        "side" => &["Left", "Right", "Top", "Bottom"],
        "tick" => &["None", "Inside", "Outside", "Both"],
        "angle_unit" => &["Radians", "Degrees"],
        "grid_shape" => &["Polygon", "Circle"],
        "align" if value.is_string() => &["Left", "Center", "Right"],
        _ => &[],
    };
    values.iter().map(|v| json!(v)).collect()
}
fn field(out: &mut Vec<Field>, value: Value, path: &str, group: &str, relative: &str, label: &str) {
    let options = choices(path, &value);
    let kind = if !options.is_empty() {
        "choice"
    } else if value.is_boolean() {
        "boolean"
    } else if value.is_number() {
        "number"
    } else if value.is_string() {
        "text"
    } else if value.is_object() && ["r", "g", "b", "a"].iter().all(|k| value[*k].is_number()) {
        "color"
    } else if value.is_array() && value.as_array().unwrap().iter().all(Value::is_number) {
        "numbers"
    } else {
        return;
    };
    out.push(Field {
        id: format!("{group}/{relative}"),
        path: path.into(),
        group: group.into(),
        label: label.into(),
        kind: kind.into(),
        integer: value.is_u64() || value.is_i64(),
        value,
        choices: options,
    });
}
fn walk(out: &mut Vec<Field>, value: &Value, path: &str, group: &str, relative: &str) {
    if value.is_object() && !["r", "g", "b", "a"].iter().all(|k| value[*k].is_number()) {
        for (key, child) in value.as_object().unwrap() {
            if [
                "id",
                "series_id",
                "x_column",
                "y_column",
                "source_id",
                "column",
                "columns",
                "components",
                "segments",
                "point_style_index_column",
                "error_bar_style_index_column",
            ]
            .contains(&key.as_str())
                || (key == "labels" && child.is_object())
            {
                continue;
            }
            walk(
                out,
                child,
                &format!("{path}/{}", pointer(key)),
                group,
                &if relative.is_empty() {
                    key.clone()
                } else {
                    format!("{relative}/{key}")
                },
            );
        }
    } else if value.is_array() && !value.as_array().unwrap().iter().all(Value::is_number) {
        for (i, child) in value.as_array().unwrap().iter().enumerate() {
            walk(
                out,
                child,
                &format!("{path}/{i}"),
                group,
                &format!("{relative}/{i}"),
            );
        }
    } else {
        let label = relative
            .split('/')
            .map(human)
            .collect::<Vec<_>>()
            .join(" · ");
        field(out, value.clone(), path, group, relative, &label);
    }
}
fn panel_path(layer: renderer::LayerRef) -> String {
    match layer {
        renderer::LayerRef::Subplot(i) | renderer::LayerRef::SubplotOverlay(i, _) => {
            format!("/config/subplots/{i}/config")
        }
        _ => "/config".into(),
    }
}
fn add_default(
    out: &mut Vec<Field>,
    state: &Value,
    path: &str,
    group: &str,
    key: &str,
    value: Value,
) {
    if state.pointer(path).is_none() {
        field(out, value, path, group, key, &human(key));
    }
}
fn columns(state: &Value) -> Vec<Value> {
    fn visit(value: &Value, key: &str, out: &mut std::collections::BTreeSet<String>) {
        match value {
            Value::String(s)
                if ["x_column", "y_column", "column", "u", "v", "lower", "upper"]
                    .contains(&key) =>
            {
                out.insert(s.clone());
            }
            Value::Array(a) if key == "columns" => {
                for v in a {
                    if let Some(s) = v.as_str() {
                        out.insert(s.into());
                    }
                }
            }
            Value::Object(o) => {
                for (k, v) in o {
                    visit(v, k, out);
                }
            }
            Value::Array(a) => {
                for v in a {
                    visit(v, "", out);
                }
            }
            _ => {}
        }
    }
    let mut out = std::collections::BTreeSet::new();
    visit(&state["series"], "", &mut out);
    out.into_iter().map(Value::String).collect()
}
fn source_field(out: &mut Vec<Field>, value: Value, path: &str, group: &str, sources: &[Value]) {
    let mut choices = vec![json!("Fixed")];
    choices.extend_from_slice(sources);
    out.push(Field {
        id: format!("{group}/source"),
        path: path.into(),
        group: group.into(),
        label: if group == "Color mapping" {
            "Color values"
        } else {
            "Size values"
        }
        .into(),
        kind: "choice".into(),
        value,
        choices,
        integer: false,
    });
}
fn colorbar_fields(out: &mut Vec<Field>, state: &Value, panel: &str) {
    let root = format!("{panel}/colorbar");
    let Some(bar) = state.pointer(&root).filter(|v| v.is_object()) else {
        return;
    };
    for (path, label) in [
        ("colormap", "Colormap"),
        ("axis/scale", "Scale"),
        ("axis/min", "Minimum"),
        ("axis/max", "Maximum"),
    ] {
        field(
            out,
            bar.pointer(&format!("/{path}")).unwrap().clone(),
            &format!("{root}/{path}"),
            "Color scale",
            path,
            label,
        );
    }
    let mut rest = bar.clone();
    rest.as_object_mut().unwrap().remove("axis");
    rest.as_object_mut().unwrap().remove("colormap");
    walk(out, &rest, &root, "Colorbar layout", "");
    let mut axis = bar["axis"].clone();
    for key in ["scale", "min", "max"] {
        axis.as_object_mut().unwrap().remove(key);
    }
    walk(
        out,
        &axis,
        &format!("{root}/axis"),
        "Colorbar ticks and labels",
        "",
    );
}
fn build(state: &Value, node: &navigation::Node) -> Object {
    let mut out = Object {
        id: node.key.clone(),
        target: node.target.clone(),
        layer: node.layer,
        fields: vec![],
        notices: vec![],
    };
    let fields = &mut out.fields;
    let target = node.target.as_deref().unwrap_or("figure");
    let short = target.rsplit(':').next().unwrap_or(target);
    let panel = panel_path(node.layer);
    let bounded = ["radial", "categorical", "boxplot", "radar"]
        .into_iter()
        .find(|k| state.get(*k).is_some());
    if let Some((index, series)) = state["series"]
        .as_array()
        .filter(|_| node.key.starts_with("series/"))
        .and_then(|v| v.iter().enumerate().find(|(_, s)| s["series_id"] == target))
    {
        for (kind, style) in series["render_type"].as_object().unwrap() {
            let root = format!("/series/{index}/render_type/{kind}");
            for (key, value) in style.as_object().unwrap() {
                if ["components", "err_x", "err_y", "yErr"].contains(&key.as_str()) {
                    continue;
                }
                let group = match key.as_str() {
                    "line" => "Line",
                    "scatter" => "Markers",
                    "bar" => "Bars",
                    "err_style" => "Error bars",
                    "contour" => "Contours",
                    "style" if kind == "Vector" => "Vectors",
                    _ => "Appearance",
                };
                let path = format!("{root}/{key}");
                walk(fields, value, &path, group, "");
                if key == "line" {
                    add_default(
                        fields,
                        state,
                        &format!("{path}/interpolation"),
                        group,
                        "interpolation",
                        json!("Linear"),
                    );
                    let enabled = value.get("fill").is_some_and(|v| !v.is_null());
                    field(
                        fields,
                        json!(enabled),
                        &format!("{path}/fill"),
                        "Area fill",
                        "enabled",
                        "Fill below / between lines",
                    );
                    if enabled {
                        let mode = if value["fill"].get("ToSeries").is_some() {
                            "Series"
                        } else {
                            "Baseline"
                        };
                        let mut mode_field = Field {
                            id: "Area fill/mode".into(),
                            path: format!("{path}/fill"),
                            group: "Area fill".into(),
                            label: "Fill to".into(),
                            kind: "choice".into(),
                            value: json!(mode),
                            choices: vec![json!("Baseline"), json!("Series")],
                            integer: false,
                        };
                        let compatible = state["series"]
                            .as_array()
                            .unwrap()
                            .iter()
                            .filter(|s| {
                                s["series_id"] != series["series_id"]
                                    && s["x_column"] == series["x_column"]
                                    && s["render_type"].as_object().is_some_and(|v| {
                                        v.values().any(|v| v.get("line").is_some())
                                    })
                            })
                            .map(|s| s["series_id"].clone())
                            .collect::<Vec<_>>();
                        if compatible.is_empty() {
                            mode_field.choices = vec![json!("Baseline")];
                        }
                        fields.push(mode_field);
                        if mode == "Series" {
                            fields.push(Field {
                                id: "Area fill/series".into(),
                                path: format!("{path}/fill/ToSeries"),
                                group: "Area fill".into(),
                                label: "Reference series".into(),
                                kind: "choice".into(),
                                value: value["fill"]["ToSeries"].clone(),
                                choices: compatible,
                                integer: false,
                            });
                        }
                        add_default(
                            fields,
                            state,
                            &format!("{path}/fill_color"),
                            "Area fill",
                            "fill_color",
                            {
                                let mut color = value["line_color"].clone();
                                color["a"] = json!(0.25);
                                color
                            },
                        );
                    }
                }
                if key == "scatter" {
                    let sources = columns(state);
                    source_field(
                        fields,
                        value["point_color_map"]
                            .get("column")
                            .cloned()
                            .unwrap_or(json!("Fixed")),
                        &format!("{path}/point_color_map"),
                        "Color mapping",
                        &sources,
                    );
                    source_field(
                        fields,
                        value["point_size_map"]
                            .get("column")
                            .cloned()
                            .unwrap_or(json!("Fixed")),
                        &format!("{path}/point_size_map"),
                        "Size mapping",
                        &sources,
                    );
                }
                if kind == "Vector" && key == "style" {
                    add_default(
                        fields,
                        state,
                        &format!("{path}/min_length_px"),
                        group,
                        "min_length_px",
                        json!(0.),
                    );
                    fields.push(Field {
                        id: "Vectors/scale_mode".into(),
                        path: format!("{path}/scale"),
                        group: group.into(),
                        label: "Length units".into(),
                        kind: "choice".into(),
                        value: json!(if value["scale"].get("Data").is_some() {
                            "Data"
                        } else {
                            "Pixels"
                        }),
                        choices: vec![json!("Pixels"), json!("Data")],
                        integer: false,
                    });
                }
                if key == "contour" {
                    // A label is optional in SSOT. Enabling it creates the
                    // host's initial label style, then exposes its controls.
                    field(
                        fields,
                        json!(value.get("labels").is_some_and(|v| !v.is_null())),
                        &format!("{path}/labels"),
                        "Contours",
                        "show_labels",
                        "Show contour labels",
                    );
                    if value.get("labels").is_some_and(|v| !v.is_null()) {
                        walk(
                            fields,
                            &value["labels"],
                            &format!("{path}/labels"),
                            "Contour labels",
                            "",
                        );
                    }
                }
            }
        }
        colorbar_fields(fields, state, &panel);
        out.notices.push(format!(
            "Data: {} · {}. Source arrays stay resident.",
            series["x_column"].as_str().unwrap_or(""),
            series["y_column"].as_str().unwrap_or("")
        ));
        let style = series["render_type"]
            .as_object()
            .unwrap()
            .values()
            .next()
            .unwrap();
        if style["scatter"].is_object() {
            let mapped = style["scatter"].get("point_color_map").is_some();
            let overrides = style["scatter"]["point_style_overrides"]
                .as_array()
                .map_or(0, |v| {
                    v.iter().filter(|v| v.get("point_color").is_some()).count()
                });
            out.notices.push(if mapped {format!("Colors use {}. {overrides} explicit point-color overrides take precedence.",style["scatter"]["point_color_map"]["column"].as_str().unwrap_or("values"))} else {"Colors are fixed RGB. Changing an independent colorbar does not recolor this series.".into()});
        }
    } else if let Some(kind) = bounded {
        let root = format!("/{kind}");
        let chart = &state[kind];
        for key in [
            "style",
            "labels",
            "label_format",
            "label_decimals",
            "value_suffix",
            "mode",
            "direction",
            "group_width",
            "bar_gap",
            "box_gap",
            "start_angle_degrees",
            "ring_spacing",
            "background",
            "text_color",
            "label_color",
        ] {
            if let Some(value) = chart.get(key) {
                walk(
                    fields,
                    value,
                    &format!("{root}/{key}"),
                    if key == "style" {
                        "Chart style"
                    } else {
                        "Chart options"
                    },
                    if key == "style" { "" } else { key },
                );
            }
        }
        if kind == "radial" {
            walk(
                fields,
                &chart["kind"],
                &format!("{root}/kind"),
                "Pie / donut",
                "",
            );
        }
        if let Some(index) = chart["series"]
            .as_array()
            .and_then(|v| v.iter().position(|s| s["id"] == target))
        {
            let item = &chart["series"][index];
            for key in ["color", "style"] {
                if let Some(v) = item.get(key) {
                    walk(
                        fields,
                        v,
                        &format!("{root}/series/{index}/{key}"),
                        "Series style",
                        key,
                    );
                }
            }
        }
    } else {
        let config = state.pointer(&panel).unwrap();
        let path = if short == "chart_title" {
            Some(format!("{panel}/chart_title"))
        } else if short == "legend" {
            Some(format!("{panel}/legend"))
        } else if short.starts_with("colorbar") {
            Some(format!("{panel}/colorbar"))
        } else if short == "data_area" {
            Some(format!("{panel}/chart_area"))
        } else if short.starts_with("axis_") || short.starts_with("tick_labels_") {
            let side = short.rsplit('_').next().unwrap();
            let axis = match side {
                "bottom" => "bottom_x",
                "top" => "top_x",
                "left" => "left_y",
                _ => "right_y",
            };
            let base = match node.layer {
                renderer::LayerRef::Overlay(i) | renderer::LayerRef::SubplotOverlay(_, i)
                    if side == "right" =>
                {
                    format!("{panel}/overlays/{i}/y_axis")
                }
                _ => format!("{panel}/{axis}"),
            };
            Some(if short.starts_with("axis_title_") {
                format!("{base}/title_option")
            } else if short.starts_with("tick_labels_") {
                format!("{base}/label_style")
            } else {
                base
            })
        } else {
            None
        };
        if short.starts_with("colorbar") {
            colorbar_fields(fields, state, &panel);
        } else if let Some(path) = path {
            if let Some(value) = state.pointer(&path) {
                walk(
                    fields,
                    value,
                    &path,
                    if short == "data_area" {
                        "Panel geometry"
                    } else {
                        "Layout and appearance"
                    },
                    "",
                );
            }
        }
        if short == "data_area" || target == "figure" {
            if let Some(polar) = config.get("polar") {
                walk(
                    fields,
                    polar,
                    &format!("{panel}/polar"),
                    "Polar coordinates",
                    "",
                );
            }
            walk(
                fields,
                &config["grid"],
                &format!("{panel}/grid"),
                "Grid",
                "",
            );
        }
        if target == "figure" {
            if let Some(layout) = state["identity"].get("layout").filter(|v| v.is_object()) {
                for key in ["gap", "row_weights", "column_weights"] {
                    walk(
                        fields,
                        &layout[key],
                        &format!("/identity/layout/{key}"),
                        "Figure grid",
                        key,
                    );
                }
                for (slot, value) in layout["placement"].as_object().unwrap() {
                    fields.push(Field {
                        id: format!("Figure grid/slot/{slot}"),
                        path: format!("/identity/layout/placement/{}", pointer(slot)),
                        group: "Figure grid".into(),
                        label: format!("Chart in slot {slot}"),
                        kind: "choice".into(),
                        value: value.clone(),
                        choices: state["identity"]["panels"]
                            .as_array()
                            .unwrap()
                            .iter()
                            .map(|v| v["id"].clone())
                            .collect(),
                        integer: false,
                    });
                }
            }
        }
    }
    out
}

impl editor::Editor {
    pub(super) fn catalog_properties(
        &mut self,
        ui: &mut egui::Ui,
        c: &mut FigureAccess<'_>,
        target: &str,
        primary: bool,
    ) {
        let objects = catalog(&c.snapshot());
        let layer = c
            .data
            .document
            .as_ref()
            .map_or(c.data.chart.config().active_layer(), |d| {
                d.chart.active_layer()
            });
        let matches = |v: &&Object| {
            v.target.as_deref() == Some(target) && (target == "figure" || v.layer == layer)
        };
        let object = objects
            .iter()
            .filter(matches)
            .find(|v| self.inspector_owner.as_ref() == Some(&v.id))
            .or_else(|| {
                objects.iter().find(|v| {
                    v.target.as_deref() == Some(target) && (target == "figure" || v.layer == layer)
                })
            });
        let Some(object) = object else {
            return;
        };
        let mut groups = Vec::<String>::new();
        for field in &object.fields {
            if !groups.contains(&field.group) {
                groups.push(field.group.clone());
            }
        }
        let covered = self
            .controls
            .keys()
            .cloned()
            .collect::<std::collections::HashSet<_>>();
        for (index, group) in groups.iter().enumerate() {
            let fields = object
                .fields
                .iter()
                .filter(|f| &f.group == group)
                .filter(|f| {
                    let key = f.path.rsplit('/').next().unwrap();
                    primary
                        || (!covered.contains(key)
                            && !(key == "scale" && covered.contains("axis_scale"))
                            && !(key == "tick" && covered.contains("tick_direction")))
                })
                .collect::<Vec<_>>();
            if fields.is_empty() {
                continue;
            }
            let response = egui::CollapsingHeader::new(group)
                .id_salt((&object.id, group))
                .default_open(primary && index < 2)
                .show(ui, |ui| {
                    for field in fields {
                        let mut value = field.value.clone();
                        let mut changed = false;
                        let response = match field.kind.as_str() {
                            "boolean" => {
                                let mut v = value.as_bool().unwrap();
                                let r = ui.checkbox(&mut v, &field.label);
                                changed = r.changed();
                                value = json!(v);
                                r
                            }
                            "number" => {
                                ui.label(&field.label);
                                let mut v = value.as_f64().unwrap();
                                let r =
                                    ui.add(egui::DragValue::new(&mut v).speed(if field.integer {
                                        1.
                                    } else {
                                        0.1
                                    }));
                                changed = r.changed();
                                value = if field.integer && v >= 0. && v.fract() == 0. {
                                    json!(v as u64)
                                } else {
                                    json!(v)
                                };
                                r
                            }
                            "color" => {
                                ui.label(&field.label);
                                let mut rgba = [
                                    value["r"].as_f64().unwrap() as f32,
                                    value["g"].as_f64().unwrap() as f32,
                                    value["b"].as_f64().unwrap() as f32,
                                    value["a"].as_f64().unwrap() as f32,
                                ];
                                let r = ui.color_edit_button_rgba_unmultiplied(&mut rgba);
                                changed = r.changed();
                                value = json!({"r":rgba[0],"g":rgba[1],"b":rgba[2],"a":rgba[3]});
                                r
                            }
                            "choice" => {
                                ui.label(&field.label);
                                egui::ComboBox::from_id_salt((&object.id, &field.id))
                                    .selected_text(value.as_str().unwrap_or(""))
                                    .show_ui(ui, |ui| {
                                        for choice in &field.choices {
                                                let response=ui.selectable_value(
                                                    &mut value,
                                                    choice.clone(),
                                                    human(choice.as_str().unwrap_or("")),
                                                    );
                                                changed|=response.changed();
                                                self.controls.insert(format!("{}_{}",control_key(field),choice.as_str().unwrap_or("")),response.rect);
                                        }
                                    })
                                    .response
                            }
                            _ => {
                                ui.label(&field.label);
                            let initial = if field.kind == "numbers" {
                                    value
                                        .as_array()
                                        .unwrap()
                                        .iter()
                                        .map(Value::to_string)
                                        .collect::<Vec<_>>()
                                        .join(", ")
                                } else {
                                    value.as_str().unwrap_or("").to_owned()
                                };
                            let id=ui.make_persistent_id((&object.id,&field.id));
                            let focused=ui.memory(|m|m.has_focus(id));
                            let draft=self.property_text.entry(format!("{}/{}",object.id,field.id)).or_insert_with(||(initial.clone(),field.value.clone(),c.data.revision));
                            if !focused&&draft.1!=field.value {*draft=(initial,field.value.clone(),c.data.revision);}
                            let r = ui.add(egui::TextEdit::singleline(&mut draft.0).id(id));
                            if r.gained_focus(){draft.1=field.value.clone();draft.2=c.data.revision;}
                                if r.lost_focus() {
                                let text=&draft.0;
                                    let parsed = if field.kind == "numbers" {
                                        text.split([',', ';', ' '])
                                            .filter(|v| !v.is_empty())
                                            .map(|v| {
                                                v.parse::<f64>().map(|v| json!(v)).map_err(invalid)
                                            })
                                            .collect::<PyResult<Vec<_>>>()
                                            .map(Value::Array)
                                    } else {
                                    Ok(json!(text))
                                    };
                                    match parsed {
                                        Ok(v) => {
                                            changed = v != field.value;
                                            value = v;
                                        if changed&&draft.2!=c.data.revision {changed=false;self.error="stale edit: the Figure changed; refresh and retry".into();}
                                        }
                                        Err(e) => self.error = e.to_string(),
                                    }
                                }
                                r
                            }
                        };
                        self.controls
                            .insert(format!("property:{}", field.id), response.rect);
                        self.controls
                            .entry(control_key(field).to_owned())
                            .or_insert(response.rect);
                        if changed {
                            let mut extents=json!(c.data.columns.iter().map(|(name,(_,min,max))|(name.clone(),json!([min,max]))).collect::<serde_json::Map<_,_>>());
                            if field.id=="Color scale/axis/scale"&&value=="Logarithmic" {
                                if let Ok(bounds)=c.log_bounds_for("z",object.layer){extents["_positive"]=json!(bounds);}
                            }
                            match apply(&c.snapshot(), &object.id, &field.id, value, &extents)
                                .and_then(|v| c.apply_settings(&v.to_string()))
                            {
                                Ok(()) => self.error.clear(),
                                Err(e) => self.error = e.to_string(),
                            }
                        }
                    }
                });
            self.controls
                .insert(format!("section:{group}"), response.header_response.rect);
        }
        for notice in &object.notices {
            ui.small(notice);
        }
    }
}
pub(crate) fn catalog(state: &Settings) -> Vec<Object> {
    fn visit(nodes: &[navigation::Node], state: &Value, out: &mut Vec<Object>) {
        for node in nodes {
            if node.target.is_some() || node.kind == "figure" {
                out.push(build(state, node));
            }
            visit(&node.children, state, out);
        }
    }
    let mut out = vec![];
    visit(
        &navigation::nodes(state),
        &serde_json::to_value(state).unwrap(),
        &mut out,
    );
    out
}
pub(crate) fn apply(
    state: &Settings,
    object: &str,
    property: &str,
    value: Value,
    extents: &Value,
) -> PyResult<Value> {
    let objects = catalog(state);
    let object = objects
        .iter()
        .find(|v| v.id == object)
        .ok_or_else(|| invalid("unknown or removed chart object"))?;
    let field = object
        .fields
        .iter()
        .find(|v| v.id == property)
        .ok_or_else(|| invalid("property is not editable for this object"))?;
    if !field.choices.is_empty() && !field.choices.contains(&value) {
        return Err(invalid("unsupported property choice"));
    }
    let mut result = serde_json::to_value(state).map_err(runtime)?;
    let (parent, key) = field.path.rsplit_once('/').unwrap();
    let value = if field.id == "Color mapping/source" || field.id == "Size mapping/source" {
        if value == "Fixed" {
            Value::Null
        } else {
            let column = value
                .as_str()
                .ok_or_else(|| invalid("choose a resident value column"))?;
            let bounds = extents[column]
                .as_array()
                .filter(|v| v.len() == 2)
                .ok_or_else(|| invalid("value column has no recorded finite domain"))?;
            let min = bounds[0]
                .as_f64()
                .ok_or_else(|| invalid("invalid value domain"))?;
            let mut max = bounds[1]
                .as_f64()
                .ok_or_else(|| invalid("invalid value domain"))?;
            if min == max {
                max = min + (min.abs() * 0.01).max(1.);
            }
            if field.id == "Color mapping/source" {
                let panel = panel_path(object.layer);
                let bar_path = format!("{panel}/colorbar");
                if result.pointer(&bar_path).is_none_or(Value::is_null) {
                    let mut bar = renderer::default::default_colorbar_options();
                    bar.axis.min = min;
                    bar.axis.max = max;
                    result
                        .pointer_mut(&panel)
                        .unwrap()
                        .as_object_mut()
                        .unwrap()
                        .insert("colorbar".into(), serde_json::to_value(bar).unwrap());
                }
                json!({"column":column})
            } else {
                json!({"column":column,"domain_min":min,"domain_max":max,"min_px":2.,"max_px":12.,"scale":"Area"})
            }
        }
    } else if field.id == "Vectors/scale_mode" {
        if value == "Data" {
            json!({"Data":{"factor":1.}})
        } else {
            json!({"Pixels":{"px_per_unit":1.}})
        }
    } else if field.id == "Contours/show_labels" {
        if value == true {
            json!({"visible":true,"font_size":12.,"color":{"r":0.,"g":0.,"b":0.,"a":1.},"format":"Decimal","significant_digits":3,"spacing_px":120.,"anchors":[],"bg_padding_px":2.})
        } else if value == false {
            Value::Null
        } else {
            return Err(invalid("show labels must be boolean"));
        }
    } else if field.id == "Area fill/enabled" {
        if value == true {
            json!({"ToBaseline":0.})
        } else if value == false {
            Value::Null
        } else {
            return Err(invalid("fill enabled must be boolean"));
        }
    } else if field.id == "Area fill/mode" {
        if value == "Baseline" {
            json!({"ToBaseline":0.})
        } else {
            let index = field
                .path
                .split('/')
                .nth(2)
                .unwrap()
                .parse::<usize>()
                .map_err(invalid)?;
            let peer = state
                .series
                .iter()
                .find(|s| {
                    s.series_id != state.series[index].series_id
                        && s.x_column == state.series[index].x_column
                        && serde_json::to_value(&s.render_type)
                            .unwrap()
                            .as_object()
                            .unwrap()
                            .values()
                            .any(|v| v.get("line").is_some())
                })
                .ok_or_else(|| invalid("fill needs a line with the same x column"))?;
            json!({"ToSeries":peer.series_id})
        }
    } else {
        value
    };
    if field.path.starts_with("/identity/layout/placement/") {
        let this_slot = key.replace("~1", "/").replace("~0", "~");
        let placement = result["identity"]["layout"]["placement"]
            .as_object_mut()
            .unwrap();
        let other = placement
            .iter()
            .find(|(slot, v)| **slot != this_slot && **v == value)
            .map(|(slot, _)| slot.clone());
        if let Some(other) = other {
            placement.insert(other, field.value.clone());
        }
    }
    if let Some(node) = result.pointer_mut(&field.path) {
        *node = value;
    } else {
        result
            .pointer_mut(parent)
            .and_then(Value::as_object_mut)
            .ok_or_else(|| invalid("property owner changed"))?
            .insert(key.replace("~1", "/").replace("~0", "~"), value);
    }
    if field.id == "Color scale/axis/scale" {
        let axis = result.pointer_mut(parent).unwrap();
        if axis["scale"] == "Logarithmic" && axis["min"].as_f64().is_some_and(|v| v <= 0.) {
            let bounds = extents["_positive"]
                .as_array()
                .filter(|v| v.len() == 2)
                .ok_or_else(|| {
                    invalid("set a positive color domain before choosing logarithmic scale")
                })?;
            axis["min"] = bounds[0].clone();
            axis["max"] = bounds[1].clone();
        }
        axis["major_spacing"] = if axis["scale"] == "Logarithmic" {
            json!(1.)
        } else {
            json!((axis["max"].as_f64().unwrap() - axis["min"].as_f64().unwrap()) / 5.)
        };
    }
    if field.path.starts_with("/identity/layout/placement/")
        || field.path == "/identity/layout/gap"
        || field.path == "/identity/layout/row_weights"
        || field.path == "/identity/layout/column_weights"
    {
        reflow_grid(&mut result)?;
    }
    if field.group == "Panel geometry" {
        result["identity"]["layout"] = Value::Null;
    }
    Ok(result)
}

fn reflow_grid(state: &mut Value) -> PyResult<()> {
    let layout = &state["identity"]["layout"];
    let gap = layout["gap"]
        .as_f64()
        .ok_or_else(|| invalid("grid gap must be finite and nonnegative"))?;
    if !gap.is_finite() || gap < 0. {
        return Err(invalid("grid gap must be finite and nonnegative"));
    }
    let positions = |key: &str, dimension: usize| -> PyResult<Vec<f64>> {
        let weights = layout[key]
            .as_array()
            .ok_or_else(|| invalid("grid weights must be a number list"))?
            .iter()
            .map(|v| {
                v.as_f64()
                    .filter(|v| v.is_finite() && *v > 0.)
                    .ok_or_else(|| invalid("grid weights must be positive and finite"))
            })
            .collect::<PyResult<Vec<_>>>()?;
        let expected = if dimension == 0 {
            layout["grid"][0].as_array().map_or(0, Vec::len)
        } else {
            layout["grid"].as_array().map_or(0, Vec::len)
        };
        if weights.len() != expected || weights.is_empty() {
            return Err(invalid("grid weight count must match the grid"));
        }
        let size = layout["size"][dimension]
            .as_f64()
            .ok_or_else(|| invalid("invalid grid dimensions"))?;
        let available = size - gap * (weights.len() - 1) as f64;
        let total: f64 = weights.iter().sum();
        if available <= 0. || !total.is_finite() {
            return Err(invalid("grid gaps or weights exceed the document size"));
        }
        let mut edges = vec![0.];
        for w in weights {
            edges.push(edges.last().unwrap() + available * w / total + gap);
        }
        Ok(edges)
    };
    let xs = positions("column_weights", 0)?;
    let ys = positions("row_weights", 1)?;
    let mut rectangles = vec![];
    for (slot, panel) in layout["placement"]
        .as_object()
        .ok_or_else(|| invalid("invalid grid placement"))?
    {
        let mut cells = vec![];
        for (r, row) in layout["grid"].as_array().unwrap().iter().enumerate() {
            for (c, value) in row.as_array().unwrap().iter().enumerate() {
                if value == slot {
                    cells.push((r, c));
                }
            }
        }
        let r0 = cells
            .iter()
            .map(|v| v.0)
            .min()
            .ok_or_else(|| invalid("unknown grid slot"))?;
        let r1 = cells.iter().map(|v| v.0).max().unwrap() + 1;
        let c0 = cells.iter().map(|v| v.1).min().unwrap();
        let c1 = cells.iter().map(|v| v.1).max().unwrap() + 1;
        let x = xs[c0].round_ties_even();
        let y = ys[r0].round_ties_even();
        let width = (xs[c1] - gap).round_ties_even() - x;
        let height = (ys[r1] - gap).round_ties_even() - y;
        if width < 100. || height < 100. {
            return Err(invalid(
                "grid panels must be at least 100 logical pixels per dimension",
            ));
        }
        let index = state["identity"]["panels"]
            .as_array()
            .unwrap()
            .iter()
            .position(|v| v["id"] == *panel)
            .ok_or_else(|| invalid("unknown panel"))?;
        rectangles.push((
            index,
            json!({"x":x as u64,"y":y as u64,"width":width as u64,"height":height as u64}),
        ));
    }
    for (index, rect) in rectangles {
        let path = if index == 0 {
            "/config/chart_area".into()
        } else {
            format!("/config/subplots/{}/config/chart_area", index - 1)
        };
        *state.pointer_mut(&path).unwrap() = rect;
    }
    Ok(())
}
#[pyfunction]
pub(crate) fn editor_catalog_json(settings: &str) -> PyResult<String> {
    Ok(serde_json::to_string(&catalog(&parse(settings)?)).map_err(runtime)?)
}
#[pyfunction]
#[pyo3(signature=(settings,object,property,value,extents=None))]
pub(crate) fn editor_property_json(
    settings: &str,
    object: &str,
    property: &str,
    value: &str,
    extents: Option<&str>,
) -> PyResult<String> {
    Ok(apply(
        &parse(settings)?,
        object,
        property,
        serde_json::from_str(value).map_err(invalid)?,
        &extents
            .map(|v| serde_json::from_str(v).map_err(invalid))
            .transpose()?
            .unwrap_or(json!({})),
    )?
    .to_string())
}
