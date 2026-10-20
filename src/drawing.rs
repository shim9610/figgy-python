//! Transient drawing gestures; only a completed gesture enters the document.
use super::*;
use renderer::annotation::{
    AnchorKind, Annotation, AnnotationAxis, AnnotationKind, AnnotationSpace, ArrowStyle, PixelSpace,
};

#[derive(Clone, Copy, PartialEq, Eq, Default)]
pub(super) enum Tool {
    #[default]
    Select,
    Text,
    Arrow,
    HLine,
    VLine,
    HSpan,
    VSpan,
}
impl Tool {
    pub fn name(self) -> &'static str {
        match self {
            Self::Select => "select",
            Self::Text => "text",
            Self::Arrow => "arrow",
            Self::HLine => "hline",
            Self::VLine => "vline",
            Self::HSpan => "hspan",
            Self::VSpan => "vspan",
        }
    }
    fn axis(self) -> Option<AnnotationAxis> {
        match self {
            Self::HLine | Self::HSpan => Some(AnnotationAxis::Y),
            Self::VLine | Self::VSpan => Some(AnnotationAxis::X),
            _ => None,
        }
    }
    pub fn allowed(self, axes: [bool; 2]) -> bool {
        self.axis()
            .is_none_or(|a| axes[usize::from(a == AnnotationAxis::Y)])
    }
}
#[derive(Default)]
pub(super) struct Drawing {
    pub open: bool,
    pub tool: Tool,
    pub data_anchor: bool,
    pub gesture: Option<(PixelSpace, [f32; 2], [f32; 2])>,
}
impl Drawing {
    pub fn cancel(&mut self) {
        self.tool = Tool::Select;
        self.gesture = None;
    }
    pub fn begin(&mut self, space: PixelSpace, point: [f32; 2]) {
        let panel = space.panel;
        if point[0] < panel.x
            || point[0] >= panel.x + panel.width
            || point[1] < panel.y
            || point[1] >= panel.y + panel.height
        {
            return;
        }
        let p = space.plot;
        if self.tool.axis().is_some()
            && (point[0] < p.x
                || point[0] > p.x + p.width
                || point[1] < p.y
                || point[1] > p.y + p.height)
        {
            return;
        }
        self.gesture = Some((space, point, point));
    }
    pub fn update(&mut self, point: [f32; 2]) {
        if let Some((space, _, end)) = &mut self.gesture {
            let p = if self.tool.axis().is_some() {
                space.plot
            } else {
                space.panel
            };
            *end = {
                [
                    point[0].clamp(p.x, p.x + p.width),
                    point[1].clamp(p.y, p.y + p.height),
                ]
            };
        }
    }
    pub fn finish(&mut self) -> Option<Annotation> {
        let (space, from, to) = self.gesture.take()?;
        let tool = self.tool;
        self.tool = Tool::Select;
        if matches!(tool, Tool::Arrow | Tool::HSpan | Tool::VSpan)
            && (to[0] - from[0]).hypot(to[1] - from[1]) < 3.
        {
            return None;
        }
        let anchor = |p| {
            space.px_to_anchor(
                p,
                if self.data_anchor {
                    AnchorKind::Data
                } else {
                    AnchorKind::Ratio
                },
            )
        };
        let value = |p: [f32; 2], axis| {
            space.px_to_value(
                axis,
                if axis == AnnotationAxis::X {
                    p[0]
                } else {
                    p[1]
                },
            )
        };
        let kind = match tool {
            Tool::Text => AnnotationKind::Text {
                anchor: anchor(to)?,
                text: renderer::text::RichText::plain(
                    "Text",
                    Color::from_rgb8(35, 45, 60),
                    16.,
                    "",
                ),
                box_style: None,
            },
            Tool::Arrow => AnnotationKind::Arrow {
                from: anchor(from)?,
                to: anchor(to)?,
                style: ArrowStyle::default(),
                text: None,
            },
            Tool::HLine | Tool::VLine => {
                let axis = tool.axis()?;
                AnnotationKind::ReferenceLine {
                    axis,
                    value: value(to, axis)?,
                    style: Default::default(),
                    label: None,
                }
            }
            Tool::HSpan | Tool::VSpan => {
                let axis = tool.axis()?;
                let (a, b) = (value(from, axis)?, value(to, axis)?);
                if a == b {
                    return None;
                }
                AnnotationKind::Span {
                    axis,
                    from: a.min(b),
                    to: a.max(b),
                    fill: Color::from_rgba8(38, 99, 173, 45),
                }
            }
            Tool::Select => return None,
        };
        let mut item = Annotation::new(kind);
        static NEXT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
        item.id = format!(
            "annotation_{:x}_{:x}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos(),
            NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
        );
        Some(item)
    }
    pub fn preview(&self, painter: &egui::Painter, transform: impl Fn([f32; 2]) -> egui::Pos2) {
        let Some((space, from, to)) = self.gesture else {
            return;
        };
        let color = egui::Color32::from_rgb(38, 99, 173);
        let stroke = egui::Stroke::new(1.5, color);
        let a = transform(from);
        let b = transform(to);
        let p = space.plot;
        match self.tool {
            Tool::Arrow => painter.arrow(a, b - a, stroke),
            Tool::Text => {
                painter.text(
                    b,
                    egui::Align2::LEFT_TOP,
                    "Text",
                    egui::FontId::proportional(16.),
                    color,
                );
            }
            Tool::HLine => {
                painter.line_segment(
                    [transform([p.x, to[1]]), transform([p.x + p.width, to[1]])],
                    stroke,
                );
            }
            Tool::VLine => {
                painter.line_segment(
                    [transform([to[0], p.y]), transform([to[0], p.y + p.height])],
                    stroke,
                );
            }
            Tool::HSpan | Tool::VSpan => {
                let (a, b) = if self.tool == Tool::HSpan {
                    (transform([p.x, from[1]]), transform([p.x + p.width, to[1]]))
                } else {
                    (
                        transform([from[0], p.y]),
                        transform([to[0], p.y + p.height]),
                    )
                };
                painter.rect_filled(
                    egui::Rect::from_two_pos(a, b),
                    0.,
                    color.gamma_multiply(0.2),
                );
            }
            Tool::Select => {}
        }
    }
}

/// A host-side text transaction. The document is untouched until confirmation.
pub(super) struct InlineText {
    item: Annotation,
    original: Option<Annotation>,
    value: String,
    focus: bool,
    composing: bool,
}

impl editor::Editor {
    pub(super) fn begin_inline_text(&mut self, item: Annotation, existing: bool) {
        let AnnotationKind::Text { text, .. } = &item.kind else {
            return;
        };
        let value = if existing {
            editor::display_text(&serde_json::to_value(&text.segments).unwrap())
        } else {
            String::new()
        };
        self.inline_text = Some(InlineText {
            original: existing.then(|| item.clone()),
            item,
            value,
            focus: true,
            composing: false,
        });
    }

    pub(super) fn inline_text_ui(
        &mut self,
        root: &mut egui::Ui,
        c: &mut FigureAccess<'_>,
        space: PixelSpace,
        transform: impl Fn([f32; 2]) -> egui::Pos2,
        font_scale: f32,
    ) -> Option<String> {
        let draft = self.inline_text.as_mut()?;
        let AnnotationKind::Text { anchor, text, .. } = &draft.item.kind else {
            return None;
        };
        let Some(point) = space.anchor_to_px(anchor) else {
            self.inline_text = None;
            return None;
        };
        let size = (text.font_size * font_scale).clamp(10., 72.);
        let pos = transform(point) - egui::vec2(5., 4.);
        let first = draft.focus;
        let mut apply = false;
        let mut cancel = false;
        let mut ime_event = false;
        for event in root.input(|i| i.events.clone()) {
            if let egui::Event::Ime(event) = event {
                ime_event = true;
                draft.composing = matches!(event, egui::ImeEvent::Preedit { .. });
            }
        }
        egui::Area::new(egui::Id::new("inline_annotation_text"))
            .order(egui::Order::Foreground)
            .fixed_pos(pos)
            .constrain_to(self.stage)
            .show(root.ctx(), |ui| {
                egui::Frame::new()
                    .fill(egui::Color32::WHITE)
                    .stroke(egui::Stroke::new(1., egui::Color32::from_rgb(38, 99, 173)))
                    .inner_margin(4)
                    .show(ui, |ui| {
                        let width = (draft.value.chars().count() as f32 * size * 0.65 + 30.)
                            .clamp(40., (self.stage.width() - 12.).clamp(40., 420.));
                        if !draft.composing && !ime_event {
                            cancel = ui.input_mut(|i| {
                                i.consume_key(egui::Modifiers::NONE, egui::Key::Escape)
                            });
                            ui.input_mut(|i| i.events.retain(|event| {
                                if matches!(event, egui::Event::Key { key: egui::Key::Enter, pressed: true, modifiers, .. }
                                    if !modifiers.shift && !modifiers.ctrl && !modifiers.alt && !modifiers.command)
                                { apply = true; false } else { true }
                            }));
                        }
                        let mut output = egui::TextEdit::multiline(&mut draft.value)
                            .id_salt("inline_annotation_input")
                            .font(egui::FontId::proportional(size))
                            .desired_width(width)
                            .desired_rows(1)
                            .hint_text("Type text")
                            .frame(egui::Frame::NONE)
                            .show(ui);
                        self.controls
                            .insert("inline_text".into(), output.response.rect);
                        if first {
                            output.response.request_focus();
                            output.state.cursor.set_char_range(Some(
                                egui::text::CCursorRange::two(
                                    egui::text::CCursor::new(0),
                                    egui::text::CCursor::new(draft.value.chars().count()),
                                ),
                            ));
                            output.state.store(ui.ctx(), output.response.id);
                            draft.focus = false;
                        }
                        apply |= !first && output.response.lost_focus();
                        ui.small("Enter: apply · Shift+Enter: new line · Esc: cancel");
                    });
            });
        if !apply && !cancel {
            return None;
        }
        let mut draft = self.inline_text.take().unwrap();
        root.ctx().request_repaint();
        if cancel || draft.value.trim().is_empty() {
            return None;
        }
        if let Some(original) = &draft.original
            && let AnnotationKind::Text { text, .. } = &original.kind
            && editor::display_text(&serde_json::to_value(&text.segments).unwrap()) == draft.value
        {
            return Some(format!("annotation:{}", draft.item.id));
        }
        let AnnotationKind::Text { text, .. } = &mut draft.item.kind else {
            return None;
        };
        let old = serde_json::to_value(&text.segments).unwrap();
        let fresh =
            serde_json::to_value(renderer::text::rich_segments_from_text(&draft.value)).unwrap();
        text.segments =
            serde_json::from_value(editor::preserve_segment_styles(&old, fresh)).unwrap();
        let target = format!("annotation:{}", draft.item.id);
        let result = if let Some(document) = &c.data.document {
            let mut chart = document.chart.clone();
            let items = &mut chart.annotations_mut().items;
            let index = if let Some(original) = &draft.original {
                let Some(index) = items
                    .iter()
                    .position(|v| v.id == original.id && v == original)
                else {
                    self.error =
                        "Text changed elsewhere. Reopen it to edit the current version.".into();
                    return None;
                };
                if items[index] == draft.item {
                    return Some(target);
                }
                items[index] = draft.item;
                index
            } else {
                let index = items.len();
                items.push(draft.item);
                index
            };
            chart.annotations_mut().visible = true;
            chart.set_active_layer(renderer::LayerRef::Annotations);
            chart.clear_selection();
            chart.decorations_mut().selected = Some(renderer::DecorationId::Annotation(index));
            c.set_document(chart)
        } else {
            let mut cfg = c.data.chart.config().clone();
            if let Some(original) = &draft.original {
                let Some(item) = cfg
                    .annotations
                    .items
                    .iter_mut()
                    .find(|v| v.id == original.id && *v == original)
                else {
                    self.error =
                        "Text changed elsewhere. Reopen it to edit the current version.".into();
                    return None;
                };
                if *item == draft.item {
                    return Some(target);
                }
                *item = draft.item;
            } else {
                cfg.annotations.items.push(draft.item);
            }
            cfg.annotations.visible = true;
            cfg.set_active_layer(renderer::LayerRef::Annotations);
            cfg.picked_data = None;
            cfg.picked_points = None;
            c.commit_config(cfg)
        };
        match result {
            Ok(()) => Some(target),
            Err(e) => {
                self.error = e.to_string();
                None
            }
        }
    }
}
impl editor::Editor {
    pub(super) fn drawing_ui(&mut self, root: &mut egui::Ui, c: &mut FigureAccess<'_>) {
        if !self.drawing.open {
            return;
        }
        let config = c.data.chart.config();
        let (axes, data, owner) = if let Some(d) = &c.data.document {
            match d.chart.family() {
                "boxplot" | "categorical" => {
                    let state = serde_json::to_value(c.snapshot()).unwrap();
                    let horizontal = state[d.chart.family()]["direction"] == "Horizontal";
                    ([horizontal, !horizontal], true, true)
                }
                _ => ([false, false], false, true),
            }
        } else {
            let owner = interaction::panel_index(config.active_layer()) == 0 && self.panel_focused;
            ([config.polar.is_none(); 2], config.polar.is_none(), owner)
        };
        if !owner || !self.drawing.tool.allowed(axes) {
            self.drawing.cancel();
        }
        if !data {
            self.drawing.data_anchor = false;
        }
        let unavailable = format!(
            "Annotations are available on “{}”. Select that chart to draw.",
            interaction::panel_label(config, c.data.identity.as_ref(), 0)
        );
        egui::Panel::top("drawing_tools").show(root,|ui| {
            egui::ScrollArea::horizontal().show(ui,|ui| {ui.horizontal(|ui| {
                for (tool,label) in [(Tool::Select,"Select"),(Tool::Text,"Text"),(Tool::Arrow,"Arrow"),(Tool::HLine,"H line"),(Tool::VLine,"V line"),(Tool::HSpan,"H band"),(Tool::VSpan,"V band")] {
                    let enabled=tool==Tool::Select || owner&&tool.allowed(axes);
                    let response=ui.add_enabled(enabled,egui::Button::selectable(self.drawing.tool==tool,label)).on_disabled_hover_text(if !owner {unavailable.as_str()}else{"This chart has no numeric value axis in this direction."});
                    self.controls.insert(format!("draw_{}",tool.name()),response.rect);
                    if response.clicked() {
                        self.drawing.cancel();self.drawing.tool=tool;self.edit_area=false;
                        if let Some(document)=&c.data.document {let mut chart=document.chart.clone();if chart.decorations().selected==Some(renderer::DecorationId::DataArea){chart.clear_selection();if let Err(e)=c.set_document(chart){self.error=e.to_string();}}}
                    }
                }
                let r=ui.add_enabled(data&&owner,egui::Checkbox::new(&mut self.drawing.data_anchor,"Follow data"));self.controls.insert("draw_data_anchor".into(),r.rect);
            });});
            ui.weak(if !owner {unavailable.as_str()}else if self.drawing.tool==Tool::Text {"Click and type. Enter: apply. Esc: cancel."}else if self.drawing.tool==Tool::Select {"Double-click text to edit it. Drag annotations to move them."}else {"Drag to draw. Release to create and edit. Esc: cancel. Follow data: move with axis ranges."});
        });
        if root.input(|i| i.key_pressed(egui::Key::Escape)) {
            self.drawing.cancel();
        }
        if self.drawing.tool != Tool::Select
            && root
                .input(|i| i.pointer.hover_pos())
                .is_some_and(|p| self.stage.contains(p))
        {
            root.ctx().set_cursor_icon(egui::CursorIcon::Crosshair);
        }
    }
    pub(super) fn drawing_button(&mut self, ui: &mut egui::Ui) {
        let r = ui.selectable_label(self.drawing.open, "Draw");
        self.controls.insert("draw".into(), r.rect);
        if r.clicked() {
            self.drawing.open = !self.drawing.open;
            self.drawing.cancel();
        }
    }
}
