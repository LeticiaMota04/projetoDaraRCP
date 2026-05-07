"""
Validação da pilha Pyro5 (fases 2–4): join, sala cheia, jogada, chat, desistência, reinício.

Executar na pasta ``dara``: ``python -m unittest tests.test_pyro_integration -v``
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from queue import Empty, Queue

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "server") not in sys.path:
    sys.path.insert(0, str(ROOT / "server"))

from shared.message_contract import ServerToClient
from transport.pyro_client_session import PyroClientSession


def _free_tcp_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    _, port = s.getsockname()
    s.close()
    return int(port)


def _drain_queue(q: Queue, max_items: int = 50) -> list[dict]:
    out: list[dict] = []
    for _ in range(max_items):
        try:
            out.append(q.get_nowait())
        except Empty:
            break
    return out


def _wait_for_event(q: Queue, event_type: str, timeout: float = 3.0) -> dict | None:
    deadline = time.monotonic() + timeout
    pending: list[dict] = []
    while time.monotonic() < deadline:
        try:
            m = q.get(timeout=0.1)
            if m.get("type") == event_type:
                for extra in pending:
                    q.put_nowait(extra)
                return m
            pending.append(m)
        except Empty:
            continue
    for extra in pending:
        q.put_nowait(extra)
    return None


class PyroIntegrationTestCase(unittest.TestCase):
    """
    Servidor em subprocesso: Pyro5 com callbacks entre processos distintos evita
    ambiguidade com vários daemons no mesmo interpretador.
    """

    def setUp(self) -> None:
        self.port = _free_tcp_port()
        env = {**os.environ, "DARA_PYRO_TEST_PORT": str(self.port)}
        self._server_proc = subprocess.Popen(
            [sys.executable, str(ROOT / "server" / "server.py")],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            try:
                probe = socket.create_connection(("127.0.0.1", self.port), timeout=0.15)
                probe.close()
                return
            except OSError:
                if self._server_proc.poll() is not None:
                    self.fail("servidor Pyro terminou antes de aceitar conexões na porta")
                time.sleep(0.05)
        self._server_proc.terminate()
        self.fail("timeout aguardando porta Pyro")

    def tearDown(self) -> None:
        if hasattr(self, "_server_proc") and self._server_proc.poll() is None:
            self._server_proc.terminate()
            try:
                self._server_proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._server_proc.kill()


class TestPyroJoinAndFullRoom(PyroIntegrationTestCase):
    def test_two_players_then_full_room(self) -> None:
        q1: Queue = Queue()
        q2: Queue = Queue()
        q3: Queue = Queue()
        s1 = PyroClientSession(q1)
        s2 = PyroClientSession(q2)
        s3 = PyroClientSession(q3)
        try:
            self.assertTrue(
                s1.connect("127.0.0.1", "127.0.0.1", game_port=self.port),
                s1.connection_error,
            )
            self.assertTrue(
                s2.connect("127.0.0.1", "127.0.0.1", game_port=self.port),
                s2.connection_error,
            )
            time.sleep(0.25)
            self.assertIsNotNone(_wait_for_event(q1, ServerToClient.START_GAME))
            self.assertIsNotNone(_wait_for_event(q2, ServerToClient.START_GAME))

            self.assertFalse(s3.connect("127.0.0.1", "127.0.0.1", game_port=self.port))
            self.assertIsNotNone(s3.connection_error)
            self.assertIn("cheia", s3.connection_error.lower())
        finally:
            s1.disconnect(1)
            s2.disconnect(2)
            s3.disconnect(None)


class TestPyroGameplay(PyroIntegrationTestCase):
    def test_place_chat_resign_restart(self) -> None:
        q1: Queue = Queue()
        q2: Queue = Queue()
        s1 = PyroClientSession(q1)
        s2 = PyroClientSession(q2)
        try:
            self.assertTrue(s1.connect("127.0.0.1", "127.0.0.1", game_port=self.port))
            self.assertTrue(s2.connect("127.0.0.1", "127.0.0.1", game_port=self.port))
            time.sleep(0.25)
            _drain_queue(q1)
            _drain_queue(q2)

            gs1 = s1.game_service
            gs2 = s2.game_service
            assert gs1 is not None and gs2 is not None

            gs1.place_piece(1, 0, 0)
            time.sleep(0.2)
            ev2 = _wait_for_event(q2, ServerToClient.UPDATE_BOARD, timeout=2.0)
            self.assertIsNotNone(ev2)
            board = ev2["data"]["board"]
            self.assertEqual(board[0][0], 1)

            gs1.chat(1, "ola")
            time.sleep(0.15)
            ch2 = _wait_for_event(q2, ServerToClient.CHAT, timeout=2.0)
            self.assertIsNotNone(ch2)
            self.assertEqual(ch2["data"]["message"], "ola")

            gs1.resign(1)
            time.sleep(0.2)
            go1 = _wait_for_event(q1, ServerToClient.GAME_OVER, timeout=2.0)
            go2 = _wait_for_event(q2, ServerToClient.GAME_OVER, timeout=2.0)
            self.assertIsNotNone(go1)
            self.assertIsNotNone(go2)
            self.assertEqual(go1["data"]["winner"], 2)

            _drain_queue(q1)
            _drain_queue(q2)
            gs1.restart_game(1)
            gs2.restart_game(2)
            time.sleep(0.25)
            self.assertIsNotNone(_wait_for_event(q1, ServerToClient.MATCH_RESET, timeout=2.0))
            self.assertIsNotNone(_wait_for_event(q2, ServerToClient.MATCH_RESET, timeout=2.0))
        finally:
            s1.disconnect(1)
            s2.disconnect(2)


if __name__ == "__main__":
    unittest.main()
