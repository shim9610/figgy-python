//! Inspect only the selected GPU samples; never retain source arrays on CPU.
use super::*;
use renderer::config::PickedDataRef;

impl FigureAccess<'_> {
    fn read_samples(&mut self, samples: &[(String, usize)]) -> PyResult<Vec<f64>> {
        let offsets = samples
            .iter()
            .map(|(column, index)| {
                let handle = self
                    .renderer
                    .pool()
                    .handle_for(&gpu::column_id(self.data.figure_id, column))
                    .ok_or_else(|| invalid("selected column no longer exists"))?;
                if *index >= handle.len_values {
                    return Err(invalid("selected index is outside the column"));
                }
                Ok(handle.offset + *index as u64 * 8)
            })
            .collect::<PyResult<Vec<_>>>()?;
        let buffer = self
            .renderer
            .device()
            .create_buffer(&wgpu::BufferDescriptor {
                label: Some("figgy selected values"),
                size: offsets.len() as u64 * 8,
                usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
                mapped_at_creation: false,
            });
        let mut encoder = self
            .renderer
            .device()
            .create_command_encoder(&Default::default());
        for (index, offset) in offsets.iter().enumerate() {
            encoder.copy_buffer_to_buffer(
                self.renderer.pool().buffer(),
                *offset,
                &buffer,
                index as u64 * 8,
                8,
            );
        }
        self.renderer.queue().submit([encoder.finish()]);
        let slice = buffer.slice(..);
        let (tx, rx) = std::sync::mpsc::channel();
        slice.map_async(wgpu::MapMode::Read, move |result| {
            let _ = tx.send(result);
        });
        self.renderer.wait_idle();
        rx.recv().map_err(runtime)?.map_err(runtime)?;
        let mapped = slice.get_mapped_range().map_err(runtime)?;
        let values = mapped
            .chunks_exact(8)
            .map(|p| {
                f32::from_le_bytes(p[..4].try_into().unwrap()) as f64
                    + f32::from_le_bytes(p[4..].try_into().unwrap()) as f64
            })
            .collect();
        drop(mapped);
        buffer.unmap();
        self.data.selection_value_readbacks += 1;
        Ok(values)
    }

    pub(crate) fn selection_details(&mut self, reference: &PickedDataRef) -> PyResult<Value> {
        let series = self
            .data
            .series
            .iter()
            .find(|s| s.series_id == reference.series_id())
            .cloned()
            .ok_or_else(|| invalid("selected series no longer exists"))?;
        let mut result = json!({"identity":reference, "series_id":series.series_id});
        match reference {
            PickedDataRef::Point { point_index, .. } => {
                let values = self.read_samples(&[
                    (series.x_column, *point_index),
                    (series.y_column, *point_index),
                ])?;
                result["index"] = json!(point_index);
                result["x"] = json!(values[0]);
                result["y"] = json!(values[1]);
            }
            PickedDataRef::HistogramBin { bin_index, .. } => {
                let renderer::DataRenderType::Histogram { bar } = &series.render_type else {
                    return Err(invalid("selected series is not a histogram"));
                };
                let (edges, values) = match bar.orientation {
                    renderer::data_config::BarOrientation::Vertical => {
                        (&series.x_column, &series.y_column)
                    }
                    renderer::data_config::BarOrientation::Horizontal => {
                        (&series.y_column, &series.x_column)
                    }
                };
                let samples = self.read_samples(&[
                    (edges.clone(), *bin_index),
                    (edges.clone(), bin_index + 1),
                    (values.clone(), *bin_index),
                ])?;
                result["index"] = json!(bin_index);
                result["bin_start"] = json!(samples[0]);
                result["bin_end"] = json!(samples[1]);
                // Histograms, weighted/density histograms and stairs share the
                // same renderer type. The stored height is not always a count.
                result["value"] = json!(samples[2]);
                result["orientation"] = json!(bar.orientation);
            }
            PickedDataRef::MatrixCell {
                x_index, y_index, ..
            } => {
                let style = serde_json::to_value(&series.render_type).map_err(runtime)?;
                let matrix = &style.as_object().unwrap().values().next().unwrap()["matrix"];
                let across_x = matrix["orientation"] == "ColumnsAreY";
                let column_index = if across_x { *y_index } else { *x_index };
                let sample_index = if across_x { *x_index } else { *y_index };
                let column = matrix["columns"][column_index]
                    .as_str()
                    .ok_or_else(|| invalid("selected cell no longer exists"))?;
                let mut samples = vec![
                    (series.x_column.clone(), *x_index),
                    (series.y_column.clone(), *y_index),
                    (column.into(), sample_index),
                ];
                let edges = matrix["grid_layout"] == "Edges";
                if edges {
                    samples.extend([
                        (series.x_column, x_index + 1),
                        (series.y_column, y_index + 1),
                    ]);
                }
                let values = self.read_samples(&samples)?;
                result["x_index"] = json!(x_index);
                result["y_index"] = json!(y_index);
                result["x"] = json!(if edges {
                    (values[0] + values[3]) * 0.5
                } else {
                    values[0]
                });
                result["y"] = json!(if edges {
                    (values[1] + values[4]) * 0.5
                } else {
                    values[1]
                });
                result["value"] = json!(values[2]);
            }
            _ => {}
        }
        Ok(result)
    }

    pub(crate) fn step_selection(&mut self, dx: i32, dy: i32) -> PyResult<bool> {
        let mut cfg = self.data.chart.config().clone();
        let Some(reference) = cfg.picked_data.as_mut().and_then(|s| s.refs.first_mut()) else {
            return Ok(false);
        };
        let Some(position) = self
            .data
            .series
            .iter()
            .position(|s| s.series_id == reference.series_id())
        else {
            return Ok(false);
        };
        let shift = |index: usize, delta: i32, count: usize| {
            index
                .saturating_add_signed(delta as isize)
                .min(count.saturating_sub(1))
        };
        match reference {
            PickedDataRef::Point {
                series_id,
                source_id,
                point_index,
            } => {
                let points = self
                    .data
                    .series
                    .iter()
                    .filter(|s| {
                        let style = serde_json::to_value(&s.render_type).unwrap();
                        style
                            .as_object()
                            .unwrap()
                            .values()
                            .next()
                            .is_some_and(|v| v["line"].is_object() || v["scatter"].is_object())
                    })
                    .collect::<Vec<_>>();
                let Some(index) = points.iter().position(|s| s.series_id == *series_id) else {
                    return Ok(false);
                };
                let series = points[shift(index, dy, points.len())];
                let count = self.data.columns[&series.x_column]
                    .0
                    .min(self.data.columns[&series.y_column].0);
                *series_id = series.series_id.clone();
                *source_id = series.source_id.clone();
                *point_index = shift(*point_index, dx, count);
            }
            PickedDataRef::HistogramBin {
                series_id,
                source_id,
                bin_index,
            } => {
                let renderer::DataRenderType::Histogram { bar } =
                    &self.data.series[position].render_type
                else {
                    return Ok(false);
                };
                let horizontal = matches!(
                    bar.orientation,
                    renderer::data_config::BarOrientation::Horizontal
                );
                let histograms = self
                    .data
                    .series
                    .iter()
                    .filter(|s| {
                        matches!(&s.render_type,
                        renderer::DataRenderType::Histogram { bar: other }
                        if other.orientation == bar.orientation)
                    })
                    .collect::<Vec<_>>();
                let index = histograms
                    .iter()
                    .position(|s| s.series_id == *series_id)
                    .unwrap();
                let (bin_delta, series_delta) = if horizontal { (dy, dx) } else { (dx, dy) };
                let series = histograms[shift(index, series_delta, histograms.len())];
                let (edges, values) = if horizontal {
                    (&series.y_column, &series.x_column)
                } else {
                    (&series.x_column, &series.y_column)
                };
                let count = self.data.columns[edges]
                    .0
                    .saturating_sub(1)
                    .min(self.data.columns[values].0);
                if count == 0 {
                    return Ok(false);
                }
                *series_id = series.series_id.clone();
                *source_id = series.source_id.clone();
                *bin_index = shift(*bin_index, bin_delta, count);
            }
            PickedDataRef::MatrixCell {
                x_index, y_index, ..
            } => {
                let series = &self.data.series[position];
                let style = serde_json::to_value(&series.render_type).map_err(runtime)?;
                let matrix = &style.as_object().unwrap().values().next().unwrap()["matrix"];
                let edges = usize::from(matrix["grid_layout"] == "Edges");
                let columns = matrix["columns"]
                    .as_array()
                    .ok_or_else(|| invalid("selected matrix no longer exists"))?;
                let depth = columns
                    .iter()
                    .filter_map(|c| self.data.columns.get(c.as_str()?))
                    .map(|c| c.0)
                    .min()
                    .unwrap_or(0);
                let (nx, ny) = if matrix["orientation"] == "ColumnsAreY" {
                    (depth, columns.len())
                } else {
                    (columns.len(), depth)
                };
                *x_index = shift(
                    *x_index,
                    dx,
                    nx.min(self.data.columns[&series.x_column].0.saturating_sub(edges)),
                );
                *y_index = shift(
                    *y_index,
                    dy,
                    ny.min(self.data.columns[&series.y_column].0.saturating_sub(edges)),
                );
            }
            _ => return Ok(false),
        }
        if cfg == *self.data.chart.config() {
            return Ok(false);
        }
        self.commit_config(cfg)?;
        Ok(true)
    }
}
