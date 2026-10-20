//! Persistent host addresses; visual state remains in the renderer model.
use super::*;
use std::collections::HashSet;

pub(super) fn fit_member(config: &Config, id: &str, axis: &str, layer: renderer::LayerRef) -> bool {
    let (x, y) = config.series_fit_roles(layer, id);
    match axis {
        "x" => x,
        "y" => y,
        _ => {
            fn panel(layer: renderer::LayerRef) -> Option<usize> {
                match layer {
                    renderer::LayerRef::Subplot(i) | renderer::LayerRef::SubplotOverlay(i, _) => {
                        Some(i)
                    }
                    _ => None,
                }
            }
            panel(config.layer_of_series(id)) == panel(layer)
        }
    }
}

pub(super) fn refresh_legends(config: &mut Config, series: &[SeriesConfig]) {
    let owned: Vec<_> = series
        .iter()
        .filter(|s| !config.subplots.iter().any(|p| p.owns_series(&s.series_id)))
        .cloned()
        .collect();
    renderer::legend::update_legend_symbols_preserving_text(
        &mut config.legend.content,
        &owned,
        config.colorbar.as_ref().map(|c| &c.colormap),
    );
    for overlay in &mut config.overlays {
        if let Some(legend) = overlay.legend.as_mut() {
            let owned: Vec<_> = owned
                .iter()
                .filter(|s| overlay.series.contains(&s.series_id))
                .cloned()
                .collect();
            renderer::legend::update_legend_symbols_preserving_text(
                &mut legend.content,
                &owned,
                config.colorbar.as_ref().map(|c| &c.colormap),
            );
        }
    }
    for subplot in &mut config.subplots {
        let owned: Vec<_> = series
            .iter()
            .filter(|s| subplot.owns_series(&s.series_id))
            .cloned()
            .collect();
        refresh_legends(&mut subplot.config, &owned);
    }
}

pub(super) fn validate_columns(series: &[SeriesConfig], names: &HashSet<String>) -> PyResult<()> {
    fn visit(value: &Value, names: &HashSet<String>) -> PyResult<()> {
        if let Some(fields) = value.as_object() {
            for (key, value) in fields {
                if matches!(
                    key.as_str(),
                    "column"
                        | "x_column"
                        | "y_column"
                        | "point_style_index_column"
                        | "lower"
                        | "upper"
                        | "u"
                        | "v"
                ) && let Some(name) = value.as_str()
                    && !names.contains(name)
                {
                    return Err(invalid(format!("unregistered source column: {name}")));
                }
                if key == "columns"
                    && let Some(columns) = value.as_array()
                {
                    for name in columns {
                        if !name.as_str().is_some_and(|n| names.contains(n)) {
                            return Err(invalid("unregistered matrix column"));
                        }
                    }
                }
                if key == "Column"
                    && let Some(name) = value.as_str()
                    && !names.contains(name)
                {
                    return Err(invalid("unregistered vector color column"));
                }
                visit(value, names)?;
            }
        } else if let Some(items) = value.as_array() {
            for item in items {
                visit(item, names)?;
            }
        }
        Ok(())
    }
    for series in series {
        visit(&serde_json::to_value(series).map_err(invalid)?, names)?;
    }
    Ok(())
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Identity {
    figure: String,
    panels: Vec<Panel>,
    layout: Option<Grid>,
    groups: HashMap<String, Shared>,
    retired: Vec<String>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Panel {
    id: String,
    overlays: Vec<String>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Shared {
    axis: String,
    members: Vec<String>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Grid {
    grid: Vec<Vec<Option<String>>>,
    placement: HashMap<String, String>,
    row_weights: Vec<f64>,
    column_weights: Vec<f64>,
    gap: f64,
    size: [u32; 2],
}

pub(super) fn validate_identity(
    value: Option<&Value>,
    config: &Config,
    schema: u32,
) -> PyResult<()> {
    let Some(value) = value else {
        return if schema == 1 {
            Ok(())
        } else {
            Err(invalid("schema 2 requires identity metadata"))
        };
    };
    if schema != 2 {
        return Err(invalid("identity metadata requires schema version 2"));
    }
    let meta: Identity = serde_json::from_value(value.clone()).map_err(invalid)?;
    let mut ids = HashSet::new();
    let mut register = |id: &str| -> PyResult<()> {
        if id.is_empty() {
            return Err(invalid("object IDs must be nonempty strings"));
        }
        if !ids.insert(id.to_owned()) {
            return Err(invalid("duplicate document object ID"));
        }
        Ok(())
    };
    register(&meta.figure)?;
    if meta.panels.len() != config.subplots.len() + 1 {
        return Err(invalid("panel identities must match document panels"));
    }
    for (i, panel) in meta.panels.iter().enumerate() {
        register(&panel.id)?;
        let cfg = if i == 0 {
            config
        } else {
            &config.subplots[i - 1].config
        };
        if panel.overlays.len() != cfg.overlays.len() {
            return Err(invalid("overlay identities must match document overlays"));
        }
        for id in &panel.overlays {
            register(id)?;
        }
    }
    let panel_ids: HashSet<_> = meta.panels.iter().map(|p| p.id.as_str()).collect();
    if meta.retired.iter().collect::<HashSet<_>>().len() != meta.retired.len() {
        return Err(invalid("duplicate retired identity"));
    }
    for group in meta.groups.values() {
        if !matches!(group.axis.as_str(), "x" | "y")
            || group.members.len() < 2
            || group.members.iter().collect::<HashSet<_>>().len() != group.members.len()
            || group
                .members
                .iter()
                .any(|id| !panel_ids.contains(id.as_str()))
        {
            return Err(invalid("invalid shared-axis group"));
        }
    }
    if let Some(layout) = meta.layout {
        let rows = layout.grid.len();
        let cols = layout.grid.first().map_or(0, Vec::len);
        if rows == 0 || cols == 0 || layout.grid.iter().any(|r| r.len() != cols) {
            return Err(invalid("grid must be nonempty and rectangular"));
        }
        if layout.row_weights.len() != rows
            || layout.column_weights.len() != cols
            || layout
                .row_weights
                .iter()
                .chain(&layout.column_weights)
                .any(|v| !v.is_finite() || *v <= 0.)
            || !layout.gap.is_finite()
            || layout.gap < 0.
            || layout.size.iter().any(|v| *v == 0 || *v > 8192)
        {
            return Err(invalid("invalid grid weights, size or gap"));
        }
        let mut cells: HashMap<&str, Vec<(usize, usize)>> = HashMap::new();
        for (r, row) in layout.grid.iter().enumerate() {
            for (c, slot) in row.iter().enumerate() {
                if let Some(id) = slot {
                    if id.is_empty() {
                        return Err(invalid("slot IDs must be nonempty"));
                    }
                    cells.entry(id).or_default().push((r, c));
                }
            }
        }
        for cells in cells.values() {
            let min_r = cells.iter().map(|p| p.0).min().unwrap();
            let max_r = cells.iter().map(|p| p.0).max().unwrap();
            let min_c = cells.iter().map(|p| p.1).min().unwrap();
            let max_c = cells.iter().map(|p| p.1).max().unwrap();
            if cells.len() != (max_r - min_r + 1) * (max_c - min_c + 1) {
                return Err(invalid("grid spans must be rectangular"));
            }
        }
        let placed: HashSet<_> = layout.placement.values().map(String::as_str).collect();
        if placed != panel_ids
            || placed.len() != layout.placement.len()
            || layout
                .placement
                .keys()
                .any(|id| !cells.contains_key(id.as_str()))
        {
            return Err(invalid("grid must place each subplot once in a valid slot"));
        }
    }
    Ok(())
}

impl FigureAccess<'_> {
    pub(super) fn refresh_addresses(&mut self) {
        let config = self.data.chart.config();
        let map = HitMap::for_active_layer(config);
        let panel = match config.active_layer() {
            renderer::LayerRef::Subplot(i) | renderer::LayerRef::SubplotOverlay(i, _) => {
                format!("subplot_{i}:")
            }
            _ => String::new(),
        };
        let overlay = match config.active_layer() {
            renderer::LayerRef::Overlay(i) | renderer::LayerRef::SubplotOverlay(_, i) => Some(i),
            _ => None,
        };
        let mut names = vec![
            "data_area".to_string(),
            "chart_title".into(),
            "legend".into(),
            "colorbar".into(),
            "colorbar_axis".into(),
            "colorbar_tick_labels".into(),
            "colorbar_title".into(),
        ];
        for side in ["bottom", "top", "left", "right"] {
            for prefix in ["axis_", "axis_title_", "tick_labels_"] {
                names.push(format!("{prefix}{side}"));
            }
        }
        let mut elements = Vec::new();
        for name in names {
            let local = format!("{panel}{name}");
            if let Some(id) = map.find(&local) {
                elements.push((local, id));
            }
            if let Some(overlay) = overlay {
                let local = format!("{panel}overlay_{overlay}:{name}");
                if let Some(id) = map.find(&local) {
                    elements.push((local, id));
                }
            }
        }
        self.data.hitmap = map;
        self.data.elements = elements;
    }

    pub(super) fn active_element(&self, target: &str) -> Option<HitId> {
        self.data.hitmap.find(target).or_else(|| {
            let panel = match self.data.chart.config().active_layer() {
                renderer::LayerRef::Subplot(i) | renderer::LayerRef::SubplotOverlay(i, _) => {
                    format!("subplot_{i}:")
                }
                _ => String::new(),
            };
            self.data.hitmap.find(&format!("{panel}{target}"))
        })
    }

    pub(super) fn annotation_index(&self, target: &str) -> PyResult<usize> {
        let id = target
            .strip_prefix("annotation:")
            .ok_or_else(|| invalid("unknown annotation target"))?;
        self.data
            .chart
            .config()
            .annotations
            .items
            .iter()
            .position(|a| a.id == id)
            .ok_or_else(|| invalid("annotation no longer exists"))
    }

    pub(super) fn annotation_view(&self) -> PyResult<renderer::ChartView> {
        let chart = Chart::new(gpu::config(self.data.figure_id, self.data.chart.config()));
        self.renderer
            .create_chart_view(&chart, chart.config().chart_area.0)
            .map_err(runtime)
    }
}
