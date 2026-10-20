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
            let p = space.plot;
            *end = if self.tool.axis().is_some() {
                [
                    point[0].clamp(p.x, p.x + p.width),
                    point[1].clamp(p.y, p.y + p.height),
                ]
            } else {
                point
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
impl editor::Editor {
    pub(super) fn drawing_ui(&mut self, root: &mut egui::Ui, c: &FigureAccess<'_>) {
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
            let owner = matches!(
                config.active_layer(),
                renderer::LayerRef::Base | renderer::LayerRef::Annotations
            );
            ([config.polar.is_none(); 2], config.polar.is_none(), owner)
        };
        if !owner || !self.drawing.tool.allowed(axes) {
            self.drawing.cancel();
        }
        if !data {
            self.drawing.data_anchor = false;
        }
        egui::Panel::top("drawing_tools").show(root,|ui| {
            egui::ScrollArea::horizontal().show(ui,|ui| {ui.horizontal(|ui| {
                for (tool,label) in [(Tool::Select,"Select"),(Tool::Text,"Text"),(Tool::Arrow,"Arrow"),(Tool::HLine,"H line"),(Tool::VLine,"V line"),(Tool::HSpan,"H band"),(Tool::VSpan,"V band")] {
                    let enabled=tool==Tool::Select || owner&&tool.allowed(axes);
                    let response=ui.add_enabled(enabled,egui::Button::selectable(self.drawing.tool==tool,label)).on_disabled_hover_text(if !owner {"Annotations belong to the root panel; select that panel first."}else{"This chart has no numeric value axis in this direction."});
                    self.controls.insert(format!("draw_{}",tool.name()),response.rect);
                    if response.clicked() {self.drawing.cancel();self.drawing.tool=tool;}
                }
                let r=ui.add_enabled(data&&owner,egui::Checkbox::new(&mut self.drawing.data_anchor,"Follow data"));self.controls.insert("draw_data_anchor".into(),r.rect);
            });});
            ui.weak(if !owner {"Select the root panel to draw annotations."}else if self.drawing.tool==Tool::Text {"Click to place text, then edit it in Properties. Esc: cancel."}else if self.drawing.tool==Tool::Select {"Choose a drawing tool. Select annotations in the chart or object tree to edit."}else {"Drag to draw. Release to create and edit. Esc: cancel. Follow data: move with axis ranges."});
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
