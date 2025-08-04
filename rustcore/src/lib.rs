use numpy::PyArray1;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use serde::Deserialize;

mod features;
mod welford;

use features::FeatureVec;

const LAMBDA: f64 = 0.995;
const IDX_LIQ_DELTA_ABS: usize = 0;
const IDX_LIQ_DELTA_RATIO: usize = 1;
const IDX_OF_SIGNED_VOL: usize = 64;
const IDX_OF_TRADE_COUNT: usize = 65;
const IDX_OF_IA_TIME_MS: usize = 66;

#[pyclass]

#[derive(Clone)]
pub struct PyEvent {
    pub tag: String,
    pub delta: Option<f64>,
    pub prev: Option<f64>,
    pub amount: Option<f64>,
    pub timestamp_ms: Option<i64>,
}

#[pymethods]
impl PyEvent {
    #[new]
    pub fn new(
        tag: String,
        delta: Option<f64>,
        prev: Option<f64>,
        amount: Option<f64>,
        timestamp_ms: Option<i64>,
    ) -> Self {
        Self {
            tag,
            delta,
            prev,
            amount,
            timestamp_ms,
        }
    }
}

#[pyclass]
#[derive(Clone)]
pub struct ParsedEvent {
    #[pyo3(get)]
    pub ts: i64,
    #[pyo3(get)]
    pub kind: String,
    #[pyo3(get)]
    pub amount_in: f64,
    #[pyo3(get)]
    pub amount_out: f64,
    #[pyo3(get)]
    pub reserve_a: f64,
    #[pyo3(get)]
    pub reserve_b: f64,
}

#[derive(Deserialize)]
struct RawLog {
    #[serde(rename = "type")]
    kind: String,
    ts: Option<i64>,
    amount_in: Option<f64>,
    amount_out: Option<f64>,
    reserve_a: Option<f64>,
    reserve_b: Option<f64>,
}

#[pyfunction]
pub fn parse_log(log: &str) -> PyResult<Option<ParsedEvent>> {
    match serde_json::from_str::<RawLog>(log) {
        Ok(raw) => Ok(Some(ParsedEvent {
            ts: raw.ts.unwrap_or(0),
            kind: raw.kind,
            amount_in: raw.amount_in.unwrap_or(0.0),
            amount_out: raw.amount_out.unwrap_or(0.0),
            reserve_a: raw.reserve_a.unwrap_or(0.0),
            reserve_b: raw.reserve_b.unwrap_or(0.0),
        })),
        Err(_) => Ok(None),
    }
}

#[pyclass]

pub struct FeatureEngine {
    fv: FeatureVec,
    lag1: [f32; 256],
    lag2: [f32; 256],
    /// Pre-allocated output buffer exposed to Python.
    out: Py<PyArray1<f32>>,
    last_swap_ts: Option<i64>,
}

#[pymethods]
impl FeatureEngine {
    #[new]
    pub fn new(py: Python<'_>) -> PyResult<Self> {
        // Allocate a contiguous NumPy array once; Rust mutates it in place.
        let out = PyArray1::<f32>::zeros(py, [256 * 3], false);
        Ok(Self {
            fv: FeatureVec::new(),
            lag1: [0.0; 256],
            lag2: [0.0; 256],
            out: out.into_py(py),
            last_swap_ts: None,
        })
    }

    pub fn push_event(&mut self, evt: PyEvent) -> PyResult<()> {
        match evt.tag.as_str() {
            "Liquidity" => {
                let delta = evt.delta.ok_or_else(|| PyValueError::new_err("missing delta"))?;
                let prev = evt.prev.ok_or_else(|| PyValueError::new_err("missing prev"))?;
                self.apply_liquidity(delta, prev);
            }
            "Swap" => {
                let amt = evt.amount.ok_or_else(|| PyValueError::new_err("missing amount"))?;
                let ts = evt.timestamp_ms.ok_or_else(|| PyValueError::new_err("missing timestamp"))?;
                self.apply_swap(amt, ts);
            }
            _ => return Err(PyValueError::new_err("unknown event tag")),
        }
        Ok(())
    }

    pub fn on_slot_end<'py>(&'py mut self, py: Python<'py>, _slot: u64) -> PyResult<&'py PyArray1<f32>> {
        // Build output slice without allocation. The NumPy array's memory is
        // mutated in place, avoiding per-slot heap churn.
        let out = self.out.as_ref(py);
        // Safety: `out` was allocated as contiguous f32 array above and is not
        // aliased while we hold the GIL.
        let slice = unsafe { out.as_slice_mut()? };
        slice[..256].copy_from_slice(&self.fv.data);
        slice[256..512].copy_from_slice(&self.lag1);
        slice[512..].copy_from_slice(&self.lag2);

        // Rotate lag buffers via swap to avoid copying 256 values per slot.
        std::mem::swap(&mut self.lag2, &mut self.lag1);
        std::mem::swap(&mut self.lag1, &mut self.fv.data);
        self.fv.reset_data();

        Ok(out)
    }

    pub fn get_stats(&self, idx: usize) -> (f64, f64) {
        (self.fv.means[idx], self.fv.vars[idx])
    }

    // Exposed for benchmarks
    pub fn push_swap_event(&mut self, amount: f64, timestamp_ms: i64) {
        self.apply_swap(amount, timestamp_ms);
    }
}

impl FeatureEngine {
    fn apply_liquidity(&mut self, delta: f64, prev: f64) {
        let abs = delta.abs();
        self.fv.data[IDX_LIQ_DELTA_ABS] += abs as f32;
        self.fv.update(IDX_LIQ_DELTA_ABS, abs, LAMBDA);
        let ratio = if prev.abs() > f64::EPSILON { delta / prev } else { 0.0 };
        self.fv.data[IDX_LIQ_DELTA_RATIO] += ratio as f32;
        self.fv.update(IDX_LIQ_DELTA_RATIO, ratio, LAMBDA);
    }

    fn apply_swap(&mut self, amount: f64, ts: i64) {
        self.fv.data[IDX_OF_SIGNED_VOL] += amount as f32;
        self.fv.update(IDX_OF_SIGNED_VOL, amount, LAMBDA);

        self.fv.data[IDX_OF_TRADE_COUNT] += 1.0;
        self.fv.update(IDX_OF_TRADE_COUNT, 1.0, LAMBDA);

        let dt = if let Some(last) = self.last_swap_ts {
            let delta = (ts - last) as f64;
            self.fv.data[IDX_OF_IA_TIME_MS] = delta as f32;
            self.last_swap_ts = Some(ts);
            delta
        } else {
            self.last_swap_ts = Some(ts);
            0.0
        };
        self.fv.update(IDX_OF_IA_TIME_MS, dt, LAMBDA);
    }
}

#[pymodule]
fn rustcore(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyEvent>()?;
    m.add_class::<FeatureEngine>()?;
    m.add_class::<ParsedEvent>()?;
    m.add_function(wrap_pyfunction!(parse_log, m)?)?;
    Ok(())
}
