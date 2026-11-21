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
    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        apply_limit_buckets: false,
        ..Default::default()
    }))
    .map_err(runtime)?;
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
        RendererDevice::new(device, queue).map_err(runtime)?,
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
                    remove_resource(renderer, id).map_err(runtime)?;
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
            renderer.wait_idle().map_err(runtime)?;
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
        | R::ContourLevel { series_id, .. }
        | R::ValueLabel { series_id, .. }
        | R::MeshTriangle { series_id, .. }
        | R::FeynmanVertex { series_id, .. }
        | R::FeynmanPropagator { series_id, .. }
        | R::FeynmanLabel { series_id, .. } => series_id,
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
    if let Some(offsets) = &mut result.line_offsets {
        for id in &mut offsets.series {
            *id = column_id(figure, id);
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
    result
}

/// Namespace series and source IDs at the GPU boundary.
pub fn series(figure: u64, input: &[SeriesConfig]) -> Vec<SeriesConfig> {
    fn remap(
        value: &mut Value,
        columns: &std::collections::HashSet<String>,
        figure: u64,
        key: &str,
    ) {
        match value {
            Value::String(id) if key == "series_id" => *id = column_id(figure, id),
            Value::String(id)
                if columns.contains(id)
                    && !matches!(
                        key,
                        "text" | "label" | "font" | "group" | "source_id" | "series_id"
                    ) =>
            {
                *id = column_id(figure, id)
            }
            Value::Array(items) => {
                for item in items {
                    remap(item, columns, figure, key);
                }
            }
            Value::Object(items) => {
                for (key, item) in items {
                    remap(item, columns, figure, key);
                }
            }
            _ => {}
        }
    }
    input
        .iter()
        .map(|s| {
            let mut columns = std::collections::HashSet::new();
            s.visit_columns(&mut |id| {
                columns.insert(id.to_owned());
            });
            s.visit_composite_columns(&mut |id| {
                columns.insert(id.to_owned());
            });
            let mut value = serde_json::to_value(s).expect("valid series model");
            remap(&mut value, &columns, figure, "");
            value["series_id"] = json!(column_id(figure, &s.series_id));
            if let Some(links) = s.render_type.range_links() {
                value["render_type"]["RangeLinks"]["bars"] = json!(column_id(figure, &links.bars));
            }
            if let Some(line) = value["render_type"]
                .as_object_mut()
                .and_then(|v| v.values_mut().next())
                .and_then(|v| v.get_mut("line"))
            {
                if let Some(id) = line["fill"]["ToSeries"].as_str().map(str::to_owned) {
                    line["fill"]["ToSeries"] = json!(column_id(figure, &id));
                }
            }
            serde_json::from_value(value).expect("namespaced series model")
        })
        .collect()
}

pub fn local_config(figure: u64, input: &Config) -> Config {
    let mut result = input.clone();
    let prefix = format!("figgy/{figure}/");
    if let Some(offsets) = &mut result.line_offsets {
        for id in &mut offsets.series {
            if let Some(local) = id.strip_prefix(&prefix) {
                *id = local.to_owned();
            }
        }
    }
    if let Some(p) = &mut result.picked_data {
        for r in &mut p.refs {
            local_selection(figure, r);
        }
    }
    for o in &mut result.overlays {
        for id in &mut o.series {
            if let Some(v) = id.strip_prefix(&prefix) {
                *id = v.into();
            }
        }
    }
    for p in &mut result.subplots {
        for id in &mut p.series {
            if let Some(v) = id.strip_prefix(&prefix) {
                *id = v.into();
            }
        }
        p.config = local_config(figure, &p.config);
    }
    result
}
pub fn remove_resource(renderer: &mut Renderer, id: &str) -> renderer::Result<bool> {
    if renderer.pool().record(id).is_some() {
        renderer.remove_record(id)
    } else if renderer.pool().ragged(id).is_some() {
        renderer.remove_ragged(id)
    } else if renderer.pool().triangles(id).is_some() {
        renderer.remove_triangles(id)
    } else {
        renderer.remove_column(id)
    }
}
