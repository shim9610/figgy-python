//! GPU-free document model for a browser-owned resident renderer.
use super::*;
#[pyclass(module = "figgy._native")]
pub struct NotebookFigure {
    background: Option<Color>,
    chart: Chart,
    series: Vec<SeriesConfig>,
    columns: HashMap<String, renderer::chart::FitExtent>,
    revision: u64,
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
            background: None,
            chart: Chart::new(config),
            series: vec![],
            columns: HashMap::new(),
            revision: 0,
        })
    }
    fn upload_column(&mut self, id: &str, array: &Bound<'_, PyAny>) -> PyResult<()> {
        if self.columns.contains_key(id) {
            return Err(invalid("column ID already exists"));
        }
        let ext = if let Ok(a) = array.extract::<PyReadonlyArray1<'_, f64>>() {
            extent(a.as_slice().map_err(invalid)?)?
        } else if let Ok(a) = array.extract::<PyReadonlyArray1<'_, f32>>() {
            extent(a.as_slice().map_err(invalid)?)?
        } else {
            return Err(invalid("expected contiguous f32/f64"));
        };
        self.columns.insert(id.into(), ext);
        Ok(())
    }
    fn remove_column(&mut self, id: &str) {
        self.columns.remove(id);
    }
    fn add_series(&mut self, json: &str) -> PyResult<()> {
        let s: SeriesConfig = parse(json)?;
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
        Ok(())
    }
    fn settings_json(&self) -> PyResult<String> {
        serde_json::to_string(&Settings {
            schema_version: 1,
            renderer_version: "0.16.1".into(),
            config: self.chart.config().clone(),
            series: self.series.clone(),
            radial: None,
            background: self.background,
        })
        .map_err(runtime)
    }
    fn add_series_fitted(
        &mut self,
        json: &str,
        config: Option<&str>,
        bounds: Option<[f64; 4]>,
        preserve_x: bool,
        preserve_y: bool,
    ) -> PyResult<()> {
        let old_config = self.chart.config().clone();
        let old_series = self.series.clone();
        let revision = self.revision;
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
                if preserve_x {
                    self.chart.config_mut().bottom_x = old_config.bottom_x.clone();
                    self.chart.config_mut().top_x = old_config.top_x.clone();
                }
                if preserve_y {
                    self.chart.config_mut().left_y = old_config.left_y.clone();
                    self.chart.config_mut().right_y = old_config.right_y.clone();
                }
            }
            validate_config(self.chart.config())?;
            Ok(())
        })();
        if let Err(error) = result {
            self.chart = Chart::new(old_config);
            self.series = old_series;
            self.revision = revision;
            return Err(error);
        }
        self.revision = revision + 1;
        Ok(())
    }
    fn apply_settings(&mut self, json: &str) -> PyResult<()> {
        let mut s: Settings = parse(json)?;
        if s.schema_version != 1 || s.renderer_version != "0.16.1" {
            return Err(invalid("unsupported settings/renderer version"));
        }
        validate_config(&s.config)?;
        validate_background(s.background)?;
        if s.radial.is_some() {
            return Err(invalid(
                "pie/donut charts currently require backend='native'",
            ));
        }
        validate_draw_style(&s.config, &s.series)?;
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
        if s.series != self.series {
            renderer::legend::update_legend_symbols_preserving_text(
                &mut s.config.legend.content,
                &s.series,
            );
        }
        if s.series != self.series
            || s.config != *self.chart.config()
            || s.background != self.background
        {
            self.chart = Chart::new(s.config);
            self.series = s.series;
            self.background = s.background;
            self.revision += 1;
        }
        Ok(())
    }
    fn fit(&mut self, padding: f64) -> PyResult<()> {
        if !padding.is_finite() || padding < 0. {
            return Err(invalid("padding must be finite and non-negative"));
        }
        let mut x = renderer::chart::FitExtent::EMPTY;
        let mut y = x;
        for s in &self.series {
            x.union(&self.columns[&s.x_column]);
            y.union(&self.columns[&s.y_column]);
        }
        let mut fitted = Chart::new(self.chart.config().clone());
        fitted.auto_fit_x_extent(&x, padding);
        fitted.auto_fit_y_extent(&y, padding);
        validate_config(fitted.config())?;
        self.chart = fitted;
        self.revision += 1;
        Ok(())
    }
    fn set_range(&mut self, axis: &str, min: f64, max: f64) -> PyResult<()> {
        if !min.is_finite() || !max.is_finite() || min >= max {
            return Err(invalid("range must be finite and increasing"));
        }
        let mut next = Chart::new(self.chart.config().clone());
        match axis {
            "x" => {
                next.set_x_range(min, max);
            }
            "y" => {
                next.set_y_range(min, max);
            }
            _ => return Err(invalid("axis must be x or y")),
        };
        validate_config(next.config())?;
        self.chart = next;
        self.revision += 1;
        Ok(())
    }
    fn clear_data_selection(&mut self) {
        self.chart.config_mut().picked_data = None;
    }
    #[getter]
    fn revision(&self) -> u64 {
        self.revision
    }
    fn info_json(&self) -> String {
        json!({"backend":"webgpu","kernel_gpu":false,"columns":self.columns.len(),"allocation_mode":"resident","revision":self.revision,"rgba_readbacks":0,"png_encodes":0}).to_string()
    }
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
