"""Roteamento (Aplicacao) e servidor HTTP: API REST/JSON em /api e a interface React em web/."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

JSON = "application/json; charset=utf-8"


@dataclass
class Resposta:
    status: int
    conteudo: bytes
    tipo: str = JSON

    @classmethod
    def json(cls, dados, status=200):
        return cls(status, json.dumps(dados, ensure_ascii=False).encode("utf-8"))

    @classmethod
    def erro(cls, status, mensagem):
        return cls.json({"erro": mensagem}, status)


class ArquivosEstaticos:
    """Serve os arquivos da interface web. Caminhos sem extensão que não existem
    (rotas do React, como /indicadores/1) recebem o index.html."""

    TIPOS = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".json": JSON,
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".ico": "image/x-icon",
    }
    INDICE = "index.html"

    def __init__(self, raiz: Path):
        self.raiz = raiz.resolve()

    def localizar(self, caminho_url):
        """Retorna o caminho do arquivo ou None."""
        relativo = unquote(caminho_url).lstrip("/") or self.INDICE
        caminho = (self.raiz / relativo).resolve()
        if caminho.is_file() and self.raiz in caminho.parents:
            return caminho
        if not Path(relativo).suffix:
            return self.raiz / self.INDICE
        return None

    def resposta(self, caminho_url):
        arquivo = self.localizar(caminho_url)
        if arquivo is None:
            return Resposta.erro(404, "Arquivo não encontrado")
        return Resposta(200, arquivo.read_bytes(), self.TIPOS.get(arquivo.suffix.lower(), "application/octet-stream"))


class Aplicacao:
    """Recebe o caminho da requisição e devolve uma Resposta (independente de HTTP)."""

    def __init__(self, consulta, estaticos: ArquivosEstaticos):
        self.consulta = consulta
        self.estaticos = estaticos
        self.rotas = [
            (re.compile(r"/api/indicadores"), self.indicadores),
            (re.compile(r"/api/indicadores/(\d+)/dados"), self.dados),
            (re.compile(r"/api/indicadores/(\d+)/json"), self.json_bruto),
            (re.compile(r"/api/notificacoes"), self.notificacoes),
        ]

    def tratar(self, caminho):
        url = urlparse(caminho)
        try:
            for padrao, rota in self.rotas:
                encontrado = padrao.fullmatch(url.path)
                if encontrado:
                    return rota(*encontrado.groups())
            if url.path.startswith("/api/"):
                return Resposta.erro(404, "Rota não encontrada")
            return self.estaticos.resposta(url.path)
        except Exception as exc:  # devolve o erro em JSON em vez de derrubar a conexão
            return Resposta.erro(500, f"{type(exc).__name__}: {exc}")

    # Rotas da API

    def indicadores(self):
        return Resposta.json(self.consulta.listar())

    def dados(self, id_indicador):
        dados = self.consulta.dados(id_indicador)
        return Resposta.json(dados) if dados else Resposta.erro(404, "Indicador não encontrado")

    def json_bruto(self, id_indicador):
        arquivo = self.consulta.arquivo_json(id_indicador)
        if not arquivo:
            return Resposta.erro(404, "Indicador sem versão publicada")
        return Resposta(200, arquivo.read_bytes())

    def notificacoes(self):
        return Resposta.json(self.consulta.notificacoes())


class Handler(BaseHTTPRequestHandler):
    server: "Servidor"

    def do_GET(self):
        self._enviar(self.server.aplicacao.tratar(self.path))

    def _enviar(self, resposta: Resposta):
        self.send_response(resposta.status)
        self.send_header("Content-Type", resposta.tipo)
        self.send_header("Content-Length", str(len(resposta.conteudo)))
        self.end_headers()
        self.wfile.write(resposta.conteudo)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


class Servidor(ThreadingHTTPServer):
    # No Windows, SO_REUSEADDR deixa um segundo servidor ocupar a mesma porta sem erro
    # (e as requisições continuam indo para o primeiro); lá a porta em uso deve falhar.
    allow_reuse_address = sys.platform != "win32"

    def __init__(self, aplicacao: Aplicacao, host, porta):
        super().__init__((host, porta), Handler)
        self.aplicacao = aplicacao

    @property
    def url(self):
        host, porta = self.server_address[:2]
        return f"http://{host}:{porta}/"
