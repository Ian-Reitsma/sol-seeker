use criterion::{criterion_group, criterion_main, Criterion};
extern crate rustcore as rc;
use pyo3::Python;
use rc::FeatureEngine;

fn bench_swaps(c: &mut Criterion) {
    c.bench_function("swap_updates", |b| {
        b.iter(|| {
            Python::with_gil(|py| {
                let mut eng = FeatureEngine::new(py).unwrap();
                for i in 0..1_000_000 {
                    eng.push_swap_event(1.0, i);
                }
            })
        });
    });
}

criterion_group!(benches, bench_swaps);
criterion_main!(benches);
