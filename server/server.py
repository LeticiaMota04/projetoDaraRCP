"""
Servidor de partida Dara via Pyro5 (Fase 3): ``Daemon`` publica ``PyroDaraGameService``.

Porta TCP padrão em ``shared/pyro_config.py`` (não rode dois servidores na mesma porta).
"""

import socket
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_server_dir = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_server_dir) not in sys.path:
    sys.path.insert(0, str(_server_dir))

import Pyro5.server

from shared.pyro_config import PYRO_GAME_OBJECT_ID, PYRO_GAME_PORT
from transport.pyro_dara_game_service import PyroDaraGameService

HOST = "0.0.0.0"
PORT = PYRO_GAME_PORT
PYRO_OBJECT_ID = PYRO_GAME_OBJECT_ID


def _ipv4_addresses_for_hints():
    seen: list[str] = []
    try:
        hostname = socket.gethostname()
        _, _, addrs = socket.gethostbyname_ex(hostname)
        for a in addrs:
            if not a.startswith("127.") and a not in seen:
                seen.append(a)
    except OSError:
        pass
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("198.51.100.1", 1))
        ip = probe.getsockname()[0]
        if not ip.startswith("127.") and ip not in seen:
            seen.append(ip)
    except OSError:
        pass
    finally:
        probe.close()
    return seen


def _print_connection_hints(listen_port: int) -> None:
    print(
        "Cliente em outro PC ou VM: use o IP desta máquina (não use localhost no cliente remoto)."
    )
    ips = _ipv4_addresses_for_hints()
    if ips:
        print("Alguns IPv4 locais:", ", ".join(ips))
    print(
        "VirtualBox com rede NAT: no Linux guest o host costuma ser 10.0.2.2 — "
        "aponte o cliente Pyro para esse IP se for o caso."
    )
    print(
        f"Firewall: libere TCP na porta do Pyro ({listen_port}). "
        "O transporte Pyro usa uma conexão TCP por chamada/callback."
    )


def start_daemon(listen_port: int | None = None) -> None:
    """
    ``listen_port``: se omitido, usa ``PYRO_GAME_PORT`` em ``shared/pyro_config.py``
    (útil em testes para evitar colisão com um servidor já em execução).
    """
    service = PyroDaraGameService()
    listen = listen_port if listen_port is not None else PORT
    daemon = Pyro5.server.Daemon(host=HOST, port=listen)
    uri = daemon.register(service, PYRO_OBJECT_ID)
    print(f"Servidor Pyro5 escutando em {HOST}:{listen}")
    print("URI registrada:", uri)
    print(f"Exemplo de URI manual: PYRO:{PYRO_OBJECT_ID}@<host>:{listen}")
    _print_connection_hints(listen)
    daemon.requestLoop()


if __name__ == "__main__":
    import os

    _p = os.environ.get("DARA_PYRO_TEST_PORT")
    start_daemon(listen_port=int(_p) if _p else None)
