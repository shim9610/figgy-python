//! Renderer document changes for view gestures, shared by native and WASM.
use renderer::{
    Config, LayerRef,
    config::{AxisOptions, AxisScale},
};
use serde_json::Value;

#[path = "tick_policy.rs"]
pub(crate) mod tick_policy;

pub(crate) enum Gesture {
    Pan {
        pixels: [f32; 2],
        logical: [f32; 2],
        area: [f32; 2],
    },
    Zoom {
        factor: f64,
        anchor: [f64; 2],
        axes: [bool; 2],
    },
}

pub(crate) fn layer_parts(layer: LayerRef) -> (Option<usize>, Option<usize>) {
    match layer {
        LayerRef::Subplot(i) => (Some(i), None),
        LayerRef::SubplotOverlay(i, o) => (Some(i), Some(o)),
        LayerRef::Overlay(o) => (None, Some(o)),
        _ => (None, None),
    }
}

pub(crate) fn apply(config: &mut Config, identity: Option<&Value>, gesture: Gesture) -> bool {
    let layer = config.active_layer();
    let (panel, overlay) = layer_parts(layer);
    let base = panel.map_or(LayerRef::Base, LayerRef::Subplot);
    let config = if let Some(i) = panel {
        &mut config.subplots[i].config
    } else {
        config
    };
    if config.view_3d().is_some() {
        return match gesture {
            Gesture::Pan {
                logical: [dx, dy], ..
            } => config.orbit_view(dx, dy),
            Gesture::Zoom { factor, .. } => config.zoom_view(factor.recip()),
        };
    }
    let (factor, anchor, shift, axes) = match gesture {
        Gesture::Pan {
            pixels: [dx, dy],
            area: [width, height],
            ..
        } => (
            1.,
            [0.5; 2],
            [
                -f64::from(dx) / f64::from(width.max(1.)),
                f64::from(dy) / f64::from(height.max(1.)),
            ],
            [true; 2],
        ),
        Gesture::Zoom {
            factor,
            anchor,
            axes,
        } => (factor, anchor, [0.; 2], axes),
    };
    let mut change = false;
    let mut update = |key: &str, axis: &mut AxisOptions, dimension: usize, owner: LayerRef| {
        if axes[dimension] && navigate_axis(axis, factor, anchor[dimension], shift[dimension]) {
            if factor != 1. && tick_policy::automatic(identity, owner, key) {
                tick_policy::retick(axis);
            }
            change = true;
        }
    };
    let mut overlay = overlay.and_then(|i| config.overlays.get_mut(i));
    if let Some(o) = overlay.as_deref_mut().filter(|o| !o.link_x) {
        update("x_axis", &mut o.x_axis, 0, layer);
    } else {
        update("bottom_x", &mut config.bottom_x, 0, base);
        update("top_x", &mut config.top_x, 0, base);
    }
    if let Some(o) = overlay.filter(|o| !o.link_y) {
        update("right_y", &mut o.y_axis, 1, layer);
    } else {
        update("left_y", &mut config.left_y, 1, base);
        update("right_y", &mut config.right_y, 1, base);
    }
    change
}

/// Scale and translate a linear or logarithmic range in its display space.
fn navigate_axis(axis: &mut AxisOptions, factor: f64, anchor: f64, shift: f64) -> bool {
    if factor == 1. && shift == 0. {
        return false;
    }
    let log = axis.scale == AxisScale::Logarithmic;
    let (min, max) = if log {
        (axis.min.log10(), axis.max.log10())
    } else {
        (axis.min, axis.max)
    };
    let span = max - min;
    let (anchor, shift) = if axis.inverted {
        (1. - anchor, -shift)
    } else {
        (anchor, shift)
    };
    let pivot = min + span * anchor;
    let low = pivot + (min - pivot) * factor + shift * span;
    let high = pivot + (max - pivot) * factor + shift * span;
    if ![low, high, high - low]
        .iter()
        .all(|v| (*v as f32).is_finite())
        || low >= high
    {
        return false;
    }
    let (low, high) = if log {
        (10_f64.powf(low), 10_f64.powf(high))
    } else {
        (low, high)
    };
    if !low.is_finite()
        || !high.is_finite()
        || low >= high
        || (log && low <= 0.)
        || (low, high) == (axis.min, axis.max)
    {
        return false;
    }
    axis.min = low;
    axis.max = high;
    true
}
