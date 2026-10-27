"""Serviço de consulta usado pela API REST/JSON: monta os dicionários que a interface React consome."""

from __future__ import annotations

from dataclasses import asdict

from .repositorio import CatalogoIndicadores, RegistroStatus

CATEGORIA_SEM_DADOS = "SEM_DADOS"


class ConsultaIndicadores:
    def __init__(self, catalogo: CatalogoIndicadores, status: RegistroStatus):
        self.catalogo = catalogo
        self.status = status

    def _resumo(self, indicador):
        tem_dados = self.catalogo.tem_dados(indicador)
        situacao = self.status.situacao(indicador)
        return indicador.para_dict() | {
            "tem_dados": tem_dados,
            "situacao": situacao.para_dict(),
            # Grupo da tela inicial: sem arquivo de dados prevalece sobre a situação de atualização.
            "categoria": situacao.status.value if tem_dados else CATEGORIA_SEM_DADOS,
        }

    def listar(self):
        return {
            "arquivo": self.catalogo.arquivo.name,
            "indicadores": [self._resumo(i) for i in self.catalogo.todos()],
        }

    def dados(self, id_indicador):
        """Ficha do indicador e sua tabela (None se o indicador não tem versão publicada)."""
        indicador = self.catalogo.buscar(id_indicador)
        if indicador is None:
            return None
        tabela = self.catalogo.carregar_tabela(indicador)
        if tabela is not None:
            tabela = {
                "arquivo": tabela.arquivo.name,
                "colunas": tabela.colunas,
                "colunas_numericas": tabela.colunas_numericas,
                "anos": tabela.anos,
                "ano_referencia": tabela.ano_referencia,
                "registros": tabela.registros,
                "estatisticas": self._estatisticas(tabela),
            }
        return {"indicador": self._resumo(indicador), "tabela": tabela}

    @staticmethod
    def _estatisticas(tabela):
        """Estatísticas da tabela inteira ("todos") e de cada ano, para não misturar anos."""
        def resumo(t):
            est = t.estatisticas()
            return asdict(est) if est else None
        return {"todos": resumo(tabela)} | {str(ano): resumo(tabela.do_ano(ano)) for ano in tabela.anos}

    def arquivo_json(self, id_indicador):
        indicador = self.catalogo.buscar(id_indicador)
        return indicador and self.catalogo.localizar_arquivo(indicador)

    def notificacoes(self):
        """Uma notificação por indicador com dados desatualizados."""
        avisos = []
        for indicador in self.catalogo.todos():
            situacao = self.status.situacao(indicador)
            if situacao.atualizado:
                continue
            avisos.append({
                "id": f"desatualizado-{indicador.id}",
                "categoria": "ATRASO",
                "indicador_id": indicador.id,
                "indicador": indicador.nome,
                "fonte": indicador.fonte,
                "mensagem": situacao.motivo or f"Os dados da fonte {indicador.fonte or 'informada'} estão desatualizados.",
                "desde": situacao.desde,
            })
        return {"notificacoes": avisos}
