//! La API de Python como proceso hijo de la ventana (de Venona; primero en IvyBells).
//!
//! 1. Genera el token y se lo pasa en `<APP>_API_TOKEN`.
//! 2. Lanza el programa de la app (por defecto `.venv/bin/python` con sus argumentos)
//!    desde la raiz del proyecto con `<APP>_API_WATCH_STDIN=1` y se queda con su entrada.
//! 3. Lee de su salida la linea `<APP>_API_PORT=<puerto>`.
//! 4. Al salir cierra esa entrada: el Python apaga solo y borra su sesion; si en
//!    `stop_grace` no termino, lo mata. Si la ventana muere de golpe, el sistema cierra el
//!    tubo y el Python tambien apaga: no queda ningun proceso suelto.
//!
//! Los nombres salen del prefijo igual que en `jacck_common.webapi.names` (Python): si uno
//! cambia, cambia el otro.

use serde::Serialize;
use std::ffi::OsString;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

const STOP_GRACE: Duration = Duration::from_secs(5);
const STOP_POLL: Duration = Duration::from_millis(50);
const TOKEN_BYTES: usize = 32;

/// Lo que la interfaz necesita para hablar con la API; `error` en español si no arranco.
#[derive(Clone, Debug, Default, PartialEq, Serialize)]
pub struct ApiSession {
    pub port: Option<u16>,
    pub token: String,
    pub error: Option<String>,
}

/// Como lanzar la API de una app.
#[derive(Clone, Debug)]
pub struct SidecarSpec {
    /// Prefijo de la app en mayusculas: `IVYBELLS`, `VENONA`.
    pub prefix: String,
    /// Raiz del proyecto: ahi corre el programa.
    pub root: PathBuf,
    pub program: PathBuf,
    pub args: Vec<OsString>,
    /// Donde mirar si la API no arranca (se muestra en el error).
    pub log_hint: String,
    pub stop_grace: Duration,
}

impl SidecarSpec {
    /// El `.venv/bin/python` de la raiz con `args` (por ejemplo `main.py --api`).
    pub fn python(prefix: &str, root: &Path, args: &[&str], log_hint: &str) -> Self {
        Self {
            prefix: prefix.to_string(),
            root: root.to_path_buf(),
            program: python_path(root),
            args: args.iter().map(OsString::from).collect(),
            log_hint: log_hint.to_string(),
            stop_grace: STOP_GRACE,
        }
    }

    pub fn token_env(&self) -> String {
        format!("{}_API_TOKEN", self.prefix)
    }

    pub fn port_prefix(&self) -> String {
        format!("{}_API_PORT=", self.prefix)
    }

    pub fn watch_stdin_env(&self) -> String {
        format!("{}_API_WATCH_STDIN", self.prefix)
    }
}

pub fn parse_port(line: &str, port_prefix: &str) -> Option<u16> {
    line.trim().strip_prefix(port_prefix)?.parse().ok()
}

pub fn new_token() -> Result<String, getrandom::Error> {
    let mut bytes = [0u8; TOKEN_BYTES];
    getrandom::fill(&mut bytes)?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

/// `<APP>_ROOT` si esta puesta; si no, dos carpetas arriba de `manifest_dir` (el
/// `desktop/src-tauri` de la app: se le pasa `env!("CARGO_MANIFEST_DIR")`).
pub fn project_root(prefix: &str, manifest_dir: &str) -> PathBuf {
    let root = std::env::var_os(format!("{prefix}_ROOT"))
        .map(PathBuf::from)
        .unwrap_or_else(|| Path::new(manifest_dir).join("../.."));
    root.canonicalize().unwrap_or(root)
}

pub fn python_path(root: &Path) -> PathBuf {
    root.join(".venv").join("bin").join("python")
}

/// Lee la salida del Python hasta el final: anota el puerto y, si el proceso termina sin
/// anunciarlo, deja el error. Seguir leyendo evita que el tubo se llene.
pub fn read_port<R: BufRead>(
    reader: R,
    port_prefix: &str,
    log_hint: &str,
    session: &Mutex<ApiSession>,
) {
    for line in reader.lines().map_while(Result::ok) {
        if let Some(port) = parse_port(&line, port_prefix) {
            session.lock().expect("sesion de la API").port = Some(port);
        }
    }
    let mut current = session.lock().expect("sesion de la API");
    if current.port.is_none() && current.error.is_none() {
        current.error = Some(format!(
            "La API de Python terminó sin anunciar su puerto (ver {log_hint})."
        ));
    }
}

pub struct PythonApi {
    child: Mutex<Option<Child>>,
    stdin: Mutex<Option<ChildStdin>>,
    session: Arc<Mutex<ApiSession>>,
    stop_grace: Duration,
}

impl PythonApi {
    /// Lanza la API; si no se puede, la ventana abre igual y muestra el error.
    pub fn start(spec: &SidecarSpec) -> Self {
        let session = Arc::new(Mutex::new(ApiSession::default()));
        let api = Self {
            child: Mutex::new(None),
            stdin: Mutex::new(None),
            session: Arc::clone(&session),
            stop_grace: spec.stop_grace,
        };
        let token = match new_token() {
            Ok(token) => token,
            Err(error) => {
                api.fail(format!("No se pudo generar el token de la sesión: {error}"));
                return api;
            }
        };
        let spawned = Command::new(&spec.program)
            .args(&spec.args)
            .current_dir(&spec.root)
            .env(spec.token_env(), &token)
            .env(spec.watch_stdin_env(), "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn();
        let mut child = match spawned {
            Ok(child) => child,
            Err(error) => {
                let program = spec.program.display();
                api.fail(format!("No se pudo lanzar {program}: {error}"));
                return api;
            }
        };
        session.lock().expect("sesion de la API").token = token;
        if let Some(stdout) = child.stdout.take() {
            let shared = Arc::clone(&session);
            let (port_prefix, log_hint) = (spec.port_prefix(), spec.log_hint.clone());
            thread::spawn(move || {
                read_port(BufReader::new(stdout), &port_prefix, &log_hint, &shared)
            });
        }
        *api.stdin.lock().expect("entrada de la API") = child.stdin.take();
        *api.child.lock().expect("proceso de la API") = Some(child);
        api
    }

    fn fail(&self, message: String) {
        self.session.lock().expect("sesion de la API").error = Some(message);
    }

    pub fn session(&self) -> ApiSession {
        self.session.lock().expect("sesion de la API").clone()
    }

    pub fn pid(&self) -> Option<u32> {
        self.child
            .lock()
            .expect("proceso de la API")
            .as_ref()
            .map(Child::id)
    }

    /// Cierra la entrada del Python y espera que apague; pasado `stop_grace`, lo mata.
    pub fn stop(&self) {
        drop(self.stdin.lock().expect("entrada de la API").take());
        let Some(mut child) = self.child.lock().expect("proceso de la API").take() else {
            return;
        };
        let deadline = Instant::now() + self.stop_grace;
        loop {
            match child.try_wait() {
                Ok(Some(_)) => return,
                Ok(None) if Instant::now() < deadline => thread::sleep(STOP_POLL),
                _ => {
                    let _ = child.kill();
                    let _ = child.wait();
                    return;
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn shell(script: &str) -> SidecarSpec {
        SidecarSpec {
            prefix: "PRUEBA".to_string(),
            root: std::env::temp_dir(),
            program: PathBuf::from("/bin/sh"),
            args: vec!["-c".into(), script.into()],
            log_hint: "logs/api.log".to_string(),
            stop_grace: Duration::from_millis(500),
        }
    }

    fn wait_port(api: &PythonApi, limit: Duration) -> Option<u16> {
        let deadline = Instant::now() + limit;
        while api.session().port.is_none() && Instant::now() < deadline {
            thread::sleep(Duration::from_millis(20));
        }
        api.session().port
    }

    fn gone(pid: u32) -> bool {
        !Path::new(&format!("/proc/{pid}")).exists()
    }

    #[test]
    fn names_match_the_python_side() {
        let spec = SidecarSpec::python("IVYBELLS", Path::new("/x"), &["main.py", "--api"], "");
        assert_eq!(spec.token_env(), "IVYBELLS_API_TOKEN");
        assert_eq!(spec.port_prefix(), "IVYBELLS_API_PORT=");
        assert_eq!(spec.watch_stdin_env(), "IVYBELLS_API_WATCH_STDIN");
        assert_eq!(spec.program, PathBuf::from("/x/.venv/bin/python"));
    }

    #[test]
    fn port_line_is_parsed_and_anything_else_ignored() {
        let prefix = "IVYBELLS_API_PORT=";
        assert_eq!(parse_port("IVYBELLS_API_PORT=43210\n", prefix), Some(43210));
        assert_eq!(parse_port("IVYBELLS_API_PORT=nada", prefix), None);
        assert_eq!(parse_port("VENONA_API_PORT=43210", prefix), None);
        assert_eq!(parse_port("otra cosa", prefix), None);
    }

    #[test]
    fn tokens_are_long_and_different() {
        let (one, two) = (new_token().unwrap(), new_token().unwrap());
        assert_eq!(one.len(), TOKEN_BYTES * 2);
        assert_ne!(one, two);
    }

    #[test]
    fn port_is_kept_and_a_silent_exit_is_an_error() {
        let prefix = "PRUEBA_API_PORT=";
        let session = Mutex::new(ApiSession::default());
        read_port(
            Cursor::new("arranque\nPRUEBA_API_PORT=5000\n"),
            prefix,
            "x",
            &session,
        );
        assert_eq!(session.lock().unwrap().port, Some(5000));
        assert_eq!(session.lock().unwrap().error, None);

        let silent = Mutex::new(ApiSession::default());
        read_port(Cursor::new("Traceback\n"), prefix, "logs/api.log", &silent);
        assert!(silent
            .lock()
            .unwrap()
            .error
            .as_ref()
            .unwrap()
            .contains("logs/api.log"));
    }

    #[test]
    fn root_comes_from_the_env_or_two_folders_up() {
        let root = project_root("JACCK_TAURI_SIN_VARIABLE", "/tmp/app/desktop/src-tauri");
        assert_eq!(root, PathBuf::from("/tmp/app/desktop/src-tauri/../.."));
    }

    #[test]
    fn missing_program_is_reported_not_a_crash() {
        let api = PythonApi::start(&SidecarSpec::python(
            "PRUEBA",
            Path::new("/no/existe"),
            &[],
            "",
        ));
        assert!(api.session().error.unwrap().contains("No se pudo lanzar"));
        assert_eq!(api.pid(), None);
        api.stop();
    }

    /// El hijo recibe el token y la vigilancia de la entrada, y apaga al cerrarla.
    #[test]
    fn closing_stdin_stops_the_child_before_the_grace() {
        let api = PythonApi::start(&shell(
            "if [ \"$PRUEBA_API_WATCH_STDIN\" = 1 ] && [ ${#PRUEBA_API_TOKEN} -eq 64 ]; \
             then echo PRUEBA_API_PORT=4321; else echo PRUEBA_API_PORT=1; fi; cat > /dev/null",
        ));
        let pid = api.pid().expect("el hijo arranco");
        assert_eq!(wait_port(&api, Duration::from_secs(5)), Some(4321));
        let started = Instant::now();
        api.stop();
        assert!(gone(pid));
        assert!(started.elapsed() < Duration::from_millis(500));
    }

    #[test]
    fn a_child_that_ignores_stdin_is_killed_after_the_grace() {
        let api = PythonApi::start(&shell("echo PRUEBA_API_PORT=1; exec sleep 60"));
        let pid = api.pid().expect("el hijo arranco");
        wait_port(&api, Duration::from_secs(5));
        api.stop();
        assert!(gone(pid));
    }

    /// La API real de `jacck_common.webapi` (Python) con estos nombres: anuncia su puerto
    /// y, al cerrarse la entrada, apaga sola sin llegar al kill. Necesita el `.venv` de
    /// jacck_common (`pip install -e ".[webapi,dev]"`).
    #[test]
    fn python_webapi_answers_and_stops_on_stdin_close() {
        let common = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let python = python_path(&common);
        assert!(python.exists(), "falta {}", python.display());
        let session = std::env::temp_dir().join(format!("jacck_tauri_{}.json", std::process::id()));
        let code = format!(
            "import os, sys; from pathlib import Path; \
             from jacck_common.webapi.names import SidecarNames; \
             from jacck_common.webapi.serve import serve, session_token; \
             from jacck_common.webapi.server import create_base_api; \
             names = SidecarNames('PRUEBA'); token = session_token(names); \
             assert token == os.environ['PRUEBA_API_TOKEN']; \
             sys.exit(serve(create_base_api(title='Prueba', token=token), names=names, \
             token=token, session_path=Path({:?})))",
            session.display().to_string()
        );
        let mut spec = SidecarSpec::python("PRUEBA", &common, &["-c", &code], "stderr");
        spec.stop_grace = STOP_GRACE;
        let api = PythonApi::start(&spec);
        let pid = api.pid().expect("el Python arranco");
        let port = wait_port(&api, Duration::from_secs(30));
        assert!(port.is_some(), "{:?}", api.session().error);
        assert!(session.exists());
        let started = Instant::now();
        api.stop();
        assert!(gone(pid));
        assert!(
            started.elapsed() < STOP_GRACE,
            "apago por el kill, no por la entrada"
        );
        assert!(!session.exists());
    }
}
