fn main() {
    tauri_build::build();
    enforce_bundled_runtime_for_release();
}

fn enforce_bundled_runtime_for_release() {
    if std::env::var("PROFILE").unwrap_or_default() != "release" {
        return;
    }

    let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let runtime_dir = manifest_dir.join("resources").join("runtime");
    let exe_name = if cfg!(windows) {
        "account-matrix-runtime.exe"
    } else {
        "account-matrix-runtime"
    };
    let runtime_exe = runtime_dir.join(exe_name);
    let runtime_manifest = runtime_dir.join("runtime-manifest.json");

    if !runtime_exe.is_file() || !runtime_manifest.is_file() {
        panic!(
            "release build requires bundled runtime files: {} and {}",
            runtime_exe.display(),
            runtime_manifest.display()
        );
    }
}
