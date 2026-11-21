//! Host label formatting through the public model helpers; no source retention.
use super::*;

pub(super) fn signature(config: &Config, series: &[SeriesConfig]) -> Value {
    let specs: Vec<_> = series
        .iter()
        .filter(|s| {
            s.render_type.category_bars().is_some()
                || s.render_type.box_plot().is_some()
                || s.render_type.radar().is_some()
        })
        .map(|s| {
            let wire = serde_json::to_value(s).unwrap();
            let (kind, body) = wire["render_type"]
                .as_object()
                .unwrap()
                .iter()
                .next()
                .unwrap();
            let overrides: Vec<_> = body["overrides"]
                .as_array()
                .into_iter()
                .flatten()
                .filter(|o| !o["labels"].is_null() || !o["label_format"].is_null())
                .map(|o| json!([o["target"], o["labels"], o["label_format"]]))
                .collect();
            json!([
                s.series_id,
                config.layer_of_series(&s.series_id),
                s.x_column,
                s.y_column,
                kind,
                body["labels"]["placement"],
                body["labels"]["decimals"],
                body["labels"]["value_suffix"],
                body["label_format"],
                overrides
            ])
        })
        .collect();
    let configs = std::iter::once(config)
        .chain(config.subplots.iter().map(|p| &p.config))
        .map(|c| {
            json!([
                c.bottom_x
                    .categories
                    .as_ref()
                    .map(|cs| cs.iter().map(|c| (&c.id, &c.label)).collect::<Vec<_>>()),
                c.left_y
                    .categories
                    .as_ref()
                    .map(|cs| cs.iter().map(|c| (&c.id, &c.label)).collect::<Vec<_>>()),
                c.bar_groups.map(|g| g.direction),
                c.overlays
                    .iter()
                    .map(|o| json!([
                        o.x_axis
                            .categories
                            .as_ref()
                            .map(|cs| cs.iter().map(|c| (&c.id, &c.label)).collect::<Vec<_>>()),
                        o.y_axis
                            .categories
                            .as_ref()
                            .map(|cs| cs.iter().map(|c| (&c.id, &c.label)).collect::<Vec<_>>()),
                        o.series,
                        o.link_x,
                        o.link_y
                    ]))
                    .collect::<Vec<_>>()
            ])
        })
        .collect::<Vec<_>>();
    json!([specs, configs])
}

pub(super) fn format(
    config: &Config,
    series: &mut [SeriesConfig],
    mut read: impl FnMut(&str, Option<&str>, usize) -> PyResult<Vec<Option<f64>>>,
) -> PyResult<()> {
    let mut layers = Vec::new();
    for s in series.iter() {
        let l = config.layer_of_series(&s.series_id);
        if !layers.contains(&l) {
            layers.push(l);
        }
    }
    for layer in layers {
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
        let (x, y) = panel.scaling_axes(overlay);
        let horizontal =
            config.bar_groups_of(layer).direction == renderer::CategoryBarDirection::Horizontal;
        for kind in 0..3 {
            let indices = series
                .iter()
                .enumerate()
                .filter(|(_, s)| {
                    config.layer_of_series(&s.series_id) == layer
                        && match kind {
                            0 => s.render_type.category_bars().is_some(),
                            1 => s.render_type.box_plot().is_some(),
                            _ => s.render_type.radar().is_some(),
                        }
                })
                .map(|(i, _)| i)
                .collect::<Vec<_>>();
            if indices.is_empty() {
                continue;
            }
            let categories = if kind == 2 {
                panel.bottom_x.categories.as_deref()
            } else if horizontal {
                y.categories.as_deref()
            } else {
                x.categories.as_deref()
            }
            .unwrap_or(&[]);
            let mut members = indices
                .iter()
                .map(|i| series[*i].clone())
                .collect::<Vec<_>>();
            let values = members
                .iter()
                .map(|s| {
                    read(
                        if kind == 0 && horizontal {
                            &s.x_column
                        } else {
                            &s.y_column
                        },
                        if kind == 1 { Some("median") } else { None },
                        categories.len(),
                    )
                })
                .collect::<PyResult<Vec<_>>>()?;
            let counts = if kind == 1 {
                members
                    .iter()
                    .map(|s| read(&s.y_column, Some("sample_count"), categories.len()))
                    .collect::<PyResult<Vec<_>>>()?
            } else {
                Vec::new()
            };
            let value =
                |k: usize, i: usize| values.get(k).and_then(|v| v.get(i)).copied().flatten();
            match kind {
                0 => renderer::data_config::format_labels(&mut members, categories, value),
                1 => renderer::data_config::format_box_plot_labels(
                    &mut members,
                    categories,
                    |k, i| {
                        value(k, i).map(|m| {
                            (
                                m,
                                counts
                                    .get(k)
                                    .and_then(|v| v.get(i))
                                    .copied()
                                    .flatten()
                                    .filter(|v| *v >= 0.)
                                    .map(|v| v as u64),
                            )
                        })
                    },
                ),
                _ => renderer::data_config::format_radar_labels(&mut members, categories, value),
            }
            for (index, member) in indices.into_iter().zip(members) {
                series[index] = member;
            }
        }
    }
    Ok(())
}
impl FigureAccess<'_> {
    pub(super) fn format_value_labels(
        &mut self,
        config: &Config,
        series: &mut [SeriesConfig],
    ) -> PyResult<()> {
        // Source IDs are immutable: replacing an existing column is rejected.
        // New unrelated uploads must not rewrite explicitly edited label text.
        if signature(config, series) == signature(self.data.chart.config(), &self.data.series) {
            return Ok(());
        }
        format(config, series, |id, field, count| {
            let mut id = gpu::column_id(self.data.figure_id, id);
            if let Some(field) = field {
                let Some(record) = self.renderer.pool().record(&id) else {
                    return Ok(vec![]);
                };
                let Some(index) = renderer::BOX_PLOT_RECORD
                    .iter()
                    .position(|(name, _)| *name == field)
                else {
                    return Ok(vec![]);
                };
                let Some(member) = record.slot().fields[index].clone() else {
                    return Ok(vec![]);
                };
                id = member;
            }
            let Some(handle) = self.renderer.pool().handle_for(&id) else {
                return Err(invalid("value-label column no longer exists"));
            };
            let samples = (0..count.min(handle.len_values))
                .map(|i| (id.clone(), i))
                .collect::<Vec<_>>();
            let previous = self.data.selection_value_readbacks;
            let values = self.read_gpu_samples(&samples, false);
            self.data.selection_value_readbacks = previous;
            Ok(values?
                .into_iter()
                .map(|v| v.is_finite().then_some(v))
                .collect())
        })
    }
}
#[pyfunction]
#[pyo3(signature=(settings, column, previous=None))]
pub(super) fn format_value_labels_json(
    settings: &str,
    column: &Bound<'_, PyAny>,
    previous: Option<&str>,
) -> PyResult<String> {
    let mut state: Settings = parse(settings)?;
    if let Some(old) = previous {
        let old: Settings = parse(old)?;
        if signature(&state.config, &state.series) == signature(&old.config, &old.series) {
            return Ok(settings.into());
        }
    }
    format(&state.config, &mut state.series, |id, field, count| {
        let array = column.call1((id, field))?;
        if array.is_none() {
            return Ok(vec![]);
        }
        if let Ok(a) = array.extract::<PyReadonlyArray1<f32>>() {
            return Ok(a
                .as_slice()
                .map_err(invalid)?
                .iter()
                .take(count)
                .map(|v| v.is_finite().then_some(*v as f64))
                .collect());
        }
        if let Ok(a) = array.extract::<PyReadonlyArray1<f64>>() {
            return Ok(a
                .as_slice()
                .map_err(invalid)?
                .iter()
                .take(count)
                .map(|v| v.is_finite().then_some(*v))
                .collect());
        }
        Err(invalid("label columns must be contiguous f32/f64"))
    })?;
    serde_json::to_string(&state).map_err(runtime)
}

/// Settings may swap a categorical series' two existing columns only when
/// rotating its owning group. This never reconnects a different source.
pub(super) fn same_sources(
    a: &SeriesConfig,
    b: &SeriesConfig,
    next: &Config,
    old: &Config,
) -> bool {
    if a.series_id != b.series_id {
        return false;
    }
    if a.x_column == b.x_column && a.y_column == b.y_column {
        return true;
    }
    let layer = next.layer_of_series(&a.series_id);
    a.render_type.category_bars().is_some()
        && b.render_type.category_bars().is_some()
        && layer == old.layer_of_series(&b.series_id)
        && next.bar_groups_of(layer).direction != old.bar_groups_of(layer).direction
        && a.x_column == b.y_column
        && a.y_column == b.x_column
}
