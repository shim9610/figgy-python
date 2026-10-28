//! Opt-in, bounded timings of binding work. These are CPU wall times, not GPU timings.
use serde_json::{Value, json};
use std::{cell::RefCell, collections::BTreeMap, time::Instant};

#[derive(Default)]
struct Samples {
    count: u64,
    total_ms: f64,
    recent_ms: std::collections::VecDeque<f64>,
}

pub(crate) struct Profile {
    enabled: bool,
    samples: RefCell<BTreeMap<&'static str, Samples>>,
}

impl Default for Profile {
    fn default() -> Self {
        Self {
            enabled: std::env::var("FIGGY_PROFILE_HOST").as_deref() == Ok("1"),
            samples: Default::default(),
        }
    }
}

impl Profile {
    pub fn start(&self) -> Option<Instant> {
        self.enabled.then(Instant::now)
    }
    pub fn finish(&self, name: &'static str, start: Option<Instant>) {
        if let Some(start) = start {
            let ms = start.elapsed().as_secs_f64() * 1000.;
            let mut samples = self.samples.borrow_mut();
            let entry = samples.entry(name).or_default();
            entry.count += 1;
            entry.total_ms += ms;
            entry.recent_ms.push_back(ms);
            if entry.recent_ms.len() > 120 {
                entry.recent_ms.pop_front();
            }
        }
    }
    pub fn snapshot(&self) -> Value {
        let entries = self.samples.borrow().iter().map(|(name, entry)| {
            let mut values: Vec<_> = entry.recent_ms.iter().copied().collect();
            values.sort_by(f64::total_cmp);
            (name.to_string(), json!({"count":entry.count,"total_ms":entry.total_ms,
                "recent_count":values.len(),"p50_ms":values[values.len()/2],
                "p95_ms":values[((values.len() as f64 * 0.95).ceil() as usize-1).min(values.len()-1)],
                "max_ms":values.last()}))
        }).collect::<serde_json::Map<_,_>>();
        Value::Object(entries)
    }
}
