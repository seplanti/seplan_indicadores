"""Back-end do Seplan Indicadores (API REST/JSON consumida pela interface React em web/).

Camadas:
    config       caminhos e constantes do projeto
    modelos      Indicador, SituacaoIndicador e TabelaDados (dados e regras)
    repositorio  CatalogoIndicadores e RegistroStatus (leitura dos arquivos JSON)
    api          ConsultaIndicadores (monta as respostas da API)
    servidor     roteamento (Aplicacao), arquivos estáticos e servidor HTTP
    navegador    abertura do app no Chrome
"""
