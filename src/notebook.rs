//! GPU-free document model for a browser-owned resident renderer.
use super::*;
#[pyclass(module = "figgyplot._native")]
pub struct NotebookFigure {
    identity: Option<Value>,
    background: Option<Color>,
    document: Option<bounded::DocumentChart>,
    chart: Chart,
    series: Vec<SeriesConfig>,
    columns: HashMap<String, renderer::chart::FitExtent>,
    edge_samples: HashMap<String, renderer::chart::FitExtent>,
    center_cells: HashMap<String, renderer::chart::FitExtent>,
    revision: u64,
    history: edit_history::History,
    fit_extents: HashMap<String, [renderer::chart::FitExtent; 2]>,
}
#[pymethods]
impl NotebookFigure {
    #[new]
    #[pyo3(signature=(width=960,height=600,pool_bytes=8388608))]
    fn new(width: u32, height: u32, pool_bytes: u64) -> PyResult<Self> {
        let _ = pool_bytes;
        let mut config = default::default_config();
        config.chart_area = ChartArea(Rect {
            x: 0,
            y: 0,
            width,
            height,
        });
        config.legend.visible = false;
        config.right_y.out_margin = 25.;
        config.top_x.out_margin = 25.;
        validate_config(&config)?;
        Ok(Self {
            identity: None,
            background: None,
            document: None,
            chart: Chart::new(config),
            series: vec![],
            columns: HashMap::new(),
            edge_samples: HashMap::new(),
            center_cells: HashMap::new(),
            revision: 0,
            history: Default::default(),
            fit_extents: HashMap::new(),
        })
    }
    fn set_radial(&mut self, json: &str) -> PyResult<()> {
        self.set_document_model(bounded::DocumentChart::Radial(parse(json)?))
    }
    fn set_bounded(&mut self, family: &str, json: &str) -> PyResult<()> {
        self.set_document_model(match family {
            "categorical" => bounded::DocumentChart::Categorical(parse(json)?),
            "boxplot" => bounded::DocumentChart::BoxPlot(parse(json)?),
            "radar" => bounded::DocumentChart::Radar(parse(json)?),
            _ => return Err(invalid("unknown chart family")),
        })
    }
    fn upload_column(&mut self, id: &str, array: &Bound<'_, PyAny>) -> PyResult<()> {
        if self.columns.contains_key(id) {
            return Err(invalid("column ID already exists"));
        }
        let (ext, samples, cells) = if let Ok(a) = array.extract::<PyReadonlyArray1<'_, f64>>() {
            let a = a.as_slice().map_err(invalid)?;
            (extent(a)?, edge_sample_extent(a), center_cell_extent(a))
        } else if let Ok(a) = array.extract::<PyReadonlyArray1<'_, f32>>() {
            let a = a.as_slice().map_err(invalid)?;
            (extent(a)?, edge_sample_extent(a), center_cell_extent(a))
        } else {
            return Err(invalid("expected contiguous f32/f64"));
        };
        self.columns.insert(id.into(), ext);
        self.edge_samples.insert(id.into(), samples);
        self.center_cells.insert(id.into(), cells);
        Ok(())
    }
    fn remove_column(&mut self, id: &str) {
        self.columns.remove(id);
        self.edge_samples.remove(id);
        self.center_cells.remove(id);
    }
    fn add_series(&mut self, json: &str) -> PyResult<()> {
        let s: SeriesConfig = parse(json)?;
        validate_columns(
            std::slice::from_ref(&s),
            &self.columns.keys().cloned().collect(),
        )?;
        validate_model_numbers(&s, "series")?;
        if self.series.iter().any(|a| a.series_id == s.series_id) {
            return Err(invalid("series IDs must be unique"));
        }
        if !self.columns.contains_key(&s.x_column) || !self.columns.contains_key(&s.y_column) {
            return Err(invalid("unregistered source columns"));
        }
        self.series.push(s);
        if let Err(error) = validate_draw_style(self.chart.config(), &self.series) {
            self.series.pop();
            return Err(error);
        }
        self.revision += 1;
        self.history = Default::default();
        Ok(())
    }
    fn settings_json(&self) -> PyResult<String> {
        serde_json::to_string(&Settings {
            schema_version: if self.identity.is_some() { 2 } else { 1 },
            identity: self.identity.clone(),
            radar: self.document.as_ref().and_then(|r| {
                if let bounded::DocumentChart::Radar(c) = r {
                    Some(c.clone())
                } else {
                    None
                }
            }),
            renderer_version: RENDERER_VERSION.into(),
            config: self.chart.config().clone(),
            series: self.series.clone(),
            radial: self.document.as_ref().and_then(|c| c.radial().cloned()),
            categorical: self.document.as_ref().and_then(|c| {
                if let bounded::DocumentChart::Categorical(c) = c {
                    Some(c.clone())
                } else {
                    None
                }
            }),
            boxplot: self.document.as_ref().and_then(|c| {
                if let bounded::DocumentChart::BoxPlot(c) = c {
                    Some(c.clone())
                } else {
                    None
                }
            }),
            background: self.background,
        })
        .map_err(runtime)
    }
    fn add_series_fitted(
        &mut self,
        json: &str,
        config: Option<&str>,
        bounds: Option<[f64; 4]>,
    ) -> PyResult<()> {
        let old_config = self.chart.config().clone();
        let old_series = self.series.clone();
        let revision = self.revision;
        let history = self.history.clone();
        let result = (|| {
            if let Some(config) = config {
                let config = parse(config)?;
                validate_config(&config)?;
                self.chart = Chart::new(config);
            }
            self.add_series(json)?;
            if let Some([xmin, xmax, ymin, ymax]) = bounds {
                self.set_range("x", xmin, xmax)?;
                self.set_range("y", ymin, ymax)?;
            } else {
                self.fit(0.05)?;
            }
            validate_config(self.chart.config())?;
            Ok(())
        })();
        if let Err(error) = result {
            if let Ok(spec) = serde_json::from_str::<SeriesConfig>(json)
                && !old_series.iter().any(|s| s.series_id == spec.series_id)
            {
                self.fit_extents.remove(&spec.series_id);
            }
            self.chart = Chart::new(old_config);
            self.series = old_series;
            self.revision = revision;
            self.history = history;
            return Err(error);
        }
        self.revision = revision + 1;
        self.history = Default::default();
        Ok(())
    }
    fn add_series_batch(&mut self, json: &str, config: &str) -> PyResult<()> {
        let previous_config = self.chart.config().clone();
        let previous_series = self.series.clone();
        let revision = self.revision;
        let history = self.history.clone();
        let result = (|| {
            let config = parse(config)?;
            validate_config(&config)?;
            self.chart = Chart::new(config);
            for spec in parse::<Vec<SeriesConfig>>(json)? {
                self.add_series(&serde_json::to_string(&spec).map_err(invalid)?)?;
            }
            self.fit(0.05)
        })();
        if let Err(error) = result {
            self.chart = Chart::new(previous_config);
            self.series = previous_series;
            self.revision = revision;
            self.history = history;
            return Err(error);
        }
        self.revision = revision + 1;
        self.history = Default::default();
        Ok(())
    }
    fn apply_settings(&mut self, json: &str) -> PyResult<()> {
        let before: Value = serde_json::from_str(&self.settings_json()?).map_err(runtime)?;
        let base_revision = self.revision;
        let mut s: Settings = parse(json)?;
        if !self.history.restoring_identities() {
            identity::track_identities(&before, &mut s)?;
        }
        s.config.sync_subplot_links(Some(self.chart.config()));
        if !supported_settings_version(s.schema_version, &s.renderer_version) {
            return Err(invalid("unsupported settings/renderer version"));
        }
        validate_config(&s.config)?;
        validate_background(s.background)?;
        let document = s.document()?;
        if document.as_ref().map(|c| c.family()) != self.document.as_ref().map(|c| c.family()) {
            return Err(invalid("settings cannot change the Figure's chart family"));
        }
        if let Some(d) = &document {
            d.validate(s.config.chart_area.0)?;
            if !matches!(s.config.draw_style, renderer::config::DrawStyle::Precise) {
                return Err(invalid(
                    "bounded charts use materials, not Cartesian draw styles",
                ));
            }
        }
        validate_draw_style(&s.config, &s.series)?;
        validate_columns(&s.series, &self.columns.keys().cloned().collect())?;
        for series in &s.series {
            validate_model_numbers(series, "series")?;
        }
        if s.series.len() != self.series.len()
            || s.series.iter().zip(&self.series).any(|(a, b)| {
                a.series_id != b.series_id || a.x_column != b.x_column || a.y_column != b.y_column
            })
        {
            return Err(invalid(
                "settings must address the same ordered series and source columns",
            ));
        }
        if s.series != self.series
            || s.config != *self.chart.config()
            || s.config.colorbar.as_ref().map(|bar| &bar.colormap)
                != self
                    .chart
                    .config()
                    .colorbar
                    .as_ref()
                    .map(|bar| &bar.colormap)
        {
            identity::refresh_legends(&mut s.config, &s.series);
        }
        if s.series != self.series
            || s.config != *self.chart.config()
            || document != self.document
            || s.background != self.background
            || s.identity != self.identity
        {
            self.document = document;
            self.chart = Chart::new(s.config);
            self.series = s.series;
            self.background = s.background;
            self.identity = s.identity;
            self.revision += 1;
            let after: Value = serde_json::from_str(&self.settings_json()?).map_err(runtime)?;
            self.history
                .record(before, after, base_revision, self.revision, "Edit chart");
        }
        Ok(())
    }
    fn edit_history_json(&self) -> String {
        self.history.status().to_string()
    }
    fn column_extents_json(&self) -> String {
        json!(
            self.columns
                .iter()
                .map(|(name, extent)| (name.clone(), json!([extent.min, extent.max])))
                .collect::<serde_json::Map<_, _>>()
        )
        .to_string()
    }
    fn edit_operations_json(&self) -> String {
        self.history.operations().to_string()
    }
    fn begin_edit(&mut self, label: &str) -> PyResult<()> {
        let state = serde_json::from_str(&self.settings_json()?).map_err(runtime)?;
        self.history.begin(state, self.revision, label);
        Ok(())
    }
    fn end_edit(&mut self) -> PyResult<()> {
        let state = serde_json::from_str(&self.settings_json()?).map_err(runtime)?;
        self.history.finish(state, self.revision);
        Ok(())
    }
    fn undo(&mut self) -> PyResult<()> {
        self.replay_edit(false)
    }
    fn redo(&mut self) -> PyResult<()> {
        self.replay_edit(true)
    }
    fn reset_edits(&mut self) -> PyResult<()> {
        let current = serde_json::from_str(&self.settings_json()?).map_err(runtime)?;
        let target = self.history.reset_target(&current)?;
        self.begin_edit("Reset edits")?;
        self.history.set_restoring(true);
        let result = self.apply_settings(&target.to_string());
        self.history.set_restoring(false);
        self.end_edit()?;
        result
    }
    fn mark_edit_baseline(&mut self) -> PyResult<()> {
        let state = serde_json::from_str(&self.settings_json()?).map_err(runtime)?;
        self.history.mark_baseline(state)
    }
    fn cache_fit_extent(
        &mut self,
        id: String,
        x: (f64, f64, Option<f64>),
        y: (f64, f64, Option<f64>),
    ) -> PyResult<()> {
        let make = |(min, max, min_positive): (f64, f64, Option<f64>)| {
            if !min.is_finite()
                || !max.is_finite()
                || min > max
                || min_positive.is_some_and(|v| !v.is_finite() || v <= 0.)
            {
                return Err(invalid("invalid fit extent"));
            }
            Ok(renderer::chart::FitExtent {
                min,
                max,
                min_positive,
            })
        };
        self.fit_extents.insert(id, [make(x)?, make(y)?]);
        Ok(())
    }
    fn log_bounds(&self, axis: &str) -> PyResult<(f64, f64)> {
        self.log_bounds_at(
            axis,
            &serde_json::to_string(&self.chart.config().active_layer()).map_err(invalid)?,
        )
    }
    fn log_bounds_at(&self, axis: &str, layer: &str) -> PyResult<(f64, f64)> {
        let layer = parse(layer)?;
        let selected: Vec<_> = self
            .series
            .iter()
            .filter(|s| identity::fit_member(self.chart.config(), &s.series_id, axis, layer))
            .cloned()
            .collect();
        let mut extra = renderer::chart::FitExtent::EMPTY;
        if matches!(axis, "x" | "y") {
            for series in &selected {
                if !matches!(
                    series.render_type,
                    renderer::DataRenderType::ScatterErrorbarX { .. }
                        | renderer::DataRenderType::ScatterErrorbarY { .. }
                        | renderer::DataRenderType::ScatterErrorbarXY { .. }
                        | renderer::DataRenderType::LineScatterErrorbarX { .. }
                        | renderer::DataRenderType::LineScatterErrorbarY { .. }
                        | renderer::DataRenderType::LineScatterErrorbarXY { .. }
                ) {
                    continue;
                }
                if let Some(bounds) = self.fit_extents.get(&series.series_id) {
                    extra.union(&bounds[usize::from(axis == "y")]);
                }
            }
        }
        positive_data_bounds(axis, &selected, extra, |id| {
            self.columns
                .get(id)
                .copied()
                .ok_or_else(|| invalid("unknown column"))
        })
    }
    fn fit(&mut self, padding: f64) -> PyResult<()> {
        self.fit_domain(padding, false)
    }
    fn fit_active(&mut self, padding: f64) -> PyResult<()> {
        self.fit_domain(padding, true)
    }
    fn fit_domain(&mut self, padding: f64, active_only: bool) -> PyResult<()> {
        if !padding.is_finite() || padding < 0. {
            return Err(invalid("padding must be finite and non-negative"));
        }
        let mut extents = Vec::new();
        for s in &self.series {
            let [mut a, mut b] = self
                .fit_extents
                .get(&s.series_id)
                .copied()
                .unwrap_or([self.columns[&s.x_column], self.columns[&s.y_column]]);
            // Use the renderer's fit-domain classification for every matrix
            // family, including SSOT shading changes after transfer release.
            use renderer::gpu_errorbar::{GpuFieldExtentMode, GpuSeriesFitMode};
            if let Some(GpuSeriesFitMode::Field(mode)) =
                GpuSeriesFitMode::from_render_type(&s.render_type)
            {
                let columns = match mode {
                    GpuFieldExtentMode::EdgesSamples => &self.edge_samples,
                    GpuFieldExtentMode::CentersCells => &self.center_cells,
                    GpuFieldExtentMode::EdgesCells | GpuFieldExtentMode::CentersSamples => {
                        &self.columns
                    }
                };
                a = columns[&s.x_column];
                b = columns[&s.y_column];
            }
            if let renderer::DataRenderType::Histogram { bar } = &s.render_type {
                let base = renderer::chart::FitExtent {
                    min: bar.baseline,
                    max: bar.baseline,
                    min_positive: (bar.baseline > 0.).then_some(bar.baseline),
                };
                if matches!(
                    bar.orientation,
                    renderer::data_config::BarOrientation::Vertical
                ) {
                    b.union(&base);
                } else {
                    a.union(&base);
                }
            }
            extents.push([a, b]);
        }
        let fitted = document_fit::fit(
            self.chart.config(),
            &self.series,
            &extents,
            padding,
            active_only,
        );
        validate_config(&fitted)?;
        let mut state: Value = serde_json::from_str(&self.settings_json()?).map_err(runtime)?;
        state["config"] = serde_json::to_value(fitted).map_err(runtime)?;
        self.apply_settings(&state.to_string())
    }
    fn set_range(&mut self, axis: &str, min: f64, max: f64) -> PyResult<()> {
        if !min.is_finite() || !max.is_finite() || min >= max {
            return Err(invalid("range must be finite and increasing"));
        }
        let next = document_fit::set_range(self.chart.config(), axis, min, max)?;
        validate_config(&next)?;
        let mut state: Value = serde_json::from_str(&self.settings_json()?).map_err(runtime)?;
        state["config"] = serde_json::to_value(next).map_err(runtime)?;
        self.apply_settings(&state.to_string())
    }

    #[getter]
    fn revision(&self) -> u64 {
        self.revision
    }
    fn info_json(&self) -> String {
        json!({"backend":"webgpu","kernel_gpu":false,"columns":self.columns.len(),"allocation_mode":"resident","revision":self.revision,"rgba_readbacks":0,"png_encodes":0}).to_string()
    }
}
fn edge_sample_extent<T: Number>(a: &[T]) -> renderer::chart::FitExtent {
    let mut ext = renderer::chart::FitExtent::EMPTY;
    for pair in a.windows(2) {
        let value = (pair[0].f64() + pair[1].f64()) * 0.5;
        if value.is_finite() {
            ext.min = ext.min.min(value);
            ext.max = ext.max.max(value);
            if value > 0. {
                ext.min_positive = Some(ext.min_positive.map_or(value, |old| old.min(value)));
            }
        }
    }
    ext
}

fn center_cell_extent<T: Number>(a: &[T]) -> renderer::chart::FitExtent {
    if a.len() < 2 {
        return renderer::chart::FitExtent::EMPTY;
    }
    let mut result = edge_sample_extent(a);
    let last = a.len() - 1;
    for value in [
        a[0].f64() + (a[0].f64() - a[1].f64()) * 0.5,
        a[last].f64() + (a[last].f64() - a[last - 1].f64()) * 0.5,
    ] {
        if value.is_finite() {
            result.min = result.min.min(value);
            result.max = result.max.max(value);
            if value > 0. {
                result.min_positive = Some(result.min_positive.map_or(value, |old| old.min(value)));
            }
        }
    }
    result
}

fn extent<T: Number>(a: &[T]) -> PyResult<renderer::chart::FitExtent> {
    let mut ext = renderer::chart::FitExtent::EMPTY;
    for (index, n) in a.iter().enumerate() {
        let v = n.f64();
        if v.is_finite() {
            if !(v as f32).is_finite() {
                return Err(invalid(format!(
                    "data value at index {index} exceeds the f32 hi/lo representation range"
                )));
            }
            ext.min = ext.min.min(v);
            ext.max = ext.max.max(v);
            if v > 0. {
                ext.min_positive = Some(ext.min_positive.map_or(v, |old| old.min(v)));
            }
        }
    }
    if !ext.min.is_finite() {
        return Err(invalid("data has no finite values"));
    }
    Ok(ext)
}

impl NotebookFigure {
    fn replay_edit(&mut self, redo: bool) -> PyResult<()> {
        let current = serde_json::from_str(&self.settings_json()?).map_err(runtime)?;
        let target = self.history.target(redo, &current)?;
        let result = self.apply_settings(&target.to_string());
        self.history.complete(redo, result.is_ok());
        result
    }
    fn set_document_model(&mut self, document: bounded::DocumentChart) -> PyResult<()> {
        if self
            .document
            .as_ref()
            .is_some_and(|d| d.family() == document.family())
        {
            let mut state: Value = serde_json::from_str(&self.settings_json()?).map_err(runtime)?;
            state[document.family()] = document.value();
            return self.apply_settings(&state.to_string());
        }
        if !self.series.is_empty()
            || !self.columns.is_empty()
            || !self.chart.config().subplots.is_empty()
            || !self.chart.config().overlays.is_empty()
            || self.chart.config().polar.is_some()
        {
            return Err(invalid("create a separate Figure for bounded charts"));
        }
        if !matches!(
            self.chart.config().draw_style,
            renderer::config::DrawStyle::Precise
        ) {
            return Err(invalid(
                "bounded charts use materials, not Cartesian draw styles",
            ));
        }
        if self
            .document
            .as_ref()
            .is_some_and(|d| d.family() != document.family())
        {
            return Err(invalid("cannot change chart family"));
        }
        document.validate(self.chart.config().chart_area.0)?;
        self.document = Some(document);
        self.revision += 1;
        self.history = Default::default();
        Ok(())
    }
}
