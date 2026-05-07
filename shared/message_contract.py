"""
Contrato de domínio da partida: nomes de ações e de eventos, e forma dos payloads.

Usado pelo despacho em ``transport/match_session``, pelos callbacks Pyro e pela UI
(``type`` / ``data`` na fila do cliente). Não implica transporte JSON em socket.

Cliente → servidor
  place_piece: row, col (int)
  move_piece: "from" [r,c], "to" [r,c] (listas de dois inteiros)
  capture_piece: row, col
  chat: message (str)
  resign: sem campos
  restart_game: sem campos

Servidor → cliente
  start_game: player (1 ou 2)
  game_state: turn, phase, must_capture, captures (lista de dois inteiros)
  update_board: board (matriz 5x6, células 0/1/2)
  chat: player (int), message (str)
  game_over: winner (1 ou 2)
  match_reset: sem campos
  error: message (str; ex.: sala cheia)
"""

from __future__ import annotations

from typing import TypedDict


class ClientToServer:
    PLACE_PIECE = "place_piece"
    MOVE_PIECE = "move_piece"
    CAPTURE_PIECE = "capture_piece"
    CHAT = "chat"
    RESIGN = "resign"
    RESTART_GAME = "restart_game"


class ServerToClient:
    START_GAME = "start_game"
    GAME_STATE = "game_state"
    UPDATE_BOARD = "update_board"
    CHAT = "chat"
    GAME_OVER = "game_over"
    MATCH_RESET = "match_reset"
    ERROR = "error"


class PlacePieceData(TypedDict):
    row: int
    col: int


class CapturePieceData(TypedDict):
    row: int
    col: int


class ChatFromClientData(TypedDict):
    message: str


class StartGameData(TypedDict):
    player: int


class GameStateData(TypedDict):
    turn: int
    phase: str
    must_capture: bool
    captures: list[int]


class UpdateBoardData(TypedDict):
    board: list[list[int]]


class ChatFromServerData(TypedDict):
    player: int
    message: str


class GameOverData(TypedDict):
    winner: int


class ErrorData(TypedDict):
    message: str
