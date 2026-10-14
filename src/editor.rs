//! Native editing controls. Chart validation/rendering remain renderer APIs.
use super::*;
use egui::{Color32, RichText, Stroke};

pub(crate) struct Editor {
    pub inspector_open: bool,
    pub error: String,
    advanced_open: bool,
    save_path: String,
    raw: String,
    notice: String,
    pub stage: egui::Rect,
    pub controls: HashMap<String, egui::Rect>,
}

impl Default for Editor {
    fn default() -> Self {
        Self {
            inspector_open: false,
            error: String::new(),
            advanced_open: false,
            save_path: "figure.png".into(),
            raw: String::new(),
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
                        match Python::attach(|py| c.fit(py, 0.05)) {
                            Ok(()) => self.notice = "View fitted".into(),
                            Err(e) => self.error = e.to_string(),
                        }
                    }
                    ui.separator();
                    let select = toolbar_icon(
                        ui,
                        Icon::Select,
                        !*edit_area,
                        "Select",
                        "Select a chart element to edit",
                    );
                    self.controls.insert("select_mode".into(), select.rect);
                    if select.clicked() {
                        *edit_area = false;
                    }
                    let layout = toolbar_icon(
                        ui,
                        Icon::Layout,
                        *edit_area,
                        "Layout",
                        "Move or resize the plot area",
                    );
                    self.controls.insert("layout_mode".into(), layout.rect);
                    if layout.clicked() {
                        *edit_area = true;
                    }
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
                            match c
                                .settings_json()
                                .and_then(|s| serde_json::to_string(&s).map_err(runtime))
                            {
                                Ok(quoted) => {
                                    ui.ctx().copy_text(format!(
                                        "import json\nfig.apply_settings(json.loads({quoted}))\n"
                                    ));
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
                    "Click a chart element to edit  ·  Scroll to zoom"
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
            egui::Panel::right("inspector")
                .exact_size(320.)
                .frame(
                    egui::Frame::NONE
                        .fill(Color32::from_rgb(248, 249, 251))
                        .inner_margin(18),
                )
                .show(root, |ui| {
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
                    ui.add_space(8.);
                    ui.label(RichText::new("OBJECT").size(11.).weak());
                    let response = egui::ComboBox::from_id_salt("object")
                        .width(ui.available_width())
                        .selected_text(
                            selected
                                .as_ref()
                                .map(|id| object_name(id, c.data))
                                .unwrap_or_else(|| "Choose an element".into()),
                        )
                        .show_ui(ui, |ui| {
                            for (id, _) in &c.data.elements {
                                ui.selectable_value(
                                    selected,
                                    Some(id.clone()),
                                    object_name(id, c.data),
                                );
                            }
                            for series in &c.data.series {
                                ui.selectable_value(
                                    selected,
                                    Some(series.series_id.clone()),
                                    object_name(&series.series_id, c.data),
                                );
                            }
                        });
                    self.controls
                        .insert("object".into(), response.response.rect);
                    ui.add_space(10.);
                    ui.separator();
                    ui.add_space(6.);
                    if let Some(target) = selected.as_ref() {
                        egui::ScrollArea::vertical().show(ui, |ui| self.properties(ui, c, target));
                    } else {
                        ui.label(
                            RichText::new(
                                "Select a title, axis, legend or data series in the chart.",
                            )
                            .weak(),
                        );
                    }
                    ui.add_space(16.);
                    ui.separator();
                    let advanced = ui.button("Advanced settings…");
                    self.controls.insert("advanced".into(), advanced.rect);
                    if advanced.clicked() {
                        self.raw = serde_json::to_string_pretty(&c.snapshot()).unwrap();
                        self.advanced_open = true;
                    }
                });
        }
        let mut advanced = self.advanced_open;
        egui::Window::new("Advanced chart settings")
            .open(&mut advanced)
            .default_width(530.)
            .show(root.ctx(), |ui| {
                ui.label("Edit the full configuration. Data and series connections are preserved.");
                egui::ScrollArea::vertical()
                    .max_height(380.)
                    .show(ui, |ui| {
                        let response = ui.add(
                            egui::TextEdit::multiline(&mut self.raw)
                                .code_editor()
                                .desired_width(f32::INFINITY)
                                .desired_rows(16),
                        );
                        self.controls.insert(
                            "settings_json".into(),
                            response.rect.intersect(ui.clip_rect()),
                        );
                    });
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
            });
        self.advanced_open = advanced;
        egui::CentralPanel::default()
            .frame(egui::Frame::NONE)
            .show(root, |ui| {
                self.stage = ui.max_rect().shrink(16.);
            });
    }

    fn properties(&mut self, ui: &mut egui::Ui, c: &mut FigureAccess<'_>, target: &str) {
        let mut state = serde_json::to_value(c.snapshot()).unwrap();
        let mut changed = false;
        let config = state["config"].clone();
        let mut config = config;
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
            let mut text = node["segments"]
                .as_array()
                .map(|a| {
                    a.iter()
                        .filter_map(|s| s["text"].as_str())
                        .collect::<String>()
                })
                .unwrap_or_default();
            ui.label("Text");
            let response =
                ui.add(egui::TextEdit::singleline(&mut text).desired_width(f32::INFINITY));
            self.controls.insert("text".into(), response.rect);
            if response.changed() {
                node["segments"] =
                    serde_json::to_value(renderer::text::rich_segments_from_text(&text)).unwrap();
                changed = true;
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
        } else if target.starts_with("tick_labels_") {
            let key = axis_key(target.trim_start_matches("tick_labels_"));
            let node = &mut config[key]["label_style"];
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
                let bar = &mut config["colorbar"];
                ui.label(RichText::new("COLOR SCALE").size(11.).weak());
                changed |= number(
                    ui,
                    &mut bar["axis"],
                    "min",
                    "Minimum",
                    "",
                    &mut self.controls,
                );
                changed |= number(
                    ui,
                    &mut bar["axis"],
                    "max",
                    "Maximum",
                    "",
                    &mut self.controls,
                );
                ui.label("Color map");
                let previous = bar["colormap"].as_str().unwrap_or("Custom").to_owned();
                let mut value = previous.clone();
                let response = egui::ComboBox::from_id_salt("colormap")
                    .width(ui.available_width())
                    .selected_text(&value)
                    .show_ui(ui, |ui| {
                        for name in ["Viridis", "Magma", "Turbo", "GrayScale", "RdBu"] {
                            let response = ui.selectable_value(&mut value, name.to_owned(), name);
                            self.controls
                                .insert(format!("colormap_{name}"), response.rect);
                        }
                    });
                self.controls
                    .insert("colormap".into(), response.response.rect);
                if value != previous {
                    bar["colormap"] = json!(value);
                    changed = true;
                }
            }
        } else if target.starts_with("axis_") {
            let key = axis_key(target.trim_start_matches("axis_"));
            let node = &mut config[key];
            changed |= number(ui, node, "min", "Minimum", "", &mut self.controls);
            changed |= number(ui, node, "max", "Maximum", "", &mut self.controls);
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
        state["config"] = config;
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
                ui.color_edit_button_srgba_unmultiplied(&mut rgba)
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
