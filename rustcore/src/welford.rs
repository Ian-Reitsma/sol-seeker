/// Exponential-moving (EWMA) variance update using Welford's method.
/// Implements the population form with decay factor `lambda`.
/// Reference: <https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance>
#[inline(always)]
pub fn update(mean: &mut f64, var: &mut f64, value: f64, lambda: f64) {
    let delta = value - *mean;
    *mean += (1.0 - lambda) * delta;
    *var = lambda * (*var + (1.0 - lambda) * delta * delta);
}
