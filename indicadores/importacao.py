"""Conversão de CSV exportado do Impala/Databricks para o JSON da pasta tabelas_bi.

Dados por município: o CSV traz o código IBGE na coluna `municipio` ou `cd_mun` (aceita
"4209508.0"); cada registro recebe o nome do município e a FECAM a partir de
Dados/municipios_sc.json. Linhas sem código (rodapés como "NULL" ou "OBS: ...") são ignoradas.

Dados por FECAM: sem coluna de código, mas com a coluna `fecam`; o nome é padronizado
pela grafia de municipios_sc.json e a linha "SC" é o total do estado (abrangencia "Estado").

Em ambos, valores NULL viram null, números inteiros perdem o ".0" e as colunas de controle
da carga (write_*) são descartadas.

Uso:  python -m indicadores.importacao <arquivo.csv> <nome_destino.json>
          [--ano 2024] [--somente-sc] [--descartar coluna ...]
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import config
from .repositorio import carregar_json

COLUNAS_CODIGO = ("municipio", "cd_mun")
COLUNA_FECAM = "fecam"
COLUNA_ANO = "ano"
FECAM_ESTADO = "SC"
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


@dataclass
class Importacao:
    registros: list = field(default_factory=list)
    ignoradas: int = 0  # linhas sem código de município ou, com somente_sc, de outros estados


def converter_registros(linhas, municipios, ano=None, somente_sc=False, descartar=()):
    """linhas: dicts do csv.DictReader; municipios: {codigo_ibge: {"municipio", "fecam"}}.

    ano: usado quando o CSV não tem a coluna `ano`.
    somente_sc: ignora códigos fora de municipios_sc.json em vez de falhar.
    """
    resultado = Importacao()
    coluna_codigo = None
    for linha in linhas:
        if coluna_codigo is None:
            coluna_codigo = next((c for c in COLUNAS_CODIGO if c in linha), None)
            if coluna_codigo is None:
                if COLUNA_FECAM in linha:
                    return converter_registros_fecam([linha, *linhas], municipios, ano, descartar)
                raise ValueError(f"CSV sem coluna de município ({' ou '.join(COLUNAS_CODIGO)}) nem de FECAM")
        codigo = normalizar_codigo(linha[coluna_codigo])
        if codigo is None or (somente_sc and codigo not in municipios):
            resultado.ignoradas += 1
            continue
        if codigo not in municipios:
            raise ValueError(f"Código IBGE sem cadastro em {config.ARQUIVO_MUNICIPIOS.name}: {codigo}")
        fora = {coluna_codigo, COLUNA_ANO, *COLUNAS_DESCARTADAS, *descartar}
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

    Os registros saem ordenados por FECAM e ano (o total do estado por último),
    independentemente da ordem do CSV.
    """
    grafias = {m["fecam"].upper(): m["fecam"] for m in municipios.values()}
    resultado = Importacao()
    fora = {COLUNA_FECAM, COLUNA_ANO, *COLUNAS_DESCARTADAS, *descartar}
    for linha in linhas:
        nome = (linha[COLUNA_FECAM] or "").strip()
        if nome.upper() in NULOS or not nome:
            resultado.ignoradas += 1
            continue
        if nome.upper() == FECAM_ESTADO:
            fecam, abrangencia = FECAM_ESTADO, "Estado"
        elif nome.upper() in grafias:
            fecam, abrangencia = grafias[nome.upper()], "FECAM"
        else:
            raise ValueError(f"FECAM sem cadastro em {config.ARQUIVO_MUNICIPIOS.name}: {nome}")
        ano_linha = converter_valor(linha[COLUNA_ANO]) if COLUNA_ANO in linha else ano
        registro = {} if ano_linha is None else {"ano": ano_linha}
        resultado.registros.append(registro | {
            "fecam": fecam,
            "abrangencia": abrangencia,
            **{c: converter_valor(v) for c, v in linha.items() if c not in fora},
        })
    resultado.registros.sort(key=lambda r: (r["abrangencia"] == "Estado", r["fecam"].upper(), r.get("ano") or 0))
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
    parser.add_argument("--descartar", nargs="+", default=(), metavar="COLUNA",
                        help="colunas do CSV que não vão para o JSON")
    args = parser.parse_args()
    destino = config.TABELAS_DIR / args.destino
    resultado = importar_csv(args.csv, destino, ano=args.ano, somente_sc=args.somente_sc, descartar=args.descartar)
    print(f"{len(resultado.registros)} registros gravados em {destino} ({resultado.ignoradas} linhas ignoradas)")


if __name__ == "__main__":
    main()
