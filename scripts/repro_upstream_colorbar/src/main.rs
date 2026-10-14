use renderer::{
    axis_render::{self, AxisLayerKind},
    default,
    layout::{ChartArea, Rect},
};
fn main() {
    let mut cfg = default::default_config();
    cfg.chart_area = ChartArea(Rect {
        x: 0,
        y: 0,
        width: 320,
        height: 240,
    });
    cfg.colorbar = Some(default::default_colorbar_options());
    cfg.chart_title.top_margin = -1e38;
    eprintln!("validation: {:?}", cfg.validate());
    eprintln!("data_area: {:?}", cfg.data_area());
    eprintln!("begin CPU decoration raster (no GPU initialization)");
    let result = axis_render::try_raster_chart_layer_to_rgba(&cfg, AxisLayerKind::Decoration);
    eprintln!("done: {:?}", result.map(|rgba| rgba.len()));
}
