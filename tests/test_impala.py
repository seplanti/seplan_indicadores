"""Testes da comparação Impala x tabelas_bi (sem rede).

Executar:  python -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from indicadores import config  # noqa: E402
from indicadores.api import ConsultaIndicadores  # noqa: E402
from indicadores.servidor import Aplicacao, ArquivosEstaticos  # noqa: E402
from indicadores.gateway import AplicacaoGateway  # noqa: E402
from indicadores.impala import (ComparadorIndicadores, RepositorioImpala, comparar_registros,  # noqa: E402
                                tabela_impala)
from indicadores.repositorio import CatalogoIndicadores, RegistroStatus  # noqa: E402
from indicadores.modelos import Indicador  # noqa: E402

MUNICIPIOS = {"4200051": {"codigo_ibge": "4200051", "municipio": "Abdon Batista", "fecam": "Amplasc"},
              "4200101": {"codigo_ibge": "4200101", "municipio": "Abelardo Luz", "fecam": "Amai"}}
SISTEMA = [
    {"id": 1, "ano": 2022, "fecam": "Amplasc", "municipio": "Abdon Batista", "codigo_ibge": "4200051", "valor": 10.94},
    {"id": 2, "ano": 2022, "fecam": "Amai", "municipio": "Abelardo Luz", "codigo_ibge": "4200101", "valor": 18.23},
]
IMPALA = [  # como vem do Hue: código numérico, decimal como texto, NBSP no nome, coluna de carga
    {"ano": 2022, "cod_munic": 4200101, "municipio": "Abelardo\xa0Luz", "valor": "18.23", "write_date": "2025-11-01"},
    {"ano": 2022, "cod_munic": 4200051, "municipio": "Abdon\xa0Batista", "valor": 10.94, "write_date": "2025-11-01"},
]


class TestCompararRegistros(unittest.TestCase):
    def test_iguais_apesar_do_formato_e_da_ordem(self):
        r = comparar_registros(IMPALA, SISTEMA, MUNICIPIOS)
        self.assertEqual(r.status, "ATUALIZADO", r.motivo)
        self.assertIn("valor", r.colunas)
        self.assertNotIn("write_date", r.colunas)

    def test_valor_diferente(self):
        impala = [IMPALA[0] | {"valor": 19.5}, IMPALA[1]]
        r = comparar_registros(impala, SISTEMA, MUNICIPIOS)
        self.assertEqual((r.status, r.diferencas), ("DESATUALIZADO", 2))
        self.assertIn("1 linha(s) só no Impala e 1 só no sistema", r.motivo)

    def test_linha_nova_no_impala(self):
        impala = IMPALA + [{"ano": 2023, "cod_munic": 4200051, "valor": 11.0}]
        self.assertEqual(comparar_registros(impala, SISTEMA, MUNICIPIOS).status, "DESATUALIZADO")

    def test_duplicadas_e_linhas_vazias_nao_contam(self):
        impala = IMPALA + [IMPALA[0], {"ano": 2030, "cod_munic": 4200051, "valor": None}]
        r = comparar_registros(impala, SISTEMA, MUNICIPIOS)
        self.assertEqual(r.status, "ATUALIZADO", r.motivo)
        self.assertEqual(r.duplicadas_impala, 1)

    def test_copia_direta_do_impala(self):
        sistema = [{"municipio": "ABDON BATISTA", "year": 2010, "total_mortes": 6}]
        impala = [{"municipio": "ABDON\xa0BATISTA", "year": "2010", "total_mortes": "6"}]
        self.assertEqual(comparar_registros(impala, sistema, MUNICIPIOS).status, "ATUALIZADO")

    def test_serie_do_estado(self):
        sistema = [{"id": 1, "ano": 1985, "fecam": "SC", "abrangencia": "Estado", "taxa": 7.06}]
        self.assertEqual(comparar_registros([{"ano": 1985, "taxa": 7.06}], sistema, MUNICIPIOS).status, "ATUALIZADO")

    def test_sem_colunas_em_comum_ou_sem_linhas(self):
        self.assertEqual(comparar_registros([{"outra": 1}], SISTEMA, MUNICIPIOS).status, "SEM_COMPARACAO")
        self.assertEqual(comparar_registros([], SISTEMA, MUNICIPIOS).status, "SEM_COMPARACAO")


class Ambiente:
    """Catálogo, tabelas_bi, tabelas_impala e municípios num diretório temporário."""

    def __init__(self, raiz: Path):
        self.raiz = raiz
        (raiz / "tabelas_bi").mkdir()
        (raiz / "municipios.json").write_text(json.dumps(list(MUNICIPIOS.values())), encoding="utf-8")
        (raiz / "catalogo.json").write_text(json.dumps([
            {"id": 1, "indicador": "Densidade", "tabela_databricks": "avancasc.habitacao_prata.densidade",
             "link_do_arquivo_json": "tabelas_bi/avancasc.habitacao_prata.densidade.json"},
            {"id": 2, "indicador": "Sem tabela"},
        ]), encoding="utf-8")
        self.gravar_sistema(SISTEMA)
        self.catalogo = CatalogoIndicadores(raiz / "catalogo.json", raiz / "tabelas_bi")
        self.repositorio = RepositorioImpala(raiz / "tabelas_impala")
        self.comparador = ComparadorIndicadores(self.catalogo, self.repositorio, raiz / "municipios.json")
        self.consulta = ConsultaIndicadores(self.catalogo, RegistroStatus(raiz / "status.json"), self.comparador)

    def gravar_sistema(self, registros):
        (self.raiz / "tabelas_bi" / "avancasc_habitacao_prata_densidade.json").write_text(
            json.dumps(registros), encoding="utf-8")


class TestComparadorEPainel(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.amb = Ambiente(Path(self.temp.name))
        self.indicador = self.amb.catalogo.buscar(1)

    def tearDown(self):
        self.temp.cleanup()

    def situacao(self):
        return self.amb.comparador.situacao(self.amb.catalogo.buscar(1))

    def test_nome_da_tabela(self):
        self.assertEqual(tabela_impala(self.indicador), "avancasc_habitacao_prata_densidade")
        self.assertIsNone(tabela_impala(Indicador(id=9)))
        self.assertIsNone(self.amb.comparador.situacao(self.amb.catalogo.buscar(2)))

    def test_sem_consulta_atualizado_e_desatualizado(self):
        s = self.situacao()
        self.assertEqual((s["impala"]["status"], s["sistema"]["status"]), ("SEM_CONSULTA", "SEM_COMPARACAO"))

        self.amb.repositorio.salvar("avancasc_habitacao_prata_densidade", "db", "SELECT", ["x"], IMPALA,
                                    consultado_em="2026-11-06T10:00:00")
        s = self.situacao()
        self.assertEqual((s["impala"]["status"], s["sistema"]["status"]), ("ATUALIZADO", "ATUALIZADO"))
        self.assertEqual(s["impala"]["consultado_em"], "2026-11-06T10:00:00")

        self.amb.gravar_sistema([SISTEMA[0]])  # sistema perdeu uma linha: recalcula pelo mtime
        s = self.situacao()
        self.assertEqual((s["impala"]["status"], s["sistema"]["status"]), ("ATUALIZADO", "DESATUALIZADO"))

    def test_consulta_incompleta_e_sem_arquivo(self):
        self.amb.repositorio.salvar("avancasc_habitacao_prata_densidade", "db", "SELECT", [], IMPALA, tem_mais=True)
        self.assertIn("incompleta", self.situacao()["sistema"]["motivo"])
        self.amb.repositorio.salvar("avancasc_habitacao_prata_densidade", "db", "SELECT", [], IMPALA)
        (self.amb.raiz / "tabelas_bi" / "avancasc_habitacao_prata_densidade.json").unlink()
        self.assertEqual(self.situacao()["sistema"]["status"], "DESATUALIZADO")

    def test_painel_usa_a_comparacao(self):
        self.amb.repositorio.salvar("avancasc_habitacao_prata_densidade", "db", "SELECT", [], IMPALA,
                                    consultado_em="2026-11-06T10:00:00")
        resumo = self.amb.consulta.listar()["indicadores"][0]
        self.assertEqual(resumo["situacao"]["status"], "ATUALIZADO")
        self.assertEqual(resumo["impala"]["sistema"]["status"], "ATUALIZADO")

        self.amb.gravar_sistema([SISTEMA[0] | {"valor": 1.0}, SISTEMA[1]])
        resumo = self.amb.consulta.listar()["indicadores"][0]
        self.assertEqual(resumo["situacao"]["status"], "DESATUALIZADO")
        self.assertEqual(resumo["situacao"]["desde"], "2026-11-06")
        self.assertIn("diferentes do Impala", resumo["situacao"]["motivo"])
        self.assertEqual([n["indicador_id"] for n in self.amb.consulta.notificacoes()["notificacoes"]], [1])
        self.assertIsNone(self.amb.consulta.listar()["indicadores"][1]["impala"])  # sem tabela no catálogo


class TestRotasDoPainel(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.amb = Ambiente(Path(self.temp.name))
        self.app = Aplicacao(self.amb.consulta, ArquivosEstaticos(config.WEB_DIR))

    def tearDown(self):
        self.temp.cleanup()

    def corpo(self, caminho):
        r = self.app.tratar(caminho)
        return r.status, json.loads(r.conteudo)

    def test_sem_consulta_e_com_consulta(self):
        status, corpo = self.corpo("/api/indicadores/1/impala")
        self.assertEqual((status, corpo["consulta"]), (200, None))
        self.assertEqual(self.app.tratar("/api/indicadores/1/impala/json").status, 404)

        self.amb.repositorio.salvar("avancasc_habitacao_prata_densidade", "db", "SELECT 1", ["valor"], IMPALA)
        status, corpo = self.corpo("/api/indicadores/1/impala")
        self.assertEqual((corpo["consulta"]["total"], corpo["consulta"]["sql"]), (2, "SELECT 1"))
        self.assertEqual(corpo["indicador"]["impala"]["sistema"]["status"], "ATUALIZADO")
        status, bruto = self.corpo("/api/indicadores/1/impala/json")
        self.assertEqual((status, len(bruto["rows"])), (200, 2))

    def test_indicador_sem_tabela_ou_inexistente(self):
        status, corpo = self.corpo("/api/indicadores/2/impala")
        self.assertEqual((status, corpo["consulta"], corpo["indicador"]["impala"]), (200, None, None))
        self.assertEqual(self.app.tratar("/api/indicadores/2/impala/json").status, 404)
        self.assertEqual(self.app.tratar("/api/indicadores/99/impala").status, 404)


class HueTabelaCompleta:
    """Hue falso com uma tabela de `n` linhas."""

    def __init__(self, n):
        self.n, self.sqls = n, []

    def executar(self, sql, dialeto, banco=None, token=None):
        self.sqls.append(sql)
        self.entregues = 0
        return {"history_uuid": "u1"}

    def situacao(self, id_operacao, token=None):
        return {"query_status": {"status": "available"}}

    def resultados(self, id_operacao, linhas, token=None):
        limite_sql = int(self.sqls[-1].rsplit(" ", 1)[1])
        pagina = [[i, "x"] for i in range(self.entregues, min(self.n, limite_sql, self.entregues + linhas))]
        self.entregues += len(pagina)
        return {"result": {"meta": [{"name": "t.n"}, {"name": "t.s"}], "data": pagina,
                           "has_more": self.entregues < min(self.n, limite_sql)}}


class TestGravacaoNoGateway(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repositorio = RepositorioImpala(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def app(self, n, limite=10):
        self.hue = HueTabelaCompleta(n)
        return AplicacaoGateway(self.hue, "impala", "db", esperar=lambda _: None, repositorio_impala=self.repositorio,
                                limite_sincronizacao=limite)

    def test_atualizar_grava_a_tabela_inteira(self):
        r = self.app(7).tratar("POST", "/api/tabelas/minha_tabela/atualizar?database=stage")
        corpo = json.loads(r.conteudo)
        self.assertEqual((r.status, corpo["total"], corpo["has_more"]), (200, 7, False))
        self.assertNotIn("rows", corpo)
        self.assertEqual(self.hue.sqls[-1], "SELECT * FROM `stage`.`minha_tabela` LIMIT 11")
        gravado = self.repositorio.ler("minha_tabela")
        self.assertEqual(gravado["rows"][0], {"n": 0, "s": "x"})

    def test_tabela_maior_que_o_limite_fica_incompleta(self):
        self.app(25).tratar("POST", "/api/tabelas/t/atualizar")
        gravado = self.repositorio.ler("t")
        self.assertEqual((gravado["total"], gravado["has_more"]), (10, True))

    def test_consulta_get_completa_tambem_grava(self):
        app = self.app(7)
        self.assertTrue(json.loads(app.tratar("GET", "/api/tabelas/t?limit=100").conteudo)["gravado"])
        self.assertEqual(self.repositorio.ler("t")["total"], 7)
        # limitada (pode haver mais linhas) ou só algumas colunas: não grava
        self.assertFalse(json.loads(app.tratar("GET", "/api/tabelas/u?limit=7").conteudo)["gravado"])
        self.assertFalse(json.loads(app.tratar("GET", "/api/tabelas/v?colunas=n").conteudo)["gravado"])
        self.assertIsNone(self.repositorio.ler("u"))


if __name__ == "__main__":
    unittest.main()
