"""Gateway local para a API v1 do Hue: consultas SQL (Impala/Hive) e listagem do HDFS.

Expõe uma API REST/JSON simples em porta própria (padrão 8001), separada do painel (8000):

    POST /api/queries                     {"statement": "...", "dialect": "impala"}
    GET  /api/queries/<id>/status
    GET  /api/queries/<id>/results[?rows=100]
    GET  /api/files?path=/user/<usuario>
    GET  /api/tabelas[?database=<banco>]                                SHOW TABLES
    GET  /api/tabelas/<tabela>[?database=<banco>&limit=100&colunas=a,b] SELECT ... LIMIT n
    GET  /api/queries/<id>/logs                                         editor/get_logs
    GET  /api/consultas                       consultas nomeadas de Dados/hue_endpoints.json
    GET  /api/consultas/<nome>[?limit=&database=&colunas=]              ex.: consultar_ice_emprego
    GET  /api/bancos[?dialect=impala]                                   editor/autocomplete
    GET  /api/hue/config | historico | conectores | filesystems
    POST /api/tabelas/<tabela>/atualizar | /api/consultas/<nome>/atualizar
         consulta a tabela inteira e grava em Dados/tabelas_impala (comparada com tabelas_bi)

<tabela> aceita o nome real ou o apelido tb_* do hue_endpoints.json. As rotas de /api/tabelas
e /api/consultas fazem o ciclo execute -> check_status -> fetch_result_data e
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
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit
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

    def logs(self, id_operacao, token=None):
        return self._enviar("POST", "/api/v1/editor/get_logs", form={"operationId": id_operacao}, token=token)

    def bancos(self, dialeto, token=None):
        return self._enviar("POST", "/api/v1/editor/autocomplete/",
                            form={"snippet": json.dumps({"type": dialeto})}, token=token)

    def configuracao(self, token=None):
        return self._enviar("POST", "/api/v1/get_config/", token=token)

    def historico(self, dialeto, token=None):
        return self._enviar("GET", "/api/v1/editor/get_history?" + urlencode({"doc_type": dialeto}), token=token)

    def conectores(self, token=None):
        return self._enviar("GET", "/api/v1/connector/types", token=token)

    def filesystems(self, token=None):
        return self._enviar("GET", "/api/v1/storage/filesystems", token=token)


class CatalogoHue:
    """Tabelas (tb_* -> nome no Impala) e consultas nomeadas de Dados/hue_endpoints.json."""

    def __init__(self, documento=None):
        documento = documento or {}
        definicoes = documento.get("definicoes", {})
        self.banco = definicoes.get("database")
        self.limite = int(definicoes.get("limit") or 100)
        self.tabelas = documento.get("tabelas", {})
        self.observacoes = documento.get("observacoes_tabelas", {})
        self.consultas = {item["nome"]: item["tabela"] for item in documento.get("endpoints", [])
                          if item.get("tabela") in self.tabelas}

    @classmethod
    def carregar(cls, arquivo):
        arquivo = Path(arquivo)
        return cls(json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.is_file() else None)

    def tabela(self, nome):
        """Nome real no Impala para um apelido tb_* (ou o próprio nome, se não for apelido)."""
        return self.tabelas.get(nome, nome)

    def consulta(self, nome):
        """(nome, apelido) da consulta, aceitando maiúsculas/minúsculas e sem o prefixo consultar_."""
        procurado = nome.lower()
        for candidato, apelido in self.consultas.items():
            if procurado in (candidato.lower(), candidato.lower().removeprefix("consultar_")):
                return candidato, apelido
        return None


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

    PAGINA = 5000  # linhas por chamada a fetch_result_data

    def __init__(self, hue: ClienteHue, dialeto_padrao="impala", banco_padrao=None,
                 limite_maximo=10000, tempo_maximo=120, intervalo=1.0, esperar=time.sleep,
                 catalogo: CatalogoHue | None = None, repositorio_impala=None, limite_sincronizacao=100000):
        self.hue = hue
        self.catalogo = catalogo or CatalogoHue()
        # RepositorioImpala (indicadores.impala): onde as consultas completas são gravadas para comparar
        # com tabelas_bi. Sem ele, nada é gravado.
        self.repositorio_impala = repositorio_impala
        self.limite_sincronizacao = limite_sincronizacao
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
            ("GET", re.compile(r"/api/queries/([\w-]+)/logs"), self.logs),
            ("GET", re.compile(r"/api/files"), self.arquivos),
            ("GET", re.compile(r"/api/tabelas/?"), self.tabelas),
            ("GET", re.compile(r"/api/tabelas/([^/]+)"), self.consultar_tabela),
            ("GET", re.compile(r"/api/consultas/?"), self.listar_consultas),
            ("GET", re.compile(r"/api/consultas/([^/]+)"), self.executar_consulta),
            ("POST", re.compile(r"/api/consultas/([^/]+)/atualizar"), self.atualizar_consulta),
            ("POST", re.compile(r"/api/tabelas/([^/]+)/atualizar"), self.atualizar),
            ("GET", re.compile(r"/api/bancos/?"), self.bancos),
            ("GET", re.compile(r"/api/hue/config"), self.configuracao),
            ("GET", re.compile(r"/api/hue/historico"), self.historico),
            ("GET", re.compile(r"/api/hue/conectores"), self.conectores),
            ("GET", re.compile(r"/api/hue/filesystems"), self.filesystems),
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

        # O Hue entrega o resultado em páginas: cada fetch_result_data continua de onde o anterior parou.
        dados, meta, tem_mais = [], [], True
        while tem_mais and len(dados) < linhas:
            resultado = self.hue.resultados(id_operacao, min(self.PAGINA, linhas - len(dados)), token).get("result", {})
            meta = meta or resultado.get("meta", [])
            pagina = resultado.get("data", [])
            dados.extend(pagina)
            tem_mais = bool(resultado.get("has_more")) and bool(pagina)
        # O Impala às vezes prefixa a coluna com a tabela ("tabela.coluna"); o Hue escapa texto em HTML.
        colunas = [coluna["name"].split(".")[-1] for coluna in meta]
        registros = [dict(zip(colunas, (html.unescape(v) if isinstance(v, str) else v for v in linha)))
                     for linha in dados]
        return colunas, registros, tem_mais

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
        # Aceita o apelido do hue_endpoints.json (tb_ice_emprego, tb_gastos_p%26d) além do nome real.
        tabela = _identificador(self.catalogo.tabela(unquote(tabela)), "Nome da tabela")
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
        completa = not colunas and not tem_mais and len(registros) < limite
        if completa and self.repositorio_impala:  # a tabela inteira veio: vale como atualização do Impala
            self.repositorio_impala.salvar(tabela, banco, sql, nomes, registros)
        return Resposta.json({"database": banco, "tabela": tabela, "sql": sql, "columns": nomes,
                              "total": len(registros), "rows": registros, "has_more": tem_mais,
                              "gravado": bool(completa and self.repositorio_impala)})

    # Atualização de Dados/tabelas_impala (tabela inteira)

    def atualizar_tabela(self, tabela, banco=None, token=None):
        """Consulta a tabela inteira e grava o resultado no repositório do Impala."""
        if not self.repositorio_impala:
            raise ErroHue(503, "Gravação dos resultados do Impala não configurada")
        banco = _identificador(banco or self.catalogo.banco or self.banco_padrao, "Banco")
        tabela = _identificador(self.catalogo.tabela(tabela), "Nome da tabela")
        limite = self.limite_sincronizacao
        # Pede uma linha a mais: se ela vier, a tabela passa do limite e o resultado é incompleto.
        sql = f"SELECT * FROM `{banco}`.`{tabela}` LIMIT {limite + 1}"
        try:
            nomes, registros, tem_mais = self.consultar(sql, banco, limite + 1, token)
        except ErroHue as exc:
            raise _erro_de_consulta(exc, banco, tabela)
        tem_mais = tem_mais or len(registros) > limite
        return self.repositorio_impala.salvar(tabela, banco, sql, nomes, registros[:limite], tem_mais)

    def atualizar(self, tabela, parametros, corpo, token):
        documento = self.atualizar_tabela(unquote(tabela), parametros.get("database"), token)
        return Resposta.json({chave: valor for chave, valor in documento.items() if chave != "rows"})

    def atualizar_consulta(self, nome, parametros, corpo, token):
        encontrada = self.catalogo.consulta(unquote(nome))
        if not encontrada:
            return Resposta.erro(404, f"Consulta {unquote(nome)!r} não existe; veja a lista em /api/consultas")
        return self.atualizar(encontrada[1], parametros, corpo, token)

    # Consultas nomeadas (seção 6 do hue_endpoints.json)

    def listar_consultas(self, parametros, corpo, token):
        catalogo = self.catalogo
        consultas = [{"nome": nome, "tabela": apelido, "tabela_impala": catalogo.tabela(apelido),
                      "url": "/api/consultas/" + quote(nome, safe=""),
                      **({"observacao": catalogo.observacoes[apelido]} if apelido in catalogo.observacoes else {})}
                     for nome, apelido in catalogo.consultas.items()]
        return Resposta.json({"database": catalogo.banco or self.banco_padrao, "total": len(consultas),
                              "consultas": consultas})

    def executar_consulta(self, nome, parametros, corpo, token):
        encontrada = self.catalogo.consulta(unquote(nome))
        if not encontrada:
            return Resposta.erro(404, f"Consulta {unquote(nome)!r} não existe; veja a lista em /api/consultas")
        nome, apelido = encontrada
        parametros = {"database": self.catalogo.banco or self.banco_padrao,
                      "limit": str(self.catalogo.limite), **parametros}
        resposta = self.consultar_tabela(apelido, parametros=parametros, corpo=corpo, token=token)
        if resposta.status == 200:
            dados = json.loads(resposta.conteudo)
            return Resposta.json({"consulta": nome, "apelido": apelido, **dados})
        return resposta

    # Metadados do Hue

    def logs(self, id_consulta, parametros, corpo, token):
        dados = self.hue.logs(id_consulta, token)
        return Resposta.json({"id": id_consulta, "logs": dados.get("logs", ""), "progress": dados.get("progress"),
                              "jobs": dados.get("jobs", []), "isFullLogs": dados.get("isFullLogs")})

    def bancos(self, parametros, corpo, token):
        dialeto = parametros.get("dialect") or self.dialeto_padrao
        return Resposta.json({"dialect": dialeto, "databases": self.hue.bancos(dialeto, token).get("databases", [])})

    def configuracao(self, parametros, corpo, token):
        return Resposta.json(self.hue.configuracao(token))

    def historico(self, parametros, corpo, token):
        return Resposta.json(self.hue.historico(parametros.get("dialect") or self.dialeto_padrao, token))

    def conectores(self, parametros, corpo, token):
        return Resposta.json(self.hue.conectores(token))

    def filesystems(self, parametros, corpo, token):
        return Resposta.json(self.hue.filesystems(token))


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
