import sys
from pathlib import Path
from queue import Empty, Queue

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pygame

from shared.message_contract import ServerToClient
from transport.pyro_client_session import PyroClientSession

HOST = "127.0.0.1"
ROWS = 5
COLS = 6

COLOR_PLAYER1 = (90, 140, 220)
COLOR_PLAYER2 = (220, 100, 100)

CELL_SIZE = 72
BOARD_X = 32
Y_TITLE = 10
Y_PHASE = 36
Y_PLAYER_LABEL = 76
Y_STATUS = 104
STATUS_TEXT_LINE_HEIGHT = 22
GAP_STATUS_TO_TURN_BANNER = 14
TURN_BANNER_Y = Y_STATUS + STATUS_TEXT_LINE_HEIGHT + GAP_STATUS_TO_TURN_BANNER
TURN_BANNER_H = 38
Y_HINTS = TURN_BANNER_Y + TURN_BANNER_H + 10
BOARD_GAP_BELOW_HINTS = 16
BOARD_Y = Y_HINTS + 22 + BOARD_GAP_BELOW_HINTS
CHAT_X = BOARD_X + COLS * CELL_SIZE + 24
CHAT_WIDTH = 340
CHAT_LOG_HEIGHT = 380
INPUT_HEIGHT = 36
MAX_CHAT_LINES = 80
FPS = 60


def make_font(size: int) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()
    try:
        return pygame.font.SysFont("Segoe UI", size)
    except Exception:
        return pygame.font.Font(None, size)


def dim_color(rgb: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(min(255, int(c * factor)) for c in rgb)


def parse_server_location(arg: str) -> tuple[str, int | None]:
    """Aceita ``host`` ou ``host:porta`` (IPv4). A porta padrão segue ``shared/pyro_config``."""
    if ":" not in arg:
        return arg, None
    host, port_str = arg.rsplit(":", 1)
    if port_str.isdigit():
        return host, int(port_str)
    return arg, None


class DaraPygameClient:
    def __init__(self):
        self.incoming: Queue = Queue()
        self._pyro_session = PyroClientSession(self.incoming)
        self._pending_player_slot: int | None = None

        self.player_id: int | None = None
        self.selected: tuple[int, int] | None = None
        self.phase = "placement"
        self.must_capture = False
        self.my_turn = False
        self.board = [[0] * COLS for _ in range(ROWS)]
        self.chat_lines: list[str] = []
        self.chat_buffer = ""
        self.chat_focused = False
        self.status_text = "Conectando..."
        self.running = True
        self.connection_error: str | None = None
        self.captures = [0, 0]
        self.show_end_modal = False
        self.modal_winner_id: int | None = None
        self.restart_button_rect = pygame.Rect(0, 0, 0, 0)

        self.font = make_font(18)
        self.font_small = make_font(15)
        self.font_title = make_font(22)
        self.font_phase = make_font(30)
        self.font_turn = make_font(24)
        self.font_modal_title = make_font(28)
        self.font_modal_btn = make_font(22)

    def _active_player_id(self) -> int | None:
        return self.player_id if self.player_id is not None else self._pending_player_slot

    def connect(
        self,
        server_host: str | None = None,
        callback_advertise_host: str | None = None,
        game_port: int | None = None,
    ) -> bool:
        host = server_host if server_host is not None else HOST
        if not self._pyro_session.connect(host, callback_advertise_host, game_port):
            self.connection_error = self._pyro_session.connection_error
            return False

        self._pending_player_slot = self._pyro_session.pending_player_slot
        self.status_text = "Aguardando oponente..."
        return True

    def disconnect(self) -> None:
        pid = self._active_player_id()
        self._pyro_session.disconnect(pid)
        self._pending_player_slot = None

    def process_incoming(self):
        while True:
            try:
                msg = self.incoming.get_nowait()
            except Empty:
                break
            t = msg["type"]
            data = msg.get("data", {})

            if t == ServerToClient.START_GAME:
                self.player_id = data["player"]
                self._pending_player_slot = None
                self._log(f"Você é o jogador {self.player_id}")

            elif t == ServerToClient.GAME_STATE:
                self.phase = data.get("phase", self.phase)
                self.must_capture = data.get("must_capture", False)
                self.my_turn = data.get("turn") == self._active_player_id()
                cap = data.get("captures")
                if cap is not None and len(cap) >= 2:
                    self.captures = [int(cap[0]), int(cap[1])]
                self._refresh_status()

            elif t == ServerToClient.UPDATE_BOARD:
                self.board = data["board"]
                self.selected = None

            elif t == ServerToClient.CHAT:
                self._log(f"P{data['player']}: {data['message']}")

            elif t == ServerToClient.GAME_OVER:
                self.modal_winner_id = int(data["winner"])
                self.show_end_modal = True
                self.my_turn = False
                self.must_capture = False
                self.selected = None
                self._log(f"Partida encerrada — vencedor: Jogador {data['winner']}")
                self._refresh_status()

            elif t == ServerToClient.MATCH_RESET:
                self.show_end_modal = False
                self.modal_winner_id = None
                self.selected = None
                self._refresh_status()

            elif t == ServerToClient.ERROR:
                err_msg = data.get("message", str(data)) if isinstance(data, dict) else str(data)
                self._log(f"Erro: {err_msg}")

    def _log(self, text: str):
        self.chat_lines.append(text)
        if len(self.chat_lines) > MAX_CHAT_LINES:
            self.chat_lines = self.chat_lines[-MAX_CHAT_LINES:]

    def _refresh_status(self):
        if self.show_end_modal:
            self.status_text = "Partida encerrada — use o botão Recomeçar"
            return
        if self.phase == "placement":
            self.status_text = "Clique numa casa vazia para colocar uma peça"
        elif self.must_capture:
            self.status_text = "Clique numa peça do oponente para capturar"
        else:
            self.status_text = "Selecione sua peça e clique na casa adjacente vazia"

    def phase_title(self) -> str:
        if self.phase == "placement":
            return "Fase: Colocação"
        if self.must_capture:
            return "Fase: Movimento — captura obrigatória"
        return "Fase: Movimento"

    def my_piece_color(self) -> tuple[int, int, int]:
        pid = self._active_player_id()
        return COLOR_PLAYER1 if pid == 1 else COLOR_PLAYER2

    def opponent_piece_color(self) -> tuple[int, int, int]:
        pid = self._active_player_id()
        return COLOR_PLAYER2 if pid == 1 else COLOR_PLAYER1

    def _blit_colored_player_label(self, screen: pygame.Surface, x: int, y: int):
        pid = self._active_player_id()
        if pid is None:
            return
        prefix = self.font.render("Você é o ", True, (180, 190, 210))
        screen.blit(prefix, (x, y))
        x2 = x + prefix.get_width()
        if pid == 1:
            name = self.font.render("Azul", True, COLOR_PLAYER1)
        else:
            name = self.font.render("Vermelho", True, COLOR_PLAYER2)
        screen.blit(name, (x2, y))

    def draw_turn_banner(self, screen: pygame.Surface):
        pid = self._active_player_id()
        if pid is None or self.show_end_modal:
            return
        banner_w = COLS * CELL_SIZE - 4
        rect = pygame.Rect(BOARD_X, TURN_BANNER_Y, banner_w, TURN_BANNER_H)

        if self.must_capture and self.my_turn:
            bg = (120, 95, 55)
            line1 = "CAPTURA OBRIGATÓRIA"
            c1 = (255, 230, 200)
        elif self.my_turn:
            bg = self.my_piece_color()
            line1 = "SUA VEZ"
            c1 = (255, 255, 255)
        else:
            bg = dim_color(self.opponent_piece_color(), 0.72)
            line1 = "VEZ DO OPONENTE"
            c1 = (255, 255, 255)

        pygame.draw.rect(screen, bg, rect, border_radius=10)
        pygame.draw.rect(screen, dim_color(bg, 1.15), rect, 2, border_radius=10)

        t1 = self.font_turn.render(line1, True, c1)
        cx = rect.centerx
        screen.blit(t1, t1.get_rect(center=(cx, rect.centery)))

    def capture_counts_for_ui(self) -> tuple[int, int]:
        pid = self._active_player_id()
        if pid is None:
            return 0, 0
        if pid == 1:
            return self.captures[0], self.captures[1]
        return self.captures[1], self.captures[0]

    def send_chat(self):
        if not self._pyro_session.game_service or not self.chat_buffer.strip():
            return
        pid = self._active_player_id()
        if pid is None:
            return
        try:
            self._pyro_session.game_service.chat(pid, self.chat_buffer.strip())
        except Exception:
            pass
        self.chat_buffer = ""

    def resign(self):
        if not self._pyro_session.game_service or self.show_end_modal:
            return
        pid = self._active_player_id()
        if pid is None:
            return
        try:
            self._pyro_session.game_service.resign(pid)
        except Exception:
            pass

    def request_restart(self):
        if not self._pyro_session.game_service:
            return
        pid = self._active_player_id()
        if pid is None:
            return
        try:
            self._pyro_session.game_service.restart_game(pid)
        except Exception:
            pass

    def board_cell_from_mouse(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        mx, my = pos
        if mx < BOARD_X or my < BOARD_Y:
            return None
        if mx >= BOARD_X + COLS * CELL_SIZE or my >= BOARD_Y + ROWS * CELL_SIZE:
            return None
        c = (mx - BOARD_X) // CELL_SIZE
        r = (my - BOARD_Y) // CELL_SIZE
        return r, c

    def input_rect(self, screen_height: int) -> pygame.Rect:
        return pygame.Rect(CHAT_X, screen_height - INPUT_HEIGHT - 24, CHAT_WIDTH, INPUT_HEIGHT)

    def chat_log_rect(self) -> pygame.Rect:
        return pygame.Rect(CHAT_X, BOARD_Y, CHAT_WIDTH, CHAT_LOG_HEIGHT)

    def on_board_click(self, r: int, c: int):
        if self.show_end_modal:
            return
        if self._pyro_session.game_service is None:
            return
        pid = self._active_player_id()
        if pid is None:
            return
        if self.phase == "placement":
            try:
                self._pyro_session.game_service.place_piece(pid, r, c)
            except Exception:
                pass
            return
        if self.must_capture:
            try:
                self._pyro_session.game_service.capture_piece(pid, r, c)
            except Exception:
                pass
            return
        if self.selected is None:
            if self.board[r][c] == pid:
                self.selected = (r, c)
            return
        fr, fc = self.selected
        try:
            self._pyro_session.game_service.move_piece(pid, fr, fc, r, c)
        except Exception:
            pass
        self.selected = None

    def winner_label_parts(self) -> tuple[str, tuple[int, int, int] | None]:
        if self.modal_winner_id is None or self.player_id is None:
            return "Fim de jogo", None
        if self.modal_winner_id == self.player_id:
            return "Você venceu!", self.my_piece_color()
        return "O oponente venceu", self.opponent_piece_color()

    def draw_end_modal(self, screen: pygame.Surface):
        if not self.show_end_modal:
            return
        sw, sh = screen.get_size()
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((15, 18, 28, 210))
        screen.blit(overlay, (0, 0))

        box_w, box_h = 440, 240
        box = pygame.Rect((sw - box_w) // 2, (sh - box_h) // 2, box_w, box_h)
        pygame.draw.rect(screen, (48, 52, 64), box, border_radius=14)
        pygame.draw.rect(screen, (100, 110, 140), box, 2, border_radius=14)

        title = self.font_modal_title.render("Partida encerrada", True, (230, 232, 240))
        screen.blit(title, title.get_rect(center=(box.centerx, box.y + 48)))

        main_text, accent = self.winner_label_parts()
        if accent:
            t_main = self.font_turn.render(main_text, True, accent)
        else:
            t_main = self.font_turn.render(main_text, True, (220, 220, 230))
        screen.blit(t_main, t_main.get_rect(center=(box.centerx, box.y + 100)))

        if self.modal_winner_id is not None:
            color_name = "Azul" if self.modal_winner_id == 1 else "Vermelho"
            ccol = COLOR_PLAYER1 if self.modal_winner_id == 1 else COLOR_PLAYER2
            sub = self.font.render("Vencedor: ", True, (170, 175, 190))
            sub_name = self.font.render(color_name, True, ccol)
            tw = sub.get_width() + sub_name.get_width()
            sx = box.centerx - tw // 2
            screen.blit(sub, (sx, box.y + 132))
            screen.blit(sub_name, (sx + sub.get_width(), box.y + 132))

        hint_modal = self.font_small.render(
            "TAB: chat  ·  ESC: sair",
            True,
            (130, 135, 150),
        )
        screen.blit(hint_modal, hint_modal.get_rect(center=(box.centerx, box.bottom - 72)))

        btn_w, btn_h = 200, 46
        self.restart_button_rect = pygame.Rect(0, 0, btn_w, btn_h)
        self.restart_button_rect.center = (box.centerx, box.bottom - 46)
        pygame.draw.rect(screen, (70, 140, 95), self.restart_button_rect, border_radius=8)
        pygame.draw.rect(screen, (120, 200, 150), self.restart_button_rect, 2, border_radius=8)
        btn_txt = self.font_modal_btn.render("Recomeçar", True, (255, 255, 255))
        screen.blit(btn_txt, btn_txt.get_rect(center=self.restart_button_rect.center))

    def draw(self, screen: pygame.Surface):
        screen.fill((40, 44, 52))
        title = self.font_title.render("Dara", True, (220, 220, 230))
        screen.blit(title, (BOARD_X, Y_TITLE))

        phase_surf = self.font_phase.render(self.phase_title(), True, (230, 232, 240))
        screen.blit(phase_surf, (BOARD_X, Y_PHASE))

        self._blit_colored_player_label(screen, BOARD_X, Y_PLAYER_LABEL)

        if not self.show_end_modal:
            st = self.font.render(self.status_text, True, (180, 190, 210))
            screen.blit(st, (BOARD_X, Y_STATUS))

        self.draw_turn_banner(screen)

        if not self.show_end_modal:
            hints = self.font_small.render(
                "TAB: chat | Enter: enviar | R: desistir | ESC: sair",
                True,
                (130, 140, 160),
            )
            screen.blit(hints, (BOARD_X, Y_HINTS))

        for r in range(ROWS):
            for c in range(COLS):
                x = BOARD_X + c * CELL_SIZE
                y = BOARD_Y + r * CELL_SIZE
                rect = pygame.Rect(x, y, CELL_SIZE - 2, CELL_SIZE - 2)
                pygame.draw.rect(screen, (70, 75, 90), rect, border_radius=4)
                pygame.draw.rect(screen, (100, 108, 128), rect, 1, border_radius=4)

                if self.selected == (r, c):
                    pygame.draw.rect(screen, (200, 180, 60), rect, 3, border_radius=4)

                val = self.board[r][c]
                cx, cy = x + CELL_SIZE // 2 - 1, y + CELL_SIZE // 2 - 1
                if val == 1:
                    pygame.draw.circle(screen, COLOR_PLAYER1, (cx, cy), CELL_SIZE // 2 - 14)
                elif val == 2:
                    pygame.draw.circle(screen, COLOR_PLAYER2, (cx, cy), CELL_SIZE // 2 - 14)

        board_bottom = BOARD_Y + ROWS * CELL_SIZE
        my_cap, op_cap = self.capture_counts_for_ui()
        cap_y = board_bottom + 14
        cap_label = self.font.render(
            f"Peças capturadas — Você: {my_cap}   |   Oponente: {op_cap}",
            True,
            (170, 175, 190),
        )
        screen.blit(cap_label, (BOARD_X, cap_y))

        log_rect = self.chat_log_rect()
        pygame.draw.rect(screen, (30, 33, 40), log_rect, border_radius=6)
        pygame.draw.rect(screen, (80, 85, 100), log_rect, 2, border_radius=6)
        chat_title = self.font_small.render("Chat", True, (160, 165, 180))
        screen.blit(chat_title, (log_rect.x + 8, log_rect.y + 6))

        y_line = log_rect.y + 32
        visible = self.chat_lines[-14:]
        for line in visible:
            surf = self.font_small.render(line[:55], True, (200, 200, 210))
            screen.blit(surf, (log_rect.x + 8, y_line))
            y_line += 22

        inp = self.input_rect(screen.get_height())
        border_color = (120, 150, 200) if self.chat_focused else (90, 95, 110)
        pygame.draw.rect(screen, (25, 28, 35), inp, border_radius=4)
        pygame.draw.rect(screen, border_color, inp, 2, border_radius=4)
        prompt = "> " + self.chat_buffer + ("|" if self.chat_focused and (pygame.time.get_ticks() // 500) % 2 else "")
        inp_surf = self.font_small.render(prompt[:48], True, (210, 210, 220))
        screen.blit(inp_surf, (inp.x + 8, inp.y + 8))

        self.draw_end_modal(screen)


def main():
    pygame.init()
    raw_server = sys.argv[1] if len(sys.argv) > 1 else HOST
    callback_host = sys.argv[2] if len(sys.argv) > 2 else None
    server_host, server_port = parse_server_location(raw_server)
    if server_host == "0.0.0.0":
        print(
            "Host 0.0.0.0 é só para o servidor escutar em todas as interfaces; "
            "conectando em 127.0.0.1 neste PC."
        )
        server_host = "127.0.0.1"
    game = DaraPygameClient()
    if not game.connect(server_host, callback_host, server_port):
        print("Não foi possível conectar ao servidor:", game.connection_error)
        print(
            "Deixe o servidor rodando antes do cliente: na pasta dara, "
            "`python server/server.py`. Em Windows, se usares `localhost` e falhar, "
            "tenta `127.0.0.1` (IPv6 ::1 vs IPv4)."
        )
        print("Servidor Pyro5: python server/server.py")
        print(
            "Uso: python client/client_ui_pygame.py [<host_servidor>[:porta]] [<host_visível_para_callbacks>]"
        )
        print(
            "Se o servidor estiver noutra máquina, o 2º argumento deve ser o IP deste PC "
            "acessível pelo servidor (callbacks Pyro)."
        )
        pygame.quit()
        sys.exit(1)

    w = CHAT_X + CHAT_WIDTH + 32
    h = BOARD_Y + ROWS * CELL_SIZE + 56
    screen = pygame.display.set_mode((w, h))
    pygame.display.set_caption("Dara (Pygame + Pyro5)")
    clock = pygame.time.Clock()

    while game.running:
        game.process_incoming()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    game.running = False
                elif event.key == pygame.K_TAB:
                    game.chat_focused = not game.chat_focused
                elif event.key == pygame.K_r and not game.chat_focused and not game.show_end_modal:
                    game.resign()
                elif game.chat_focused:
                    if event.key == pygame.K_RETURN:
                        game.send_chat()
                    elif event.key == pygame.K_BACKSPACE:
                        game.chat_buffer = game.chat_buffer[:-1]
                    elif event.unicode and event.unicode.isprintable() and len(game.chat_buffer) < 200:
                        game.chat_buffer += event.unicode

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if game.show_end_modal and game.restart_button_rect.collidepoint(pos):
                    game.request_restart()
                    continue
                if game.input_rect(screen.get_height()).collidepoint(pos):
                    game.chat_focused = True
                elif game.chat_log_rect().collidepoint(pos):
                    game.chat_focused = True
                else:
                    cell = game.board_cell_from_mouse(pos)
                    if cell:
                        game.chat_focused = False
                        game.on_board_click(cell[0], cell[1])

        game.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)

    game.disconnect()
    pygame.quit()


if __name__ == "__main__":
    main()
