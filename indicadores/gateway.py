"""Gateway local para a API v1 do Hue: consultas SQL (Impala/Hive) e listagem do HDFS.

Expõe uma API REST/JSON simples em porta própria (padrão 8001), separada do painel (8000):

    POST /api/queries                     {"statement": "...", "dialect": "impala"}
    GET  /api/queries/<id>/status
    GET  /api/queries/<id>/results[?rows=100]
    GET  /api/files?path=/user/<usuario>
    GET  /api/tabelas[?database=<banco>]                                SHOW TABLES
    GET  /api/tabelas/<tabela>[?database=<banco>&limit=100&colunas=a,b] SELECT ... LIMIT n

As rotas de /api/tabelas fazem o ciclo execute -> check_status -> fetch_result_data e
devolvem o resultado numa única chamada.
"""

from __future__ import annotations

import html
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from .servidor import Resposta, Servidor, token_bearer


class ErroHue(Exception):
    def __init__(self, status, mensagem):
        super().__init__(mensagem)
        self.status = status


class ClienteHue:
    """Chamadas à API v1 do Hue. Usa o token JWT recebido do cliente (Authorization: Bearer) ou,
    sem ele, um token obtido (e renovado) a partir do usuário e senha do .env."""

    def __init__(self, url_base, usuario, senha, timeout=60):
        self.url_base = url_base.rstrip("/")
        self.usuario = usuario
        self.senha = senha
        self.timeout = timeout
        self._token = None
        self._trava = threading.Lock()

    # Autenticação

    def _autenticar(self):
        if not (self.usuario and self.senha):
            raise ErroHue(503, "Credenciais do Hue não configuradas: preencha HUE_USUARIO e HUE_SENHA no .env "
                               "(e reinicie o app) ou envie o header Authorization: Bearer <access_token do Hue>")
        tokens = self._enviar("POST", "/api/v1/token/auth/", json_=
                              {"username": self.usuario, "password": self.senha}, autenticado=False)
        return tokens["access"]

    def _token_atual(self, renovar=False):
        with self._trava:
            if renovar or not self._token:
                self._token = self._autenticar()
            return self._token

    # HTTP

    def _enviar(self, metodo, caminho, form=None, json_=None, autenticado=True, token=None, _tentativa=0):
        cabecalhos = {"Accept": "application/json"}
        corpo = None
        if form is not None:
            corpo = urlencode(form).encode("utf-8")
            cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"
        elif json_ is not None:
            corpo = json.dumps(json_).encode("utf-8")
            cabecalhos["Content-Type"] = "application/json"
        if autenticado:
            cabecalhos["Authorization"] = f"Bearer {token or self._token_atual(renovar=_tentativa > 0)}"

        requisicao = Request(self.url_base + caminho, data=corpo, headers=cabecalhos, method=metodo)
        try:
            with urlopen(requisicao, timeout=self.timeout) as resposta:
                dados = json.loads(resposta.read().decode("utf-8") or "{}")
        except HTTPError as exc:
            if exc.code == 401 and token:
                raise ErroHue(401, "Token do Hue recusado (expirado?): rode \"Obter token\" ou \"Renovar token\" de novo")
            if exc.code == 401 and autenticado and _tentativa == 0:  # token expirado: autentica de novo
                return self._enviar(metodo, caminho, form, json_, autenticado, _tentativa=1)
            raise ErroHue(exc.code, f"Hue respondeu {exc.code}: {exc.read().decode('utf-8', 'replace')[:500]}")
        except URLError as exc:
            raise ErroHue(502, f"Hue inacessível ({self.url_base}): {exc.reason}")

        if isinstance(dados, dict) and dados.get("status", 0) not in (0, None):
            raise ErroHue(502, dados.get("message") or dados.get("error") or json.dumps(dados, ensure_ascii=False))
        return dados

    # Operações

    def executar(self, sql, dialeto, banco=None, token=None):
        form = {"statement": sql}
        if banco:
            form["database"] = banco
        return self._enviar("POST", f"/api/v1/editor/execute/{quote(dialeto)}", form=form, token=token)

    def situacao(self, id_operacao, token=None):
        return self._enviar("POST", "/api/v1/editor/check_status", form={"operationId": id_operacao}, token=token)

    def resultados(self, id_operacao, linhas, token=None):
        return self._enviar("POST", "/api/v1/editor/fetch_result_data",
                            form={"operationId": id_operacao, "rows": linhas}, token=token)

    def listar(self, caminho, token=None):
        return self._enviar("GET", "/api/v1/storage/view=" + quote(caminho), token=token)


# Nomes de banco, tabela e coluna aceitos nas consultas montadas pelo gateway (evita injeção de SQL).
IDENTIFICADOR = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Situações do check_status do Hue que encerram a consulta.
SITUACOES_CONCLUIDAS = {"available", "success"}
SITUACOES_COM_FALHA = {"failed", "expired", "canceled"}


def _identificador(valor, descricao):
    if not valor or not IDENTIFICADOR.fullmatch(valor):
        raise ErroHue(400, f"{descricao} inválido: {valor!r} (use apenas letras, números e _)")
    return valor


def _erro_de_consulta(exc: ErroHue, banco, tabela=None):
    """Traduz as mensagens de erro do Impala para códigos HTTP mais úteis."""
    mensagem = str(exc)
    if "AuthorizationException" in mensagem:
        return ErroHue(403, f"Sem permissão de leitura (Ranger): {mensagem}")
    if re.search(r"Could not resolve (table|path)|does not exist", mensagem, re.I):
        alvo = f"Tabela {banco}.{tabela}" if tabela else f"Banco {banco}"
        return ErroHue(404, f"{alvo} não encontrada: {mensagem}")
    return exc


class AplicacaoGateway:
    """Recebe método, caminho e corpo e devolve uma Resposta (independente de HTTP)."""

    def __init__(self, hue: ClienteHue, dialeto_padrao="impala", banco_padrao=None,
                 limite_maximo=10000, tempo_maximo=120, intervalo=1.0, esperar=time.sleep):
        self.hue = hue
        self.dialeto_padrao = dialeto_padrao
        self.banco_padrao = banco_padrao
        self.limite_maximo = limite_maximo
        self.tempo_maximo = tempo_maximo
        self.intervalo = intervalo
        self.esperar = esperar
        self.rotas = [
            ("POST", re.compile(r"/api/queries"), self.iniciar_consulta),
            ("GET", re.compile(r"/api/queries/([\w-]+)/status"), self.status),
            ("GET", re.compile(r"/api/queries/([\w-]+)/results"), self.resultados),
            ("GET", re.compile(r"/api/files"), self.arquivos),
            ("GET", re.compile(r"/api/tabelas/?"), self.tabelas),
            ("GET", re.compile(r"/api/tabelas/([^/]+)"), self.consultar_tabela),
        ]

    def tratar(self, metodo, caminho, corpo=b"", token=None):
        url = urlsplit(caminho)
        parametros = {chave: valores[-1] for chave, valores in parse_qs(url.query).items()}
        try:
            metodos = []
            for metodo_rota, padrao, rota in self.rotas:
                encontrado = padrao.fullmatch(url.path)
                if encontrado:
                    if metodo_rota == metodo:
                        return rota(*encontrado.groups(), parametros=parametros, corpo=corpo, token=token)
                    metodos.append(metodo_rota)
            if metodos:
                return Resposta.erro(405, f"Método {metodo} não permitido; use {', '.join(metodos)}")
            return Resposta.erro(404, "Rota não encontrada")
        except ErroHue as exc:
            return Resposta.erro(exc.status, str(exc))
        except Exception as exc:  # devolve o erro em JSON em vez de derrubar a conexão
            return Resposta.erro(500, f"{type(exc).__name__}: {exc}")

    # Consulta completa (execute -> check_status -> fetch_result_data)

    def consultar(self, sql, banco, linhas, token):
        """Executa o SQL, espera terminar e devolve (colunas, linhas como dicts, has_more)."""
        id_operacao = self.hue.executar(sql, self.dialeto_padrao, banco, token)["history_uuid"]
        limite = time.monotonic() + self.tempo_maximo
        while True:
            situacao = self.hue.situacao(id_operacao, token).get("query_status", {})
            estado = situacao.get("status")
            if estado in SITUACOES_CONCLUIDAS:
                break
            if estado in SITUACOES_COM_FALHA:
                raise ErroHue(502, situacao.get("message") or f"Consulta terminou como {estado!r}")
            if time.monotonic() >= limite:
                raise ErroHue(504, f"Consulta não terminou em {self.tempo_maximo}s (id {id_operacao}); "
                                   f"acompanhe em /api/queries/{id_operacao}/status")
            self.esperar(self.intervalo)

        resultado = self.hue.resultados(id_operacao, linhas, token).get("result", {})
        # O Impala às vezes prefixa a coluna com a tabela ("tabela.coluna"); o Hue escapa texto em HTML.
        colunas = [coluna["name"].split(".")[-1] for coluna in resultado.get("meta", [])]
        registros = [dict(zip(colunas, (html.unescape(v) if isinstance(v, str) else v for v in linha)))
                     for linha in resultado.get("data", [])]
        return colunas, registros, resultado.get("has_more", False)

    # Rotas

    def iniciar_consulta(self, parametros, corpo, token):
        try:
            dados = json.loads(corpo or b"{}")
        except json.JSONDecodeError as exc:
            return Resposta.erro(400, f"Corpo deve ser JSON válido: {exc}")
        sql = (dados.get("statement") or "").strip() if isinstance(dados, dict) else ""
        if not sql:
            return Resposta.erro(400, 'Informe o SQL em "statement"')
        dialeto = dados.get("dialect") or self.dialeto_padrao
        banco = dados.get("database") or self.banco_padrao
        execucao = self.hue.executar(sql, dialeto, banco, token)
        return Resposta.json({"id": execucao["history_uuid"], "dialect": dialeto, "database": banco,
                              "status": "submitted"}, 201)

    def status(self, id_consulta, parametros, corpo, token):
        situacao = self.hue.situacao(id_consulta, token).get("query_status", {})
        return Resposta.json({"id": id_consulta, "status": situacao.get("status"),
                              "has_result_set": situacao.get("has_result_set")})

    def resultados(self, id_consulta, parametros, corpo, token):
        linhas = int(parametros.get("rows", 100))
        resultado = self.hue.resultados(id_consulta, linhas, token).get("result", {})
        colunas = [coluna["name"] for coluna in resultado.get("meta", [])]
        return Resposta.json({
            "id": id_consulta,
            "columns": colunas,
            "rows": [dict(zip(colunas, linha)) for linha in resultado.get("data", [])],
            "has_more": resultado.get("has_more", False),
        })

    def arquivos(self, parametros, corpo, token):
        caminho = parametros.get("path")
        if not caminho:
            return Resposta.erro(400, 'Informe o parâmetro "path", ex.: /api/files?path=/user/<usuario>')
        listagem = self.hue.listar(caminho, token)
        return Resposta.json({
            "path": listagem.get("path", caminho),
            "files": [
                {"name": item["name"], "path": item["path"], "type": item.get("type"),
                 "size": item.get("stats", {}).get("size"), "mtime": item.get("mtime")}
                for item in listagem.get("files", []) if item.get("name") not in (".", "..")
            ],
        })

    def tabelas(self, parametros, corpo, token):
        banco = _identificador(parametros.get("database") or self.banco_padrao, "Banco")
        try:
            _, registros, _ = self.consultar(f"SHOW TABLES IN `{banco}`", banco, self.limite_maximo, token)
        except ErroHue as exc:
            raise _erro_de_consulta(exc, banco)
        nomes = [next(iter(registro.values())) for registro in registros if registro]
        return Resposta.json({"database": banco, "total": len(nomes), "tabelas": nomes})

    def consultar_tabela(self, tabela, parametros, corpo, token):
        banco = _identificador(parametros.get("database") or self.banco_padrao, "Banco")
        tabela = _identificador(tabela, "Nome da tabela")
        try:
            limite = int(parametros.get("limit", 100))
        except ValueError:
            return Resposta.erro(400, '"limit" deve ser um número inteiro')
        if not 1 <= limite <= self.limite_maximo:
            return Resposta.erro(400, f'"limit" deve estar entre 1 e {self.limite_maximo}')
        colunas = [c.strip() for c in parametros.get("colunas", "").split(",") if c.strip()]
        selecao = ", ".join(f"`{_identificador(c, 'Coluna')}`" for c in colunas) or "*"

        sql = f"SELECT {selecao} FROM `{banco}`.`{tabela}` LIMIT {limite}"
        try:
            nomes, registros, tem_mais = self.consultar(sql, banco, limite, token)
        except ErroHue as exc:
            raise _erro_de_consulta(exc, banco, tabela)
        return Resposta.json({"database": banco, "tabela": tabela, "sql": sql, "columns": nomes,
                              "total": len(registros), "rows": registros, "has_more": tem_mais})


class HandlerGateway(BaseHTTPRequestHandler):
    server: Servidor

    def do_GET(self):
        self._tratar("GET")

    def do_POST(self):
        self._tratar("POST")

    def do_PUT(self):
        self._tratar("PUT")

    def do_DELETE(self):
        self._tratar("DELETE")

    def _tratar(self, metodo):
        tamanho = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(tamanho) if tamanho else b""
        resposta = self.server.aplicacao.tratar(metodo, self.path, corpo, token_bearer(self.headers))
        self.send_response(resposta.status)
        self.send_header("Content-Type", resposta.tipo)
        self.send_header("Content-Length", str(len(resposta.conteudo)))
        self.end_headers()
        self.wfile.write(resposta.conteudo)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def criar_servidor(aplicacao: AplicacaoGateway, host, porta):
    return Servidor(aplicacao, host, porta, HandlerGateway)
