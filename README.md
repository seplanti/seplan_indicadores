# seplan_indicadores
Módulo para verificação e atualização de indicadores (versão preliminar).

Interface em React com back-end Python que serve uma API REST/JSON. Nesta versão
não há banco de dados, autenticação, DVC nem Vault: os dados vêm dos arquivos JSON
da pasta `Dados/`.

## Executar

```
python app.py [--porta 8000] [--sem-navegador]
```

Requer apenas Python 3.10+ (sem dependências externas). React, htm e Bootstrap
já estão em `web/vendor/`; não é preciso Node nem etapa de build.

No VS Code, use as configurações de `.vscode/launch.json` (Ctrl+Shift+D, F5).

## Telas

- **Painel** (`/`): todos os indicadores, com a tag de situação (Atualizado /
  Desatualizado), filtros por texto, eixo e situação, e ordenação por coluna.
  O nome da fonte aparece em vermelho quando os dados do indicador estão desatualizados.
- **Dados do indicador** (`/indicadores/<id>`): ficha técnica, estatísticas e a
  tabela de `Dados/tabelas_bi`, com filtro por FECAM. Séries históricas ganham um
  filtro de ano (abre no ano mais recente) e as estatísticas são calculadas por ano.
- **Notificações** (botão no topo de todas as telas): lista os indicadores desatualizados.

## Situação de atualização

Todo indicador é considerado **Atualizado** por padrão. Para marcar um como
desatualizado, inclua-o em `Dados/status_indicadores.json` (o arquivo é relido
sem reiniciar o app):

```json
{
  "indicadores": {
    "2": {"status": "DESATUALIZADO", "motivo": "Nova publicação do Censo não coletada.", "desde": "2026-10-20"}
  }
}
```

A chave é o `id` do indicador no catálogo. `motivo` e `desde` são opcionais.

## Importar dados do Impala/Databricks (CSV)

```
python -m indicadores.importacao <arquivo.csv> <nome_destino.json> [--ano 2024] [--somente-sc] [--descartar coluna ...]
```

Grava o JSON em `Dados/tabelas_bi`. O CSV deve ter o código IBGE do município na
coluna `municipio` ou `cd_mun` (aceita `4209508.0`); as demais colunas viram colunas
de dados (`write_date`/`write_time` são descartadas, `NULL` vira `null`) e linhas sem
código (rodapés `NULL`/`OBS: ...`) são ignoradas. Nome e FECAM de cada município vêm de
`Dados/municipios_sc.json`.

CSVs agregados por FECAM (coluna `fecam`, sem código de município) também são aceitos:
o nome da FECAM é padronizado pela grafia de `municipios_sc.json` e a linha `SC` vira o
total do estado (`abrangencia: "Estado"`). Na tela, esse total aparece num cartão próprio
e fica fora da média, do maior e do menor. Em séries com projeção, a tela abre no último
ano com dado observado, e nos anos projetados as estatísticas usam a primeira coluna com dados.

- `--ano`: ano dos dados quando o CSV não tem a coluna `ano`.
- `--somente-sc`: para CSVs com todos os municípios do Brasil; mantém só os de SC.
  Sem essa opção, um código fora de SC é erro.
- `--descartar`: colunas redundantes que não devem ir para o JSON.

Exemplos usados nos dados atuais:

```
python -m indicadores.importacao query-impala-318538.csv emprego_renda_hab_asssoc_bronze_censo_habitacional_consolidado.json
python -m indicadores.importacao infraestrutura_bronze_area_municipal.csv infraestrutura_bronze_tl_area_municipal.json --ano 2024 --somente-sc --descartar cd_uf nm_uf nm_uf_sigla nm_mun
python -m indicadores.importacao Taxa_de_participacao_cultura_emprego.csv turismo_gold_taxa_de_participacao_da_cultura_no_emprego_projecao.json
python -m indicadores.importacao empregos_economia_criativa_sebrae.csv emprego_renda_hab_asssoc_gold_tl_empregos_economia_criativa_sebrae.json --descartar trajetoria_suavizada intervalo_de_confianca_mais intervalo_de_confianca_menos
```

Tabelas por FECAM saem ordenadas por FECAM e ano (total do estado por último), qualquer
que seja a ordem das linhas no CSV. O nome do destino deve corresponder ao
`link_do_arquivo_json` do indicador no catálogo, com `_` no lugar de `.`
(ex.: `tabelas_bi/a.b.c.json` → `a_b_c.json`).

## API

| Rota | Retorno |
|---|---|
| `GET /api/indicadores` | catálogo com `tem_dados` e `situacao` de cada indicador |
| `GET /api/indicadores/<id>/dados` | ficha do indicador e sua tabela (`tabela: null` se não houver arquivo) |
| `GET /api/indicadores/<id>/json` | arquivo JSON bruto da tabela_bi |
| `GET /api/notificacoes` | uma notificação por indicador desatualizado |

## Testes

```
python -m unittest discover -s tests
```

## Estrutura

```
app.py                  ponto de entrada (argumentos, servidor, abre o Chrome)
indicadores/            back-end
  config.py             caminhos e constantes
  modelos.py            Indicador, SituacaoIndicador, TabelaDados, Estatisticas
  repositorio.py        CatalogoIndicadores, RegistroStatus (leitura dos JSON)
  api.py                ConsultaIndicadores (monta as respostas da API)
  importacao.py         conversão de CSV do Impala para tabelas_bi
  servidor.py           Aplicacao (rotas /api), ArquivosEstaticos, Servidor
  navegador.py          abertura no Chrome
web/                    front-end React
  index.html            carrega React, htm e Bootstrap de web/vendor
  js/main.js, app.js    inicialização e rotas das telas
  js/paginas/           Painel, DadosIndicador
  js/componentes/       Cabecalho, Notificacoes, StatusTag, TabelaOrdenavel, Comuns
  css/app.css           ajustes sobre o Bootstrap
Dados/                  catálogo, status_indicadores.json, municipios_sc.json e tabelas_bi
tests/                  testes unitários
```

Os componentes usam `html\`...\`` (biblioteca htm) no lugar de JSX, para rodar
direto no navegador sem compilação. Para criar uma tela nova: crie o componente
em `web/js/paginas/` e inclua a rota em `telaDa()` no `web/js/app.js`.
