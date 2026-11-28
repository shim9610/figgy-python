//! Host bridge to the renderer-owned radial hit map and GPU pick tickets.
use super::*;
use renderer::layout::{NudgeResult, RectF};
use renderer::{DecorationId, DecorationLayout, RadialChart, RadialFrame, RadialTarget};

pub(super) struct Frame {
    inner: Arc<RadialFrame>,
    decorations: Decorations,
}
impl Frame {
    pub fn new(inner: Arc<RadialFrame>, chart: RadialChart) -> Self {
        Self {
            decorations: Decorations {
                frame: inner.clone(),
                chart,
            },
            inner,
        }
    }
    pub fn decorations(&self) -> &Decorations {
        &self.decorations
    }
    pub fn hit_test(&self, p: [f32; 2]) -> Option<RadialTarget> {
        self.inner.pick(p).ok()?.resolve_blocking().ok().flatten()
    }
    pub fn hit_test_at_rest(&self, p: [f32; 2]) -> Option<RadialTarget> {
        self.inner
            .pick_at_rest(p)
            .ok()?
            .resolve_blocking()
            .ok()
            .flatten()
    }
}
impl std::ops::Deref for Frame {
    type Target = RadialFrame;
    fn deref(&self) -> &RadialFrame {
        &self.inner
    }
}
pub(super) struct Element {
    pub id: DecorationId,
}
pub(super) struct Decorations {
    frame: Arc<RadialFrame>,
    chart: RadialChart,
}
impl Decorations {
    pub fn entries(&self) -> impl Iterator<Item = (HitId, Element)> + '_ {
        self.frame
            .decoration_ids(&self.chart)
            .map(|(hit, id)| (hit, Element { id }))
    }
    pub fn element(&self, id: HitId) -> Option<Element> {
        self.frame
            .decoration_id(&self.chart, id)
            .map(|id| Element { id })
    }
    pub fn hit_test(&self, layout: &DecorationLayout, p: [f32; 2]) -> Option<HitId> {
        let mut c = self.chart.clone();
        c.decorations = layout.clone();
        self.frame.decoration_at(&c, p)
    }
    pub fn hit_resize_handle(&self, id: HitId, p: [f32; 2]) -> Option<ResizeHandle> {
        self.frame.decoration_resize_handle(&self.chart, id, p)
    }
    pub fn selection_box(&self, id: HitId) -> Option<renderer::SelectionBox> {
        self.frame.decoration_selection_box(&self.chart, id)
    }
    pub fn bounds(&self, id: HitId) -> Option<RectF> {
        self.frame.decoration_bounds(&self.chart, id)
    }
    pub fn drag_by(
        &self,
        layout: &mut DecorationLayout,
        id: HitId,
        dx: f32,
        dy: f32,
    ) -> Option<NudgeResult> {
        let mut c = self.chart.clone();
        c.decorations = layout.clone();
        let result = self.frame.drag_decoration(&mut c, id, dx, dy);
        *layout = c.decorations;
        result
    }
    pub fn resize_by(
        &self,
        layout: &mut DecorationLayout,
        id: HitId,
        h: ResizeHandle,
        dx: f32,
        dy: f32,
    ) -> Option<NudgeResult> {
        let mut c = self.chart.clone();
        c.decorations = layout.clone();
        let result = self.frame.resize_decoration(&mut c, id, h, dx, dy);
        *layout = c.decorations;
        result
    }
}
pub(super) fn hit_test_layer(
    annotations: &renderer::annotation::BoundedAnnotationFrame,
    layer: renderer::LayerRef,
    map: &Decorations,
    p: [f32; 2],
) -> Option<renderer::annotation::LayerHit> {
    if layer == renderer::LayerRef::Annotations {
        let a = annotations.annotations();
        if let Some(hit) = a.hit_test(p) {
            return Some(renderer::annotation::LayerHit::Annotation {
                index: a.element(hit)?.index,
                id: hit,
            });
        }
    }
    map.hit_test(&map.chart.decorations, p)
        .map(renderer::annotation::LayerHit::Element)
}

/// Paths follow the renderer's ring order, including zero-valued nodes.
pub(super) fn slice_paths(chart: &Value) -> Vec<(usize, usize, String)> {
    let mut level = chart["slices"]
        .as_array()
        .map(|nodes| {
            (0..nodes.len())
                .map(|i| format!("/slices/{i}"))
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let mut result = Vec::new();
    let mut group = 0;
    while !level.is_empty() {
        let mut next = Vec::new();
        for (index, path) in level.into_iter().enumerate() {
            if let Some(children) = chart
                .pointer(&path)
                .and_then(|node| node.get("children"))
                .and_then(Value::as_array)
            {
                next.extend((0..children.len()).map(|i| format!("{path}/children/{i}")));
            }
            result.push((group, index, path));
        }
        level = next;
        group += 1;
    }
    if group == 1 {
        if let Some(children) = chart["split"]["children"].as_array() {
            result.extend((0..children.len()).map(|i| (1, i, format!("/split/children/{i}"))));
        }
    }
    result
}
pub(super) fn slice_path(chart: &Value, group: usize, index: usize) -> Option<String> {
    slice_paths(chart)
        .into_iter()
        .find(|(g, i, _)| *g == group && *i == index)
        .map(|(_, _, path)| path)
}
