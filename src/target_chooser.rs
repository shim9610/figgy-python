//! Transient disambiguation. Preview never edits the Figure document.
use super::*;
use renderer::LayerRef;

#[derive(Clone)]
pub(super) struct Choice {
    pub key: String,
    pub label: String,
    pub detail: String,
    pub color: Color,
    pub layer: LayerRef,
    pub target: Option<String>,
    pub pick: Option<renderer::config::PickedDataRef>,
}
fn owner(c: &FigureAccess<'_>, layer: LayerRef) -> String {
    let index = interaction::panel_index(layer);
    let label = interaction::panel_label(c.data.chart.config(), c.data.identity.as_ref(), index);
    let overlay = match layer {
        LayerRef::Overlay(i) | LayerRef::SubplotOverlay(_, i) => Some(i),
        _ => None,
    };
    if let Some(i) = overlay {
        let id = c
            .data
            .identity
            .as_ref()
            .and_then(|v| v["panels"][index]["overlays"][i].as_str())
            .unwrap_or("Secondary Y");
        format!("{label} · Right Y · {id}")
    } else {
        format!("{label} · Primary axes")
    }
}
fn series_color(s: &SeriesConfig) -> Color {
    let value = serde_json::to_value(&s.render_type).unwrap();
    let style = value.as_object().unwrap().values().next().unwrap();
    for color in [
        &style["line"]["line_color"],
        &style["scatter"]["point_color"],
        &style["bar"]["fill_color"],
    ] {
        if let Ok(color) = serde_json::from_value::<Color>(color.clone()) {
            return color;
        }
    }
    Color::from_rgb8(85, 105, 130)
}
impl Choice {
    pub fn panel(c: &FigureAccess<'_>, index: usize) -> Self {
        let id = interaction::panel_id(c.data.identity.as_ref(), index);
        Self {
            key: format!("panel/{id}"),
            label: interaction::panel_label(c.data.chart.config(), c.data.identity.as_ref(), index),
            detail: format!("Chart · {id}"),
            color: Color::from_rgb8(38, 99, 173),
            layer: interaction::base_layer(index),
            target: None,
            pick: None,
        }
    }
    pub fn data(c: &FigureAccess<'_>, hit: interaction::DataHit) -> Self {
        let target = hit.reference.series_id().to_owned();
        let color = c
            .data
            .series
            .iter()
            .find(|s| s.series_id == target)
            .map(series_color)
            .unwrap_or(Color::BLACK);
        Self {
            key: format!("series/{target}"),
            label: editor::object_name(&target, c.data),
            detail: format!("{} · {}", owner(c, hit.layer), target),
            color,
            layer: hit.layer,
            target: Some(target),
            pick: Some(hit.reference),
        }
    }
    pub fn element(c: &FigureAccess<'_>, layer: LayerRef, target: String) -> Self {
        Self {
            key: format!("element/{target}"),
            label: editor::object_name(target.rsplit(':').next().unwrap(), c.data),
            detail: owner(c, layer),
            color: Color::from_rgb8(85, 105, 130),
            layer,
            target: Some(target),
            pick: None,
        }
    }
    pub fn apply(&self, c: &mut FigureAccess<'_>) -> PyResult<()> {
        let mut cfg = c.data.chart.config().clone();
        cfg.set_active_layer(self.layer);
        cfg.picked_points = None;
        cfg.picked_data = self
            .pick
            .clone()
            .map(|p| renderer::config::DataSelectionsConfig {
                refs: vec![p],
                ..Default::default()
            });
        if cfg != *c.data.chart.config() {
            c.commit_config(cfg)?;
        }
        Ok(())
    }
}
pub(super) struct Chooser {
    pub choices: Vec<Choice>,
    pub point: (f32, f32),
    pub revision: u64,
    pub active: usize,
    filter: String,
    pub rect: egui::Rect,
}
pub(super) enum Action {
    Choose(Choice),
    Cancel,
}
impl Chooser {
    pub fn new(choices: Vec<Choice>, point: (f32, f32), revision: u64) -> Self {
        Self {
            choices,
            point,
            revision,
            active: 0,
            filter: String::new(),
            rect: egui::Rect::NOTHING,
        }
    }
    pub fn preview(&self) -> Option<&Choice> {
        self.choices.get(self.active)
    }
    pub fn show(
        &mut self,
        root: &mut egui::Ui,
        stage: egui::Rect,
        dpr: f32,
        controls: &mut HashMap<String, egui::Rect>,
    ) -> Option<Action> {
        let mut action = None;
        let indices: Vec<_> = self
            .choices
            .iter()
            .enumerate()
            .filter(|(_, v)| {
                format!("{} {}", v.label, v.detail)
                    .to_lowercase()
                    .contains(&self.filter.to_lowercase())
            })
            .map(|(i, _)| i)
            .collect();
        if !indices.contains(&self.active) {
            self.active = indices.first().copied().unwrap_or(usize::MAX);
        }
        let pointer_moved = root.input(|i| {
            i.events
                .iter()
                .any(|e| matches!(e, egui::Event::PointerMoved(_)))
        });
        let cursor = indices.iter().position(|i| *i == self.active).unwrap_or(0);
        root.input_mut(|i| {
            if i.consume_key(egui::Modifiers::NONE, egui::Key::Escape) {
                action = Some(Action::Cancel);
            }
            let next = if i.consume_key(egui::Modifiers::NONE, egui::Key::ArrowDown) {
                Some((cursor + 1) % indices.len().max(1))
            } else if i.consume_key(egui::Modifiers::NONE, egui::Key::ArrowUp) {
                Some((cursor + indices.len().max(1) - 1) % indices.len().max(1))
            } else {
                None
            };
            if let Some(next) = next.and_then(|n| indices.get(n)) {
                self.active = *next;
            }
            if i.consume_key(egui::Modifiers::NONE, egui::Key::Enter) {
                action = self
                    .choices
                    .get(self.active)
                    .filter(|_| !indices.is_empty())
                    .cloned()
                    .map(Action::Choose);
            }
        });
        let width = stage.width().min(340.).max(180.);
        let height = (100. + indices.len().min(8) as f32 * 52.).min(stage.height());
        let pos = egui::pos2(
            (self.point.0 / dpr + 12.)
                .clamp(stage.left(), (stage.right() - width).max(stage.left())),
            (self.point.1 / dpr + 12.)
                .clamp(stage.top(), (stage.bottom() - height).max(stage.top())),
        );
        let area = egui::Area::new(egui::Id::new("target_chooser"))
            .order(egui::Order::Foreground)
            .fixed_pos(pos)
            .show(root.ctx(), |ui| {
                egui::Frame::popup(ui.style())
                    .inner_margin(10.)
                    .show(ui, |ui| {
                        ui.set_width(width - 20.);
                        ui.horizontal(|ui| {
                            ui.strong(format!("Choose what to edit ({})", self.choices.len()));
                            if ui.small_button("×").clicked() {
                                action = Some(Action::Cancel);
                            }
                        });
                        ui.weak("Point to preview · Click to select");
                        if self.choices.len() > 8 {
                            let r = ui.add(
                                egui::TextEdit::singleline(&mut self.filter)
                                    .hint_text("Find a target…"),
                            );
                            controls.insert("choice_search".into(), r.rect);
                        }
                        egui::ScrollArea::vertical()
                            .max_height((height - 80.).max(50.))
                            .show(ui, |ui| {
                                for &index in &indices {
                                    let choice = &self.choices[index];
                                    let color = egui::Color32::from_rgba_unmultiplied(
                                        (choice.color.r * 255.) as u8,
                                        (choice.color.g * 255.) as u8,
                                        (choice.color.b * 255.) as u8,
                                        255,
                                    );
                                    let response = ui.add_sized(
                                        [width - 20., 48.],
                                        egui::Button::selectable(
                                            index == self.active,
                                            egui::RichText::new(format!(
                                                "{}\n{}",
                                                choice.label, choice.detail
                                            )),
                                        ),
                                    );
                                    ui.painter().line_segment(
                                        [
                                            response.rect.left_center() + egui::vec2(4., -4.),
                                            response.rect.left_center() + egui::vec2(15., -4.),
                                        ],
                                        egui::Stroke::new(3., color),
                                    );
                                    controls
                                        .insert(format!("choose:{}", choice.key), response.rect);
                                    if response.hovered() && pointer_moved {
                                        self.active = index;
                                    }
                                    if response.clicked() {
                                        action = Some(Action::Choose(choice.clone()));
                                    }
                                }
                                if indices.is_empty() {
                                    ui.weak("No matching targets");
                                }
                            });
                        ui.weak("Up/Down: preview · Enter: select · Esc: cancel");
                    });
            });
        self.rect = area.response.rect;
        action
    }
}
