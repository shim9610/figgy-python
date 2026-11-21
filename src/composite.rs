//! Borrow NumPy buffers only for the duration of a composite GPU upload.
use super::*;
use pyo3::types::PyDict;
use renderer::data::ColumnSource;
enum Array<'py> {
    F32(PyReadonlyArray1<'py, f32>),
    F64(PyReadonlyArray1<'py, f64>),
    U32(PyReadonlyArray1<'py, u32>),
}
impl<'py> Array<'py> {
    fn extract(v: &Bound<'py, PyAny>) -> PyResult<Self> {
        if let Ok(a) = v.extract::<PyReadonlyArray1<'py, f32>>() {
            a.as_slice().map_err(invalid)?;
            return Ok(Self::F32(a));
        }
        if let Ok(a) = v.extract::<PyReadonlyArray1<'py, f64>>() {
            a.as_slice().map_err(invalid)?;
            return Ok(Self::F64(a));
        }
        if let Ok(a) = v.extract::<PyReadonlyArray1<'py, u32>>() {
            a.as_slice().map_err(invalid)?;
            return Ok(Self::U32(a));
        }
        Err(invalid(
            "composite fields require contiguous one-dimensional f32, f64 or u32 arrays",
        ))
    }
}
impl ColumnSource for Array<'_> {
    fn len(&self) -> usize {
        match self {
            Self::F32(a) => a.as_slice().unwrap().len(),
            Self::F64(a) => a.as_slice().unwrap().len(),
            Self::U32(a) => a.as_slice().unwrap().len(),
        }
    }
    fn write_pairs(&self, dst: &mut ColumnPairWriter<'_>) {
        match self {
            Self::F32(a) => {
                for (i, v) in a.as_slice().unwrap().iter().enumerate() {
                    dst.write_pair(i, *v, 0.);
                }
            }
            Self::F64(a) => {
                for (i, v) in a.as_slice().unwrap().iter().enumerate() {
                    let (h, l) = split_f64_to_f32_pair(*v);
                    dst.write_pair(i, h, l);
                }
            }
            Self::U32(a) => {
                for (i, v) in a.as_slice().unwrap().iter().enumerate() {
                    let (h, l) = split_f64_to_f32_pair(*v as f64);
                    dst.write_pair(i, h, l);
                }
            }
        }
    }
}
impl FigureAccess<'_> {
    pub(super) fn upload_composite(
        &mut self,
        kind: &str,
        id: &str,
        data: &Bound<'_, PyDict>,
    ) -> PyResult<()> {
        if self.data.columns.contains_key(id) {
            return Err(invalid("resource ID already exists"));
        }
        let arrays = data
            .iter()
            .map(|(k, v)| Ok((k.extract::<String>()?, Array::extract(&v)?)))
            .collect::<PyResult<Vec<_>>>()?;
        let fields = arrays
            .iter()
            .map(|(k, v)| (k.as_str(), v as &dyn ColumnSource))
            .collect::<Vec<_>>();
        let field = |name: &str| {
            fields
                .iter()
                .find(|(k, _)| *k == name)
                .map(|(_, v)| *v)
                .ok_or_else(|| invalid(format!("missing composite field {name}")))
        };
        let gid = gpu::column_id(self.data.figure_id, id);
        let _rows = match kind {
            "record" => {
                self.renderer
                    .upsert_record(
                        gid,
                        &renderer::RecordSource {
                            schema: renderer::BOX_PLOT_RECORD,
                            fields: &fields,
                        },
                    )
                    .map_err(invalid)?;
                fields.first().map_or(0, |(_, v)| v.len())
            }
            "ragged" => {
                self.renderer
                    .upsert_ragged(
                        gid,
                        &renderer::RaggedSource {
                            values: field("values")?,
                            offsets: field("offsets")?,
                        },
                    )
                    .map_err(invalid)?;
                field("offsets")?.len().saturating_sub(1)
            }
            "triangles" => {
                self.renderer
                    .upsert_triangles(
                        gid,
                        &renderer::TriangleSource {
                            indices: field("indices")?,
                        },
                    )
                    .map_err(invalid)?;
                field("indices")?.len() / 3
            }
            _ => return Err(invalid("unknown composite kind")),
        };
        self.data.columns.insert(
            id.into(),
            (arrays.iter().map(|(_, array)| array.len()).sum(), 0., 0.),
        );
        self.data.uploads += 1;
        Ok(())
    }
    pub(super) fn export_format(&mut self, format: &str, scale: f32) -> PyResult<Vec<u8>> {
        if format == "png" {
            if !scale.is_finite() || !(0.25..=8.).contains(&scale) {
                return Err(invalid("scale must be 0.25..8"));
            }
            self.data.png_encodes += 1;
            return encode_png(&self.render(scale)?).map_err(runtime);
        }
        let format = match format {
            "svg" => renderer::ExportFormat::Svg,
            "pdf" => renderer::ExportFormat::Pdf,
            "png" => renderer::ExportFormat::Png,
            _ => return Err(invalid("format must be png, svg or pdf")),
        };
        if !scale.is_finite() || scale <= 0. {
            return Err(invalid("export scale must be positive and finite"));
        }
        let options = renderer::ExportOptions::document(scale)
            .with_clear(self.data.background.unwrap_or(Color::WHITE));
        if self.data.document.is_some() {
            let area = self.data.chart.config().chart_area.0;
            let doc = self.document_renderer()?;
            let (bounded::DocumentRenderer::Radial(r), bounded::DocumentChart::Radial(c)) =
                (doc.renderer.as_mut().unwrap(), &doc.chart)
            else {
                return Err(invalid("legacy chart requires migration"));
            };
            let bytes = r
                .export_bytes_blocking(c, (area.width, area.height), options, format)
                .map_err(runtime)?;
            return self.physical_export(bytes, format);
        }
        let chart = Chart::new(gpu::config(self.data.figure_id, self.data.chart.config()));
        let series = gpu::series(self.data.figure_id, &self.data.series);
        let bytes = self
            .renderer
            .export_bytes_blocking(
                renderer::ExportSource::Chart {
                    chart: &chart,
                    series: &series,
                },
                options,
                format,
            )
            .map_err(runtime)?;
        self.physical_export(bytes, format)
    }
    fn physical_export(&self, data: Vec<u8>, format: renderer::ExportFormat) -> PyResult<Vec<u8>> {
        let name = match format {
            renderer::ExportFormat::Svg => "svg",
            renderer::ExportFormat::Pdf => "pdf",
            _ => return Ok(data),
        };
        Python::attach(|py| {
            py.import("figgyplot._export_size")?
                .getattr("physical_size")?
                .call1((PyBytes::new(py, &data), name, self.data.code_dpi))?
                .extract()
        })
    }
}
