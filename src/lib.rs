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

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Settings {
    schema_version: u32,
    renderer_version: String,
    config: Config,
    series: Vec<SeriesConfig>,
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
    instance: wgpu::Instance,
    adapter: wgpu::Adapter,
    renderer: Renderer,
    chart: Chart,
    chart_id: ChartId,
    series: Vec<SeriesConfig>,
    hitmap: HitMap,
    elements: Vec<(String, HitId)>,
    columns: HashMap<String, (usize, f64, f64)>,
    adapter_info: Value,
    revision: u64,
    uploads: u64,
    readbacks: u64,
    png_encodes: u64,
    target: Option<RenderTarget>,
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
}

impl FigureCore {
    fn render(&mut self, scale: f32) -> PyResult<renderer::RasterImage> {
        self.readbacks += 1;
        let device = Arc::clone(self.renderer.device());
        let oom = device.push_error_scope(wgpu::ErrorFilter::OutOfMemory);
        let validation = device.push_error_scope(wgpu::ErrorFilter::Validation);
        let rendered = self.render_inner(scale);
        self.renderer.wait_idle();
        let validation = pollster::block_on(validation.pop());
        let oom = pollster::block_on(oom.pop());
        if let Some(error) = oom {
            self.target = None;
            return Err(PyMemoryError::new_err(format!(
                "render allocation failed on {}: {error}",
                self.adapter_info["name"]
            )));
        }
        if let Some(error) = validation {
            self.target = None;
            return Err(runtime(format!(
                "GPU render failed on {}: {error}",
                self.adapter_info["name"]
            )));
        }
        if rendered.is_err() {
            self.target = None;
        }
        rendered
    }
    fn render_inner(&mut self, scale: f32) -> PyResult<renderer::RasterImage> {
        self.renderer
            .ensure_target_format(wgpu::TextureFormat::Rgba8Unorm)
            .map_err(runtime)?;
        if scale != 1.0 {
            return pollster::block_on(self.renderer.export_panel_rgba_with_clear_async(
                &self.chart,
                &self.series,
                scale,
                Color::WHITE,
            ))
            .map_err(runtime);
        }
        let rect = self.chart.config().chart_area.0;
        if self
            .target
            .as_ref()
            .is_none_or(|t| t.width != rect.width || t.height != rect.height)
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
                .create_chart_view(&self.chart, rect)
                .map_err(runtime)?;
            self.target = Some(RenderTarget {
                width: rect.width,
                height: rect.height,
                row_bytes,
                revision: self.revision,
                texture,
                view,
                readback,
            });
        }
        let target = self.target.as_mut().unwrap();
        if target.revision != self.revision {
            self.renderer
                .refresh_axis(&mut target.view, &self.chart, rect)
                .map_err(runtime)?;
            target.revision = self.revision;
        }
        let prepared = self
            .renderer
            .prepare_registered(&[renderer::RegisteredChartDrawItem {
                chart_id: self.chart_id,
                view: &target.view,
            }])
            .map_err(runtime)?;
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
                        load: wgpu::LoadOp::Clear(wgpu::Color::WHITE),
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
        if self.columns.contains_key(id) {
            return Err(invalid(format!("column already exists: {id}")));
        }
        if values.is_empty() {
            return Err(invalid("data must contain at least one value"));
        }
        let (mut min, mut max) = (f64::INFINITY, f64::NEG_INFINITY);
        for v in values {
            let v = v.f64();
            if v.is_finite() {
                min = min.min(v);
                max = max.max(v);
            }
        }
        if !min.is_finite() {
            return Err(invalid("data has no finite values"));
        }
        let source = BorrowedColumn { values, min, max };
        if let Err(error) = self.renderer.add_hilo_column(id.to_owned(), &source) {
            let message = format!(
                "upload failed: column={id:?}, values={}, requested_gpu_bytes={}, pool_used_bytes={}, pool_capacity_bytes={}, adapter_column_pool_limit_bytes={}, adapter={}; {error}",
                values.len(),
                (values.len() as u64).saturating_mul(8),
                self.renderer.pool().used_bytes(),
                self.renderer.pool().capacity(),
                self.adapter_info["maximum_column_pool_bytes"],
                self.adapter_info["name"]
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
        self.columns.insert(id.to_owned(), (values.len(), min, max));
        self.uploads += 1;
        Ok(())
    }
    fn element(&self, target: &str) -> PyResult<HitId> {
        self.elements
            .iter()
            .find(|(name, _)| name == target)
            .map(|(_, id)| *id)
            .ok_or_else(|| invalid(format!("unknown decoration: {target}")))
    }
    fn commit_config(&mut self, config: Config) -> PyResult<()> {
        validate_config(&config)?;
        self.renderer
            .set_chart_config(self.chart_id, config.clone())
            .map_err(invalid)?;
        self.chart = Chart::new(config);
        self.revision += 1;
        Ok(())
    }
    fn snapshot(&self) -> Settings {
        Settings {
            schema_version: 1,
            renderer_version: "0.16.1".into(),
            config: self.chart.config().clone(),
            series: self.series.clone(),
        }
    }
}

fn validate_config(config: &Config) -> PyResult<()> {
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
    ] {
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
        if matches!(axis.scale, renderer::config::AxisScale::Logarithmic) && axis.min <= 0.0 {
            return Err(invalid("logarithmic axes require positive bounds"));
        }
    }
    config
        .data_area()
        .map_err(|e| invalid(format!("invalid layout: {e:?}")))?;
    Ok(())
}

impl FigureCore {
    fn new(py: Python<'_>, width: u32, height: u32, pool_bytes: u64) -> PyResult<Self> {
        py.detach(move || {
            let instance = create_instance();
            let adapter = request_adapter(&instance).map_err(runtime)?;
            let info = adapter.get_info();
            let available = adapter.limits();
            let mut limits = wgpu::Limits::default();
            limits.max_storage_buffer_binding_size = available.max_storage_buffer_binding_size;
            limits.max_buffer_size = available.max_buffer_size;
            let capacity = pool_bytes.min(available.max_storage_buffer_binding_size as u64);
            let (device, queue) =
                pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
                    label: Some("figgy Python device"),
                    required_limits: limits,
                    ..Default::default()
                }))
                .map_err(runtime)?;
            let mut renderer = Renderer::try_new(
                RendererDevice::new(Arc::new(device), Arc::new(queue)),
                wgpu::TextureFormat::Rgba8Unorm,
                capacity,
            )
            .map_err(runtime)?;
            renderer.set_pool_growth_policy(renderer::GrowthPolicy::OnAllocFailure);
            let _ = renderer.set_memory_budget(None);
            let mut config = default::default_config();
            config.chart_area = ChartArea(Rect {
                x: 0,
                y: 0,
                width,
                height,
            });
            config.legend.visible = false;
            config.left_y.out_margin = 65.0;
            config.right_y.out_margin = 25.0;
            config.bottom_x.out_margin = 55.0;
            config.top_x.out_margin = 25.0;
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
                instance,
                adapter,
                renderer,
                chart,
                chart_id,
                series: Vec::new(),
                hitmap,
                elements,
                columns: HashMap::new(),
                adapter_info: json!({"name": info.name, "backend": format!("{:?}", info.backend),
                    "device_type": format!("{:?}", info.device_type), "driver": info.driver,
                    "initial_pool_capacity_bytes": capacity, "maximum_column_pool_bytes": available.max_storage_buffer_binding_size}),
                revision: 0,
                uploads: 0,
                readbacks: 0,
                png_encodes: 0,
                target: None,
            })
        })
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
        self.renderer.remove_column(id).map_err(runtime)?;
        self.columns.remove(id);
        Ok(())
    }
    fn settings_json(&self) -> PyResult<String> {
        serde_json::to_string(&self.snapshot()).map_err(runtime)
    }
    fn add_series(&mut self, json: &str) -> PyResult<()> {
        let cfg: SeriesConfig = parse(json)?;
        if self.series.iter().any(|s| s.series_id == cfg.series_id) {
            return Err(invalid("series IDs must be unique"));
        }
        let mut next = self.series.clone();
        next.push(cfg);
        self.renderer
            .set_chart_series(self.chart_id, next.clone())
            .map_err(invalid)?;
        self.series = next;
        self.revision += 1;
        Ok(())
    }
    fn apply_settings(&mut self, json: &str) -> PyResult<()> {
        let mut next: Settings = parse(json)?;
        if next.schema_version != 1 || next.renderer_version != "0.16.1" {
            return Err(invalid("unsupported settings/renderer version"));
        }
        validate_config(&next.config)?;
        // Settings cannot introduce, remove or silently reconnect source arrays.
        if next.series.len() != self.series.len()
            || next.series.iter().zip(&self.series).any(|(a, b)| {
                a.series_id != b.series_id || a.x_column != b.x_column || a.y_column != b.y_column
            })
        {
            return Err(invalid(
                "settings must address the same ordered series and source columns",
            ));
        }
        let old = self.series.clone();
        let series_changed = next.series != old;
        if series_changed {
            renderer::legend::update_legend_symbols_preserving_text(
                &mut next.config.legend.content,
                &next.series,
            );
        }
        if next.config == *self.chart.config() && !series_changed {
            return Ok(());
        }
        if series_changed {
            self.renderer
                .set_chart_series(self.chart_id, next.series.clone())
                .map_err(invalid)?;
        }
        if let Err(e) = self
            .renderer
            .set_chart_config(self.chart_id, next.config.clone())
        {
            if series_changed {
                self.renderer
                    .set_chart_series(self.chart_id, old)
                    .map_err(runtime)?;
            }
            return Err(invalid(e));
        }
        self.chart = Chart::new(next.config);
        self.series = next.series;
        self.revision += 1;
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
                .begin_fit_commit(self.chart_id)
                .map_err(runtime)?;
            let mut x = renderer::chart::FitExtent::EMPTY;
            let mut y = renderer::chart::FitExtent::EMPTY;
            let mut jobs = Vec::new();
            for series in &self.series {
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
        self.chart = Chart::new(
            self.renderer
                .chart_config(self.chart_id)
                .map_err(runtime)?
                .clone(),
        );
        self.revision += 1;
        Ok(())
    }
    fn set_range(&mut self, axis: &str, min: f64, max: f64) -> PyResult<()> {
        if !min.is_finite() || !max.is_finite() || min >= max {
            return Err(invalid("range must be finite and increasing"));
        }
        let mut next = Chart::new(self.chart.config().clone());
        match axis {
            "x" => next.set_x_range(min, max),
            "y" => next.set_y_range(min, max),
            _ => return Err(invalid("axis must be x or y")),
        }
        self.commit_config(next.config().clone())
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
        self.png_encodes += 1;
        let bytes = py.detach(|| {
            let image = self.render(scale)?;
            encode_png(&image).map_err(runtime)
        })?;
        Ok(PyBytes::new(py, &bytes))
    }
    fn hit_test(&self, x: f32, y: f32) -> Option<String> {
        self.hitmap
            .hit_test(
                self.chart.config(),
                &CpuTextMeasure::for_style(&self.chart.config().draw_style),
                x,
                y,
            )
            .and_then(|id| self.hitmap.get(id))
            .map(|el| el.element_id())
    }
    fn bounds_json(&self, target: &str) -> PyResult<String> {
        let id = self.element(target)?;
        let measure = CpuTextMeasure::for_style(&self.chart.config().draw_style);
        let value = self.hitmap.selection_box(id, self.chart.config(), &measure).map(|b| json!({
            "rect": [b.rect.x, b.rect.y, b.rect.width, b.rect.height],
            "handles": b.handles.iter().map(|r| vec![r.x, r.y, r.width, r.height]).collect::<Vec<_>>()
        }));
        serde_json::to_string(&value).map_err(runtime)
    }
    fn resize_handle(&self, target: &str, x: f32, y: f32) -> PyResult<Option<String>> {
        let id = self.element(target)?;
        Ok(self
            .hitmap
            .get(id)
            .and_then(|e| e.as_resizable())
            .and_then(|e| {
                e.hit_resize_handle(
                    self.chart.config(),
                    &CpuTextMeasure::for_style(&self.chart.config().draw_style),
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
        let el = self.hitmap.get(id).unwrap();
        let mut cfg = self.chart.config().clone();
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
        let picked = py.detach(|| {
            self.renderer.enable_gpu_picking().map_err(runtime)?;
            let request = GpuPickRequest {
                canvas_position_px: [x, y],
                display_panel_px: self.chart.config().chart_area.0,
                display_scale: 1.0,
                max_distance_px: 6.0,
            };
            let ticket = self
                .renderer
                .pick_chart_data(self.chart_id, request)
                .map_err(runtime)?;
            self.renderer.wait_idle();
            pollster::block_on(ticket.resolve()).map_err(runtime)
        })?;
        let mut cfg = self.chart.config().clone();
        cfg.picked_data = picked
            .as_ref()
            .map(|p| renderer::config::DataSelectionsConfig {
                refs: vec![p.to_ref()],
                ..Default::default()
            });
        if cfg != *self.chart.config() {
            self.commit_config(cfg)?;
        }
        let value = picked.map(|p| json!({"target": p.series_id(), "distance_px": p.distance_px(), "identity": p.to_ref()}));
        serde_json::to_string(&value).map_err(runtime)
    }
    fn clear_data_selection(&mut self) -> PyResult<()> {
        let mut cfg = self.chart.config().clone();
        if cfg.picked_data.is_some() {
            cfg.picked_data = None;
            self.commit_config(cfg)?;
        }
        Ok(())
    }
    fn info_json(&self) -> String {
        let host_bytes = self.target.as_ref().map_or(0, |t| {
            u64::from(t.width) * u64::from(t.height) * 4
                + u64::from(t.row_bytes) * u64::from(t.height)
        });
        json!({"adapter": self.adapter_info, "revision": self.revision, "column_uploads": self.uploads, "rgba_readbacks": self.readbacks, "png_encodes": self.png_encodes, "columns": self.columns.len(),
            "pool_capacity_bytes": self.renderer.pool().capacity(), "pool_used_bytes": self.renderer.pool().used_bytes(),
            "known_gpu_bytes": self.renderer.gpu_memory_usage().total_bytes() + host_bytes, "allocation_mode": "resident"}).to_string()
    }
}

mod desktop;
mod notebook;

#[pyclass(module = "figgy._native")]
struct NativeFigure {
    core: Arc<Mutex<FigureCore>>,
}

impl NativeFigure {
    fn lock(&self) -> PyResult<std::sync::MutexGuard<'_, FigureCore>> {
        Python::attach(|py| self.core.lock_py_attached(py))
            .map_err(|_| runtime("native Figure lock poisoned"))
    }
}
#[pymethods]
impl NativeFigure {
    #[new]
    #[pyo3(signature=(width=960, height=600, pool_bytes=8388608))]
    fn new(py: Python<'_>, width: u32, height: u32, pool_bytes: u64) -> PyResult<Self> {
        Ok(Self {
            core: Arc::new(Mutex::new(FigureCore::new(py, width, height, pool_bytes)?)),
        })
    }
    fn upload_column(&self, id: &str, array: &Bound<'_, PyAny>) -> PyResult<()> {
        self.lock()?.upload_column(id, array)
    }
    fn remove_column(&self, id: &str) -> PyResult<()> {
        self.lock()?.remove_column(id)
    }
    fn settings_json(&self) -> PyResult<String> {
        self.lock()?.settings_json()
    }
    fn add_series(&self, json: &str) -> PyResult<()> {
        self.lock()?.add_series(json)
    }
    fn apply_settings(&self, json: &str) -> PyResult<()> {
        self.lock()?.apply_settings(json)
    }
    fn fit(&self, py: Python<'_>, padding: f64) -> PyResult<()> {
        self.lock()?.fit(py, padding)
    }
    fn set_range(&self, axis: &str, min: f64, max: f64) -> PyResult<()> {
        self.lock()?.set_range(axis, min, max)
    }
    fn bounds_json(&self, target: &str) -> PyResult<String> {
        self.lock()?.bounds_json(target)
    }
    fn resize_handle(&self, target: &str, x: f32, y: f32) -> PyResult<Option<String>> {
        self.lock()?.resize_handle(target, x, y)
    }
    #[pyo3(signature=(target, dx, dy, handle=None))]
    fn drag(&self, target: &str, dx: f32, dy: f32, handle: Option<&str>) -> PyResult<bool> {
        self.lock()?.drag(target, dx, dy, handle)
    }
    fn pick_json(&self, py: Python<'_>, x: f32, y: f32) -> PyResult<String> {
        self.lock()?.pick_json(py, x, y)
    }
    fn clear_data_selection(&self) -> PyResult<()> {
        self.lock()?.clear_data_selection()
    }
    #[pyo3(signature=(scale=1.0))]
    fn render_rgba<'py>(
        &self,
        py: Python<'py>,
        scale: f32,
    ) -> PyResult<(u32, u32, Bound<'py, PyBytes>)> {
        self.lock()?.render_rgba(py, scale)
    }
    #[pyo3(signature=(scale=1.0))]
    fn render_png<'py>(&self, py: Python<'py>, scale: f32) -> PyResult<Bound<'py, PyBytes>> {
        self.lock()?.render_png(py, scale)
    }
    fn hit_test(&self, x: f32, y: f32) -> PyResult<Option<String>> {
        Ok(self.lock()?.hit_test(x, y))
    }
    fn info_json(&self) -> PyResult<String> {
        Ok(self.lock()?.info_json())
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

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NativeFigure>()?;
    m.add_class::<notebook::NotebookFigure>()?;
    m.add_class::<desktop::WindowHandle>()?;
    m.add_function(wrap_pyfunction!(desktop::poll_events, m)?)?;
    m.add_function(wrap_pyfunction!(desktop::run_events, m)?)?;
    m.add_function(wrap_pyfunction!(default_colorbar_json, m)?)?;
    m.add_function(wrap_pyfunction!(rebuild_legend_json, m)?)?;
    Ok(())
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
