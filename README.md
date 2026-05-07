# Dara em rede

Jogo de tabuleiro **Dara** para dois jogadores: servidor **Pyro5** (`Daemon` + `PyroDaraGameService`) e cliente **Pygame** que fala Pyro (proxy + callbacks). Constantes do objeto remoto: `shared/pyro_config.py`.

## Pré-requisitos

- **Python 3.10+**
- Dependências (inclui **Pyro5** para RPC e callbacks):

  ```bash
  pip install -r requirements.txt
  ```

## Pastas

| Pasta | Função |
|--------|--------|
| `server/` | `server.py` (daemon Pyro5), `game_logic.py` |
| `client/` | `client_ui_pygame.py` (Pygame; sessão em `transport/pyro_client_session`) |
| `shared/` | `message_contract.py` (contrato de domínio), `pyro_config.py` (porta e id do objeto remoto) |
| `transport/` | Contrato (`game_service_contract`), `match_session`, serviço/listener/sessão Pyro |
| `tests/` | Testes de integração Pyro (subprocesso servidor + dois clientes na mesma máquina) |

## Executar

Na pasta **`dara`**:

### 1. Servidor Pyro5

```bash
python server/server.py
```

Escuta em **`0.0.0.0`** na porta definida em `shared/pyro_config.py` (padrão **`5002`**). Anote o **IP** da máquina se os clientes forem remotos.

### 2. Dois clientes Pygame

Mesmo host que o servidor:

```bash
python client/client_ui_pygame.py
python client/client_ui_pygame.py
```

Servidor noutro PC (substitua pelo IP do host do Pyro):

```bash
python client/client_ui_pygame.py 192.168.0.10
```

**Callbacks (3º argumento):** o servidor invoca o teu listener neste IP. Se conectares ao servidor remoto e o Pyro não conseguir voltar a contactar-te, passa o **IP deste cliente** visível a partir do servidor:

```bash
python client/client_ui_pygame.py 192.168.0.10 192.168.0.20
```

Em **localhost** isso não é necessário. **VirtualBox NAT:** do guest para o host em Windows costuma ser **`10.0.2.2`**.

## Testes automatizados

Na pasta **`dara`** (dois clientes na mesma máquina, servidor num subprocesso; porta TCP aleatória):

```bash
python -m unittest tests.test_pyro_integration -v
```

## Firewall

No **Windows**, regra de entrada **TCP** na porta do servidor Pyro (padrão **5002**). O cliente abre ainda uma porta **local** aleatória para o daemon do **listener** (callbacks do servidor); em uso típico em **localhost** isso não exige regra extra; entre PCs distintos, o firewall do cliente não costuma bloquear conexões de entrada iniciadas em resposta ao teu `join_game`.

## Documentação

`plano.md` e `explicacao.md` no repositório, conforme a organização do projeto.
