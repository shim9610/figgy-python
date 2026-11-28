//! Restore beta pixel offsets and fit notebook dependency exits from bar endpoints.
use super::*;

type Sample = (String, usize);

pub(super) fn migrate(
    mut document: Value,
    read: impl FnOnce(&[Sample]) -> PyResult<Vec<f64>>,
) -> PyResult<Value> {
    let offsets = document["series"]
        .as_array_mut()
        .ok_or_else(|| invalid("settings series must be a list"))?
        .iter_mut()
        .enumerate()
        .flat_map(|(series, spec)| {
            spec.get_mut("render_type")
                .and_then(|rt| rt.get_mut("RangeLinks"))
                .and_then(|s| s.get_mut("links"))
                .and_then(Value::as_array_mut)
                .into_iter()
                .flatten()
                .enumerate()
                .filter_map(move |(index, row)| {
                    let map = row.as_object_mut()?;
                    let offset = map.remove("exit_offset")?;
                    Some((series, index, map.contains_key("exit_fraction"), offset))
                })
        })
        .collect::<Vec<_>>();
    if offsets.is_empty() {
        return Ok(document);
    }
    let mut legacy = HashMap::new();
    for (series, index, has_fraction, offset) in offsets {
        if has_fraction {
            return Err(invalid("specify exit_fraction or exit_offset, not both"));
        }
        if !offset.is_null() {
            let offset = offset
                .as_f64()
                .filter(|v| v.is_finite() && *v >= 0.)
                .ok_or_else(|| invalid("exit_offset must be finite and nonnegative"))?;
            legacy.insert((series, index), offset);
        }
    }
    if !legacy.is_empty() {
        let config: Config = parse(&document["config"].to_string())?;
        let mut series: Vec<SeriesConfig> = parse(&document["series"].to_string())?;
        update(&config, &mut series, Some(&legacy), false, read)?;
        for ((series_index, index), _) in legacy {
            let link = &series[series_index]
                .render_type
                .range_links()
                .unwrap()
                .links[index];
            document["series"][series_index]["render_type"]["RangeLinks"]["links"][index]["exit_fraction"] =
                json!(link.exit_fraction);
        }
    }
    Ok(document)
}

pub(super) fn update(
    config: &Config,
    series: &mut [SeriesConfig],
    legacy: Option<&HashMap<(usize, usize), f64>>,
    active_only: bool,
    read: impl FnOnce(&[Sample]) -> PyResult<Vec<f64>>,
) -> PyResult<()> {
    let mut jobs = Vec::new();
    let mut samples = Vec::new();
    for (k, spec) in series.iter().enumerate() {
        let Some(links) = spec.render_type.range_links() else {
            continue;
        };
        if active_only && config.layer_of_series(&spec.series_id) != config.active_layer() {
            continue;
        }
        let Some(bars) = series.iter().find(|s| s.series_id == links.bars) else {
            return Err(invalid(format!("unknown range bar series: {}", links.bars)));
        };
        let Some(style) = bars.render_type.range_bars() else {
            return Err(invalid(format!("{} is not a range bar series", links.bars)));
        };
        for (j, link) in links.links.iter().enumerate() {
            let offset = legacy.and_then(|v| v.get(&(k, j)).copied());
            if legacy.is_some() && offset.is_none() || link.exit_fraction.is_some() {
                continue;
            }
            let span = samples.len();
            samples.push((style.start.clone(), link.from as usize));
            samples.push((bars.y_column.clone(), link.from as usize));
            if offset.is_none() {
                samples.push((style.start.clone(), link.to as usize));
                samples.push((bars.y_column.clone(), link.to as usize));
            }
            jobs.push((k, j, config.panel_of_series(&bars.series_id), span, offset));
        }
    }
    if jobs.is_empty() {
        return Ok(());
    }
    let expansion = config.expand().ok();
    let values = read(&samples)?;
    for (k, j, panel, span, offset) in jobs {
        let panel = expansion
            .as_ref()
            .and_then(|e| e.panels.get(panel))
            .map(|p| &p.config)
            .unwrap_or(config);
        let space = renderer::annotation::pixel_space_for_config(panel);
        let horizontal =
            panel.effective_bar_groups().direction == renderer::CategoryBarDirection::Horizontal;
        let along = |value: f64| {
            let (axis, start, width) = if horizontal {
                (&space.x, space.plot.x, space.plot.width)
            } else {
                (
                    &space.y,
                    space.plot.y + space.plot.height,
                    -space.plot.height,
                )
            };
            Some(start + axis.fraction(value)? as f32 * width)
        };
        let ends = |i: usize| Some([along(values[i])?, along(values[i + 1])?]);
        let links = series[k].render_type.range_links_mut().unwrap();
        let fraction = if let Some(offset) = offset {
            let length = ends(span).map(|[a, b]| (b - a).abs()).unwrap_or_default();
            if offset == 0. {
                Some(0.)
            } else if length > 0. && length.is_finite() {
                Some((offset / f64::from(length)).clamp(0., 1.) as f32)
            } else {
                return Err(invalid(
                    "legacy exit_offset requires a drawable predecessor bar",
                ));
            }
        } else {
            ends(span)
                .zip(ends(span + 2))
                .and_then(|(pred, succ)| links.chosen_exit_offset(pred, succ))
        };
        links.links[j].exit_fraction = fraction;
    }
    Ok(())
}
