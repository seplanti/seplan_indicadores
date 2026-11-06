"""Testes do gateway do Hue (sem rede: o cliente do Hue é substituído por um falso).

Executar:  python -m unittest discover -s tests   (ou: pytest)
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from indicadores import config  # noqa: E402
from indicadores.gateway import AplicacaoGateway, CatalogoHue, ClienteHue, ErroHue  # noqa: E402
from indicadores.servidor import Aplicacao, ArquivosEstaticos, token_bearer  # noqa: E402


class HueFalso:
    def __init__(self):
        self.chamadas = []

    def executar(self, sql, dialeto, banco=None, token=None):
        self.chamadas.append(("executar", sql, dialeto, banco))
        self.token = token
        return {"status": 0, "history_uuid": "9aa393f7-a274-4713-8378-4500be172bfd", "handle": {}}

    def situacao(self, id_operacao, token=None):
        return {"status": 0, "query_status": {"status": "available", "has_result_set": True}}

    def resultados(self, id_operacao, linhas, token=None):
        self.chamadas.append(("resultados", id_operacao, linhas))
        return {"status": 0, "result": {"has_more": False, "data": [["t1", 1], ["t2", 2]],
                                        "meta": [{"name": "nome"}, {"name": "n"}]}}

    def listar(self, caminho, token=None):
        if caminho == "/proibido":
            raise ErroHue(403, "Hue respondeu 403")
        return {"path": caminho, "files": [
            {"name": "..", "path": "/user", "type": "dir", "stats": {"size": 0}},
            {"name": "a.csv", "path": caminho + "/a.csv", "type": "file", "stats": {"size": 10}, "mtime": "x"},
        ]}


class TestAplicacaoGateway(unittest.TestCase):
    def setUp(self):
        self.hue = HueFalso()
        self.app = AplicacaoGateway(self.hue, "impala")

    def corpo(self, resposta):
        return json.loads(resposta.conteudo)

    def test_iniciar_consulta(self):
        r = self.app.tratar("POST", "/api/queries", b'{"statement": "SHOW TABLES", "database": "db1"}')
        self.assertEqual(r.status, 201)
        self.assertEqual(self.corpo(r)["id"], "9aa393f7-a274-4713-8378-4500be172bfd")
        self.assertEqual(self.hue.chamadas, [("executar", "SHOW TABLES", "impala", "db1")])

    def test_iniciar_consulta_invalida(self):
        for corpo in (b"{statement ,\ndialect}", b"{}", b'{"statement": "  "}'):
            with self.subTest(corpo=corpo):
                self.assertEqual(self.app.tratar("POST", "/api/queries", corpo).status, 400)

    def test_status_e_resultados(self):
        r = self.app.tratar("GET", "/api/queries/abc-1/status")
        self.assertEqual(self.corpo(r)["status"], "available")
        r = self.app.tratar("GET", "/api/queries/abc-1/results?rows=5")
        self.assertEqual(self.corpo(r)["rows"], [{"nome": "t1", "n": 1}, {"nome": "t2", "n": 2}])
        self.assertEqual(self.hue.chamadas[-1], ("resultados", "abc-1", 5))

    def test_arquivos(self):
        r = self.app.tratar("GET", "/api/files?path=%2Fuser%2Fx")
        self.assertEqual([f["name"] for f in self.corpo(r)["files"]], ["a.csv"])
        self.assertEqual(self.app.tratar("GET", "/api/files").status, 400)
        self.assertEqual(self.app.tratar("GET", "/api/files?path=/proibido").status, 403)

    def test_metodo_e_rota(self):
        self.assertEqual(self.app.tratar("GET", "/api/queries").status, 405)
        self.assertEqual(self.app.tratar("GET", "/api/queries//status").status, 404)
        self.assertEqual(self.app.tratar("GET", "/api/xyz").status, 404)

    def test_rotas_no_painel(self):
        painel = Aplicacao(None, ArquivosEstaticos(config.WEB_DIR), self.app)
        r = painel.tratar("/api/queries", "POST", b'{"statement": "SHOW TABLES"}')
        self.assertEqual((r.status, r.tipo), (201, "application/json; charset=utf-8"))
        self.assertEqual(self.hue.chamadas[-1], ("executar", "SHOW TABLES", "impala", None))
        self.assertEqual(self.corpo(painel.tratar("/api/queries/abc/status"))["status"], "available")
        r = painel.tratar("/painel", "POST", b"")
        self.assertEqual((r.status, r.tipo), (405, "application/json; charset=utf-8"))

    def test_token_bearer(self):
        self.assertEqual(token_bearer({"Authorization": "Bearer abc.def"}), "abc.def")
        for cabecalhos in ({}, {"Authorization": "Basic xyz"}, {"Authorization": "Bearer "}):
            self.assertIsNone(token_bearer(cabecalhos))
        painel = Aplicacao(None, ArquivosEstaticos(config.WEB_DIR), self.app)
        painel.tratar("/api/queries", "POST", b'{"statement": "SELECT 1"}', "tok")
        self.assertEqual(self.hue.token, "tok")

    def test_sem_credenciais(self):
        app = AplicacaoGateway(ClienteHue("http://127.0.0.1:1", None, None))
        r = app.tratar("GET", "/api/queries/a/status")
        self.assertEqual(r.status, 503)
        self.assertIn("HUE_USUARIO", self.corpo(r)["erro"])


class HueTabelas(HueFalso):
    """Hue simulado para /api/tabelas: a consulta fica "running" uma vez antes de terminar."""

    def __init__(self, situacoes=("running", "available"), erro=None):
        super().__init__()
        self.situacoes = list(situacoes)
        self.erro = erro

    def executar(self, sql, dialeto, banco=None, token=None):
        if self.erro:
            raise ErroHue(502, self.erro)
        return super().executar(sql, dialeto, banco, token)

    def situacao(self, id_operacao, token=None):
        return {"status": 0, "query_status": {"status": self.situacoes.pop(0) if self.situacoes else "running"}}

    def resultados(self, id_operacao, linhas, token=None):
        self.chamadas.append(("resultados", id_operacao, linhas))
        if self.chamadas[0][1].startswith("SHOW TABLES"):
            return {"result": {"meta": [{"name": "name"}], "data": [["tab_a"], ["tab_b"]], "has_more": False}}
        # Tabela com 7 linhas iguais, entregue em páginas como no Hue: cada chamada continua da anterior.
        entregues = getattr(self, "entregues", 0)
        pagina = [[4216602, "S&atilde;o Jos&eacute;", 1023.5]] * min(linhas, 7 - entregues)
        self.entregues = entregues + len(pagina)
        return {"result": {"has_more": self.entregues < 7, "data": pagina,
                           "meta": [{"name": "t.cod_munic"}, {"name": "t.municipio"}, {"name": "t.densidade"}]}}


class TestTabelas(unittest.TestCase):
    TABELA = "avancasc_habitacao_prata_densidade_demografica_2022_den_demografica"

    def criar(self, **kwargs):
        self.hue = HueTabelas(**kwargs)
        self.esperas = []
        return AplicacaoGateway(self.hue, "impala", "seplan_avancasc", limite_maximo=1000,
                                tempo_maximo=60, esperar=self.esperas.append)

    def corpo(self, resposta):
        return json.loads(resposta.conteudo)

    def test_listar_tabelas(self):
        r = self.criar().tratar("GET", "/api/tabelas?database=seplan_avancasc_stage")
        self.assertEqual(r.status, 200)
        self.assertEqual(self.corpo(r), {"database": "seplan_avancasc_stage", "total": 2, "tabelas": ["tab_a", "tab_b"]})
        self.assertEqual(self.hue.chamadas[0][1], "SHOW TABLES IN `seplan_avancasc_stage`")
        self.assertEqual(len(self.esperas), 1)  # esperou uma vez enquanto estava "running"

    def test_consultar_tabela(self):
        r = self.criar().tratar("GET", f"/api/tabelas/{self.TABELA}?limit=5")
        corpo = self.corpo(r)
        self.assertEqual(r.status, 200)
        self.assertEqual(corpo["sql"], f"SELECT * FROM `seplan_avancasc`.`{self.TABELA}` LIMIT 5")
        self.assertEqual(corpo["columns"], ["cod_munic", "municipio", "densidade"])
        self.assertEqual(corpo["rows"], [{"cod_munic": 4216602, "municipio": "São José", "densidade": 1023.5}] * 5)
        self.assertTrue(corpo["has_more"])
        self.assertEqual(self.hue.chamadas[0][3], "seplan_avancasc")
        self.assertEqual(self.hue.chamadas[-1][2], 5)

    def test_paginacao(self):
        app = self.criar()
        app.PAGINA = 2
        corpo = self.corpo(app.tratar("GET", "/api/tabelas/t?limit=100"))
        self.assertEqual((corpo["total"], corpo["has_more"]), (7, False))
        self.assertEqual([c[2] for c in self.hue.chamadas if c[0] == "resultados"], [2, 2, 2, 2])

    def test_colunas(self):
        r = self.criar().tratar("GET", "/api/tabelas/t?database=db&colunas=municipio,%20densidade")
        self.assertEqual(self.corpo(r)["sql"], "SELECT `municipio`, `densidade` FROM `db`.`t` LIMIT 100")

    def test_parametros_invalidos(self):
        app = self.criar()
        for caminho in ("/api/tabelas/x;DROP%20TABLE%20y", "/api/tabelas/t?database=a.b",
                        "/api/tabelas/t?colunas=a,b%20c", "/api/tabelas/t?limit=0",
                        "/api/tabelas/t?limit=1001", "/api/tabelas/t?limit=abc"):
            with self.subTest(caminho=caminho):
                self.assertEqual(app.tratar("GET", caminho).status, 400)
        self.assertEqual(self.hue.chamadas, [])  # nada chegou ao Impala

    def test_erros_do_impala(self):
        casos = [("AnalysisException: Could not resolve table reference: 'db.t'", 404),
                 ("AuthorizationException: User does not have privileges", 403),
                 ("Algum outro erro", 502)]
        for mensagem, status in casos:
            with self.subTest(status=status):
                self.assertEqual(self.criar(erro=mensagem).tratar("GET", "/api/tabelas/t").status, status)

    def test_falha_e_tempo_esgotado(self):
        self.assertEqual(self.criar(situacoes=["failed"]).tratar("GET", "/api/tabelas/t").status, 502)
        app = self.criar(situacoes=[])
        app.tempo_maximo = 0
        self.assertEqual(app.tratar("GET", "/api/tabelas/t").status, 504)

    def test_no_painel(self):
        painel = Aplicacao(None, ArquivosEstaticos(config.WEB_DIR), self.criar())
        self.assertEqual(painel.tratar(f"/api/tabelas/{self.TABELA}").status, 200)


class HueMetadados(HueFalso):
    def logs(self, id_operacao, token=None):
        return {"status": 0, "logs": "Query submitted", "progress": 100, "jobs": [], "isFullLogs": True}

    def bancos(self, dialeto, token=None):
        self.chamadas.append(("bancos", dialeto))
        return {"status": 0, "databases": ["default", "seplan_avancasc_stage"]}


class TestConsultasNomeadas(unittest.TestCase):
    def setUp(self):
        self.catalogo = CatalogoHue.carregar(config.ARQUIVO_ENDPOINTS_HUE)

    def criar(self):
        self.hue = HueTabelas(situacoes=["available"])
        return AplicacaoGateway(self.hue, "impala", "seplan_avancasc", esperar=lambda _: None,
                                catalogo=self.catalogo)

    def corpo(self, resposta):
        return json.loads(resposta.conteudo)

    def test_arquivo_de_endpoints(self):
        documento = json.loads(config.ARQUIVO_ENDPOINTS_HUE.read_text(encoding="utf-8"))
        self.assertEqual(documento["definicoes"]["dialect"], "impala")
        self.assertFalse(documento["definicoes"]["password"])  # senha nunca vai para o JSON
        self.assertEqual(len(self.catalogo.tabelas), 75)
        self.assertEqual(len(self.catalogo.consultas), 75)
        for apelido, tabela in self.catalogo.tabelas.items():
            self.assertRegex(tabela, r"^[a-z0-9_]+$", apelido)
        for item in documento["endpoints"]:
            self.assertRegex(item["url"], r"^\{\{ _\.(base_url|gateway_url) \}\}/api/", item["nome"])

    def test_listar_consultas(self):
        corpo = self.corpo(self.criar().tratar("GET", "/api/consultas"))
        self.assertEqual((corpo["database"], corpo["total"]), ("seplan_avancasc_stage", 75))
        gastos = next(c for c in corpo["consultas"] if c["nome"] == "consultar_gastos_P&D")
        self.assertEqual(gastos["url"], "/api/consultas/consultar_gastos_P%26D")
        self.assertEqual(gastos["tabela_impala"], "industria_gold_gastos_pd_projecao")

    def test_executar_consulta(self):
        for caminho in ("/api/consultas/consultar_ice_emprego", "/api/consultas/ICE_EMPREGO"):
            with self.subTest(caminho=caminho):
                r = self.criar().tratar("GET", caminho)
                corpo = self.corpo(r)
                self.assertEqual(r.status, 200)
                self.assertEqual(corpo["consulta"], "consultar_ice_emprego")
                self.assertEqual(corpo["sql"], "SELECT * FROM `seplan_avancasc_stage`."
                                 "`emprego_renda_hab_asssoc_gold_indice_vulnerabilidade_social_municipio` LIMIT 100")
        r = self.criar().tratar("GET", "/api/consultas/consultar_gastos_P%26D?limit=5&database=outro")
        self.assertEqual(self.corpo(r)["sql"], "SELECT * FROM `outro`.`industria_gold_gastos_pd_projecao` LIMIT 5")
        self.assertEqual(self.criar().tratar("GET", "/api/consultas/nao_existe").status, 404)

    def test_apelido_em_tabelas(self):
        r = self.criar().tratar("GET", "/api/tabelas/tb_gastos_c%26t?database=seplan_avancasc_stage&limit=100")
        self.assertEqual(self.corpo(r)["tabela"], "industria_gold_gastos_ct_por_uf_projecao")

    def test_logs_e_bancos(self):
        app = AplicacaoGateway(HueMetadados(), "impala", catalogo=self.catalogo)
        self.assertEqual(self.corpo(app.tratar("GET", "/api/queries/abc/logs"))["logs"], "Query submitted")
        corpo = self.corpo(app.tratar("GET", "/api/bancos"))
        self.assertEqual(corpo, {"dialect": "impala", "databases": ["default", "seplan_avancasc_stage"]})

    def test_no_painel(self):
        painel = Aplicacao(None, ArquivosEstaticos(config.WEB_DIR), self.criar())
        self.assertEqual(painel.tratar("/api/consultas").status, 200)
        self.assertEqual(painel.tratar("/api/consultas/consultar_IAA").status, 200)


if __name__ == "__main__":
    unittest.main()
