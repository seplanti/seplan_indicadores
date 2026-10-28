"""Conversão de CSV exportado do Impala/Databricks para o JSON da pasta tabelas_bi.

Dados por município: o CSV traz o código IBGE na coluna `id_municipio`, `codigo`,
`codigo_ibge`, `cod_munic`, `cod__municipio`, `co_municipio`, `cd_mun` ou `municipio` (aceita "4209508.0" e o código de 6 dígitos, sem o dígito verificador); cada
registro recebe o nome do município e a FECAM a partir de Dados/municipios_sc.json, e as
colunas fecam/municipio do CSV, se houver, são descartadas. Linhas sem código (rodapés como
"NULL" ou "OBS: ...") são ignoradas.

Dados por FECAM: sem coluna de código, mas com a coluna `fecam`; o nome é padronizado
pela grafia de municipios_sc.json e a linha "SC" (ou "Santa Catarina") é o total do estado
(abrangencia "Estado"). Linhas de outras UFs ou do Brasil, usadas para comparação, recebem
abrangencia "UF" ou "País".

Com --colunas-por-ano, colunas como `esperanca_de_vida_1991`, `esperanca_de_vida_2000` viram
uma linha por ano, com a coluna `ano` e a coluna `esperanca_de_vida`.

Em ambos, valores NULL viram null, números inteiros perdem o ".0" e as colunas de controle
da carga (write_*) são descartadas.

Uso:  python -m indicadores.importacao <arquivo.csv> <nome_destino.json>
          [--ano 2024] [--somente-sc] [--colunas-por-ano] [--descartar coluna ...]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config
from .repositorio import carregar_json

# "municipio" fica depois dos demais porque, em alguns CSVs, traz o nome e não o código
COLUNAS_CODIGO = ("id_municipio", "codigo", "codigo_ibge", "cod_munic", "cod__municipio", "co_municipio", "cd_mun",
                  "municipio")
COLUNAS_PREENCHIDAS = ("fecam", "municipio", "codigo_ibge")  # vêm de municipios_sc.json
COLUNA_COM_ANO = re.compile(r"^(?P<base>.+)_(?P<ano>(19|20)\d{2})$")
COLUNA_FECAM = "fecam"
COLUNA_ANO = "ano"
FECAM_ESTADO = "SC"
NOMES_ESTADO = ("SC", "SANTA CATARINA")
COMPARACOES = {"BRASIL": "País"}  # demais nomes conhecidos abaixo são UFs
UFS = ("Acre", "Alagoas", "Amapá", "Amazonas", "Bahia", "Ceará", "Distrito Federal", "Espírito Santo",
       "Goiás", "Maranhão", "Mato Grosso", "Mato Grosso do Sul", "Minas Gerais", "Pará", "Paraíba",
       "Paraná", "Pernambuco", "Piauí", "Rio de Janeiro", "Rio Grande do Norte", "Rio Grande do Sul",
       "Rondônia", "Roraima", "São Paulo", "Sergipe", "Tocantins")
GRAFIAS_ALTERNATIVAS = {"AMONOROESTE": "AMNOROESTE"}
ORDEM_ABRANGENCIA = {"FECAM": 0, "Estado": 1, "UF": 2, "País": 3}
COLUNAS_DESCARTADAS = ("write_date", "write_time")
NULOS = ("", "NULL", "null", "None")


def converter_valor(texto):
    """'2718.0' -> 2718, '1.5' -> 1.5, 'NULL' -> None; demais textos ficam como estão."""
    if texto is None or texto.strip() in NULOS:
        return None
    try:
        numero = float(texto)
    except ValueError:
        return texto
    return int(numero) if numero.is_integer() else numero


def normalizar_codigo(texto):
    """'4209508.0' -> '4209508'; None se o valor não for um código numérico."""
    valor = converter_valor(texto)
    return str(valor) if isinstance(valor, int) else None


def expandir_colunas_por_ano(linhas):
    """{"x": 1, "v_2000": 5, "v_2010": 7} -> {"x": 1, "ano": "2000", "v": 5}, {"x": 1, "ano": "2010", "v": 7}."""
    for linha in linhas:
        fixas = {c: v for c, v in linha.items() if not COLUNA_COM_ANO.match(c)}
        por_ano = {}
        for coluna, valor in linha.items():
            if m := COLUNA_COM_ANO.match(coluna):
                por_ano.setdefault(m["ano"], {})[m["base"]] = valor
        for ano in sorted(por_ano):
            yield fixas | {COLUNA_ANO: ano} | por_ano[ano]


@dataclass
class Importacao:
    registros: list = field(default_factory=list)
    ignoradas: int = 0  # linhas sem código de município ou, com somente_sc, de outros estados


def converter_registros(linhas, municipios, ano=None, somente_sc=False, descartar=(), colunas_por_ano=False):
    """linhas: dicts do csv.DictReader; municipios: {codigo_ibge: {"municipio", "fecam"}}.

    ano: usado quando o CSV não tem a coluna `ano`.
    somente_sc: ignora códigos fora de municipios_sc.json em vez de falhar.
    colunas_por_ano: transforma colunas com sufixo _AAAA em uma linha por ano.
    """
    resultado = Importacao()
    linhas = iter(expandir_colunas_por_ano(linhas) if colunas_por_ano else linhas)
    sem_digito = {c[:6]: c for c in municipios}
    coluna_codigo = None
    for linha in linhas:
        if coluna_codigo is None:
            coluna_codigo = next((c for c in COLUNAS_CODIGO if c in linha), None)
            if coluna_codigo is None:
                if COLUNA_FECAM in linha:
                    return converter_registros_fecam([linha, *linhas], municipios, ano, descartar)
                raise ValueError(f"CSV sem coluna de município ({' ou '.join(COLUNAS_CODIGO)}) nem de FECAM")
        codigo = normalizar_codigo(linha[coluna_codigo])
        if codigo is not None and len(codigo) == 6:
            codigo = sem_digito.get(codigo, codigo)
        if codigo is None or (somente_sc and codigo not in municipios):
            resultado.ignoradas += 1
            continue
        if codigo not in municipios:
            raise ValueError(f"Código IBGE sem cadastro em {config.ARQUIVO_MUNICIPIOS.name}: {codigo}")
        fora = {coluna_codigo, COLUNA_ANO, *COLUNAS_PREENCHIDAS, *COLUNAS_DESCARTADAS, *descartar}
        metricas = {c: converter_valor(v) for c, v in linha.items() if c not in fora}
        ano_linha = converter_valor(linha[COLUNA_ANO]) if COLUNA_ANO in linha else ano
        registro = {"id": len(resultado.registros) + 1}
        if ano_linha is not None:
            registro["ano"] = ano_linha
        resultado.registros.append(registro | {
            "fecam": municipios[codigo]["fecam"],
            "municipio": municipios[codigo]["municipio"],
            "codigo_ibge": codigo,
            **metricas,
        })
    return resultado


def converter_registros_fecam(linhas, municipios, ano=None, descartar=()):
    """CSV agregado por FECAM. A linha "SC" é o total do estado.

    Os registros saem ordenados por FECAM e ano (depois o total do estado e as linhas de
    comparação), independentemente da ordem do CSV.
    """
    grafias = {m["fecam"].upper(): m["fecam"] for m in municipios.values()}
    comparacoes = COMPARACOES | {uf.upper(): "UF" for uf in UFS}
    nomes_comparacao = {"BRASIL": "Brasil"} | {uf.upper(): uf for uf in UFS}
    resultado = Importacao()
    fora = {COLUNA_FECAM, COLUNA_ANO, *COLUNAS_DESCARTADAS, *descartar}
    for linha in linhas:
        nome = (linha[COLUNA_FECAM] or "").strip()
        if nome.upper() in NULOS or not nome:
            resultado.ignoradas += 1
            continue
        chave = GRAFIAS_ALTERNATIVAS.get(nome.upper(), nome.upper())
        if chave in NOMES_ESTADO:
            fecam, abrangencia = FECAM_ESTADO, "Estado"
        elif chave in grafias:
            fecam, abrangencia = grafias[chave], "FECAM"
        elif chave in comparacoes:
            fecam, abrangencia = nomes_comparacao[chave], comparacoes[chave]
        else:
            raise ValueError(f"FECAM sem cadastro em {config.ARQUIVO_MUNICIPIOS.name}: {nome}")
        ano_linha = converter_valor(linha[COLUNA_ANO]) if COLUNA_ANO in linha else ano
        registro = {} if ano_linha is None else {"ano": ano_linha}
        resultado.registros.append(registro | {
            "fecam": fecam,
            "abrangencia": abrangencia,
            **{c: converter_valor(v) for c, v in linha.items() if c not in fora},
        })
    resultado.registros.sort(key=lambda r: (ORDEM_ABRANGENCIA[r["abrangencia"]], r["fecam"].upper(), r.get("ano") or 0))
    resultado.registros = [{"id": i} | r for i, r in enumerate(resultado.registros, start=1)]
    return resultado


def importar_csv(origem: Path, destino: Path, arquivo_municipios: Path = config.ARQUIVO_MUNICIPIOS, **opcoes):
    municipios = {m["codigo_ibge"]: m for m in carregar_json(arquivo_municipios)}
    with open(origem, encoding="utf-8-sig", newline="") as f:
        resultado = converter_registros(csv.DictReader(f), municipios, **opcoes)
    destino.write_text(json.dumps(resultado.registros, ensure_ascii=False, indent=1), encoding="utf-8")
    return resultado


def main():
    parser = argparse.ArgumentParser(description="Converte CSV do Impala para Dados/tabelas_bi")
    parser.add_argument("csv", type=Path)
    parser.add_argument("destino", help="nome do arquivo JSON em Dados/tabelas_bi")
    parser.add_argument("--ano", type=int, help="ano dos dados, se o CSV não tiver a coluna 'ano'")
    parser.add_argument("--somente-sc", action="store_true",
                        help="ignora municípios fora de Santa Catarina (CSV com dados do Brasil)")
    parser.add_argument("--colunas-por-ano", action="store_true",
                        help="colunas com sufixo _AAAA (ex.: valor_2010) viram uma linha por ano")
    parser.add_argument("--descartar", nargs="+", default=(), metavar="COLUNA",
                        help="colunas do CSV que não vão para o JSON")
    args = parser.parse_args()
    destino = config.TABELAS_DIR / args.destino
    resultado = importar_csv(args.csv, destino, ano=args.ano, somente_sc=args.somente_sc, descartar=args.descartar,
                             colunas_por_ano=args.colunas_por_ano)
    print(f"{len(resultado.registros)} registros gravados em {destino} ({resultado.ignoradas} linhas ignoradas)")


if __name__ == "__main__":
    main()
