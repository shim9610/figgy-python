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

    pub(crate) fn show_radial(
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
                    let props = ui.button("Properties");
                    self.controls.insert("properties".into(), props.rect);
                    if props.clicked() {
                        self.inspector_open = !self.inspector_open;
                    }
                    let advanced = ui.button("Advanced settings…");
                    self.controls.insert("advanced".into(), advanced.rect);
                    if advanced.clicked() {
                        self.advanced_requested = true;
                    }
                    let copy = ui.button("Copy Python");
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
                    let save = ui.button("Save PNG");
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
            } else { "Click a slice: Select / clear  ·  Left / Right: Change slice  ·  Esc: Clear  ·  F11: Full screen" });
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

    fn radial_properties(&mut self, ui: &mut egui::Ui, c: &mut FigureAccess<'_>) {
        let mut chart = c.data.radial.as_ref().unwrap().chart.clone();
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
