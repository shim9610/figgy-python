//! Bounded pie/donut documents use the upstream radial model and renderer.
use super::*;
use renderer::radial::{RadialChart, RadialRenderer};

pub(super) struct RadialDocument {
    pub chart: RadialChart,
    renderer: Option<RadialRenderer>,
}

impl RadialDocument {
    pub(super) fn gpu_bytes(&self) -> u64 {
        self.renderer
            .as_ref()
            .map_or(0, |r| r.gpu_memory_usage().total_bytes())
    }
}

pub(super) fn validate(chart: &RadialChart, rect: Rect) -> PyResult<()> {
    if rect.width < 160 || rect.height < 160 {
        return Err(invalid("pie/donut canvas must be at least 160x160 pixels"));
    }
    validate_model_numbers(chart, "radial")?;
    chart.validate().map_err(invalid)
}

impl FigureAccess<'_> {
    pub(super) fn set_radial(&mut self, json: &str) -> PyResult<()> {
        if !matches!(
            self.data.chart.config().draw_style,
            renderer::config::DrawStyle::Precise
        ) {
            return Err(invalid(
                "pie/donut charts use radial materials; reset the Cartesian draw style first",
            ));
        }
        if !self.data.series.is_empty() || !self.data.columns.is_empty() {
            return Err(invalid("create a separate Figure for pie/donut charts"));
        }
        let chart: RadialChart = parse(json)?;
        validate(&chart, self.data.chart.config().chart_area.0)?;
        if let Some(document) = &mut self.data.radial {
            document.chart = chart;
        } else {
            self.data.radial = Some(RadialDocument {
                chart,
                renderer: None,
            });
        }
        self.data.revision += 1;
        Ok(())
    }

    pub(super) fn render_radial(&mut self, scale: f32) -> PyResult<renderer::RasterImage> {
        if !scale.is_finite() || !(0.5..=4.).contains(&scale) {
            return Err(invalid("pie/donut export scale must be 0.5..4"));
        }
        let rect = self.data.chart.config().chart_area.0;
        let document = self.data.radial.as_mut().unwrap();
        if document.renderer.is_none() {
            document.renderer = Some(
                RadialRenderer::new(
                    RendererDevice::new(
                        self.renderer.device().clone(),
                        self.renderer.queue().clone(),
                    ),
                    wgpu::TextureFormat::Rgba8Unorm,
                )
                .map_err(runtime)?,
            );
        }
        document
            .renderer
            .as_mut()
            .unwrap()
            .export_rgba(&document.chart, (rect.width, rect.height), scale)
            .map_err(runtime)
    }

    pub(super) fn pick_radial(&mut self, x: f32, y: f32) -> PyResult<String> {
        let rect = self.data.chart.config().chart_area.0;
        let document = self.data.radial.as_mut().unwrap();
        if document.renderer.is_none() {
            document.renderer = Some(
                RadialRenderer::new(
                    RendererDevice::new(
                        self.renderer.device().clone(),
                        self.renderer.queue().clone(),
                    ),
                    wgpu::TextureFormat::Rgba8Unorm,
                )
                .map_err(runtime)?,
            );
        }
        let frame = document
            .renderer
            .as_mut()
            .unwrap()
            .prepare(&document.chart, (rect.width, rect.height), 1.)
            .map_err(runtime)?;
        let picked = frame.hit_test([x, y]);
        if document.chart.interaction.selected != picked {
            document.chart.interaction.selected = picked;
            self.data.revision += 1;
        }
        let value = picked.and_then(|target| document.chart.slice(target).map(|s|
            json!({"target":format!("slice_{}", target.index), "group":target.group, "index":target.index, "label":s.label, "value":s.value})));
        serde_json::to_string(&value).map_err(runtime)
    }
}

#[pyfunction]
pub(super) fn default_radial_json() -> PyResult<String> {
    serde_json::to_string(&RadialChart::default()).map_err(runtime)
}
