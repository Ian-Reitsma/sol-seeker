use crate::event::Event;
use crate::features::FeatureVec;
use crate::welford;
use std::sync::atomic::{AtomicI64, Ordering};

pub trait Functor: Send + Sync {
    fn apply(&self, fv: &mut FeatureVec, evt: &Event);
}

const LAMBDA: f64 = 0.995;
const IDX_LIQ_DELTA_ABS: usize = 0;
const IDX_LIQ_DELTA_RATIO: usize = 1;
const IDX_OF_SIGNED_VOL: usize = 64;
const IDX_OF_TRADE_COUNT: usize = 65;
const IDX_OF_IA_TIME_MS: usize = 66;

pub struct LiqDeltaAbs;
impl Functor for LiqDeltaAbs {
    #[inline(always)]
    fn apply(&self, fv: &mut FeatureVec, evt: &Event) {
        if let Event::Liquidity { delta, .. } = evt {
            let abs = delta.abs();
            fv.data[IDX_LIQ_DELTA_ABS] += abs as f32;
            welford::update(&mut fv.means[IDX_LIQ_DELTA_ABS], &mut fv.vars[IDX_LIQ_DELTA_ABS], abs, LAMBDA);
        }
    }
}

pub struct LiqDeltaRatio;
impl Functor for LiqDeltaRatio {
    #[inline(always)]
    fn apply(&self, fv: &mut FeatureVec, evt: &Event) {
        if let Event::Liquidity { delta, prev } = evt {
            let ratio = if prev.abs() > f64::EPSILON { delta / prev } else { 0.0 };
            fv.data[IDX_LIQ_DELTA_RATIO] += ratio as f32;
            welford::update(&mut fv.means[IDX_LIQ_DELTA_RATIO], &mut fv.vars[IDX_LIQ_DELTA_RATIO], ratio, LAMBDA);
        }
    }
}

pub struct OfSignedVolume;
impl Functor for OfSignedVolume {
    #[inline(always)]
    fn apply(&self, fv: &mut FeatureVec, evt: &Event) {
        if let Event::Swap { amount, .. } = evt {
            fv.data[IDX_OF_SIGNED_VOL] += *amount as f32;
            welford::update(&mut fv.means[IDX_OF_SIGNED_VOL], &mut fv.vars[IDX_OF_SIGNED_VOL], *amount, LAMBDA);
        }
    }
}

pub struct OfTradeCount;
impl Functor for OfTradeCount {
    #[inline(always)]
    fn apply(&self, fv: &mut FeatureVec, evt: &Event) {
        if matches!(evt, Event::Swap { .. }) {
            fv.data[IDX_OF_TRADE_COUNT] += 1.0;
            welford::update(&mut fv.means[IDX_OF_TRADE_COUNT], &mut fv.vars[IDX_OF_TRADE_COUNT], 1.0, LAMBDA);
        }
    }
}

#[derive(Default)]
pub struct OfIaTimeMs {
    last: AtomicI64,
}
impl Functor for OfIaTimeMs {
    #[inline(always)]
    fn apply(&self, fv: &mut FeatureVec, evt: &Event) {
        if let Event::Swap { timestamp_ms, .. } = evt {
            let last = self.last.swap(*timestamp_ms, Ordering::SeqCst);
            let dt = if last == 0 { 0.0 } else { (*timestamp_ms - last) as f64 };
            fv.data[IDX_OF_IA_TIME_MS] = dt as f32;
            welford::update(&mut fv.means[IDX_OF_IA_TIME_MS], &mut fv.vars[IDX_OF_IA_TIME_MS], dt, LAMBDA);
        }
    }
}

// Registry
use once_cell::sync::Lazy;
use std::collections::HashMap;
use std::sync::Arc;

pub static REGISTRY: Lazy<HashMap<&'static str, Arc<dyn Functor>>> = Lazy::new(|| {
    let mut m: HashMap<&'static str, Arc<dyn Functor>> = HashMap::new();
    m.insert("liq_pool_delta_abs", Arc::new(LiqDeltaAbs));
    m.insert("liq_pool_delta_ratio", Arc::new(LiqDeltaRatio));
    m.insert("of_signed_volume", Arc::new(OfSignedVolume));
    m.insert("of_trade_count", Arc::new(OfTradeCount));
    m.insert("of_ia_time_ms", Arc::new(OfIaTimeMs::default()));
    m
});

// helper arrays mapping event types to functor keys
pub static LIQ_KEYS: &[&str] = &["liq_pool_delta_abs", "liq_pool_delta_ratio"];
pub static SWAP_KEYS: &[&str] = &["of_signed_volume", "of_trade_count", "of_ia_time_ms"];
