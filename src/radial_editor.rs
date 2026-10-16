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
                        !self.edit_area,
                        "Select",
                        "Select a chart element",
                    );
                    self.controls.insert("select_mode".into(), select.rect);
                    if select.clicked() {
                        self.edit_area = false;
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
                        self.edit_area,
                        "Layout",
                        "Move or resize the plot area",
                    );
                    self.controls.insert("edit_area".into(), area.rect);
                    self.controls.insert("layout_mode".into(), area.rect);
                    if area.clicked() {
                        self.edit_area = true;
                    }
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
                        if let crate::bounded::DocumentChart::BoxPlot(c) = &mut chart {
                            c.value_range = None;
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
        egui::Panel::bottom("radial_status").exact_size(30.).show(root, |ui| {
            ui.label(if !self.error.is_empty() { self.error.as_str() } else if !self.notice.is_empty() {
                self.notice.as_str()
            } else { "Click: select / clear · Drag: move / resize · Arrows: move selection · Esc: clear · F11: full screen" });
        });
        if self.inspector_open && !overlay {
            egui::Panel::right("radial_properties")
                .exact_size(INSPECTOR_WIDTH)
                .show(root, |ui| {
                    egui::ScrollArea::vertical().show(ui, |ui| self.radial_properties(ui, c));
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
                    egui::ScrollArea::vertical()
                        .max_height(500.)
                        .show(ui, |ui| self.radial_properties(ui, c));
                });
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
            _ => unreachable!(),
        };
        ui.heading(if family == "categorical" {
            "Categorical bars"
        } else {
            "Box plot"
        });
        let mut changed = false;
        for key in ["title", "category_title", "value_title"] {
            ui.label(key.replace('_', " "));
            let mut text = value[key].as_str().unwrap().to_owned();
            let response = ui.text_edit_singleline(&mut text);
            self.controls
                .insert(format!("bounded_{key}"), response.rect);
            if response.changed() {
                value[key] = json!(text);
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
                .position(|v| v["id"] == selected["category_id"])
                .unwrap();
            let category = &mut value["categories"][index];
            let mut label = category["label"].as_str().unwrap().to_owned();
            ui.label("Category label");
            if ui.text_edit_singleline(&mut label).changed() {
                category["label"] = json!(label);
                changed = true;
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
            if family == "categorical" {
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
    fn radial_properties(&mut self, ui: &mut egui::Ui, c: &mut FigureAccess<'_>) {
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
        changed |= title.changed();
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
