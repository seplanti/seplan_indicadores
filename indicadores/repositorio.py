"""Acesso aos arquivos de dados: catálogo de indicadores, situação de atualização e tabelas_bi."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from .modelos import Indicador, SituacaoIndicador, TabelaDados


def carregar_json(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


class ArquivoJson:
    """Arquivo JSON mantido em cache e relido automaticamente quando é modificado em disco,
    para que atualizações apareçam sem reiniciar o app.

    Com `padrao`, um arquivo inexistente vale `padrao`; sem ele, a ausência é um erro.
    """

    def __init__(self, caminho: Path, converter=lambda dados: dados, padrao=None):
        self.caminho = caminho
        self.converter = converter
        self.padrao = padrao
        self._valor = None
        self._mtime = None
        self._trava = threading.Lock()

    def ler(self):
        with self._trava:
            if self.padrao is not None and not self.caminho.exists():
                return self.padrao
            mtime = self.caminho.stat().st_mtime
            if mtime != self._mtime:
                self._valor = self.converter(carregar_json(self.caminho))
                self._mtime = mtime
            return self._valor


class CatalogoIndicadores:
    """Catálogo de indicadores lido do JSON de base."""

    def __init__(self, arquivo: Path, pasta_tabelas: Path):
        self.arquivo = arquivo
        self.pasta_tabelas = pasta_tabelas
        self._json = ArquivoJson(arquivo, lambda dados: [Indicador.de_dict(d) for d in dados])

    def todos(self):
        return list(self._json.ler())

    def buscar(self, id_indicador):
        if id_indicador is None:
            return None
        return next((i for i in self.todos() if str(i.id) == str(id_indicador)), None)

    def eixos(self):
        return sorted({i.eixo or "" for i in self.todos()})

    def localizar_arquivo(self, indicador: Indicador):
        """Resolve link_arquivo_json para um arquivo existente na pasta de tabelas.

        No catálogo o link vem como tabelas_bi/catalogo.schema.tabela.json, mas os
        arquivos salvos usam underscores (catalogo_schema_tabela.json).
        """
        nome = indicador.link_arquivo_json
        if not nome:
            return None
        relativo = Path(nome)
        pasta = self.pasta_tabelas / relativo.parent.relative_to(self.pasta_tabelas.name) \
            if relativo.parts[:1] == (self.pasta_tabelas.name,) else self.pasta_tabelas
        arquivo = relativo.name
        base = arquivo[:-5] if arquivo.lower().endswith(".json") else arquivo
        for candidato in (arquivo, base.replace(".", "_") + ".json"):
            caminho = (pasta / candidato).resolve()
            if caminho.is_file() and self.pasta_tabelas.resolve() in caminho.parents:
                return caminho
        return None

    def tem_dados(self, indicador: Indicador):
        return self.localizar_arquivo(indicador) is not None

    def carregar_tabela(self, indicador: Indicador):
        arquivo = self.localizar_arquivo(indicador)
        if arquivo is None:
            return None
        return TabelaDados(carregar_json(arquivo), arquivo, indicador.coluna_valor)


class RegistroStatus:
    """Situação de atualização dos indicadores, lida de status_indicadores.json:

        {"indicadores": {"12": {"status": "DESATUALIZADO", "motivo": "...", "desde": "2026-10-20"}}}

    Indicadores ausentes do arquivo (ou arquivo inexistente) são considerados atualizados.
    """

    def __init__(self, arquivo: Path):
        self.arquivo = arquivo
        self._json = ArquivoJson(arquivo, self._converter, padrao={})

    @staticmethod
    def _converter(dados):
        return {str(id_): SituacaoIndicador.de_dict(s) for id_, s in dados.get("indicadores", {}).items()}

    def situacao(self, indicador: Indicador):
        return self._json.ler().get(str(indicador.id), SituacaoIndicador())
