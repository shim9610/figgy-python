//! Radial frames are rendered to a GPU texture embedded in the native egui host.
//! There is no PNG/RGBA round trip during window interaction.
use super::*;
use crate::bounded::{DocumentFrame, DocumentRenderer};

pub(super) struct BoundedSurface {
    renderer: DocumentRenderer,
    texture: wgpu::Texture,
    id: egui::TextureId,
    size: (u32, u32),
    frame: DocumentFrame,
    annotations: Arc<renderer::annotation::BoundedAnnotationFrame>,
}

impl SurfaceWindow {
    pub(super) fn frame_bounded(&mut self, c: &mut FigureAccess<'_>) -> PyResult<()> {
        let input = self.input.take_egui_input(&self.window);
        let ctx = self.ctx.clone();
        let overlay = self.inspector_overlay();
        let mut error = None;
        let output = ctx.run_ui(input, |root| {
            self.editor.show_bounded(root, c, overlay);
            // Side-panel frame margins must not enlarge the chart when the
            // window grows to accommodate the docked inspector.
            if !overlay {
                let available = self.pending_chart_width.unwrap_or_else(|| {
                    self.config.width.saturating_sub(if self.inspector_docked {
                        self.sidebar_pixels()
                    } else {
                        0
                    })
                });
                self.editor.stage.max.x = self.editor.stage.min.x
                    + (available as f32 / ctx.pixels_per_point() - 32.).max(1.);
            }
            let (_, panel, scale) = self.display(c);
            self.panel = panel;
            self.scale = scale;
            let dpr = ctx.pixels_per_point();
            let image_rect = egui::Rect::from_min_size(
                egui::pos2(panel.x as f32 / dpr, panel.y as f32 / dpr),
                egui::vec2(panel.width as f32 / dpr, panel.height as f32 / dpr),
            );
            let prepared = (|| -> PyResult<()> {
                let document_size = c.data.chart.config().chart_area.0;
                let logical_size = (document_size.width, document_size.height);
                let scale = scale.clamp(0.5, 4.0);
                let size = (
                    (logical_size.0 as f32 * scale).round() as u32,
                    (logical_size.1 as f32 * scale).round() as u32,
                );
                if self.bounded_surface.as_ref().is_none_or(|s| s.size != size) {
                    if let Some(old) = self.bounded_surface.take() {
                        self.ui_renderer.free_texture(&old.id);
                    }
                    let mut renderer = DocumentRenderer::new(
                        RendererDevice::new(
                            c.renderer.device().clone(),
                            c.renderer.queue().clone(),
                        ),
                        &c.data.document.as_ref().unwrap().chart,
                    )
                    .map_err(runtime)?;
                    let frame = renderer
                        .prepare(
                            &c.data.document.as_ref().unwrap().chart,
                            logical_size,
                            scale,
                        )
                        .map_err(runtime)?;
                    let texture = c
                        .renderer
                        .device()
                        .create_texture(&wgpu::TextureDescriptor {
                            label: Some("Figgy radial surface texture"),
                            size: wgpu::Extent3d {
                                width: size.0,
                                height: size.1,
                                depth_or_array_layers: 1,
                            },
                            mip_level_count: 1,
                            sample_count: 1,
                            dimension: wgpu::TextureDimension::D2,
                            format: wgpu::TextureFormat::Rgba8Unorm,
                            usage: wgpu::TextureUsages::RENDER_ATTACHMENT
                                | wgpu::TextureUsages::TEXTURE_BINDING,
                            view_formats: &[],
                        });
                    let id = self.ui_renderer.register_native_texture(
                        c.renderer.device(),
                        &texture.create_view(&Default::default()),
                        wgpu::FilterMode::Linear,
                    );
                    let annotations = renderer.prepare_annotations(
                        &c.data.document.as_ref().unwrap().chart,
                        logical_size,
                        scale,
                    )?;
                    self.bounded_surface = Some(BoundedSurface {
                        renderer,
                        texture,
                        id,
                        size,
                        frame,
                        annotations,
                    });
                }
                let surface = self.bounded_surface.as_mut().unwrap();
                surface.frame = surface
                    .renderer
                    .prepare(
                        &c.data.document.as_ref().unwrap().chart,
                        logical_size,
                        scale,
                    )
                    .map_err(runtime)?;
                surface.annotations = surface.renderer.prepare_annotations(
                    &c.data.document.as_ref().unwrap().chart,
                    logical_size,
                    scale,
                )?;
                root.painter().image(
                    surface.id,
                    image_rect,
                    egui::Rect::from_min_max(egui::Pos2::ZERO, egui::pos2(1., 1.)),
                    egui::Color32::WHITE,
                );
                let response = root.interact(
                    image_rect,
                    egui::Id::new("radial_image"),
                    egui::Sense::click_and_drag(),
                );
                // Bounded value axes have their own range model; do not
                // silently drop wheel input as if they were immutable images.
                if response.hovered()
                    && let Some(view) = navigation::bounded_view(&c.snapshot())
                {
                    let delta = root.input(|i| {
                        i.raw
                            .events
                            .iter()
                            .filter_map(|e| {
                                if let egui::Event::MouseWheel { delta, .. } = e {
                                    Some(delta.y)
                                } else {
                                    None
                                }
                            })
                            .sum::<f32>()
                    });
                    let modifiers = root.input(|i| i.modifiers);
                    let horizontal = view["axis"] == "x";
                    let allowed = if horizontal {
                        !modifiers.shift || modifiers.ctrl
                    } else {
                        !modifiers.ctrl || modifiers.shift
                    };
                    if delta != 0. && allowed {
                        let [low, high]: [f64; 2] =
                            serde_json::from_value(view["range"].clone()).unwrap();
                        let area = surface
                            .frame
                            .decorations()
                            .entries()
                            .find(|(_, v)| v.id == renderer::DecorationId::DataArea)
                            .and_then(|(id, _)| surface.frame.decorations().bounds(id));
                        if let (Some(p), Some(area)) = (response.hover_pos(), area) {
                            let x = (p.x - image_rect.min.x) * logical_size.0 as f32
                                / image_rect.width();
                            let y = (p.y - image_rect.min.y) * logical_size.1 as f32
                                / image_rect.height();
                            let anchor = if view["axis"] == "radius" {
                                0.
                            } else if horizontal {
                                ((x - area.x) / area.width).clamp(0., 1.) as f64
                            } else {
                                (1. - (y - area.y) / area.height).clamp(0., 1.) as f64
                            };
                            let factor = (-delta as f64 / 40. * 0.1).clamp(-1.2, 1.2).exp();
                            let pivot = low + (high - low) * anchor;
                            let range = Some([
                                pivot + (low - pivot) * factor,
                                pivot + (high - pivot) * factor,
                            ]);
                            let mut chart = c.data.document.as_ref().unwrap().chart.clone();
                            match &mut chart {
                                crate::bounded::DocumentChart::BoxPlot(c) => c.value_range = range,
                                crate::bounded::DocumentChart::Radar(c) => c.value_range = range,
                                _ => {}
                            }
                            if let Err(error) = c.set_document(chart) {
                                self.editor.error = error.to_string();
                            }
                            root.ctx().request_repaint();
                        }
                    }
                }
                let map = surface.frame.decorations();
                let to_local = |p: egui::Pos2| {
                    [
                        (p.x - image_rect.min.x) * logical_size.0 as f32 / image_rect.width(),
                        (p.y - image_rect.min.y) * logical_size.1 as f32 / image_rect.height(),
                    ]
                };
                if self.editor.drawing.tool != crate::drawing::Tool::Select {
                    if let Some(origin) = ctx.input(|i| i.pointer.press_origin()) {
                        if image_rect.contains(origin)
                            && self.editor.drawing.gesture.is_none()
                            && (response.drag_started()
                                || response.clicked()
                                || response.is_pointer_button_down_on())
                        {
                            self.editor
                                .drawing
                                .begin(surface.frame.annotation_space(), to_local(origin));
                        }
                    }
                    if let Some(p) = ctx.input(|i| i.pointer.interact_pos()) {
                        self.editor.drawing.update(to_local(p));
                    }
                    self.editor.drawing.preview(root.painter(), |p| {
                        egui::pos2(
                            image_rect.min.x + p[0] * image_rect.width() / logical_size.0 as f32,
                            image_rect.min.y + p[1] * image_rect.height() / logical_size.1 as f32,
                        )
                    });
                    if ctx.input(|i| i.pointer.any_released()) {
                        if let Some(item) = self.editor.drawing.finish() {
                            if matches!(
                                &item.kind,
                                renderer::annotation::AnnotationKind::Text { .. }
                            ) {
                                self.editor.focus_annotation = Some(item.id.clone());
                            }
                            let mut chart = c.data.document.as_ref().unwrap().chart.clone();
                            let index = chart.annotations().items.len();
                            chart.annotations_mut().visible = true;
                            chart.annotations_mut().items.push(item);
                            chart.set_active_layer(renderer::LayerRef::Annotations);
                            chart.clear_selection();
                            chart.decorations_mut().selected =
                                Some(renderer::DecorationId::Annotation(index));
                            if let Err(e) = c.set_document(chart) {
                                self.editor.error = e.to_string();
                            } else {
                                self.editor.inspector_open = true;
                            }
                        }
                    }
                    if response.dragged() || response.clicked() {
                        ctx.request_repaint();
                    }
                    return Ok(());
                }
                let mut chart = c.data.document.as_ref().unwrap().chart.clone();
                let before = chart.clone();
                let decoration = response.interact_pointer_pos().and_then(|p| {
                    let point = to_local(p);
                    let key = match surface.annotations.hit_test_active_layer(
                        chart.active_layer(),
                        map,
                        point,
                    )? {
                        renderer::annotation::LayerHit::Annotation { index, .. } => {
                            renderer::DecorationId::Annotation(index)
                        }
                        renderer::annotation::LayerHit::Element(id) => map.element(id)?.id.clone(),
                    };
                    if key == renderer::DecorationId::DataArea
                        && !self.editor.edit_area
                        && chart.decorations().selected != Some(key.clone())
                        && surface.frame.has_data(point)
                    {
                        return None;
                    }
                    Some(key)
                });
                if response.drag_started() {
                    self.handle = ctx.input(|i| i.pointer.press_origin()).and_then(|p| {
                        let selected = chart.decorations().selected.as_ref()?;
                        if let renderer::DecorationId::Annotation(index) = selected {
                            let id = surface.annotations.annotations().find(*index)?;
                            return surface
                                .annotations
                                .annotations()
                                .hit_resize_handle(id, to_local(p))
                                .map(|h| format!("{h:?}"));
                        }
                        let (id, _) = map.entries().find(|(_, e)| &e.id == selected)?;
                        map.hit_resize_handle(id, to_local(p))
                            .map(|h| format!("{h:?}"))
                    });
                }
                if (response.clicked() || response.drag_started()) && self.handle.is_none() {
                    chart.decorations_mut().selected = decoration.clone();
                    if decoration.is_some() {
                        match &mut chart {
                            crate::bounded::DocumentChart::Radial(c) => {
                                c.interaction.selected = None
                            }
                            crate::bounded::DocumentChart::Categorical(c) => c.selected = None,
                            crate::bounded::DocumentChart::BoxPlot(c) => c.selected = None,
                            crate::bounded::DocumentChart::Radar(c) => c.selected = None,
                        }
                    }
                }
                if response.dragged() {
                    if let Some(selected) = chart.decorations().selected.clone() {
                        if let Some((id, _)) = map.entries().find(|(_, e)| e.id == selected) {
                            let d = ctx.input(|i| {
                                if response.drag_started() {
                                    i.pointer
                                        .interact_pos()
                                        .zip(i.pointer.press_origin())
                                        .map(|(now, start)| now - start)
                                        .unwrap_or_default()
                                } else {
                                    i.pointer.delta()
                                }
                            });
                            let dx = d.x * logical_size.0 as f32 / image_rect.width();
                            let dy = d.y * logical_size.1 as f32 / image_rect.height();
                            // A stationary pointer must not materialize an explicit
                            // layout or increment the document revision.
                            if dx != 0. || dy != 0. {
                                if let Some(h) = self.handle.as_ref().and_then(|name| {
                                    ALL_HANDLES.into_iter().find(|h| format!("{h:?}") == *name)
                                }) {
                                    map.resize_by(chart.decorations_mut(), id, h, dx, dy);
                                } else {
                                    map.drag_by(chart.decorations_mut(), id, dx, dy);
                                }
                            }
                        }
                    }
                }
                if response.dragged() {
                    if let Some(renderer::DecorationId::Annotation(index)) =
                        chart.decorations().selected
                    {
                        if let Some(id) = surface.annotations.annotations().find(index) {
                            let delta = ctx.input(|i| i.pointer.delta());
                            let dx = delta.x * logical_size.0 as f32 / image_rect.width();
                            let dy = delta.y * logical_size.1 as f32 / image_rect.height();
                            if let Some(handle) = self.handle.as_ref().and_then(|name| {
                                ALL_HANDLES.into_iter().find(|h| format!("{h:?}") == *name)
                            }) {
                                surface.annotations.annotations().resize_by(
                                    chart.annotations_mut(),
                                    id,
                                    handle,
                                    dx,
                                    dy,
                                );
                            } else {
                                surface.annotations.annotations().drag_by(
                                    chart.annotations_mut(),
                                    id,
                                    dx,
                                    dy,
                                );
                            }
                        }
                    }
                }
                if response.drag_stopped() {
                    self.handle = None;
                }
                let hover = response
                    .hover_pos()
                    .filter(|_| decoration.is_none() && !response.dragged())
                    .map(to_local);
                if response.clicked() && decoration.is_none() {
                    if let Some(p) = response.interact_pointer_pos() {
                        chart.select_at(&surface.frame, to_local(p), true);
                    }
                }
                if chart.hover(&surface.frame, hover, ctx.input(|i| i.stable_dt).min(0.1)) {
                    ctx.request_repaint();
                }
                if chart != before {
                    match surface.renderer.prepare(&chart, logical_size, scale) {
                        Ok(frame) => {
                            surface.frame = frame;
                            surface.annotations = surface.renderer.prepare_annotations(
                                &chart,
                                logical_size,
                                scale,
                            )?;
                            c.set_document(chart)?;
                            self.editor.error.clear();
                        }
                        Err(e) => self.editor.error = e.to_string(),
                    }
                    if response.clicked() {
                        let chart = &c.data.document.as_ref().unwrap().chart;
                        self.editor.inspector_open |= !chart.selected_json().is_null()
                            || chart.decorations().selected.is_some();
                    }
                    ctx.request_repaint();
                }
                Ok(())
            })();
            if let Err(e) = prepared {
                error = Some(e);
            }
        });
        if let Some(error) = error {
            return Err(error);
        }
        self.input
            .handle_platform_output(&self.window, output.platform_output);
        let old_size = (self.config.width, self.config.height);
        self.sync_inspector_size();
        if old_size != (self.config.width, self.config.height) {
            self.surface.configure(c.renderer.device(), &self.config);
        }
        let frame = match self.surface.get_current_texture() {
            wgpu::CurrentSurfaceTexture::Success(f)
            | wgpu::CurrentSurfaceTexture::Suboptimal(f) => f,
            wgpu::CurrentSurfaceTexture::Outdated | wgpu::CurrentSurfaceTexture::Lost => {
                self.surface.configure(c.renderer.device(), &self.config);
                self.window.request_redraw();
                return Ok(());
            }
            other => return Err(runtime(format!("surface acquisition: {other:?}"))),
        };
        let mut encoder = c
            .renderer
            .device()
            .create_command_encoder(&Default::default());
        let radial = self.bounded_surface.as_ref().unwrap();
        let radial_view = radial.texture.create_view(&Default::default());
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &radial_view,
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(background_wgpu(Some(
                            c.data.document.as_ref().unwrap().chart.background(),
                        ))),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                ..Default::default()
            });
            radial.annotations.draw_underlay(&mut pass);
            radial.frame.draw(&mut pass);
            radial.annotations.draw_overlay(&mut pass);
        }
        for (id, deltas) in &output.textures_delta.set {
            for delta in deltas {
                self.ui_renderer.update_texture(
                    c.renderer.device(),
                    c.renderer.queue(),
                    *id,
                    delta,
                );
            }
        }
        let jobs = ctx.tessellate(output.shapes, output.pixels_per_point);
        let screen = egui_wgpu::ScreenDescriptor {
            size_in_pixels: [self.config.width, self.config.height],
            pixels_per_point: output.pixels_per_point,
        };
        let extra = self.ui_renderer.update_buffers(
            c.renderer.device(),
            c.renderer.queue(),
            &mut encoder,
            &jobs,
            &screen,
        );
        let view = frame.texture.create_view(&Default::default());
        {
            let pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color::WHITE),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                ..Default::default()
            });
            self.ui_renderer
                .render(&mut pass.forget_lifetime(), &jobs, &screen);
        }
        c.renderer
            .queue()
            .submit(extra.into_iter().chain(std::iter::once(encoder.finish())));
        c.renderer.queue().present(frame);
        radial.renderer.end_frame();
        for id in &output.textures_delta.free {
            self.ui_renderer.free_texture(id);
        }
        self.repaint_at = output
            .viewport_output
            .get(&egui::ViewportId::ROOT)
            .filter(|v| v.repaint_delay != Duration::MAX)
            .and_then(|v| Instant::now().checked_add(v.repaint_delay));
        self.last_revision = c.data.revision;
        self.frames += 1;
        let dpr = output.pixels_per_point;
        let controls = self
            .editor
            .controls
            .iter()
            .map(|(name, r)| {
                (
                    name.clone(),
                    json!([
                        r.min.x * dpr,
                        r.min.y * dpr,
                        r.width() * dpr,
                        r.height() * dpr
                    ]),
                )
            })
            .collect::<serde_json::Map<_, _>>();
        *self.control.stats.lock().unwrap() = json!({
            "host":"winit-wgpu", "window_role":"chart", "chart_family":c.data.document.as_ref().unwrap().chart.family(),
            "controls":controls, "layout_mode":self.editor.edit_area,"drawing_tool":self.editor.drawing.tool.name(),"error":self.editor.error, "properties_open":self.editor.inspector_open,
            "inspector_overlay":self.inspector_overlay(), "selected":c.data.document.as_ref().unwrap().chart.selected_json(),
            "chart_panel":[self.panel.x,self.panel.y,self.panel.width,self.panel.height],
            "surface_size":[self.config.width,self.config.height], "scale_factor":self.window.scale_factor(),
            "surface_frames":self.frames, "gpu_context_id":c.context.id, "figure_id":c.data.figure_id,
            "column_uploads":c.data.uploads,"rgba_readbacks":c.data.readbacks,"png_encodes":c.data.png_encodes,
            "revision":c.data.revision,
            "decorations":self.bounded_surface.as_ref().map(|s|s.frame.decorations().entries().filter_map(|(id,e)|s.frame.decorations().bounds(id).map(|r|(e.id.element_id(),json!([r.x,r.y,r.width,r.height])))).collect::<serde_json::Map<_,_>>()),
            "decoration_selected":c.data.document.as_ref().unwrap().chart.decorations().selected,

        });
        Ok(())
    }
}
