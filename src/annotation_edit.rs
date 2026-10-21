//! Coordinate conversion delegates to the upstream anchor/axis transforms.
use super::*;
use renderer::annotation::{AxisMap, AxisSpace, PixelSpace};

pub(crate) fn space(settings: &Settings) -> PyResult<PixelSpace> {
    if settings.document()?.is_none() {
        return Ok(renderer::annotation::pixel_space_for_config(
            &settings.config,
        ));
    }
    // Converting Data <-> Ratio cancels the plot rectangle. Unit geometry avoids
    // duplicating font measurement or automatic margin layout in the kernel.
    let rect = renderer::layout::RectF {
        x: 0.,
        y: 0.,
        width: 1.,
        height: 1.,
    };
    let mut space = PixelSpace {
        panel: rect,
        plot: rect,
        x: AxisSpace::NONE,
        y: AxisSpace::NONE,
    };
    let (horizontal, count, range) = if let Some(chart) = &settings.categorical {
        use renderer::categorical::{CategoryBarDirection, CategoryBarLabels, CategoryBarMode};
        let (mut low, mut high) = (0.0f64, 0.0f64);
        for segment in chart.segments().map_err(invalid)? {
            low = low.min(segment.start).min(segment.end);
            high = high.max(segment.start).max(segment.end);
        }
        let percent = chart.mode == CategoryBarMode::PercentStacked;
        if percent {
            high = 100.;
        } else if low == high {
            high = 1.;
        }
        let unit = 10.0f64
            .powf(low.abs().max(high.abs()).log10().floor())
            .max(f64::MIN_POSITIVE);
        let outside = chart.labels == CategoryBarLabels::Outside
            || (chart.labels == CategoryBarLabels::Auto && chart.mode == CategoryBarMode::Grouped)
            || chart
                .overrides
                .iter()
                .any(|v| v.labels == Some(CategoryBarLabels::Outside));
        let padding = if outside && !percent {
            0.12 * (high / unit - low / unit)
        } else {
            0.
        };
        let plan = renderer::config::AxisOptions::compute_nice_ticks(
            renderer::config::AxisScale::Linear,
            low / unit - if low < 0. { padding } else { 0. },
            high / unit + if high > 0. { padding } else { 0. },
            5,
        )
        .map_err(|_| invalid("categorical axis range cannot be represented"))?;
        (
            chart.direction == CategoryBarDirection::Horizontal,
            chart.categories.len(),
            [plan.min * unit, plan.max * unit],
        )
    } else if let Some(chart) = &settings.boxplot {
        let view = navigation::bounded_view(settings)
            .ok_or_else(|| invalid("cannot determine the boxplot value domain"))?;
        (
            chart.direction == renderer::boxplot::BoxPlotDirection::Horizontal,
            chart.categories.len(),
            [
                view["range"][0].as_f64().unwrap(),
                view["range"][1].as_f64().unwrap(),
            ],
        )
    } else {
        return Ok(space);
    }; // Polar, pie/donut and radar have no separable value axes.
    let value = AxisSpace {
        map: AxisMap::Linear {
            min: range[0],
            max: range[1],
        },
        inverted: false,
    };
    let category = AxisSpace {
        map: AxisMap::Index { count },
        inverted: horizontal,
    };
    if horizontal {
        space.x = value;
        space.y = category;
    } else {
        space.x = category;
        space.y = value;
    }
    Ok(space)
}

pub(crate) fn convert(settings: &Settings, anchor: &Value, kind: &Value) -> PyResult<Value> {
    let anchor: renderer::annotation::Anchor =
        serde_json::from_value(anchor.clone()).map_err(invalid)?;
    let kind: renderer::annotation::AnchorKind =
        serde_json::from_value(kind.clone()).map_err(invalid)?;
    let converted=anchor.converted(&space(settings)?,kind).ok_or_else(||invalid("this chart cannot express the current point in those coordinates; the document was preserved"))?;
    serde_json::to_value(converted).map_err(runtime)
}

/// Reordering uses the annotation's ID, and keeps any currently selected bounded
/// annotation attached to that ID instead of an obsolete renderer array index.
pub(crate) fn reorder(
    state: &mut Value,
    items_path: &str,
    index: usize,
    to: usize,
) -> PyResult<()> {
    let owner_path = items_path.trim_end_matches("/annotations/items");
    let selected = state
        .pointer(owner_path)
        .and_then(|v| v["decorations"]["selected"]["Annotation"].as_u64())
        .and_then(|i| state.pointer(items_path)?.get(i as usize)?["id"].as_str())
        .map(str::to_owned);
    let items = state
        .pointer_mut(items_path)
        .and_then(Value::as_array_mut)
        .ok_or_else(|| invalid("annotation layer changed"))?;
    if index >= items.len() || to >= items.len() {
        return Err(invalid("annotation order is outside the layer"));
    }
    let item = items.remove(index);
    items.insert(to, item);
    let at = selected.and_then(|id| items.iter().position(|v| v["id"] == id));
    if let Some(index) = at {
        state.pointer_mut(owner_path).unwrap()["decorations"]["selected"] =
            json!({"Annotation":index});
    }
    Ok(())
}
