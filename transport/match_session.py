"""
Despacho de mensagens de jogador sobre ``DaraGame`` (regras em ``server.game_logic``).

Usado pelo ``PyroDaraGameService`` (e qualquer outro adaptador de sessão) para centralizar
notificações após jogadas e chat.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import sys

_server_dir = Path(__file__).resolve().parent.parent / "server"
if str(_server_dir) not in sys.path:
    sys.path.insert(0, str(_server_dir))

from game_logic import DaraGame, PLAYER1, PLAYER2
from shared.message_contract import ClientToServer, ServerToClient


def game_state_data(game: DaraGame) -> dict:
    return {
        "turn": game.current_turn,
        "phase": game.phase,
        "must_capture": game.must_capture,
        "captures": [game.captures[PLAYER1], game.captures[PLAYER2]],
    }


def dispatch_player_message(
    game: DaraGame,
    player_id: int,
    msg_type: str,
    data: dict,
    notify_all: Callable[[str, dict], None],
) -> None:
    """
    Replica o comportamento de ``server.handle_message``: notificações via ``notify_all(kind, data)``.
    """

    if game.game_over_winner is not None:
        if msg_type == ClientToServer.RESTART_GAME:
            game.reset()
            notify_all(ServerToClient.UPDATE_BOARD, {"board": game.get_board()})
            notify_all(ServerToClient.GAME_STATE, game_state_data(game))
            notify_all(ServerToClient.MATCH_RESET, {})
            return
        if msg_type == ClientToServer.CHAT:
            notify_all(
                ServerToClient.CHAT,
                {"player": player_id, "message": data["message"]},
            )
            return
        return

    if msg_type == ClientToServer.RESTART_GAME:
        return

    if msg_type == ClientToServer.PLACE_PIECE:
        success = game.place_piece(data["row"], data["col"], player_id)
        if success:
            notify_all(ServerToClient.UPDATE_BOARD, {"board": game.get_board()})
            notify_all(ServerToClient.GAME_STATE, game_state_data(game))
        return

    if msg_type == ClientToServer.MOVE_PIECE:
        success = game.move_piece(
            data["from"][0],
            data["from"][1],
            data["to"][0],
            data["to"][1],
            player_id,
        )
        if success:
            notify_all(ServerToClient.UPDATE_BOARD, {"board": game.get_board()})
            notify_all(ServerToClient.GAME_STATE, game_state_data(game))
        return

    if msg_type == ClientToServer.CAPTURE_PIECE:
        success = game.capture_piece(data["row"], data["col"], player_id)
        if success:
            notify_all(ServerToClient.UPDATE_BOARD, {"board": game.get_board()})
            winner = game.check_game_over()
            if winner:
                game.game_over_winner = winner
                notify_all(ServerToClient.GAME_OVER, {"winner": winner})
            else:
                notify_all(ServerToClient.GAME_STATE, game_state_data(game))
        return

    if msg_type == ClientToServer.CHAT:
        notify_all(
            ServerToClient.CHAT,
            {"player": player_id, "message": data["message"]},
        )
        return

    if msg_type == ClientToServer.RESIGN:
        winner = PLAYER2 if player_id == PLAYER1 else PLAYER1
        game.game_over_winner = winner
        notify_all(ServerToClient.GAME_OVER, {"winner": winner})
