//! Controls for upstream radial materials and global Cartesian draw styles.
use super::*;
use renderer::radial::*;

impl Editor {
    pub(super) fn draw_style_menu(&mut self, ui: &mut egui::Ui, c: &mut FigureAccess<'_>) {
        use renderer::config::*;
        let button = ui.button("Style");
        self.controls.insert("draw_style_menu".into(), button.rect);
        egui::Popup::menu(&button)
            .close_behavior(egui::PopupCloseBehavior::CloseOnClickOutside)
            .show(|ui| {
                ui.set_width(270.);
                let mut cfg = c.data.chart.config().clone();
                let mut changed = false;
                for (name, mode) in [
                    ("Precise", DrawStyle::Precise),
                    ("Sketch", DrawStyle::Sketch(Default::default())),
                    ("Milkyway", DrawStyle::Milkyway(Default::default())),
                    (
                        "Constellation",
                        DrawStyle::Constellation(Default::default()),
                    ),
                ] {
                    let allowed = validate_draw_style(
                        &Config {
                            draw_style: mode,
                            ..cfg.clone()
                        },
                        &c.data.series,
                    )
                    .is_ok();
                    let same =
                        std::mem::discriminant(&cfg.draw_style) == std::mem::discriminant(&mode);
                    let response = ui.add_enabled(allowed, egui::Button::new(name).selected(same));
                    self.controls
                        .insert(format!("style_{}", name.to_lowercase()), response.rect);
                    if response.clicked() && !same {
                        cfg.draw_style = mode;
                        changed = true;
                    }
                }
                ui.small("Sketch: lines, scatter, error bars. Milkyway: lines only. Constellation: marker lines.");
                let mut value = serde_json::to_value(cfg.draw_style).unwrap();
                for spec in draw_style_specs(&cfg.draw_style) {
                    let mut number = value[spec.key].as_f64().unwrap();
                    ui.label(spec.key.replace('_', " "));
                    if ui
                        .add(
                            egui::DragValue::new(&mut number)
                                .range(spec.min..=spec.max)
                                .speed(if spec.integer { 1. } else { 0.05 }),
                        )
                        .changed()
                    {
                        value[spec.key] = if spec.integer {
                            json!(number.round() as u32)
                        } else {
                            json!(number)
                        };
                        changed = true;
                    }
                }
                if changed {
                    if let Ok(style) = serde_json::from_value(value) {
                        cfg.draw_style = style;
                    }
                    match c.commit_config(cfg) {
                        Ok(()) => self.error.clear(),
                        Err(e) => self.error = e.to_string(),
                    }
                }
            });
    }

    pub(crate) fn show_bounded(
        &mut self,
        root: &mut egui::Ui,
        c: &mut FigureAccess<'_>,
        overlay: bool,
    ) {
        self.controls.clear();
        egui::Panel::top("radial_toolbar")
            .exact_size(58.)
            .show(root, |ui| {
                ui.horizontal_centered(|ui| {
                    ui.label(RichText::new("Figgy").size(19.).strong());
                    let props = toolbar_icon(
                        ui,
                        Icon::Properties,
                        self.inspector_open,
                        "Properties",
                        "Open or close properties",
                    );
                    self.controls.insert("properties".into(), props.rect);
                    if props.clicked() {
                        self.inspector_open = !self.inspector_open;
                    }
                    let select = toolbar_icon(
                        ui,
                        Icon::Select,
                        !self.edit_area && self.drawing.tool == crate::drawing::Tool::Select,
                        "Select",
                        "Select a chart element",
                    );
                    self.controls.insert("select_mode".into(), select.rect);
                    if select.clicked() {
                        self.edit_area = false;
                        self.drawing.cancel();
                        let mut chart = c.data.document.as_ref().unwrap().chart.clone();
                        if chart.decorations().selected == Some(renderer::DecorationId::DataArea) {
                            chart.clear_selection();
                            if let Err(e) = c.set_document(chart) {
                                self.error = e.to_string();
                            }
                        }
                    }
                    let area = toolbar_icon(
                        ui,
                        Icon::Layout,
                        self.edit_area && self.drawing.tool == crate::drawing::Tool::Select,
                        "Layout",
                        "Move or resize the plot area",
                    );
                    self.controls.insert("edit_area".into(), area.rect);
                    self.controls.insert("layout_mode".into(), area.rect);
                    if area.clicked() {
                        self.edit_area = true;
                        self.drawing.cancel();
                    }
                    self.drawing_button(ui);
                    let fit = toolbar_icon(
                        ui,
                        Icon::Fit,
                        false,
                        "Fit view",
                        "Reset the automatic plot area",
                    );
                    self.controls.insert("fit".into(), fit.rect);
                    if fit.clicked() {
                        let mut chart = c.data.document.as_ref().unwrap().chart.clone();
                        chart.decorations_mut().data_area = None;
                        match &mut chart {
                            crate::bounded::DocumentChart::BoxPlot(c) => c.value_range = None,
                            crate::bounded::DocumentChart::Radar(c) => c.value_range = None,
                            _ => {}
                        }
                        match c.set_document(chart) {
                            Ok(()) => self.error.clear(),
                            Err(e) => self.error = e.to_string(),
                        }
                    }

                    let advanced = ui.button("Advanced settings…");
                    self.controls.insert("advanced".into(), advanced.rect);
                    if advanced.clicked() {
                        self.advanced_requested = true;
                    }
                    let copy = toolbar_icon(
                        ui,
                        Icon::Code,
                        false,
                        "Copy Python",
                        "Copy reusable chart settings",
                    );
                    self.controls.insert("copy".into(), copy.rect);
                    if copy.clicked() {
                        let code = c.settings_json().and_then(|settings| {
                            Python::attach(|py| {
                                py.import("figgyplot._codegen")?
                                    .getattr("settings_to_code")?
                                    .call1((
                                        settings,
                                        serde_json::to_string(&c.data.default_config)
                                            .map_err(runtime)?,
                                        c.data.code_dpi,
                                    ))?
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
                    let save = toolbar_icon(
                        ui,
                        Icon::Save,
                        false,
                        "Save PNG",
                        "Export the current chart",
                    );
                    self.controls.insert("save".into(), save.rect);
                    egui::Popup::menu(&save).show(|ui| {
                        ui.label("File path");
                        let path = ui.text_edit_singleline(&mut self.save_path);
                        self.controls.insert("save_path".into(), path.rect);
                        let confirm = ui.button("Save image");
                        self.controls.insert("save_confirm".into(), confirm.rect);
                        if confirm.clicked() {
                            let result = c
                                .render(1.)
                                .and_then(|image| encode_png(&image).map_err(runtime))
                                .and_then(|bytes| {
                                    std::fs::write(&self.save_path, bytes).map_err(runtime)
                                });
                            match result {
                                Ok(()) => {
                                    c.data.png_encodes += 1;
                                    self.error.clear();
                                    self.notice = format!("Saved {}", self.save_path);
                                    ui.close();
                                }
                                Err(e) => self.error = e.to_string(),
                            }
                        }
                    });
                });
            });
        self.drawing_ui(root, c);
        egui::Panel::bottom("radial_status").exact_size(30.).show(root, |ui| {
            ui.label(if !self.error.is_empty() { self.error.as_str() } else if !self.notice.is_empty() {
                self.notice.as_str()
            } else { "Click: select / clear · Drag: move / resize · Arrows: move selection · Esc: clear · F11: full screen" });
        });
        if self.inspector_open && !overlay {
            egui::Panel::right("radial_properties")
                .exact_size(INSPECTOR_WIDTH)
                .show(root, |ui| {
                    self.bounded_navigator(ui, c);
                    let form = egui::ScrollArea::vertical()
                        .id_salt("bounded_properties")
                        .show(ui, |ui| self.radial_properties(ui, c));
                    self.controls
                        .insert("properties_viewport".into(), form.inner_rect);
                });
        }
        egui::CentralPanel::default()
            .frame(egui::Frame::NONE.inner_margin(16.))
            .show(root, |ui| {
                self.stage = ui.max_rect();
            });
        if self.inspector_open && overlay {
            egui::Window::new("Properties")
                .id(egui::Id::new("radial_overlay"))
                .anchor(egui::Align2::RIGHT_TOP, [-16., 70.])
                .default_width(INSPECTOR_WIDTH)
                .resizable(false)
                .show(root.ctx(), |ui| {
                    self.bounded_navigator(ui, c);
                    let form = egui::ScrollArea::vertical()
                        .id_salt("bounded_properties")
                        .max_height(300.)
                        .show(ui, |ui| self.radial_properties(ui, c));
                    self.controls
                        .insert("properties_viewport".into(), form.inner_rect);
                });
        }
    }

    fn bounded_navigator(&mut self, ui: &mut egui::Ui, c: &mut FigureAccess<'_>) {
        let document = &c.data.document.as_ref().unwrap().chart;
        let target = if let Some(id) = document.decorations().selected.as_ref() {
            Some(id.element_id())
        } else {
            let selected = document.selected_json();
            selected["series_id"]
                .as_str()
                .map(str::to_owned)
                .or_else(|| selected["index"].as_u64().map(|i| format!("slice_0_{i}")))
        };
        let nodes = navigation::nodes(&c.snapshot());
        if let Some(node) = self.navigator.show(
            ui,
            &nodes,
            document.active_layer(),
            target.as_deref(),
            &mut self.controls,
        ) {
            let mut chart = c.data.document.as_ref().unwrap().chart.clone();
            chart.clear_selection();
            chart.set_active_layer(node.layer);
            if let Some(target) = node.target.as_deref() {
                chart.decorations_mut().selected = if let Some(index) = target
                    .strip_prefix("annotation_")
                    .and_then(|s| s.parse::<usize>().ok())
                {
                    Some(renderer::DecorationId::Annotation(index))
                } else {
                    c.document_frame().ok().and_then(|frame| {
                        frame
                            .decorations()
                            .entries()
                            .find(|(_, element)| element.id.element_id() == target)
                            .map(|(_, element)| element.id.clone())
                    })
                };
                if chart.decorations().selected.is_none() && node.kind == "series" {
                    let family = chart.family();
                    let mut state = serde_json::to_value(c.snapshot()).unwrap();
                    if family == "radial" {
                        if let Some(index) = target
                            .strip_prefix("slice_0_")
                            .and_then(|s| s.parse::<usize>().ok())
                        {
                            state[family]["interaction"]["selected"] =
                                json!({"group":0,"index":index});
                        }
                    } else {
                        state[family]["selected"] = json!({"series_id":target,"category_id":state[family]["categories"][0]["id"]});
                    }
                    state[family]["decorations"]["selected"] = Value::Null;
                    state[family]["active_layer"] = serde_json::to_value(node.layer).unwrap();
                    let result = if family == "radial" {
                        c.set_radial(&state[family].to_string())
                    } else {
                        c.set_bounded(family, &state[family].to_string())
                    };
                    if let Err(error) = result {
                        self.error = error.to_string();
                    }
                    return;
                }
            }
            if let Err(error) = c.set_document(chart) {
                self.error = error.to_string();
            }
        }
    }

    fn bounded_properties(&mut self, ui: &mut egui::Ui, c: &mut FigureAccess<'_>) {
        let document = &c.data.document.as_ref().unwrap().chart;
        let (family, mut value) = match document {
            crate::bounded::DocumentChart::Categorical(v) => {
                ("categorical", serde_json::to_value(v).unwrap())
            }
            crate::bounded::DocumentChart::BoxPlot(v) => {
                ("boxplot", serde_json::to_value(v).unwrap())
            }
            crate::bounded::DocumentChart::Radar(v) => ("radar", serde_json::to_value(v).unwrap()),
            _ => unreachable!(),
        };
        ui.heading(if family == "categorical" {
            "Categorical bars"
        } else {
            "Box plot"
        });
        let mut changed = false;
        for key in ["title", "category_title", "value_title"]
            .into_iter()
            .filter(|key| family != "radar" || *key == "title")
        {
            ui.label(key.replace('_', " "));
            let mut text = value[key].as_str().unwrap().to_owned();
            let response = ui.text_edit_singleline(&mut text);
            self.controls
                .insert(format!("bounded_{key}"), response.rect);
            if response.changed() {
                value[key] = json!(text);
                if key == "title" && value["chart_title"].is_object() {
                    value["chart_title"]["text"]["segments"] =
                        json!(renderer::text::rich_segments_from_text(&text));
                }
                changed = true;
            }
        }
        for key in ["grid", "legend"] {
            let mut v = value[key].as_bool().unwrap();
            if ui.checkbox(&mut v, key).changed() {
                value[key] = json!(v);
                changed = true;
            }
        }
        if let Some(selected) = value["selected"].as_object().cloned() {
            ui.separator();
            ui.heading("Selected data");
            let index = value["categories"]
                .as_array()
                .unwrap()
                .iter()
                .position(|v| selected.get("category_id").is_some_and(|id| &v["id"] == id));
            let index = index.unwrap_or(0);
            if selected.contains_key("category_id") {
                let category = &mut value["categories"][index];
                let mut label = category["label"].as_str().unwrap().to_owned();
                ui.label("Category label");
                if ui.text_edit_singleline(&mut label).changed() {
                    category["label"] = json!(label);
                    changed = true;
                }
            }
            let series = value["series"]
                .as_array_mut()
                .unwrap()
                .iter_mut()
                .find(|v| v["id"] == selected["series_id"])
                .unwrap();
            let mut label = series["label"].as_str().unwrap().to_owned();
            ui.label("Series label");
            if ui.text_edit_singleline(&mut label).changed() {
                series["label"] = json!(label);
                changed = true;
            }
            let mut rgb = [
                series["color"]["r"].as_f64().unwrap() as f32,
                series["color"]["g"].as_f64().unwrap() as f32,
                series["color"]["b"].as_f64().unwrap() as f32,
            ];
            if ui.color_edit_button_rgb(&mut rgb).changed() {
                series["color"] = json!(Color::new(rgb[0], rgb[1], rgb[2], 1.));
                changed = true;
            }
            if family == "categorical"
                || (family == "radar" && selected.contains_key("category_id"))
            {
                let mut v = series["values"][index].as_f64().unwrap();
                ui.label("Value");
                if ui.add(egui::DragValue::new(&mut v).speed(0.1)).changed() {
                    series["values"][index] = json!(v);
                    changed = true;
                }
            } else {
                ui.label(
                    "Summary statistics: edit through Advanced settings or the Python artist.",
                );
            }
        }
        if changed {
            match c.set_bounded(family, &value.to_string()) {
                Ok(()) => {
                    self.error.clear();
                    ui.ctx().request_repaint();
                }
                Err(e) => self.error = e.to_string(),
            }
        }
    }
    fn bounded_context_properties(&mut self, ui: &mut egui::Ui, c: &mut FigureAccess<'_>) -> bool {
        let document = &c.data.document.as_ref().unwrap().chart;
        if let Some(renderer::DecorationId::Annotation(index)) = document.decorations().selected {
            let mut state = serde_json::to_value(c.snapshot()).unwrap();
            let family = document.family();
            if let Some(item) = state[family]["annotations"]["items"].get_mut(index) {
                let changed = self.annotation_properties(ui, item);
                if self.delete_annotation {
                    state[family]["annotations"]["items"]
                        .as_array_mut()
                        .unwrap()
                        .remove(index);
                    state[family]["decorations"]["selected"] = Value::Null;
                }
                if changed || self.delete_annotation {
                    let result = if family == "radial" {
                        c.set_radial(&state[family].to_string())
                    } else {
                        c.set_bounded(family, &state[family].to_string())
                    };
                    match result {
                        Ok(_) => self.error.clear(),
                        Err(error) => self.error = error.to_string(),
                    }
                }
            }
            return true;
        }
        if let Some(view) = navigation::bounded_view(&c.snapshot()) {
            let mut range: [f64; 2] = serde_json::from_value(view["range"].clone()).unwrap();
            let mut automatic = view["automatic"].as_bool().unwrap();
            ui.label(
                egui::RichText::new(if view["axis"] == "radius" {
                    "Radial range"
                } else {
                    "Value axis range"
                })
                .strong(),
            );
            let auto = ui.checkbox(&mut automatic, "Automatic range");
            self.controls.insert("auto_range".into(), auto.rect);
            let mut changed = auto.changed();
            let speed = (range[1] - range[0]).abs().max(1.) * 0.01;
            ui.horizontal(|ui| {
                for (i, key) in ["range_min", "range_max"].into_iter().enumerate() {
                    ui.label(if i == 0 { "Min" } else { "Max" });
                    let response = ui.add(egui::DragValue::new(&mut range[i]).speed(speed));
                    self.controls.insert(key.into(), response.rect);
                    if response.changed() {
                        automatic = false;
                        changed = true;
                    }
                }
            });
            if changed {
                let mut chart = c.data.document.as_ref().unwrap().chart.clone();
                let value = if automatic { None } else { Some(range) };
                match &mut chart {
                    crate::bounded::DocumentChart::BoxPlot(c) => c.value_range = value,
                    crate::bounded::DocumentChart::Radar(c) => c.value_range = value,
                    _ => {}
                }
                if let Err(error) = c.set_document(chart) {
                    self.error = error.to_string();
                }
            }
            ui.small("Wheel over plot: zoom values · Fit: automatic range");
            ui.separator();
        }
        false
    }

    fn radial_properties(&mut self, ui: &mut egui::Ui, c: &mut FigureAccess<'_>) {
        if self.bounded_context_properties(ui, c) {
            return;
        }
        if c.data.document.as_ref().unwrap().chart.radial().is_none() {
            self.bounded_properties(ui, c);
            return;
        }
        let mut chart = c
            .data
            .document
            .as_ref()
            .unwrap()
            .chart
            .radial()
            .unwrap()
            .clone();
        let mut changed = false;
        ui.heading("Pie / donut");
        ui.label("Title");
        let title = ui.text_edit_singleline(&mut chart.title);
        self.controls.insert("radial_title".into(), title.rect);
        if title.changed() {
            if let Some(option) = chart.chart_title.as_mut() {
                option.text.segments = renderer::text::rich_segments_from_text(&chart.title);
            }
            changed = true;
        }
        let mut donut = matches!(chart.kind, RadialKind::Donut { .. });
        if ui.checkbox(&mut donut, "Donut").changed() {
            chart.kind = if donut {
                RadialKind::Donut { inner_radius: 0.5 }
            } else {
                RadialKind::Pie
            };
            changed = true;
        }
        if let RadialKind::Donut { inner_radius } = &mut chart.kind {
            changed |= ui
                .add(egui::Slider::new(inner_radius, 0.1..=0.85).text("Inner radius"))
                .changed();
        }
        let material = egui::ComboBox::from_label("Material")
            .height(460.)
            .selected_text(format!("{:?}", chart.style.material))
            .show_ui(ui, |ui| {
                for value in [
                    RadialMaterial::Flat,
                    RadialMaterial::Matte,
                    RadialMaterial::Ceramic,
                    RadialMaterial::BrushedMetal,
                    RadialMaterial::Paper,
                    RadialMaterial::Wood,
                    RadialMaterial::SatinMetal,
                    RadialMaterial::Toon,
                    RadialMaterial::Enamel,
                    RadialMaterial::Hatch,
                    RadialMaterial::Pearl,
                ] {
                    let response =
                        ui.selectable_value(&mut chart.style.material, value, format!("{value:?}"));
                    self.controls
                        .insert(format!("radial_material_{value:?}"), response.rect);
                    changed |= response.changed();
                }
            });
        self.controls
            .insert("radial_material".into(), material.response.rect);
        for (label, field, low, high) in [
            ("Tilt", &mut chart.style.tilt_degrees, 0., 65.),
            ("Depth", &mut chart.style.depth, 0., 0.4),
            (
                "Texture strength",
                &mut chart.style.texture_strength,
                0.,
                1.,
            ),
            ("Texture scale", &mut chart.style.texture_scale, 0.1, 8.),
            ("Roughness", &mut chart.style.roughness, 0.05, 1.),
            ("Gloss", &mut chart.style.gloss, 0., 1.),
            ("Gap", &mut chart.style.gap_degrees, 0., 8.),
            ("Inner corners", &mut chart.style.inner_corner, 0., 0.15),
            ("Outer corners", &mut chart.style.outer_corner, 0., 0.15),
        ] {
            let control = ui.add(egui::Slider::new(field, low..=high).text(label));
            self.controls.insert(
                format!("radial_{}", label.to_lowercase().replace(' ', "_")),
                control.rect,
            );
            changed |= control.changed();
        }
        changed |= ui.checkbox(&mut chart.style.shadow, "Shadow").changed();
        egui::ComboBox::from_label("Labels")
            .selected_text(format!("{:?}", chart.labels))
            .show_ui(ui, |ui| {
                for labels in [
                    RadialLabels::None,
                    RadialLabels::Inside,
                    RadialLabels::Outside,
                ] {
                    changed |= ui
                        .selectable_value(&mut chart.labels, labels, format!("{labels:?}"))
                        .changed();
                }
            });
        if let Some(target) = chart.interaction.selected {
            ui.separator();
            ui.heading(format!("Slice {}", target.index + 1));
            if let Some(slice) = chart.slice_mut(target) {
                changed |= ui.text_edit_singleline(&mut slice.label).changed();
                ui.label("Value");
                changed |= ui
                    .add(
                        egui::DragValue::new(&mut slice.value)
                            .range(0.0..=f64::MAX)
                            .speed(0.1),
                    )
                    .changed();
                ui.label("Explode");
                changed |= ui
                    .add(egui::Slider::new(&mut slice.explode, 0.0..=0.35))
                    .changed();
                let mut rgb = [slice.color.r, slice.color.g, slice.color.b];
                if ui.color_edit_button_rgb(&mut rgb).changed() {
                    slice.color = Color::new(rgb[0], rgb[1], rgb[2], 1.);
                    changed = true;
                }
            }
        }
        if changed {
            match serde_json::to_string(&chart)
                .map_err(runtime)
                .and_then(|json| c.set_radial(&json))
            {
                Ok(()) => {
                    self.error.clear();
                    ui.ctx().request_repaint();
                }
                Err(e) => self.error = e.to_string(),
            }
        }
    }
}
