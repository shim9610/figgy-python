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
    undo: VecDeque<Entry>,
    redo: Vec<Entry>,
    gesture: Option<(Value, u64, String)>,
    replaying: bool,
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
    pub fn record(
        &mut self,
        before: Value,
        after: Value,
        base_revision: u64,
        revision: u64,
        label: &str,
    ) {
        if self.replaying {
            return;
        }
        if source_key(&before) != source_key(&after) {
            *self = Self::default(); // Existing source arrays cannot be resurrected by settings replay.
            return;
        }
        let before = persistent(before);
        let after = persistent(after);
        if before == after || self.gesture.is_some() {
            return;
        }
        self.redo.clear();
        let bytes = before.to_string().len() + after.to_string().len();
        if bytes > MAX_BYTES {
            self.undo.clear();
            return;
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
            "undo_label":self.undo.back().map(|v|&v.label),"redo_label":self.redo.last().map(|v|&v.label),
            "undo_count":self.undo.len(),"redo_count":self.redo.len(),"gesture_active":self.gesture.is_some()})
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
                    fields.insert("selected".into(), Value::Null);
                    fields.insert("hovered".into(), Value::Null);
                    fields.insert("hover_progress".into(), json!(0.));
                }
            }
        }
        self.replaying = true;
        Ok(target)
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
