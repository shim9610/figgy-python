#![allow(deprecated)]
//! Bounded chart hosts delegate geometry, picking and drag policy to figgy-renderer.
use super::*;
use renderer::{DecorationLayout, boxplot::*, categorical::*, radar::*, radial::*};

#[derive(Clone, PartialEq)]
pub(super) enum DocumentChart {
    Radial(RadialChart),
    Categorical(CategoricalChart),
    BoxPlot(BoxPlotChart),
    Radar(RadarChart),
}
impl DocumentChart {
    pub fn value(&self) -> Value {
        match self {
            Self::Radial(c) => serde_json::to_value(c),
            Self::Categorical(c) => serde_json::to_value(c),
            Self::BoxPlot(c) => serde_json::to_value(c),
            Self::Radar(c) => serde_json::to_value(c),
        }
        .unwrap()
    }
    pub fn family(&self) -> &'static str {
        match self {
            Self::Radial(_) => "radial",
            Self::Categorical(_) => "categorical",
            Self::BoxPlot(_) => "boxplot",
            Self::Radar(_) => "radar",
        }
    }
    pub fn annotations(&self) -> &renderer::AnnotationLayer {
        match self {
            Self::Radial(c) => &c.annotations,
            Self::Categorical(c) => &c.annotations,
            Self::BoxPlot(c) => &c.annotations,
            Self::Radar(c) => &c.annotations,
        }
    }
    pub fn annotations_mut(&mut self) -> &mut renderer::AnnotationLayer {
        match self {
            Self::Radial(c) => &mut c.annotations,
            Self::Categorical(c) => &mut c.annotations,
            Self::BoxPlot(c) => &mut c.annotations,
            Self::Radar(c) => &mut c.annotations,
        }
    }
    pub fn active_layer(&self) -> renderer::LayerRef {
        match self {
            Self::Radial(c) => c.active_layer,
            Self::Categorical(c) => c.active_layer,
            Self::BoxPlot(c) => c.active_layer,
            Self::Radar(c) => c.active_layer,
        }
    }
    pub fn set_active_layer(&mut self, layer: renderer::LayerRef) {
        match self {
            Self::Radial(c) => {
                c.active_layer = layer;
            }
            Self::Categorical(c) => {
                c.active_layer = layer;
            }
            Self::BoxPlot(c) => {
                c.active_layer = layer;
            }
            Self::Radar(c) => {
                c.active_layer = layer;
            }
        }
    }
    pub fn background(&self) -> Color {
        match self {
            Self::Radial(c) => c.background,
            Self::Categorical(c) => c.background,
            Self::BoxPlot(c) => c.background,
            Self::Radar(c) => c.background,
        }
    }
    pub fn decorations(&self) -> &DecorationLayout {
        match self {
            Self::Radial(c) => &c.decorations,
            Self::Categorical(c) => &c.decorations,
            Self::BoxPlot(c) => &c.decorations,
            Self::Radar(c) => &c.decorations,
        }
    }
    pub fn decorations_mut(&mut self) -> &mut DecorationLayout {
        match self {
            Self::Radial(c) => &mut c.decorations,
            Self::Categorical(c) => &mut c.decorations,
            Self::BoxPlot(c) => &mut c.decorations,
            Self::Radar(c) => &mut c.decorations,
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
        let minimum = match self {
            Self::Radial(_) => (160, 160),
            Self::Radar(_) => (240, 240),
            _ => (240, 200),
        };
        if rect.width < minimum.0 || rect.height < minimum.1 {
            return Err(invalid(format!(
                "{} canvas must be at least {}x{} pixels",
                self.family(),
                minimum.0,
                minimum.1
            )));
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
            Self::Radar(c) => {
                validate_model_numbers(c, "radar")?;
                c.validate().map_err(invalid)
            }
        }
    }
    pub fn selected_json(&self) -> serde_json::Value {
        match self {
            Self::Radial(c) => json!(c.interaction.selected),
            Self::Categorical(c) => json!(c.selected),
            Self::BoxPlot(c) => json!(c.selected),
            Self::Radar(c) => json!(c.selected),
        }
    }
    pub fn clear_selection(&mut self) {
        self.decorations_mut().selected = None;
        match self {
            Self::Radial(c) => c.interaction.selected = None,
            Self::Categorical(c) => c.selected = None,
            Self::BoxPlot(c) => c.selected = None,
            Self::Radar(c) => c.selected = None,
        }
    }
    pub fn select_at(&mut self, frame: &DocumentFrame, point: [f32; 2], toggle: bool) {
        if let (Self::Radial(c), DocumentFrame::Radial(f)) = (self, frame) {
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
    }
    pub fn hover(&mut self, frame: &DocumentFrame, point: Option<[f32; 2]>, dt: f32) -> bool {
        if let (Self::Radial(c), DocumentFrame::Radial(f)) = (self, frame) {
            let hit = point.and_then(|p| {
                f.hit_test(p).or_else(|| {
                    f.hit_test_at_rest(p)
                        .filter(|t| Some(*t) == c.interaction.hovered)
                })
            });
            c.interaction.animate_hover(hit, dt, 0.16)
        } else {
            false
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
            Self::Radar(c) => {
                let selected_series = c
                    .selected
                    .as_ref()
                    .filter(|target| target.category_id.is_some())
                    .and_then(|target| c.series.iter().find(|s| s.id == target.series_id));
                let items = if let Some(series) = selected_series {
                    c.categories
                        .iter()
                        .zip(&series.values)
                        .filter(|(_, value)| value.is_finite())
                        .map(|(category, _)| RadarTarget::vertex(&series.id, &category.id))
                        .collect()
                } else {
                    c.series
                        .iter()
                        .map(|series| RadarTarget::series(&series.id))
                        .collect()
                };
                next(items, &mut c.selected, backwards);
            }
            Self::Radial(c) => {
                let items = (0..c.group_count())
                    .flat_map(|group| {
                        (0..c.group_len(group)).map(move |index| RadialTarget { group, index })
                    })
                    .filter(|target| c.slice(*target).is_some_and(|node| node.value > 0.))
                    .collect();
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
    pub(super) renderer: Option<DocumentRenderer>,
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
}
pub(super) enum DocumentFrame {
    Radial(Arc<crate::radial_compat::Frame>),
}
impl DocumentRenderer {
    pub fn new(gpu: RendererDevice, chart: &DocumentChart) -> PyResult<Self> {
        match chart {
            DocumentChart::Radial(_) => Ok(Self::Radial(
                RadialRenderer::try_new(gpu, wgpu::TextureFormat::Rgba8Unorm).map_err(runtime)?,
            )),
            _ => Err(invalid(
                "legacy charts must migrate to column-backed series",
            )),
        }
    }
    pub fn prepare(
        &mut self,
        chart: &DocumentChart,
        size: (u32, u32),
        scale: f32,
    ) -> PyResult<DocumentFrame> {
        let (Self::Radial(r), DocumentChart::Radial(c)) = (self, chart) else {
            return Err(invalid("legacy chart requires migration"));
        };
        let inner = r.prepare(c, size, scale).map_err(runtime)?;
        Ok(DocumentFrame::Radial(Arc::new(
            crate::radial_compat::Frame::new(inner, c.clone()),
        )))
    }
    pub fn prepare_annotations(
        &mut self,
        chart: &DocumentChart,
        size: (u32, u32),
        scale: f32,
    ) -> PyResult<Arc<renderer::annotation::BoundedAnnotationFrame>> {
        let (Self::Radial(r), DocumentChart::Radial(c)) = (self, chart) else {
            return Err(invalid("legacy chart requires migration"));
        };
        r.prepare_annotations(c, size, scale).map_err(runtime)
    }
    pub fn export(
        &mut self,
        chart: &DocumentChart,
        size: (u32, u32),
        scale: f32,
    ) -> PyResult<renderer::RasterImage> {
        let (Self::Radial(r), DocumentChart::Radial(c)) = (self, chart) else {
            return Err(invalid("legacy chart requires migration"));
        };
        r.export_rgba_blocking(c, size, renderer::ExportOptions::document(scale))
            .map_err(runtime)
    }
    pub fn gpu_bytes(&self) -> u64 {
        let Self::Radial(r) = self;
        r.gpu_memory_usage().total_bytes()
    }
    pub fn end_frame(&self) {
        let Self::Radial(r) = self;
        r.end_frame();
    }
}
impl DocumentFrame {
    pub fn annotation_space(&self) -> renderer::annotation::PixelSpace {
        let Self::Radial(f) = self;
        f.annotation_space()
    }
    pub fn decorations(&self) -> &crate::radial_compat::Decorations {
        let Self::Radial(f) = self;
        f.decorations()
    }
    pub fn draw(&self, pass: &mut wgpu::RenderPass<'_>) {
        let Self::Radial(f) = self;
        f.draw(pass);
    }
    pub fn has_data(&self, p: [f32; 2]) -> bool {
        let Self::Radial(f) = self;
        f.hit_test(p).is_some() || f.hit_test_at_rest(p).is_some()
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
            "radar" => DocumentChart::Radar(parse(json)?),
            _ => return Err(invalid("unknown chart family")),
        })
    }
    pub(super) fn set_document(&mut self, mut chart: DocumentChart) -> PyResult<()> {
        if let DocumentChart::Radial(c) = &mut chart {
            c.normalize_labels();
        }
        if self
            .data
            .document
            .as_ref()
            .is_some_and(|d| d.chart.family() == chart.family())
        {
            let mut state = serde_json::to_value(self.snapshot()).map_err(runtime)?;
            state[chart.family()] = chart.value();
            return self.apply_settings(&state.to_string());
        }
        if !matches!(
            self.data.chart.config().draw_style,
            renderer::config::DrawStyle::Precise
        ) {
            return Err(invalid(
                "bounded charts use materials, not Cartesian draw styles",
            ));
        }
        if !self.data.series.is_empty()
            || !self.data.columns.is_empty()
            || !self.data.chart.config().subplots.is_empty()
            || !self.data.chart.config().overlays.is_empty()
            || self.data.chart.config().polar().is_some()
        {
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
        self.data.history = Default::default();
        Ok(())
    }
    pub(super) fn document_renderer(&mut self) -> PyResult<&mut BoundedDocument> {
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
                )
                .map_err(runtime)?,
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
    pub(super) fn document_annotations(
        &mut self,
    ) -> PyResult<Arc<renderer::annotation::BoundedAnnotationFrame>> {
        let r = self.data.chart.config().chart_area.0;
        let d = self.document_renderer()?;
        d.renderer
            .as_mut()
            .unwrap()
            .prepare_annotations(&d.chart, (r.width, r.height), 1.)
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
            DocumentChart::Radar(c)=>c.selected.as_ref().map(|t|json!({"target":t,"value":c.value(t)})),
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
        if let Some(index) = target
            .strip_prefix("annotation_")
            .and_then(|v| v.parse::<usize>().ok())
        {
            let frame = self.document_annotations()?;
            let map = frame.annotations();
            let id = map
                .find(index)
                .ok_or_else(|| invalid("annotation is not visible"))?;
            let mut chart = self.data.document.as_ref().unwrap().chart.clone();
            let result = if let Some(handle) = handle {
                let handle = ALL_HANDLES
                    .into_iter()
                    .find(|h| format!("{h:?}") == handle)
                    .ok_or_else(|| invalid("unknown resize handle"))?;
                map.resize_by(chart.annotations_mut(), id, handle, dx, dy)
            } else {
                map.drag_by(chart.annotations_mut(), id, dx, dy)
            };
            if result == Some(renderer::layout::NudgeResult::Moved) {
                self.set_document(chart)?;
                return Ok(true);
            }
            return Ok(false);
        }
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
        "radar" => serde_json::to_string(&RadarChart::default()).map_err(runtime),
        _ => Err(invalid("unknown chart family")),
    }
}
