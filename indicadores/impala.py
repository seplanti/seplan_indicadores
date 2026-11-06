"""Resultados das consultas ao Impala (via Hue) e comparação com as tabelas_bi do sistema.

Cada consulta completa a uma tabela é gravada em Dados/tabelas_impala/<tabela>.json, separada
de Dados/tabelas_bi (que continua sendo a fonte do painel):

    {"tabela": ..., "database": ..., "sql": ..., "consultado_em": "2026-11-06T10:00:00",
     "columns": [...], "total": 295, "has_more": false, "rows": [{coluna: valor}, ...]}

A comparação passa as linhas do Impala pela mesma conversão do importador de CSV
(importacao.converter_registros: nome e FECAM do município, NULL -> null, decimais etc.) e
compara com a tabela_bi equivalente nas colunas que as duas têm em comum, sem olhar a ordem
das linhas, o `id`, maiúsculas/espaços nos textos nem linhas repetidas (cargas duplicadas no
Impala são informadas em `duplicadas_impala`). Resultado por indicador:

    impala:  ATUALIZADO (há consulta gravada) | SEM_CONSULTA
    sistema: ATUALIZADO (dados iguais) | DESATUALIZADO (diferentes ou sem tabela_bi) | SEM_COMPARACAO

Atualizar todas as tabelas do catálogo pela linha de comando:

    python -m indicadores.impala [--indicador 1 2 ...] [--database seplan_avancasc_stage]
"""

from __future__ import annotations

import json
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import config
from .importacao import COLUNA_COM_ANO, COLUNAS_CODIGO, converter_registros, converter_valor
from .repositorio import carregar_json

IMPALA_ATUALIZADO = "ATUALIZADO"
IMPALA_SEM_CONSULTA = "SEM_CONSULTA"
SISTEMA_ATUALIZADO = "ATUALIZADO"
SISTEMA_DESATUALIZADO = "DESATUALIZADO"
SISTEMA_SEM_COMPARACAO = "SEM_COMPARACAO"

# Colunas que identificam a linha; é preciso ao menos uma coluna de dados além delas para comparar.
COLUNAS_IDENTIFICACAO = {"id", "ano", "fecam", "municipio", "codigo_ibge", "abrangencia"}


def tabela_impala(indicador):
    """avancasc.saude_ouro.x (catálogo) -> avancasc_saude_ouro_x (nome no seplan_avancasc_stage)."""
    nome = (indicador.tabela_databricks or "").strip()
    return nome.replace(".", "_") or None


class RepositorioImpala:
    """Arquivos JSON com o resultado das consultas ao Impala, um por tabela."""

    def __init__(self, pasta: Path):
        self.pasta = pasta

    def caminho(self, tabela):
        return self.pasta / f"{tabela}.json"

    def salvar(self, tabela, database, sql, colunas, registros, tem_mais=False, consultado_em=None):
        self.pasta.mkdir(parents=True, exist_ok=True)
        documento = {
            "tabela": tabela, "database": database, "sql": sql,
            "consultado_em": consultado_em or datetime.now().isoformat(timespec="seconds"),
            "columns": colunas, "total": len(registros), "has_more": tem_mais,
            # Resultado incompleto não serve para comparar: guarda só os metadados, sem ocupar disco.
            "rows": [] if tem_mais else registros,
        }
        destino = self.caminho(tabela)
        temporario = destino.with_suffix(".json.tmp")  # grava inteiro e troca, para nunca ler meio arquivo
        temporario.write_text(json.dumps(documento, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temporario.replace(destino)
        return documento

    def ler(self, tabela):
        caminho = self.caminho(tabela)
        return carregar_json(caminho) if caminho.is_file() else None


@dataclass(frozen=True)
class ResultadoComparacao:
    status: str  # SISTEMA_*
    motivo: str | None = None
    colunas: tuple = ()
    linhas_impala: int | None = None
    linhas_sistema: int | None = None
    diferencas: int = 0
    duplicadas_impala: int = 0


def _normalizar(valor):
    """Mesma representação para 10.94 / "10.94" / "10,94", 2022 / "2022" / 2022.0 e textos que só
    diferem em maiúsculas ou espaços (o Impala às vezes traz espaço não separável, \xa0)."""
    if valor is None:
        return None
    if not isinstance(valor, (int, float)) or isinstance(valor, bool):
        valor = converter_valor(str(valor))
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f"{valor:.9g}"
    return " ".join(str(valor).split()).casefold()


def comparar_registros(linhas_impala, registros_sistema, municipios):
    """Compara as linhas brutas do Impala com os registros de uma tabela_bi."""
    if not linhas_impala:
        return ResultadoComparacao(SISTEMA_SEM_COMPARACAO, "A consulta ao Impala não trouxe linhas.", linhas_impala=0,
                                   linhas_sistema=len(registros_sistema))
    colunas_sistema = {c for r in registros_sistema for c in r}
    # O Impala às vezes traz espaço não separável (\xa0) nos textos ("Santa\xa0Catarina").
    linhas_impala = [{c: v.replace("\xa0", " ") if isinstance(v, str) else v for c, v in linha.items()}
                     for linha in linhas_impala]
    colunas_impala = set(linhas_impala[0])
    # Algumas tabelas_bi foram copiadas direto do Impala, sem o importador; por isso a comparação é
    # feita das duas formas (linhas como estão e linhas convertidas) e vale a que casar melhor.
    direta = _comparar(linhas_impala, registros_sistema, colunas_sistema)
    if direta.status == SISTEMA_ATUALIZADO:
        return direta
    if not colunas_impala & {*COLUNAS_CODIGO, "fecam"} and {r.get("fecam") for r in registros_sistema} == {"SC"}:
        # série só do estado: o importador recebeu as linhas com fecam = SC
        linhas_impala = [{"fecam": "SC"} | linha for linha in linhas_impala]
    # Mesmas opções que o importador recebeu ao gerar a tabela_bi, deduzidas das colunas:
    # --colunas-por-ano: o Impala tem valor_2000, valor_2010 e o sistema tem a coluna ano.
    por_ano = "ano" in colunas_sistema and any(
        COLUNA_COM_ANO.match(c) and c not in colunas_sistema for c in colunas_impala)
    # --ano: o Impala não tem a coluna ano e o sistema tem um ano só.
    anos = {r.get("ano") for r in registros_sistema}
    ano = next(iter(anos)) if "ano" not in colunas_impala and not por_ano and len(anos) == 1 else None
    textos = [{c: "NULL" if v is None else str(v) for c, v in linha.items()} for linha in linhas_impala]
    try:
        convertidos = converter_registros(textos, municipios, ano=ano, somente_sc=True, colunas_por_ano=por_ano).registros
    except ValueError as exc:
        convertida = ResultadoComparacao(SISTEMA_SEM_COMPARACAO, f"Linhas do Impala não convertidas: {exc}",
                                         linhas_impala=len(linhas_impala), linhas_sistema=len(registros_sistema))
    else:
        convertida = _comparar(convertidos, registros_sistema, colunas_sistema)
    # Prefere a que conseguiu comparar e, entre elas, a com menos diferenças.
    return min((convertida, direta), key=lambda r: (r.status == SISTEMA_SEM_COMPARACAO, r.diferencas))


def _comparar(convertidos, registros_sistema, colunas_sistema):
    colunas = sorted(({c for r in convertidos for c in r} & colunas_sistema) - {"id"})
    if not set(colunas) - COLUNAS_IDENTIFICACAO:
        return ResultadoComparacao(SISTEMA_SEM_COMPARACAO, "Nenhuma coluna de dados em comum entre o Impala e o sistema.",
                                   tuple(colunas), len(convertidos), len(registros_sistema))

    dados = [i for i, c in enumerate(colunas) if c not in COLUNAS_IDENTIFICACAO]

    def contagem(registros):
        # Linhas sem nenhum valor (ex.: anos de projeção ainda vazios) não contam como dado.
        linhas = (tuple(_normalizar(r.get(c)) for c in colunas) for r in registros)
        return Counter(linha for linha in linhas if any(linha[i] is not None for i in dados))

    impala, sistema = contagem(convertidos), contagem(registros_sistema)
    so_impala, so_sistema = len(impala.keys() - sistema.keys()), len(sistema.keys() - impala.keys())
    base = dict(colunas=tuple(colunas), linhas_impala=len(convertidos), linhas_sistema=len(registros_sistema),
                duplicadas_impala=sum(impala.values()) - len(impala))
    if not so_impala and not so_sistema:
        return ResultadoComparacao(SISTEMA_ATUALIZADO, None, diferencas=0, **base)
    motivo = (f"Dados do sistema diferentes do Impala: {so_impala} linha(s) só no Impala e "
              f"{so_sistema} só no sistema ({len(convertidos)} x {len(registros_sistema)} linhas).")
    return ResultadoComparacao(SISTEMA_DESATUALIZADO, motivo, diferencas=so_impala + so_sistema, **base)


class ComparadorIndicadores:
    """Situação Impala x sistema de cada indicador, recalculada só quando um dos arquivos muda."""

    def __init__(self, catalogo, repositorio: RepositorioImpala, arquivo_municipios: Path = config.ARQUIVO_MUNICIPIOS):
        self.catalogo = catalogo
        self.repositorio = repositorio
        self.arquivo_municipios = arquivo_municipios
        self._municipios = None
        self._cache = {}
        self._trava = threading.Lock()

    @property
    def municipios(self):
        if self._municipios is None:
            self._municipios = {m["codigo_ibge"]: m for m in carregar_json(self.arquivo_municipios)}
        return self._municipios

    def situacao(self, indicador):
        tabela = tabela_impala(indicador)
        if tabela is None:
            return None
        arquivo_impala = self.repositorio.caminho(tabela)
        arquivo_sistema = self.catalogo.localizar_arquivo(indicador)
        chave = (tabela, _mtime(arquivo_impala), arquivo_sistema, _mtime(arquivo_sistema), indicador.coluna_valor)
        with self._trava:
            if chave not in self._cache:
                self._cache[chave] = self._calcular(tabela, arquivo_sistema)
            return self._cache[chave]

    def _calcular(self, tabela, arquivo_sistema):
        documento = self.repositorio.ler(tabela)
        if documento is None:
            return {"tabela": tabela,
                    "impala": {"status": IMPALA_SEM_CONSULTA, "consultado_em": None, "linhas": None},
                    "sistema": {"status": SISTEMA_SEM_COMPARACAO, "motivo": "O Impala ainda não foi consultado."}}
        impala = {"status": IMPALA_ATUALIZADO, "consultado_em": documento.get("consultado_em"),
                  "linhas": documento.get("total"), "database": documento.get("database")}
        if documento.get("has_more"):
            resultado = ResultadoComparacao(SISTEMA_SEM_COMPARACAO,
                                            f"Consulta ao Impala incompleta: a tabela passa de {documento.get('total')} "
                                            "linhas (HUE_LIMITE_SINCRONIZACAO).")
        elif not documento.get("rows"):
            resultado = ResultadoComparacao(SISTEMA_SEM_COMPARACAO, "A tabela está vazia no Impala.", linhas_impala=0)
        elif arquivo_sistema is None:
            resultado = ResultadoComparacao(SISTEMA_DESATUALIZADO, "O Impala tem dados, mas não há arquivo em tabelas_bi.",
                                            linhas_impala=documento.get("total"), linhas_sistema=0)
        else:
            resultado = comparar_registros(documento.get("rows", []), carregar_json(arquivo_sistema), self.municipios)
        return {"tabela": tabela, "impala": impala, "sistema": {
            "status": resultado.status, "motivo": resultado.motivo, "colunas": list(resultado.colunas),
            "linhas_impala": resultado.linhas_impala, "linhas_sistema": resultado.linhas_sistema,
            "diferencas": resultado.diferencas, "duplicadas_impala": resultado.duplicadas_impala}}


def _mtime(caminho):
    try:
        return caminho.stat().st_mtime if caminho else None
    except FileNotFoundError:
        return None


def main():
    import argparse

    from .gateway import AplicacaoGateway, ClienteHue, ErroHue
    from .repositorio import CatalogoIndicadores

    parser = argparse.ArgumentParser(description="Consulta as tabelas do catálogo no Impala e grava em Dados/tabelas_impala")
    parser.add_argument("--indicador", nargs="+", metavar="ID", help="só estes indicadores (padrão: todos)")
    parser.add_argument("--database", default=config.HUE_BANCO_IMPALA)
    parser.add_argument("--pasta", type=Path, default=config.TABELAS_IMPALA_DIR, help="pasta de destino dos JSON")
    args = parser.parse_args()

    catalogo = CatalogoIndicadores(config.ARQUIVO_INDICADORES, config.TABELAS_DIR)
    repositorio = RepositorioImpala(args.pasta)
    gateway = AplicacaoGateway(ClienteHue(config.HUE_URL, config.HUE_USUARIO, config.HUE_SENHA),
                               config.HUE_DIALETO_PADRAO, args.database, tempo_maximo=config.HUE_TEMPO_MAXIMO,
                               repositorio_impala=repositorio)
    comparador = ComparadorIndicadores(catalogo, repositorio)
    indicadores = [i for i in catalogo.todos() if not args.indicador or str(i.id) in args.indicador]
    feitas = {}
    for indicador in indicadores:
        tabela = tabela_impala(indicador)
        if tabela is None:
            print(f"{indicador.id:>3}  sem tabela no catálogo")
            continue
        if tabela not in feitas:
            try:
                documento = gateway.atualizar_tabela(tabela, args.database)
                feitas[tabela] = f"{documento['total']} linhas"
            except ErroHue as exc:
                feitas[tabela] = f"ERRO {exc.status}: {str(exc)[:150]}"
        situacao = comparador.situacao(indicador)
        print(f"{indicador.id:>3}  {tabela}  [{feitas[tabela]}]  sistema: {situacao['sistema']['status']}"
              + (f" - {situacao['sistema']['motivo']}" if situacao['sistema'].get('motivo') else ""))


if __name__ == "__main__":
    main()
