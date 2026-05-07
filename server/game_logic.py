ROWS = 5
COLS = 6

EMPTY = 0
PLAYER1 = 1
PLAYER2 = 2

PIECES_PER_PLAYER = 12


class DaraGame:

    def __init__(self):
        self.board = [[EMPTY for _ in range(COLS)] for _ in range(ROWS)]
        self.current_turn = PLAYER1
        self.pieces_to_place = {
            PLAYER1: PIECES_PER_PLAYER,
            PLAYER2: PIECES_PER_PLAYER
        }
        self.phase = "placement"  # placement ou movement
        self.must_capture = False
        self.player_that_must_capture = None
        self.captures = {PLAYER1: 0, PLAYER2: 0}
        self.game_over_winner = None


    def reset(self):
        self.board = [[EMPTY for _ in range(COLS)] for _ in range(ROWS)]
        self.current_turn = PLAYER1
        self.pieces_to_place = {
            PLAYER1: PIECES_PER_PLAYER,
            PLAYER2: PIECES_PER_PLAYER
        }
        self.phase = "placement"
        self.must_capture = False
        self.player_that_must_capture = None
        self.captures = {PLAYER1: 0, PLAYER2: 0}
        self.game_over_winner = None


    def get_board(self):
        return self.board


    def switch_turn(self):
        if self.current_turn == PLAYER1:
            self.current_turn = PLAYER2
        else:
            self.current_turn = PLAYER1


    def is_valid_position(self, row, col):
        return 0 <= row < ROWS and 0 <= col < COLS


    def place_piece(self, row, col, player):
        """
        Executa jogada na fase de colocação
        """
        if self.phase != "placement":
            return False
        if player != self.current_turn:
            return False
        if not self.is_valid_position(row, col):
            return False
        if self.board[row][col] != EMPTY:
            return False
        # colocar peça temporariamente
        self.board[row][col] = player
        # verificar se formou linha de 3 (não permitido nesta fase)
        if self.check_three_in_a_row(player):
            self.board[row][col] = EMPTY
            return False
        # confirmar jogada
        self.pieces_to_place[player] -= 1
        # verificar se fase terminou
        if (
            self.pieces_to_place[PLAYER1] == 0 and
            self.pieces_to_place[PLAYER2] == 0
        ):
            self.phase = "movement"
        self.switch_turn()
        return True


    def check_three_in_a_row(self, player):
        """
        Retorna lista de posições que formam linha de 3
        ou lista vazia se não houver
        """
        triples = []
        # verificar horizontal
        for r in range(ROWS):
            for c in range(COLS - 2):
                if (
                    self.board[r][c] == player and
                    self.board[r][c + 1] == player and
                    self.board[r][c + 2] == player
                ):
                    triples.append([(r, c), (r, c+1), (r, c+2)])
        # verificar vertical
        for c in range(COLS):
            for r in range(ROWS - 2):
                if (
                    self.board[r][c] == player and
                    self.board[r + 1][c] == player and
                    self.board[r + 2][c] == player
                ):
                    triples.append([(r, c), (r+1, c), (r+2, c)])
        return triples


    def triples_including_cell(self, player, row, col):
        return [t for t in self.check_three_in_a_row(player) if (row, col) in t]


    def is_adjacent(self, r1, c1, r2, c2):
        """
        Verifica se duas posições são adjacentes
        (horizontal ou vertical)
        """
        return abs(r1 - r2) + abs(c1 - c2) == 1
    

    def move_piece(self, from_row, from_col, to_row, to_col, player):
        if self.phase != "movement":
            return False
        if player != self.current_turn:
            return False
        if not self.is_valid_position(to_row, to_col):
            return False
        if self.board[from_row][from_col] != player:
            return False
        if self.board[to_row][to_col] != EMPTY:
            return False
        if not self.is_adjacent(from_row, from_col, to_row, to_col):
            return False
        # mover peça
        self.board[from_row][from_col] = EMPTY
        self.board[to_row][to_col] = player
        # captura só se este movimento formou linha de 3 que inclui a casa de destino
        if self.triples_including_cell(player, to_row, to_col):
            self.must_capture = True
            self.player_that_must_capture = player
        else:
            self.switch_turn()
        return True
    

    def capture_piece(self, row, col, player):
        if not self.must_capture:
            return False
        if player != self.player_that_must_capture:
            return False
        opponent = PLAYER1 if player == PLAYER2 else PLAYER2
        if not self.is_valid_position(row, col):
            return False
        if self.board[row][col] != opponent:
            return False
        # remover peça
        self.board[row][col] = EMPTY
        self.captures[player] += 1
        # resetar estado de captura
        self.must_capture = False
        self.player_that_must_capture = None
        # verificar fim de jogo
        winner = self.check_game_over()
        # trocar turno se não acabou
        if not winner:
            self.switch_turn()
        return True


    def count_pieces(self, player):
        count = 0
        for row in self.board:
            count += row.count(player)
        return count


    def check_game_over(self):
        p1 = self.count_pieces(PLAYER1)
        p2 = self.count_pieces(PLAYER2)
        if p1 <= 2:
            return PLAYER2
        if p2 <= 2:
            return PLAYER1
        return None