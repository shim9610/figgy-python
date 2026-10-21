//! Python owns data input and UI; renderer models own accepted chart settings.
use numpy::PyReadonlyArray1;
use pyo3::sync::MutexExt;
use pyo3::{
    exceptions::{PyMemoryError, PyRuntimeError, PyValueError},
    prelude::*,
    types::PyBytes,
};
use renderer::{
    Chart, ChartId, Color, Config, CpuTextMeasure, GpuPickRequest, HitId, HitMap, Renderer,
    RendererDevice, Selectable, SeriesConfig,
    data::{ColumnPairWriter, ColumnUploadStats, HiLoColumnSource, split_f64_to_f32_pair},
    data_render::{create_instance, request_adapter},
    default, encode_png,
    layout::{ChartArea, Rect, Side},
    resize::{ALL_HANDLES, ResizeHandle},
    select::{
        AxisElement, AxisLabelElement, AxisTitleElement, ChartTitleElement, ColorBarAxisElement,
        ColorBarElement, ColorBarLabelElement, ColorBarTitleElement, DataAreaElement,
        LegendElement,
    },
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
};

fn runtime(e: impl std::fmt::Display) -> PyErr {
    PyRuntimeError::new_err(e.to_string())
}
fn invalid(e: impl std::fmt::Display) -> PyErr {
    PyValueError::new_err(e.to_string())
}

fn parse<T: serde::de::DeserializeOwned>(json: &str) -> PyResult<T> {
    // Internally tagged serde enums buffer their fields before deserialization;
    // serde_ignored cannot observe unknown draw-style parameters inside them.
    if json.contains("\"draw_style\"") {
        fn styles(value: &Value) -> PyResult<()> {
            if let Some(fields) = value.as_object() {
                if let Some(style) = fields.get("draw_style") {
                    let parsed: renderer::config::DrawStyle =
                        serde_json::from_value(style.clone()).map_err(invalid)?;
                    if let Some(fields) = style.as_object() {
                        for key in fields.keys() {
                            if key != "mode"
                                && !draw_style_specs(&parsed).iter().any(|p| p.key == key)
                            {
                                return Err(invalid(format!(
                                    "unknown draw-style parameter: {key}"
                                )));
                            }
                        }
                    }
                }
                if let Some(config) = fields.get("config") {
                    styles(config)?;
                }
                if let Some(items) = fields.get("subplots").and_then(Value::as_array) {
                    for subplot in items {
                        if let Some(config) = subplot.get("config") {
                            styles(config)?;
                        }
                    }
                }
            }
            Ok(())
        }
        styles(&serde_json::from_str::<Value>(json).map_err(invalid)?)?;
    }
    let mut de = serde_json::Deserializer::from_str(json);
    let mut unknown = Vec::new();
    let value = serde_ignored::deserialize(&mut de, |path| unknown.push(path.to_string()))
        .map_err(invalid)?;
    de.end().map_err(invalid)?;
    if !unknown.is_empty() {
        return Err(invalid(format!(
            "unknown settings fields: {}",
            unknown.join(", ")
        )));
    }
    Ok(value)
}

/// Renderer version stamped into Settings documents. Previous compatible
/// documents are accepted explicitly by supported_settings_version.
/// It names the `figgy-renderer` pin in Cargo.toml; update both together.
const RENDERER_VERSION: &str = "0.18.1";

fn supported_settings_version(schema: u32, renderer: &str) -> bool {
    matches!(schema, 1 | 2) && matches!(renderer, "0.17.0" | "0.18.0" | RENDERER_VERSION)
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Settings {
    schema_version: u32,
    renderer_version: String,
    config: Config,
    series: Vec<SeriesConfig>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    radial: Option<renderer::radial::RadialChart>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    background: Option<Color>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    categorical: Option<renderer::categorical::CategoricalChart>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    boxplot: Option<renderer::boxplot::BoxPlotChart>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    radar: Option<renderer::radar::RadarChart>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    identity: Option<Value>,
}

impl Settings {
    fn document(&self) -> PyResult<Option<bounded::DocumentChart>> {
        validate_identity(self.identity.as_ref(), &self.config, self.schema_version)?;
        let docs = [
            self.radial.clone().map(bounded::DocumentChart::Radial),
            self.radar.clone().map(bounded::DocumentChart::Radar),
            self.categorical
                .clone()
                .map(bounded::DocumentChart::Categorical),
            self.boxplot.clone().map(bounded::DocumentChart::BoxPlot),
        ];
        if docs.iter().filter(|v| v.is_some()).count() > 1 {
            return Err(invalid("settings must contain one chart family"));
        }
        Ok(docs.into_iter().flatten().next())
    }
}

trait Number: Copy {
    fn f64(self) -> f64;
}
impl Number for f64 {
    fn f64(self) -> f64 {
        self
    }
}
impl Number for f32 {
    fn f64(self) -> f64 {
        self as f64
    }
}

/// Reads borrowed contiguous NumPy storage directly into renderer staging.
/// No Python list, temporary Vec, or retained CPU copy of source data.
struct BorrowedColumn<'a, T> {
    values: &'a [T],
    min: f64,
    max: f64,
}
impl<T: Number> HiLoColumnSource for BorrowedColumn<'_, T> {
    fn len(&self) -> usize {
        self.values.len()
    }
    fn min(&self) -> f64 {
        self.min
    }
    fn max(&self) -> f64 {
        self.max
    }
    fn write_f32_pair_le_into(&self, dst: &mut [u8]) {
        for (chunk, value) in dst.chunks_exact_mut(8).zip(self.values) {
            let (hi, lo) = split_f64_to_f32_pair(value.f64());
            chunk[..4].copy_from_slice(&hi.to_le_bytes());
            chunk[4..].copy_from_slice(&lo.to_le_bytes());
        }
    }
    fn write_f32_pair_le_into_with_stats(
        &self,
        mut dst: ColumnPairWriter<'_>,
    ) -> ColumnUploadStats {
        let mut min_positive: Option<f64> = None;
        for (i, value) in self.values.iter().enumerate() {
            let (hi, lo) = split_f64_to_f32_pair(value.f64());
            dst.write_pair(i, hi, lo);
            let encoded = hi as f64 + lo as f64;
            if (hi + lo).is_finite() && encoded.is_finite() && encoded > 0.0 {
                min_positive = Some(min_positive.map_or(encoded, |v| v.min(encoded)));
            }
        }
        ColumnUploadStats { min_positive }
    }
}

struct FigureCore {
    identity: Option<Value>,
    background: Option<Color>,
    code_dpi: f64,
    default_config: Config,
    gpu: Arc<gpu::GpuContext>,
    figure_id: u64,
    chart: Chart,
    chart_id: ChartId,
    series: Vec<SeriesConfig>,
    hitmap: HitMap,
    elements: Vec<(String, HitId)>,
    columns: HashMap<String, (usize, f64, f64)>,
    revision: u64,
    history: edit_history::History,
    uploads: u64,
    readbacks: u64,
    png_encodes: u64,
    selection_value_readbacks: u64,
    preparation: Option<Value>,
    target: Option<RenderTarget>,
    document: Option<bounded::BoundedDocument>,
    /// Tick-guard warnings of the last rebuilt axis raster, and the messages
    /// not yet handed to Python. The renderer re-derives them only when the
    /// raster is rebuilt; a changed list is reported once.
    render_warnings: Vec<renderer::RenderWarning>,
    pending_warnings: Vec<String>,
    /// Document revision the warnings above were derived for.
    warnings_revision: Option<u64>,
}

/// An operation holds the document lock, then the shared renderer lock.
/// Both guards outlive GPU recording, readback and error scopes.
struct FigureAccess<'a> {
    context: &'a gpu::GpuContext,
    renderer: &'a mut Renderer,
    data: &'a mut FigureCore,
}
impl<'a> FigureAccess<'a> {
    fn new(
        context: &'a gpu::GpuContext,
        data: &'a mut FigureCore,
        renderer: &'a mut Renderer,
    ) -> Self {
        Self {
            context,
            renderer,
            data,
        }
    }
    fn gpu_series(&self, series: &[SeriesConfig]) -> Vec<SeriesConfig> {
        gpu::series(self.data.figure_id, series)
    }
}
impl Drop for FigureCore {
    fn drop(&mut self) {
        // Do not wait for a GPU lock from Python GC/finalization. The next
        // renderer operation drains this small ownership record before use.
        self.gpu.retire(
            self.chart_id,
            self.columns
                .keys()
                .map(|id| gpu::column_id(self.figure_id, id))
                .collect(),
        );
    }
}

/// Display-sized target and rasterized axes survive redraws. This is a host
/// render target; chart geometry and GPU pipelines still belong to renderer.
struct RenderTarget {
    width: u32,
    height: u32,
    row_bytes: u32,
    revision: u64,
    texture: wgpu::Texture,
    view: renderer::ChartView,
    readback: wgpu::Buffer,
    styles: Vec<renderer::ChartStyle>,
    scale: f32,
}

impl FigureAccess<'_> {
    fn render(&mut self, scale: f32) -> PyResult<renderer::RasterImage> {
        self.data.readbacks += 1;
        let device = Arc::clone(self.renderer.device());
        let oom = device.push_error_scope(wgpu::ErrorFilter::OutOfMemory);
        let validation = device.push_error_scope(wgpu::ErrorFilter::Validation);
        let rendered = self.render_inner(scale);
        self.renderer.wait_idle();
        let validation = pollster::block_on(validation.pop());
        let oom = pollster::block_on(oom.pop());
        if let Some(error) = oom {
            self.data.target = None;
            return Err(PyMemoryError::new_err(format!(
                "render allocation failed on {}: {error}",
                self.context.adapter_info["name"]
            )));
        }
        if let Some(error) = validation {
            self.data.target = None;
            return Err(runtime(format!(
                "GPU render failed on {}: {error}",
                self.context.adapter_info["name"]
            )));
        }
        if rendered.is_err() {
            self.data.target = None;
        }
        rendered
    }
    /// Record the tick warnings of the current revision's raster; a changed
    /// list is queued for Python once.
    fn note_render_warnings(&mut self, warnings: &[renderer::RenderWarning]) {
        self.data.warnings_revision = Some(self.data.revision);
        if warnings != self.data.render_warnings.as_slice() {
            self.data.pending_warnings = warnings.iter().map(ToString::to_string).collect();
            self.data.render_warnings = warnings.to_vec();
        }
    }
    fn render_inner(&mut self, scale: f32) -> PyResult<renderer::RasterImage> {
        if self.data.document.is_some() {
            return self.render_document(scale);
        }
        self.renderer
            .ensure_target_format(wgpu::TextureFormat::Rgba8Unorm)
            .map_err(runtime)?;
        let styled = !matches!(
            self.data.chart.config().draw_style,
            renderer::config::DrawStyle::Precise
        ) || self
            .data
            .chart
            .config()
            .subplots
            .iter()
            .any(|p| !matches!(p.config.draw_style, renderer::config::DrawStyle::Precise));
        if !styled
            && (!self.data.chart.config().subplots.is_empty()
                || !self.data.chart.config().overlays.is_empty()
                || scale != 1.0)
        {
            // Exports at another scale rasterize without a ChartView, so derive
            // this revision's tick warnings from a view of the document itself.
            if self.data.warnings_revision != Some(self.data.revision) {
                let chart = Chart::new(gpu::config(self.data.figure_id, self.data.chart.config()));
                let view = self
                    .renderer
                    .create_chart_view(&chart, chart.config().chart_area.0)
                    .map_err(runtime)?;
                self.note_render_warnings(view.render_warnings());
            }
            return pollster::block_on(self.renderer.export_document_rgba_with_clear_async(
                &Chart::new(gpu::config(self.data.figure_id, self.data.chart.config())),
                &gpu::series(self.data.figure_id, &self.data.series),
                scale,
                self.data.background.unwrap_or(Color::WHITE),
            ))
            .map_err(runtime);
        }
        let mut config = gpu::config(self.data.figure_id, self.data.chart.config());
        if scale != 1.0 {
            let original = config.chart_area.0;
            config = config.scaled(scale);
            config.chart_area.0.width = (original.width as f32 * scale).round().max(1.) as u32;
            config.chart_area.0.height = (original.height as f32 * scale).round().max(1.) as u32;
        }
        let original = self.data.chart.config().document_area();
        let rect = Rect {
            x: 0,
            y: 0,
            width: (original.width as f32 * scale).round().max(1.) as u32,
            height: (original.height as f32 * scale).round().max(1.) as u32,
        };
        config = renderer::place_document(&config, 1., rect);
        let chart = Chart::new(config);
        if rect.width > self.renderer.device().limits().max_texture_dimension_2d
            || rect.height > self.renderer.device().limits().max_texture_dimension_2d
        {
            return Err(invalid("export size exceeds the GPU texture limit"));
        }
        if self
            .data
            .target
            .as_ref()
            .is_none_or(|t| t.width != rect.width || t.height != rect.height || t.scale != scale)
        {
            let device = self.renderer.device();
            let row_bytes = (rect.width * 4).div_ceil(wgpu::COPY_BYTES_PER_ROW_ALIGNMENT)
                * wgpu::COPY_BYTES_PER_ROW_ALIGNMENT;
            let texture = device.create_texture(&wgpu::TextureDescriptor {
                label: Some("figgy Python persistent target"),
                size: wgpu::Extent3d {
                    width: rect.width,
                    height: rect.height,
                    depth_or_array_layers: 1,
                },
                mip_level_count: 1,
                sample_count: 1,
                dimension: wgpu::TextureDimension::D2,
                format: wgpu::TextureFormat::Rgba8Unorm,
                usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC,
                view_formats: &[],
            });
            let readback = device.create_buffer(&wgpu::BufferDescriptor {
                label: Some("figgy Python persistent readback"),
                size: row_bytes as u64 * rect.height as u64,
                usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
                mapped_at_creation: false,
            });
            let view = self
                .renderer
                .create_chart_view(&chart, chart.config().chart_area.0)
                .map_err(runtime)?;
            self.data.target = Some(RenderTarget {
                width: rect.width,
                height: rect.height,
                row_bytes,
                revision: self.data.revision,
                texture,
                view,
                readback,
                styles: Vec::new(),
                scale,
            });
        }
        let target = self.data.target.as_mut().unwrap();
        let specs = gpu::series(self.data.figure_id, &self.data.series);
        if styled && (target.styles.is_empty() || target.revision != self.data.revision) {
            target.styles = specs
                .iter()
                .zip(&self.data.series)
                .map(|(gpu_spec, local)| {
                    let mut style_spec = gpu_spec.clone();
                    // Keep renderer scratch-cache IDs namespaced, but stable user
                    // IDs own sketch/star patterns across independent Figures.
                    style_spec.series_id = local.series_id.clone();
                    self.renderer
                        .create_style_for_series_scaled(&style_spec, scale)
                        .map_err(runtime)
                })
                .collect::<PyResult<Vec<_>>>()?;
        }
        if target.revision != self.data.revision {
            self.renderer
                .refresh_axis(&mut target.view, &chart, chart.config().chart_area.0)
                .map_err(runtime)?;
            target.revision = self.data.revision;
        }
        // Same bookkeeping as note_render_warnings, on disjoint fields while
        // `target` is still borrowed.
        self.data.warnings_revision = Some(self.data.revision);
        if target.view.render_warnings() != self.data.render_warnings.as_slice() {
            self.data.render_warnings = target.view.render_warnings().to_vec();
            self.data.pending_warnings = self
                .data
                .render_warnings
                .iter()
                .map(ToString::to_string)
                .collect();
        }
        let drawn = specs
            .iter()
            .zip(&target.styles)
            .map(|(config, style)| renderer::Series { config, style })
            .collect::<Vec<_>>();
        let prepared = if styled {
            self.renderer
                .prepare(&[renderer::ChartDrawItem {
                    view: &target.view,
                    chart_config: chart.config(),
                    series: &drawn,
                }])
                .map_err(runtime)?
        } else {
            self.renderer
                .prepare_registered(&[renderer::RegisteredChartDrawItem {
                    chart_id: self.data.chart_id,
                    view: &target.view,
                }])
                .map_err(runtime)?
        };
        let texture_view = target.texture.create_view(&Default::default());
        let mut encoder = self
            .renderer
            .device()
            .create_command_encoder(&Default::default());
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &texture_view,
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(background_wgpu(self.data.background)),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                ..Default::default()
            });
            self.renderer
                .paint_prepared(&mut pass, (target.width, target.height), &prepared)
                .map_err(runtime)?;
        }
        encoder.copy_texture_to_buffer(
            wgpu::TexelCopyTextureInfo {
                texture: &target.texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            wgpu::TexelCopyBufferInfo {
                buffer: &target.readback,
                layout: wgpu::TexelCopyBufferLayout {
                    offset: 0,
                    bytes_per_row: Some(target.row_bytes),
                    rows_per_image: Some(target.height),
                },
            },
            wgpu::Extent3d {
                width: target.width,
                height: target.height,
                depth_or_array_layers: 1,
            },
        );
        self.renderer.queue().submit([encoder.finish()]);
        let (tx, rx) = std::sync::mpsc::channel();
        let slice = target.readback.slice(..);
        slice.map_async(wgpu::MapMode::Read, move |result| {
            let _ = tx.send(result);
        });
        self.renderer.wait_idle();
        rx.recv().map_err(runtime)?.map_err(runtime)?;
        let mapped = slice.get_mapped_range().map_err(runtime)?;
        let mut rgba = Vec::with_capacity((target.width * target.height * 4) as usize);
        for row in mapped
            .chunks(target.row_bytes as usize)
            .take(target.height as usize)
        {
            rgba.extend_from_slice(&row[..target.width as usize * 4]);
        }
        drop(mapped);
        target.readback.unmap();
        drop(prepared);
        self.renderer.end_gpu_frame();
        Ok(renderer::RasterImage {
            width: target.width,
            height: target.height,
            rgba,
        })
    }
    fn upload<T: Number>(&mut self, id: &str, values: &[T]) -> PyResult<()> {
        if self.data.columns.contains_key(id) {
            return Err(invalid(format!("column already exists: {id}")));
        }
        if values.is_empty() {
            return Err(invalid("data must contain at least one value"));
        }
        let (mut min, mut max) = (f64::INFINITY, f64::NEG_INFINITY);
        for (index, v) in values.iter().enumerate() {
            let v = v.f64();
            if v.is_finite() {
                if !(v as f32).is_finite() {
                    return Err(invalid(format!(
                        "column {id:?} value at index {index} exceeds the f32 hi/lo representation range"
                    )));
                }
                min = min.min(v);
                max = max.max(v);
            }
        }
        if !min.is_finite() {
            return Err(invalid("data has no finite values"));
        }
        let source = BorrowedColumn { values, min, max };
        if let Err(error) = self
            .renderer
            .add_hilo_column(gpu::column_id(self.data.figure_id, id), &source)
        {
            let message = format!(
                "upload failed: column={id:?}, values={}, requested_gpu_bytes={}, pool_used_bytes={}, pool_capacity_bytes={}, adapter_column_pool_limit_bytes={}, adapter={}; {error}",
                values.len(),
                (values.len() as u64).saturating_mul(8),
                self.renderer.pool().used_bytes(),
                self.renderer.pool().capacity(),
                self.context.adapter_info["maximum_column_pool_bytes"],
                self.context.adapter_info["name"]
            );
            return Err(match error {
                renderer::FiggyError::Pool(
                    renderer::AllocError::OutOfSpace { .. }
                    | renderer::AllocError::ResourceLimit { .. }
                    | renderer::AllocError::BudgetExceeded { .. }
                    | renderer::AllocError::AllocationFailed { .. },
                )
                | renderer::FiggyError::GpuResourceAllocationFailed { .. }
                | renderer::FiggyError::GpuResourceLimit { .. } => PyMemoryError::new_err(message),
                _ => runtime(message),
            });
        }
        self.data
            .columns
            .insert(id.to_owned(), (values.len(), min, max));
        self.data.uploads += 1;
        Ok(())
    }
    fn element(&self, target: &str) -> PyResult<HitId> {
        self.active_element(target)
            .ok_or_else(|| invalid(format!("unknown decoration: {target}")))
    }
    fn commit_config(&mut self, config: Config) -> PyResult<()> {
        let mut state = self.snapshot();
        state.config = config;
        self.apply_settings(&serde_json::to_string(&state).map_err(runtime)?)
    }
    fn snapshot(&self) -> Settings {
        Settings {
            schema_version: if self.data.identity.is_some() { 2 } else { 1 },
            identity: self.data.identity.clone(),
            radar: self.data.document.as_ref().and_then(|r| {
                if let bounded::DocumentChart::Radar(c) = &r.chart {
                    Some(c.clone())
                } else {
                    None
                }
            }),
            renderer_version: RENDERER_VERSION.into(),
            config: self.data.chart.config().clone(),
            series: self.data.series.clone(),
            radial: self
                .data
                .document
                .as_ref()
                .and_then(|r| r.chart.radial().cloned()),
            categorical: self.data.document.as_ref().and_then(|r| {
                if let bounded::DocumentChart::Categorical(c) = &r.chart {
                    Some(c.clone())
                } else {
                    None
                }
            }),
            boxplot: self.data.document.as_ref().and_then(|r| {
                if let bounded::DocumentChart::BoxPlot(c) = &r.chart {
                    Some(c.clone())
                } else {
                    None
                }
            }),
            background: self.data.background,
        }
    }
}

/// Positive range metadata only: source samples remain untouched, including noise.
fn positive_data_bounds(
    axis: &str,
    series: &[SeriesConfig],
    mut extent: renderer::chart::FitExtent,
    mut column: impl FnMut(&str) -> PyResult<renderer::chart::FitExtent>,
) -> PyResult<(f64, f64)> {
    if !matches!(axis, "x" | "y" | "z") {
        return Err(invalid("log bounds axis must be x, y or z"));
    }
    for s in series {
        match axis {
            "x" => extent.union(&column(&s.x_column)?),
            "y" => extent.union(&column(&s.y_column)?),
            "z" => {
                let value = serde_json::to_value(&s.render_type).map_err(invalid)?;
                let style = value.as_object().unwrap().values().next().unwrap();
                for matrix in [&style["matrix"], &style["style"]["color_map"]["Grid"]] {
                    if let Some(columns) = matrix["columns"].as_array() {
                        for id in columns {
                            extent.union(&column(id.as_str().unwrap())?);
                        }
                    }
                }
                for id in [
                    &style["scatter"]["point_color_map"]["column"],
                    &style["style"]["color_map"]["Column"],
                ] {
                    if let Some(id) = id.as_str() {
                        extent.union(&column(id)?);
                    }
                }
            }
            _ => return Err(invalid("log bounds axis must be x, y or z")),
        }
        if let renderer::DataRenderType::Histogram { bar } = &s.render_type {
            let dimension = match bar.orientation {
                renderer::data_config::BarOrientation::Vertical => "y",
                renderer::data_config::BarOrientation::Horizontal => "x",
            };
            if axis == dimension {
                extent.union(&renderer::chart::FitExtent {
                    min: bar.baseline,
                    max: bar.baseline,
                    min_positive: (bar.baseline > 0.).then_some(bar.baseline),
                });
            }
        }
    }
    let Some(min) = extent.min_positive.filter(|v| *v > 0.) else {
        // A valid empty logarithmic view, not a fabricated data point.
        return Ok((1., 10.));
    };
    if extent.max > min {
        Ok((min, extent.max))
    } else {
        let lower = min / 10.;
        let upper = min * 10.;
        Ok((
            if lower > 0. { lower } else { min },
            if upper.is_finite() { upper } else { min },
        ))
    }
}

fn validate_config(config: &Config) -> PyResult<()> {
    validate_model_numbers(config, "config")?;
    let rect = config.chart_area.0;
    if (config.subplots.is_empty() && (rect.x != 0 || rect.y != 0))
        || rect.width == 0
        || rect.height == 0
        || rect.width > 8192
        || rect.height > 8192
    {
        return Err(invalid(
            "chart canvas must begin at (0, 0) and be 1..8192 pixels",
        ));
    }
    let document = config.document_area();
    if document.width > 8192 || document.height > 8192 {
        return Err(invalid(
            "complete document exceeds the 8192 pixel canvas limit",
        ));
    }
    for axis in [
        &config.bottom_x,
        &config.top_x,
        &config.left_y,
        &config.right_y,
    ]
    .into_iter()
    .chain(config.colorbar.as_ref().map(|bar| &bar.axis))
    {
        if !axis.min.is_finite()
            || !axis.max.is_finite()
            || axis.min >= axis.max
            || !axis.major_spacing.is_finite()
            || axis.major_spacing <= 0.0
        {
            return Err(invalid(
                "axes require finite increasing bounds and positive tick spacing",
            ));
        }
        let (min, max) = match axis.scale {
            renderer::config::AxisScale::Logarithmic => {
                if axis.min <= 0.0 {
                    return Err(invalid("logarithmic axes require positive bounds"));
                }
                (axis.min.log10(), axis.max.log10())
            }
            _ => (axis.min, axis.max),
        };
        if !(min as f32).is_finite()
            || !(max as f32).is_finite()
            || !((max - min) as f32).is_finite()
        {
            return Err(invalid(
                "axis bounds/span exceed the f32 hi/lo representation range",
            ));
        }
    }
    if config.chart_title.top_margin < 0. {
        return Err(invalid(
            "config.chart_title.top_margin must be nonnegative; use offset_y to move the title",
        ));
    }
    config
        .validate()
        .map_err(|e| invalid(format!("invalid layout: {e:?}")))?;
    Ok(())
}

fn validate_background(color: Option<Color>) -> PyResult<()> {
    if let Some(c) = color {
        if [c.r, c.g, c.b, c.a]
            .iter()
            .any(|v| !v.is_finite() || !(0.0..=1.0).contains(v))
        {
            return Err(invalid("background must be finite RGBA in 0..1"));
        }
    }
    Ok(())
}

fn background_wgpu(color: Option<Color>) -> wgpu::Color {
    let c = color.unwrap_or(Color::WHITE);
    wgpu::Color {
        r: c.r as f64,
        g: c.g as f64,
        b: c.b as f64,
        a: c.a as f64,
    }
}

fn draw_style_specs(
    style: &renderer::config::DrawStyle,
) -> &'static [renderer::config::StyleParamSpec] {
    use renderer::config::*;
    match style {
        DrawStyle::Precise => &[],
        DrawStyle::Sketch(_) => SketchOptions::PARAM_SPECS,
        DrawStyle::Milkyway(_) => MilkywayOptions::PARAM_SPECS,
        DrawStyle::Constellation(_) => ConstellationOptions::PARAM_SPECS,
    }
}

fn validate_draw_style(config: &Config, series: &[SeriesConfig]) -> PyResult<()> {
    if !config.subplots.is_empty() {
        let mut base = config.clone();
        base.subplots.clear();
        let owned: Vec<_> = series
            .iter()
            .filter(|s| !config.subplots.iter().any(|p| p.owns_series(&s.series_id)))
            .cloned()
            .collect();
        validate_draw_style(&base, &owned)?;
        for panel in &config.subplots {
            let owned: Vec<_> = series
                .iter()
                .filter(|s| panel.owns_series(&s.series_id))
                .cloned()
                .collect();
            validate_draw_style(&panel.config, &owned)?;
        }
        return Ok(());
    }
    use renderer::{DataRenderType, config::DrawStyle};
    // A stylized style silently skips series it has no entry point for; the
    // renderer's own predicate says which, so none reaches it unrejected.
    if !series
        .iter()
        .all(|s| renderer::draw_style_supports(&config.draw_style, &s.render_type))
    {
        return Err(invalid(match config.draw_style {
            DrawStyle::Sketch(_) => {
                "Sketch draws line, scatter and errorbar series; bars, heatmaps and contours are not supported"
            }
            DrawStyle::Milkyway(_) => {
                "Milkyway supports line-only series; scatter and marker lines are disabled"
            }
            _ => "Constellation requires line series with markers (plot(..., marker='o'))",
        }));
    }
    // Product policy on top of the renderer: the binding offers Milkyway for
    // plain lines only (the renderer also draws its scatter and errorbars).
    if matches!(config.draw_style, DrawStyle::Milkyway(_))
        && series
            .iter()
            .any(|s| !matches!(s.render_type, DataRenderType::Line { .. }))
    {
        return Err(invalid(
            "Milkyway supports line-only series; scatter and marker lines are disabled",
        ));
    }
    let values = serde_json::to_value(config.draw_style).map_err(invalid)?;
    for spec in draw_style_specs(&config.draw_style) {
        let value = values[spec.key]
            .as_f64()
            .ok_or_else(|| invalid("invalid draw-style parameter"))?;
        let maximum = if spec.integer {
            u32::MAX as f64
        } else {
            spec.max
        };
        if value < spec.min || value > maximum {
            return Err(invalid(format!(
                "draw_style.{} must be in {}..{}",
                spec.key, spec.min, maximum
            )));
        }
    }
    Ok(())
}

#[pyfunction]
fn draw_style_specs_json() -> PyResult<String> {
    use renderer::config::*;
    serde_json::to_string(&json!({
        "precise": [], "sketch": SketchOptions::PARAM_SPECS,
        "milkyway": MilkywayOptions::PARAM_SPECS,
        "constellation": ConstellationOptions::PARAM_SPECS,
    }))
    .map_err(runtime)
}

// serde accepts a finite f64 JSON number that overflows a renderer f32 field.
// Serialization then turns that infinity into null. Reject it before GPU use,
// including optional floats whose null would otherwise deserialize as None.
fn validate_model_numbers<T: Serialize + serde::de::DeserializeOwned + PartialEq>(
    model: &T,
    name: &str,
) -> PyResult<()> {
    let value = serde_json::to_value(model).map_err(invalid)?;
    let restored: T = serde_json::from_value(value.clone()).map_err(|_| {
        invalid(format!(
            "{name} contains a non-finite or out-of-range floating-point property"
        ))
    })?;
    if &restored != model {
        return Err(invalid(format!(
            "{name} contains a non-finite or out-of-range floating-point property"
        )));
    }
    fn visit(value: &Value, path: &str) -> PyResult<()> {
        match value {
            Value::Object(fields) => {
                for (key, value) in fields {
                    let path = format!("{path}.{key}");
                    if key == "font_size"
                        && let Some(size) = value.as_f64()
                        && !(size > 0.)
                    {
                        return Err(invalid(format!("{path} must be greater than 0 pixels")));
                    }
                    if [
                        "line_width",
                        "point_size",
                        "major_x_width",
                        "major_y_width",
                        "minor_x_width",
                        "minor_y_width",
                    ]
                    .contains(&key.as_str())
                        && let Some(size) = value.as_f64()
                        && size < 0.
                    {
                        return Err(invalid(format!("{path} must be nonnegative")));
                    }
                    visit(value, &path)?;
                }
            }
            Value::Array(values) => {
                for (index, value) in values.iter().enumerate() {
                    visit(value, &format!("{path}[{index}]"))?;
                }
            }
            _ => {}
        }
        Ok(())
    }
    visit(&value, name)
}

impl FigureCore {
    fn new(py: Python<'_>, width: u32, height: u32, pool_bytes: u64) -> PyResult<Self> {
        py.detach(move || {
            let gpu = gpu::context(pool_bytes)?;
            let figure_id = gpu::figure_id()?;
            let mut renderer = gpu::lock(&gpu)?;
            let mut config = default::default_config();
            config.chart_area = ChartArea(Rect {
                x: 0,
                y: 0,
                width,
                height,
            });
            config.legend.visible = false;
            config.right_y.out_margin = 25.0;
            config.top_x.out_margin = 25.0;
            let default_config = config.clone();
            let chart = Chart::new(config);
            validate_config(chart.config())?;
            let chart_id = renderer
                .register_chart(chart.config().clone(), Vec::new())
                .map_err(runtime)?;
            let mut hitmap = HitMap::new();
            let mut elements = Vec::new();
            macro_rules! add {
                ($el:expr) => {{
                    let el = $el;
                    let name = el.element_id();
                    let id = hitmap.register(el);
                    elements.push((name, id));
                }};
            }
            add!(DataAreaElement);
            for side in [Side::Top, Side::Bottom, Side::Left, Side::Right] {
                add!(AxisElement { side });
            }
            for side in [Side::Top, Side::Bottom, Side::Left, Side::Right] {
                add!(AxisLabelElement { side });
            }
            for side in [Side::Top, Side::Bottom, Side::Left, Side::Right] {
                add!(AxisTitleElement { side });
            }
            add!(LegendElement);
            add!(ChartTitleElement);
            add!(ColorBarElement);
            add!(ColorBarAxisElement);
            add!(ColorBarLabelElement);
            add!(ColorBarTitleElement);
            Ok(Self {
                identity: None,
                background: None,
                code_dpi: 120.0,
                default_config,
                gpu: Arc::clone(&gpu),
                figure_id,
                chart,
                chart_id,
                series: Vec::new(),
                hitmap,
                elements,
                columns: HashMap::new(),
                revision: 0,
                history: Default::default(),
                uploads: 0,
                readbacks: 0,
                png_encodes: 0,
                selection_value_readbacks: 0,
                preparation: None,
                target: None,
                document: None,
                render_warnings: Vec::new(),
                pending_warnings: Vec::new(),
                warnings_revision: None,
            })
        })
    }
}

impl FigureAccess<'_> {
    fn prepare(&mut self, py: Python<'_>) -> PyResult<String> {
        let report = py.detach(|| {
            let start = std::time::Instant::now();
            if let Some(family) = self.data.document.as_ref().map(|document| document.chart.family()) {
                let _ = self.render(1.)?;
                return Ok(json!({"backend":"native", "ready":true, "elapsed_ms":start.elapsed().as_secs_f64()*1000.,
                    "target_format":"Rgba8Unorm", "stages":[{"scope":family, "stage":"first-frame", "phase":"Ready"}],
                    "persistent_cache_supported":false}));
            }
            self.renderer.ensure_target_format(wgpu::TextureFormat::Rgba8Unorm).map_err(runtime)?;
            let device = self.renderer.device().clone();
            let oom = device.push_error_scope(wgpu::ErrorFilter::OutOfMemory);
            let validation = device.push_error_scope(wgpu::ErrorFilter::Validation);
            let mut stages = Vec::new();
            let prepared = pollster::block_on(self.renderer.prewarm_all_observed(&mut |event| {
                stages.push(json!({"scope":event.scope,"stage":event.stage,"phase":format!("{:?}",event.phase)}));
            })).map_err(runtime);
            self.renderer.wait_idle();
            let validation = pollster::block_on(validation.pop());
            let oom = pollster::block_on(oom.pop());
            if let Some(error) = oom { return Err(PyMemoryError::new_err(format!("GPU preparation allocation failed: {error}"))); }
            if let Some(error) = validation { return Err(runtime(format!("GPU preparation failed: {error}"))); }
            prepared?;
            // Execute the current document, not just create pipeline handles. No PNG encoding.
            let _ = self.render(1.0)?;
            Ok(json!({"backend":"native","ready":true,"elapsed_ms":start.elapsed().as_secs_f64()*1000.,
                "target_format":"Rgba8Unorm","stages":stages,"persistent_cache_supported":false}))
        })?;
        self.data.preparation = Some(report.clone());
        Ok(report.to_string())
    }
    fn upload_column(&mut self, id: &str, array: &Bound<'_, PyAny>) -> PyResult<()> {
        if let Ok(data) = array.extract::<PyReadonlyArray1<'_, f64>>() {
            self.upload(
                id,
                data.as_slice()
                    .map_err(|_| invalid("array must be contiguous"))?,
            )
        } else if let Ok(data) = array.extract::<PyReadonlyArray1<'_, f32>>() {
            self.upload(
                id,
                data.as_slice()
                    .map_err(|_| invalid("array must be contiguous"))?,
            )
        } else {
            Err(invalid(
                "expected contiguous one-dimensional float32 or float64 NumPy array",
            ))
        }
    }
    fn remove_column(&mut self, id: &str) -> PyResult<()> {
        self.renderer
            .remove_column(&gpu::column_id(self.data.figure_id, id))
            .map_err(runtime)?;
        self.data.columns.remove(id);
        Ok(())
    }
    fn settings_json(&self) -> PyResult<String> {
        serde_json::to_string(&self.snapshot()).map_err(runtime)
    }
    fn add_series(&mut self, json: &str) -> PyResult<()> {
        if self.data.document.is_some() {
            return Err(invalid(
                "a pie/donut Figure cannot contain Cartesian series",
            ));
        }
        let cfg: SeriesConfig = parse(json)?;
        validate_model_numbers(&cfg, "series")?;
        if self
            .data
            .series
            .iter()
            .any(|s| s.series_id == cfg.series_id)
        {
            return Err(invalid("series IDs must be unique"));
        }
        let mut next = self.data.series.clone();
        next.push(cfg);
        validate_draw_style(self.data.chart.config(), &next)?;
        self.renderer
            .set_chart_series(self.data.chart_id, gpu::series(self.data.figure_id, &next))
            .map_err(invalid)?;
        self.data.series = next;
        self.data.revision += 1;
        self.data.history = Default::default();
        Ok(())
    }
    // Upload rollback belongs to Python; document registration, fitting and
    // heatmap settings are one transaction under the document/GPU locks.
    fn add_series_fitted(
        &mut self,
        py: Python<'_>,
        json: &str,
        config: Option<&str>,
        bounds: Option<[f64; 4]>,
    ) -> PyResult<()> {
        let old = self.snapshot();
        let revision = self.data.revision;
        let history = self.data.history.clone();
        let result = (|| {
            if let Some(config) = config {
                self.commit_config(parse(config)?)?;
            }
            self.add_series(json)?;
            if let Some([xmin, xmax, ymin, ymax]) = bounds {
                self.set_range("x", xmin, xmax)?;
                self.set_range("y", ymin, ymax)?;
            } else {
                self.fit(py, 0.05)?;
            }
            validate_config(self.data.chart.config())?;
            Ok(())
        })();
        if let Err(error) = result {
            self.renderer
                .set_chart_state(
                    self.data.chart_id,
                    gpu::config(self.data.figure_id, &old.config),
                    gpu::series(self.data.figure_id, &old.series),
                )
                .map_err(runtime)?;
            self.data.chart = Chart::new(old.config);
            self.data.series = old.series;
            self.data.revision = revision;
            self.data.history = history;
            return Err(error);
        }
        self.data.revision = revision + 1;
        self.data.history = Default::default();
        Ok(())
    }
    fn add_series_batch(&mut self, py: Python<'_>, json: &str, config: &str) -> PyResult<()> {
        if self.data.document.is_some() {
            return Err(invalid("bounded charts cannot contain coordinate series"));
        }
        let previous = self.snapshot();
        let revision = self.data.revision;
        let history = self.data.history.clone();
        let result = (|| {
            let mut series = self.data.series.clone();
            series.extend(parse::<Vec<SeriesConfig>>(json)?);
            let config: Config = parse(config)?;
            validate_config(&config)?;
            validate_draw_style(&config, &series)?;
            self.renderer
                .set_chart_state(
                    self.data.chart_id,
                    gpu::config(self.data.figure_id, &config),
                    gpu::series(self.data.figure_id, &series),
                )
                .map_err(invalid)?;
            self.data.chart = Chart::new(config);
            self.refresh_addresses();
            self.data.series = series;
            self.fit(py, 0.05)
        })();
        if let Err(error) = result {
            self.renderer
                .set_chart_state(
                    self.data.chart_id,
                    gpu::config(self.data.figure_id, &previous.config),
                    gpu::series(self.data.figure_id, &previous.series),
                )
                .map_err(runtime)?;
            self.data.chart = Chart::new(previous.config);
            self.data.series = previous.series;
            self.data.revision = revision;
            self.data.history = history;
            return Err(error);
        }
        self.data.revision = revision + 1;
        self.data.history = Default::default();
        Ok(())
    }
    fn apply_settings(&mut self, json: &str) -> PyResult<()> {
        let before = serde_json::to_value(self.snapshot()).map_err(runtime)?;
        let base_revision = self.data.revision;
        let mut next: Settings = parse(json)?;
        if !self.data.history.restoring_identities() {
            identity::track_identities(&before, &mut next)?;
        }
        next.config
            .sync_subplot_links(Some(self.data.chart.config()));
        if !supported_settings_version(next.schema_version, &next.renderer_version) {
            return Err(invalid("unsupported settings/renderer version"));
        }
        validate_config(&next.config)?;
        validate_background(next.background)?;
        validate_draw_style(&next.config, &next.series)?;
        let document = next.document()?;
        if document.as_ref().map(|d| d.family())
            != self.data.document.as_ref().map(|d| d.chart.family())
        {
            return Err(invalid("settings cannot change the Figure's chart family"));
        }
        if let Some(chart) = &document {
            if !matches!(next.config.draw_style, renderer::config::DrawStyle::Precise) {
                return Err(invalid(
                    "bounded charts use materials, not Cartesian draw styles",
                ));
            }
            chart.validate(next.config.chart_area.0)?;
        }
        for series in &next.series {
            validate_model_numbers(series, "series")?;
        }
        // Settings cannot introduce, remove or silently reconnect source arrays.
        if next.series.len() != self.data.series.len()
            || next.series.iter().zip(&self.data.series).any(|(a, b)| {
                a.series_id != b.series_id || a.x_column != b.x_column || a.y_column != b.y_column
            })
        {
            return Err(invalid(
                "settings must address the same ordered series and source columns",
            ));
        }
        let old = self.data.series.clone();
        let series_changed = next.series != old;
        if series_changed
            || next.config != *self.data.chart.config()
            || next.config.colorbar.as_ref().map(|bar| &bar.colormap)
                != self
                    .data
                    .chart
                    .config()
                    .colorbar
                    .as_ref()
                    .map(|bar| &bar.colormap)
        {
            identity::refresh_legends(&mut next.config, &next.series);
        }
        let radial_changed = document.as_ref() != self.data.document.as_ref().map(|r| &r.chart);
        if next.config == *self.data.chart.config()
            && !series_changed
            && !radial_changed
            && next.background == self.data.background
            && next.identity == self.data.identity
        {
            return Ok(());
        }
        // Config and series can introduce or remove dependencies together
        // (for example, a point color map and its colorbar). Let the renderer
        // validate and commit the complete state without an invalid interim.
        self.renderer
            .set_chart_state(
                self.data.chart_id,
                gpu::config(self.data.figure_id, &next.config),
                gpu::series(self.data.figure_id, &next.series),
            )
            .map_err(invalid)?;
        self.data.chart = Chart::new(next.config);
        self.refresh_addresses();
        self.data.series = next.series;
        self.data.background = next.background;
        self.data.identity = next.identity;
        if let Some(chart) = document {
            self.data.document.as_mut().unwrap().chart = chart;
        }
        self.data.revision += 1;
        let after = serde_json::to_value(self.snapshot()).map_err(runtime)?;
        self.data.history.record(
            before,
            after,
            base_revision,
            self.data.revision,
            "Edit chart",
        );
        Ok(())
    }
    fn log_bounds(&mut self, axis: &str) -> PyResult<(f64, f64)> {
        self.log_bounds_for(axis, self.data.chart.config().active_layer())
    }
    fn log_bounds_for(&mut self, axis: &str, layer: renderer::LayerRef) -> PyResult<(f64, f64)> {
        let selected: Vec<_> = self
            .data
            .series
            .iter()
            .filter(|s| identity::fit_member(self.data.chart.config(), &s.series_id, axis, layer))
            .cloned()
            .collect();
        let mut extra = renderer::chart::FitExtent::EMPTY;
        if matches!(axis, "x" | "y") {
            let errorbars: Vec<_> = gpu::series(self.data.figure_id, &selected)
                .into_iter()
                .filter(|s| {
                    matches!(
                        s.render_type,
                        renderer::DataRenderType::ScatterErrorbarX { .. }
                            | renderer::DataRenderType::ScatterErrorbarY { .. }
                            | renderer::DataRenderType::ScatterErrorbarXY { .. }
                            | renderer::DataRenderType::LineScatterErrorbarX { .. }
                            | renderer::DataRenderType::LineScatterErrorbarY { .. }
                            | renderer::DataRenderType::LineScatterErrorbarXY { .. }
                    )
                })
                .collect();
            if !errorbars.is_empty() {
                pollster::block_on(self.renderer.ensure_errorbar_extent_engine())
                    .map_err(runtime)?;
                let jobs = errorbars
                    .iter()
                    .map(|s| self.renderer.begin_series_fit_extent(s))
                    .collect::<Result<Vec<_>, _>>()
                    .map_err(runtime)?;
                self.renderer.wait_idle();
                for job in jobs.into_iter().flatten() {
                    if let Some(bounds) = pollster::block_on(job.resolve()).map_err(runtime)? {
                        let bounds = if axis == "x" { bounds.x } else { bounds.y };
                        extra.union(&renderer::chart::FitExtent {
                            min: bounds.min,
                            max: bounds.max,
                            min_positive: bounds.min_positive,
                        });
                    }
                }
            }
        }
        positive_data_bounds(axis, &selected, extra, |id| {
            Chart::slot_extent(
                self.renderer.pool(),
                &gpu::column_id(self.data.figure_id, id),
            )
            .map_err(runtime)
        })
    }
    fn fit(&mut self, py: Python<'_>, padding: f64) -> PyResult<()> {
        self.fit_domain(py, padding, false)
    }
    fn fit_domain(&mut self, py: Python<'_>, padding: f64, active_only: bool) -> PyResult<()> {
        if !padding.is_finite() || padding < 0.0 {
            return Err(invalid("padding must be finite and non-negative"));
        }
        let extents = py.detach(|| -> PyResult<Vec<[renderer::chart::FitExtent; 2]>> {
            pollster::block_on(self.renderer.ensure_errorbar_extent_engine()).map_err(runtime)?;
            let specs = gpu::series(self.data.figure_id, &self.data.series);
            let mut jobs = Vec::new();
            let mut extents = Vec::new();
            for series in &specs {
                let a =
                    Chart::slot_extent(self.renderer.pool(), &series.x_column).map_err(runtime)?;
                let b =
                    Chart::slot_extent(self.renderer.pool(), &series.y_column).map_err(runtime)?;
                extents.push([a, b]);
                jobs.push(
                    self.renderer
                        .begin_series_fit_extent(series)
                        .map_err(runtime)?,
                );
            }
            self.renderer.wait_idle();
            for (i, job) in jobs.into_iter().enumerate() {
                if let Some(job) = job {
                    extents[i] =
                        if let Some(e) = pollster::block_on(job.resolve()).map_err(runtime)? {
                            [
                                renderer::chart::FitExtent {
                                    min: e.x.min,
                                    max: e.x.max,
                                    min_positive: e.x.min_positive,
                                },
                                renderer::chart::FitExtent {
                                    min: e.y.min,
                                    max: e.y.max,
                                    min_positive: e.y.min_positive,
                                },
                            ]
                        } else {
                            [renderer::chart::FitExtent::EMPTY; 2]
                        };
                }
                if let renderer::DataRenderType::Histogram { bar } = &specs[i].render_type {
                    let dimension = usize::from(matches!(
                        bar.orientation,
                        renderer::data_config::BarOrientation::Vertical
                    ));
                    extents[i][dimension].union(&renderer::chart::FitExtent {
                        min: bar.baseline,
                        max: bar.baseline,
                        min_positive: (bar.baseline > 0.).then_some(bar.baseline),
                    });
                }
            }
            Ok(extents)
        })?;
        let config = document_fit::fit(
            self.data.chart.config(),
            &self.data.series,
            &extents,
            padding,
            active_only,
        );
        self.commit_config(config)
    }
    fn set_range(&mut self, axis: &str, min: f64, max: f64) -> PyResult<()> {
        if !min.is_finite() || !max.is_finite() || min >= max {
            return Err(invalid("range must be finite and increasing"));
        }
        let next = document_fit::set_range(self.data.chart.config(), axis, min, max)?;
        self.commit_config(next)
    }

    fn render_rgba<'py>(
        &mut self,
        py: Python<'py>,
        scale: f32,
    ) -> PyResult<(u32, u32, Bound<'py, PyBytes>)> {
        if !scale.is_finite() || !(0.25..=8.0).contains(&scale) {
            return Err(invalid("scale must be 0.25..8"));
        }
        let image = py.detach(|| self.render(scale))?;
        Ok((image.width, image.height, PyBytes::new(py, &image.rgba)))
    }
    fn render_png<'py>(&mut self, py: Python<'py>, scale: f32) -> PyResult<Bound<'py, PyBytes>> {
        if !scale.is_finite() || !(0.25..=8.0).contains(&scale) {
            return Err(invalid("scale must be 0.25..8"));
        }
        self.data.png_encodes += 1;
        let bytes = py.detach(|| {
            let image = self.render(scale)?;
            encode_png(&image).map_err(runtime)
        })?;
        Ok(PyBytes::new(py, &bytes))
    }
    fn hit_test(&mut self, x: f32, y: f32) -> PyResult<Option<String>> {
        if self.data.document.is_some() {
            let frame = self.document_frame()?;
            let map = frame.decorations();
            let annotations = self.document_annotations()?;
            return Ok(
                match annotations.hit_test_active_layer(
                    self.data.document.as_ref().unwrap().chart.active_layer(),
                    map,
                    [x, y],
                ) {
                    Some(renderer::annotation::LayerHit::Annotation { index, .. }) => {
                        Some(format!("annotation_{index}"))
                    }
                    Some(renderer::annotation::LayerHit::Element(id)) => {
                        map.element(id).map(|e| e.id.element_id())
                    }
                    None => None,
                },
            );
        }
        if self.data.chart.config().active_layer() == renderer::LayerRef::Annotations {
            let view = self.annotation_view()?;
            if let Some(id) = view.annotation_map().hit_test([x, y]) {
                let index = view
                    .annotation_map()
                    .entries()
                    .find(|(hit, _)| *hit == id)
                    .map(|(_, item)| item.index)
                    .unwrap();
                return Ok(Some(format!(
                    "annotation:{}",
                    self.data.chart.config().annotations.items[index].id
                )));
            }
        }
        Ok(self
            .data
            .hitmap
            .hit_test(
                self.data.chart.config(),
                &CpuTextMeasure::for_style(&self.data.chart.config().draw_style),
                x,
                y,
            )
            .and_then(|id| self.data.hitmap.get(id))
            .map(|el| el.element_id()))
    }
    fn bounds_json(&mut self, target: &str) -> PyResult<String> {
        if self.data.document.is_some()
            && let Some(index) = target
                .strip_prefix("annotation_")
                .and_then(|v| v.parse::<usize>().ok())
        {
            let frame = self.document_annotations()?;
            let value = frame.annotations().find(index).and_then(|id|frame.annotations().selection_box(id)).map(|b|json!({"rect":[b.rect.x,b.rect.y,b.rect.width,b.rect.height],"handles":b.handles.iter().map(|r|vec![r.x,r.y,r.width,r.height]).collect::<Vec<_>>()}));
            return serde_json::to_string(&value).map_err(runtime);
        }

        if target.starts_with("annotation:") {
            let view = self.annotation_view()?;
            let map = view.annotation_map();
            let value = map.find(self.annotation_index(target)?).and_then(|id| map.selection_box(id)).map(|b| json!({"rect":[b.rect.x,b.rect.y,b.rect.width,b.rect.height],"handles":b.handles.iter().map(|r|vec![r.x,r.y,r.width,r.height]).collect::<Vec<_>>() }));
            return serde_json::to_string(&value).map_err(runtime);
        }

        if self.data.document.is_some() {
            let frame = self.document_frame()?;
            let map = frame.decorations();
            let (id, _) = map
                .entries()
                .find(|(_, e)| e.id.element_id() == target)
                .ok_or_else(|| invalid("unknown decoration"))?;
            let value=map.selection_box(id).map(|b|json!({"rect":[b.rect.x,b.rect.y,b.rect.width,b.rect.height],"handles":b.handles.iter().map(|r|vec![r.x,r.y,r.width,r.height]).collect::<Vec<_>>()}));
            return serde_json::to_string(&value).map_err(runtime);
        }
        let id = self.element(target)?;
        let measure = CpuTextMeasure::for_style(&self.data.chart.config().draw_style);
        let value = self.data.hitmap.selection_box(id, self.data.chart.config(), &measure).map(|b| json!({
            "rect": [b.rect.x, b.rect.y, b.rect.width, b.rect.height],
            "handles": b.handles.iter().map(|r| vec![r.x, r.y, r.width, r.height]).collect::<Vec<_>>()
        }));
        serde_json::to_string(&value).map_err(runtime)
    }
    fn resize_handle(&mut self, target: &str, x: f32, y: f32) -> PyResult<Option<String>> {
        if target.starts_with("annotation:") {
            let view = self.annotation_view()?;
            return Ok(view
                .annotation_map()
                .find(self.annotation_index(target)?)
                .and_then(|id| view.annotation_map().hit_resize_handle(id, [x, y]))
                .map(|h| format!("{h:?}")));
        }
        let id = self.element(target)?;
        Ok(self
            .data
            .hitmap
            .get(id)
            .and_then(|e| e.as_resizable())
            .and_then(|e| {
                e.hit_resize_handle(
                    self.data.chart.config(),
                    &CpuTextMeasure::for_style(&self.data.chart.config().draw_style),
                    x,
                    y,
                )
            })
            .map(|h| format!("{h:?}")))
    }
    fn drag(&mut self, target: &str, dx: f32, dy: f32, handle: Option<&str>) -> PyResult<bool> {
        if !dx.is_finite() || !dy.is_finite() {
            return Err(invalid("drag must be finite"));
        }
        if self.data.document.is_some() {
            return self.document_drag(target, dx, dy, handle);
        }
        if target.starts_with("annotation:") {
            let view = self.annotation_view()?;
            let map = view.annotation_map();
            let id = map
                .find(self.annotation_index(target)?)
                .ok_or_else(|| invalid("annotation is not visible"))?;
            let mut config = self.data.chart.config().clone();
            let moved = if let Some(handle) = handle {
                let handle = ALL_HANDLES
                    .into_iter()
                    .find(|h| format!("{h:?}") == handle)
                    .ok_or_else(|| invalid("unknown resize handle"))?;
                map.resize_by(&mut config.annotations, id, handle, dx, dy)
            } else {
                map.drag_by(&mut config.annotations, id, dx, dy)
            };
            if moved == Some(renderer::layout::NudgeResult::Moved) {
                self.commit_config(config)?;
                return Ok(true);
            }
            return Ok(false);
        }

        let id = self.element(target)?;
        let el = self.data.hitmap.get(id).unwrap();
        let mut cfg = self.data.chart.config().clone();
        let result = if let Some(handle) = handle {
            let h: ResizeHandle = ALL_HANDLES
                .into_iter()
                .find(|h| format!("{h:?}") == handle)
                .ok_or_else(|| invalid("unknown resize handle"))?;
            el.as_resizable()
                .ok_or_else(|| invalid("element cannot be resized"))?
                .resize_by(&mut cfg, h, dx, dy)
        } else {
            el.as_draggable()
                .ok_or_else(|| invalid("element cannot be dragged"))?
                .drag_by(&mut cfg, dx, dy)
        };
        if result == renderer::layout::NudgeResult::Moved {
            self.commit_config(cfg)?;
            Ok(true)
        } else {
            Ok(false)
        }
    }
    fn pick_json(&mut self, py: Python<'_>, x: f32, y: f32) -> PyResult<String> {
        if self.data.document.is_some() {
            return py.detach(|| self.pick_document(x, y));
        }
        let picked = py.detach(|| {
            self.renderer.enable_gpu_picking().map_err(runtime)?;
            let request = GpuPickRequest {
                canvas_position_px: [x, y],
                display_panel_px: self.data.chart.config().chart_area.0,
                display_scale: 1.0,
                max_distance_px: 6.0,
            };
            let ticket = self
                .renderer
                .pick_chart_data(self.data.chart_id, request)
                .map_err(runtime)?;
            self.renderer.wait_idle();
            pollster::block_on(ticket.resolve()).map_err(runtime)
        })?;
        let picked = picked.map(|p| {
            let mut reference = p.to_ref();
            gpu::local_selection(self.data.figure_id, &mut reference);
            (p.distance_px(), reference)
        });
        let mut cfg = self.data.chart.config().clone();
        cfg.picked_data = picked
            .as_ref()
            .map(|p| renderer::config::DataSelectionsConfig {
                refs: vec![p.1.clone()],
                ..Default::default()
            });
        if cfg != *self.data.chart.config() {
            self.commit_config(cfg)?;
        }
        let value =
            picked.map(|p| json!({"target":p.1.series_id(), "distance_px":p.0, "identity":p.1}));
        serde_json::to_string(&value).map_err(runtime)
    }
    fn clear_data_selection(&mut self) -> PyResult<()> {
        if let Some(radial) = self.data.document.as_mut() {
            let old = radial.chart.clone();
            radial.chart.clear_selection();
            if radial.chart != old {
                self.data.revision += 1;
            }
            return Ok(());
        }
        let mut cfg = self.data.chart.config().clone();
        if cfg.picked_data.is_some() || cfg.picked_points.is_some() {
            cfg.picked_data = None;
            cfg.picked_points = None;
            self.commit_config(cfg)?;
        }
        Ok(())
    }
    fn selection_details_json(&mut self, py: Python<'_>) -> PyResult<String> {
        let reference = self
            .data
            .chart
            .config()
            .picked_data
            .as_ref()
            .and_then(|s| s.refs.first())
            .cloned();
        let details = reference
            .map(|r| py.detach(|| self.selection_details(&r)))
            .transpose()?;
        serde_json::to_string(&details).map_err(runtime)
    }
    fn move_data_selection(&mut self, py: Python<'_>, dx: i32, dy: i32) -> PyResult<bool> {
        py.detach(|| self.step_selection(dx, dy))
    }
    fn info_json(&self) -> String {
        let host_bytes = self.data.target.as_ref().map_or(0, |t| {
            u64::from(t.width) * u64::from(t.height) * 4
                + u64::from(t.row_bytes) * u64::from(t.height)
        });
        json!({"adapter": self.context.adapter_info, "gpu_context_id":self.context.id,"figure_id":self.data.figure_id,"gpu_sharing":"process","active_figures":self.renderer.chart_order().len(),"figure_column_bytes":self.data.columns.values().map(|v|v.0 as u64 * 8).sum::<u64>(), "revision": self.data.revision, "column_uploads": self.data.uploads, "rgba_readbacks": self.data.readbacks, "png_encodes": self.data.png_encodes, "columns": self.data.columns.len(),
            "selection_value_readbacks":self.data.selection_value_readbacks,"pool_capacity_bytes": self.renderer.pool().capacity(), "pool_used_bytes": self.renderer.pool().used_bytes(),
            "known_gpu_bytes": self.renderer.gpu_memory_usage().total_bytes() + host_bytes + self.data.document.as_ref().map_or(0, |r| r.gpu_bytes()), "allocation_mode": if self.data.document.is_some() { "bounded" } else { "resident" }, "preparation": self.data.preparation}).to_string()
    }
}

mod annotation_edit;
mod axis_edit;
mod bounded;
mod desktop;
mod document_fit;
mod drawing;
mod edit_history;
mod editor;
mod gpu;
mod identity;
mod interaction;
mod navigation;
mod notebook;
mod property_catalog;
mod target_chooser;
mod tick_policy;
mod ui_fonts;
use identity::{validate_columns, validate_identity};
mod selection;

#[pyclass(module = "figgyplot._native")]
struct NativeFigure {
    core: Arc<Mutex<FigureCore>>,
}

impl NativeFigure {
    fn lock(&self) -> PyResult<std::sync::MutexGuard<'_, FigureCore>> {
        Python::attach(|py| self.core.lock_py_attached(py))
            .map_err(|_| runtime("native Figure lock poisoned"))
    }
    fn with<R>(&self, operation: impl FnOnce(&mut FigureAccess<'_>) -> PyResult<R>) -> PyResult<R> {
        let mut data = self.lock()?;
        let gpu = Arc::clone(&data.gpu);
        let mut renderer = gpu::lock(&gpu)?;
        operation(&mut FigureAccess::new(&gpu, &mut data, &mut renderer))
    }
}
#[pymethods]
impl NativeFigure {
    #[new]
    #[pyo3(signature=(width=960, height=600, pool_bytes=8388608, dpi=120.0))]
    fn new(py: Python<'_>, width: u32, height: u32, pool_bytes: u64, dpi: f64) -> PyResult<Self> {
        if !dpi.is_finite() || dpi <= 0.0 {
            return Err(invalid("dpi must be positive and finite"));
        }
        let mut core = FigureCore::new(py, width, height, pool_bytes)?;
        core.code_dpi = dpi;
        Ok(Self {
            core: Arc::new(Mutex::new(core)),
        })
    }
    fn upload_column(&self, id: &str, array: &Bound<'_, PyAny>) -> PyResult<()> {
        self.with(|core| core.upload_column(id, array))
    }
    fn remove_column(&self, id: &str) -> PyResult<()> {
        self.with(|core| core.remove_column(id))
    }
    fn settings_json(&self) -> PyResult<String> {
        self.with(|core| core.settings_json())
    }
    fn add_series(&self, json: &str) -> PyResult<()> {
        self.with(|core| core.add_series(json))
    }
    fn add_series_fitted(
        &self,
        py: Python<'_>,
        json: &str,
        config: Option<&str>,
        bounds: Option<[f64; 4]>,
    ) -> PyResult<()> {
        self.with(|core| core.add_series_fitted(py, json, config, bounds))
    }
    fn add_series_batch(&self, py: Python<'_>, json: &str, config: &str) -> PyResult<()> {
        self.with(|core| core.add_series_batch(py, json, config))
    }
    fn apply_settings(&self, json: &str) -> PyResult<()> {
        self.with(|core| core.apply_settings(json))
    }
    fn edit_history_json(&self) -> PyResult<String> {
        self.with(|core| Ok(core.data.history.status().to_string()))
    }
    fn column_extents_json(&self) -> PyResult<String> {
        self.with(|core| {
            Ok(json!(
                core.data
                    .columns
                    .iter()
                    .map(|(name, (_, min, max))| (name.clone(), json!([min, max])))
                    .collect::<serde_json::Map<_, _>>()
            )
            .to_string())
        })
    }
    fn edit_operations_json(&self) -> PyResult<String> {
        self.with(|core| Ok(core.data.history.operations().to_string()))
    }
    fn undo(&self) -> PyResult<()> {
        self.with(|core| core.replay_edit(false))
    }
    fn redo(&self) -> PyResult<()> {
        self.with(|core| core.replay_edit(true))
    }
    fn reset_edits(&self) -> PyResult<()> {
        self.with(|core| core.reset_edits())
    }
    fn mark_edit_baseline(&self) -> PyResult<()> {
        self.with(|core| {
            let state = serde_json::to_value(core.snapshot()).map_err(runtime)?;
            core.data.history.mark_baseline(state)
        })
    }
    fn begin_edit(&self, label: &str) -> PyResult<()> {
        self.with(|core| {
            core.begin_edit(label);
            Ok(())
        })
    }
    fn end_edit(&self) -> PyResult<()> {
        self.with(|core| {
            core.end_edit();
            Ok(())
        })
    }
    fn set_bounded(&self, family: &str, json: &str) -> PyResult<()> {
        self.with(|core| core.set_bounded(family, json))
    }
    fn set_radial(&self, json: &str) -> PyResult<()> {
        self.with(|core| core.set_radial(json))
    }
    fn fit_active(&self, py: Python<'_>, padding: f64) -> PyResult<()> {
        self.with(|core| core.fit_domain(py, padding, true))
    }
    fn fit(&self, py: Python<'_>, padding: f64) -> PyResult<()> {
        self.with(|core| core.fit(py, padding))
    }
    fn log_bounds_at(&self, axis: &str, layer: &str) -> PyResult<(f64, f64)> {
        let layer = parse(layer)?;
        self.with(|core| core.log_bounds_for(axis, layer))
    }
    fn log_bounds(&self, axis: &str) -> PyResult<(f64, f64)> {
        self.with(|core| core.log_bounds(axis))
    }
    fn prepare_json(&self, py: Python<'_>) -> PyResult<String> {
        self.with(|core| core.prepare(py))
    }
    fn set_range(&self, axis: &str, min: f64, max: f64) -> PyResult<()> {
        self.with(|core| core.set_range(axis, min, max))
    }
    fn bounds_json(&self, target: &str) -> PyResult<String> {
        self.with(|core| core.bounds_json(target))
    }
    fn resize_handle(&self, target: &str, x: f32, y: f32) -> PyResult<Option<String>> {
        self.with(|core| core.resize_handle(target, x, y))
    }
    #[pyo3(signature=(target, dx, dy, handle=None))]
    fn drag(&self, target: &str, dx: f32, dy: f32, handle: Option<&str>) -> PyResult<bool> {
        self.with(|core| core.drag(target, dx, dy, handle))
    }
    fn pick_json(&self, py: Python<'_>, x: f32, y: f32) -> PyResult<String> {
        self.with(|core| core.pick_json(py, x, y))
    }
    fn clear_data_selection(&self) -> PyResult<()> {
        self.with(|core| core.clear_data_selection())
    }
    fn selection_details_json(&self, py: Python<'_>) -> PyResult<String> {
        self.with(|core| core.selection_details_json(py))
    }
    fn move_data_selection(&self, py: Python<'_>, dx: i32, dy: i32) -> PyResult<bool> {
        self.with(|core| core.move_data_selection(py, dx, dy))
    }
    #[pyo3(signature=(scale=1.0))]
    fn render_rgba<'py>(
        &self,
        py: Python<'py>,
        scale: f32,
    ) -> PyResult<(u32, u32, Bound<'py, PyBytes>)> {
        self.with(|core| core.render_rgba(py, scale))
    }
    #[pyo3(signature=(scale=1.0))]
    fn render_png<'py>(&self, py: Python<'py>, scale: f32) -> PyResult<Bound<'py, PyBytes>> {
        self.with(|core| core.render_png(py, scale))
    }
    fn hit_test(&self, x: f32, y: f32) -> PyResult<Option<String>> {
        self.with(|core| core.hit_test(x, y))
    }
    fn info_json(&self) -> PyResult<String> {
        self.with(|core| Ok(core.info_json()))
    }
    /// Messages for tick settings the last rebuilt axis raster replaced, each
    /// returned once after the list changed.
    fn take_render_warnings(&self) -> PyResult<Vec<String>> {
        Ok(std::mem::take(&mut self.lock()?.pending_warnings))
    }
    #[getter]
    fn revision(&self) -> PyResult<u64> {
        Ok(self.lock()?.revision)
    }
    #[pyo3(signature=(block=true))]
    fn show(&self, py: Python<'_>, block: bool) -> PyResult<desktop::WindowHandle> {
        let core = self.core.clone();
        py.detach(move || desktop::show(core, block))
    }
}

#[pymodule(gil_used = true)]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NativeFigure>()?;
    m.add_function(wrap_pyfunction!(gpu::release_gpu, m)?)?;
    m.add_function(wrap_pyfunction!(gpu::collect_gpu, m)?)?;
    m.add_class::<notebook::NotebookFigure>()?;
    m.add_class::<desktop::WindowHandle>()?;
    m.add_function(wrap_pyfunction!(desktop::poll_events, m)?)?;
    m.add_function(wrap_pyfunction!(desktop::run_events, m)?)?;
    m.add_function(wrap_pyfunction!(default_colorbar_json, m)?)?;
    m.add_function(wrap_pyfunction!(rebuild_legend_json, m)?)?;
    m.add_function(wrap_pyfunction!(bounded::default_radial_json, m)?)?;
    m.add_function(wrap_pyfunction!(bounded::default_bounded_json, m)?)?;
    m.add_function(wrap_pyfunction!(draw_style_specs_json, m)?)?;
    m.add_function(wrap_pyfunction!(font_family_available, m)?)?;
    m.add_function(wrap_pyfunction!(text_segments_json, m)?)?;
    m.add_function(wrap_pyfunction!(segments_plain_text, m)?)?;
    m.add_function(wrap_pyfunction!(fitted_chart_title_margin, m)?)?;
    m.add_function(wrap_pyfunction!(fitted_range_json, m)?)?;
    m.add_function(wrap_pyfunction!(navigation::object_outline_json, m)?)?;
    m.add_function(wrap_pyfunction!(property_catalog::editor_catalog_json, m)?)?;
    m.add_function(wrap_pyfunction!(property_catalog::editor_property_json, m)?)?;
    m.add_function(wrap_pyfunction!(navigation::bounded_view_json, m)?)?;
    m.add_function(wrap_pyfunction!(axis_edit::sync_linked_axis_edit_json, m)?)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}

/// Whether a font family resolves to a registered or installed face rather
/// than the bundled fallback (native text stack).
#[pyfunction]
fn font_family_available(family: &str) -> bool {
    renderer::text_render::font_family_available(family)
}

/// The renderer's plain-text segments for `text`, including its
/// superscript/subscript character mapping.
#[pyfunction]
fn text_segments_json(text: &str) -> PyResult<String> {
    serde_json::to_string(&renderer::text::rich_segments_from_text(text)).map_err(runtime)
}

/// The text whose renderer segments are exactly `json`, when there is one.
/// Lets code export write `text_segments("10⁻³")` back instead of raw dicts.
#[pyfunction]
fn segments_plain_text(json: &str) -> PyResult<Option<String>> {
    let segments: Vec<renderer::text::RichSegment> = parse(json)?;
    Ok(plain_text_of(&segments))
}

/// The text whose renderer segments are exactly `segments`, when there is one:
/// the inverse of `rich_segments_from_text`, so editors can show and re-map
/// "10⁻³" without losing its superscripts.
pub(crate) fn plain_text_of(segments: &[renderer::text::RichSegment]) -> Option<String> {
    use renderer::text::{RichSegment, rich_segments_from_text};
    use std::sync::OnceLock;
    // Characters the renderer maps to styled segments, found by asking the
    // renderer itself over the blocks that hold super/subscript forms.
    static STYLED: OnceLock<Vec<(RichSegment, char)>> = OnceLock::new();
    let styled = STYLED.get_or_init(|| {
        ('\u{a0}'..='\u{2fff}')
            .chain('\u{1d00}'..='\u{1dbf}')
            .filter_map(|c| {
                let segment = rich_segments_from_text(&c.to_string()).pop()?;
                (segment.text != c).then_some((segment, c))
            })
            .collect()
    });
    let text: String = segments
        .iter()
        .map(|segment| {
            styled
                .iter()
                .find(|(styled, _)| styled == segment)
                .map_or(segment.text, |(_, c)| *c)
        })
        .collect();
    (rich_segments_from_text(&text) == segments).then_some(text)
}

/// `chart_title.top_margin` after the renderer's title-band fit: grown to the
/// measured title when the title is taller than its band, otherwise as given.
/// The title helpers call it; settings applied directly keep their margin.
#[pyfunction]
fn fitted_chart_title_margin(config: &str) -> PyResult<f32> {
    let mut config: Config = parse(config)?;
    let measure = renderer::CpuTextMeasure::for_style(&config.draw_style);
    renderer::layout::fit_chart_title_margin(&mut config, &measure);
    Ok(config.chart_title.top_margin)
}

#[pyfunction]
fn fitted_range_json(config: &str, axis: &str, min: f64, max: f64) -> PyResult<String> {
    if !min.is_finite() || !max.is_finite() || min >= max {
        return Err(invalid("range must be finite and increasing"));
    }
    let config: Config = parse(config)?;
    let fitted = document_fit::set_range(&config, axis, min, max)?;
    validate_config(&fitted)?;
    serde_json::to_string(&fitted).map_err(invalid)
}

#[pyfunction]
fn default_colorbar_json() -> PyResult<String> {
    serde_json::to_string(&default::default_colorbar_options()).map_err(runtime)
}

#[pyfunction]
#[pyo3(signature = (series, rich, colormap=None))]
fn rebuild_legend_json(series: &str, rich: &str, colormap: Option<&str>) -> PyResult<String> {
    let series: Vec<SeriesConfig> = parse(series)?;
    let mut rich: renderer::text::RichText = parse(rich)?;
    let colormap: Option<renderer::colormap::ColorMap> = colormap.map(parse).transpose()?;
    rich.segments.clear();
    for spec in series {
        if let Some(label) = &spec.label {
            renderer::legend::append_legend_entry_rich(
                &mut rich,
                renderer::legend::series_symbol_segments(&spec, colormap.as_ref()),
                label.segments.clone(),
            );
        }
    }
    serde_json::to_string(&rich).map_err(runtime)
}
