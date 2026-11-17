//! Host-owned panel focus and automatic routing of visible targets.
use super::*;
use renderer::LayerRef;

pub(super) fn panel_index(layer: LayerRef) -> usize {
    match layer {
        LayerRef::Subplot(i) | LayerRef::SubplotOverlay(i, _) => i + 1,
        _ => 0,
    }
}
pub(super) fn base_layer(index: usize) -> LayerRef {
    if index == 0 {
        LayerRef::Base
    } else {
        LayerRef::Subplot(index - 1)
    }
}
pub(super) fn panel(config: &Config, index: usize) -> &Config {
    if index == 0 {
        config
    } else {
        &config.subplots[index - 1].config
    }
}
pub(super) fn panel_id(identity: Option<&Value>, index: usize) -> String {
    identity
        .and_then(|v| v["panels"][index]["id"].as_str())
        .map(str::to_owned)
        .unwrap_or_else(|| format!("panel_{index}"))
}
pub(super) fn contains(rect: Rect, point: (f32, f32)) -> bool {
    point.0 >= rect.x as f32
        && point.1 >= rect.y as f32
        && point.0 < (rect.x + rect.width) as f32
        && point.1 < (rect.y + rect.height) as f32
}
pub(super) fn panel_label(config: &Config, identity: Option<&Value>, index: usize) -> String {
    let title: String = panel(config, index)
        .chart_title
        .text
        .segments
        .iter()
        .map(|s| s.text)
        .collect();
    if title.trim().is_empty() {
        panel_id(identity, index)
    } else {
        title
    }
}
#[derive(Default)]
pub(super) struct Focus {
    pub id: Option<String>,
    observed_layer: Option<LayerRef>,
}
impl Focus {
    pub fn index(&self, config: &Config, identity: Option<&Value>) -> Option<usize> {
        self.id
            .as_ref()
            .and_then(|id| (0..=config.subplots.len()).find(|&i| panel_id(identity, i) == *id))
    }
    pub fn select(&mut self, config: &Config, identity: Option<&Value>, index: Option<usize>) {
        self.id = index.map(|i| panel_id(identity, i));
        self.observed_layer = Some(config.active_layer());
    }
    pub fn sync(&mut self, config: &Config, identity: Option<&Value>, selected: bool) {
        if config.subplots.is_empty() {
            self.id = None;
        } else if selected
            || self
                .observed_layer
                .is_some_and(|old| old != config.active_layer())
        {
            self.id = Some(panel_id(identity, panel_index(config.active_layer())));
        } else if self.index(config, identity).is_none() {
            self.id = None;
        }
        self.observed_layer = Some(config.active_layer());
    }
}

/// Every distinct visible decoration under the pointer, with shared elements
/// deduplicated back to their panel owner.
pub(super) fn decorations_at(
    config: &Config,
    index: usize,
    point: (f32, f32),
) -> Vec<(LayerRef, String)> {
    let measure = CpuTextMeasure::for_style(&config.draw_style);
    let mut hits = vec![];
    for layer in config
        .panel_layers()
        .into_iter()
        .filter(|l| panel_index(*l) == index)
        .rev()
    {
        let mut probe = config.clone();
        probe.set_active_layer(layer);
        let map = HitMap::for_active_layer(&probe);
        if let Some(target) = map
            .hit_test(&probe, &measure, point.0, point.1)
            .and_then(|id| map.get(id))
            .map(|e| e.element_id())
        {
            let owner = if target.contains("overlay_") {
                layer
            } else {
                base_layer(index)
            };
            if !hits.iter().any(|(_, t)| *t == target) {
                hits.push((owner, target));
            }
        }
    }
    // A plot background behind a title or axis is not an ambiguous target.
    if hits.iter().any(|(_, t)| !t.ends_with("data_area")) {
        hits.retain(|(_, t)| !t.ends_with("data_area"));
    }
    hits
}
pub(super) fn panels_at(config: &Config, point: (f32, f32)) -> Vec<usize> {
    (0..=config.subplots.len())
        .rev()
        .filter(|&i| contains(panel(config, i).chart_area.0, point))
        .collect()
}
pub(super) fn overlapping_panels(config: &Config, index: usize) -> Vec<usize> {
    let a = panel(config, index).chart_area.0;
    (0..=config.subplots.len())
        .rev()
        .filter(|&i| {
            let b = panel(config, i).chart_area.0;
            a.x < b.x + b.width
                && b.x < a.x + a.width
                && a.y < b.y + b.height
                && b.y < a.y + a.height
        })
        .collect()
}
#[derive(Clone)]
pub(super) struct DataHit {
    pub layer: LayerRef,
    pub reference: renderer::config::PickedDataRef,
    pub distance: f32,
}
// Fills are not pick primitives. Removing them from a temporary picker registry
// keeps cross-series fills valid while already-found series are excluded.
fn picker_series(
    input: &[SeriesConfig],
    excluded: &std::collections::HashSet<String>,
) -> Vec<SeriesConfig> {
    use renderer::data_config::DataRenderType as T;
    input
        .iter()
        .filter(|s| !excluded.contains(&s.series_id))
        .cloned()
        .map(|mut s| {
            match &mut s.render_type {
                T::Xy(renderer::XySeries {
                    line: Some(line), ..
                }) => line.fill = None,
                _ => {}
            }
            s
        })
        .collect()
}
impl FigureAccess<'_> {
    /// Enumerate all nearby series, including coincident series on the same
    /// axis. Only renderer metadata and compact pick identities change. The
    /// authoritative document, columns, legend and order are restored exactly.
    pub(super) fn pick_panel_candidates(
        &mut self,
        index: usize,
        request: GpuPickRequest,
    ) -> PyResult<Vec<DataHit>> {
        self.renderer.enable_gpu_picking().map_err(runtime)?;
        let original = self.data.chart.config().clone();
        let original_gpu = gpu::config(self.data.figure_id, &original);
        let series = self.gpu_series(&self.data.series);
        let mut probe = original_gpu.clone();
        probe.picked_data = None;

        let result = (|| {
            self.renderer
                .set_chart_config(self.data.chart_id, probe)
                .map_err(runtime)?;
            let mut hits = vec![];
            let mut excluded = std::collections::HashSet::new();
            for layer in original
                .panel_layers()
                .into_iter()
                .filter(|l| panel_index(*l) == index)
                .rev()
            {
                self.renderer
                    .set_active_layer(self.data.chart_id, layer)
                    .map_err(runtime)?;
                loop {
                    let remaining = self
                        .renderer
                        .chart_series(self.data.chart_id)
                        .map_err(runtime)?;
                    if !remaining
                        .iter()
                        .any(|s| original_gpu.layer_of_series(&s.series_id) == layer)
                    {
                        break;
                    }
                    let ticket = self
                        .renderer
                        .pick_chart_data(self.data.chart_id, request)
                        .map_err(runtime)?;
                    self.renderer.wait_idle().map_err(runtime)?;
                    let Some(pick) = pollster::block_on(ticket.resolve()).map_err(runtime)? else {
                        break;
                    };
                    let mut reference = pick.to_ref();
                    if !excluded.insert(reference.series_id().to_owned()) {
                        return Err(runtime("picker repeated an excluded series"));
                    }
                    gpu::local_selection(self.data.figure_id, &mut reference);
                    hits.push(DataHit {
                        layer,
                        reference,
                        distance: pick.distance_px(),
                    });
                    self.renderer
                        .set_chart_series(self.data.chart_id, picker_series(&series, &excluded))
                        .map_err(runtime)?;
                }
            }
            hits.sort_by(|a, b| a.distance.total_cmp(&b.distance));
            Ok(hits)
        })();
        // Attempt both restorations even after a rejected probe.
        let restore_series = self
            .renderer
            .set_chart_series(self.data.chart_id, series)
            .map_err(runtime);
        let restore_config = self
            .renderer
            .set_chart_config(self.data.chart_id, original_gpu)
            .map_err(runtime);
        restore_series?;
        restore_config?;
        result
    }
}

impl FigureAccess<'_> {
    /// Route diagram gestures through the renderer model's public movement API.
    /// Only configuration is copied; source columns stay resident.
    pub(super) fn drag_selected_record(
        &mut self,
        reference: &renderer::config::PickedDataRef,
        dx: f32,
        dy: f32,
    ) -> PyResult<()> {
        use renderer::config::PickedDataRef as R;
        let id = reference.series_id();
        let mut next = self.snapshot();
        let Some(series) = next.series.iter_mut().find(|s| s.series_id == id) else {
            return Ok(());
        };
        let moved = if let R::FeynmanLabel { part, index, .. } = reference {
            let Some(diagram) = series.render_type.feynman_mut() else {
                return Ok(());
            };
            diagram.drag_label(*part, *index, dx, dy)
        } else if let R::ValueLabel {
            category_index,
            part,
            ..
        } = reference
        {
            if let (Some(part), Some(levels)) = (part, series.render_type.energy_levels_mut()) {
                levels.drag_label(*part, *category_index, dx, dy)
            } else {
                let count = series.value_label_text().map_or(0, <[String]>::len);
                series.drag_value_label(*category_index, count, dx, dy)
            }
        } else {
            let hit = match reference {
                R::FeynmanVertex { vertex_index, .. } => {
                    renderer::FeynmanHit::Vertex(*vertex_index)
                }
                R::FeynmanPropagator {
                    propagator_index, ..
                } => renderer::FeynmanHit::Propagator(*propagator_index),
                _ => return Ok(()),
            };
            let gpu_id = gpu::column_id(self.data.figure_id, id);
            let moved = self
                .renderer
                .drag_feynman(self.data.chart_id, &gpu_id, hit, dx, dy)
                .map_err(runtime)?;
            if moved == renderer::layout::NudgeResult::Moved {
                let result = self
                    .renderer
                    .chart_series(self.data.chart_id)
                    .map_err(runtime)?
                    .iter()
                    .find(|s| s.series_id == gpu_id)
                    .map(|s| s.render_type.clone());
                // Commit through the normal SSOT transaction and history below.
                self.renderer
                    .set_chart_series(
                        self.data.chart_id,
                        gpu::series(self.data.figure_id, &self.data.series),
                    )
                    .map_err(runtime)?;
                series.render_type = result.ok_or_else(|| runtime("dragged series disappeared"))?;
            }
            moved
        };
        if moved == renderer::layout::NudgeResult::Moved {
            self.apply_settings_model(next)?;
        }
        Ok(())
    }
}
