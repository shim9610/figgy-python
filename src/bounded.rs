//! Bounded chart hosts delegate geometry, picking and drag policy to figgy-renderer.
use super::*;
use renderer::{DecorationLayout, boxplot::*, categorical::*, radial::*};

#[derive(Clone, PartialEq)]
pub(super) enum DocumentChart {
    Radial(RadialChart),
    Categorical(CategoricalChart),
    BoxPlot(BoxPlotChart),
}
impl DocumentChart {
    pub fn family(&self) -> &'static str {
        match self {
            Self::Radial(_) => "radial",
            Self::Categorical(_) => "categorical",
            Self::BoxPlot(_) => "boxplot",
        }
    }
    pub fn decorations(&self) -> &DecorationLayout {
        match self {
            Self::Radial(c) => &c.decorations,
            Self::Categorical(c) => &c.decorations,
            Self::BoxPlot(c) => &c.decorations,
        }
    }
    pub fn decorations_mut(&mut self) -> &mut DecorationLayout {
        match self {
            Self::Radial(c) => &mut c.decorations,
            Self::Categorical(c) => &mut c.decorations,
            Self::BoxPlot(c) => &mut c.decorations,
        }
    }
    pub fn radial(&self) -> Option<&RadialChart> {
        if let Self::Radial(c) = self {
            Some(c)
        } else {
            None
        }
    }
    pub fn validate(&self, rect: Rect) -> PyResult<()> {
        if rect.width < 160 || rect.height < 160 {
            return Err(invalid(
                "bounded chart canvas must be at least 160x160 pixels",
            ));
        }
        match self {
            Self::Radial(c) => {
                validate_model_numbers(c, "radial")?;
                c.validate().map_err(invalid)
            }
            Self::Categorical(c) => {
                validate_model_numbers(c, "categorical")?;
                c.validate().map_err(invalid)
            }
            Self::BoxPlot(c) => {
                validate_model_numbers(c, "boxplot")?;
                c.validate().map_err(invalid)
            }
        }
    }
    pub fn selected_json(&self) -> serde_json::Value {
        match self {
            Self::Radial(c) => json!(c.interaction.selected),
            Self::Categorical(c) => json!(c.selected),
            Self::BoxPlot(c) => json!(c.selected),
        }
    }
    pub fn clear_selection(&mut self) {
        self.decorations_mut().selected = None;
        match self {
            Self::Radial(c) => c.interaction.selected = None,
            Self::Categorical(c) => c.selected = None,
            Self::BoxPlot(c) => c.selected = None,
        }
    }
    pub fn select_at(&mut self, frame: &DocumentFrame, point: [f32; 2], toggle: bool) {
        match (self, frame) {
            (Self::Radial(c), DocumentFrame::Radial(f)) => {
                let hit = f.hit_test(point).or_else(|| {
                    f.hit_test_at_rest(point)
                        .filter(|t| Some(*t) == c.interaction.hovered)
                });
                c.interaction.selected = if toggle && hit == c.interaction.selected {
                    None
                } else {
                    hit
                };
            }
            (Self::Categorical(c), DocumentFrame::Categorical(f)) => {
                let hit = f.hit_test(point);
                c.selected = if toggle && hit == c.selected {
                    None
                } else {
                    hit
                };
            }
            (Self::BoxPlot(c), DocumentFrame::BoxPlot(f)) => {
                let hit = f.hit_test(point).map(|p| p.target);
                c.selected = if toggle && hit == c.selected {
                    None
                } else {
                    hit
                };
            }
            _ => unreachable!(),
        }
    }
    pub fn hover(&mut self, frame: &DocumentFrame, point: Option<[f32; 2]>, dt: f32) -> bool {
        match (self, frame) {
            (Self::Radial(c), DocumentFrame::Radial(f)) => {
                let hit = point.and_then(|p| {
                    f.hit_test(p).or_else(|| {
                        f.hit_test_at_rest(p)
                            .filter(|t| Some(*t) == c.interaction.hovered)
                    })
                });
                c.interaction.animate_hover(hit, dt, 0.16)
            }
            (Self::Categorical(c), DocumentFrame::Categorical(f)) => {
                let hit = point.and_then(|p| f.hit_test(p));
                let changed = hit != c.hovered;
                c.hovered = hit;
                changed
            }
            (Self::BoxPlot(c), DocumentFrame::BoxPlot(f)) => {
                let hit = point.and_then(|p| f.hit_test(p)).map(|p| p.target);
                let changed = hit != c.hovered;
                c.hovered = hit;
                changed
            }
            _ => unreachable!(),
        }
    }
    pub fn step(&mut self, backwards: bool) {
        fn next<T: PartialEq + Clone>(items: Vec<T>, selected: &mut Option<T>, backwards: bool) {
            if items.is_empty() {
                return;
            }
            let i = selected
                .as_ref()
                .and_then(|s| items.iter().position(|x| x == s));
            let n = items.len();
            let i = match i {
                Some(i) if backwards => (i + n - 1) % n,
                Some(i) => (i + 1) % n,
                None if backwards => n - 1,
                None => 0,
            };
            *selected = Some(items[i].clone());
        }
        match self {
            Self::Radial(c) => {
                let mut items = c
                    .slices
                    .iter()
                    .enumerate()
                    .filter(|(_, s)| s.value > 0.)
                    .map(|(i, _)| RadialTarget::main(i))
                    .collect::<Vec<_>>();
                if let Some(split) = &c.split {
                    items.extend(
                        split
                            .children
                            .iter()
                            .enumerate()
                            .filter(|(_, s)| s.value > 0.)
                            .map(|(i, _)| RadialTarget::detail(i)),
                    );
                }
                next(items, &mut c.interaction.selected, backwards);
            }
            Self::Categorical(c) => {
                let items = c
                    .categories
                    .iter()
                    .enumerate()
                    .flat_map(|(i, cat)| {
                        c.series.iter().filter_map(move |s| {
                            s.values[i].map(|_| CategoryBarTarget::new(&cat.id, &s.id))
                        })
                    })
                    .collect();
                next(items, &mut c.selected, backwards);
            }
            Self::BoxPlot(c) => {
                let items = c
                    .categories
                    .iter()
                    .enumerate()
                    .flat_map(|(i, cat)| {
                        c.series.iter().filter_map(move |s| {
                            s.values[i]
                                .as_ref()
                                .map(|_| BoxPlotTarget::new(&cat.id, &s.id))
                        })
                    })
                    .collect();
                next(items, &mut c.selected, backwards);
            }
        }
    }
}

pub(super) struct BoundedDocument {
    pub chart: DocumentChart,
    renderer: Option<DocumentRenderer>,
}
impl BoundedDocument {
    pub fn gpu_bytes(&self) -> u64 {
        self.renderer
            .as_ref()
            .map_or(0, DocumentRenderer::gpu_bytes)
    }
}
pub(super) enum DocumentRenderer {
    Radial(RadialRenderer),
    Categorical(CategoricalRenderer),
    BoxPlot(BoxPlotRenderer),
}
pub(super) enum DocumentFrame {
    Radial(Arc<RadialFrame>),
    Categorical(Arc<CategoricalFrame>),
    BoxPlot(Arc<BoxPlotFrame>),
}
impl DocumentRenderer {
    pub fn new(gpu: RendererDevice, chart: &DocumentChart) -> PyResult<Self> {
        Ok(match chart {
            DocumentChart::Radial(_) => Self::Radial(
                RadialRenderer::new(gpu, wgpu::TextureFormat::Rgba8Unorm).map_err(runtime)?,
            ),
            DocumentChart::Categorical(_) => Self::Categorical(
                CategoricalRenderer::new(gpu, wgpu::TextureFormat::Rgba8Unorm).map_err(runtime)?,
            ),
            DocumentChart::BoxPlot(_) => Self::BoxPlot(
                BoxPlotRenderer::new(gpu, wgpu::TextureFormat::Rgba8Unorm).map_err(runtime)?,
            ),
        })
    }
    pub fn prepare(
        &mut self,
        chart: &DocumentChart,
        size: (u32, u32),
        scale: f32,
    ) -> PyResult<DocumentFrame> {
        match (self, chart) {
            (Self::Radial(r), DocumentChart::Radial(c)) => Ok(DocumentFrame::Radial(
                r.prepare(c, size, scale).map_err(runtime)?,
            )),
            (Self::Categorical(r), DocumentChart::Categorical(c)) => Ok(
                DocumentFrame::Categorical(r.prepare(c, size, scale).map_err(runtime)?),
            ),
            (Self::BoxPlot(r), DocumentChart::BoxPlot(c)) => Ok(DocumentFrame::BoxPlot(
                r.prepare(c, size, scale).map_err(runtime)?,
            )),
            _ => Err(invalid("cannot change chart family")),
        }
    }
    pub fn export(
        &mut self,
        chart: &DocumentChart,
        size: (u32, u32),
        scale: f32,
    ) -> PyResult<renderer::RasterImage> {
        match (self, chart) {
            (Self::Radial(r), DocumentChart::Radial(c)) => {
                r.export_rgba(c, size, scale).map_err(runtime)
            }
            (Self::Categorical(r), DocumentChart::Categorical(c)) => {
                r.export_rgba(c, size, scale).map_err(runtime)
            }
            (Self::BoxPlot(r), DocumentChart::BoxPlot(c)) => {
                r.export_rgba(c, size, scale).map_err(runtime)
            }
            _ => Err(invalid("cannot change chart family")),
        }
    }
    pub fn gpu_bytes(&self) -> u64 {
        match self {
            Self::Radial(r) => r.gpu_memory_usage().total_bytes(),
            Self::Categorical(r) => r.gpu_memory_usage().total_bytes(),
            Self::BoxPlot(r) => r.gpu_memory_usage().total_bytes(),
        }
    }
    pub fn end_frame(&self) {
        match self {
            Self::Radial(r) => r.end_frame(),
            Self::Categorical(r) => r.end_frame(),
            Self::BoxPlot(r) => r.end_frame(),
        }
    }
}
impl DocumentFrame {
    pub fn decorations(&self) -> &renderer::decoration::DecorationMap {
        match self {
            Self::Radial(f) => f.decorations(),
            Self::Categorical(f) => f.decorations(),
            Self::BoxPlot(f) => f.decorations(),
        }
    }
    pub fn draw(&self, pass: &mut wgpu::RenderPass<'_>) {
        match self {
            Self::Radial(f) => f.draw(pass),
            Self::Categorical(f) => f.draw(pass),
            Self::BoxPlot(f) => f.draw(pass),
        }
    }
    pub fn has_data(&self, p: [f32; 2]) -> bool {
        match self {
            Self::Radial(f) => f.hit_test(p).is_some() || f.hit_test_at_rest(p).is_some(),
            Self::Categorical(f) => f.hit_test(p).is_some(),
            Self::BoxPlot(f) => f.hit_test(p).is_some(),
        }
    }
}
impl FigureAccess<'_> {
    pub(super) fn set_radial(&mut self, json: &str) -> PyResult<()> {
        self.set_document(DocumentChart::Radial(parse(json)?))
    }
    pub(super) fn set_bounded(&mut self, family: &str, json: &str) -> PyResult<()> {
        self.set_document(match family {
            "categorical" => DocumentChart::Categorical(parse(json)?),
            "boxplot" => DocumentChart::BoxPlot(parse(json)?),
            _ => return Err(invalid("unknown chart family")),
        })
    }
    pub(super) fn set_document(&mut self, chart: DocumentChart) -> PyResult<()> {
        if !matches!(
            self.data.chart.config().draw_style,
            renderer::config::DrawStyle::Precise
        ) {
            return Err(invalid(
                "bounded charts use materials, not Cartesian draw styles",
            ));
        }
        if !self.data.series.is_empty() || !self.data.columns.is_empty() {
            return Err(invalid("create a separate Figure for bounded charts"));
        }
        chart.validate(self.data.chart.config().chart_area.0)?;
        if let Some(document) = &mut self.data.document {
            if document.chart.family() != chart.family() {
                return Err(invalid("cannot change chart family"));
            }
            document.chart = chart;
        } else {
            self.data.document = Some(BoundedDocument {
                chart,
                renderer: None,
            });
        }
        self.data.revision += 1;
        Ok(())
    }
    fn document_renderer(&mut self) -> PyResult<&mut BoundedDocument> {
        let doc = self
            .data
            .document
            .as_mut()
            .ok_or_else(|| invalid("no bounded chart"))?;
        if doc.renderer.is_none() {
            doc.renderer = Some(DocumentRenderer::new(
                RendererDevice::new(
                    self.renderer.device().clone(),
                    self.renderer.queue().clone(),
                ),
                &doc.chart,
            )?);
        }
        Ok(doc)
    }
    pub(super) fn document_frame(&mut self) -> PyResult<DocumentFrame> {
        let r = self.data.chart.config().chart_area.0;
        let d = self.document_renderer()?;
        d.renderer
            .as_mut()
            .unwrap()
            .prepare(&d.chart, (r.width, r.height), 1.)
    }
    pub(super) fn render_document(&mut self, scale: f32) -> PyResult<renderer::RasterImage> {
        if !scale.is_finite() || !(0.5..=4.).contains(&scale) {
            return Err(invalid("bounded chart export scale must be 0.5..4"));
        }
        let r = self.data.chart.config().chart_area.0;
        let d = self.document_renderer()?;
        d.renderer
            .as_mut()
            .unwrap()
            .export(&d.chart, (r.width, r.height), scale)
    }
    pub(super) fn pick_document(&mut self, x: f32, y: f32) -> PyResult<String> {
        let frame = self.document_frame()?;
        let doc = self.data.document.as_mut().unwrap();
        let before = doc.chart.clone();
        doc.chart.select_at(&frame, [x, y], false);
        if before != doc.chart {
            self.data.revision += 1;
        }
        let value=match &doc.chart {
            DocumentChart::Radial(c)=>c.interaction.selected.and_then(|t|c.slice(t).map(|s|json!({"target":format!("slice_{}",t.index),"group":t.group,"index":t.index,"label":s.label,"value":s.value}))),
            DocumentChart::Categorical(c)=>c.selected.as_ref().map(|t|json!({"target":t,"value":c.value(t)})),
            DocumentChart::BoxPlot(c)=>c.selected.as_ref().map(|t|json!({"target":t,"summary":c.summary(t)})),
        };
        serde_json::to_string(&value).map_err(runtime)
    }
    pub(super) fn document_drag(
        &mut self,
        target: &str,
        dx: f32,
        dy: f32,
        handle: Option<&str>,
    ) -> PyResult<bool> {
        let frame = self.document_frame()?;
        let map = frame.decorations();
        let (id, _) = map
            .entries()
            .find(|(_, e)| e.id.element_id() == target)
            .ok_or_else(|| invalid("unknown decoration"))?;
        let mut chart = self.data.document.as_ref().unwrap().chart.clone();
        let result = if let Some(handle) = handle {
            let h = ALL_HANDLES
                .into_iter()
                .find(|h| format!("{h:?}") == handle)
                .ok_or_else(|| invalid("unknown resize handle"))?;
            map.resize_by(chart.decorations_mut(), id, h, dx, dy)
        } else {
            map.drag_by(chart.decorations_mut(), id, dx, dy)
        };
        if result != Some(renderer::layout::NudgeResult::Moved) {
            return Ok(false);
        }
        let rect = self.data.chart.config().chart_area.0;
        self.document_renderer()?
            .renderer
            .as_mut()
            .unwrap()
            .prepare(&chart, (rect.width, rect.height), 1.)?;
        self.set_document(chart)?;
        Ok(true)
    }
}
#[pyfunction]
pub(super) fn default_radial_json() -> PyResult<String> {
    serde_json::to_string(&RadialChart::default()).map_err(runtime)
}
#[pyfunction]
pub(super) fn default_bounded_json(family: &str) -> PyResult<String> {
    match family {
        "categorical" => serde_json::to_string(&CategoricalChart::default()).map_err(runtime),
        "boxplot" => serde_json::to_string(&BoxPlotChart::default()).map_err(runtime),
        _ => Err(invalid("unknown chart family")),
    }
}
