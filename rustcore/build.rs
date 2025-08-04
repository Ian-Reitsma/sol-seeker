use std::{env, path::Path, process::Command};


fn main() {
    let manifest_dir = env::var("CARGO_MANIFEST_DIR").unwrap();
    let spec_path = Path::new(&manifest_dir).join("../src/sol_seeker/features/spec.py");
    // Execute a tiny Python snippet to parse the spec and validate index
    // coverage. This keeps the Rust build fast while enforcing drift
    // detection at compile time.
    let output = Command::new("python")
        .args([
            "-c",
            "import importlib.util,sys;sp=importlib.util.spec_from_file_location('spec',sys.argv[1]);m=importlib.util.module_from_spec(sp);sys.modules['spec']=m;sp.loader.exec_module(m);idx=[v.index for v in m.FEATURES.values()];print(len(idx),len(set(idx)),max(idx))",
            spec_path.to_str().unwrap(),
        ])
        .output()
        .expect("run python to parse spec");

    let out = String::from_utf8(output.stdout).expect("utf8");
    let parts: Vec<_> = out.trim().split_whitespace().collect();
    let len: usize = parts.get(0).and_then(|s| s.parse().ok()).unwrap_or(0);
    let uniq: usize = parts.get(1).and_then(|s| s.parse().ok()).unwrap_or(0);
    let max: usize = parts.get(2).and_then(|s| s.parse().ok()).unwrap_or(0);
    if len != 256 || uniq != 256 || max != 255 {
        panic!("feature spec must define 256 unique indices 0..255");
    }

    println!("cargo:rustc-env=FEATURE_COUNT=256");
    println!("cargo:rerun-if-changed=../src/sol_seeker/features/spec.py");
}