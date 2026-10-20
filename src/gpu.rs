//! One process-local native renderer. Figure documents retain their own ownership.
use super::*;
use std::sync::{
    MutexGuard, OnceLock,
    atomic::{AtomicU64, Ordering},
};

pub(crate) struct GpuContext {
    pub id: u64,
    pub instance: wgpu::Instance,
    pub adapter: wgpu::Adapter,
    pub adapter_info: Value,
    pub renderer: Mutex<Renderer>,
    pending: Mutex<Vec<(ChartId, Vec<String>)>>,
}

static CONTEXT: OnceLock<Mutex<Option<Arc<GpuContext>>>> = OnceLock::new();
static NEXT_CONTEXT: AtomicU64 = AtomicU64::new(1);
static NEXT_FIGURE: AtomicU64 = AtomicU64::new(1);

pub fn figure_id() -> PyResult<u64> {
    NEXT_FIGURE
        .try_update(Ordering::Relaxed, Ordering::Relaxed, |n| n.checked_add(1))
        .map_err(|_| runtime("native Figure id exhausted"))
}

pub fn context(pool_bytes: u64) -> PyResult<Arc<GpuContext>> {
    // Called detached from Python. Serialize first construction, including failure.
    let mut slot = CONTEXT
        .get_or_init(|| Mutex::new(None))
        .lock()
        .map_err(runtime)?;
    if let Some(context) = slot.as_ref() {
        return Ok(Arc::clone(context));
    }
    let instance = create_instance();
    let adapter = request_adapter(&instance).map_err(runtime)?;
    let info = adapter.get_info();
    let available = adapter.limits();
    let mut limits = wgpu::Limits::default();
    limits.max_storage_buffer_binding_size = available.max_storage_buffer_binding_size;
    limits.max_buffer_size = available.max_buffer_size;
    let capacity = pool_bytes.min(available.max_storage_buffer_binding_size as u64);
    let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
        label: Some("figgy shared Python device"),
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
    let id = NEXT_CONTEXT
        .try_update(Ordering::Relaxed, Ordering::Relaxed, |n| n.checked_add(1))
        .map_err(|_| runtime("native GPU context id exhausted"))?;
    let context = Arc::new(GpuContext {
        id,
        instance,
        adapter,
        renderer: Mutex::new(renderer),
        pending: Mutex::new(Vec::new()),
        adapter_info: json!({"name":info.name,"backend":format!("{:?}",info.backend),
            "device_type":format!("{:?}",info.device_type),"driver":info.driver,
            "initial_pool_capacity_bytes":capacity,"maximum_column_pool_bytes":available.max_storage_buffer_binding_size}),
    });
    *slot = Some(Arc::clone(&context));
    Ok(context)
}

impl GpuContext {
    pub fn retire(&self, chart: ChartId, columns: Vec<String>) {
        self.pending
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push((chart, columns));
    }
    fn drain(&self, renderer: &mut Renderer) -> PyResult<()> {
        let retired = std::mem::take(&mut *self.pending.lock().map_err(runtime)?);
        let mut jobs = retired.into_iter();
        while let Some((chart, columns)) = jobs.next() {
            let removed = (|| {
                if renderer.chart_order().contains(&chart) {
                    renderer.remove_chart(chart).map_err(runtime)?;
                }
                for id in &columns {
                    renderer.remove_column(id).map_err(runtime)?;
                }
                Ok(())
            })();
            if let Err(error) = removed {
                let mut pending = self.pending.lock().map_err(runtime)?;
                pending.push((chart, columns));
                pending.extend(jobs);
                return Err(error);
            }
        }
        Ok(())
    }
}

pub fn lock(context: &GpuContext) -> PyResult<MutexGuard<'_, Renderer>> {
    let mut renderer = Python::attach(|py| context.renderer.lock_py_attached(py))
        .map_err(|_| runtime("shared GPU renderer lock poisoned"))?;
    context.drain(&mut renderer)?;
    Ok(renderer)
}

#[pyfunction]
pub fn collect_gpu(py: Python<'_>) -> PyResult<()> {
    py.detach(|| {
        let context = CONTEXT
            .get_or_init(|| Mutex::new(None))
            .lock()
            .map_err(runtime)?
            .clone();
        if let Some(context) = context {
            let mut renderer = context.renderer.lock().map_err(runtime)?;
            context.drain(&mut renderer)?;
            renderer.end_gpu_frame();
        }
        Ok(())
    })
}

#[pyfunction]
pub fn release_gpu(py: Python<'_>) -> PyResult<bool> {
    py.detach(|| {
        let mut slot = CONTEXT
            .get_or_init(|| Mutex::new(None))
            .lock()
            .map_err(runtime)?;
        let Some(context) = slot.as_ref() else {
            return Ok(false);
        };
        // Reservations during Figure construction count too: reset cannot race
        // a constructor and publish two process-wide contexts.
        if Arc::strong_count(context) != 1 {
            return Err(runtime("close all native Figures before release_gpu()"));
        }
        {
            let mut renderer = context.renderer.lock().map_err(runtime)?;
            context.drain(&mut renderer)?;
            renderer.wait_idle();
        }
        *slot = None;
        Ok(true)
    })
}

pub fn column_id(figure: u64, local: &str) -> String {
    format!("figgy/{figure}/{local}")
}

fn selection_series(reference: &mut renderer::config::PickedDataRef) -> &mut String {
    use renderer::config::PickedDataRef as R;
    match reference {
        R::Point { series_id, .. }
        | R::HistogramBin { series_id, .. }
        | R::MatrixCell { series_id, .. }
        | R::ContourLevel { series_id, .. } => series_id,
    }
}

pub fn local_selection(figure: u64, reference: &mut renderer::config::PickedDataRef) {
    let id = selection_series(reference);
    if let Some(local) = id.strip_prefix(&format!("figgy/{figure}/")) {
        *id = local.to_owned();
    }
}

pub fn config(figure: u64, input: &Config) -> Config {
    let mut result = input.clone();
    if let Some(points) = &mut result.picked_points {
        for reference in &mut points.refs {
            reference.series_id = column_id(figure, &reference.series_id);
        }
    }
    if let Some(data) = &mut result.picked_data {
        for reference in &mut data.refs {
            let id = selection_series(reference);
            *id = column_id(figure, id);
        }
    }
    for overlay in &mut result.overlays {
        for id in &mut overlay.series {
            *id = column_id(figure, id);
        }
    }
    for subplot in &mut result.subplots {
        for id in &mut subplot.series {
            *id = column_id(figure, id);
        }
        subplot.config = config(figure, &subplot.config);
    }
    // Renderer 0.18's registry validates mapped series against the document
    // root before expansion. Subplots still draw with their own colorbars.
    // Supply an invisible validation context only at the GPU boundary; it
    // never becomes an additional authority in the persisted chart model.
    if result.colorbar.is_none() {
        if let Some(bar) = result
            .subplots
            .iter()
            .find_map(|p| p.config.colorbar.as_ref())
        {
            let mut bar = bar.clone();
            bar.visible = false;
            result.colorbar = Some(bar);
        }
    }
    result
}

/// Names and the derived registry validation context change at this boundary.
/// Public SSOT retains local ids and its own colorbars;
/// typed renderer models still own all validation, fitting and rendering.
pub fn series(figure: u64, input: &[SeriesConfig]) -> Vec<SeriesConfig> {
    use renderer::data_config::{
        DataErrorBarStyleConfig, DataRenderType as T, DataScatterStyleConfig, ErrorRef, LineFill,
        MatrixRef, VectorColorMap, VectorComponents,
    };
    fn scatter(figure: u64, style: &mut DataScatterStyleConfig) {
        if let Some(id) = &mut style.point_style_index_column {
            *id = column_id(figure, id);
        }
        if let Some(map) = &mut style.point_color_map {
            map.column = column_id(figure, &map.column);
        }
        if let Some(map) = &mut style.point_size_map {
            map.column = column_id(figure, &map.column);
        }
    }
    fn matrix(figure: u64, reference: &mut MatrixRef) {
        for id in &mut reference.columns {
            *id = column_id(figure, id);
        }
    }
    fn error(figure: u64, reference: &mut ErrorRef) {
        match reference {
            ErrorRef::Symmetric { column } => *column = column_id(figure, column),
            ErrorRef::Asymmetric { lower, upper } => {
                *lower = column_id(figure, lower);
                *upper = column_id(figure, upper);
            }
        }
    }
    fn error_style(figure: u64, style: &mut DataErrorBarStyleConfig) {
        if let Some(id) = &mut style.error_bar_style_index_column {
            *id = column_id(figure, id);
        }
    }
    let mut result = input.to_vec();
    for s in &mut result {
        // Renderer scratch caches are keyed by series id, not just chart id.
        s.series_id = column_id(figure, &s.series_id);
        s.x_column = column_id(figure, &s.x_column);
        s.y_column = column_id(figure, &s.y_column);
        if let T::Line { line }
        | T::ScatterLine { line, .. }
        | T::LineScatterErrorbarX { line, .. }
        | T::LineScatterErrorbarY { line, .. }
        | T::LineScatterErrorbarXY { line, .. } = &mut s.render_type
        {
            if let Some(LineFill::ToSeries(id)) = &mut line.fill {
                *id = column_id(figure, id);
            }
        }
        match &mut s.render_type {
            T::Line { .. } | T::Histogram { .. } => {}
            T::Scatter { scatter: style } | T::ScatterLine { scatter: style, .. } => {
                scatter(figure, style)
            }
            T::ScatterErrorbarX {
                scatter: style,
                err_x: err,
                err_style,
            }
            | T::ScatterErrorbarY {
                scatter: style,
                err_y: err,
                err_style,
            }
            | T::LineScatterErrorbarX {
                scatter: style,
                err_x: err,
                err_style,
                ..
            }
            | T::LineScatterErrorbarY {
                scatter: style,
                err_y: err,
                err_style,
                ..
            } => {
                scatter(figure, style);
                error(figure, err);
                error_style(figure, err_style);
            }
            T::ScatterErrorbarXY {
                scatter: style,
                err_x,
                err_y,
                err_style,
            }
            | T::LineScatterErrorbarXY {
                scatter: style,
                err_x,
                err_y,
                err_style,
                ..
            } => {
                scatter(figure, style);
                error(figure, err_x);
                error(figure, err_y);
                error_style(figure, err_style);
            }
            T::Heatmap { matrix: grid, .. }
            | T::Contour { matrix: grid, .. }
            | T::HeatmapContour { matrix: grid, .. } => matrix(figure, grid),
            T::Vector { components, style } => {
                match components {
                    VectorComponents::Points { u, v } => {
                        *u = column_id(figure, u);
                        *v = column_id(figure, v);
                    }
                    VectorComponents::Grid { u, v } => {
                        matrix(figure, u);
                        matrix(figure, v);
                    }
                }
                match &mut style.color_map {
                    Some(VectorColorMap::Column(id)) => *id = column_id(figure, id),
                    Some(VectorColorMap::Grid(grid)) => matrix(figure, grid),
                    None => {}
                }
            }
        }
    }
    result
}
