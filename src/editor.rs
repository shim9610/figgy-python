//! Native editing controls. Chart validation/rendering remain renderer APIs.
use super::*;
use egui::{Color32, RichText, Stroke};

pub const INSPECTOR_WIDTH: f32 = 320.;

pub(crate) struct Editor {
    pub inspector_open: bool,
    pub(super) drawing: crate::drawing::Drawing,
    pub(super) delete_annotation: bool,
    pub(super) inline_text: Option<crate::drawing::InlineText>,
    pub edit_area: bool,
    pub error: String,
    pub advanced_requested: bool,
    pub picked: Option<Value>,
    pub(super) navigator: navigation::Navigator,
    save_path: String,
    raw: String,
    text_ranges: HashMap<String, std::ops::Range<usize>>,
    inspector_context: String,
    notice: String,
    pub stage: egui::Rect,
    pub controls: HashMap<String, egui::Rect>,
}

impl Default for Editor {
    fn default() -> Self {
        Self {
            inspector_open: false,
            drawing: Default::default(),
            delete_annotation: false,
            inline_text: None,
            edit_area: false,
            error: String::new(),
            advanced_requested: false,
            picked: None,
            navigator: navigation::Navigator::default(),
            save_path: "figure.png".into(),
            raw: String::new(),
            text_ranges: HashMap::new(),
            inspector_context: String::new(),
            notice: String::new(),
            stage: egui::Rect::NOTHING,
            controls: HashMap::new(),
        }
    }
}

pub fn theme(ctx: &egui::Context) {
    ctx.set_theme(egui::ThemePreference::Light);
    let mut visuals = egui::Visuals::light();
    visuals.override_text_color = Some(Color32::from_rgb(32, 43, 59));
    visuals.weak_text_color = Some(Color32::from_rgb(108, 119, 135));
    visuals.panel_fill = Color32::WHITE;
    visuals.window_fill = Color32::WHITE;
    visuals.extreme_bg_color = Color32::from_rgb(245, 247, 250);
    visuals.faint_bg_color = Color32::from_rgb(248, 249, 251);
    visuals.selection.bg_fill = Color32::from_rgb(221, 234, 250);
    visuals.selection.stroke = Stroke::new(1., Color32::from_rgb(38, 99, 173));
    for widget in [
        &mut visuals.widgets.inactive,
        &mut visuals.widgets.hovered,
        &mut visuals.widgets.active,
    ] {
        widget.corner_radius = 5.into();
        widget.bg_stroke = Stroke::new(1., Color32::from_rgb(210, 216, 225));
    }
    ctx.set_visuals_of(egui::Theme::Light, visuals);
    ctx.style_mut_of(egui::Theme::Light, |style| {
        style.spacing.item_spacing = egui::vec2(10., 10.);
        style.spacing.button_padding = egui::vec2(12., 7.);
        style.spacing.interact_size.y = 30.;
        style
            .text_styles
            .insert(egui::TextStyle::Body, egui::FontId::proportional(14.));
        style
            .text_styles
            .insert(egui::TextStyle::Button, egui::FontId::proportional(14.));
        style
            .text_styles
            .insert(egui::TextStyle::Heading, egui::FontId::proportional(19.));
    });
}

pub fn object_name(id: &str, data: &FigureCore) -> String {
    if let Some((prefix, element)) = id.split_once(':') {
        if let Some(index) = prefix
            .strip_prefix("subplot_")
            .and_then(|v| v.parse::<usize>().ok())
        {
            let panel = data
                .identity
                .as_ref()
                .and_then(|v| v["panels"][index + 1]["id"].as_str())
                .unwrap_or("Panel");
            return format!("{} · {}", panel, object_name(element, data));
        }
        if prefix.starts_with("overlay_") {
            return object_name(element, data);
        }
    }
    let name = match id {
        "chart_title" => "Chart title",
        "data_area" => "Plot area",
        "legend" => "Legend",
        "axis_top" => "Top axis",
        "axis_bottom" => "X axis",
        "axis_left" => "Y axis",
        "axis_right" => "Right axis",
        "axis_title_top" => "Top axis title",
        "axis_title_bottom" => "X axis title",
        "axis_title_left" => "Y axis title",
        "axis_title_right" => "Right axis title",
        "tick_labels_top" => "Top tick labels",
        "tick_labels_bottom" => "X tick labels",
        "tick_labels_left" => "Y tick labels",
        "tick_labels_right" => "Right tick labels",
        "colorbar" => "Color scale",
        "colorbar_axis" => "Color scale axis",
        "colorbar_tick_labels" => "Color scale labels",
        "colorbar_title" => "Color scale title",
        _ => {
            return data
                .series
                .iter()
                .find(|s| s.series_id == id)
                .and_then(|s| s.label.as_ref())
                .map(|r| r.segments.iter().map(|s| s.text).collect())
                .filter(|s: &String| !s.is_empty())
                .unwrap_or_else(|| {
                    if id.starts_with("series_") {
                        data.series
                            .iter()
                            .position(|s| s.series_id == id)
                            .map(|index| format!("Series {}", index + 1))
                            .unwrap_or_else(|| id.to_owned())
                    } else {
                        id.to_owned()
                    }
                });
        }
    };
    name.into()
}

// UI helper only: direct SSOT injection keeps the caller's layout untouched.
fn fit_enabled_title(config: &mut Config, target: &str) {
    if target == "chart_title" {
        let measure = renderer::CpuTextMeasure::for_style(&config.draw_style);
        renderer::layout::fit_chart_title_margin(config, &measure);
    } else {
        let axis = match target {
            "axis_title_bottom" => &mut config.bottom_x,
            "axis_title_left" => &mut config.left_y,
            "axis_title_top" => &mut config.top_x,
            "axis_title_right" => &mut config.right_y,
            _ => return,
        };
        if axis.title_option.visible {
            axis.out_margin = axis.out_margin.max(axis.title_option.text.font_size * 2.0);
        }
    }
}

impl Editor {
    pub fn show(
        &mut self,
        root: &mut egui::Ui,
        c: &mut FigureAccess<'_>,
        selected: &mut Option<String>,
        edit_area: &mut bool,
    ) {
        self.controls.clear();
        egui::Panel::top("toolbar")
            .exact_size(58.)
            .frame(
                egui::Frame::NONE
                    .fill(Color32::WHITE)
                    .inner_margin(egui::Margin::symmetric(18, 10)),
            )
            .show(root, |ui| {
                ui.horizontal_centered(|ui| {
                    ui.label(
                        RichText::new("Figgy")
                            .size(19.)
                            .strong()
                            .color(Color32::from_rgb(30, 91, 166)),
                    );
                    ui.add_space(14.);
                    let response = toolbar_icon(
                        ui,
                        Icon::Fit,
                        false,
                        "Fit view",
                        "Fit axes to the current data",
                    );
                    self.controls.insert("fit".into(), response.rect);
                    if response.clicked() {
                        let padding = if !c.data.series.is_empty()
                            && c.data.series.iter().all(|s| {
                                matches!(
                                    s.render_type,
                                    renderer::DataRenderType::Heatmap { .. }
                                        | renderer::DataRenderType::Contour { .. }
                                        | renderer::DataRenderType::HeatmapContour { .. }
                                )
                            }) {
                            0.0
                        } else {
                            0.05
                        };
                        match Python::attach(|py| c.fit(py, padding)) {
                            Ok(()) => self.notice = "View fitted".into(),
                            Err(e) => self.error = e.to_string(),
                        }
                    }
                    ui.separator();
                    let select = toolbar_icon(
                        ui,
                        Icon::Select,
                        !*edit_area && self.drawing.tool == crate::drawing::Tool::Select,
                        "Select",
                        "Select a chart element to edit",
                    );
                    self.controls.insert("select_mode".into(), select.rect);
                    if select.clicked() {
                        *edit_area = false;
                        self.drawing.cancel();
                    }
                    let layout = toolbar_icon(
                        ui,
                        Icon::Layout,
                        *edit_area && self.drawing.tool == crate::drawing::Tool::Select,
                        "Layout",
                        "Move or resize the plot area",
                    );
                    self.controls.insert("layout_mode".into(), layout.rect);
                    if layout.clicked() {
                        *edit_area = true;
                        self.drawing.cancel();
                    }
                    ui.separator();
                    self.drawing_button(ui);
                    let visibility = ui.button("Show / hide");
                    self.controls
                        .insert("visibility_menu".into(), visibility.rect);
                    egui::Popup::menu(&visibility)
                        .close_behavior(egui::PopupCloseBehavior::CloseOnClickOutside)
                        .show(|ui| {
                            ui.set_width(210.);
                            ui.heading("Show / hide");
                            let mut cfg = c.data.chart.config().clone();
                            let mut changed = false;
                            let mut enabled_title = None;
                            for (key, label, visible, rich) in [
                                (
                                    "chart_title",
                                    "Chart title",
                                    &mut cfg.chart_title.visible,
                                    Some(&mut cfg.chart_title.text),
                                ),
                                ("legend", "Legend", &mut cfg.legend.visible, None),
                                (
                                    "axis_title_bottom",
                                    "X axis title",
                                    &mut cfg.bottom_x.title_option.visible,
                                    Some(&mut cfg.bottom_x.title_option.text),
                                ),
                                (
                                    "axis_title_left",
                                    "Y axis title",
                                    &mut cfg.left_y.title_option.visible,
                                    Some(&mut cfg.left_y.title_option.text),
                                ),
                                (
                                    "axis_title_top",
                                    "Top axis title",
                                    &mut cfg.top_x.title_option.visible,
                                    Some(&mut cfg.top_x.title_option.text),
                                ),
                                (
                                    "axis_title_right",
                                    "Right axis title",
                                    &mut cfg.right_y.title_option.visible,
                                    Some(&mut cfg.right_y.title_option.text),
                                ),
                            ] {
                                // An empty title is not visible, even when its SSOT flag is true.
                                let empty = rich.as_ref().is_some_and(|r| {
                                    r.segments.iter().all(|s| s.text.is_whitespace())
                                });
                                let mut shown = *visible && !empty;
                                let response = ui.checkbox(&mut shown, label);
                                self.controls.insert(format!("show_{key}"), response.rect);
                                if response.changed() {
                                    *visible = shown;
                                    changed = true;
                                    if shown && let Some(rich) = rich {
                                        if empty {
                                            rich.segments =
                                                renderer::text::rich_segments_from_text(label);
                                        }
                                        enabled_title = Some(key);
                                    }
                                }
                            }
                            if let Some(target) = enabled_title {
                                fit_enabled_title(&mut cfg, target);
                            }
                            if changed {
                                match c.commit_config(cfg) {
                                    Ok(()) => {
                                        self.error.clear();
                                        self.notice = "Visibility updated".into();
                                        if let Some(target) = enabled_title {
                                            *selected = Some(target.into());
                                            self.inspector_open = true;
                                        }
                                    }
                                    Err(error) => self.error = error.to_string(),
                                }
                            }
                        });
                    self.draw_style_menu(ui, c);
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        let save = toolbar_icon(
                            ui,
                            Icon::Save,
                            false,
                            "Save PNG",
                            "Export the chart as a PNG image",
                        );
                        self.controls.insert("save".into(), save.rect);
                        egui::Popup::menu(&save)
                            .close_behavior(egui::PopupCloseBehavior::CloseOnClickOutside)
                            .show(|ui| {
                                ui.set_width(310.);
                                ui.heading("Export figure");
                                ui.add_space(4.);
                                ui.label("File path");
                                let path = ui.add(
                                    egui::TextEdit::singleline(&mut self.save_path)
                                        .desired_width(f32::INFINITY),
                                );
                                self.controls.insert("save_path".into(), path.rect);
                                ui.label(
                                    RichText::new("Chart only, at the document resolution.")
                                        .small()
                                        .weak(),
                                );
                                let response = ui.add_sized(
                                    [ui.available_width(), 32.],
                                    egui::Button::new(
                                        RichText::new("Save image").color(Color32::WHITE),
                                    )
                                    .fill(Color32::from_rgb(38, 99, 173)),
                                );
                                self.controls.insert("save_confirm".into(), response.rect);
                                if response.clicked() {
                                    c.data.png_encodes += 1;
                                    match c
                                        .render(1.)
                                        .and_then(|r| encode_png(&r).map_err(runtime))
                                        .and_then(|bytes| {
                                            std::fs::write(&self.save_path, bytes).map_err(runtime)
                                        }) {
                                        Ok(_) => {
                                            self.error.clear();
                                            self.notice = format!("Saved {}", self.save_path);
                                            ui.close();
                                        }
                                        Err(e) => self.error = e.to_string(),
                                    }
                                }
                            });
                        let copy = toolbar_icon(
                            ui,
                            Icon::Code,
                            false,
                            "Copy Python",
                            "Copy the current settings as Python code",
                        );
                        self.controls.insert("copy".into(), copy.rect);
                        if copy.clicked() {
                            // The exporter is pure Python: it never reacquires the
                            // Figure/renderer locks already held by this frame.
                            let code = c.settings_json().and_then(|settings| {
                                let defaults = serde_json::to_string(&c.data.default_config)
                                    .map_err(runtime)?;
                                Python::attach(|py| {
                                    py.import("figgyplot._codegen")?
                                        .getattr("settings_to_code")?
                                        .call1((settings, defaults, c.data.code_dpi))?
                                        .extract::<String>()
                                })
                            });
                            match code {
                                Ok(code) => {
                                    ui.ctx().copy_text(code);
                                    self.notice = "Python settings copied".into();
                                }
                                Err(e) => self.error = e.to_string(),
                            }
                        }
                        ui.separator();
                        let properties = toolbar_icon(
                            ui,
                            Icon::Properties,
                            self.inspector_open,
                            "Properties",
                            "Open or close the selected element’s properties",
                        );
                        self.controls.insert("properties".into(), properties.rect);
                        if properties.clicked() {
                            self.inspector_open = !self.inspector_open;
                        }
                    });
                });
            });
        self.edit_area = *edit_area;
        self.drawing_ui(root, c);
        *edit_area = self.edit_area;
        egui::Panel::top("navigation_help")
            .exact_size(24.)
            .frame(egui::Frame::NONE.fill(Color32::from_rgb(248, 249, 251))
                .inner_margin(egui::Margin::symmetric(18, 3)))
            .show(root, |ui| {
                let help = ui.label(RichText::new(
                    "Ctrl + wheel: Zoom X  ·  Shift + wheel: Zoom Y  ·  Wheel: Zoom XY  ·  Drag plot: Pan  ·  Click: Edit")
                    .size(12.).color(Color32::from_rgb(105, 116, 131)));
                self.controls.insert("navigation_help".into(), help.rect);
            });
        egui::Panel::bottom("status")
            .exact_size(30.)
            .frame(
                egui::Frame::NONE
                    .fill(Color32::from_rgb(248, 249, 251))
                    .inner_margin(egui::Margin::symmetric(18, 5)),
            )
            .show(root, |ui| {
                let message = if !self.error.is_empty() {
                    self.error.as_str()
                } else if !self.notice.is_empty() {
                    self.notice.as_str()
                } else {
                    "Click an element to edit  ·  Esc: Clear selection  ·  Arrows: Move selection  ·  F11: Full screen"
                };
                ui.label(
                    RichText::new(message)
                        .size(12.)
                        .color(if self.error.is_empty() {
                            Color32::from_rgb(105, 116, 131)
                        } else {
                            Color32::from_rgb(170, 45, 45)
                        }),
                );
            });
        if self.inspector_open {
            let mut area = root.max_rect();
            area.min.y = root.available_rect_before_wrap().top();
            area.max.y -= 30.;
            egui::Area::new(egui::Id::new("inspector"))
                .order(egui::Order::Foreground)
                .fixed_pos(egui::pos2(area.right() - INSPECTOR_WIDTH, area.top()))
                .movable(false)
                .show(root.ctx(), |ui| {
                    egui::Frame::NONE
                        .fill(Color32::from_rgb(248, 249, 251))
                        .inner_margin(18)
                        .show(ui, |ui| {
                            ui.set_width(INSPECTOR_WIDTH - 36.);
                            ui.set_height((area.height() - 36.).max(100.));
                            self.inspector(ui, c, selected);
                        });
                });
        }
        egui::CentralPanel::default()
            .frame(egui::Frame::NONE)
            .show(root, |ui| {
                self.stage = ui.max_rect().shrink(16.);
            });
    }

    fn inspector(
        &mut self,
        ui: &mut egui::Ui,
        c: &mut FigureAccess<'_>,
        selected: &mut Option<String>,
    ) {
        ui.horizontal(|ui| {
            ui.heading("Properties");
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                let close = ui.small_button("Close");
                self.controls.insert("close_properties".into(), close.rect);
                if close.clicked() {
                    self.inspector_open = false;
                }
            });
        });
        let nodes = navigation::nodes(&c.snapshot());
        if let Some(node) = self.navigator.show(
            ui,
            &nodes,
            c.data.chart.config().active_layer(),
            selected.as_deref(),
            &mut self.controls,
        ) {
            let mut config = c.data.chart.config().clone();
            config.active_layer = node.layer;
            config.picked_data = None;
            config.picked_points = None;
            if let Err(error) = c.commit_config(config) {
                self.error = error.to_string();
            }
            *selected = node.target;
            self.picked = None;
        }
        ui.add_space(6.);
        let context = format!("{:?}/{:?}", c.data.chart.config().active_layer(), selected);
        if context != self.inspector_context {
            self.text_ranges.clear();
            self.inspector_context = context;
        }
        if let Some(target) = selected.as_ref() {
            let form = egui::ScrollArea::vertical()
                .id_salt("object_properties")
                .max_height(
                    (ui.available_height() - if self.picked.is_some() { 250. } else { 74. })
                        .max(100.),
                )
                .show(ui, |ui| self.properties(ui, c, target));
            self.controls
                .insert("properties_viewport".into(), form.inner_rect);
        } else {
            ui.label(
                RichText::new("Select a title, axis, legend or data series in the chart.").weak(),
            );
        }
        if self.delete_annotation {
            *selected = None;
            self.delete_annotation = false;
        }
        if let Some(picked) = &self.picked {
            ui.separator();
            ui.label(RichText::new("SELECTED DATA").size(11.).strong());
            for key in [
                "index",
                "x_index",
                "y_index",
                "color_value",
                "size_value",
                "u",
                "v",
                "bin_start",
                "bin_end",
                "x",
                "y",
                "value",
                "orientation",
            ] {
                if let Some(value) = picked.get(key) {
                    ui.monospace(format!("{key}: {value}"));
                }
            }
            ui.label(
                RichText::new("Arrows: move selection · Esc: clear")
                    .small()
                    .weak(),
            );
        }
        ui.add_space(16.);
        ui.separator();
        let advanced = ui.button("Advanced settings…");
        self.controls.insert("advanced".into(), advanced.rect);
        if advanced.clicked() {
            self.raw = serde_json::to_string_pretty(&c.snapshot()).unwrap();
            self.advanced_requested = true;
        }
    }

    pub fn begin_settings(&mut self, c: &FigureAccess<'_>) {
        self.raw = serde_json::to_string_pretty(&c.snapshot()).unwrap();
    }

    pub fn show_settings(&mut self, root: &mut egui::Ui, c: &mut FigureAccess<'_>) {
        self.controls.clear();
        egui::CentralPanel::default()
            .frame(egui::Frame::NONE.inner_margin(18))
            .show(root, |ui| {
                ui.heading("Advanced chart settings");
                ui.label("Data and series connections are preserved.");
                egui::Panel::bottom("settings_actions").show(ui, |ui| {
                    let apply = ui.button("Apply settings");
                    self.controls.insert("apply_settings".into(), apply.rect);
                    if apply.clicked() {
                        match c.apply_settings(&self.raw) {
                            Ok(_) => {
                                self.error.clear();
                                self.notice = "Settings applied".into();
                            }
                            Err(e) => self.error = e.to_string(),
                        }
                    }
                    if !self.error.is_empty() {
                        ui.colored_label(Color32::DARK_RED, &self.error);
                    } else {
                        ui.label(&self.notice);
                    }
                });
                egui::ScrollArea::both().show(ui, |ui| {
                    let response = ui.add(
                        egui::TextEdit::multiline(&mut self.raw)
                            .code_editor()
                            .desired_width(f32::INFINITY)
                            .desired_rows(20),
                    );
                    self.controls.insert(
                        "settings_json".into(),
                        response.rect.intersect(ui.clip_rect()),
                    );
                });
            });
    }

    fn rich_text_editor(&mut self, ui: &mut egui::Ui, node: &mut Value, key: &str) -> bool {
        let mut text = display_text(&node["segments"]);
        ui.label("Text (select characters to format)");
        let output = egui::TextEdit::singleline(&mut text)
            .id_salt(key)
            .desired_width(f32::INFINITY)
            .show(ui);
        self.controls.insert(key.to_owned(), output.response.rect);
        if let Some(range) = output.cursor_range {
            if output.response.has_focus() || output.response.lost_focus() {
                let chars = range.as_sorted_char_range();
                self.text_ranges
                    .insert(key.to_owned(), chars.start.0..chars.end.0);
            }
        }
        let mut changed = output.response.changed();
        if changed {
            let fresh =
                serde_json::to_value(renderer::text::rich_segments_from_text(&text)).unwrap();
            node["segments"] = preserve_segment_styles(&node["segments"], fresh);
        }
        let segments = node["segments"].as_array_mut().unwrap();
        let count = segments.len();
        let range = self
            .text_ranges
            .get(key)
            .filter(|r| r.start < r.end)
            .cloned()
            .unwrap_or(0..count);
        let range = range.start.min(count)..range.end.min(count);
        ui.horizontal_wrapped(|ui| {
            for (flag, label) in [
                ("bold", "B"),
                ("italic", "I"),
                ("underline", "U"),
                ("superscript", "x²"),
                ("subscript", "x₂"),
                ("greek", "αβ"),
            ] {
                let active =
                    !range.is_empty() && segments[range.clone()].iter().all(|s| s[flag] == true);
                let response = ui.selectable_label(active, label).on_hover_text(flag);
                self.controls.insert(format!("{key}_{flag}"), response.rect);
                if response.clicked() {
                    for segment in &mut segments[range.clone()] {
                        segment[flag] = json!(!active);
                        if !active && flag == "superscript" {
                            segment["subscript"] = json!(false);
                        }
                        if !active && flag == "subscript" {
                            segment["superscript"] = json!(false);
                        }
                    }
                    changed = true;
                }
            }
        });
        changed
    }

    pub(super) fn annotation_properties(&mut self, ui: &mut egui::Ui, item: &mut Value) -> bool {
        self.delete_annotation = false;
        let remove =
            ui.button(RichText::new("Delete annotation").color(Color32::from_rgb(165, 42, 37)));
        self.controls
            .insert("delete_annotation".into(), remove.rect);
        self.delete_annotation = remove.clicked();
        let mut changed = false;
        let annotation_id = item["id"].as_str().unwrap_or("").to_owned();
        let mut visible = item["visible"].as_bool().unwrap_or(true);
        let response = ui.checkbox(&mut visible, "Visible");
        self.controls
            .insert("annotation_visible".into(), response.rect);
        if response.changed() {
            item["visible"] = json!(visible);
            changed = true;
        }
        let kind = item["kind"]
            .as_object()
            .unwrap()
            .keys()
            .next()
            .unwrap()
            .clone();
        ui.weak(&kind);
        let geometry = &mut item["kind"][&kind];
        for field in match kind.as_str() {
            "ReferenceLine" => vec!["value"],
            "Span" => vec!["from", "to"],
            _ => vec![],
        } {
            changed |= number(ui, geometry, field, field, "", &mut self.controls);
        }
        for field in ["anchor", "from", "to"] {
            if let Some(unit) = geometry[field]
                .as_object()
                .and_then(|v| v.keys().next())
                .cloned()
            {
                if geometry[field][&unit].is_object() {
                    ui.label(format!("{} · {} coordinates", field, unit.to_lowercase()));
                    for dimension in ["x", "y"] {
                        changed |= number(
                            ui,
                            &mut geometry[field][&unit],
                            dimension,
                            dimension,
                            "",
                            &mut self.controls,
                        );
                        if let Some(rect) = self.controls.get(dimension).copied() {
                            self.controls.insert(format!("{field}_{dimension}"), rect);
                        }
                    }
                }
            }
        }
        let text_key = if kind == "ReferenceLine" {
            "label"
        } else {
            "text"
        };
        if kind == "Arrow" || kind == "ReferenceLine" {
            let mut label = geometry[text_key].is_object();
            let response = ui.checkbox(&mut label, "Show label");
            self.controls
                .insert("annotation_label".into(), response.rect);
            if response.changed() {
                geometry[text_key] = if label {
                    serde_json::to_value(renderer::text::RichText::plain(
                        "Label",
                        Color::from_rgb8(35, 45, 60),
                        16.,
                        "",
                    ))
                    .unwrap()
                } else {
                    Value::Null
                };
                changed = true;
            }
        }
        if geometry[text_key].is_object() {
            let key = format!("annotation_text_{annotation_id}");
            changed |= self.rich_text_editor(ui, &mut geometry[text_key], &key);
            if let Some(rect) = self.controls.get(&key).copied() {
                self.controls.insert("annotation_text".into(), rect);
            }
            changed |= number(
                ui,
                &mut geometry[text_key],
                "font_size",
                "Font size",
                " px",
                &mut self.controls,
            );
            changed |= color(
                ui,
                &mut geometry[text_key],
                "color",
                "Text color",
                &mut self.controls,
            );
        }
        if kind == "Arrow" {
            for key in ["head_length", "head_width"] {
                changed |= number(
                    ui,
                    &mut geometry["style"],
                    key,
                    key,
                    " px",
                    &mut self.controls,
                );
            }
        }
        if kind == "Text" {
            let mut boxed = geometry["box_style"].is_object();
            let r = ui.checkbox(&mut boxed, "Text box");
            self.controls.insert("annotation_box".into(), r.rect);
            if r.changed() {
                geometry["box_style"] = if boxed {
                    serde_json::to_value(renderer::annotation::BoxStyle::default()).unwrap()
                } else {
                    Value::Null
                };
                changed = true;
            }
            if boxed {
                let style = &mut geometry["box_style"];
                changed |= color(ui, style, "fill", "Box fill", &mut self.controls);
                changed |= color(
                    ui,
                    style,
                    "border_color",
                    "Border color",
                    &mut self.controls,
                );
                for key in ["border_width", "padding"] {
                    changed |= number(ui, style, key, key, " px", &mut self.controls);
                }
            }
        }
        if geometry["fill"].is_object() {
            changed |= color(ui, geometry, "fill", "Fill", &mut self.controls);
            changed |= number(
                ui,
                &mut geometry["fill"],
                "a",
                "Opacity",
                "",
                &mut self.controls,
            );
        }
        if kind == "Arrow" || kind == "ReferenceLine" {
            let style = if kind == "Arrow" {
                &mut geometry["style"]["line"]
            } else {
                &mut geometry["style"]
            };
            if style.is_object() {
                changed |= color(ui, style, "color", "Line color", &mut self.controls);
                changed |= number(ui, style, "width", "Line width", " px", &mut self.controls);
                let mut value = style["style"].as_str().unwrap_or("Solid").to_owned();
                let before = value.clone();
                let r = egui::ComboBox::from_label("Stroke")
                    .selected_text(&value)
                    .show_ui(ui, |ui| {
                        for name in [
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
                        ] {
                            ui.selectable_value(&mut value, name.into(), name);
                        }
                    });
                self.controls
                    .insert("annotation_line_style".into(), r.response.rect);
                if value != before {
                    style["style"] = json!(value);
                    changed = true;
                }
            }
        }
        changed
    }

    fn properties(&mut self, ui: &mut egui::Ui, c: &mut FigureAccess<'_>, target: &str) {
        let mut state = serde_json::to_value(c.snapshot()).unwrap();
        if let Some(id) = target.strip_prefix("annotation:") {
            if let Some(item) = state["config"]["annotations"]["items"]
                .as_array_mut()
                .and_then(|items| items.iter_mut().find(|v| v["id"] == id))
            {
                let changed = self.annotation_properties(ui, item);
                if self.delete_annotation {
                    state["config"]["annotations"]["items"]
                        .as_array_mut()
                        .unwrap()
                        .retain(|v| v["id"] != id);
                }
                if changed || self.delete_annotation {
                    match c.apply_settings(&state.to_string()) {
                        Ok(_) => self.error.clear(),
                        Err(error) => self.error = error.to_string(),
                    }
                }
            }
            return;
        }
        let scoped_path = match c.data.chart.config().active_layer() {
            renderer::LayerRef::Subplot(i) | renderer::LayerRef::SubplotOverlay(i, _) => {
                format!("/config/subplots/{i}/config")
            }
            _ => "/config".to_string(),
        };
        let overlay_target = target.contains("overlay_");
        let overlay_index = if overlay_target {
            match c.data.chart.config().active_layer() {
                renderer::LayerRef::Overlay(i) | renderer::LayerRef::SubplotOverlay(_, i) => {
                    Some(i)
                }
                _ => None,
            }
        } else {
            None
        };
        let target = target.rsplit(':').next().unwrap_or(target);
        let mut changed = false;
        let config = state.pointer(&scoped_path).unwrap().clone();
        let mut config = config;
        let original_right = config["right_y"].clone();
        if let Some(i) = overlay_index {
            config["right_y"] = config["overlays"][i]["y_axis"].clone();
        }
        let visibility = match target {
            "chart_title" => Some((&mut config["chart_title"], "visible")),
            "legend" => Some((&mut config["legend"], "visible")),
            "colorbar" => Some((&mut config["colorbar"], "visible")),
            _ if target.starts_with("axis_title_") => Some((
                &mut config[axis_key(target.trim_start_matches("axis_title_"))]["title_option"],
                "visible",
            )),
            _ if target.starts_with("tick_labels_") => Some((
                &mut config[axis_key(target.trim_start_matches("tick_labels_"))]["label_style"],
                "visible",
            )),
            _ if target.starts_with("axis_") => Some((
                &mut config[axis_key(target.trim_start_matches("axis_"))],
                "line_visible",
            )),
            _ => None,
        };
        if let Some((node, key)) = visibility {
            if let Some(mut value) = node[key].as_bool() {
                let is_title = target == "chart_title" || target.starts_with("axis_title_");
                if is_title
                    && node["text"]["segments"].as_array().is_some_and(|segments| {
                        segments
                            .iter()
                            .all(|s| s["text"].as_str().is_none_or(|v| v.trim().is_empty()))
                    })
                {
                    value = false;
                }
                let label = if key == "line_visible" {
                    "Axis line"
                } else {
                    "Visible"
                };
                let response = ui.checkbox(&mut value, label);
                self.controls.insert("visible".into(), response.rect);
                if response.changed() {
                    node[key] = json!(value);
                    if value
                        && is_title
                        && node["text"]["segments"].as_array().is_some_and(|segments| {
                            segments
                                .iter()
                                .all(|s| s["text"].as_str().is_none_or(|v| v.trim().is_empty()))
                        })
                    {
                        node["text"]["segments"] = json!(renderer::text::rich_segments_from_text(
                            &object_name(target, c.data)
                        ));
                    }
                    changed = true;
                }
            }
        }
        let rich = match target {
            "chart_title" => Some(&mut config["chart_title"]["text"]),
            "axis_title_bottom" => Some(&mut config["bottom_x"]["title_option"]["text"]),
            "axis_title_top" => Some(&mut config["top_x"]["title_option"]["text"]),
            "axis_title_left" => Some(&mut config["left_y"]["title_option"]["text"]),
            "axis_title_right" => Some(&mut config["right_y"]["title_option"]["text"]),
            "legend" => Some(&mut config["legend"]["content"]),
            _ => None,
        };
        if let Some(node) = rich {
            if target == "legend" {
                let mut labels_changed = false;
                ui.label("Legend entries");
                for series in state["series"].as_array_mut().unwrap() {
                    if !series["label"].is_object() {
                        continue;
                    }
                    let key = format!("legend_label_{}", series["series_id"].as_str().unwrap());
                    labels_changed |= self.rich_text_editor(ui, &mut series["label"], &key);
                }
                if labels_changed {
                    let mut content: renderer::text::RichText =
                        serde_json::from_value(node.clone()).unwrap();
                    content.segments.clear();
                    for series in state["series"].as_array().unwrap() {
                        let series: SeriesConfig = serde_json::from_value(series.clone()).unwrap();
                        if let Some(label) = &series.label {
                            renderer::legend::append_legend_entry_rich(
                                &mut content,
                                renderer::legend::series_symbol_segments(
                                    &series,
                                    c.data
                                        .chart
                                        .config()
                                        .colorbar
                                        .as_ref()
                                        .map(|bar| &bar.colormap),
                                ),
                                label.segments.clone(),
                            );
                        }
                    }
                    *node = serde_json::to_value(content).unwrap();
                    changed = true;
                }
            } else {
                changed |= self.rich_text_editor(ui, node, "text");
            }
            changed |= text_field(
                ui,
                node,
                "font",
                "Font family",
                "Default font",
                &mut self.controls,
            );
            changed |= number(
                ui,
                node,
                "font_size",
                "Font size",
                " px",
                &mut self.controls,
            );
            changed |= color(ui, node, "color", "Text color", &mut self.controls);
            let previous = node["align"].as_str().unwrap_or("Left").to_owned();
            let mut align = previous.clone();
            ui.horizontal(|ui| {
                for name in ["Left", "Center", "Right"] {
                    let response = ui.selectable_value(&mut align, name.to_owned(), name);
                    self.controls.insert(format!("align_{name}"), response.rect);
                }
            });
            if align != previous {
                node["align"] = json!(align);
                changed = true;
            }
        } else if target.starts_with("tick_labels_") {
            let key = axis_key(target.trim_start_matches("tick_labels_"));
            let node = &mut config[key]["label_style"];
            changed |= label_format_controls(ui, node, &mut self.controls);
            changed |= text_field(
                ui,
                node,
                "label_font",
                "Font family",
                "Default font",
                &mut self.controls,
            );
            changed |= number(
                ui,
                node,
                "font_size",
                "Font size",
                " px",
                &mut self.controls,
            );
            changed |= color(ui, node, "color", "Text color", &mut self.controls);
        } else if let Some(series) = state["series"]
            .as_array_mut()
            .unwrap()
            .iter_mut()
            .find(|s| s["series_id"] == target)
        {
            let style = series["render_type"]
                .as_object_mut()
                .unwrap()
                .values_mut()
                .next()
                .unwrap();
            if style["line"].is_object() {
                ui.label(RichText::new("LINE").size(11.).weak());
                changed |= color(
                    ui,
                    &mut style["line"],
                    "line_color",
                    "Color",
                    &mut self.controls,
                );
                changed |= number(
                    ui,
                    &mut style["line"],
                    "line_width",
                    "Width",
                    " px",
                    &mut self.controls,
                );
            }
            if style["scatter"].is_object() {
                ui.label(RichText::new("MARKERS").size(11.).weak());
                changed |= color(
                    ui,
                    &mut style["scatter"],
                    "point_color",
                    "Color",
                    &mut self.controls,
                );
                changed |= number(
                    ui,
                    &mut style["scatter"],
                    "point_size",
                    "Size",
                    " px",
                    &mut self.controls,
                );
            }
            if style["matrix"].is_object() {
                changed |= color_scale_properties(ui, &mut config["colorbar"], &mut self.controls);
            }
        } else if target == "colorbar" || target.starts_with("colorbar_") {
            changed |= color_scale_properties(ui, &mut config["colorbar"], &mut self.controls);
        } else if target.starts_with("axis_") {
            let key = axis_key(target.trim_start_matches("axis_"));
            let node = &mut config[key];
            changed |= scale_control(ui, node, "axis_scale", &mut self.controls);
            let mut labels = node["label_style"]["visible"].as_bool().unwrap_or(true);
            let response = ui.checkbox(&mut labels, "Tick labels");
            self.controls
                .insert("tick_labels_visible".into(), response.rect);
            if response.changed() {
                node["label_style"]["visible"] = json!(labels);
                changed = true;
            }
            let mut ticks = node["tick"] != "None";
            let response = ui.checkbox(&mut ticks, "Tick marks");
            self.controls.insert("ticks_visible".into(), response.rect);
            if response.changed() {
                node["tick"] = json!(if ticks { "Outside" } else { "None" });
                changed = true;
            }
            ui.label("Tick direction / visibility");
            let previous = node["tick"].as_str().unwrap_or("Outside").to_owned();
            let mut direction = previous.clone();
            let response = egui::ComboBox::from_id_salt("tick_direction")
                .selected_text(if direction == "None" {
                    "Hidden"
                } else {
                    &direction
                })
                .show_ui(ui, |ui| {
                    for (value, label) in [
                        ("None", "Hidden"),
                        ("Outside", "Outside"),
                        ("Inside", "Inside"),
                        ("Both", "Both sides"),
                    ] {
                        let response = ui.selectable_value(&mut direction, value.to_owned(), label);
                        self.controls.insert(format!("tick_{value}"), response.rect);
                    }
                });
            self.controls
                .insert("tick_direction".into(), response.response.rect);
            if direction != previous {
                node["tick"] = json!(direction);
                changed = true;
            }
            changed |= label_format_controls(ui, &mut node["label_style"], &mut self.controls);
            let range_changed = number(ui, node, "min", "Minimum", "", &mut self.controls)
                | number(ui, node, "max", "Maximum", "", &mut self.controls);
            changed |= range_changed;
            let node = &mut config[key];
            changed |= number(
                ui,
                node,
                "major_spacing",
                "Tick spacing",
                "",
                &mut self.controls,
            );
            changed |= number(
                ui,
                node,
                "line_width",
                "Line width",
                " px",
                &mut self.controls,
            );
            changed |= color(ui, node, "line_color", "Line color", &mut self.controls);
        } else {
            ui.label(RichText::new("Drag this element to adjust its layout.").weak());
        }
        if changed && (target == "chart_title" || target.starts_with("axis_title_")) {
            // The title fields act as the renderer's title helper: a title
            // taller than its band grows the band instead of being clipped.
            if let Ok(mut parsed) = serde_json::from_value::<Config>(config.clone()) {
                fit_enabled_title(&mut parsed, target);
                config = serde_json::to_value(parsed).unwrap();
            }
        }
        if changed {
            // A scale switch is a view helper: use the positive data domain if
            // the old linear limits cross zero, without editing source arrays.
            for (key, dimension) in [
                ("bottom_x", "x"),
                ("top_x", "x"),
                ("left_y", "y"),
                ("right_y", "y"),
                ("colorbar", "z"),
            ] {
                if !config[key].is_object() {
                    continue;
                }
                let old = if key == "colorbar" {
                    &state.pointer(&scoped_path).unwrap()[key]["axis"]
                } else {
                    &state.pointer(&scoped_path).unwrap()[key]
                };
                let axis = if key == "colorbar" {
                    &mut config[key]["axis"]
                } else {
                    &mut config[key]
                };
                if axis["scale"] == "Logarithmic"
                    && old["scale"] != "Logarithmic"
                    && axis["min"].as_f64().is_some_and(|v| v <= 0.)
                {
                    match c.log_bounds(dimension) {
                        Ok((min, max)) => {
                            axis["min"] = json!(min);
                            axis["max"] = json!(max);
                        }
                        Err(e) => {
                            self.error = e.to_string();
                            return;
                        }
                    }
                }
            }
        }
        if changed {
            crate::axis_edit::sync_linked_axis_edit(
                state.pointer(&scoped_path).unwrap(),
                &mut config,
                target,
            );
        }
        if let Some(i) = overlay_index {
            config["overlays"][i]["y_axis"] = config["right_y"].clone();
            config["right_y"] = original_right;
        }
        *state.pointer_mut(&scoped_path).unwrap() = config;
        if changed {
            match c.apply_settings(&state.to_string()) {
                Ok(_) => {
                    self.error.clear();
                    self.notice = "Changes applied".into();
                }
                Err(e) => self.error = e.to_string(),
            }
        }
    }
}

/// What a text field shows for a rich node: the text whose renderer segments
/// these are (keeping "10⁻³" as typed), or the plain characters when the
/// segments carry styling no plain text maps to.
pub(super) fn display_text(segments: &Value) -> String {
    serde_json::from_value::<Vec<renderer::text::RichSegment>>(segments.clone())
        .ok()
        .and_then(|segments| crate::plain_text_of(&segments))
        .unwrap_or_else(|| {
            segments
                .as_array()
                .map(|a| a.iter().filter_map(|s| s["text"].as_str()).collect())
                .unwrap_or_default()
        })
}

fn axis_key(name: &str) -> &'static str {
    match name {
        "bottom" => "bottom_x",
        "top" => "top_x",
        "left" => "left_y",
        _ => "right_y",
    }
}

fn text_field(
    ui: &mut egui::Ui,
    node: &mut Value,
    key: &str,
    label: &str,
    hint: &'static str,
    controls: &mut HashMap<String, egui::Rect>,
) -> bool {
    let Some(mut value) = node[key].as_str().map(str::to_owned) else {
        return false;
    };
    ui.label(label);
    let response = ui.add(
        egui::TextEdit::singleline(&mut value)
            .hint_text(hint)
            .desired_width(f32::INFINITY),
    );
    controls.insert(key.into(), response.rect);
    if response.changed() {
        node[key] = json!(value);
    }
    response.changed()
}
fn color_scale_properties(
    ui: &mut egui::Ui,
    bar: &mut Value,
    controls: &mut HashMap<String, egui::Rect>,
) -> bool {
    if !bar.is_object() {
        ui.label("No color scale is configured.");
        return false;
    }
    let mut changed = scale_control(ui, &mut bar["axis"], "color_scale", controls);
    ui.label(RichText::new("COLOR SCALE").size(11.).weak());
    changed |= number(ui, &mut bar["axis"], "min", "Minimum", "", controls);
    changed |= number(ui, &mut bar["axis"], "max", "Maximum", "", controls);
    ui.label("Color map");
    let previous = bar["colormap"].as_str().unwrap_or("Custom").to_owned();
    let mut value = previous.clone();
    let response = egui::ComboBox::from_id_salt("colormap")
        .width(ui.available_width())
        .selected_text(&value)
        .show_ui(ui, |ui| {
            for name in ["Viridis", "Magma", "Turbo", "GrayScale", "RdBu"] {
                let response = ui.selectable_value(&mut value, name.to_owned(), name);
                controls.insert(format!("colormap_{name}"), response.rect);
            }
        });
    controls.insert("colormap".into(), response.response.rect);
    if value != previous {
        bar["colormap"] = json!(value);
        changed = true;
    }
    changed |= label_format_controls(ui, &mut bar["axis"]["label_style"], controls);
    changed
}

fn label_format_controls(
    ui: &mut egui::Ui,
    labels: &mut Value,
    controls: &mut HashMap<String, egui::Rect>,
) -> bool {
    ui.label("Number format");
    let previous = labels["format"].as_str().unwrap_or("Timestamp");
    let mut value = previous.to_owned();
    let response = egui::ComboBox::from_id_salt("label_format")
        .selected_text(previous)
        .show_ui(ui, |ui| {
            for (name, label) in [
                ("Decimal", "Decimal (123.45)"),
                ("Scientific", "Scientific (1.23e2)"),
                ("Power", "Power (1.23 × 10²)"),
            ] {
                let response = ui.selectable_value(&mut value, name.to_owned(), label);
                controls.insert(format!("label_format_{name}"), response.rect);
            }
        });
    controls.insert("label_format".into(), response.response.rect);
    let mut changed = value != previous;
    if changed {
        labels["format"] = json!(value);
    }
    if value != "Timestamp" {
        let mut digits = labels["significant_digits"].as_u64().unwrap_or(3) as u8;
        let response = ui
            .horizontal(|ui| {
                ui.label("Significant digits");
                ui.add(egui::DragValue::new(&mut digits).range(1..=15).speed(1))
            })
            .inner;
        controls.insert("significant_digits".into(), response.rect);
        if response.changed() {
            labels["significant_digits"] = json!(digits);
            changed = true;
        }
    }
    changed
}

fn scale_control(
    ui: &mut egui::Ui,
    axis: &mut Value,
    id: &str,
    controls: &mut HashMap<String, egui::Rect>,
) -> bool {
    ui.label("Scale");
    let previous = axis["scale"].as_str().unwrap_or("Linear");
    let mut value = previous.to_owned();
    let response = egui::ComboBox::from_id_salt(id)
        .selected_text(if previous == "Logarithmic" {
            "Logarithmic (base 10)"
        } else {
            "Linear"
        })
        .show_ui(ui, |ui| {
            for (name, label) in [
                ("Linear", "Linear"),
                ("Logarithmic", "Logarithmic (base 10)"),
            ] {
                let response = ui.selectable_value(&mut value, name.to_owned(), label);
                controls.insert(format!("{id}_{name}"), response.rect);
            }
        });
    controls.insert(id.into(), response.response.rect);
    ui.label("Log view omits zero and negative values; source data is preserved.");
    if value == previous {
        return false;
    }
    axis["scale"] = json!(value);
    axis["major_spacing"] = json!(if value == "Logarithmic" {
        1.0
    } else {
        (axis["max"].as_f64().unwrap() - axis["min"].as_f64().unwrap()) / 5.0
    });
    true
}

fn number(
    ui: &mut egui::Ui,
    node: &mut Value,
    key: &str,
    label: &str,
    suffix: &str,
    controls: &mut HashMap<String, egui::Rect>,
) -> bool {
    let Some(mut value) = node[key].as_f64() else {
        return false;
    };
    let response = ui
        .horizontal(|ui| {
            ui.label(label);
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.add_sized(
                    [105., 30.],
                    egui::DragValue::new(&mut value).speed(0.1).suffix(suffix),
                )
            })
            .inner
        })
        .inner;
    controls.insert(key.into(), response.rect);
    if response.changed() {
        node[key] = json!(value);
    }
    response.changed()
}
fn color(
    ui: &mut egui::Ui,
    node: &mut Value,
    key: &str,
    label: &str,
    controls: &mut HashMap<String, egui::Rect>,
) -> bool {
    if !node[key].is_object() {
        return false;
    }
    let keys = ["r", "g", "b", "a"];
    let mut rgba = std::array::from_fn::<_, 4, _>(|i| {
        (node[key][keys[i]].as_f64().unwrap_or(0.).clamp(0., 1.) * 255.).round() as u8
    });
    let response = ui
        .horizontal(|ui| {
            ui.label(label);
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                let mut response = ui.add_sized(
                    [36., 30.],
                    egui::Button::new("").fill(Color32::from_rgba_unmultiplied(
                        rgba[0], rgba[1], rgba[2], rgba[3],
                    )),
                );
                let id = ui.make_persistent_id(("picker", key));
                let cached = ui
                    .ctx()
                    .data_mut(|d| d.get_temp::<([u8; 4], egui::ecolor::Hsva)>(id));
                let mut hsva = cached
                    .filter(|p| p.0 == rgba)
                    .map(|p| p.1)
                    .unwrap_or_else(|| egui::ecolor::Hsva::from_srgba_unmultiplied(rgba));
                if let Some(popup) = egui::Popup::menu(&response)
                    .frame(egui::Frame::popup(ui.style()).inner_margin(26))
                    .close_behavior(egui::PopupCloseBehavior::CloseOnClickOutside)
                    .show(|ui| {
                        // The SV marker extends by width/12 beyond the square.
                        // Reserve that space before the hue bar and at its edges.
                        ui.spacing_mut().slider_width = 250.;
                        ui.spacing_mut().item_spacing.y = 32.;
                        if egui::color_picker::color_picker_hsva_2d(
                            ui,
                            &mut hsva,
                            egui::color_picker::Alpha::OnlyBlend,
                        ) {
                            rgba = hsva.to_srgba_unmultiplied();
                            response.mark_changed();
                        }
                    })
                {
                    controls.insert("color_picker".into(), popup.response.rect);
                }
                ui.ctx().data_mut(|d| d.insert_temp(id, (rgba, hsva)));
                response
            })
            .inner
        })
        .inner;
    controls.insert(key.into(), response.rect);
    if response.changed() {
        for i in 0..4 {
            node[key][keys[i]] = json!(rgba[i] as f32 / 255.);
        }
    }
    response.changed()
}

#[derive(Clone, Copy)]
enum Icon {
    Fit,
    Select,
    Layout,
    Properties,
    Code,
    Save,
}

/// Resolution-independent toolbar glyphs, drawn on the same native surface.
fn toolbar_icon(
    ui: &mut egui::Ui,
    icon: Icon,
    selected: bool,
    label: &str,
    hint: &str,
) -> egui::Response {
    let (rect, response) = ui.allocate_exact_size(egui::vec2(36., 36.), egui::Sense::click());
    response.widget_info(|| {
        egui::WidgetInfo::labeled(egui::WidgetType::Button, ui.is_enabled(), label)
    });
    let painter = ui.painter_at(rect);
    if selected || response.hovered() || response.has_focus() {
        painter.rect_filled(
            rect,
            7.,
            if selected {
                Color32::from_rgb(227, 237, 250)
            } else {
                Color32::from_rgb(241, 245, 250)
            },
        );
    }
    let stroke = Stroke::new(
        1.7,
        if selected {
            Color32::from_rgb(35, 96, 171)
        } else {
            Color32::from_rgb(77, 92, 111)
        },
    );
    let origin = rect.min + egui::vec2(6., 6.);
    let point = |x: f32, y: f32| origin + egui::vec2(x, y);
    let line = |a: [f32; 2], b: [f32; 2]| {
        painter.line_segment([point(a[0], a[1]), point(b[0], b[1])], stroke);
    };
    let path = |points: &[[f32; 2]]| {
        painter.add(egui::Shape::line(
            points.iter().map(|p| point(p[0], p[1])).collect(),
            stroke,
        ));
    };
    match icon {
        Icon::Fit => {
            for (x, y, sx, sy) in [
                (4., 4., 1., 1.),
                (20., 4., -1., 1.),
                (4., 20., 1., -1.),
                (20., 20., -1., -1.),
            ] {
                path(&[[x + sx * 6., y], [x, y], [x, y + sy * 6.]]);
                line([x, y], [x + sx * 6., y + sy * 6.]);
            }
        }
        Icon::Select => {
            path(&[
                [5., 3.],
                [5., 20.],
                [10., 15.],
                [14., 22.],
                [17., 20.],
                [13., 13.],
                [20., 13.],
                [5., 3.],
            ]);
        }
        Icon::Layout => {
            line([12., 3.], [12., 21.]);
            line([3., 12.], [21., 12.]);
            path(&[[8., 7.], [12., 3.], [16., 7.]]);
            path(&[[8., 17.], [12., 21.], [16., 17.]]);
            path(&[[7., 8.], [3., 12.], [7., 16.]]);
            path(&[[17., 8.], [21., 12.], [17., 16.]]);
        }
        Icon::Properties => {
            for (x, y) in [(5., 8.), (12., 16.), (19., 10.)] {
                line([x, 3.], [x, y - 2.5]);
                line([x, y + 2.5], [x, 21.]);
                painter.circle_stroke(point(x, y), 2.5, stroke);
            }
        }
        Icon::Code => {
            path(&[
                [14., 2.],
                [4., 2.],
                [4., 22.],
                [20., 22.],
                [20., 8.],
                [14., 2.],
                [14., 8.],
                [20., 8.],
            ]);
            path(&[[10., 11.], [7., 14.], [10., 17.]]);
            path(&[[14., 11.], [17., 14.], [14., 17.]]);
        }
        Icon::Save => {
            line([12., 3.], [12., 16.]);
            path(&[[7., 11.], [12., 16.], [17., 11.]]);
            path(&[[4., 16.], [4., 21.], [20., 21.], [20., 16.]]);
        }
    }
    response.on_hover_text(format!("{label}\n{hint}"))
}

#[path = "radial_editor.rs"]
mod radial_editor;

// Preserve unchanged rich characters when editing the plain text input.
pub(super) fn preserve_segment_styles(old: &Value, mut fresh: Value) -> Value {
    let (Some(old), Some(next)) = (old.as_array(), fresh.as_array_mut()) else {
        return fresh;
    };
    let mut prefix = 0;
    while prefix < old.len().min(next.len()) && old[prefix]["text"] == next[prefix]["text"] {
        next[prefix] = old[prefix].clone();
        prefix += 1;
    }
    let mut suffix = 0;
    while suffix < old.len().min(next.len()) - prefix
        && old[old.len() - 1 - suffix]["text"] == next[next.len() - 1 - suffix]["text"]
    {
        let index = next.len() - 1 - suffix;
        next[index] = old[old.len() - 1 - suffix].clone();
        suffix += 1;
    }
    fresh
}
