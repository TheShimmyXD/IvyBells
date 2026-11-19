//! Ventana de escritorio de IvyBells: todo lo de Tauri vive en el crate comun
//! `jacck_tauri`; aqui solo van el prefijo, como se lanza la API y el tamano al abrir.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

const PREFIX: &str = "IVYBELLS";
/// Fraccion del area libre del monitor al abrir.
const SCREEN_FRACTION: (f64, f64) = (0.75, 0.75);

fn main() {
    let root = jacck_tauri::project_root(PREFIX, env!("CARGO_MANIFEST_DIR"));
    let spec =
        jacck_tauri::SidecarSpec::python(PREFIX, &root, &["main.py", "--api"], "logs/ivybells.log");
    jacck_tauri::run(
        spec,
        SCREEN_FRACTION,
        tauri::generate_context!(),
        |builder| builder,
    );
}
