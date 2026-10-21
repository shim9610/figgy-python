//! Fit each coordinate owner, unioning linked domains before choosing ranges.
use super::*;
use renderer::{CellRef, chart::FitExtent};

fn root(config: &Config, mut cell: usize, x: bool) -> usize {
    while cell > 0 {
        let panel = &config.subplots[cell - 1];
        match if x { panel.link_x } else { panel.link_y } {
            Some(CellRef::Parent) => cell = 0,
            Some(CellRef::Subplot(i)) if i + 1 < cell => cell = i + 1,
            _ => break,
        }
    }
    cell
}

pub(super) fn fit(
    config: &Config,
    series: &[SeriesConfig],
    extents: &[[FitExtent; 2]],
    padding: f64,
    active_only: bool,
) -> Config {
    let mut groups: HashMap<(usize, usize, Option<usize>), FitExtent> = HashMap::new();
    for (spec, extent) in series.iter().zip(extents) {
        let panel = config
            .subplots
            .iter()
            .position(|p| p.owns_series(&spec.series_id))
            .map_or(0, |i| i + 1);
        let cfg = if panel == 0 {
            config
        } else {
            &config.subplots[panel - 1].config
        };
        let overlay = cfg
            .overlays
            .iter()
            .position(|p| p.owns_series(&spec.series_id));
        for (dimension, value) in extent.iter().enumerate() {
            let mut value = *value;
            if dimension == 1
                && value.min.is_finite()
                && value.max.is_finite()
                && value.min <= value.max
            {
                use renderer::DataRenderType as T;
                let line = match &spec.render_type {
                    T::Line { line }
                    | T::ScatterLine { line, .. }
                    | T::LineScatterErrorbarX { line, .. }
                    | T::LineScatterErrorbarY { line, .. }
                    | T::LineScatterErrorbarXY { line, .. } => Some(line),
                    _ => None,
                };
                if let Some(renderer::data_config::LineFill::ToBaseline(baseline)) =
                    line.and_then(|line| line.fill.as_ref())
                {
                    value.union(&FitExtent {
                        min: *baseline,
                        max: *baseline,
                        min_positive: (*baseline > 0.).then_some(*baseline),
                    });
                }
            }
            let owner = if dimension == 1 && overlay.is_some() {
                panel
            } else {
                root(config, panel, dimension == 0)
            };
            groups
                .entry((
                    owner,
                    dimension,
                    if dimension == 1 { overlay } else { None },
                ))
                .or_insert(FitExtent::EMPTY)
                .union(&value);
        }
    }
    let (active_panel, active_overlay) = match config.active_layer() {
        renderer::LayerRef::Subplot(i) => (i + 1, None),
        renderer::LayerRef::SubplotOverlay(i, o) => (i + 1, Some(o)),
        renderer::LayerRef::Overlay(o) => (0, Some(o)),
        _ => (0, None),
    };
    let x_root = root(config, active_panel, true);
    let y_root = root(config, active_panel, false);
    let mut result = config.clone();
    for index in 0..=config.subplots.len() {
        let cfg = if index == 0 {
            &mut result
        } else {
            &mut result.subplots[index - 1].config
        };
        let mut chart = Chart::new(cfg.clone());
        if (!active_only || index == x_root)
            && let Some(extent) = groups.get(&(index, 0, None))
        {
            chart.auto_fit_x_extent(extent, padding);
        }
        if (!active_only || (active_overlay.is_none() && index == y_root))
            && let Some(extent) = groups.get(&(index, 1, None))
        {
            chart.auto_fit_y_extent(extent, padding);
        }
        *cfg = chart.config().clone();
        for overlay in 0..cfg.overlays.len() {
            if (!active_only || (index == active_panel && active_overlay == Some(overlay)))
                && let Some(extent) = groups.get(&(index, 1, Some(overlay)))
            {
                let mut local = cfg.clone();
                local.left_y = cfg.overlays[overlay].y_axis.clone();
                let mut chart = Chart::new(local);
                chart.auto_fit_y_extent(extent, padding);
                cfg.overlays[overlay].y_axis = chart.config().left_y.clone();
            }
        }
    }
    result.sync_subplot_links(None);
    result
}

pub(super) fn set_range(config: &Config, axis: &str, min: f64, max: f64) -> PyResult<Config> {
    let mut result = config.clone();
    let (panel, overlay) = match config.active_layer() {
        renderer::LayerRef::Subplot(i) => (i + 1, None),
        renderer::LayerRef::SubplotOverlay(i, o) => (i + 1, Some(o)),
        renderer::LayerRef::Overlay(i) => (0, Some(i)),
        _ => (0, None),
    };
    let cfg = if panel == 0 {
        &mut result
    } else {
        &mut result.subplots[panel - 1].config
    };
    let mut local = cfg.clone();
    if axis == "y"
        && let Some(i) = overlay
    {
        local.left_y = cfg.overlays[i].y_axis.clone();
    }
    let mut chart = Chart::new(local);
    match axis {
        "x" => chart.set_x_range(min, max),
        "y" => chart.set_y_range(min, max),
        _ => return Err(invalid("axis must be x or y")),
    };
    if axis == "y"
        && let Some(i) = overlay
    {
        cfg.overlays[i].y_axis = chart.config().left_y.clone();
    } else {
        *cfg = chart.config().clone();
    }
    result.sync_subplot_links(Some(config));
    Ok(result)
}
