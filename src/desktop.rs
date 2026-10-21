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
    dpi::{LogicalSize, PhysicalSize},
    event::{ElementState, MouseButton, MouseScrollDelta, WindowEvent},
    event_loop::{ActiveEventLoop, ControlFlow, EventLoop},
    keyboard::{Key, ModifiersState, NamedKey},
    platform::pump_events::EventLoopExtPumpEvents,
    window::{Window, WindowId},
};

#[derive(Default)]
struct Control {
    close: AtomicBool,
    dirty: AtomicBool,
    stats: Mutex<Value>,
    settings: Mutex<Option<Arc<Control>>>,
}
#[pyclass(module = "figgyplot._native")]
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
        let mut stats = self.control.stats.lock().unwrap().clone();
        if let Some(settings) = self.control.settings.lock().unwrap().as_ref() {
            stats["settings_window"] = if settings.close.load(Ordering::Acquire) {
                Value::Null
            } else {
                settings.stats.lock().unwrap().clone()
            };
        }
        stats.to_string()
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
    last_pool_generation: u32,
    selected: Option<String>,
    panel_focus: interaction::Focus,
    chooser: Option<target_chooser::Chooser>,
    pending_choices: Option<(u64, Vec<target_chooser::Choice>)>,
    rendered_selection: Option<String>,
    handle: Option<String>,
    dragging: bool,
    panning: bool,
    pan_moved: bool,
    drag_origin: (f32, f32),
    chart_pressed: bool,
    edit_area: bool,
    cursor: (f32, f32),
    panel: Rect,
    scale: f32,
    editor: editor::Editor,
    last_panel: Option<Rect>,
    frames: u64,
    last_input: Option<Instant>,
    latency_ms: f64,
    repaint_at: Option<Instant>,
    settings_only: bool,
    parent: Option<Weak<Control>>,
    inspector_docked: bool,
    resize_target: Option<u32>,
    pending_chart_width: Option<u32>,
    last_pick: Option<renderer::config::PickedDataRef>,
    modifiers: ModifiersState,
    bounded_surface: Option<bounded_host::BoundedSurface>,
    last_text_click: Option<(Instant, String, (f32, f32))>,
}
#[path = "bounded_host.rs"]
mod bounded_host;

impl SurfaceWindow {
    fn new(
        event_loop: &ActiveEventLoop,
        core: &Arc<Mutex<FigureCore>>,
        control: Arc<Control>,
        settings_only: bool,
        parent: Option<Weak<Control>>,
    ) -> PyResult<Self> {
        let mut data = core.lock().map_err(runtime)?;
        let gpu = Arc::clone(&data.gpu);
        let mut renderer = gpu::lock(&gpu)?;
        let c = FigureAccess::new(&gpu, &mut data, &mut renderer);
        let rect = c.data.chart.config().chart_area.0;
        let window = Arc::new(
            event_loop
                .create_window(
                    Window::default_attributes()
                        .with_title(if settings_only {
                            "Figgy — Advanced chart settings"
                        } else {
                            "Figgy"
                        })
                        .with_min_inner_size(if settings_only {
                            LogicalSize::new(500., 400.)
                        } else {
                            LogicalSize::new(900., 520.)
                        })
                        .with_inner_size(if settings_only {
                            LogicalSize::new(680., 680.)
                        } else {
                            LogicalSize::new(
                                (rect.width as f64 + 32.).max(900.),
                                (rect.height as f64 + 144.).max(700.),
                            )
                        }),
                )
                .map_err(runtime)?,
        );
        let size = window.inner_size();
        let surface = c
            .context
            .instance
            .create_surface(window.clone())
            .map_err(runtime)?;
        let caps = surface.get_capabilities(&c.context.adapter);
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
        editor::theme(&ctx);
        let input = egui_winit::State::new(
            ctx.clone(),
            egui::ViewportId::ROOT,
            window.as_ref(),
            Some(window.scale_factor() as f32),
            window.theme(),
            None,
        );
        let ui_renderer = egui_wgpu::Renderer::new(c.renderer.device(), format, Default::default());
        let mut editor = editor::Editor::default();
        if settings_only {
            editor.begin_settings(&c);
        }
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
            last_pool_generation: 0,
            selected: None,
            panel_focus: Default::default(),
            chooser: None,
            pending_choices: None,
            rendered_selection: None,
            handle: None,
            dragging: false,
            panning: false,
            pan_moved: false,
            drag_origin: (0., 0.),
            chart_pressed: false,
            edit_area: false,
            cursor: (0., 0.),
            panel: rect,
            scale: 1.,
            editor,
            last_panel: None,
            frames: 0,
            last_input: None,
            latency_ms: 0.,
            repaint_at: None,
            settings_only,
            parent,
            inspector_docked: false,
            resize_target: None,
            pending_chart_width: None,
            last_pick: None,
            modifiers: ModifiersState::empty(),
            bounded_surface: None,
            last_text_click: None,
        })
    }
    fn resize(&mut self, w: u32, h: u32) {
        if w == 0 || h == 0 {
            return;
        }
        if self.resize_target == Some(w) {
            self.resize_target = None;
            self.pending_chart_width = None;
        }
        self.config.width = w;
        self.config.height = h;
        if let Some(core) = self.core.upgrade() {
            let mut data = core.lock().unwrap();
            let gpu = Arc::clone(&data.gpu);
            let Ok(mut renderer) = gpu::lock(&gpu) else {
                return;
            };
            let c = FigureAccess::new(&gpu, &mut data, &mut renderer);
            self.surface.configure(c.renderer.device(), &self.config);
        }
        self.last_scale = 0.;
        self.window.request_redraw();
    }
    fn display(&self, c: &FigureAccess<'_>) -> (Config, Rect, f32) {
        let stage = self.editor.stage;
        let dpr = self.ctx.pixels_per_point();
        let width = (stage.width() * dpr).round().max(1.) as u32;
        let height = (stage.height() * dpr).round().max(1.) as u32;
        let document = c.data.chart.config().document_area();
        let (scale, mut panel) =
            renderer::fit_display_panel((document.width, document.height), (width, height));
        // Keep the document aspect ratio, including the fitted letterbox.
        panel.x += (stage.min.x * dpr).round().max(0.) as u32;
        panel.y += (stage.min.y * dpr).round().max(0.) as u32;
        let mut config = c.data.chart.config().clone();
        if let Some(choice) = self.chooser.as_ref().and_then(|v| v.preview()) {
            config.set_active_layer(choice.layer);
            config.picked_points = None;
            config.picked_data =
                choice
                    .pick
                    .clone()
                    .map(|p| renderer::config::DataSelectionsConfig {
                        refs: vec![p],
                        ..Default::default()
                    });
        }
        let display = renderer::place_document(&config, scale, panel);
        (display, panel, scale)
    }
    fn fit_stage_width(&mut self) {
        if !self.settings_only && !self.inspector_overlay() {
            let available = self.pending_chart_width.unwrap_or_else(|| {
                self.config.width.saturating_sub(if self.inspector_docked {
                    self.sidebar_pixels()
                } else {
                    0
                })
            });
            self.editor.stage.max.x = self.editor.stage.min.x
                + (available as f32 / self.ctx.pixels_per_point() - 32.).max(1.);
        }
    }
    fn choose_target(
        &mut self,
        c: &mut FigureAccess<'_>,
        choice: target_chooser::Choice,
    ) -> PyResult<()> {
        choice.apply(c)?;
        self.panel_focus.select(
            c.data.chart.config(),
            c.data.identity.as_ref(),
            Some(interaction::panel_index(choice.layer)),
        );
        self.selected = choice.target;
        self.chooser = None;
        self.pending_choices = None;
        self.dragging = false;
        self.panning = false;
        self.chart_pressed = false;
        if self.selected.is_some() {
            self.editor.inspector_open = true;
        }
        self.last_revision = u64::MAX;
        self.window.request_redraw();
        Ok(())
    }
    fn inspector_overlay(&self) -> bool {
        self.window.is_maximized()
            || self.window.fullscreen().is_some()
            || self.window.current_monitor().is_some_and(|m| {
                !self.inspector_docked && self.config.width + self.sidebar_pixels() > m.size().width
            })
    }
    fn sidebar_pixels(&self) -> u32 {
        (editor::INSPECTOR_WIDTH * self.ctx.pixels_per_point()).round() as u32
    }
    fn sync_inspector_size(&mut self) {
        if self.settings_only || self.inspector_overlay() {
            return;
        }
        if self.editor.inspector_open != self.inspector_docked {
            let sidebar = self.sidebar_pixels();
            let base = self.pending_chart_width.unwrap_or_else(|| {
                self.config
                    .width
                    .saturating_sub(if self.inspector_docked { sidebar } else { 0 })
            });
            let target = base
                + if self.editor.inspector_open {
                    sidebar
                } else {
                    0
                };
            self.pending_chart_width = Some(base);
            self.resize_target = Some(target);
            self.inspector_docked = self.editor.inspector_open;
            if let Some(size) = self
                .window
                .request_inner_size(PhysicalSize::new(target, self.config.height))
            {
                self.config.width = size.width;
                self.config.height = size.height;
                self.resize_target = None;
                self.pending_chart_width = None;
                self.last_scale = 0.;
            }
            self.window.request_redraw();
        }
    }
    fn keyboard(&mut self, key: &NamedKey) -> PyResult<()> {
        if self.chooser.is_some() {
            return Ok(());
        }
        if self.editor.inline_text.is_some() {
            return Ok(());
        }
        if *key == NamedKey::Escape && self.editor.drawing.tool != crate::drawing::Tool::Select {
            self.editor.drawing.cancel();
            self.dragging = false;
            self.window.request_redraw();
            return Ok(());
        }
        if *key == NamedKey::F11 {
            self.window
                .set_fullscreen(if self.window.fullscreen().is_some() {
                    None
                } else {
                    Some(winit::window::Fullscreen::Borderless(None))
                });
            self.window.request_redraw();
            return Ok(());
        }
        if self.editor.drawing.tool != crate::drawing::Tool::Select {
            return Ok(());
        }
        let Some(core) = self.core.upgrade() else {
            return Ok(());
        };
        let mut data = core.lock().map_err(runtime)?;
        let gpu = Arc::clone(&data.gpu);
        let mut renderer = gpu::lock(&gpu)?;
        let mut c = FigureAccess::new(&gpu, &mut data, &mut renderer);
        if matches!(key, NamedKey::Delete | NamedKey::Backspace) {
            if let Some(d) = &c.data.document {
                let mut chart = d.chart.clone();
                if let Some(renderer::DecorationId::Annotation(index)) =
                    chart.decorations().selected
                {
                    chart.annotations_mut().items.remove(index);
                    chart.clear_selection();
                    c.set_document(chart)?;
                }
            } else if let Some(target) = self
                .selected
                .as_deref()
                .and_then(|v| v.strip_prefix("annotation:"))
            {
                let mut cfg = c.data.chart.config().clone();
                cfg.annotations.items.retain(|v| v.id != target);
                c.commit_config(cfg)?;
                self.selected = None;
            }
            self.window.request_redraw();
            return Ok(());
        }
        if c.data.document.is_some() {
            let mut chart = c.data.document.as_ref().unwrap().chart.clone();
            if *key == NamedKey::Escape {
                chart.clear_selection();
            } else if let Some(selected) = chart.decorations().selected.clone() {
                let step = if self.modifiers.shift_key() { 10. } else { 1. };
                let (dx, dy) = match key {
                    NamedKey::ArrowLeft => (-step, 0.),
                    NamedKey::ArrowRight => (step, 0.),
                    NamedKey::ArrowUp => (0., -step),
                    NamedKey::ArrowDown => (0., step),
                    _ => return Ok(()),
                };
                c.document_drag(&selected.element_id(), dx, dy, None)?;
                self.window.request_redraw();
                return Ok(());
            } else if matches!(key, NamedKey::ArrowLeft | NamedKey::ArrowRight) {
                chart.step(*key == NamedKey::ArrowLeft);
            }
            c.set_document(chart)?;
            self.window.request_redraw();
            return Ok(());
        }
        if *key == NamedKey::Escape {
            self.panel_focus
                .select(c.data.chart.config(), c.data.identity.as_ref(), None);
            self.selected = None;
            self.handle = None;
            self.dragging = false;
            self.panning = false;
            c.clear_data_selection()?;
        } else {
            let step = if self.modifiers.shift_key() { 10 } else { 1 };
            let (mut dx, mut dy) = match key {
                NamedKey::ArrowLeft => (-step, 0),
                NamedKey::ArrowRight => (step, 0),
                NamedKey::ArrowUp => (0, 1),
                NamedKey::ArrowDown => (0, -1),
                _ => return Ok(()),
            };
            if c.data.chart.config().picked_data.is_some() {
                if c.data
                    .chart
                    .config()
                    .picked_data
                    .as_ref()
                    .and_then(|p| p.refs.first())
                    .is_some_and(|p| {
                        matches!(p, renderer::config::PickedDataRef::MatrixCell { .. })
                    })
                {
                    if c.data.chart.config().bottom_x.inverted {
                        dx = -dx;
                    }
                    if c.data.chart.config().left_y.inverted {
                        dy = -dy;
                    }
                }
                c.step_selection(dx, dy)?;
                self.selected = c
                    .data
                    .chart
                    .config()
                    .picked_data
                    .as_ref()
                    .and_then(|p| p.refs.first())
                    .map(|p| p.series_id().to_owned());
            } else if let Some(target) = &self.selected {
                if c.element(target)
                    .ok()
                    .and_then(|id| c.data.hitmap.get(id))
                    .is_some_and(|e| e.as_draggable().is_some())
                {
                    // Screen up is negative y; data up is positive y.
                    c.drag(
                        target,
                        dx as f32 / self.scale,
                        -(dy * step) as f32 / self.scale,
                        None,
                    )?;
                }
            }
        }
        self.last_revision = u64::MAX;
        self.window.request_redraw();
        Ok(())
    }
    fn chart_contains_cursor(&self) -> bool {
        let p = self.panel;
        self.cursor.0 >= p.x as f32
            && self.cursor.0 < (p.x + p.width) as f32
            && self.cursor.1 >= p.y as f32
            && self.cursor.1 < (p.y + p.height) as f32
    }
    fn pointer(&mut self, event: &WindowEvent) -> PyResult<()> {
        if self.editor.inline_text.is_some() {
            return Ok(());
        }
        let input_received = Instant::now();
        let Some(core) = self.core.upgrade() else {
            return Ok(());
        };
        let mut data = core.lock().map_err(runtime)?;
        let gpu = Arc::clone(&data.gpu);
        let mut renderer = gpu::lock(&gpu)?;
        let mut c = FigureAccess::new(&gpu, &mut data, &mut renderer);
        if c.data.document.is_some() {
            self.window.request_redraw();
            return Ok(());
        }
        if self.chooser.is_some() {
            if matches!(
                event,
                WindowEvent::MouseInput {
                    state: ElementState::Pressed,
                    button: MouseButton::Left,
                    ..
                }
            ) {
                self.chooser = None;
                self.last_revision = u64::MAX;
                self.window.request_redraw();
            }
            return Ok(());
        }
        let (display, panel, scale) = self.display(&c);
        self.panel = panel;
        self.scale = scale;
        if !display.subplots.is_empty() {
            if matches!(
                event,
                WindowEvent::MouseInput {
                    state: ElementState::Pressed,
                    button: MouseButton::Left,
                    ..
                }
            ) {
                let panels = interaction::panels_at(&display, self.cursor);
                let focused = self.panel_focus.index(&display, c.data.identity.as_ref());
                let at = focused
                    .filter(|i| panels.contains(i))
                    .or_else(|| panels.first().copied());
                if focused.is_none() && panels.len() > 1 {
                    self.chooser = Some(target_chooser::Chooser::new(
                        panels
                            .into_iter()
                            .map(|i| target_chooser::Choice::panel(&c, i))
                            .collect(),
                        self.cursor,
                        c.data.revision,
                    ));
                    self.last_revision = u64::MAX;
                    self.window.request_redraw();
                    return Ok(());
                }
                if at != focused || at.is_none() {
                    self.selected = None;
                    self.handle = None;
                    self.dragging = false;
                    self.panning = false;
                    self.chart_pressed = false;
                    self.last_text_click = None;
                    self.editor.drawing.cancel();
                    let mut cfg = c.data.chart.config().clone();
                    if let Some(index) = at {
                        cfg.set_active_layer(interaction::base_layer(index));
                    }
                    cfg.picked_data = None;
                    cfg.picked_points = None;
                    if cfg != *c.data.chart.config() {
                        c.commit_config(cfg)?;
                    }
                    self.panel_focus
                        .select(c.data.chart.config(), c.data.identity.as_ref(), at);
                    self.last_revision = u64::MAX;
                    self.window.request_redraw();
                    return Ok(());
                }
            }
            if matches!(event, WindowEvent::MouseWheel { .. }) && self.panel_focus.id.is_none() {
                return Ok(());
            }
        }
        if self.editor.drawing.tool != crate::drawing::Tool::Select {
            match event {
                WindowEvent::MouseInput {
                    state: ElementState::Pressed,
                    button: MouseButton::Left,
                    ..
                } => {
                    let space = renderer::annotation::pixel_space_for_config(&display);
                    self.editor
                        .drawing
                        .begin(space, [self.cursor.0, self.cursor.1]);
                    self.dragging = true;
                }
                WindowEvent::CursorMoved { position, .. } => {
                    self.cursor = (position.x as f32, position.y as f32);
                    self.editor.drawing.update([self.cursor.0, self.cursor.1]);
                }
                WindowEvent::MouseInput {
                    state: ElementState::Released,
                    button: MouseButton::Left,
                    ..
                } => {
                    self.dragging = false;
                    if let Some(item) = self.editor.drawing.finish() {
                        let target = format!("annotation:{}", item.id);
                        if matches!(
                            &item.kind,
                            renderer::annotation::AnnotationKind::Text { .. }
                        ) {
                            self.editor.begin_inline_text(item, false);
                            self.window.request_redraw();
                            return Ok(());
                        }
                        let mut cfg = c.data.chart.config().clone();
                        cfg.annotations.visible = true;
                        cfg.annotations.items.push(item);
                        cfg.set_active_layer(renderer::LayerRef::Annotations);
                        cfg.picked_data = None;
                        cfg.picked_points = None;
                        if let Err(e) = c.commit_config(cfg) {
                            self.editor.error = e.to_string();
                        } else {
                            self.selected = Some(target);
                            self.editor.inspector_open = true;
                            self.last_revision = u64::MAX;
                        }
                    }
                }
                _ => {}
            }
            self.window.request_redraw();
            return Ok(());
        }
        match event {
            WindowEvent::CursorMoved { position, .. } => {
                let old = self.cursor;
                self.cursor = (position.x as f32, position.y as f32);
                if self.panning {
                    let distance = (self.cursor.0 - self.drag_origin.0)
                        .hypot(self.cursor.1 - self.drag_origin.1);
                    if self.pan_moved || distance >= 3. {
                        if !self.pan_moved {
                            c.clear_data_selection()?;
                            self.selected = None;
                            self.pan_moved = true;
                            self.pending_choices = None;
                        }
                        let bounds = c
                            .data
                            .hitmap
                            .selection_box(
                                c.element("data_area")?,
                                &display,
                                &CpuTextMeasure::for_style(&display.draw_style),
                            )
                            .unwrap()
                            .rect;
                        let mut cfg = c.data.chart.config().clone();
                        let dx = -(self.cursor.0 - old.0) as f64 / bounds.width.max(1.) as f64;
                        let dy = (self.cursor.1 - old.1) as f64 / bounds.height.max(1.) as f64;
                        navigate_document_axis(
                            &mut cfg,
                            c.data.identity.as_ref(),
                            "x",
                            1.,
                            0.5,
                            dx,
                        );
                        navigate_document_axis(
                            &mut cfg,
                            c.data.identity.as_ref(),
                            "y",
                            1.,
                            0.5,
                            dy,
                        );
                        c.commit_config(cfg)?;
                        self.last_input = Some(input_received);
                        self.window.request_redraw();
                    }
                } else if self.dragging
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
                let text = c
                    .data
                    .chart
                    .config()
                    .annotations
                    .visible
                    .then(|| {
                        let map = self.view.as_ref()?.annotation_map();
                        let index = map
                            .element(map.hit_test([self.cursor.0, self.cursor.1])?)?
                            .index;
                        let rendered = map.layer().items.get(index)?;
                        let item = c
                            .data
                            .chart
                            .config()
                            .annotations
                            .items
                            .iter()
                            .find(|item| item.id == rendered.id)?;
                        matches!(item.kind, renderer::annotation::AnnotationKind::Text { .. })
                            .then(|| item.clone())
                    })
                    .flatten();
                if let Some(item) = text {
                    let double = self
                        .last_text_click
                        .as_ref()
                        .is_some_and(|(time, id, point)| {
                            time.elapsed() < Duration::from_millis(450)
                                && id == &item.id
                                && (point.0 - self.cursor.0).hypot(point.1 - self.cursor.1) < 6.
                        });
                    self.last_text_click = Some((Instant::now(), item.id.clone(), self.cursor));
                    if double {
                        self.editor.begin_inline_text(item, true);
                        self.last_text_click = None;
                        self.dragging = false;
                        self.chart_pressed = false;
                        self.window.request_redraw();
                        return Ok(());
                    }
                    let mut cfg = c.data.chart.config().clone();
                    if cfg.active_layer() != renderer::LayerRef::Annotations
                        || cfg.picked_data.is_some()
                        || cfg.picked_points.is_some()
                    {
                        cfg.set_active_layer(renderer::LayerRef::Annotations);
                        cfg.picked_data = None;
                        cfg.picked_points = None;
                        c.commit_config(cfg)?;
                    }
                    self.selected = Some(format!("annotation:{}", item.id));
                    self.handle = None;
                    self.dragging = true;
                    self.chart_pressed = true;
                    self.panning = false;
                    self.pan_moved = false;
                    self.drag_origin = self.cursor;
                    self.last_revision = u64::MAX;
                    self.window.request_redraw();
                    return Ok(());
                } else {
                    self.last_text_click = None;
                }
                self.chart_pressed = true;
                self.panning = false;
                self.pan_moved = false;
                self.drag_origin = self.cursor;
                let (x, y) = self.cursor;
                let measure = CpuTextMeasure::for_style(&display.draw_style);
                self.handle = self
                    .selected
                    .as_deref()
                    .and_then(|t| c.element(t).ok())
                    .and_then(|id| c.data.hitmap.get(id))
                    .and_then(|e| e.as_resizable())
                    .and_then(|e| e.hit_resize_handle(&display, &measure, x, y))
                    .map(|h| format!("{h:?}"));
                if self.handle.is_none()
                    && let Some(target) = self.selected.as_deref()
                    && target.starts_with("annotation:")
                {
                    if let Ok(index) = c.annotation_index(target) {
                        self.handle = self
                            .view
                            .as_ref()
                            .and_then(|view| {
                                view.annotation_map().find(index).and_then(|id| {
                                    view.annotation_map().hit_resize_handle(id, [x, y])
                                })
                            })
                            .map(|h| format!("{h:?}"));
                    }
                }
                if self.handle.is_none() {
                    let index = interaction::panel_index(c.data.chart.config().active_layer());
                    let annotation = self
                        .view
                        .as_ref()
                        .and_then(|view| {
                            let map = view.annotation_map();
                            map.element(map.hit_test([x, y])?).map(|e| e.index)
                        })
                        .filter(|_| index == 0 && display.annotations.visible);
                    let hits = interaction::decorations_at(&display, index, (x, y));
                    let area = interaction::panel(&display, index)
                        .data_area()
                        .ok()
                        .map(|a| a.0);
                    let inside = area.is_some_and(|area| interaction::contains(area, (x, y)));
                    let data_hit = hits.iter().all(|(_, t)| t.ends_with("data_area"));
                    if annotation.is_none() && data_hit && inside && !self.edit_area {
                        self.panning = true;
                        let picked = c.pick_panel_candidates(
                            index,
                            GpuPickRequest {
                                canvas_position_px: [x, y],
                                display_panel_px: panel,
                                display_scale: scale,
                                max_distance_px: 6.,
                            },
                        )?;
                        if picked.len() > 1 {
                            self.pending_choices = Some((
                                c.data.revision,
                                picked
                                    .into_iter()
                                    .map(|p| target_chooser::Choice::data(&c, p))
                                    .collect(),
                            ));
                        } else {
                            let mut cfg = c.data.chart.config().clone();
                            let picked = picked.into_iter().next();
                            let same = picked.as_ref().is_some_and(|p| {
                                cfg.picked_data
                                    .as_ref()
                                    .is_some_and(|s| s.refs.first() == Some(&p.reference))
                            });
                            self.selected = if same {
                                None
                            } else {
                                picked.as_ref().map(|p| p.reference.series_id().to_owned())
                            };
                            if let Some(p) = &picked {
                                cfg.set_active_layer(p.layer);
                            }
                            cfg.picked_data = if same {
                                None
                            } else {
                                picked.map(|p| renderer::config::DataSelectionsConfig {
                                    refs: vec![p.reference],
                                    ..Default::default()
                                })
                            };
                            cfg.picked_points = None;
                            if cfg != *c.data.chart.config() {
                                c.commit_config(cfg)?;
                            }
                        }
                    } else if annotation.is_none() && hits.len() > 1 {
                        self.pending_choices = Some((
                            c.data.revision,
                            hits.into_iter()
                                .map(|(l, t)| target_chooser::Choice::element(&c, l, t))
                                .collect(),
                        ));
                    } else {
                        let mut cfg = c.data.chart.config().clone();
                        self.selected = if let Some(index) = annotation {
                            cfg.set_active_layer(renderer::LayerRef::Annotations);
                            Some(format!("annotation:{}", cfg.annotations.items[index].id))
                        } else if let Some((layer, target)) = hits.into_iter().next() {
                            cfg.set_active_layer(layer);
                            Some(target)
                        } else {
                            None
                        };
                        cfg.picked_data = None;
                        cfg.picked_points = None;
                        if cfg != *c.data.chart.config() {
                            c.commit_config(cfg)?;
                        }
                    }
                }
                self.dragging = self.panning
                    || (self.pending_choices.is_none()
                        && (self
                            .selected
                            .as_deref()
                            .is_some_and(|id| id.starts_with("annotation:"))
                            || self
                                .selected
                                .as_deref()
                                .and_then(|t| c.element(t).ok())
                                .and_then(|id| c.data.hitmap.get(id))
                                .is_some_and(|e| e.as_draggable().is_some())));
                self.last_revision = u64::MAX;
                self.last_input = Some(input_received);
                self.window.request_redraw();
            }
            WindowEvent::MouseInput {
                state: ElementState::Released,
                button: MouseButton::Left,
                ..
            } => {
                if let Some((revision, choices)) = self.pending_choices.take() {
                    self.dragging = false;
                    self.panning = false;
                    self.chart_pressed = false;
                    if !self.pan_moved && revision == c.data.revision {
                        self.chooser = Some(target_chooser::Chooser::new(
                            choices,
                            self.cursor,
                            c.data.revision,
                        ));
                        self.last_revision = u64::MAX;
                        self.window.request_redraw();
                    }
                    return Ok(());
                }
                let chart_pressed = std::mem::take(&mut self.chart_pressed);
                self.dragging = false;
                self.panning = false;
                self.handle = None;
                if !self.pan_moved
                    && chart_pressed
                    && self.selected.is_some()
                    && !self
                        .selected
                        .as_deref()
                        .and_then(|t| c.annotation_index(t).ok())
                        .is_some_and(|i| {
                            matches!(
                                c.data.chart.config().annotations.items[i].kind,
                                renderer::annotation::AnnotationKind::Text { .. }
                            )
                        })
                    && self.chart_contains_cursor()
                {
                    self.editor.inspector_open = true;
                    self.window.request_redraw();
                }
            }
            WindowEvent::MouseWheel { delta, .. } => {
                // Decorations and the surrounding canvas do not own plot zoom.
                let Ok(area) = active_coordinate_config(&display).data_area() else {
                    return Ok(());
                };
                let area = area.0;
                if self.cursor.0 < area.x as f32
                    || self.cursor.0 >= (area.x + area.width) as f32
                    || self.cursor.1 < area.y as f32
                    || self.cursor.1 >= (area.y + area.height) as f32
                {
                    return Ok(());
                }
                let (dx, dy) = match delta {
                    MouseScrollDelta::LineDelta(x, y) => (*x as f64, *y as f64),
                    MouseScrollDelta::PixelDelta(p) => (p.x / 40., p.y / 40.),
                };
                let bounds = c
                    .data
                    .hitmap
                    .selection_box(
                        c.element("data_area")?,
                        &display,
                        &CpuTextMeasure::for_style(&display.draw_style),
                    )
                    .unwrap()
                    .rect;
                let x = ((self.cursor.0 - bounds.x) / bounds.width.max(1.)).clamp(0., 1.) as f64;
                let y =
                    1. - ((self.cursor.1 - bounds.y) / bounds.height.max(1.)).clamp(0., 1.) as f64;
                let mut cfg = c.data.chart.config().clone();
                let delta = if dy != 0. { dy } else { dx };
                let factor = (-delta.clamp(-12., 12.) * 0.1).exp();
                let ctrl = self.modifiers.control_key();
                let shift = self.modifiers.shift_key();
                // Ctrl isolates X, Shift isolates Y; plain wheel zooms both.
                if !shift || ctrl {
                    navigate_document_axis(&mut cfg, c.data.identity.as_ref(), "x", factor, x, 0.);
                }
                if !ctrl || shift {
                    navigate_document_axis(&mut cfg, c.data.identity.as_ref(), "y", factor, y, 0.);
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
        let mut data = core.lock().map_err(runtime)?;
        let gpu = Arc::clone(&data.gpu);
        let mut renderer = gpu::lock(&gpu)?;
        let mut c = FigureAccess::new(&gpu, &mut data, &mut renderer);
        if c.data.document.is_some() && !self.settings_only {
            return self.frame_bounded(&mut c);
        }
        c.renderer
            .ensure_target_format(self.config.format)
            .map_err(runtime)?;
        let input = self.input.take_egui_input(&self.window);
        let ctx = self.ctx.clone();
        let current_pick = c
            .data
            .chart
            .config()
            .picked_data
            .as_ref()
            .and_then(|p| p.refs.first())
            .cloned();
        if current_pick != self.last_pick {
            self.editor.picked = match current_pick
                .as_ref()
                .map(|p| c.selection_details(p))
                .transpose()
            {
                Ok(value) => value,
                Err(error) => {
                    self.editor.error = error.to_string();
                    None
                }
            };
            self.last_pick = current_pick;
        }
        if self
            .chooser
            .as_ref()
            .is_some_and(|v| v.revision != c.data.revision)
        {
            self.chooser = None;
            self.last_revision = u64::MAX;
        }
        let previous_selection = self.selected.clone();
        self.panel_focus
            .sync(c.data.chart.config(), c.data.identity.as_ref(), false);
        self.editor.panel_focused =
            c.data.chart.config().subplots.is_empty() || self.panel_focus.id.is_some();
        self.editor.selection_hint = if c.data.chart.config().subplots.is_empty() {
            String::new()
        } else if let Some(index) = self
            .panel_focus
            .index(c.data.chart.config(), c.data.identity.as_ref())
        {
            format!(
                "{} selected · Click an axis or data to edit · Click another chart to switch · Esc: leave chart",
                interaction::panel_label(c.data.chart.config(), c.data.identity.as_ref(), index)
            )
        } else {
            "Click a chart to select it, then click or drag inside to edit".into()
        };
        let mut output = ctx.run_ui(input, |root| {
            if self.chooser.as_ref().is_some_and(|v| {
                v.rect.is_positive()
                    && root.input(|i| {
                        i.pointer.any_pressed()
                            && i.pointer
                                .interact_pos()
                                .is_some_and(|p| !v.rect.contains(p))
                    })
            }) {
                self.chooser = None;
                self.last_revision = u64::MAX;
            }
            if self.settings_only {
                self.editor.show_settings(root, &mut c);
            } else {
                self.editor
                    .show(root, &mut c, &mut self.selected, &mut self.edit_area);
                self.panel_focus.sync(
                    c.data.chart.config(),
                    c.data.identity.as_ref(),
                    previous_selection != self.selected && self.selected.is_some(),
                );
                self.fit_stage_width();
                // Tree/toolbar edits cancel a stale chooser before applying anything.
                if self
                    .chooser
                    .as_ref()
                    .is_some_and(|v| v.revision != c.data.revision)
                    || previous_selection != self.selected
                {
                    self.chooser = None;
                    self.last_revision = u64::MAX;
                }
                let display = self.display(&c).0;
                let dpr = ctx.pixels_per_point();
                if let Some(index) = self.panel_focus.index(&display, c.data.identity.as_ref()) {
                    let panels = interaction::overlapping_panels(&display, index);
                    if panels.len() > 1 {
                        let r = interaction::panel(&display, index).chart_area.0;
                        egui::Area::new(egui::Id::new("switch_chart"))
                            .order(egui::Order::Foreground)
                            .fixed_pos(egui::pos2(
                                (r.x + r.width) as f32 / dpr - 145.,
                                r.y as f32 / dpr + 5.,
                            ))
                            .show(root.ctx(), |ui| {
                                let response =
                                    ui.button(format!("Switch chart ({})", panels.len()));
                                self.editor
                                    .controls
                                    .insert("switch_chart".into(), response.rect);
                                if response.clicked() {
                                    self.chooser = Some(target_chooser::Chooser::new(
                                        panels
                                            .into_iter()
                                            .map(|i| target_chooser::Choice::panel(&c, i))
                                            .collect(),
                                        (response.rect.left() * dpr, response.rect.bottom() * dpr),
                                        c.data.revision,
                                    ));
                                    self.last_revision = u64::MAX;
                                }
                            });
                    }
                }
                if let Some(chooser) = &mut self.chooser {
                    let before = chooser.active;
                    let action =
                        chooser.show(root, self.editor.stage, dpr, &mut self.editor.controls);
                    if before != chooser.active {
                        self.last_revision = u64::MAX;
                    }
                    match action {
                        Some(target_chooser::Action::Choose(choice)) => {
                            if let Err(e) = self.choose_target(&mut c, choice) {
                                self.editor.error = e.to_string();
                            }
                        }
                        Some(target_chooser::Action::Cancel) => {
                            self.chooser = None;
                            self.last_revision = u64::MAX;
                        }
                        None => {}
                    }
                }
                let space = renderer::annotation::pixel_space_for_config(&display);
                if let Some(target) = self.editor.inline_text_ui(
                    root,
                    &mut c,
                    space,
                    |p| egui::pos2(p[0] / dpr, p[1] / dpr),
                    self.scale / dpr,
                ) {
                    self.selected = Some(target);
                    self.last_revision = u64::MAX;
                }
                self.editor
                    .drawing
                    .preview(&root.painter().with_clip_rect(self.editor.stage), |p| {
                        egui::pos2(p[0] / ctx.pixels_per_point(), p[1] / ctx.pixels_per_point())
                    });
            }
        });
        // Explicit export may temporarily select its RGBA target pipelines.
        c.renderer
            .ensure_target_format(self.config.format)
            .map_err(runtime)?;
        if previous_selection != self.selected {
            if c.data
                .chart
                .config()
                .picked_data
                .as_ref()
                .and_then(|p| p.refs.first())
                .is_some_and(|p| Some(p.series_id()) != self.selected.as_deref())
            {
                c.clear_data_selection()?;
            }
            self.last_revision = u64::MAX;
            self.window.request_redraw();
        }
        self.input
            .handle_platform_output(&self.window, output.platform_output);
        let previous_size = (self.config.width, self.config.height);
        self.sync_inspector_size();
        if previous_size != (self.config.width, self.config.height) {
            self.surface.configure(c.renderer.device(), &self.config);
        }
        self.fit_stage_width();
        let (display, panel, scale) = if self.settings_only {
            (
                c.data.chart.config().clone(),
                c.data.chart.config().chart_area.0,
                1.,
            )
        } else {
            self.display(&c)
        };
        self.panel = panel;
        self.scale = scale;
        // Use the final stage after inspector docking/resizing, like the chart.
        if !self.settings_only && !display.subplots.is_empty() {
            if let Some(index) = self
                .chooser
                .as_ref()
                .and_then(|v| v.preview())
                .map(|v| interaction::panel_index(v.layer))
                .or_else(|| self.panel_focus.index(&display, c.data.identity.as_ref()))
            {
                let dpr = output.pixels_per_point;
                let r = interaction::panel(&display, index).chart_area.0;
                let rect = egui::Rect::from_min_size(
                    egui::pos2(r.x as f32 / dpr, r.y as f32 / dpr),
                    egui::vec2(r.width as f32 / dpr, r.height as f32 / dpr),
                )
                .shrink(2.);
                output.shapes.push(egui::epaint::ClippedShape {
                    clip_rect: self.editor.stage,
                    shape: egui::Shape::rect_stroke(
                        rect,
                        3.,
                        egui::Stroke::new(1.5, egui::Color32::from_rgb(38, 99, 173)),
                        egui::StrokeKind::Inside,
                    ),
                });
            }
        }
        if !self.settings_only && self.view.is_none() {
            self.view = Some(
                c.renderer
                    .create_chart_view(&Chart::new(display.clone()), display.chart_area.0)
                    .map_err(runtime)?,
            );
        }
        if !self.settings_only
            && (c.data.revision != self.last_revision
                || self.selected != self.rendered_selection
                || scale != self.last_scale
                || self.last_pool_generation != c.renderer.pool().generation()
                || self.last_panel != Some(panel))
        {
            let preview_target = self
                .chooser
                .as_ref()
                .and_then(|v| v.preview())
                .and_then(|v| v.target.clone());
            let preview_map = HitMap::for_active_layer(&display);
            let boxes = preview_target
                .as_ref()
                .or(self.selected.as_ref())
                .as_deref()
                .and_then(|t| preview_map.find(t))
                .and_then(|id| {
                    preview_map.selection_box(
                        id,
                        &display,
                        &CpuTextMeasure::for_style(&display.draw_style),
                    )
                })
                .into_iter()
                .collect::<Vec<_>>();
            let annotation_selected = self
                .selected
                .as_deref()
                .and_then(|target| c.annotation_index(target).ok());
            c.renderer
                .refresh_axis_with_selection(
                    self.view.as_mut().unwrap(),
                    &Chart::new(display.clone()),
                    display.chart_area.0,
                    &boxes,
                )
                .map_err(runtime)?;
            // Let the renderer draw the selection from the current annotation
            // raster. A box taken from the previous view is stale after an edit.
            if self.view.as_ref().unwrap().annotation_selected() != annotation_selected {
                c.renderer
                    .refresh_annotations(
                        self.view.as_mut().unwrap(),
                        &Chart::new(display.clone()),
                        display.chart_area.0,
                        annotation_selected,
                    )
                    .map_err(runtime)?;
            }
            let specs = c.gpu_series(&c.data.series);
            self.styles = specs
                .iter()
                .zip(&c.data.series)
                .map(|(s, local)| {
                    let mut style_spec = s.clone();
                    style_spec.series_id = local.series_id.clone();
                    c.renderer
                        .create_style_for_series_scaled(&style_spec, scale)
                        .map_err(runtime)
                })
                .collect::<PyResult<Vec<_>>>()?;
            self.last_revision = c.data.revision;
            self.rendered_selection = self.selected.clone();
            self.last_scale = scale;
            self.last_pool_generation = c.renderer.pool().generation();
            self.last_panel = Some(panel);
        }
        let specs = c.gpu_series(&c.data.series);
        let series = specs
            .iter()
            .zip(&self.styles)
            .map(|(config, style)| renderer::Series { config, style })
            .collect::<Vec<_>>();
        let prepared = if self.settings_only {
            None
        } else {
            Some(
                c.renderer
                    .prepare(&[renderer::ChartDrawItem {
                        view: self.view.as_ref().unwrap(),
                        chart_config: &gpu::config(c.data.figure_id, &display),
                        series: &series,
                    }])
                    .map_err(runtime)?,
            )
        };
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
                        load: wgpu::LoadOp::Clear(background_wgpu(c.data.background)),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                ..Default::default()
            });
            if let Some(prepared) = &prepared {
                c.renderer
                    .paint_prepared(&mut pass, (self.config.width, self.config.height), prepared)
                    .map_err(runtime)?;
            }
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
        // egui popups use a sizing pass before their visible pass; text inputs
        // also request delayed caret redraws without another OS input event.
        self.repaint_at = output
            .viewport_output
            .get(&egui::ViewportId::ROOT)
            .filter(|viewport| viewport.repaint_delay != Duration::MAX)
            .and_then(|viewport| Instant::now().checked_add(viewport.repaint_delay));
        if self.settings_only {
            self.last_revision = c.data.revision;
        }
        self.frames += 1;
        if let Some(start) = self.last_input.take() {
            self.latency_ms = start.elapsed().as_secs_f64() * 1000.;
        }
        let dpr = output.pixels_per_point;
        let controls = self
            .editor
            .controls
            .iter()
            .map(|(name, rect)| {
                (
                    name.clone(),
                    json!([
                        rect.min.x * dpr,
                        rect.min.y * dpr,
                        rect.width() * dpr,
                        rect.height() * dpr
                    ]),
                )
            })
            .collect::<serde_json::Map<_, _>>();
        let measure = CpuTextMeasure::for_style(&display.draw_style);
        let decorations = c
            .data
            .elements
            .iter()
            .filter_map(|(name, id)| {
                c.data
                    .hitmap
                    .selection_box(*id, &display, &measure)
                    .map(|b| {
                        (
                            name.clone(),
                            json!([b.rect.x, b.rect.y, b.rect.width, b.rect.height]),
                        )
                    })
            })
            .collect::<serde_json::Map<_, _>>();
        let annotation_selection=self.view.as_ref().and_then(|view|{
            let index=view.annotation_selected()?;let id=view.annotation_map().find(index)?;let bounds=view.annotation_map().selection_box(id)?;
            Some(json!({"index":index,"rect":[bounds.rect.x,bounds.rect.y,bounds.rect.width,bounds.rect.height]}))
        });
        *self.control.stats.lock().unwrap() = json!({"layout_probe":self.editor.layout_probe,"choice_candidates":self.chooser.as_ref().map(|v|v.choices.iter().map(|v|json!({"key":v.key,"label":v.label,"detail":v.detail})).collect::<Vec<_>>()),"choice_preview":self.chooser.as_ref().and_then(|v|v.preview()).map(|v|&v.key),"focused_panel":self.panel_focus.id,"annotation_selection":annotation_selection,"host":"winit-wgpu","layout_mode":self.edit_area,"drawing_tool":self.editor.drawing.tool.name(),"window_role":if self.settings_only { "settings" } else { "chart" },"inspector_overlay":self.inspector_overlay(),"picked_values":self.editor.picked,"selection_value_readbacks":c.data.selection_value_readbacks,"error":self.editor.error,"controls":controls,"decorations":decorations,"selected":self.selected,"properties_open":self.editor.inspector_open,"chart_panel":[panel.x,panel.y,panel.width,panel.height],"gpu_context_id":c.context.id,"figure_id":c.data.figure_id,"pool_used_bytes":c.renderer.pool().used_bytes(),"surface_frames":self.frames,"last_input_to_submit_ms":self.latency_ms,"scale_factor":self.window.scale_factor(),"surface_size":[self.config.width,self.config.height],"column_uploads":c.data.uploads,"rgba_readbacks":c.data.readbacks,"png_encodes":c.data.png_encodes,"revision":c.data.revision});
        Ok(())
    }
}
/// Transform bounds in axis space so logarithmic and inverted axes behave like
/// linear axes. Shift is measured as a fraction of the visible span.
fn navigate_axis(axis: &mut renderer::config::AxisOptions, factor: f64, anchor: f64, shift: f64) {
    let log = axis.scale == renderer::config::AxisScale::Logarithmic;
    let (min, max) = if log {
        (axis.min.log10(), axis.max.log10())
    } else {
        (axis.min, axis.max)
    };
    let span = max - min;
    let anchor = if axis.inverted { 1. - anchor } else { anchor };
    let shift = if axis.inverted { -shift } else { shift };
    let pivot = min + span * anchor;
    let low = pivot + (min - pivot) * factor + shift * span;
    let high = pivot + (max - pivot) * factor + shift * span;
    let (low, high) = if log {
        (10_f64.powf(low), 10_f64.powf(high))
    } else {
        (low, high)
    };
    if low.is_finite()
        && high.is_finite()
        && low < high
        && (!log || low > 0.)
        && (high - low) <= f32::MAX as f64
        && low.abs() <= f32::MAX as f64
        && high.abs() <= f32::MAX as f64
    {
        axis.min = low;
        axis.max = high;
    }
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
        self.windows.retain(|_, w| {
            !w.control.close.load(Ordering::Acquire)
                && w.core.strong_count() > 0
                && w.parent.as_ref().is_none_or(|p| {
                    p.upgrade()
                        .is_some_and(|p| !p.close.load(Ordering::Acquire))
                })
        });
        let settings = self
            .windows
            .values_mut()
            .filter_map(|w| {
                if !std::mem::take(&mut w.editor.advanced_requested) {
                    return None;
                }
                if let Some(existing) = w.control.settings.lock().unwrap().as_ref() {
                    if !existing.close.load(Ordering::Acquire) {
                        return None;
                    }
                }
                Some((w.core.upgrade()?, Arc::clone(&w.control)))
            })
            .collect::<Vec<_>>();
        for (core, parent) in settings {
            let control = Arc::new(Control::default());
            match SurfaceWindow::new(
                events,
                &core,
                control.clone(),
                true,
                Some(Arc::downgrade(&parent)),
            ) {
                Ok(w) => {
                    *parent.settings.lock().unwrap() = Some(control);
                    w.window.request_redraw();
                    self.windows.insert(w.window.id(), w);
                }
                Err(e) => self.error = Some(e),
            }
        }
        for w in self.windows.values_mut() {
            let due = w
                .repaint_at
                .is_some_and(|deadline| Instant::now() >= deadline);
            if due {
                w.repaint_at = None;
            }
            if due
                || w.control.dirty.swap(false, Ordering::AcqRel)
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
            WindowEvent::Focused(false) => {
                w.chooser = None;
                w.pending_choices = None;
                w.last_revision = u64::MAX;
                w.modifiers = ModifiersState::empty();
                w.dragging = false;
                w.panning = false;
                w.chart_pressed = false;
                // Losing focus cancels an active gesture, not an armed tool.
                if w.editor.drawing.gesture.is_some() {
                    w.editor.drawing.cancel();
                }
                Ok(())
            }
            WindowEvent::ModifiersChanged(modifiers) => {
                w.modifiers = modifiers.state();
                Ok(())
            }
            WindowEvent::KeyboardInput { ref event, .. }
                if !w.settings_only
                    && event.state == ElementState::Pressed
                    && !w.ctx.egui_wants_keyboard_input()
                    && !response.consumed =>
            {
                if let Key::Named(key) = &event.logical_key {
                    w.keyboard(key)
                } else {
                    Ok(())
                }
            }
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
            WindowEvent::CursorMoved { position, .. } if !w.dragging => {
                w.cursor = (position.x as f32, position.y as f32);
                Ok(())
            }
            WindowEvent::CursorMoved { .. } => w.pointer(&event),
            WindowEvent::MouseInput {
                state: ElementState::Released,
                ..
            } if !w.settings_only => w.pointer(&event),
            _ if !w.settings_only
                && (w.chart_contains_cursor()
                    || (matches!(
                        event,
                        WindowEvent::MouseInput {
                            state: ElementState::Pressed,
                            button: MouseButton::Left,
                            ..
                        }
                    ) && w.editor.stage.contains(egui::pos2(
                        w.cursor.0 / w.ctx.pixels_per_point(),
                        w.cursor.1 / w.ctx.pixels_per_point(),
                    ))))
                && (!response.consumed
                    || w.ctx
                        .layer_id_at(egui::pos2(
                            w.cursor.0 / w.ctx.pixels_per_point(),
                            w.cursor.1 / w.ctx.pixels_per_point(),
                        ))
                        .is_none_or(|layer| layer.order == egui::Order::Background)) =>
            {
                w.pointer(&event)
            }
            _ => Ok(()),
        };
        if let Err(e) = result {
            w.editor.error = e.to_string();
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
            match SurfaceWindow::new(events, &core, control, false, None) {
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

fn active_coordinate_config(config: &Config) -> Config {
    match config.active_layer() {
        renderer::LayerRef::Subplot(i) | renderer::LayerRef::SubplotOverlay(i, _) => {
            config.subplot_config(i).unwrap_or_else(|| config.clone())
        }
        _ => config.clone(),
    }
}
fn navigate_document_axis(
    config: &mut Config,
    identity: Option<&Value>,
    dimension: &str,
    factor: f64,
    anchor: f64,
    shift: f64,
) {
    let layer = config.active_layer();
    let (panel, overlay) = match layer {
        renderer::LayerRef::Subplot(i) => (Some(i), None),
        renderer::LayerRef::SubplotOverlay(i, o) => (Some(i), Some(o)),
        renderer::LayerRef::Overlay(o) => (None, Some(o)),
        _ => (None, None),
    };
    let cfg = if let Some(i) = panel {
        &mut config.subplots[i].config
    } else {
        config
    };
    if dimension == "y"
        && let Some(o) = overlay
    {
        navigate_axis(&mut cfg.overlays[o].y_axis, factor, anchor, shift);
        if factor != 1. && crate::tick_policy::automatic(identity, layer, "right_y") {
            crate::tick_policy::retick(&mut cfg.overlays[o].y_axis);
        }
    } else if dimension == "x" {
        for (key, axis) in [("bottom_x", &mut cfg.bottom_x), ("top_x", &mut cfg.top_x)] {
            navigate_axis(axis, factor, anchor, shift);
            if factor != 1. && crate::tick_policy::automatic(identity, layer, key) {
                crate::tick_policy::retick(axis);
            }
        }
    } else {
        for (key, axis) in [("left_y", &mut cfg.left_y), ("right_y", &mut cfg.right_y)] {
            navigate_axis(axis, factor, anchor, shift);
            if factor != 1. && crate::tick_policy::automatic(identity, layer, key) {
                crate::tick_policy::retick(axis);
            }
        }
    }
}
