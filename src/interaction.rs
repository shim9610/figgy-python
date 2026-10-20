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
pub(super) fn panel_at(config: &Config, point: (f32, f32)) -> Option<usize> {
    // Later panels paint above earlier panels if a hand-authored layout overlaps.
    (0..=config.subplots.len())
        .rev()
        .find(|&i| contains(panel(config, i).chart_area.0, point))
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

/// Probe the renderer's own hit maps, without installing speculative document
/// edits. Overlay-only hits win over shared panel decorations.
pub(super) fn decoration_at(
    config: &Config,
    index: usize,
    point: (f32, f32),
) -> Option<(LayerRef, String)> {
    let measure = CpuTextMeasure::for_style(&config.draw_style);
    let mut layers: Vec<_> = config
        .panel_layers()
        .into_iter()
        .filter(|l| panel_index(*l) == index)
        .collect();
    // The current axis wins when several secondary axes occupy the same pixels.
    if let Some(at) = layers.iter().position(|l| *l == config.active_layer()) {
        let current = layers.remove(at);
        layers.push(current);
    }
    let mut fallback = None;
    for layer in layers.into_iter().rev() {
        let mut probe = config.clone();
        probe.set_active_layer(layer);
        let map = HitMap::for_active_layer(&probe);
        let Some(target) = map
            .hit_test(&probe, &measure, point.0, point.1)
            .and_then(|id| map.get(id))
            .map(|e| e.element_id())
        else {
            continue;
        };
        if target.contains("overlay_") {
            return Some((layer, target));
        }
        // Shared elements retain their base owner, even when probed in an overlay.
        if !target.ends_with("data_area") {
            fallback = Some((base_layer(index), target));
        } else if fallback.is_none() {
            fallback = Some((base_layer(index), target));
        }
    }
    fallback
}

impl FigureAccess<'_> {
    /// Only compact pick identities cross the GPU boundary. Temporary layer
    /// routing is restored on both success and failure; no source is reuploaded.
    pub(super) fn pick_panel_data(
        &mut self,
        index: usize,
        request: GpuPickRequest,
        cycle: bool,
    ) -> PyResult<Option<(LayerRef, renderer::config::PickedDataRef)>> {
        self.renderer.enable_gpu_picking().map_err(runtime)?;
        let original = self.data.chart.config().active_layer();
        let layers: Vec<_> = self
            .data
            .chart
            .config()
            .panel_layers()
            .into_iter()
            .filter(|l| panel_index(*l) == index)
            .collect();
        let result = (|| {
            let mut hits = vec![];
            for layer in layers {
                self.renderer
                    .set_active_layer(self.data.chart_id, layer)
                    .map_err(runtime)?;
                let ticket = self
                    .renderer
                    .pick_chart_data(self.data.chart_id, request)
                    .map_err(runtime)?;
                self.renderer.wait_idle();
                if let Some(pick) = pollster::block_on(ticket.resolve()).map_err(runtime)? {
                    let distance = pick.distance_px();
                    let mut reference = pick.to_ref();
                    gpu::local_selection(self.data.figure_id, &mut reference);
                    hits.push((distance, layer, reference));
                }
            }
            hits.sort_by(|a, b| a.0.total_cmp(&b.0));
            let current = self
                .data
                .chart
                .config()
                .picked_data
                .as_ref()
                .and_then(|p| p.refs.first());
            let at = if cycle {
                hits.iter()
                    .position(|(_, _, p)| Some(p) == current)
                    .map(|i| (i + 1) % hits.len())
                    .unwrap_or(0)
            } else {
                0
            };
            Ok(hits
                .into_iter()
                .nth(at)
                .map(|(_, layer, reference)| (layer, reference)))
        })();
        let restore = self
            .renderer
            .set_active_layer(self.data.chart_id, original)
            .map_err(runtime);
        restore?;
        result
    }
}
