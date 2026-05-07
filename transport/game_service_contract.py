"""
Contrato lógico da sessão remota (Fase 2): assinaturas estáveis sem Pyro na interface pública.

A implementação concreta com Pyro5 fica em ``pyro_dara_game_service`` (servidor) e
``pyro_client_session`` (cliente: proxy + listener). Para trocar o protocolo de rede,
substitua principalmente esses módulos e mantenha este contrato alinhado à UI e à lógica de jogo.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict


class JoinGameAccepted(TypedDict):
    ok: bool
    player: int


class JoinGameRejected(TypedDict):
    ok: bool
    message: str


JoinGameResult = JoinGameAccepted | JoinGameRejected


class GameClientListener(Protocol):
    """
    Objeto no cliente chamado pelo servidor (callback Pyro).

    Na implementação Pyro do cliente, marque ``receive_event`` com ``@Pyro5.server.oneway``
    quando possível, para o servidor não bloquear à espera do retorno (evita deadlock
    em cenários de callback encadeado).
    """

    def receive_event(self, kind: str, data: dict) -> None:
        """``kind`` usa os valores em ``shared.message_contract.ServerToClient``; ``data`` é o payload."""


class RemoteGameService(Protocol):
    """
    Serviço no host da partida: ações com ``player_id`` vindo de ``join_game``.
    ``join_game`` registra o proxy do listener; sala cheia devolve ``ok: False`` e ``message``.
    """

    def join_game(self, listener: Any) -> JoinGameResult: ...

    def place_piece(self, player_id: int, row: int, col: int) -> None: ...

    def move_piece(self, player_id: int, from_row: int, from_col: int, to_row: int, to_col: int) -> None: ...

    def capture_piece(self, player_id: int, row: int, col: int) -> None: ...

    def chat(self, player_id: int, message: str) -> None: ...

    def resign(self, player_id: int) -> None: ...

    def restart_game(self, player_id: int) -> None: ...

    def leave_game(self, player_id: int) -> None: ...
