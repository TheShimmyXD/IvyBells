//! Colocacion de la ventana al abrir (de Venona).

use tauri::{PhysicalPosition, PhysicalSize, Runtime, WebviewWindow};

/// Tamano y posicion que dejan la ventana centrada y ocupando `fraction` del area libre.
pub fn centered(
    area: (i32, i32, u32, u32),
    fraction: (f64, f64),
) -> (PhysicalPosition<i32>, PhysicalSize<u32>) {
    let (x0, y0, width_area, height_area) = area;
    let width = (f64::from(width_area) * fraction.0) as u32;
    let height = (f64::from(height_area) * fraction.1) as u32;
    let x = x0 + ((width_area - width) / 2) as i32;
    let y = y0 + ((height_area - height) / 2) as i32;
    (
        PhysicalPosition::new(x, y),
        PhysicalSize::new(width, height),
    )
}

/// Tamano inicial centrado en el area libre del monitor; luego se muestra (la ventana
/// arranca con `visible: false` para no verse saltar).
pub fn place_window<R: Runtime>(
    window: &WebviewWindow<R>,
    fraction: (f64, f64),
) -> tauri::Result<()> {
    if let Some(monitor) = window.current_monitor()? {
        let work = monitor.work_area();
        let area = (
            work.position.x,
            work.position.y,
            work.size.width,
            work.size.height,
        );
        let (position, size) = centered(area, fraction);
        window.set_size(size)?;
        window.set_position(position)?;
    }
    window.show()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn window_is_centered_in_the_work_area() {
        // Monitor de 1920x1080 con la barra arriba (27 px) y un segundo monitor a la izquierda.
        let (position, size) = centered((1920, 27, 1920, 1053), (0.75, 0.75));
        assert_eq!((size.width, size.height), (1440, 789));
        assert_eq!((position.x, position.y), (1920 + 240, 27 + 132));
    }
}
