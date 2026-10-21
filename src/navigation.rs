//! Derived object navigation. IDs, geometry and styles remain in the document.
use super::*;
use renderer::LayerRef;

#[derive(Clone, Serialize)]
pub(super) struct Node {
    pub key: String,
    pub label: String,
    pub kind: String,
    pub layer: LayerRef,
    pub target: Option<String>,
    pub children: Vec<Node>,
    pub collapsed: bool,
    pub visible: bool,
}
impl Node {
    fn new(
        key: String,
        label: String,
        kind: &str,
        layer: LayerRef,
        target: Option<String>,
    ) -> Self {
        Self {
            key,
            label,
            kind: kind.into(),
            layer,
            target,
            children: vec![],
            collapsed: false,
            visible: true,
        }
    }
}
fn text(value: &Value) -> String {
    value["segments"]
        .as_array()
        .map(|v| v.iter().filter_map(|s| s["text"].as_str()).collect())
        .unwrap_or_default()
}
fn leaf(key: &str, label: &str, kind: &str, layer: LayerRef, target: String) -> Node {
    Node::new(key.into(), label.into(), kind, layer, Some(target))
}
fn decoration(panel: &str, prefix: &str, name: &str, label: &str, layer: LayerRef) -> Node {
    leaf(
        &format!("{panel}/{name}"),
        label,
        "element",
        layer,
        format!("{prefix}{name}"),
    )
}
fn axes(panel: &str, prefix: &str, sides: &[(&str, &str)], layer: LayerRef) -> Node {
    let mut group = Node::new(format!("{panel}/axes"), "Axes".into(), "group", layer, None);
    group.collapsed = true;
    for (side, name) in sides {
        let mut axis = decoration(panel, prefix, &format!("axis_{side}"), name, layer);
        axis.kind = "axis".into();
        axis.collapsed = true;
        axis.children.push(decoration(
            panel,
            prefix,
            &format!("axis_title_{side}"),
            "Title",
            layer,
        ));
        axis.children.push(decoration(
            panel,
            prefix,
            &format!("tick_labels_{side}"),
            "Tick labels",
            layer,
        ));
        group.children.push(axis);
    }
    group
}
fn annotations(panel: &str, owner: &Value, bounded: bool) -> Option<Node> {
    let items = owner["annotations"]["items"].as_array()?;
    if items.is_empty() {
        return None;
    }
    let mut group = Node::new(
        format!("{panel}/annotations"),
        "Annotations".into(),
        "layer",
        LayerRef::Annotations,
        None,
    );
    for (i, item) in items.iter().enumerate() {
        let id = item["id"].as_str().unwrap_or("");
        let kind = item["kind"]
            .as_object()
            .and_then(|v| v.keys().next())
            .map(String::as_str)
            .unwrap_or("Annotation");
        let geometry = &item["kind"][kind];
        let content = text(if kind == "ReferenceLine" {
            &geometry["label"]
        } else {
            &geometry["text"]
        });
        let label = if !content.trim().is_empty() {
            content
        } else if id.is_empty() || id.starts_with("annotation_") {
            let name = match kind {
                "ReferenceLine" => {
                    if geometry["axis"] == "X" {
                        "Vertical line"
                    } else {
                        "Horizontal line"
                    }
                }
                "Span" => {
                    if geometry["axis"] == "X" {
                        "Vertical band"
                    } else {
                        "Horizontal band"
                    }
                }
                other => other,
            };
            format!("{name} {}", i + 1)
        } else {
            id.to_owned()
        };
        let mut node = leaf(
            &format!("{panel}/annotation/{id}"),
            &label,
            kind,
            LayerRef::Annotations,
            if bounded {
                format!("annotation_{i}")
            } else {
                format!("annotation:{id}")
            },
        );
        node.visible = item["visible"].as_bool().unwrap_or(true);
        group.children.push(node);
    }
    Some(group)
}
pub(super) fn nodes(settings: &Settings) -> Vec<Node> {
    let state = serde_json::to_value(settings).unwrap();
    let figure_id = state["identity"]["figure"].as_str().unwrap_or("figure");
    let mut figure = Node::new(
        format!("figure/{figure_id}"),
        "Figure".into(),
        "figure",
        LayerRef::Base,
        Some("figure".into()),
    );
    if let Some(family) = ["radial", "categorical", "boxplot", "radar"]
        .into_iter()
        .find(|k| state[*k].is_object())
    {
        let owner = &state[family];
        let label = owner["title"]
            .as_str()
            .filter(|v| !v.trim().is_empty())
            .unwrap_or(match family {
                "radial" => "Pie / donut",
                "categorical" => "Bars",
                "boxplot" => "Box plot",
                _ => "Radar",
            });
        let mut panel = leaf(
            "bounded",
            label,
            "panel",
            LayerRef::Base,
            "data_area".into(),
        );
        panel.children.push(decoration(
            "bounded",
            "",
            "chart_title",
            "Chart title",
            LayerRef::Base,
        ));
        panel.children.push(decoration(
            "bounded",
            "",
            "legend",
            "Legend",
            LayerRef::Base,
        ));
        if family != "radial" && family != "radar" {
            let horizontal = owner["direction"] == "Horizontal";
            panel.children.push(axes(
                "bounded",
                "",
                if horizontal {
                    &[("left", "Category axis"), ("bottom", "Value axis")]
                } else {
                    &[("bottom", "Category axis"), ("left", "Value axis")]
                },
                LayerRef::Base,
            ));
        }
        let mut data = Node::new(
            "bounded/data".into(),
            "Data".into(),
            "group",
            LayerRef::Base,
            None,
        );
        let entries = if family == "radial" {
            &owner["slices"]
        } else {
            &owner["series"]
        };
        if let Some(entries) = entries.as_array() {
            for (i, item) in entries.iter().enumerate() {
                let id = item["id"]
                    .as_str()
                    .map(str::to_owned)
                    .unwrap_or_else(|| format!("slice_0_{i}"));
                let label = item["label"]
                    .as_str()
                    .filter(|s| !s.trim().is_empty())
                    .unwrap_or(&id);
                data.children.push(leaf(
                    &format!("bounded/series/{id}"),
                    label,
                    "series",
                    LayerRef::Base,
                    id.clone(),
                ));
            }
        }
        if family == "radial" {
            if let Some(children) = owner["split"]["children"].as_array() {
                let mut detail = Node::new(
                    "bounded/split".into(),
                    "Detail slices".into(),
                    "group",
                    LayerRef::Base,
                    None,
                );
                for (i, item) in children.iter().enumerate() {
                    let id = format!("slice_1_{i}");
                    detail.children.push(leaf(
                        &format!("bounded/series/{id}"),
                        item["label"].as_str().unwrap_or(&id),
                        "series",
                        LayerRef::Base,
                        id.clone(),
                    ));
                }
                data.children.push(detail);
            }
        }
        panel.children.push(data);
        if let Some(a) = annotations("bounded", owner, true) {
            panel.children.push(a);
        }
        figure.children.push(panel);
        return vec![figure];
    }
    let configs: Vec<_> = std::iter::once(&state["config"])
        .chain(
            state["config"]["subplots"]
                .as_array()
                .into_iter()
                .flatten()
                .map(|p| &p["config"]),
        )
        .collect();
    for (index, config) in configs.into_iter().enumerate() {
        let layer = if index == 0 {
            LayerRef::Base
        } else {
            LayerRef::Subplot(index - 1)
        };
        let panel_id = state["identity"]["panels"][index]["id"]
            .as_str()
            .map(str::to_owned)
            .unwrap_or_else(|| format!("panel_{index}"));
        let key = format!("panel/{panel_id}");
        let prefix = if index == 0 {
            String::new()
        } else {
            format!("subplot_{}:", index - 1)
        };
        let title = text(&config["chart_title"]["text"]);
        let label = if title.trim().is_empty() {
            panel_id
        } else {
            title
        };
        let mut panel = leaf(&key, &label, "panel", layer, format!("{prefix}data_area"));
        panel.collapsed = !settings.config.subplots.is_empty();
        panel.children.push(decoration(
            &key,
            &prefix,
            "chart_title",
            "Chart title",
            layer,
        ));
        panel.children.push(axes(
            &key,
            &prefix,
            &[
                ("bottom", "X axis"),
                ("left", "Y axis"),
                ("top", "Top axis"),
                ("right", "Right axis"),
            ],
            layer,
        ));
        panel
            .children
            .push(decoration(&key, &prefix, "legend", "Legend", layer));
        if config["colorbar"].is_object() {
            let mut bar = decoration(&key, &prefix, "colorbar", "Color scale", layer);
            bar.collapsed = true;
            for (name, label) in [
                ("colorbar_axis", "Axis"),
                ("colorbar_title", "Title"),
                ("colorbar_tick_labels", "Tick labels"),
            ] {
                bar.children
                    .push(decoration(&key, &prefix, name, label, layer));
            }
            panel.children.push(bar);
        }
        let owner = |id: &str| settings.config.layer_of_series(id);
        let mut series_group = Node::new(
            format!("{key}/series"),
            "Series".into(),
            "group",
            layer,
            None,
        );
        let series_nodes = |target_layer: LayerRef| {
            state["series"]
                .as_array()
                .unwrap()
                .iter()
                .filter(|s| owner(s["series_id"].as_str().unwrap()) == target_layer)
                .enumerate()
                .map(|(i, s)| {
                    let id = s["series_id"].as_str().unwrap();
                    let label = text(&s["label"]);
                    let label = if label.trim().is_empty() {
                        if id.starts_with("series_") {
                            format!("Series {}", i + 1)
                        } else {
                            id.into()
                        }
                    } else {
                        label
                    };
                    let mut node = leaf(
                        &format!("series/{id}"),
                        &label,
                        "series",
                        target_layer,
                        id.into(),
                    );
                    node.kind = s["render_type"]
                        .as_object()
                        .and_then(|v| v.keys().next())
                        .cloned()
                        .unwrap_or_else(|| "series".into());
                    node
                })
                .collect::<Vec<_>>()
        };
        series_group.children = series_nodes(layer);
        panel.children.push(series_group);
        for (o, _) in config["overlays"]
            .as_array()
            .into_iter()
            .flatten()
            .enumerate()
        {
            let overlay_layer = if index == 0 {
                LayerRef::Overlay(o)
            } else {
                LayerRef::SubplotOverlay(index - 1, o)
            };
            let id = state["identity"]["panels"][index]["overlays"][o]
                .as_str()
                .unwrap_or("Secondary Y");
            let overlay_key = format!("{key}/overlay/{id}");
            let mut overlay = leaf(
                &overlay_key,
                &format!("Secondary Y · {id}"),
                "layer",
                overlay_layer,
                format!("{prefix}overlay_{o}:axis_right"),
            );
            overlay.children.push(axes(
                &overlay_key,
                &format!("{prefix}overlay_{o}:"),
                &[("right", "Y axis")],
                overlay_layer,
            ));
            overlay.children.extend(series_nodes(overlay_layer));
            panel.children.push(overlay);
        }
        if index == 0
            && let Some(a) = annotations(&key, config, false)
        {
            panel.children.push(a);
        }
        figure.children.push(panel);
    }
    vec![figure]
}

#[pyfunction]
pub(super) fn object_outline_json(settings: &str) -> PyResult<String> {
    let settings: Settings = parse(settings)?;
    serde_json::to_string(&nodes(&settings)).map_err(invalid)
}

/// Host range controls use the renderer's public tick planner. This contains no
/// geometry/rendering and never constructs a GPU in a notebook kernel.
pub(super) fn bounded_view(settings: &Settings) -> Option<Value> {
    use renderer::config::{AxisOptions, AxisScale};
    let (mut low, mut high) = (f64::INFINITY, f64::NEG_INFINITY);
    let (explicit, axis, radar, spacing) = if let Some(chart) = &settings.boxplot {
        for v in chart.series.iter().flat_map(|s| s.values.iter().flatten()) {
            for n in [v.whisker_low, v.q1, v.median, v.q3, v.whisker_high]
                .into_iter()
                .chain(v.mean)
                .chain(v.median_ci.into_iter().flatten())
                .chain(v.outliers.iter().copied())
            {
                low = low.min(n);
                high = high.max(n);
            }
        }
        (
            chart.value_range,
            if chart.direction == renderer::boxplot::BoxPlotDirection::Horizontal {
                "x"
            } else {
                "y"
            },
            false,
            None,
        )
    } else if let Some(chart) = &settings.radar {
        for n in chart
            .series
            .iter()
            .flat_map(|s| s.values.iter().copied())
            .filter(|n| n.is_finite())
        {
            low = low.min(n);
            high = high.max(n);
        }
        (chart.value_range, "radius", true, chart.ring_spacing)
    } else {
        return None;
    };
    let range = if let Some(range) = explicit {
        range
    } else {
        if !low.is_finite() {
            low = 0.;
            high = 1.;
        }
        if radar {
            low = low.min(0.);
            if high <= low {
                high = low + 1.;
            }
            let plan = AxisOptions::compute_nice_ticks(AxisScale::Linear, low, high, 5).ok()?;
            let spacing = spacing.unwrap_or(plan.major_spacing);
            let min = (low / spacing).floor() * spacing;
            let max = (high / spacing).ceil() * spacing;
            [min, if max > min { max } else { min + spacing }]
        } else {
            let unit = 10.0f64
                .powf(
                    low.abs()
                        .max(high.abs())
                        .max(f64::MIN_POSITIVE)
                        .log10()
                        .floor(),
                )
                .max(f64::MIN_POSITIVE);
            let (mut a, mut b) = (low / unit, high / unit);
            if a == b {
                let delta = (a.abs() * 0.05).max(0.5);
                a -= delta;
                b += delta;
            }
            let pad = (b - a) * 0.1;
            let plan =
                AxisOptions::compute_nice_ticks(AxisScale::Linear, a - pad, b + pad, 5).ok()?;
            [plan.min * unit, plan.max * unit]
        }
    };
    Some(json!({"range":range,"axis":axis,"automatic":explicit.is_none()}))
}

#[pyfunction]
pub(super) fn bounded_view_json(settings: &str) -> PyResult<String> {
    let settings: Settings = parse(settings)?;
    serde_json::to_string(&bounded_view(&settings)).map_err(invalid)
}

#[derive(Default)]
pub(super) struct Navigator {
    pub filter: String,
    open: HashMap<String, bool>,
    last_selection: String,
    pending_focus: Option<String>,
}
impl Navigator {
    pub fn show(
        &mut self,
        ui: &mut egui::Ui,
        nodes: &[Node],
        layer: LayerRef,
        target: Option<&str>,
        controls: &mut HashMap<String, egui::Rect>,
    ) -> Option<Node> {
        fn path<'a>(
            nodes: &'a [Node],
            layer: LayerRef,
            target: Option<&str>,
            ancestors: &mut Vec<&'a Node>,
        ) -> bool {
            for node in nodes {
                ancestors.push(node);
                if node.layer == layer && node.target.as_deref() == target && target.is_some() {
                    return true;
                }
                if path(&node.children, layer, target, ancestors) {
                    return true;
                }
                ancestors.pop();
            }
            false
        }
        let mut selected_path = vec![];
        path(nodes, layer, target, &mut selected_path);
        let signature = format!("{layer:?}/{target:?}");
        let mut reveal = signature != self.last_selection;
        if reveal {
            self.last_selection = signature;
            for node in &selected_path {
                self.open.insert(node.key.clone(), true);
            }
            // Direct canvas selection must remain discoverable after a search.
            if target.is_some() {
                self.filter.clear();
            }
        }
        ui.label(egui::RichText::new("OBJECTS").strong().small());
        ui.horizontal(|ui| {
            let search = ui.add(
                egui::TextEdit::singleline(&mut self.filter)
                    .hint_text("Find a panel, axis or series…")
                    .desired_width(ui.available_width() - 30.),
            );
            controls.insert("object_search".into(), search.rect);
            if ui.small_button("×").on_hover_text("Clear search").clicked() {
                self.filter.clear();
                reveal = true;
            }
        });
        let query = self.filter.to_lowercase();
        fn matches(node: &Node, query: &str) -> bool {
            query.is_empty()
                || format!(
                    "{} {} {}",
                    node.label,
                    node.kind,
                    node.key.rsplit('/').next().unwrap_or("")
                )
                .to_lowercase()
                .contains(query)
                || node.children.iter().any(|n| matches(n, query))
        }
        fn flatten<'a>(
            nodes: &'a [Node],
            depth: usize,
            query: &str,
            open: &HashMap<String, bool>,
            rows: &mut Vec<(&'a Node, usize)>,
        ) {
            for node in nodes {
                if !matches(node, query) {
                    continue;
                }
                rows.push((node, depth));
                if !query.is_empty() || *open.get(&node.key).unwrap_or(&!node.collapsed) {
                    flatten(&node.children, depth + 1, query, open, rows);
                }
            }
        }
        let mut rows = vec![];
        flatten(nodes, 0, &query, &self.open, &mut rows);
        let mut chosen = None;
        egui::ScrollArea::vertical()
            .id_salt("object_tree")
            .max_height((ui.available_height() * 0.4).clamp(90., 190.))
            .show(ui, |ui| {
                ui.spacing_mut().item_spacing.y = 2.;
                ui.spacing_mut().button_padding = egui::vec2(5., 3.);
                ui.spacing_mut().interact_size.y = 24.;
                if rows.is_empty() {
                    ui.weak("No matching objects");
                }
                for (index, (node, depth)) in rows.iter().enumerate() {
                    ui.push_id(&node.key, |ui| {
                        ui.horizontal(|ui| {
                            ui.spacing_mut().item_spacing.x = 3.;
                            ui.add_space(*depth as f32 * 12.);
                            let expanded = *self.open.get(&node.key).unwrap_or(&!node.collapsed);
                            if node.children.is_empty() {
                                ui.add_space(20.);
                            } else {
                                let toggle = ui.add_sized(
                                    [20., 24.],
                                    egui::Button::new(if expanded { "v" } else { ">" })
                                        .frame(false),
                                );
                                controls.insert(format!("tree_toggle:{}", node.key), toggle.rect);
                                if toggle.clicked() {
                                    self.open.insert(node.key.clone(), !expanded);
                                }
                            }
                            let selected = node.layer == layer
                                && node.target.as_deref() == target
                                && target.is_some();
                            let response = ui.add_sized(
                                [ui.available_width(), 24.],
                                egui::Button::new(egui::RichText::new(&node.label).color(
                                    if node.visible {
                                        egui::Color32::from_rgb(32, 43, 59)
                                    } else {
                                        egui::Color32::GRAY
                                    },
                                ))
                                .selected(selected)
                                .frame(selected)
                                .shortcut_text("")
                                .truncate(),
                            );
                            if response.rect.intersects(ui.clip_rect()) {
                                controls.insert(
                                    format!("tree:{}", node.key),
                                    response.rect.intersect(ui.clip_rect()),
                                );
                            }
                            if selected && reveal {
                                response.scroll_to_me(Some(egui::Align::Center));
                            }
                            if response.clicked() {
                                response.request_focus();
                                if node.target.is_some() || node.kind == "layer" {
                                    chosen = Some((*node).clone());
                                } else {
                                    self.open.insert(node.key.clone(), !expanded);
                                }
                            }
                            if response.has_focus() {
                                ui.input(|input| {
                                    if input.key_pressed(egui::Key::ArrowDown) {
                                        self.pending_focus = Some(
                                            rows[(index + 1).min(rows.len() - 1)].0.key.clone(),
                                        );
                                        ui.ctx().request_repaint();
                                    }
                                    if input.key_pressed(egui::Key::ArrowUp) {
                                        self.pending_focus =
                                            Some(rows[index.saturating_sub(1)].0.key.clone());
                                        ui.ctx().request_repaint();
                                    }
                                    if input.key_pressed(egui::Key::ArrowRight) {
                                        self.open.insert(node.key.clone(), true);
                                    }
                                    if input.key_pressed(egui::Key::ArrowLeft) {
                                        self.open.insert(node.key.clone(), false);
                                    }
                                });
                            }
                            if self.pending_focus.as_deref() == Some(node.key.as_str()) {
                                response.request_focus();
                                response.scroll_to_me(Some(egui::Align::Center));
                                self.pending_focus = None;
                            }
                            response.on_hover_text(format!("{}\n{}", node.kind, node.key));
                        });
                    });
                }
            });
        ui.separator();
        let breadcrumb = if selected_path.is_empty() {
            "Click an object in the chart or tree".into()
        } else {
            selected_path
                .iter()
                .skip(1)
                .map(|n| n.label.as_str())
                .collect::<Vec<_>>()
                .join(" / ")
        };
        let header = ui.label(egui::RichText::new(breadcrumb).strong());
        controls.insert("properties_header".into(), header.rect);
        if let Some(node) = &chosen {
            self.last_selection = format!("{:?}/{:?}", node.layer, node.target.as_deref());
        }
        chosen
    }
}
