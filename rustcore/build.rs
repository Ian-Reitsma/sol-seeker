use std::{env, fs, path::Path};

fn main() {
    let manifest_dir = env::var("CARGO_MANIFEST_DIR").unwrap();
    let spec_path = Path::new(&manifest_dir).join("../src/sol_seeker/features/spec.py");
    let contents = fs::read_to_string(&spec_path).expect("read spec.py");
    if !contents.contains("for i in range(256):") {
        panic!("spec missing 256-slot range");
    }
    println!("cargo:rustc-env=FEATURE_COUNT=256");
}
