//! winit + egui surface host. It shares the existing resident FigureCore.
use super::*;
use std::{
    cell::RefCell,
    sync::{
        Weak,
        atomic::{AtomicBool, Ordering},
    },
    time::{Duration, Instant},
};
use winit::{
    application::ApplicationHandler,
    dpi::LogicalSize,
    event::{ElementState, MouseButton, MouseScrollDelta, WindowEvent},
    event_loop::{ActiveEventLoop, ControlFlow, EventLoop},
    platform::pump_events::EventLoopExtPumpEvents,
    window::{Window, WindowId},
};

#[derive(Default)]
struct Control {
    close: AtomicBool,
    dirty: AtomicBool,
    stats: Mutex<Value>,
}
#[pyclass(module = "figgy._native")]
pub struct WindowHandle {
    control: Arc<Control>,
}
#[pymethods]
impl WindowHandle {
    fn close(&self) {
        self.control.close.store(true, Ordering::Release);
    }
    fn refresh(&self) {
        self.control.dirty.store(true, Ordering::Release);
    }
    fn info_json(&self) -> String {
        self.control.stats.lock().unwrap().to_string()
    }
    #[getter]
    fn closed(&self) -> bool {
        self.control.close.load(Ordering::Acquire)
    }
}

struct SurfaceWindow {
    window: Arc<Window>,
    surface: wgpu::Surface<'static>,
    config: wgpu::SurfaceConfiguration,
    core: Weak<Mutex<FigureCore>>,
    control: Arc<Control>,
    ctx: egui::Context,
    input: egui_winit::State,
    ui_renderer: egui_wgpu::Renderer,
    view: Option<renderer::ChartView>,
    styles: Vec<renderer::ChartStyle>,
    last_revision: u64,
    last_scale: f32,
    selected: Option<String>,
    handle: Option<String>,
    dragging: bool,
    edit_area: bool,
    cursor: (f32, f32),
    panel: Rect,
    scale: f32,
    save_path: String,
    raw: String,
    error: String,
    frames: u64,
    last_input: Option<Instant>,
    latency_ms: f64,
}
impl SurfaceWindow {
    fn new(
        event_loop: &ActiveEventLoop,
        core: &Arc<Mutex<FigureCore>>,
        control: Arc<Control>,
    ) -> PyResult<Self> {
        let c = core.lock().map_err(runtime)?;
        let rect = c.chart.config().chart_area.0;
        let window = Arc::new(
            event_loop
                .create_window(
                    Window::default_attributes()
                        .with_title("Figgy — Rust surface")
                        .with_inner_size(LogicalSize::new(
                            rect.width as f64 + 310.,
                            rect.height as f64,
                        )),
                )
                .map_err(runtime)?,
        );
        let size = window.inner_size();
        let surface = c.instance.create_surface(window.clone()).map_err(runtime)?;
        let caps = surface.get_capabilities(&c.adapter);
        let format = caps.formats.iter().copied().find(|f| !f.is_srgb()).or(caps.formats.first().copied()).ok_or_else(|| runtime("the Figure GPU cannot present to this window; create it on a compatible adapter"))?;
        let config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format,
            width: size.width.max(1),
            height: size.height.max(1),
            present_mode: wgpu::PresentMode::Fifo,
            desired_maximum_frame_latency: 2,
            alpha_mode: caps.alpha_modes[0],
            view_formats: vec![],
            color_space: Default::default(),
        };
        surface.configure(c.renderer.device(), &config);
        let ctx = egui::Context::default();
        let input = egui_winit::State::new(
            ctx.clone(),
            egui::ViewportId::ROOT,
            window.as_ref(),
            Some(window.scale_factor() as f32),
            window.theme(),
            None,
        );
        let ui_renderer = egui_wgpu::Renderer::new(c.renderer.device(), format, Default::default());
        Ok(Self {
            window,
            surface,
            config,
            core: Arc::downgrade(core),
            control,
            ctx,
            input,
            ui_renderer,
            view: None,
            styles: vec![],
            last_revision: u64::MAX,
            last_scale: 0.,
            selected: None,
            handle: None,
            dragging: false,
            edit_area: false,
            cursor: (0., 0.),
            panel: rect,
            scale: 1.,
            save_path: "figure.png".into(),
            raw: String::new(),
            error: String::new(),
            frames: 0,
            last_input: None,
            latency_ms: 0.,
        })
    }
    fn resize(&mut self, w: u32, h: u32) {
        if w == 0 || h == 0 {
            return;
        }
        self.config.width = w;
        self.config.height = h;
        if let Some(core) = self.core.upgrade() {
            let c = core.lock().unwrap();
            self.surface.configure(c.renderer.device(), &self.config);
        }
        self.last_scale = 0.;
        self.window.request_redraw();
    }
    fn display(&self, c: &FigureCore) -> (Config, Rect, f32) {
        let width = self
            .config
            .width
            .saturating_sub((310. * self.window.scale_factor()) as u32)
            .max(1);
        renderer::display_config_for_surface(c.chart.config(), (width, self.config.height))
    }
    fn pointer(&mut self, event: &WindowEvent) -> PyResult<()> {
        let input_received = Instant::now();
        let Some(core) = self.core.upgrade() else {
            return Ok(());
        };
        let mut c = core.lock().map_err(runtime)?;
        let (display, panel, scale) = self.display(&c);
        self.panel = panel;
        self.scale = scale;
        match event {
            WindowEvent::CursorMoved { position, .. } => {
                let old = self.cursor;
                self.cursor = (position.x as f32, position.y as f32);
                if self.dragging
                    && let Some(target) = &self.selected
                {
                    c.drag(
                        target,
                        (self.cursor.0 - old.0) / scale,
                        (self.cursor.1 - old.1) / scale,
                        self.handle.as_deref(),
                    )?;
                    self.last_input = Some(input_received);
                    self.window.request_redraw();
                }
            }
            WindowEvent::MouseInput {
                state: ElementState::Pressed,
                button: MouseButton::Left,
                ..
            } => {
                let (x, y) = self.cursor;
                let measure = CpuTextMeasure::for_style(&display.draw_style);
                self.handle = self
                    .selected
                    .as_deref()
                    .and_then(|t| c.element(t).ok())
                    .and_then(|id| c.hitmap.get(id))
                    .and_then(|e| e.as_resizable())
                    .and_then(|e| e.hit_resize_handle(&display, &measure, x, y))
                    .map(|h| format!("{h:?}"));
                if self.handle.is_none() {
                    self.selected = c
                        .hitmap
                        .hit_test(&display, &measure, x, y)
                        .and_then(|id| c.hitmap.get(id))
                        .map(|e| e.element_id());
                    if self.selected.as_deref() == Some("data_area") && !self.edit_area {
                        c.renderer.enable_gpu_picking().map_err(runtime)?;
                        let id = c.chart_id;
                        let ticket = c
                            .renderer
                            .pick_chart_data(
                                id,
                                GpuPickRequest {
                                    canvas_position_px: [x, y],
                                    display_panel_px: panel,
                                    display_scale: scale,
                                    max_distance_px: 6.,
                                },
                            )
                            .map_err(runtime)?;
                        c.renderer.wait_idle();
                        let picked = pollster::block_on(ticket.resolve()).map_err(runtime)?;
                        self.selected = picked.as_ref().map(|p| p.series_id().to_string());
                        let mut cfg = c.chart.config().clone();
                        cfg.picked_data = picked.map(|p| renderer::config::DataSelectionsConfig {
                            refs: vec![p.to_ref()],
                            ..Default::default()
                        });
                        c.commit_config(cfg)?;
                    }
                }
                self.dragging = self
                    .selected
                    .as_deref()
                    .and_then(|t| c.element(t).ok())
                    .and_then(|id| c.hitmap.get(id))
                    .is_some_and(|e| e.as_draggable().is_some());
                self.last_revision = u64::MAX;
                self.last_input = Some(input_received);
                self.window.request_redraw();
            }
            WindowEvent::MouseInput {
                state: ElementState::Released,
                button: MouseButton::Left,
                ..
            } => {
                self.dragging = false;
                self.handle = None;
            }
            WindowEvent::MouseWheel { delta, .. } => {
                let dy = match delta {
                    MouseScrollDelta::LineDelta(_, y) => *y,
                    MouseScrollDelta::PixelDelta(p) => p.y as f32 / 40.,
                };
                let factor = (-dy as f64 * 0.1).exp();
                let mut cfg = c.chart.config().clone();
                for axis in [
                    &mut cfg.bottom_x,
                    &mut cfg.top_x,
                    &mut cfg.left_y,
                    &mut cfg.right_y,
                ] {
                    if axis.scale == renderer::config::AxisScale::Linear {
                        let mid = (axis.min + axis.max) * 0.5;
                        let half = (axis.max - axis.min) * factor * 0.5;
                        axis.min = mid - half;
                        axis.max = mid + half;
                    }
                }
                c.commit_config(cfg)?;
                self.last_input = Some(input_received);
                self.window.request_redraw();
            }
            _ => {}
        }
        Ok(())
    }
    fn frame(&mut self) -> PyResult<()> {
        let Some(core) = self.core.upgrade() else {
            self.control.close.store(true, Ordering::Release);
            return Ok(());
        };
        let mut c = core.lock().map_err(runtime)?;
        c.renderer
            .ensure_target_format(self.config.format)
            .map_err(runtime)?;
        let input = self.input.take_egui_input(&self.window);
        let ctx = self.ctx.clone();
        let previous_selection = self.selected.clone();
        let output = ctx.run_ui(input, |root| {
            egui::Panel::right("properties")
                .exact_size(310.)
                .show(root, |ui| {
                    ui.heading("Figgy");
                    ui.label("Rust · wgpu surface");
                    ui.checkbox(&mut self.edit_area, "Edit plot area");
                    if ui.button("Copy Python").clicked() {
                        match c
                            .settings_json()
                            .and_then(|s| serde_json::to_string(&s).map_err(runtime))
                        {
                            Ok(quoted) => ctx.copy_text(format!(
                                "import json\nfig.apply_settings(json.loads({quoted}))\n"
                            )),
                            Err(e) => self.error = e.to_string(),
                        }
                    }
                    ui.horizontal(|ui| {
                        ui.add(egui::TextEdit::singleline(&mut self.save_path).desired_width(170.));
                        if ui.button("Save PNG").clicked() {
                            c.png_encodes += 1;
                            match c
                                .render(1.)
                                .and_then(|r| encode_png(&r).map_err(runtime))
                                .and_then(|b| std::fs::write(&self.save_path, b).map_err(runtime))
                            {
                                Ok(_) => self.error.clear(),
                                Err(e) => self.error = e.to_string(),
                            }
                            // Export uses its own RGBA target; restore surface pipeline format.
                            if let Err(e) = c.renderer.ensure_target_format(self.config.format) {
                                self.error = e.to_string();
                            }
                        }
                    });
                    egui::ComboBox::from_id_salt("target")
                        .selected_text(self.selected.as_deref().unwrap_or("Select an object"))
                        .show_ui(ui, |ui| {
                            for (id, _) in &c.elements {
                                ui.selectable_value(&mut self.selected, Some(id.clone()), id);
                            }
                            for s in &c.series {
                                ui.selectable_value(
                                    &mut self.selected,
                                    Some(s.series_id.clone()),
                                    &s.series_id,
                                );
                            }
                        });
                    if let Some(target) = self.selected.clone() {
                        let mut state = serde_json::to_value(c.snapshot()).unwrap();
                        let mut changed = false;
                        let config = &mut state["config"];
                        let node = match target.as_str() {
                            "chart_title" => Some(&mut config["chart_title"]["text"]),
                            "axis_title_bottom" => {
                                Some(&mut config["bottom_x"]["title_option"]["text"])
                            }
                            "axis_title_top" => Some(&mut config["top_x"]["title_option"]["text"]),
                            "axis_title_left" => {
                                Some(&mut config["left_y"]["title_option"]["text"])
                            }
                            "axis_title_right" => {
                                Some(&mut config["right_y"]["title_option"]["text"])
                            }
                            "legend" => Some(&mut config["legend"]["content"]),
                            _ => None,
                        };
                        if let Some(node) = node {
                            let mut text = node["segments"]
                                .as_array()
                                .map(|a| {
                                    a.iter()
                                        .filter_map(|s| s["text"].as_str())
                                        .collect::<String>()
                                })
                                .unwrap_or_default();
                            if ui.text_edit_singleline(&mut text).changed() {
                                node["segments"] = serde_json::to_value(
                                    renderer::text::rich_segments_from_text(&text),
                                )
                                .unwrap();
                                changed = true;
                            }
                            changed |= number(ui, node, "font_size");
                            changed |= color(ui, node, "color");
                        } else if let Some(s) = state["series"]
                            .as_array_mut()
                            .unwrap()
                            .iter_mut()
                            .find(|s| s["series_id"] == target)
                        {
                            let style = s["render_type"]
                                .as_object_mut()
                                .unwrap()
                                .values_mut()
                                .next()
                                .unwrap();
                            if style["line"].is_object() {
                                changed |= color(ui, &mut style["line"], "line_color");
                                changed |= number(ui, &mut style["line"], "line_width");
                            }
                            if style["scatter"].is_object() {
                                changed |= color(ui, &mut style["scatter"], "point_color");
                                changed |= number(ui, &mut style["scatter"], "point_size");
                            }
                            if style["matrix"].is_object() {
                                ui.label("Heatmap: edit colorbar through full SSOT below");
                            }
                        } else {
                            let key = match target.as_str() {
                                "axis_bottom" | "tick_labels_bottom" => "bottom_x",
                                "axis_top" | "tick_labels_top" => "top_x",
                                "axis_left" | "tick_labels_left" => "left_y",
                                "axis_right" | "tick_labels_right" => "right_y",
                                _ => "",
                            };
                            if !key.is_empty() {
                                for field in ["min", "max", "major_spacing", "line_width"] {
                                    changed |= number(ui, &mut state["config"][key], field);
                                }
                                changed |= color(ui, &mut state["config"][key], "line_color");
                            }
                        }
                        if changed {
                            match c.apply_settings(&state.to_string()) {
                                Ok(_) => self.error.clear(),
                                Err(e) => self.error = e.to_string(),
                            }
                        }
                    }
                    ui.collapsing("Full SSOT", |ui| {
                        if ui.button("Refresh JSON").clicked() {
                            self.raw = serde_json::to_string_pretty(&c.snapshot()).unwrap();
                        }
                        egui::ScrollArea::vertical()
                            .max_height(220.)
                            .show(ui, |ui| {
                                ui.add(egui::TextEdit::multiline(&mut self.raw).desired_rows(8));
                            });
                        if ui.button("Apply JSON").clicked() {
                            match c.apply_settings(&self.raw) {
                                Ok(_) => self.error.clear(),
                                Err(e) => self.error = e.to_string(),
                            }
                        }
                    });
                    if !self.error.is_empty() {
                        ui.colored_label(egui::Color32::RED, &self.error);
                    }
                });
        });
        if previous_selection != self.selected {
            self.last_revision = u64::MAX;
        }
        self.input
            .handle_platform_output(&self.window, output.platform_output);
        let (display, panel, scale) = self.display(&c);
        self.panel = panel;
        self.scale = scale;
        if self.view.is_none() {
            self.view = Some(
                c.renderer
                    .create_chart_view(&Chart::new(display.clone()), panel)
                    .map_err(runtime)?,
            );
        }
        if c.revision != self.last_revision || scale != self.last_scale {
            let boxes = self
                .selected
                .as_deref()
                .and_then(|t| c.element(t).ok())
                .and_then(|id| {
                    c.hitmap.selection_box(
                        id,
                        &display,
                        &CpuTextMeasure::for_style(&display.draw_style),
                    )
                })
                .into_iter()
                .collect::<Vec<_>>();
            c.renderer
                .refresh_axis_with_selection(
                    self.view.as_mut().unwrap(),
                    &Chart::new(display.clone()),
                    panel,
                    &boxes,
                )
                .map_err(runtime)?;
            let specs = c.series.clone();
            self.styles = specs
                .iter()
                .map(|s| {
                    c.renderer
                        .create_style_for_series_scaled(s, scale)
                        .map_err(runtime)
                })
                .collect::<PyResult<Vec<_>>>()?;
            self.last_revision = c.revision;
            self.last_scale = scale;
        }
        let specs = c.series.clone();
        let series = specs
            .iter()
            .zip(&self.styles)
            .map(|(config, style)| renderer::Series { config, style })
            .collect::<Vec<_>>();
        let prepared = c
            .renderer
            .prepare(&[renderer::ChartDrawItem {
                view: self.view.as_ref().unwrap(),
                chart_config: &display,
                series: &series,
            }])
            .map_err(runtime)?;
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
        let view = frame.texture.create_view(&Default::default());
        let mut encoder = c
            .renderer
            .device()
            .create_command_encoder(&Default::default());
        let jobs = ctx.tessellate(output.shapes, output.pixels_per_point);
        let screen = egui_wgpu::ScreenDescriptor {
            size_in_pixels: [self.config.width, self.config.height],
            pixels_per_point: output.pixels_per_point,
        };
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
        let extra = self.ui_renderer.update_buffers(
            c.renderer.device(),
            c.renderer.queue(),
            &mut encoder,
            &jobs,
            &screen,
        );
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
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
            c.renderer
                .paint_prepared(
                    &mut pass,
                    (self.config.width, self.config.height),
                    &prepared,
                )
                .map_err(runtime)?;
            self.ui_renderer
                .render(&mut pass.forget_lifetime(), &jobs, &screen);
        }
        c.renderer
            .queue()
            .submit(extra.into_iter().chain(std::iter::once(encoder.finish())));
        c.renderer.queue().present(frame);
        c.renderer.end_gpu_frame();
        for id in &output.textures_delta.free {
            self.ui_renderer.free_texture(id);
        }
        self.frames += 1;
        if let Some(start) = self.last_input.take() {
            self.latency_ms = start.elapsed().as_secs_f64() * 1000.;
        }
        *self.control.stats.lock().unwrap() = json!({"host":"winit-wgpu","surface_frames":self.frames,"last_input_to_submit_ms":self.latency_ms,"scale_factor":self.window.scale_factor(),"surface_size":[self.config.width,self.config.height],"column_uploads":c.uploads,"rgba_readbacks":c.readbacks,"png_encodes":c.png_encodes,"revision":c.revision});
        Ok(())
    }
}
fn number(ui: &mut egui::Ui, node: &mut Value, key: &str) -> bool {
    let Some(mut value) = node[key].as_f64() else {
        return false;
    };
    let changed = ui
        .horizontal(|ui| {
            ui.label(key);
            ui.add(egui::DragValue::new(&mut value).speed(0.1))
                .changed()
        })
        .inner;
    if changed {
        node[key] = json!(value);
    }
    changed
}
fn color(ui: &mut egui::Ui, node: &mut Value, key: &str) -> bool {
    if !node[key].is_object() {
        return false;
    }
    let keys = ["r", "g", "b", "a"];
    let mut rgba =
        std::array::from_fn::<_, 4, _>(|i| node[key][keys[i]].as_f64().unwrap_or(0.) as f32);
    let changed = ui
        .horizontal(|ui| {
            ui.label(key);
            ui.color_edit_button_rgba_unmultiplied(&mut rgba).changed()
        })
        .inner;
    if changed {
        for i in 0..4 {
            node[key][keys[i]] = json!(rgba[i]);
        }
    }
    changed
}
struct App {
    pending: Vec<(Arc<Mutex<FigureCore>>, Arc<Control>)>,
    windows: HashMap<WindowId, SurfaceWindow>,
    error: Option<PyErr>,
}
impl ApplicationHandler for App {
    fn resumed(&mut self, events: &ActiveEventLoop) {
        self.open_pending(events);
    }
    fn about_to_wait(&mut self, events: &ActiveEventLoop) {
        self.open_pending(events);
        self.windows
            .retain(|_, w| !w.control.close.load(Ordering::Acquire) && w.core.strong_count() > 0);
        for w in self.windows.values() {
            if w.control.dirty.swap(false, Ordering::AcqRel)
                || w.core
                    .upgrade()
                    .is_some_and(|c| c.lock().unwrap().revision != w.last_revision)
            {
                w.window.request_redraw();
            }
        }
    }
    fn window_event(&mut self, _: &ActiveEventLoop, id: WindowId, event: WindowEvent) {
        let Some(w) = self.windows.get_mut(&id) else {
            return;
        };
        if matches!(event, WindowEvent::CloseRequested) {
            w.control.close.store(true, Ordering::Release);
            return;
        }
        let response = w.input.on_window_event(&w.window, &event);
        let result = match event {
            WindowEvent::Resized(s) => {
                w.resize(s.width, s.height);
                Ok(())
            }
            WindowEvent::ScaleFactorChanged { .. } => {
                let s = w.window.inner_size();
                w.resize(s.width, s.height);
                Ok(())
            }
            WindowEvent::RedrawRequested => w.frame(),
            WindowEvent::CursorMoved { position, .. }
                if !w.dragging
                    && position.x as f32
                        >= w.config.width as f32 - 310. * w.window.scale_factor() as f32 =>
            {
                w.cursor = (position.x as f32, position.y as f32);
                Ok(())
            }
            WindowEvent::MouseInput {
                state: ElementState::Released,
                ..
            } => w.pointer(&event),
            _ if !response.consumed
                && w.cursor.0 < w.config.width as f32 - 310. * w.window.scale_factor() as f32 =>
            {
                w.pointer(&event)
            }
            _ => Ok(()),
        };
        if let Err(e) = result {
            w.error = e.to_string();
            self.error = Some(e);
            w.control.close.store(true, Ordering::Release);
        }
        if response.repaint && !matches!(event, WindowEvent::RedrawRequested) {
            w.window.request_redraw();
        }
    }
}
impl App {
    fn open_pending(&mut self, events: &ActiveEventLoop) {
        for (core, control) in self.pending.drain(..) {
            match SurfaceWindow::new(events, &core, control) {
                Ok(w) => {
                    w.window.request_redraw();
                    self.windows.insert(w.window.id(), w);
                }
                Err(e) => self.error = Some(e),
            }
        }
    }
}
struct Host {
    events: EventLoop<()>,
    app: App,
}
thread_local! {static HOST:RefCell<Option<Host>>=const{RefCell::new(None)};}
fn pump(block: bool) -> PyResult<usize> {
    HOST.with(|h| {
        let mut h = h.borrow_mut();
        let Some(host) = h.as_mut() else { return Ok(0) };
        host.events.pump_app_events(
            Some(if block {
                Duration::from_millis(16)
            } else {
                Duration::ZERO
            }),
            &mut host.app,
        );
        if let Some(e) = host.app.error.take() {
            return Err(e);
        }
        Ok(host.app.windows.len())
    })
}
pub fn show(core: Arc<Mutex<FigureCore>>, block: bool) -> PyResult<WindowHandle> {
    let control = Arc::new(Control::default());
    HOST.with(|h| -> PyResult<()> {
        let mut h = h.borrow_mut();
        if h.is_none() {
            let events = EventLoop::new().map_err(runtime)?;
            events.set_control_flow(ControlFlow::Wait);
            *h = Some(Host {
                events,
                app: App {
                    pending: vec![],
                    windows: HashMap::new(),
                    error: None,
                },
            });
        }
        h.as_mut()
            .unwrap()
            .app
            .pending
            .push((core, control.clone()));
        Ok(())
    })?;
    pump(false)?;
    if block {
        while pump(true)? > 0 {}
    }
    Ok(WindowHandle { control })
}
#[pyfunction]
pub fn poll_events(py: Python<'_>) -> PyResult<usize> {
    py.detach(|| pump(false))
}
#[pyfunction]
pub fn run_events(py: Python<'_>) -> PyResult<()> {
    while py.detach(|| pump(true))? > 0 {
        py.check_signals()?;
    }
    Ok(())
}
