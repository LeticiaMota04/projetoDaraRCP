"""
Serviço de partida exposto via Pyro5: métodos remotos + callbacks para os listeners.

Publicado pelo ``Daemon`` em ``server/server.py``. Dois lugares fixos (slots); falha ao
notificar um listener trata desconexão e reinicia a sala para novos jogadores.
"""

from __future__ import annotations

import threading
from pathlib import Path
import sys
from typing import Any

_root = Path(__file__).resolve().parent.parent
_server_dir = _root / "server"
for _p in (_root, _server_dir):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

import Pyro5.server

from game_logic import DaraGame
from shared.message_contract import ClientToServer, ServerToClient
from .game_service_contract import JoinGameResult
from .match_session import dispatch_player_message, game_state_data

_PEER_DISCONNECT_MESSAGE = (
    "Oponente desconectou ou conexão perdida. Reconecte e entre de novo na sala."
)


def _invoke_listener(listener: Any, kind: str, data: dict) -> None:
    """
    O ``Daemon`` Pyro pode despachar ``join_game`` em threads distintas; o proxy do
    listener pertence à thread que recebeu o objeto. Reivindicar ownership antes do
    callback evita ``PyroError`` ao notificar a partir de outra thread.
    """
    claim = getattr(listener, "_pyroClaimOwnership", None)
    if callable(claim):
        claim()
    listener.receive_event(kind, data)


@Pyro5.server.expose
class PyroDaraGameService:
    """
    Instância única da sala: dois slots (jogador 1 e 2). ``join_game`` preenche o próximo vazio.
    """

    def __init__(self) -> None:
        self._game = DaraGame()
        self._session_lock = threading.Lock()
        self._slots: list[Any | None] = [None, None]

    def _disconnect_slot(self, dead_index: int) -> None:
        if dead_index not in (0, 1):
            return
        if self._slots[dead_index] is None:
            return
        peer_index = 1 - dead_index
        peer = self._slots[peer_index]
        self._slots[dead_index] = None
        self._game.reset()
        if peer is not None:
            self._slots[peer_index] = None
            try:
                _invoke_listener(
                    peer,
                    ServerToClient.ERROR,
                    {"message": _PEER_DISCONNECT_MESSAGE},
                )
            except Exception:
                pass

    def _notify_all(self, kind: str, data: dict) -> None:
        failed: list[int] = []
        for i in range(2):
            listener = self._slots[i]
            if listener is None:
                continue
            try:
                _invoke_listener(listener, kind, data)
            except Exception:
                failed.append(i)
        for i in failed:
            self._disconnect_slot(i)

    def _notify_start_and_state(self) -> None:
        if self._slots[0] is None or self._slots[1] is None:
            return
        self._game.reset()
        for index in range(2):
            listener = self._slots[index]
            if listener is None:
                return
            try:
                _invoke_listener(
                    listener,
                    ServerToClient.START_GAME,
                    {"player": index + 1},
                )
            except Exception:
                self._disconnect_slot(index)
                return
        for index in range(2):
            listener = self._slots[index]
            if listener is None:
                return
            try:
                _invoke_listener(
                    listener,
                    ServerToClient.GAME_STATE,
                    game_state_data(self._game),
                )
            except Exception:
                self._disconnect_slot(index)
                return

    def join_game(self, listener: Any) -> JoinGameResult:
        with self._session_lock:
            if self._slots[0] is None:
                slot_index = 0
            elif self._slots[1] is None:
                slot_index = 1
            else:
                return {"ok": False, "message": "Sala cheia"}
            self._slots[slot_index] = listener
            player_id = slot_index + 1
            if self._slots[0] is not None and self._slots[1] is not None:
                print("Iniciando partida (Pyro)!")
                self._notify_start_and_state()
            else:
                print(f"Jogador {player_id} aguardando oponente (Pyro).")
            return {"ok": True, "player": player_id}

    def leave_game(self, player_id: int) -> None:
        with self._session_lock:
            if player_id not in (1, 2):
                return
            self._disconnect_slot(player_id - 1)

    def place_piece(self, player_id: int, row: int, col: int) -> None:
        with self._session_lock:
            dispatch_player_message(
                self._game,
                player_id,
                ClientToServer.PLACE_PIECE,
                {"row": row, "col": col},
                self._notify_all,
            )

    def move_piece(
        self,
        player_id: int,
        from_row: int,
        from_col: int,
        to_row: int,
        to_col: int,
    ) -> None:
        with self._session_lock:
            dispatch_player_message(
                self._game,
                player_id,
                ClientToServer.MOVE_PIECE,
                {"from": [from_row, from_col], "to": [to_row, to_col]},
                self._notify_all,
            )

    def capture_piece(self, player_id: int, row: int, col: int) -> None:
        with self._session_lock:
            dispatch_player_message(
                self._game,
                player_id,
                ClientToServer.CAPTURE_PIECE,
                {"row": row, "col": col},
                self._notify_all,
            )

    def chat(self, player_id: int, message: str) -> None:
        with self._session_lock:
            dispatch_player_message(
                self._game,
                player_id,
                ClientToServer.CHAT,
                {"message": message},
                self._notify_all,
            )

    def resign(self, player_id: int) -> None:
        with self._session_lock:
            dispatch_player_message(
                self._game,
                player_id,
                ClientToServer.RESIGN,
                {},
                self._notify_all,
            )

    def restart_game(self, player_id: int) -> None:
        with self._session_lock:
            dispatch_player_message(
                self._game,
                player_id,
                ClientToServer.RESTART_GAME,
                {},
                self._notify_all,
            )
