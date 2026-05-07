"""
Sessão Pyro5 no cliente: ``Proxy`` do serviço de jogo + ``Daemon`` do listener.

A UI deve usar esta camada em vez de montar URIs Pyro ou daemons diretamente.
"""

from __future__ import annotations

import socket
import threading
from queue import Queue
from typing import cast

import Pyro5.api

from shared.pyro_config import PYRO_GAME_OBJECT_ID, PYRO_GAME_PORT
from transport.game_service_contract import JoinGameResult, RemoteGameService
from transport.pyro_client_listener import PyroGameClientListener


def guess_ipv4_for_pyro_callback() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("198.51.100.1", 1))
        ip = probe.getsockname()[0]
        if not ip.startswith("127."):
            return ip
    except OSError:
        pass
    finally:
        probe.close()
    return "127.0.0.1"


def pyro_game_connect_host(server_host: str) -> str:
    """Evita ``localhost`` → ``::1`` (IPv6) quando o daemon só escuta IPv4 (``0.0.0.0``)."""
    if server_host == "localhost":
        return "127.0.0.1"
    return server_host


def callback_bind_host(server_host: str, override: str | None) -> str:
    if override:
        return override
    if server_host in ("localhost", "127.0.0.1", "::1"):
        return "127.0.0.1"
    return guess_ipv4_for_pyro_callback()


class PyroClientSession:
    """
    Mantém o proxy do ``PyroDaraGameService`` e o daemon do ``PyroGameClientListener``.
    """

    def __init__(self, incoming: Queue) -> None:
        self._incoming = incoming
        self._game_port = PYRO_GAME_PORT
        self._game_service: Pyro5.api.Proxy | None = None
        self._listener_daemon: Pyro5.api.Daemon | None = None
        self._listener_thread: threading.Thread | None = None
        self._pyro_listener: PyroGameClientListener | None = None
        self.connection_error: str | None = None
        self.pending_player_slot: int | None = None

    @property
    def game_service(self) -> RemoteGameService | None:
        if self._game_service is None:
            return None
        return cast(RemoteGameService, self._game_service)

    def connect(
        self,
        server_host: str,
        callback_advertise_host: str | None = None,
        game_port: int | None = None,
    ) -> bool:
        self.connection_error = None
        self.pending_player_slot = None
        if game_port is not None:
            self._game_port = game_port

        bind_host = callback_bind_host(server_host, callback_advertise_host)
        self._pyro_listener = PyroGameClientListener(self._incoming)
        try:
            self._listener_daemon = Pyro5.api.Daemon(host=bind_host, port=0)
        except Exception as exc:
            self.connection_error = str(exc)
            return False

        self._listener_daemon.register(self._pyro_listener, "dara.listener")
        self._listener_thread = threading.Thread(
            target=self._listener_daemon.requestLoop,
            name="PyroClientListener",
            daemon=True,
        )
        self._listener_thread.start()

        game_host = pyro_game_connect_host(server_host)
        uri = f"PYRO:{PYRO_GAME_OBJECT_ID}@{game_host}:{self._game_port}"
        try:
            self._game_service = Pyro5.api.Proxy(uri)
            result: JoinGameResult = self._game_service.join_game(self._pyro_listener)
        except Exception as exc:
            self._shutdown_listener_daemon()
            self._game_service = None
            self.connection_error = str(exc)
            return False

        if not result.get("ok"):
            self._shutdown_listener_daemon()
            try:
                self._game_service._pyroRelease()
            except Exception:
                pass
            self._game_service = None
            self.connection_error = str(result.get("message", "Não foi possível entrar na sala"))
            return False

        self.pending_player_slot = int(result["player"])
        return True

    def _shutdown_listener_daemon(self) -> None:
        if self._listener_daemon is not None:
            try:
                self._listener_daemon.shutdown()
            except Exception:
                pass
            self._listener_daemon = None
        self._listener_thread = None
        self._pyro_listener = None

    def disconnect(self, player_id: int | None) -> None:
        if self._game_service is not None and player_id is not None:
            try:
                self._game_service.leave_game(player_id)
            except Exception:
                pass
            try:
                self._game_service._pyroRelease()
            except Exception:
                pass
            self._game_service = None
        self.pending_player_slot = None
        self._shutdown_listener_daemon()
