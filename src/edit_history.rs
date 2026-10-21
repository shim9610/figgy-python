//! Persistent document edits, independent of host selection and GPU resources.
use super::*;
use std::collections::VecDeque;

const MAX_ENTRIES: usize = 128;
const MAX_BYTES: usize = 8 * 1024 * 1024;

#[derive(Clone, Serialize)]
pub(crate) struct Change {
    pub path: String,
    pub object_id: String,
    pub before: Option<Value>,
    pub after: Option<Value>,
    pub before_exists: bool,
    pub after_exists: bool,
}

#[derive(Clone)]
struct Entry {
    before: Value,
    after: Value,
    base_revision: u64,
    revision: u64,
    label: String,
    bytes: usize,
}

#[derive(Clone, Default)]
pub(crate) struct History {
    baseline: Option<Value>,
    undo: VecDeque<Entry>,
    redo: Vec<Entry>,
    gesture: Option<(Value, u64, String)>,
    gesture_changed: bool,
    replaying: bool,
    restoring: bool,
    dirty: bool,
}

/// Selection fields are serialized for renderer compatibility, but are not edits.
pub(crate) fn persistent(mut state: Value) -> Value {
    fn config(value: &mut Value) {
        if let Some(fields) = value.as_object_mut() {
            for key in ["active_layer", "picked_data", "picked_points"] {
                fields.remove(key);
            }
        }
        if let Some(panels) = value.get_mut("subplots").and_then(Value::as_array_mut) {
            for panel in panels {
                config(&mut panel["config"]);
            }
        }
    }
    config(&mut state["config"]);
    for kind in ["radial", "categorical", "boxplot", "radar"] {
        if let Some(chart) = state.get_mut(kind) {
            if let Some(fields) = chart.as_object_mut() {
                for key in ["selected", "hovered", "active_layer"] {
                    fields.remove(key);
                }
            }
            if let Some(fields) = chart.get_mut("decorations").and_then(Value::as_object_mut) {
                fields.remove("selected");
            }
            if let Some(fields) = chart.get_mut("interaction").and_then(Value::as_object_mut) {
                for key in ["selected", "hovered", "hover_progress"] {
                    fields.remove(key);
                }
            }
        }
    }
    state
}

fn source_key(state: &Value) -> Value {
    let family = ["radial", "categorical", "boxplot", "radar"]
        .into_iter()
        .find(|k| state.get(*k).is_some());
    json!({"figure":state["identity"]["figure"],"family":family,
        "series":state["series"].as_array().map(|v|v.iter().map(|s|json!([s["series_id"],s["x_column"],s["y_column"]])).collect::<Vec<_>>())})
}

impl FigureAccess<'_> {
    pub(crate) fn reset_edits(&mut self) -> PyResult<()> {
        let current = serde_json::to_value(self.snapshot()).map_err(runtime)?;
        let target = self.data.history.reset_target(&current)?;
        self.begin_edit("Reset edits");
        self.data.history.restoring = true;
        let result = self.apply_settings(&target.to_string());
        self.data.history.restoring = false;
        self.end_edit();
        result
    }
    pub(crate) fn begin_edit(&mut self, label: &str) {
        let state = serde_json::to_value(self.snapshot()).unwrap();
        self.data.history.begin(state, self.data.revision, label);
    }
    pub(crate) fn end_edit(&mut self) {
        let state = serde_json::to_value(self.snapshot()).unwrap();
        self.data.history.finish(state, self.data.revision);
    }
    pub(crate) fn replay_edit(&mut self, redo: bool) -> PyResult<()> {
        let current = serde_json::to_value(self.snapshot()).map_err(runtime)?;
        let target = self.data.history.target(redo, &current)?;
        let result = self.apply_settings(&target.to_string());
        self.data.history.complete(redo, result.is_ok());
        result
    }
}

fn escape(value: &str) -> String {
    value.replace('~', "~0").replace('/', "~1")
}

fn object_id(state: &Value, path: &str) -> String {
    let parts: Vec<_> = path.split('/').collect();
    let figure = state["identity"]["figure"].as_str().unwrap_or("figure");
    let mut result = format!("figure/{figure}");
    for (index, part) in parts.iter().enumerate() {
        if *part == "series" {
            if let Some(id) = parts
                .get(index + 1)
                .and_then(|v| v.parse::<usize>().ok())
                .and_then(|i| state["series"][i]["series_id"].as_str())
            {
                return format!("{result}/series/{id}");
            }
        }
        if *part == "subplots" {
            if let Some(id) = parts
                .get(index + 1)
                .and_then(|v| v.parse::<usize>().ok())
                .and_then(|i| state["identity"]["panels"][i + 1]["id"].as_str())
            {
                result.push_str(&format!("/panel/{id}"));
            }
        }
        if *part == "items"
            && index + 1 < parts.len()
            && parts.get(index.wrapping_sub(1)) == Some(&"annotations")
        {
            let prefix = parts[..=index + 1].join("/");
            if let Some(id) = state.pointer(&prefix).and_then(|v| v["id"].as_str()) {
                return format!("{result}/annotation/{id}");
            }
        }
    }
    result
}

pub(crate) fn changes(before: &Value, after: &Value) -> Vec<Change> {
    fn walk(
        a: Option<&Value>,
        b: Option<&Value>,
        path: String,
        state: &Value,
        out: &mut Vec<Change>,
    ) {
        if a == b {
            return;
        }
        match (a, b) {
            (Some(Value::Object(a)), Some(Value::Object(b))) => {
                let keys: std::collections::BTreeSet<_> = a.keys().chain(b.keys()).collect();
                for key in keys {
                    walk(
                        a.get(key),
                        b.get(key),
                        format!("{path}/{}", escape(key)),
                        state,
                        out,
                    );
                }
            }
            (Some(Value::Array(a)), Some(Value::Array(b))) if a.len() == b.len() => {
                for (i, (a, b)) in a.iter().zip(b).enumerate() {
                    walk(Some(a), Some(b), format!("{path}/{i}"), state, out);
                }
            }
            _ => out.push(Change {
                object_id: object_id(state, &path),
                path,
                before: a.cloned(),
                after: b.cloned(),
                before_exists: a.is_some(),
                after_exists: b.is_some(),
            }),
        }
    }
    let mut out = vec![];
    walk(Some(before), Some(after), String::new(), after, &mut out);
    out
}

impl History {
    pub fn restoring_identities(&self) -> bool {
        self.replaying || self.restoring
    }
    pub fn set_restoring(&mut self, restoring: bool) {
        self.restoring = restoring;
    }
    pub fn mark_baseline(&mut self, state: Value) -> PyResult<()> {
        if self.gesture.is_some() {
            return Err(invalid(
                "finish the current edit before setting the reset baseline",
            ));
        }
        self.baseline = Some(persistent(state));
        self.dirty = false;
        Ok(())
    }
    pub fn record(
        &mut self,
        before: Value,
        after: Value,
        base_revision: u64,
        revision: u64,
        label: &str,
    ) {
        if source_key(&before) != source_key(&after) {
            *self = Self::default(); // Existing source arrays cannot be resurrected by settings replay.
            return;
        }
        let before = persistent(before);
        let after = persistent(after);
        self.gesture_changed = self
            .gesture
            .as_ref()
            .is_some_and(|(start, _, _)| persistent(start.clone()) != after);
        if self.baseline.is_none() && before != after {
            self.baseline = Some(before.clone());
        }
        self.dirty = self.baseline.as_ref().is_some_and(|v| v != &after);
        if self.replaying {
            return;
        }
        if before == after || self.gesture.is_some() {
            return;
        }
        self.redo.clear();
        let bytes = before.to_string().len() + after.to_string().len();
        if bytes > MAX_BYTES {
            self.undo.clear();
            return;
        }
        if self.baseline.is_none() {
            self.baseline = Some(before.clone());
        }
        self.undo.push_back(Entry {
            before,
            after,
            base_revision,
            revision,
            label: label.into(),
            bytes,
        });
        while self.undo.len() > MAX_ENTRIES
            || self.undo.iter().map(|v| v.bytes).sum::<usize>() > MAX_BYTES
        {
            self.undo.pop_front();
        }
    }
    pub fn begin(&mut self, state: Value, revision: u64, label: &str) {
        if self.gesture.is_none() {
            self.gesture_changed = false;
            self.gesture = Some((state, revision, label.into()));
        }
    }
    pub fn finish(&mut self, state: Value, revision: u64) {
        if let Some((before, base, label)) = self.gesture.take() {
            self.record(before, state, base, revision, &label);
        }
    }
    pub fn status(&self) -> Value {
        json!({"can_undo":!self.undo.is_empty(),"can_redo":!self.redo.is_empty(),
            "can_reset":self.dirty,
            "undo_label":self.undo.back().map(|v|&v.label),"redo_label":self.redo.last().map(|v|&v.label),
            "undo_count":self.undo.len(),"redo_count":self.redo.len(),"gesture_active":self.gesture.is_some(),"pending_edit":self.gesture_changed})
    }
    pub fn operations(&self) -> Value {
        json!(
            self.undo
                .iter()
                .map(|v| json!({"label":v.label,"base_revision":v.base_revision,
            "revision":v.revision,"changes":changes(&v.before,&v.after)}))
                .collect::<Vec<_>>()
        )
    }
    pub fn target(&mut self, redo: bool, current: &Value) -> PyResult<Value> {
        if self.gesture.is_some() {
            return Err(invalid("finish the current edit before undo/redo"));
        }
        let entry = if redo {
            self.redo.last()
        } else {
            self.undo.back()
        }
        .ok_or_else(|| {
            invalid(if redo {
                "nothing to redo"
            } else {
                "nothing to undo"
            })
        })?;
        let expected = if redo { &entry.before } else { &entry.after };
        if &persistent(current.clone()) != expected {
            return Err(invalid(
                "document changed outside the edit history; refresh before undo/redo",
            ));
        }
        let mut target = if redo {
            entry.after.clone()
        } else {
            entry.before.clone()
        };
        target = restore_transient(target, current);
        self.replaying = true;
        Ok(target)
    }
    pub fn reset_target(&self, current: &Value) -> PyResult<Value> {
        if self.gesture.is_some() {
            return Err(invalid("finish the current edit before resetting"));
        }
        let baseline = self
            .baseline
            .as_ref()
            .ok_or_else(|| invalid("no edits to reset"))?;
        if source_key(baseline) != source_key(current) {
            return Err(invalid("source data changed; start a new edit history"));
        }
        Ok(restore_transient(baseline.clone(), current))
    }
    pub fn complete(&mut self, redo: bool, success: bool) {
        self.replaying = false;
        if success {
            if redo {
                self.undo.push_back(self.redo.pop().unwrap());
            } else {
                self.redo.push(self.undo.pop_back().unwrap());
            }
        }
    }
}

fn restore_transient(mut target: Value, current: &Value) -> Value {
    // Preserve a still-valid coordinate owner, rather than making undo jump
    // to the root chart. Selection/highlight references are cleared below.
    if let Some(layer) = current["config"].get("active_layer") {
        let config = &target["config"];
        let valid = if let Some(i) = layer.get("Subplot").and_then(Value::as_u64) {
            config["subplots"]
                .as_array()
                .is_some_and(|v| (i as usize) < v.len())
        } else if let Some(i) = layer.get("Overlay").and_then(Value::as_u64) {
            config["overlays"]
                .as_array()
                .is_some_and(|v| (i as usize) < v.len())
        } else if let Some(indices) = layer.get("SubplotOverlay").and_then(Value::as_array) {
            indices.len() == 2
                && indices[0]
                    .as_u64()
                    .zip(indices[1].as_u64())
                    .is_some_and(|(i, j)| {
                        config["subplots"][i as usize]["config"]["overlays"]
                            .as_array()
                            .is_some_and(|v| (j as usize) < v.len())
                    })
        } else {
            layer == "Base" || layer == "Annotations"
        };
        if valid {
            target["config"]["active_layer"] = layer.clone();
        }
    }
    // Clear transient references: an annotation restored/removed by replay
    // need not share the current selection. Hosts retain their own focus.
    for kind in ["radial", "categorical", "boxplot", "radar"] {
        if let Some(chart) = target.get_mut(kind) {
            if let Some(layer) = current[kind].get("active_layer") {
                chart["active_layer"] = layer.clone();
            }
            if let Some(fields) = chart.get_mut("interaction").and_then(Value::as_object_mut) {
                fields.insert(
                    "selected".into(),
                    current[kind]["interaction"]["selected"].clone(),
                );
                fields.insert("hovered".into(), Value::Null);
                fields.insert("hover_progress".into(), json!(0.));
            }
            if let Some(selected) = current[kind].get("selected") {
                chart["selected"] = selected.clone();
            }
            if let Some(selected) = current[kind]["decorations"].get("selected") {
                let selected = if let Some(index) = selected["Annotation"].as_u64() {
                    current[kind]["annotations"]["items"][index as usize]["id"]
                        .as_str()
                        .and_then(|id| {
                            chart["annotations"]["items"]
                                .as_array()?
                                .iter()
                                .position(|v| v["id"] == id)
                        })
                        .map(|i| json!({"Annotation":i}))
                        .unwrap_or(Value::Null)
                } else {
                    selected.clone()
                };
                chart["decorations"]["selected"] = selected;
            }
        }
    }
    // A restored document can remove the currently selected category/outlier.
    // Validate only this copied transient state; the retained document itself
    // was accepted before it entered history.
    let valid = serde_json::from_value::<Settings>(target.clone())
        .ok()
        .and_then(|s| s.document().ok().map(|d| (s.config.chart_area.0, d)))
        .is_some_and(|(area, document)| document.is_none_or(|d| d.validate(area).is_ok()));
    if !valid {
        for kind in ["radial", "categorical", "boxplot", "radar"] {
            if let Some(chart) = target.get_mut(kind) {
                if chart.get("selected").is_some() {
                    chart["selected"] = Value::Null;
                }
                if chart.get("interaction").is_some() {
                    chart["interaction"]["selected"] = Value::Null;
                }
                chart["decorations"]["selected"] = Value::Null;
            }
        }
    }

    target
}
