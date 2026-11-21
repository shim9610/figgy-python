#![allow(deprecated)]
//! Public model helpers shared by Python, native editing and notebook editing.
use super::*;
use renderer::data_config::MatrixRef;
use renderer::theme::{Theme, ThemeScope};

#[pyfunction]
pub fn series_template_json(kind: &str) -> PyResult<String> {
    if kind == "surface_style" {
        return serde_json::to_string(&renderer::view3d::SurfaceStyle::default()).map_err(runtime);
    }
    let matrix = || MatrixRef::columns_are_y(["values"]);
    let s = match kind {
        "stem" => SeriesConfig::stem("s", "x", "y"),
        "streamlines" => SeriesConfig::streamlines("s", "x", "y"),
        "category_bars" => SeriesConfig::category_bars("s", "x", "y"),
        "box_plot" => SeriesConfig::box_plot("s", "x", "y"),
        "range_bars" => SeriesConfig::range_bars("s", "x", "start", "y"),
        "range_links" => SeriesConfig::range_links("s", "bars", []),
        "radar" => SeriesConfig::radar("s", "x", "y"),
        "ternary" => SeriesConfig::ternary("s", "x", "y", "c"),
        "parallel" => SeriesConfig::parallel("s", ["x", "y"]),
        "rgb_image" => SeriesConfig::rgb_image("s", "x", "y", matrix(), matrix(), matrix()),
        "hexbin" => SeriesConfig::hexbin("s", "x", "y", matrix()),
        "tri_mesh" => SeriesConfig::tri_mesh(
            "s",
            "x",
            "y",
            "triangles",
            renderer::tri_mesh::MeshValues {
                column: "values".into(),
                at: renderer::tri_mesh::MeshValueLocation::Vertices,
            },
        ),
        "energy_levels" => SeriesConfig::energy_levels("s", Default::default()),
        "feynman" => SeriesConfig::feynman("s", Default::default()),
        _ => return Err(invalid("unknown series template")),
    };
    let mut value = serde_json::to_value(&s).map_err(runtime)?;
    match kind {
        "energy_levels" => {
            value["render_type"]["EnergyLevels"]["style"] =
                serde_json::to_value(renderer::energy_levels::EnergyLevelSeries::default().style)
                    .map_err(runtime)?
        }
        "feynman" => {
            value["render_type"]["Feynman"]["style"] =
                serde_json::to_value(renderer::feynman::FeynmanSeries::default().style)
                    .map_err(runtime)?
        }
        _ => {}
    }
    serde_json::to_string(&value).map_err(runtime)
}
#[pyfunction]
pub fn coordinate_defaults_json(kind: &str) -> PyResult<String> {
    let mut config = default::default_config();
    match kind {
        "polar" => config.set_polar(Some(Default::default())),
        "ternary" => config.set_ternary(Some(Default::default())),
        "3d" => config.set_view_3d(Some(Default::default())),
        "parallel" => config.set_parallel(Some(Default::default())),
        _ => return Err(invalid("unknown projection")),
    };
    serde_json::to_string(&config).map_err(runtime)
}
#[pyfunction]
pub fn transform_settings_json(
    settings: &str,
    operation: &str,
    argument: &str,
) -> PyResult<String> {
    let mut state: Settings = parse(settings)?;
    if operation == "annotation_offset" {
        use renderer::drag::DragConfig;
        use renderer::text::MeasureText;
        let arg: Value = parse(argument)?;
        let panel = arg["panel"]
            .as_u64()
            .ok_or_else(|| invalid("missing panel"))? as usize;
        let index = arg["index"]
            .as_u64()
            .ok_or_else(|| invalid("missing annotation index"))? as usize;
        let cfg = if panel == 0 {
            &mut state.config
        } else {
            &mut state
                .config
                .subplots
                .get_mut(panel - 1)
                .ok_or_else(|| invalid("unknown panel"))?
                .config
        };
        let item = cfg
            .annotations
            .items
            .get(index)
            .ok_or_else(|| invalid("annotation index out of range"))?;
        let measure = CpuTextMeasure::for_style(&cfg.draw_style);
        use renderer::annotation::{AnnotationElement, AnnotationKind, MeasuredText};
        let (rich, padding) = match &item.kind {
            AnnotationKind::Text {
                text, box_style, ..
            } => (Some(text), box_style.as_ref().map_or(0., |s| s.padding)),
            AnnotationKind::Arrow { text, .. } => (text.as_ref(), 0.),
            AnnotationKind::ReferenceLine { label, .. } => (label.as_ref(), 0.),
            _ => (None, 0.),
        };
        let text = rich.map(|rt| {
            let e = measure.measure_rich(rt);
            MeasuredText {
                size: [e.width + padding * 2., e.ascent + e.descent + padding * 2.],
                ascent: e.ascent,
                padding,
                em: rt.font_size,
            }
        });
        let element = AnnotationElement {
            index,
            space: renderer::annotation::pixel_space_for_config(cfg),
            text,
            handle: None,
        };
        let number = |key: &str| {
            arg[key]
                .as_f64()
                .filter(|v| v.is_finite())
                .map(|v| v as f32)
                .ok_or_else(|| invalid("offset must be finite"))
        };
        let result = cfg
            .annotations
            .nudge(element, &measure, number("dx")?, number("dy")?);
        if result != renderer::layout::NudgeResult::Moved {
            return Err(invalid(format!("annotation move rejected: {result:?}")));
        }
        return serde_json::to_string(&state).map_err(runtime);
    }
    if let Some(radial) = state.radial.as_mut() {
        if operation == "theme" {
            radial.apply_theme(argument).map_err(invalid)?;
            state.background = Some(radial.background);
        } else if operation == "layout" {
            radial.decorations.data_area = None;
        } else {
            return Err(invalid("unknown document operation"));
        }
    } else {
        let mut chart = Chart::new(state.config);
        match operation {
            "theme" => {
                Theme::apply_named(
                    argument,
                    chart.config_mut(),
                    &mut state.series,
                    ThemeScope::All,
                )
                .map_err(invalid)?;
                chart.fit_layout();
                state.background = chart.config().background;
            }
            "layout" => chart.fit_layout(),
            _ => return Err(invalid("unknown document operation")),
        }
        state.config = chart.config().clone();
    }
    serde_json::to_string(&state).map_err(runtime)
}
#[pyfunction]
pub fn convert_legacy_chart_json(kind: &str, input: &str) -> PyResult<String> {
    use renderer::{SeriesUpload, UploadValues};
    fn bundle(
        mut config: Config,
        series: Vec<SeriesConfig>,
        uploads: Vec<SeriesUpload<'_>>,
        background: Color,
    ) -> PyResult<String> {
        let values = |column: &renderer::BoxColumn<'_>| {
            (0..column.len())
                .map(|i| json!(column.value(i)))
                .collect::<Vec<_>>()
        };
        let mut columns = vec![];
        for upload in uploads {
            let id = upload.column;
            match upload.values {
                UploadValues::BoxRecord(_)=>{
                    let fields=upload.values.box_fields().unwrap();
                    let data=renderer::BOX_PLOT_RECORD.iter().zip(fields).map(|((name,_),column)|(name.to_string(),json!(values(&column)))).collect::<serde_json::Map<_,_>>();
                    columns.push(json!({"kind":"record","id":id,"data":data}));
                },
                UploadValues::BoxOutliers(_)=>{
                    let (v,o)=upload.values.box_outliers().unwrap();
                    columns.push(json!({"kind":"ragged","id":id,"data":{"values":values(&v),"offsets":values(&o)}}));
                },
                _=>columns.push(json!({"kind":"column","id":id,"data":(0..upload.values.len()).map(|i|json!(upload.values.value(i))).collect::<Vec<_>>()})),
            }
        }
        config.background = Some(background);
        serde_json::to_string(&json!({"config":config,"series":series,"uploads":columns}))
            .map_err(runtime)
    }
    match kind {
        "categorical" => {
            let c: renderer::CategoricalChart = parse(input)?;
            c.validate().map_err(invalid)?;
            let (cfg, s, u) = Config::from_categorical(&c);
            bundle(cfg, s, u, c.background)
        }
        "boxplot" => {
            let c: renderer::BoxPlotChart = parse(input)?;
            c.validate().map_err(invalid)?;
            let (cfg, s, u) = Config::from_boxplot(&c);
            bundle(cfg, s, u, c.background)
        }
        "radar" => {
            let c: renderer::RadarChart = parse(input)?;
            c.validate().map_err(invalid)?;
            let (cfg, s, u) = Config::from_radar(&c);
            bundle(cfg, s, u, c.background)
        }
        _ => Err(invalid("unknown legacy chart")),
    }
}

#[pyfunction]
pub fn format_radial_labels_json(input: &str) -> PyResult<String> {
    let mut chart: renderer::RadialChart = parse(input)?;
    chart.format_labels();
    serde_json::to_string(&chart).map_err(runtime)
}
