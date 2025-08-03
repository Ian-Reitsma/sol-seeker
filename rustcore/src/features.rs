use crate::welford;

#[repr(align(64))]
pub struct FeatureVec {
    pub data: [f32; 256],
    pub means: [f64; 256],
    pub vars: [f64; 256],
}

impl FeatureVec {
    #[inline(always)]
    pub fn new() -> Self {
        Self {
            data: [0.0; 256],
            means: [0.0; 256],
            vars: [0.0; 256],
        }
    }

    #[inline(always)]
    pub fn reset_data(&mut self) {
        // Only the raw data slice is cleared at slot boundaries.
        // Running means/vars persist to maintain decay across slots.
        self.data = [0.0; 256];
    }

    #[inline(always)]
    pub fn copy_to_slice(&self, out: &mut [f32]) {
        out.copy_from_slice(&self.data);
    }

    #[inline(always)]
    pub fn update(&mut self, idx: usize, value: f64, lambda: f64) {
        welford::update(&mut self.means[idx], &mut self.vars[idx], value, lambda);
    }
}
