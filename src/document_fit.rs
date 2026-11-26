//! Fit each coordinate owner, unioning linked domains before choosing ranges.
use super::*;
use renderer::chart::FitExtent;

pub(super) fn energy_extent(spec: &SeriesConfig, series: &[SeriesConfig]) -> FitExtent {
    let Some(diagram) = spec.render_type.energy_levels() else {
        return FitExtent::EMPTY;
    };
    let source = diagram
        .source
        .as_ref()
        .and_then(|id| {
            series
                .iter()
                .find(|s| &s.series_id == id)?
                .render_type
                .energy_levels()
        })
        .unwrap_or(diagram);
    let Some((min, max)) = source.energy_extent(diagram.show) else {
        return FitExtent::EMPTY;
    };
    let min_positive = if min > 0. {
        Some(min)
    } else {
        source
            .levels
            .iter()
            .filter(|level| level.role.drawn_in(diagram.show))
            .map(|level| level.energy)
            .chain(source.limits.iter().map(|limit| limit.energy))
            .filter(|energy| energy.is_finite() && *energy > 0.)
            .reduce(f64::min)
    };
    FitExtent {
        min,
        max,
        min_positive,
    }
}

pub(super) fn include_energy_levels(
    chart: &mut Chart,
    layer: renderer::LayerRef,
    series: &[SeriesConfig],
    padding: f64,
) {
    let config = chart.config();
    let mut extent = FitExtent::EMPTY;
    let mut has_other_data = false;
    for spec in series {
        if config.series_fit_roles(layer, &spec.series_id).1 {
            extent.union(&energy_extent(spec, series));
            has_other_data |= (!spec.is_dataless() && spec.render_type.range_links().is_none())
                || spec.render_type.feynman().is_some();
        }
    }
    if !extent.min.is_finite() {
        return;
    }
    if !has_other_data {
        chart.auto_fit_layer_extent(layer, &FitExtent::EMPTY, &extent, padding);
        return;
    }
    // The native renderer already fit the ordinary sources. Union the two
    // independently padded ranges so neither side receives padding twice.
    let bounds = |config: &Config| {
        let panel = match layer {
            renderer::LayerRef::Subplot(i) | renderer::LayerRef::SubplotOverlay(i, _) => {
                &config.subplots[i].config
            }
            _ => config,
        };
        let overlay = match layer {
            renderer::LayerRef::Overlay(i) | renderer::LayerRef::SubplotOverlay(_, i) => Some(i),
            _ => None,
        };
        let axis = panel.scaling_axes(overlay).1;
        (axis.min, axis.max)
    };
    let mut candidate = Chart::as_given(config.clone());
    candidate.auto_fit_layer_extent(layer, &FitExtent::EMPTY, &extent, padding);
    let (a, b) = bounds(config);
    let (c, d) = bounds(candidate.config());
    if c < a || d > b {
        let mut merged = FitExtent::point(a);
        for value in [b, c, d] {
            merged.union(&FitExtent::point(value));
        }
        chart.auto_fit_layer_extent(layer, &FitExtent::EMPTY, &merged, 0.);
    }
}

pub(super) fn fit(
    config: &Config,
    series: &[SeriesConfig],
    extents: &[[FitExtent; 2]],
    padding: f64,
    active_only: bool,
) -> Config {
    let mut result = Chart::new(config.clone());
    let mut layers = vec![renderer::LayerRef::Base];
    layers.extend((0..config.overlays.len()).map(renderer::LayerRef::Overlay));
    for (i, subplot) in config.subplots.iter().enumerate() {
        layers.push(renderer::LayerRef::Subplot(i));
        layers.extend(
            (0..subplot.config.overlays.len()).map(|o| renderer::LayerRef::SubplotOverlay(i, o)),
        );
    }
    for layer in layers {
        if active_only && layer != config.active_layer() {
            continue;
        }
        let mut x = FitExtent::EMPTY;
        let mut y = FitExtent::EMPTY;
        for (spec, extent) in series.iter().zip(extents) {
            let (fit_x, fit_y) = config.series_fit_roles(layer, &spec.series_id);
            let (member_x, member_y) =
                Chart::line_offset_fit_extents(config, &spec.series_id, extent[0], extent[1]);
            if let renderer::DataRenderType::Xy(xy) = &spec.render_type {
                if let Some(stem) = &xy.stem {
                    if stem.direction == renderer::data_config::CategoryBarDirection::Horizontal {
                        if fit_x {
                            x.union(&FitExtent::point(stem.baseline));
                        }
                    } else if fit_y {
                        y.union(&FitExtent::point(stem.baseline));
                    }
                }
            }
            if fit_x {
                x.union(&member_x);
            }
            if fit_y {
                y.union(&member_y);
                if let renderer::DataRenderType::Xy(renderer::XySeries {
                    line: Some(line), ..
                }) = &spec.render_type
                {
                    if let Some(renderer::data_config::LineFill::ToBaseline(baseline)) =
                        line.fill.as_ref()
                    {
                        y.union(&FitExtent::point(*baseline));
                    }
                }
            }
        }
        result.auto_fit_layer_extent(layer, &x, &y, padding);
    }
    result.config().clone()
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
    let own_x = overlay.is_some_and(|i| !cfg.overlays[i].link_x);
    let own_y = overlay.is_some_and(|i| !cfg.overlays[i].link_y);
    if own_x && axis == "x" {
        local.bottom_x = cfg.overlays[overlay.unwrap()].x_axis.clone();
    }
    if own_y && axis == "y" {
        local.left_y = cfg.overlays[overlay.unwrap()].y_axis.clone();
    }
    let mut chart = Chart::new(local);
    match axis {
        "x" => chart.set_x_range(min, max),
        "y" => chart.set_y_range(min, max),
        _ => return Err(invalid("axis must be x or y")),
    };
    if own_x && axis == "x" {
        cfg.overlays[overlay.unwrap()].x_axis = chart.config().bottom_x.clone();
    } else if own_y && axis == "y" {
        cfg.overlays[overlay.unwrap()].y_axis = chart.config().left_y.clone();
    } else if axis == "y" && cfg.view_3d().is_some() {
        cfg.left_y = chart.config().left_y.clone();
    } else {
        *cfg = chart.config().clone();
    }
    result.sync_subplot_links(Some(config));
    Ok(result)
}
