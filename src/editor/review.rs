use super::*;

#[derive(Default)]
pub(super) struct Context {
    menu: Option<(egui::Pos2, Vec<(String, String)>)>,
    target: Option<(String, String)>,
    text: String,
    dialog_point: egui::Pos2,
    editing: Option<String>,
    pub(super) list: bool,
}
impl Editor {
    pub(crate) fn review_enabled(&self) -> bool {
        self.review.as_ref().is_some_and(|shared| {
            let state = shared.lock().unwrap();
            state["enabled"] == true && state["request"].is_null()
        })
    }
    pub(crate) fn take_tree_review_target(&mut self) {
        if let Some(node) = self.navigator.comment_target.take() {
            self.review_context.target = Some((node.key, node.label));
            self.review_context.text.clear();
            self.review_context.editing = None;
        }
    }
    pub(crate) fn review_target(
        &mut self,
        point: egui::Pos2,
        c: &FigureAccess<'_>,
        targets: Vec<(renderer::LayerRef, String)>,
    ) {
        if !self.review_enabled() {
            return;
        }
        fn label(nodes: &[navigation::Node], id: &str) -> Option<String> {
            for node in nodes {
                if node.key == id {
                    return Some(node.label.clone());
                }
                if let Some(v) = label(&node.children, id) {
                    return Some(v);
                }
            }
            None
        }
        let snapshot = c.snapshot();
        self.review_context.dialog_point = point;
        let outline = navigation::nodes(&snapshot);
        let objects = targets
            .into_iter()
            .filter_map(|(layer, target)| {
                crate::property_catalog::selected(&snapshot, &target, layer, None).map(|object| {
                    (
                        object.id.clone(),
                        label(&outline, &object.id).unwrap_or_else(|| object_name(&target, c.data)),
                    )
                })
            })
            .collect::<Vec<_>>();
        if !objects.is_empty() {
            self.review_context.menu = Some((point, objects));
        }
    }
    pub(crate) fn review_context_ui(&mut self, root: &mut egui::Ui) {
        let Some(shared) = self.review.clone() else {
            return;
        };
        let mut state = shared.lock().unwrap();
        if state.is_null() || !state["request"].is_null() {
            return;
        }
        if root.input(|i| i.key_pressed(egui::Key::Escape)) {
            self.review_context.menu = None;
            self.review_context.target = None;
            self.review_context.list = false;
        }
        let font = egui::FontId::new(
            state["font_size"].as_f64().unwrap_or(14.) as f32,
            if self.review_font.is_empty() {
                egui::FontFamily::Proportional
            } else {
                egui::FontFamily::Name("figgy-review".into())
            },
        );
        if let Some((point, targets)) = self.review_context.menu.clone() {
            let area = egui::Area::new(egui::Id::new("review_context_menu"))
                .order(egui::Order::Foreground)
                .fixed_pos(point)
                .show(root.ctx(), |ui| {
                    egui::Frame::popup(ui.style()).show(ui, |ui| {
                        for (id, label) in targets {
                            let button = ui.button(format!("Add review comment · {label}"));
                            self.controls
                                .insert(format!("review_target:{id}"), button.rect);
                            if button.clicked() {
                                self.review_context.target = Some((id, label));
                                self.review_context.text.clear();
                                self.review_context.editing = None;
                                self.review_context.menu = None;
                            }
                        }
                    });
                });
            if root.input(|i| {
                i.key_pressed(egui::Key::Escape)
                    || i.pointer.any_pressed()
                        && i.pointer
                            .interact_pos()
                            .is_some_and(|p| !area.response.rect.contains(p))
            }) {
                self.review_context.menu = None;
            }
        }
        if let Some((target, label)) = self.review_context.target.clone() {
            egui::Window::new("Element review comment").id(egui::Id::new("review_target_dialog")).collapsible(false).default_width(380.).default_pos(self.review_context.dialog_point+egui::vec2(10.,10.)).show(root.ctx(),|ui|{
                ui.label(label.clone());
                let input=ui.add(egui::TextEdit::multiline(&mut self.review_context.text).font(font.clone()).desired_width(f32::INFINITY).desired_rows(4));
                self.controls.insert("review_target_text".into(),input.rect);
                ui.horizontal(|ui|{
                    let save=ui.add_enabled(!self.review_context.text.trim().is_empty(),egui::Button::new("Save comment"));
                    self.controls.insert("review_target_save".into(),save.rect);
                    if save.clicked(){
                        if !state["target_comments"].is_array(){state["target_comments"]=json!([]);}
                        let comments=state["target_comments"].as_array_mut().unwrap();
                        let id=self.review_context.editing.take().unwrap_or_else(||format!("ui-{}-{}",std::process::id(),std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
                        comments.retain(|v|v["id"]!=id);
                        comments.push(json!({"id":id,"target":target,"label":label,"text":self.review_context.text,"channel":"ui_target"}));
                        self.review_context.target=None;
                    }
                    let cancel=ui.button("Cancel");self.controls.insert("review_target_cancel".into(),cancel.rect);
                    if cancel.clicked(){self.review_context.target=None;}
                });
            });
        }
        if self.review_context.list {
            let mut open = true;
            egui::Window::new("Element review comments")
                .id(egui::Id::new("review_target_list"))
                .open(&mut open)
                .default_width(420.)
                .show(root.ctx(), |ui| {
                    let mut remove = None;
                    for (i, item) in state["target_comments"]
                        .as_array()
                        .unwrap_or(&vec![])
                        .iter()
                        .enumerate()
                    {
                        ui.group(|ui| {
                            ui.label(
                                item["label"]
                                    .as_str()
                                    .or_else(|| item["target"].as_str())
                                    .unwrap_or("Chart element"),
                            );
                            ui.label(
                                RichText::new(item["text"].as_str().unwrap_or(""))
                                    .font(font.clone()),
                            );
                            let edit = ui.button("Edit");
                            self.controls.insert(
                                format!("review_target_edit:{}", item["id"].as_str().unwrap()),
                                edit.rect,
                            );
                            if edit.clicked() {
                                self.review_context.target = Some((
                                    item["target"].as_str().unwrap().into(),
                                    item["label"].as_str().unwrap_or("Chart element").into(),
                                ));
                                self.review_context.text = item["text"].as_str().unwrap().into();
                                self.review_context.editing =
                                    Some(item["id"].as_str().unwrap().into());
                            }
                            let delete = ui.button("Delete");
                            self.controls.insert(
                                format!("review_target_delete:{}", item["id"].as_str().unwrap()),
                                delete.rect,
                            );
                            if delete.clicked() {
                                remove = Some(i);
                            }
                        });
                    }
                    if let Some(i) = remove {
                        state["target_comments"].as_array_mut().unwrap().remove(i);
                    }
                });
            self.review_context.list = open;
        }
    }
}
