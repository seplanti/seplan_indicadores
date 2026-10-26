"""Modelos de domínio: indicadores do catálogo, situação de atualização e tabelas de dados."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from functools import cached_property
from pathlib import Path


class StatusAtualizacao(str, Enum):
    ATUALIZADO = "ATUALIZADO"
    DESATUALIZADO = "DESATUALIZADO"


@dataclass(frozen=True)
class SituacaoIndicador:
    """Situação de atualização de um indicador. Por padrão, atualizado."""

    status: StatusAtualizacao = StatusAtualizacao.ATUALIZADO
    motivo: str | None = None
    desde: str | None = None

    @classmethod
    def de_dict(cls, dados):
        status = StatusAtualizacao(str(dados.get("status", StatusAtualizacao.ATUALIZADO.value)).upper())
        return cls(status, dados.get("motivo"), dados.get("desde"))

    @property
    def atualizado(self):
        return self.status is StatusAtualizacao.ATUALIZADO

    def para_dict(self):
        return {"status": self.status.value, "motivo": self.motivo, "desde": self.desde}


@dataclass(frozen=True)
class Indicador:
    """Um registro do catálogo dados_de_base_indicadores-v5.json."""

    id: int
    eixo: str | None = None
    nome: str | None = None
    descricao: str | None = None
    formula: str | None = None
    unidade: str | None = None
    fonte: str | None = None
    temporalidade: str | None = None
    link_fonte: str | None = None
    link_fonte_2: str | None = None
    tabela_databricks: str | None = None
    link_arquivo_json: str | None = None

    # Nome do campo no JSON -> atributo
    CAMPOS_JSON = {
        "id": "id",
        "bloco_eixo": "eixo",
        "indicador": "nome",
        "descricao": "descricao",
        "formula_de_calculo": "formula",
        "unidade_de_medida": "unidade",
        "fonte_dos_dados": "fonte",
        "temporalidade": "temporalidade",
        "link_da_fonte_publico": "link_fonte",
        "link_da_fonte_publico_2": "link_fonte_2",
        "tabela_databricks": "tabela_databricks",
        "link_do_arquivo_json": "link_arquivo_json",
    }

    @classmethod
    def de_dict(cls, dados):
        return cls(**{attr: dados.get(campo) for campo, attr in cls.CAMPOS_JSON.items()})

    def fontes_publicas(self):
        """Links públicos válidos (http/https) da fonte dos dados."""
        return [u for u in (self.link_fonte, self.link_fonte_2) if u and str(u).startswith("http")]

    def para_dict(self):
        return asdict(self) | {"fontes_publicas": self.fontes_publicas()}


@dataclass(frozen=True)
class Estatisticas:
    """Resumo da primeira coluna numérica com dados de uma tabela."""

    coluna: str
    total: int
    media: float
    maior: object
    rotulo_maior: object
    menor: object
    rotulo_menor: object
    valor_estado: object = None  # valor da linha de total do estado, quando há uma só


class TabelaDados:
    """Registros de um arquivo JSON da pasta tabelas_bi.

    Tabelas por FECAM podem ter uma linha de total do estado (abrangencia "Estado");
    ela fica fora da média, do maior e do menor, e aparece em `valor_estado`.
    """

    COLUNAS_NAO_METRICAS = ("id", "ano")
    COLUNA_ANO = "ano"
    COLUNAS_ROTULO = ("municipio", "fecam")
    COLUNA_ABRANGENCIA = "abrangencia"
    ABRANGENCIA_ESTADO = "Estado"

    def __init__(self, registros, arquivo: Path | None = None):
        self.registros = registros
        self.arquivo = arquivo

    def __len__(self):
        return len(self.registros)

    @cached_property
    def colunas(self):
        """Todas as colunas, na ordem em que aparecem nos registros."""
        return list(dict.fromkeys(k for r in self.registros for k in r))

    @cached_property
    def colunas_numericas(self):
        """Colunas cujos valores preenchidos são todos numéricos (exceto id/ano)."""
        return [c for c in self.colunas
                if c not in self.COLUNAS_NAO_METRICAS
                and all(isinstance(r.get(c), (int, float)) for r in self.registros if r.get(c) is not None)]

    def tem_coluna(self, coluna):
        return coluna in self.colunas

    def indice(self, coluna):
        return self.colunas.index(coluna)

    def valores_distintos(self, coluna):
        return sorted({str(r.get(coluna) or "") for r in self.registros})

    @cached_property
    def anos(self):
        """Anos presentes na tabela, em ordem crescente (vazio se não há coluna de ano)."""
        return sorted({r[self.COLUNA_ANO] for r in self.registros if r.get(self.COLUNA_ANO) is not None})

    def do_ano(self, ano):
        """Nova tabela só com os registros do ano informado."""
        return TabelaDados([r for r in self.registros if r.get(self.COLUNA_ANO) == ano], self.arquivo)

    def _eh_estado(self, registro):
        return registro.get(self.COLUNA_ABRANGENCIA) == self.ABRANGENCIA_ESTADO

    def _coluna_com_dados(self, registros):
        """Primeira coluna numérica preenchida em algum dos registros (ex.: a projeção,
        nos anos em que a série observada está vazia)."""
        return next((c for c in self.colunas_numericas if any(r.get(c) is not None for r in registros)), None)

    @cached_property
    def ano_referencia(self):
        """Último ano com dado na primeira coluna numérica (o observado, não a projeção)."""
        if not self.colunas_numericas:
            return None
        col = self.colunas_numericas[0]
        return max((r[self.COLUNA_ANO] for r in self.registros
                    if r.get(col) is not None and r.get(self.COLUNA_ANO) is not None), default=None)

    def estatisticas(self):
        """Estatísticas da primeira coluna numérica com dados, ou None se não houver."""
        registros = [r for r in self.registros if not self._eh_estado(r)]
        col = self._coluna_com_dados(registros)
        if col is None:
            return None
        preenchidos = [r for r in registros if r.get(col) is not None]
        rotulo = next((c for c in self.COLUNAS_ROTULO if self.tem_coluna(c)), self.colunas[0])
        maior = max(preenchidos, key=lambda r: r[col])
        menor = min(preenchidos, key=lambda r: r[col])
        estado = [r for r in self.registros if self._eh_estado(r)]
        return Estatisticas(
            coluna=col,
            total=len(registros),
            media=sum(r[col] for r in preenchidos) / len(preenchidos),
            maior=maior[col], rotulo_maior=maior.get(rotulo),
            menor=menor[col], rotulo_menor=menor.get(rotulo),
            valor_estado=estado[0].get(col) if len(estado) == 1 else None,
        )
