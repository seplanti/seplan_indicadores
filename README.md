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

- **Início** (`/`): quantos indicadores estão atualizados, desatualizados e sem dados
  (sem arquivo em `Dados/tabelas_bi`), com a lista de cada grupo e o botão que abre o painel.
  Um indicador sem arquivo conta como "Sem dados" mesmo que esteja marcado como
  desatualizado, de modo que os três grupos somam o total do catálogo.
- **Painel** (`/painel`): todos os indicadores, com a tag de situação (Atualizado /
  Desatualizado / Sem dados), filtros por texto, eixo e situação, e ordenação por coluna.
  O nome da fonte aparece em vermelho quando os dados do indicador estão desatualizados.
- **Dados do indicador** (`/indicadores/<id>`): ficha técnica, estatísticas e a
  tabela de `Dados/tabelas_bi`, com filtro por FECAM. Séries históricas ganham um
  filtro de ano (abre no ano mais recente) e as estatísticas são calculadas por ano.
- **Consulta ao Impala** (`/indicadores/<id>/impala`): aberta pelo botão **Consultar Impala** de cada linha do
  painel (que consulta a tabela do indicador no Impala ao abrir) ou por **Ver última consulta**. Mostra as tags
  Impala/Sistema, o SQL, a data e o total de linhas, e os dados em **Tabela** (ordenável) ou **JSON** (botão
  copiar e link para o JSON bruto completo; na tela, até 1.000 linhas), com busca. Aceita `?modo=json` ou
  `?modo=tabela` na URL; sem isso, lembra a última escolha.
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

## Gateway do Hue (Impala/HDFS)

O próprio painel (`python app.py`, porta 8000) atende as rotas abaixo e repassa para a
API v1 do Hue (`https://boavista-dados.ciasc.sc.gov.br`), cuidando do token JWT sozinho.
Copie `.env.exemplo` para `.env` (ignorado pelo git) e preencha `HUE_USUARIO` e `HUE_SENHA`;
sem isso as rotas respondem 503. Alternativa sem senha em arquivo: envie o header
`Authorization: Bearer <access_token>` (o token de `/api/v1/token/auth/` do Hue), que é repassado ao Hue
e tem prioridade sobre o `.env`. `HUE_BANCO` é o banco usado quando o corpo não traz `database`.

Para rodar o Hue separado do painel há também `python gateway.py` (porta 8001), com as mesmas rotas.

| Método | Rota | Hue |
|---|---|---|
| POST | `/api/queries` com `{"statement": "SHOW TABLES", "dialect": "impala", "database": "seplan_avancasc"}` → `{"id": ...}` | `editor/execute/<dialeto>` |
| GET | `/api/queries/<id>/status` | `editor/check_status` |
| GET | `/api/queries/<id>/results?rows=100` | `editor/fetch_result_data` |
| GET | `/api/files?path=/user/<usuario>` | `storage/view=<caminho>` |
| GET | `/api/tabelas?database=<banco>` | `SHOW TABLES IN <banco>` |
| GET | `/api/tabelas/<tabela>?database=<banco>&limit=100&colunas=a,b` | `SELECT a, b FROM <banco>.<tabela> LIMIT 100` |
| GET | `/api/queries/<id>/logs` | `editor/get_logs` |
| GET | `/api/consultas` | lista as 75 consultas nomeadas de `Dados/hue_endpoints.json` |
| GET | `/api/consultas/<nome>?limit=100&database=<banco>&colunas=a,b` | `SELECT` na tabela da consulta (ex.: `consultar_ice_emprego` ou só `ice_emprego`) |
| GET | `/api/bancos?dialect=impala` | `editor/autocomplete` |
| GET | `/api/hue/config`, `/api/hue/historico`, `/api/hue/conectores`, `/api/hue/filesystems` | `get_config`, `get_history`, `connector/types`, `storage/filesystems` |

As rotas `/api/tabelas` fazem o ciclo execute → check_status → fetch_result_data numa só chamada e
devolvem `{"sql", "columns", "total", "rows": [{coluna: valor}], "has_more"}`. Banco, tabela e colunas só
aceitam letras, números e `_` (400 caso contrário); tabela inexistente dá 404 e falta de permissão no Ranger, 403.
`limit` vai de 1 a `HUE_LIMITE_MAXIMO` (10000) e a espera pela consulta é de até `HUE_TEMPO_MAXIMO` (120 s, depois 504).
A maioria das tabelas está em `seplan_avancasc_stage`.

`Dados/hue_endpoints.json` reúne as definições (ambiente do Insomnia, sem senha nem tokens), os apelidos
`tb_*` → nome da tabela no Impala e todos os endpoints do Hue e do gateway, com URLs na sintaxe
`{{ _.variavel }}` do Insomnia. Em `/api/tabelas/<tabela>` vale tanto o nome real quanto o apelido
(`/api/tabelas/tb_ice_emprego`; `&` vai como `%26`: `tb_gastos_p%26d`). As consultas nomeadas usam por
padrão `database` e `limit` das definições (`seplan_avancasc_stage`, 100). Os 75 nomes de tabela foram
conferidos com `SHOW TABLES IN seplan_avancasc_stage` em 2026-11-06; as correções em relação ao PDF original
estão em `observacoes_tabelas` e `correcoes_em_relacao_ao_pdf`.

No Insomnia, `gateway_url` = `http://127.0.0.1:8000` (ou `:8001` se usar o `gateway.py` avulso).

## Comparação Impala × sistema (tabelas_impala × tabelas_bi)

As tabelas de `Dados/tabelas_bi` continuam sendo os dados do sistema (as rotas `/api/indicadores/...` não mudaram).
O resultado das consultas ao Impala fica separado, em `Dados/tabelas_impala/<tabela>.json` (um por tabela,
com `consultado_em`, `sql`, `columns` e `rows`), e é comparado com a tabela_bi equivalente do indicador
(`tabela_databricks` do catálogo com `_` no lugar de `.`, no banco `HUE_BANCO_IMPALA`, padrão `seplan_avancasc_stage`).

Cada indicador ganha no painel duas tags:

| Situação | Tags |
|---|---|
| Dados do sistema iguais à última consulta | `Atualizado/Impala` e `Atualizado/Sistema` |
| Dados diferentes, ou Impala com dados e sem arquivo em tabelas_bi | `Atualizado/Impala` e `Desatualizado/Sistema` |
| Impala ainda não consultado | `Sem consulta/Impala` e `Sem comparação/Sistema` |
| Consulta incompleta, tabela vazia ou sem colunas de dados em comum | `Atualizado/Impala` e `Sem comparação/Sistema` |

Quando o sistema difere do Impala, o indicador também passa a **Desatualizado** (situação, notificações e
tela inicial), com o motivo e a data da consulta; `status_indicadores.json` continua valendo para os demais casos.

A comparação passa as linhas do Impala pela mesma conversão do importador de CSV (nome e FECAM do município,
`NULL`, decimais) e compara nas colunas que as duas tabelas têm em comum (colunas descartadas na importação,
como `write_date` e `file_source`, não contam). Não importam a ordem das linhas, o `id`, maiúsculas/espaços nos
textos, linhas repetidas no Impala nem linhas sem nenhum valor (anos de projeção vazios). Tabelas_bi copiadas
direto do Impala, sem o importador, são comparadas linha a linha. O resultado é recalculado quando um dos dois
arquivos muda.

Como atualizar `tabelas_impala`:

- Botão **Consultar Impala** em cada linha do painel, que abre a tela da consulta, ou **Consultar Impala agora** na
  tela de dados do indicador (ambos usam `POST /api/tabelas/<tabela>/atualizar`).
- `POST /api/consultas/<nome>/atualizar` (consultas do `hue_endpoints.json`).
- Toda consulta `GET /api/tabelas/<tabela>` ou `/api/consultas/<nome>` que traga a tabela inteira (menos linhas que o
  `limit`, sem `colunas`) também é gravada; consultas cortadas pelo `limit` não são.
- Todas as tabelas do catálogo de uma vez: `python -m indicadores.impala [--indicador 7 10 ...]`, que mostra a
  situação de cada indicador ao final.

A atualização pede até `HUE_LIMITE_SINCRONIZACAO` linhas (padrão 100000). Tabelas maiores (ex.: frota de veículos do
Brasil) ficam como consulta incompleta, gravada só com os metadados, e não são comparadas.

Para atualizar o sistema depois de ver a diferença, gere de novo a tabela_bi pelo importador (seção abaixo).

## Importar dados do Impala/Databricks (CSV)

```
python -m indicadores.importacao <arquivo.csv> <nome_destino.json> [--ano 2024] [--somente-sc] [--colunas-por-ano] [--descartar coluna ...]
```

Grava o JSON em `Dados/tabelas_bi`. O CSV deve ter o código IBGE do município na
coluna `id_municipio`, `codigo`, `codigo_ibge`, `codigo_do_municipio`, `cod_munic`, `cod__municipio`, `co_municipio`, `cd_mun` ou `municipio`
(nessa ordem de preferência, porque `municipio` às vezes traz o nome; aceita `4209508.0` e o código de
6 dígitos, sem o dígito verificador); as demais colunas viram colunas de dados (as colunas
`fecam`/`municipio` do CSV são substituídas pelas de `municipios_sc.json`, `write_date`/`write_time`
são descartadas, `NULL` vira `null`, decimal com vírgula como `"68,61"` vira número). Se o código vier
`NULL` mas a coluna `municipio` trouxer o nome, o município é achado pelo nome (sem diferenciar acentos);
linhas sem código nem nome conhecido (rodapés `NULL`/`OBS: ...`) são ignoradas. Nome e FECAM de cada município vêm de
`Dados/municipios_sc.json`.

CSVs agregados por FECAM (coluna `fecam`, sem código de município) também são aceitos:
o nome da FECAM é padronizado pela grafia de `municipios_sc.json` e a linha `SC` (ou
`Santa Catarina`) vira o total do estado (`abrangencia: "Estado"`). Linhas de outras UFs
e do Brasil, usadas para comparação, viram `abrangencia: "UF"` ou `"País"`. Na tela, o
total do estado aparece num cartão próprio; ele e as linhas de comparação ficam fora da
média, do maior e do menor. Em séries com projeção, a tela abre no último ano com dado observado, e nos anos projetados as estatísticas usam a primeira coluna com dados.

- `--ano`: ano dos dados quando o CSV não tem a coluna `ano`.
- `--colunas-por-ano`: para CSVs com um ano por coluna (`valor_2000`, `valor_2010`);
  cada ano vira uma linha, com as colunas `ano` e `valor`.
- `--somente-sc`: para CSVs com todos os municípios do Brasil; mantém só os de SC.
  Sem essa opção, um código fora de SC é erro.
- `--descartar`: colunas redundantes que não devem ir para o JSON.

Exemplos usados nos dados atuais:

```
python -m indicadores.importacao query-impala-318538.csv emprego_renda_hab_asssoc_bronze_censo_habitacional_consolidado.json
python -m indicadores.importacao infraestrutura_bronze_area_municipal.csv infraestrutura_bronze_tl_area_municipal.json --ano 2024 --somente-sc --descartar cd_uf nm_uf nm_uf_sigla nm_mun
python -m indicadores.importacao Taxa_de_participacao_cultura_emprego.csv turismo_gold_taxa_de_participacao_da_cultura_no_emprego_projecao.json
python -m indicadores.importacao tl_percent_programas_habit.csv avancasc_assistencia_social_ouro_tl_percent_programas_habit.json --ano 2020
python -m indicadores.importacao id_graf_taxa_abandono_ensino_medio.csv avancasc_educacao_ouro_id_graf_taxa_abandono_ensino_medio.json --descartar file_source
python -m indicadores.importacao avancasc.saude_bronze.esperanca_vida_ao_nascer_planilha1.csv avancasc_saude_bronze_esperanca_vida_ao_nascer_planilha1.json --colunas-por-ano --descartar espacialidades
python -m indicadores.importacao avancasc.saneamento_ouro.indice_de_abastecimento_de_agua.csv avancasc_saneamento_ouro_indice_de_abastecimento_de_agua.json
python -m indicadores.importacao taxa_rdo_corrigido.csv avancasc_saneamento_bronze_taxa_rdo.json --descartar estado
python -m indicadores.importacao empregos_economia_criativa_sebrae.csv emprego_renda_hab_asssoc_gold_tl_empregos_economia_criativa_sebrae.json --descartar trajetoria_suavizada intervalo_de_confianca_mais intervalo_de_confianca_menos
```

O CSV `avancasc.saneamento_bronze.taxa_rdo.csv` vem do Impala com nomes de prestador que têm vírgula
sem aspas (ex.: `Secretaria de Agricultura, Indústria, Comércio`), o que desloca as colunas. Antes de
importar, junte as partes do nome em `prestador` e deixe `natureza_juridica` como `NULL` nessas linhas
(nelas a taxa já vem `NULL`).

Quando vários indicadores dividem o mesmo arquivo (ex.: a participação do VAB de cada setor
em `industria_silver_tl__extract_pib_municipal_fecam.json`), informe no catálogo a coluna de
cada um em `coluna_do_valor` (ex.: `"coluna_do_valor": "vab_ind"`). Essa coluna passa a ser a
usada nos cartões de resumo, nas estatísticas e no ano de referência; sem o campo, vale a
primeira coluna numérica do arquivo.

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
| `GET /api/indicadores/<id>/impala` | ficha do indicador e a última consulta ao Impala (`consulta: null` se não houver) |
| `GET /api/indicadores/<id>/impala/json` | arquivo JSON bruto de `Dados/tabelas_impala` do indicador |
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
  gateway.py            gateway da API do Hue (/api/queries, /api/tabelas, /api/consultas...)
  impala.py             tabelas_impala: gravação, comparação com tabelas_bi e atualização em lote
  servidor.py           Aplicacao (rotas /api), ArquivosEstaticos, Servidor
  navegador.py          abertura no Chrome
web/                    front-end React
  index.html            carrega React, htm e Bootstrap de web/vendor
  js/main.js, app.js    inicialização e rotas das telas
  js/paginas/           Inicio, Painel, DadosIndicador, ConsultaImpala
  js/componentes/       Cabecalho (e Rodape), Pagina, Notificacoes, StatusTag, TabelaOrdenavel, Comuns
  css/app.css           tema (Avança SC) sobre o Bootstrap
  vendor/fonts/         Montserrat (woff2, OFL)
Dados/                  catálogo, status_indicadores.json, municipios_sc.json, hue_endpoints.json,
                        tabelas_bi (sistema) e tabelas_impala (consultas ao Impala)
tests/                  testes unitários
```

### Visual

O tema segue a identidade do Avança SC (https://avanca.sc.gov.br): verde-petróleo `#0b373b` na faixa de título de
cada tela, verdes da marca nos botões em pílula, fundo `#edf2ef`, rodapé `#d9e3e3` e a fonte Montserrat (servida de
`web/vendor/fonts`, licença OFL, sem depender de internet). Os tokens de cor estão no início de `web/css/app.css`.
O verde dos botões é um tom mais escuro que o `#5d912a` da marca, para que o texto branco tenha contraste de 5:1
(WCAG AA). Toda tela usa o componente `Pagina` (`web/js/componentes/Pagina.js`): faixa com migalhas, título, tags e
ações, e o conteúdo abaixo.

No painel, os cartões de resumo filtram a tabela ao serem clicados, e os filtros ficam na URL
(`/painel?situacao=DESATUALIZADO&impala=DESATUALIZADO&q=pib&detalhes=1`). A tela inicial usa esses links.

Os componentes usam `html\`...\`` (biblioteca htm) no lugar de JSX, para rodar
direto no navegador sem compilação. Para criar uma tela nova: crie o componente
em `web/js/paginas/` e inclua a rota em `telaDa()` no `web/js/app.js`.
