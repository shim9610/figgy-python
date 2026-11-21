//! Fit each coordinate owner, unioning linked domains before choosing ranges.
use super::*;
use renderer::chart::FitExtent;

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
    } else {
        *cfg = chart.config().clone();
    }
    result.sync_subplot_links(Some(config));
    Ok(result)
}
