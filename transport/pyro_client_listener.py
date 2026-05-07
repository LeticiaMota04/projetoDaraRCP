"""
Objeto de callback Pyro5 no cliente: o servidor invoca ``receive_event``; o método só enfileira
para a thread principal (ex.: loop do Pygame) processar.
"""

from __future__ import annotations

from queue import Queue

import Pyro5.api


@Pyro5.api.expose
class PyroGameClientListener:
    def __init__(self, incoming: Queue) -> None:
        self._incoming = incoming

    @Pyro5.api.oneway
    def receive_event(self, kind: str, data: dict) -> None:
        self._incoming.put({"type": kind, "data": data})
