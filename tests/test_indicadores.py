"""Testes do visualizador (sem subir servidor HTTP).

Executar:  python -m unittest discover -s tests   (ou: pytest)
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from indicadores import config  # noqa: E402
from indicadores.api import ConsultaIndicadores  # noqa: E402
from indicadores.importacao import converter_valor, importar_csv, normalizar_codigo  # noqa: E402
from indicadores.modelos import Indicador, SituacaoIndicador, StatusAtualizacao, TabelaDados  # noqa: E402
from indicadores.repositorio import CatalogoIndicadores, RegistroStatus  # noqa: E402
from indicadores.servidor import Aplicacao, ArquivosEstaticos  # noqa: E402

REGISTROS = [
    {"id": 1, "ano": 2022, "fecam": "A", "municipio": "Alfa", "valor": 10.5},
    {"id": 2, "ano": 2022, "fecam": "B", "municipio": "Beta", "valor": 2.0},
    {"id": 3, "ano": 2022, "fecam": "A", "municipio": "Gama", "valor": None},
]


class TestIndicador(unittest.TestCase):
    def test_de_dict_e_fontes_publicas(self):
        ind = Indicador.de_dict({"id": 7, "indicador": "X", "link_da_fonte_publico": "ftp://a",
                                 "link_da_fonte_publico_2": "https://b"})
        self.assertEqual((ind.id, ind.nome), (7, "X"))
        self.assertEqual(ind.fontes_publicas(), ["https://b"])
        self.assertEqual(ind.para_dict()["fontes_publicas"], ["https://b"])


class TestSituacaoIndicador(unittest.TestCase):
    def test_padrao_atualizado(self):
        self.assertTrue(SituacaoIndicador().atualizado)
        self.assertEqual(SituacaoIndicador.de_dict({}).status, StatusAtualizacao.ATUALIZADO)

    def test_desatualizado(self):
        s = SituacaoIndicador.de_dict({"status": "desatualizado", "motivo": "m", "desde": "2026-10-01"})
        self.assertFalse(s.atualizado)
        self.assertEqual(s.para_dict(), {"status": "DESATUALIZADO", "motivo": "m", "desde": "2026-10-01"})

    def test_status_invalido(self):
        with self.assertRaises(ValueError):
            SituacaoIndicador.de_dict({"status": "QUALQUER"})


class TestTabelaDados(unittest.TestCase):
    def setUp(self):
        self.tabela = TabelaDados(REGISTROS)

    def test_colunas_numericas_ignoram_id_e_ano(self):
        self.assertEqual(self.tabela.colunas_numericas, ["valor"])

    def test_estatisticas(self):
        est = self.tabela.estatisticas()
        self.assertEqual(est.total, 3)
        self.assertAlmostEqual(est.media, 6.25)
        self.assertEqual((est.maior, est.rotulo_maior), (10.5, "Alfa"))
        self.assertEqual((est.menor, est.rotulo_menor), (2.0, "Beta"))

    def test_anos_e_filtro_por_ano(self):
        tabela = TabelaDados([{"ano": 2023, "municipio": "Alfa", "valor": 1},
                              {"ano": 2024, "municipio": "Alfa", "valor": 3},
                              {"ano": 2024, "municipio": "Beta", "valor": 5}])
        self.assertEqual(tabela.anos, [2023, 2024])
        est = tabela.do_ano(2024).estatisticas()
        self.assertEqual((est.total, est.media, est.rotulo_menor), (2, 4, "Alfa"))

    def test_sem_coluna_numerica(self):
        self.assertIsNone(TabelaDados([{"municipio": "Alfa"}]).estatisticas())

    def test_tabela_por_fecam_com_total_do_estado_e_projecao(self):
        tabela = TabelaDados([
            {"ano": 2022, "fecam": "Amai", "abrangencia": "FECAM", "observada": 6.0, "projetada": 6.1},
            {"ano": 2022, "fecam": "Amurc", "abrangencia": "FECAM", "observada": 19.0, "projetada": 19.2},
            {"ano": 2022, "fecam": "SC", "abrangencia": "Estado", "observada": 8.7, "projetada": 8.7},
            {"ano": 2024, "fecam": "Amai", "abrangencia": "FECAM", "observada": None, "projetada": 6.5},
            {"ano": 2024, "fecam": "SC", "abrangencia": "Estado", "observada": None, "projetada": 8.74},
        ])
        self.assertEqual(tabela.ano_referencia, 2022)
        est = tabela.do_ano(2022).estatisticas()
        self.assertEqual((est.coluna, est.total, est.media), ("observada", 2, 12.5))
        self.assertEqual((est.rotulo_maior, est.rotulo_menor, est.valor_estado), ("Amurc", "Amai", 8.7))
        projecao = tabela.do_ano(2024).estatisticas()
        self.assertEqual((projecao.coluna, projecao.valor_estado), ("projetada", 8.74))
        self.assertIsNone(tabela.estatisticas().valor_estado)  # vários anos: não há um total único


class TestImportacao(unittest.TestCase):
    def test_converter_valor(self):
        self.assertEqual(converter_valor("2718.0"), 2718)
        self.assertIsInstance(converter_valor("2718.0"), int)
        self.assertEqual(converter_valor("1.5"), 1.5)
        self.assertIsNone(converter_valor("NULL"))
        self.assertEqual(converter_valor("abc"), "abc")

    def test_importar_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "municipios.json").write_text(json.dumps(
                [{"codigo_ibge": "4200051", "municipio": "Abdon Batista", "fecam": "Amplasc"}]), encoding="utf-8")
            (raiz / "dados.csv").write_text(
                "municipio,ano,populacao_residente,write_date,write_time\n"
                "4200051,2001,2718.0,2025-08-12,21:28:14\n"
                "4200051,2002,NULL,2025-08-12,21:28:14\n", encoding="utf-8")
            registros = importar_csv(raiz / "dados.csv", raiz / "saida.json", raiz / "municipios.json").registros
            self.assertEqual(registros[0], {"id": 1, "ano": 2001, "fecam": "Amplasc", "municipio": "Abdon Batista",
                                            "codigo_ibge": "4200051", "populacao_residente": 2718})
            self.assertIsNone(registros[1]["populacao_residente"])
            self.assertEqual(json.loads((raiz / "saida.json").read_text(encoding="utf-8")), registros)

    def test_importar_csv_nacional_sem_coluna_ano(self):
        """Formato da área municipal: cd_mun com '.0', Brasil inteiro e rodapé NULL/OBS."""
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "municipios.json").write_text(json.dumps(
                [{"codigo_ibge": "4200051", "municipio": "Abdon Batista", "fecam": "Amplasc"}]), encoding="utf-8")
            (raiz / "dados.csv").write_text(
                "cd_uf,nm_uf,cd_mun,nm_mun,ar_mun_2024,write_date,write_time\n"
                "11,Rondônia,1101203.0,Ministro Andreazza,798.083,2025-11-19,19:31:44\n"
                "42,Santa Catarina,4200051.0,Abdon Batista,237.517,2025-11-19,19:31:44\n"
                "NULL,NULL,NULL,NULL,NULL,2025-11-19,19:31:44\n"
                '"OBS: valores calculados",NULL,NULL,NULL,NULL,2025-11-19,19:31:44\n', encoding="utf-8")
            resultado = importar_csv(raiz / "dados.csv", raiz / "saida.json", raiz / "municipios.json",
                                     ano=2024, somente_sc=True, descartar=("cd_uf", "nm_uf", "nm_mun"))
            self.assertEqual(resultado.registros, [{"id": 1, "ano": 2024, "fecam": "Amplasc", "municipio": "Abdon Batista",
                                                    "codigo_ibge": "4200051", "ar_mun_2024": 237.517}])
            self.assertEqual(resultado.ignoradas, 3)

    def test_importar_csv_por_fecam(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "municipios.json").write_text(json.dumps(
                [{"codigo_ibge": "4200051", "municipio": "Abdon Batista", "fecam": "Amplasc"},
                 {"codigo_ibge": "4200101", "municipio": "Abelardo Luz", "fecam": "AMFRI"}]), encoding="utf-8")
            (raiz / "dados.csv").write_text(
                "fecam,ano,trajetoria_observada,trajetoria_suavizada,write_date,write_time\n"
                "AMPLASC,2022,4.96,4.9,2025-07-30,18:48:32\n"
                "AMFRI,2023,NULL,7.66,2025-07-30,18:48:32\n"
                "SC,2022,8.66,8.7,2025-07-30,18:48:32\n", encoding="utf-8")
            registros = importar_csv(raiz / "dados.csv", raiz / "saida.json", raiz / "municipios.json").registros
            # ordenados por FECAM (sem diferenciar maiúsculas) e ano, com o total do estado por último
            self.assertEqual([(r["id"], r["fecam"]) for r in registros], [(1, "AMFRI"), (2, "Amplasc"), (3, "SC")])
            self.assertEqual(registros[1], {"id": 2, "ano": 2022, "fecam": "Amplasc", "abrangencia": "FECAM",
                                            "trajetoria_observada": 4.96, "trajetoria_suavizada": 4.9})
            self.assertIsNone(registros[0]["trajetoria_observada"])
            self.assertEqual(registros[2]["abrangencia"], "Estado")
            (raiz / "dados.csv").write_text("fecam,ano,valor\nAMXYZ,2022,1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                importar_csv(raiz / "dados.csv", raiz / "saida.json", raiz / "municipios.json")

    def test_normalizar_codigo(self):
        self.assertEqual(normalizar_codigo("4209508.0"), "4209508")
        self.assertIsNone(normalizar_codigo("NULL"))
        self.assertIsNone(normalizar_codigo("OBS: texto"))

    def test_codigo_sem_cadastro(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "municipios.json").write_text("[]", encoding="utf-8")
            (raiz / "dados.csv").write_text("municipio,ano,valor\n9999999,2001,1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                importar_csv(raiz / "dados.csv", raiz / "saida.json", raiz / "municipios.json")


class TestCatalogo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raiz = Path(self.tmp.name)
        self.tabelas = raiz / "tabelas_bi"
        self.tabelas.mkdir()
        (self.tabelas / "cat_schema_tab.json").write_text(json.dumps(REGISTROS), encoding="utf-8")
        self.arquivo = raiz / "catalogo.json"
        self.arquivo.write_text(json.dumps([
            {"id": 1, "bloco_eixo": "Demografia", "indicador": "Com dados",
             "link_do_arquivo_json": "tabelas_bi/cat.schema.tab.json"},
            {"id": 2, "bloco_eixo": "Saúde", "indicador": "Sem dados",
             "link_do_arquivo_json": "tabelas_bi/inexistente.json"},
            {"id": 3, "indicador": "Fora da pasta", "link_do_arquivo_json": "../catalogo.json"},
        ]), encoding="utf-8")
        self.catalogo = CatalogoIndicadores(self.arquivo, self.tabelas)
        self.arquivo_status = raiz / "status.json"
        self.status = RegistroStatus(self.arquivo_status)
        self.consulta = ConsultaIndicadores(self.catalogo, self.status)

    def tearDown(self):
        self.tmp.cleanup()

    def test_buscar(self):
        self.assertEqual(self.catalogo.buscar("1").nome, "Com dados")
        self.assertIsNone(self.catalogo.buscar("99"))
        self.assertIsNone(self.catalogo.buscar(None))

    def test_eixos(self):
        self.assertEqual(self.catalogo.eixos(), ["", "Demografia", "Saúde"])

    def test_localiza_arquivo_com_pontos_convertidos(self):
        ind = self.catalogo.buscar(1)
        self.assertEqual(self.catalogo.localizar_arquivo(ind).name, "cat_schema_tab.json")
        self.assertEqual(len(self.catalogo.carregar_tabela(ind)), 3)

    def test_arquivo_inexistente_ou_fora_da_pasta(self):
        self.assertFalse(self.catalogo.tem_dados(self.catalogo.buscar(2)))
        self.assertFalse(self.catalogo.tem_dados(self.catalogo.buscar(3)))

    def test_status_padrao_sem_arquivo(self):
        self.assertTrue(self.status.situacao(self.catalogo.buscar(1)).atualizado)
        self.assertEqual(self.consulta.notificacoes(), {"notificacoes": []})

    def test_status_desatualizado_gera_notificacao(self):
        self.arquivo_status.write_text(json.dumps(
            {"indicadores": {"2": {"status": "DESATUALIZADO", "desde": "2026-10-01"}}}), encoding="utf-8")
        self.assertFalse(self.status.situacao(self.catalogo.buscar(2)).atualizado)
        self.assertTrue(self.status.situacao(self.catalogo.buscar(1)).atualizado)
        avisos = self.consulta.notificacoes()["notificacoes"]
        self.assertEqual([a["indicador_id"] for a in avisos], [2])
        self.assertEqual(avisos[0]["desde"], "2026-10-01")

    def test_consulta_listar_e_dados(self):
        lista = self.consulta.listar()["indicadores"]
        self.assertEqual([i["tem_dados"] for i in lista], [True, False, False])
        self.assertEqual(lista[0]["situacao"]["status"], "ATUALIZADO")
        dados = self.consulta.dados(1)
        self.assertEqual(dados["tabela"]["colunas_numericas"], ["valor"])
        self.assertEqual(dados["tabela"]["anos"], [2022])
        self.assertEqual(dados["tabela"]["estatisticas"]["todos"]["total"], 3)
        self.assertEqual(dados["tabela"]["estatisticas"]["2022"]["total"], 3)
        self.assertIsNone(self.consulta.dados(2)["tabela"])
        self.assertIsNone(self.consulta.dados(99))


class TestAplicacao(unittest.TestCase):
    """Rotas com os dados reais do projeto."""

    @classmethod
    def setUpClass(cls):
        catalogo = CatalogoIndicadores(config.ARQUIVO_INDICADORES, config.TABELAS_DIR)
        consulta = ConsultaIndicadores(catalogo, RegistroStatus(config.ARQUIVO_STATUS))
        cls.app = Aplicacao(consulta, ArquivosEstaticos(config.WEB_DIR))

    def corpo(self, caminho):
        r = self.app.tratar(caminho)
        self.assertEqual(r.status, 200, caminho)
        self.assertTrue(r.tipo.startswith("application/json"))
        return json.loads(r.conteudo)

    def test_api_indicadores(self):
        indicadores = self.corpo("/api/indicadores")["indicadores"]
        self.assertGreater(len(indicadores), 0)
        self.assertIn("situacao", indicadores[0])

    def test_api_dados_e_json(self):
        self.assertIsNotNone(self.corpo("/api/indicadores/1/dados")["tabela"])
        self.assertIsInstance(self.corpo("/api/indicadores/1/json"), list)

    def test_api_populacao_serie_historica(self):
        tabela = self.corpo("/api/indicadores/2/dados")["tabela"]
        self.assertEqual(tabela["anos"][-1], 2024)
        est = tabela["estatisticas"]["2024"]
        self.assertEqual((est["coluna"], est["total"]), ("populacao_residente", 295))
        self.assertEqual(est["rotulo_maior"], "Joinville")

    def test_api_area_municipal(self):
        tabela = self.corpo("/api/indicadores/3/dados")["tabela"]
        self.assertEqual(tabela["anos"], [2024])
        est = tabela["estatisticas"]["todos"]
        self.assertEqual((est["coluna"], est["total"]), ("ar_mun_2024", 295))
        self.assertEqual(est["rotulo_maior"], "Lages")

    def test_api_cultura_por_fecam(self):
        tabela = self.corpo("/api/indicadores/4/dados")["tabela"]
        self.assertEqual((tabela["anos"][0], tabela["anos"][-1], tabela["ano_referencia"]), (2010, 2035, 2022))
        est = tabela["estatisticas"]["2022"]
        self.assertEqual((est["coluna"], est["total"], est["rotulo_maior"]), ("trajetoria_observada", 21, "Amurc"))
        self.assertAlmostEqual(est["valor_estado"], 8.66, places=2)
        self.assertEqual(tabela["estatisticas"]["2030"]["coluna"], "trajetoria_suavizada")

    def test_api_economia_criativa(self):
        tabela = self.corpo("/api/indicadores/5/dados")["tabela"]
        self.assertEqual((tabela["anos"][0], tabela["ano_referencia"]), (2010, 2022))
        self.assertEqual(tabela["colunas_numericas"], ["trajetoria_observada"])
        est = tabela["estatisticas"]["2022"]
        self.assertEqual((est["total"], est["valor_estado"], est["rotulo_maior"]), (21, 703688, "AMVE"))

    def test_api_notificacoes(self):
        self.assertIn("notificacoes", self.corpo("/api/notificacoes"))

    def test_interface_react(self):
        for caminho in ("/", "/indicadores/1", "/qualquer-rota"):
            with self.subTest(caminho=caminho):
                r = self.app.tratar(caminho)
                self.assertEqual(r.status, 200)
                self.assertIn(b'<div id="app">', r.conteudo)
        r = self.app.tratar("/js/main.js")
        self.assertEqual((r.status, r.tipo), (200, "text/javascript; charset=utf-8"))

    def test_nao_encontrado(self):
        # O indicador 80 não tem link_do_arquivo_json no catálogo, então nunca terá arquivo de dados.
        for caminho in ("/api/indicadores/999/dados", "/api/indicadores/80/json", "/api/xyz",
                        "/css/nada.css", "/../app.py", "/%2e%2e/app.py"):
            with self.subTest(caminho=caminho):
                self.assertEqual(self.app.tratar(caminho).status, 404)


if __name__ == "__main__":
    unittest.main()
