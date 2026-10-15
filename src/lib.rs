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
        let raw: Value = serde_json::from_str(json).map_err(invalid)?;
        let style = raw
            .get("draw_style")
            .or_else(|| raw.get("config").and_then(|c| c.get("draw_style")));
        if let Some(style) = style {
            let parsed: renderer::config::DrawStyle =
                serde_json::from_value(style.clone()).map_err(invalid)?;
            if let Some(fields) = style.as_object() {
                for key in fields.keys() {
                    if key != "mode" && !draw_style_specs(&parsed).iter().any(|p| p.key == key) {
                        return Err(invalid(format!("unknown draw-style parameter: {key}")));
                    }
                }
            }
        }
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

/// Renderer version stamped into, and required from, Settings documents.
/// It names the `figgy-renderer` pin in Cargo.toml; update both together.
const RENDERER_VERSION: &str = "0.16.1";

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
    uploads: u64,
    readbacks: u64,
    png_encodes: u64,
    selection_value_readbacks: u64,
    preparation: Option<Value>,
    target: Option<RenderTarget>,
    radial: Option<radial::RadialDocument>,
    /// Tick-guard warnings of the last rebuilt axis raster, and the messages
    /// not yet handed to Python. The renderer re-derives them only when the
    /// raster is rebuilt; a changed list is reported once.
    render_warnings: Vec<renderer::RenderWarning>,
    pending_warnings: Vec<String>,
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
    fn render_inner(&mut self, scale: f32) -> PyResult<renderer::RasterImage> {
        if self.data.radial.is_some() {
            return self.render_radial(scale);
        }
        self.renderer
            .ensure_target_format(wgpu::TextureFormat::Rgba8Unorm)
            .map_err(runtime)?;
        let styled = !matches!(
            self.data.chart.config().draw_style,
            renderer::config::DrawStyle::Precise
        );
        if scale != 1.0 && !styled {
            return pollster::block_on(self.renderer.export_panel_rgba_with_clear_async(
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
        let chart = Chart::new(config);
        let rect = chart.config().chart_area.0;
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
                .create_chart_view(&chart, rect)
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
                .refresh_axis(&mut target.view, &chart, rect)
                .map_err(runtime)?;
            target.revision = self.data.revision;
        }
        if target.view.render_warnings() != self.data.render_warnings.as_slice() {
            let warnings = target.view.render_warnings().to_vec();
            self.data.pending_warnings = warnings.iter().map(ToString::to_string).collect();
            self.data.render_warnings = warnings;
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
        self.data
            .elements
            .iter()
            .find(|(name, _)| name == target)
            .map(|(_, id)| *id)
            .ok_or_else(|| invalid(format!("unknown decoration: {target}")))
    }
    fn commit_config(&mut self, config: Config) -> PyResult<()> {
        validate_config(&config)?;
        validate_draw_style(&config, &self.data.series)?;
        self.renderer
            .set_chart_config(
                self.data.chart_id,
                gpu::config(self.data.figure_id, &config),
            )
            .map_err(invalid)?;
        self.data.chart = Chart::new(config);
        self.data.revision += 1;
        Ok(())
    }
    fn snapshot(&self) -> Settings {
        Settings {
            schema_version: 1,
            renderer_version: RENDERER_VERSION.into(),
            config: self.data.chart.config().clone(),
            series: self.data.series.clone(),
            radial: self.data.radial.as_ref().map(|r| r.chart.clone()),
            background: self.data.background,
        }
    }
}

fn validate_config(config: &Config) -> PyResult<()> {
    validate_model_numbers(config, "config")?;
    let rect = config.chart_area.0;
    if rect.x != 0
        || rect.y != 0
        || rect.width == 0
        || rect.height == 0
        || rect.width > 8192
        || rect.height > 8192
    {
        return Err(invalid(
            "chart canvas must begin at (0, 0) and be 1..8192 pixels",
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

/// Record in the SSOT that the host fixed this dimension's range, on both
/// axes of the pair, so later fits (e.g. when a series is added) keep it.
fn mark_range_fixed(config: &mut Config, axis: &str) {
    let (a, b) = match axis {
        "x" => (&mut config.bottom_x, &mut config.top_x),
        _ => (&mut config.left_y, &mut config.right_y),
    };
    a.range_locked = true;
    b.range_locked = true;
}

fn clear_range_fixed(config: &mut Config) {
    for axis in [
        &mut config.bottom_x,
        &mut config.top_x,
        &mut config.left_y,
        &mut config.right_y,
    ] {
        axis.range_locked = false;
    }
}

fn validate_draw_style(config: &Config, series: &[SeriesConfig]) -> PyResult<()> {
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
    if matches!(config.draw_style, DrawStyle::Constellation(_))
        && series
            .iter()
            .any(|s| !matches!(s.render_type, DataRenderType::ScatterLine { .. }))
    {
        return Err(invalid(
            "Constellation requires line series with markers (plot(..., marker='o'))",
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
                uploads: 0,
                readbacks: 0,
                png_encodes: 0,
                selection_value_readbacks: 0,
                preparation: None,
                target: None,
                radial: None,
                render_warnings: Vec::new(),
                pending_warnings: Vec::new(),
            })
        })
    }
}

impl FigureAccess<'_> {
    fn prepare(&mut self, py: Python<'_>) -> PyResult<String> {
        let report = py.detach(|| {
            let start = std::time::Instant::now();
            if self.data.radial.is_some() {
                let _ = self.render(1.)?;
                return Ok(json!({"backend":"native", "ready":true, "elapsed_ms":start.elapsed().as_secs_f64()*1000.,
                    "target_format":"Rgba8Unorm", "stages":[{"scope":"radial", "stage":"first-frame", "phase":"Ready"}],
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
        if self.data.radial.is_some() {
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
        let preserve_x = old.config.bottom_x.range_locked;
        let preserve_y = old.config.left_y.range_locked;
        let revision = self.data.revision;
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
                let mut next = self.data.chart.config().clone();
                if preserve_x {
                    next.bottom_x = old.config.bottom_x.clone();
                    next.top_x = old.config.top_x.clone();
                }
                if preserve_y {
                    next.left_y = old.config.left_y.clone();
                    next.right_y = old.config.right_y.clone();
                }
                self.commit_config(next)?;
            }
            validate_config(self.data.chart.config())?;
            Ok(())
        })();
        if let Err(error) = result {
            self.renderer
                .set_chart_series(
                    self.data.chart_id,
                    gpu::series(self.data.figure_id, &old.series),
                )
                .map_err(runtime)?;
            self.renderer
                .set_chart_config(
                    self.data.chart_id,
                    gpu::config(self.data.figure_id, &old.config),
                )
                .map_err(runtime)?;
            self.data.chart = Chart::new(old.config);
            self.data.series = old.series;
            self.data.revision = revision;
            return Err(error);
        }
        self.data.revision = revision + 1;
        Ok(())
    }
    fn apply_settings(&mut self, json: &str) -> PyResult<()> {
        let mut next: Settings = parse(json)?;
        if next.schema_version != 1 || next.renderer_version != RENDERER_VERSION {
            return Err(invalid("unsupported settings/renderer version"));
        }
        validate_config(&next.config)?;
        validate_background(next.background)?;
        validate_draw_style(&next.config, &next.series)?;
        if next.radial.is_some() != self.data.radial.is_some() {
            return Err(invalid("settings cannot change the Figure's chart family"));
        }
        if let Some(radial) = &next.radial {
            if !matches!(next.config.draw_style, renderer::config::DrawStyle::Precise) {
                return Err(invalid(
                    "pie/donut charts use radial materials, not Cartesian draw styles",
                ));
            }
            radial::validate(radial, next.config.chart_area.0)?;
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
        if series_changed {
            renderer::legend::update_legend_symbols_preserving_text(
                &mut next.config.legend.content,
                &next.series,
            );
        }
        let radial_changed = next.radial.as_ref() != self.data.radial.as_ref().map(|r| &r.chart);
        if next.config == *self.data.chart.config()
            && !series_changed
            && !radial_changed
            && next.background == self.data.background
        {
            return Ok(());
        }
        if series_changed {
            self.renderer
                .set_chart_series(
                    self.data.chart_id,
                    gpu::series(self.data.figure_id, &next.series),
                )
                .map_err(invalid)?;
        }
        if let Err(e) = self.renderer.set_chart_config(
            self.data.chart_id,
            gpu::config(self.data.figure_id, &next.config),
        ) {
            if series_changed {
                self.renderer
                    .set_chart_series(self.data.chart_id, gpu::series(self.data.figure_id, &old))
                    .map_err(runtime)?;
            }
            return Err(invalid(e));
        }
        self.data.chart = Chart::new(next.config);
        self.data.series = next.series;
        self.data.background = next.background;
        if let Some(chart) = next.radial {
            self.data.radial.as_mut().unwrap().chart = chart;
        }
        self.data.revision += 1;
        Ok(())
    }
    fn fit(&mut self, py: Python<'_>, padding: f64) -> PyResult<()> {
        if !padding.is_finite() || padding < 0.0 {
            return Err(invalid("padding must be finite and non-negative"));
        }
        py.detach(|| {
            pollster::block_on(self.renderer.ensure_errorbar_extent_engine()).map_err(runtime)?;
            let token = self
                .renderer
                .begin_fit_commit(self.data.chart_id)
                .map_err(runtime)?;
            let mut x = renderer::chart::FitExtent::EMPTY;
            let mut y = renderer::chart::FitExtent::EMPTY;
            let mut jobs = Vec::new();
            for series in &gpu::series(self.data.figure_id, &self.data.series) {
                if let Some(job) = self
                    .renderer
                    .begin_series_fit_extent(series)
                    .map_err(runtime)?
                {
                    jobs.push(job);
                }
                if let renderer::DataRenderType::Histogram { bar } = &series.render_type {
                    let mut a = Chart::slot_extent(self.renderer.pool(), &series.x_column)
                        .map_err(runtime)?;
                    let mut b = Chart::slot_extent(self.renderer.pool(), &series.y_column)
                        .map_err(runtime)?;
                    let base = renderer::chart::FitExtent {
                        min: bar.baseline,
                        max: bar.baseline,
                        min_positive: (bar.baseline > 0.0).then_some(bar.baseline),
                    };
                    if matches!(
                        bar.orientation,
                        renderer::data_config::BarOrientation::Vertical
                    ) {
                        b.union(&base);
                    } else {
                        a.union(&base);
                    }
                    x.union(&a);
                    y.union(&b);
                }
            }
            self.renderer.wait_idle();
            for job in jobs {
                if let Some(ext) = pollster::block_on(job.resolve()).map_err(runtime)? {
                    x.union(&renderer::chart::FitExtent {
                        min: ext.x.min,
                        max: ext.x.max,
                        min_positive: ext.x.min_positive,
                    });
                    y.union(&renderer::chart::FitExtent {
                        min: ext.y.min,
                        max: ext.y.max,
                        min_positive: ext.y.min_positive,
                    });
                }
            }
            self.renderer
                .commit_auto_fit_all_if_current(&token, &x, &y, padding)
                .map_err(runtime)
        })?;
        let mut next = self
            .renderer
            .chart_config(self.data.chart_id)
            .map_err(runtime)?
            .clone();
        if let Err(error) = validate_config(&next) {
            self.renderer
                .set_chart_config(
                    self.data.chart_id,
                    gpu::config(self.data.figure_id, self.data.chart.config()),
                )
                .map_err(runtime)?;
            return Err(error);
        }
        // An explicit fit fits every axis (renderer contract), so no range is
        // host-fixed afterwards. add_series_fitted restores the fixed ones.
        clear_range_fixed(&mut next);
        // Fitting changes axes only; keep the local document's selection ids.
        next.picked_data = self.data.chart.config().picked_data.clone();
        next.picked_points = self.data.chart.config().picked_points.clone();
        self.data.chart = Chart::new(next);
        self.data.revision += 1;
        Ok(())
    }
    fn set_range(&mut self, axis: &str, min: f64, max: f64) -> PyResult<()> {
        if !min.is_finite() || !max.is_finite() || min >= max {
            return Err(invalid("range must be finite and increasing"));
        }
        let mut next = Chart::new(self.data.chart.config().clone());
        match axis {
            "x" => next.set_x_range(min, max),
            "y" => next.set_y_range(min, max),
            _ => return Err(invalid("axis must be x or y")),
        }
        let mut config = next.config().clone();
        mark_range_fixed(&mut config, axis);
        self.commit_config(config)
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
    fn hit_test(&self, x: f32, y: f32) -> Option<String> {
        self.data
            .hitmap
            .hit_test(
                self.data.chart.config(),
                &CpuTextMeasure::for_style(&self.data.chart.config().draw_style),
                x,
                y,
            )
            .and_then(|id| self.data.hitmap.get(id))
            .map(|el| el.element_id())
    }
    fn bounds_json(&self, target: &str) -> PyResult<String> {
        let id = self.element(target)?;
        let measure = CpuTextMeasure::for_style(&self.data.chart.config().draw_style);
        let value = self.data.hitmap.selection_box(id, self.data.chart.config(), &measure).map(|b| json!({
            "rect": [b.rect.x, b.rect.y, b.rect.width, b.rect.height],
            "handles": b.handles.iter().map(|r| vec![r.x, r.y, r.width, r.height]).collect::<Vec<_>>()
        }));
        serde_json::to_string(&value).map_err(runtime)
    }
    fn resize_handle(&self, target: &str, x: f32, y: f32) -> PyResult<Option<String>> {
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
        if self.data.radial.is_some() {
            return py.detach(|| self.pick_radial(x, y));
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
        if let Some(radial) = self.data.radial.as_mut() {
            if radial.chart.interaction.selected.take().is_some() {
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
            "known_gpu_bytes": self.renderer.gpu_memory_usage().total_bytes() + host_bytes + self.data.radial.as_ref().map_or(0, |r| r.gpu_bytes()), "allocation_mode": if self.data.radial.is_some() { "bounded" } else { "resident" }, "preparation": self.data.preparation}).to_string()
    }
}

mod desktop;
mod editor;
mod gpu;
mod notebook;
mod radial;
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
    fn apply_settings(&self, json: &str) -> PyResult<()> {
        self.with(|core| core.apply_settings(json))
    }
    fn set_radial(&self, json: &str) -> PyResult<()> {
        self.with(|core| core.set_radial(json))
    }
    fn fit(&self, py: Python<'_>, padding: f64) -> PyResult<()> {
        self.with(|core| core.fit(py, padding))
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
        self.with(|core| Ok(core.hit_test(x, y)))
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
    m.add_function(wrap_pyfunction!(radial::default_radial_json, m)?)?;
    m.add_function(wrap_pyfunction!(draw_style_specs_json, m)?)?;
    m.add_function(wrap_pyfunction!(font_family_available, m)?)?;
    m.add_function(wrap_pyfunction!(text_segments_json, m)?)?;
    m.add_function(wrap_pyfunction!(segments_plain_text, m)?)?;
    m.add_function(wrap_pyfunction!(fitted_chart_title_margin, m)?)?;
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
    use renderer::text::{RichSegment, rich_segments_from_text};
    use std::sync::OnceLock;
    let segments: Vec<RichSegment> = parse(json)?;
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
    Ok((rich_segments_from_text(&text) == segments).then_some(text))
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
fn default_colorbar_json() -> PyResult<String> {
    serde_json::to_string(&default::default_colorbar_options()).map_err(runtime)
}

#[pyfunction]
fn rebuild_legend_json(series: &str, rich: &str) -> PyResult<String> {
    let series: Vec<SeriesConfig> = parse(series)?;
    let mut rich: renderer::text::RichText = parse(rich)?;
    rich.segments.clear();
    for spec in series {
        if let Some(label) = &spec.label {
            renderer::legend::append_legend_entry_rich(
                &mut rich,
                renderer::legend::series_symbol_segments(&spec),
                label.segments.clone(),
            );
        }
    }
    serde_json::to_string(&rich).map_err(runtime)
}
