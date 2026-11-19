"""
Adaptador Qt de los perfiles del agente (`app.profiles.ProfileLibrary`).

La vista solo habla con él; los pedidos pasan tal cual al caso de uso y sus avisos salen
como señales.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from app.profiles import ProfileLibrary, ProfileListeners
from domain.agent.agent_profile import EXAMPLE_NAME


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
        store: object | None = None,
        active: str = EXAMPLE_NAME,
        save_active: Callable[[str], object] | None = None,
        parent: QObject | None = None,
        *,
        library: ProfileLibrary | None = None,
    ) -> None:
        super().__init__(parent)
        if library is None:
            library = ProfileLibrary(store, active, save_active)  # type: ignore[arg-type]
        self.library = library
        library.listeners = ProfileListeners(
            changed=self.profiles_changed.emit,
            active=self.active_changed.emit,
            notice=self.notice.emit,
        )

    # -- Lectura -----------------------------------------------

    @property
    def store(self):
        return self.library.store

    def names(self) -> list[str]:
        return self.library.names()

    @property
    def active(self) -> str:
        return self.library.active

    def text(self, name: str) -> str:
        return self.library.text(name)

    def is_editable(self, name: str) -> bool:
        return self.library.is_editable(name)

    def system_prompt(self, context: str = "") -> str:
        return self.library.system_prompt(context)

    # -- Pedidos de la vista -----------------------------------

    def set_active(self, name: str) -> None:
        self.library.set_active(name)

    def save(self, name: str, text: str) -> bool:
        return self.library.save(name, text)

    def create(self) -> str:
        return self.library.create()

    def duplicate(self, name: str) -> str:
        return self.library.duplicate(name)

    def rename(self, old: str, new: str) -> str:
        return self.library.rename(old, new)

    def delete(self, name: str) -> bool:
        return self.library.delete(name)
