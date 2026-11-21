//! Ventana de Tauri comun a los proyectos de Jacck (de Venona; primero en IvyBells).
//!
//! Cada app deja en su `desktop/src-tauri/src/main.rs` solo esto:
//!
//! ```ignore
//! fn main() {
//!     let root = jacck_tauri::project_root("IVYBELLS", env!("CARGO_MANIFEST_DIR"));
//!     let spec = jacck_tauri::SidecarSpec::python("IVYBELLS", &root, &["main.py", "--api"], "logs/");
//!     jacck_tauri::run(spec, (0.75, 0.75), tauri::generate_context!(), |builder| builder);
//! }
//! ```
//!
//! `run` lanza la API de Python (`sidecar`), coloca la ventana `main` (`window`), registra
//! la orden `api_session` (la interfaz pide puerto y token con `invoke("api_session")`) y
//! apaga la API al salir. Nada de logica de negocio aqui (web_frontend.md).

pub mod sidecar;
pub mod window;

pub use sidecar::{project_root, ApiSession, PythonApi, SidecarSpec};

use tauri::{Builder, Context, Manager, RunEvent, Wry};

/// Etiqueta de la ventana que se coloca al abrir (la de `tauri.conf.json`).
pub const MAIN_WINDOW: &str = "main";

/// Puerto y token de la API para la interfaz.
#[tauri::command]
fn api_session(api: tauri::State<'_, PythonApi>) -> ApiSession {
    api.session()
}

/// Arma y corre la ventana. `customize` agrega lo propio de la app (plugins como el de
/// dialogos); si cambia `invoke_handler`, debe volver a incluir `api_session`.
pub fn run<F>(spec: SidecarSpec, screen_fraction: (f64, f64), context: Context<Wry>, customize: F)
where
    F: FnOnce(Builder<Wry>) -> Builder<Wry>,
{
    let builder = Builder::default()
        .manage(PythonApi::start(&spec))
        .invoke_handler(tauri::generate_handler![api_session])
        .setup(move |app| {
            if let Some(main) = app.get_webview_window(MAIN_WINDOW) {
                window::place_window(&main, screen_fraction)?;
            }
            Ok(())
        });
    let app = customize(builder)
        .build(context)
        .expect("no se pudo construir la ventana");
    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            handle.state::<PythonApi>().stop();
        }
    });
}
