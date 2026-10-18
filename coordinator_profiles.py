"""
Coordinador de los perfiles del agente: cuál está en uso y cómo se editan.

El perfil activo se recuerda en `app_settings.json`; si su archivo ya no está, se usa el
de ejemplo (o ninguno: entonces el system prompt son solo las reglas fijas). Los avisos
para la ventana salen por `notice`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from core.agent_profile import (
    EXAMPLE_NAME,
    ProfileError,
    build_system_prompt,
    is_editable,
    unique_name,
)
from services.service_profiles import ProfileStore

logger = logging.getLogger(__name__)

NEW_NAME = "nuevo perfil"


class AgentProfiles(QObject):
    """
    Signals
    -------
    profiles_changed() -> cambió la lista de perfiles.
    active_changed(str) -> el nombre del perfil en uso ("" si no hay ninguno).
    notice(dict)        -> `text` y `level` ("ok" o "error") para la ventana.
    """

    profiles_changed = Signal()
    active_changed = Signal(str)
    notice = Signal(dict)

    def __init__(
        self,
        store: ProfileStore | None = None,
        active: str = EXAMPLE_NAME,
        save_active: Callable[[str], object] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.store = store or ProfileStore()
        self._active = active
        self._save_active = save_active

    # -- Lectura -----------------------------------------------

    def names(self) -> list[str]:
        return self.store.names()

    @property
    def active(self) -> str:
        """El perfil en uso; si el recordado ya no existe, el de ejemplo o el primero."""
        names = self.names()
        if self._active in names:
            return self._active
        if EXAMPLE_NAME in names:
            return EXAMPLE_NAME
        return names[0] if names else ""

    def text(self, name: str) -> str:
        return self.store.read(name) if name else ""

    def is_editable(self, name: str) -> bool:
        return bool(name) and is_editable(name)

    def system_prompt(self, context: str = "") -> str:
        return build_system_prompt(self.text(self.active), context)

    # -- Pedidos de la vista -----------------------------------

    def set_active(self, name: str) -> None:
        if name not in self.names() or name == self._active:
            return
        self._active = name
        if self._save_active is not None:
            self._save_active(name)
        logger.info("Perfil en uso: %s", name)
        self.active_changed.emit(name)

    def save(self, name: str, text: str) -> bool:
        ok, _ = self._run(lambda: self.store.save(name, text))
        if not ok:
            return False
        self._notify(f"Perfil {name} guardado", "ok")
        return True

    def create(self) -> str:
        """Crea un perfil vacío; devuelve su nombre o "" si falló."""
        name = unique_name(NEW_NAME, self.names())
        return self._added(lambda: self.store.create(name))

    def duplicate(self, name: str) -> str:
        copy = unique_name(f"{name} copia", self.names())
        return self._added(lambda: self.store.create(copy, self.text(name)))

    def rename(self, old: str, new: str) -> str:
        """Devuelve el nombre nuevo o "" si falló; el perfil en uso sigue en uso."""
        was_active = old == self.active
        ok, renamed = self._run(lambda: self.store.rename(old, new))
        if not ok:
            return ""
        self.profiles_changed.emit()
        if was_active:
            self.set_active(renamed)
        return renamed

    def delete(self, name: str) -> bool:
        was_active = name == self.active
        ok, _ = self._run(lambda: self.store.delete(name))
        if not ok:
            return False
        self.profiles_changed.emit()
        self._notify(f"Perfil {name} borrado", "ok")
        if was_active:
            fallback = self.active
            if fallback:
                self.set_active(fallback)
            else:
                self.active_changed.emit("")
        return True

    # -- Internos ----------------------------------------------

    def _added(self, action: Callable[[], str]) -> str:
        ok, name = self._run(action)
        if not ok:
            return ""
        self.profiles_changed.emit()
        return name

    def _run(self, action: Callable[[], object]) -> tuple[bool, object]:
        """Corre el pedido; si falla, lo avisa y devuelve (False, None)."""
        try:
            return True, action()
        except ProfileError as exc:
            self._notify(str(exc), "error")
            return False, None

    def _notify(self, text: str, level: str) -> None:
        self.notice.emit({"text": text, "level": level})
