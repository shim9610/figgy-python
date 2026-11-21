//! Small selected-record readbacks for column-backed chart families.
use super::*;
use renderer::config::PickedDataRef;
impl FigureAccess<'_> {
    pub(super) fn selection_category(
        &self,
        series: &SeriesConfig,
        index: usize,
        result: &mut Value,
    ) {
        let cfg = self.data.chart.config();
        let layer = cfg.layer_of_series(&series.series_id);
        let panel = match layer {
            renderer::LayerRef::Subplot(i) | renderer::LayerRef::SubplotOverlay(i, _) => {
                &cfg.subplots[i].config
            }
            _ => cfg,
        };
        let overlay = match layer {
            renderer::LayerRef::Overlay(i) | renderer::LayerRef::SubplotOverlay(_, i) => Some(i),
            _ => None,
        };
        let (x, y) = panel.scaling_axes(overlay);
        let groups = cfg.bar_groups_of(layer);
        let axis = if series.render_type.radar().is_some() {
            &panel.bottom_x
        } else if groups.direction == renderer::CategoryBarDirection::Horizontal {
            y
        } else {
            x
        };
        if let Some(category) = axis.categories.as_ref().and_then(|v| v.get(index)) {
            result["category_id"] = json!(category.id);
            result["category_label"] = json!(category.label);
        }
        result["direction"] = json!(groups.direction);
    }
    pub(super) fn selection_019(
        &mut self,
        reference: &PickedDataRef,
        series: &SeriesConfig,
        result: &mut Value,
    ) -> PyResult<bool> {
        let wire = if let Some(levels) = series.render_type.energy_levels() {
            serde_json::to_value(
                renderer::energy_level_records(levels, &self.data.series).ok_or_else(|| {
                    invalid("the energy-level source names no series with records")
                })?,
            )
            .map_err(runtime)?
        } else {
            serde_json::to_value(&series.render_type).map_err(runtime)?
        };
        let wire = if series.render_type.energy_levels().is_some() {
            json!({"EnergyLevels": wire})
        } else {
            wire
        };
        let body = wire.as_object().unwrap().values().next().unwrap();
        match reference {
            PickedDataRef::HistogramBin { bin_index, .. }
                if series.render_type.energy_levels().is_some() =>
            {
                let row = body["levels"]
                    .get(*bin_index)
                    .filter(|v| v.is_object())
                    .ok_or_else(|| invalid("selected level no longer exists"))?;
                result["index"] = json!(bin_index);
                result["part"] = json!("level");
                result["id"] = row["id"].clone();
                result["record"] = row.clone();
            }
            PickedDataRef::Point { point_index, .. }
                if series.render_type.energy_levels().is_some() =>
            {
                let row = body["transitions"]
                    .get(*point_index)
                    .filter(|v| v.is_object())
                    .ok_or_else(|| invalid("selected transition no longer exists"))?;
                result["index"] = json!(point_index);
                result["part"] = json!("transition");
                result["id"] = row["id"].clone();
                result["record"] = row.clone();
            }
            PickedDataRef::Point { point_index, .. }
                if series
                    .render_type
                    .box_plot()
                    .is_some_and(|b| b.points.is_some()) =>
            {
                let points = series
                    .render_type
                    .box_plot()
                    .unwrap()
                    .points
                    .as_ref()
                    .unwrap();
                let values = self.read_samples(&[
                    (points.positions.clone(), *point_index),
                    (points.values.clone(), *point_index),
                ])?;
                result["index"] = json!(point_index);
                result["position"] = json!(values[0]);
                result["value"] = json!(values[1]);
                if values[0].is_finite() && values[0] >= 0. {
                    self.selection_category(series, values[0].round() as usize, result);
                }
            }
            PickedDataRef::HistogramBin {
                bin_index, half, ..
            } if series.render_type.box_plot().is_some() => {
                self.selection_category(series, *bin_index, result);
                result["index"] = json!(bin_index);
                if let Some(half) = half {
                    result["half"] = json!(half);
                }
                let (_, id) = series.box_plot_columns();
                if !id.is_empty() {
                    let record = self
                        .renderer
                        .pool()
                        .record(&gpu::column_id(self.data.figure_id, id))
                        .ok_or_else(|| invalid("selected record no longer exists"))?;
                    let fields = renderer::BOX_PLOT_RECORD
                        .iter()
                        .enumerate()
                        .filter_map(|(i, (name, _))| {
                            record.slot().fields[i]
                                .as_ref()
                                .map(|id| (*name, id.clone()))
                        })
                        .collect::<Vec<_>>();
                    let samples = fields
                        .iter()
                        .map(|(_, id)| (id.clone(), *bin_index))
                        .collect::<Vec<_>>();
                    for ((name, _), value) in
                        fields.iter().zip(self.read_gpu_samples(&samples, false)?)
                    {
                        result[*name] = json!(value);
                    }
                }
            }
            PickedDataRef::HistogramBin { bin_index, .. }
                if series.render_type.category_bars().is_some() =>
            {
                let cfg = self.data.chart.config();
                let groups = cfg.bar_groups_of(cfg.layer_of_series(&series.series_id));
                let (_, values) = series.category_bar_columns(groups.direction);
                result["mode"] = json!(groups.mode);
                result["index"] = json!(bin_index);
                result["value"] = json!(self.read_samples(&[(values.into(), *bin_index)])?[0]);
                self.selection_category(series, *bin_index, result);
            }
            PickedDataRef::HistogramBin { bin_index, .. }
                if series.render_type.range_bars().is_some() =>
            {
                let mut fields = vec![
                    ("position", series.x_column.clone()),
                    ("end", series.y_column.clone()),
                    ("start", body["start"].as_str().unwrap().to_owned()),
                ];
                for (name, path) in [
                    ("low", &body["whiskers"]["low"]),
                    ("high", &body["whiskers"]["high"]),
                    ("progress", &body["progress"]["column"]),
                    ("state", &body["color_by"]["State"]["column"]),
                    ("total", &body["color_by"]["Direction"]["total"]["column"]),
                ] {
                    if let Some(id) = path.as_str() {
                        fields.push((name, id.into()));
                    }
                }
                let samples = fields
                    .iter()
                    .map(|(_, id)| (id.clone(), *bin_index))
                    .collect::<Vec<_>>();
                let values = self.read_samples(&samples)?;
                result["index"] = json!(bin_index);
                self.selection_category(series, values[0].round().max(0.) as usize, result);
                for ((name, _), value) in fields.iter().zip(values) {
                    result[*name] = json!(value);
                }
            }
            PickedDataRef::ValueLabel {
                category_index,
                part,
                ..
            } => {
                result["index"] = json!(category_index);
                if let Some(part) = part {
                    let key = match part {
                        renderer::energy_levels::LabelPart::Level => "levels",
                        renderer::energy_levels::LabelPart::Transition => "transitions",
                        renderer::energy_levels::LabelPart::Limit => "limits",
                        renderer::energy_levels::LabelPart::Band => "bands",
                    };
                    result["part"] = json!(part);
                    result["record"] = body[key][*category_index].clone();
                } else {
                    self.selection_category(series, *category_index, result);
                    result["text"] = json!(
                        series
                            .value_label_text()
                            .and_then(|v| v.get(*category_index))
                    );
                    result["offset"] = json!(series.value_label_offset(*category_index));
                }
            }
            PickedDataRef::ContourLevel {
                level_index,
                x_index,
                y_index,
                ..
            } => {
                result["index"] = json!(level_index);
                result["value"] = body["contour"]["levels"][*level_index].clone();
                result["x_index"] = json!(x_index);
                result["y_index"] = json!(y_index);
            }
            PickedDataRef::FeynmanVertex { vertex_index, .. } => {
                let diagram = series
                    .render_type
                    .feynman()
                    .ok_or_else(|| invalid("selected series is not a diagram"))?;
                let vertex = diagram
                    .vertices
                    .get(*vertex_index)
                    .ok_or_else(|| invalid("selected vertex no longer exists"))?;
                result["index"] = json!(vertex_index);
                result["id"] = json!(vertex.id);
                result["role"] = json!(vertex.role);
                result["placed"] = json!(vertex.at.is_some());
                result["position"] = json!(match vertex.at {
                    Some(at) => at,
                    None => diagram.positions().map_err(invalid)?[*vertex_index],
                });
            }
            PickedDataRef::FeynmanPropagator {
                propagator_index, ..
            } => {
                result["index"] = json!(propagator_index);
                result["propagator"] = body["propagators"][*propagator_index].clone();
            }
            PickedDataRef::FeynmanLabel { part, index, .. } => {
                result["index"] = json!(index);
                result["part"] = json!(part);
            }
            PickedDataRef::MeshTriangle { triangle_index, .. } => {
                let mesh = series
                    .render_type
                    .tri_mesh()
                    .ok_or_else(|| invalid("selected series is not a mesh"))?;
                let member = self
                    .renderer
                    .pool()
                    .triangles(&gpu::column_id(self.data.figure_id, &mesh.triangles))
                    .ok_or_else(|| invalid("selected triangles no longer exist"))?
                    .slot()
                    .indices
                    .clone();
                let first = triangle_index
                    .checked_mul(3)
                    .ok_or_else(|| invalid("triangle index is out of range"))?;
                first
                    .checked_add(2)
                    .ok_or_else(|| invalid("triangle index is out of range"))?;
                let corners = self.read_gpu_samples(
                    &(0..3)
                        .map(|i| (member.clone(), first + i))
                        .collect::<Vec<_>>(),
                    true,
                )?;
                result["index"] = json!(triangle_index);
                result["vertices"] = json!(corners);
                for (name, id) in [
                    ("x", Some(&series.x_column)),
                    ("y", Some(&series.y_column)),
                    ("z", series.z_column.as_ref()),
                ] {
                    if let Some(id) = id {
                        result[name] = json!(
                            self.read_samples(
                                &corners
                                    .iter()
                                    .map(|v| (id.clone(), *v as usize))
                                    .collect::<Vec<_>>()
                            )?
                        );
                    }
                }
                result["at"] = json!(mesh.values.at);
                if mesh.values.at == renderer::tri_mesh::MeshValueLocation::Faces {
                    result["value"] = json!(
                        self.read_samples(&[(mesh.values.column.clone(), *triangle_index)])?[0]
                    );
                } else {
                    result["values"] = json!(
                        self.read_samples(
                            &corners
                                .iter()
                                .map(|v| (mesh.values.column.clone(), *v as usize))
                                .collect::<Vec<_>>()
                        )?
                    );
                }
            }
            _ => return Ok(false),
        }
        Ok(true)
    }
}
