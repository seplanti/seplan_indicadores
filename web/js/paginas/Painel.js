// Painel: todos os indicadores do catálogo com a situação de atualização e a comparação com o Impala.
// Os filtros ficam na URL (?q=&eixo=&situacao=&impala=&detalhes=1), para links diretos e para o "voltar".
import { html, useEffect, useMemo, useState } from '../lib.js';
import { api, useConsulta } from '../api.js';
import { comparar, plural } from '../formato.js';
import { Link } from '../rotas.js';
import { CartoesResumo, Carregando, Erro } from '../componentes/Comuns.js';
import { Pagina } from '../componentes/Pagina.js';
import {
  ImpalaTags, NomeFonte, ROTULO_CATEGORIA, ROTULO_IMPALA, StatusTag, categoriaDe, situacaoImpala,
} from '../componentes/StatusTag.js';
import { TabelaOrdenavel } from '../componentes/TabelaOrdenavel.js';

const CAMPOS_BUSCA = ['nome', 'eixo', 'descricao', 'formula', 'unidade', 'fonte', 'temporalidade', 'tabela_databricks'];
const FILTROS_VAZIOS = { q: '', eixo: '', situacao: '', impala: '', detalhes: '' };

function lerFiltros() {
  const parametros = new URLSearchParams(location.search);
  return Object.fromEntries(Object.keys(FILTROS_VAZIOS).map((chave) => [chave, parametros.get(chave) ?? '']));
}

function gravarFiltros(filtros) {
  const parametros = new URLSearchParams(Object.entries(filtros).filter(([, valor]) => valor));
  const busca = parametros.toString();
  history.replaceState(null, '', `${location.pathname}${busca ? `?${busca}` : ''}`);
}

function LinksFonte({ indicador }) {
  return indicador.fontes_publicas.map((url, i) => html`
    <a key=${url} href=${url} target="_blank" rel="noopener" className="ms-1 text-nowrap">
      fonte${indicador.fontes_publicas.length > 1 ? ` ${i + 1}` : ''}
      <span className="visually-hidden"> de ${indicador.nome} (abre em nova aba)</span>
    </a>`);
}

function Acoes({ indicador: i }) {
  return html`
    <div className="acoes">
      ${i.tem_dados
        ? html`<${Link} para=${`/indicadores/${i.id}`} className="btn btn-primary btn-sm text-nowrap">
                 Ver dados<span className="visually-hidden"> de ${i.nome}</span><//>`
        : html`<span className="status-tag tag-neutro justify-content-center">Sem arquivo no sistema</span>`}
      ${i.impala && html`
        <${Link} para=${`/indicadores/${i.id}/impala?consultar=1`} className="btn btn-outline-primary btn-sm text-nowrap"
                 title="Consulta a tabela no Impala agora e mostra o resultado">
          Consultar Impala<span className="visually-hidden"> para ${i.nome}</span><//>
        ${i.impala.impala.consultado_em && html`
          <${Link} para=${`/indicadores/${i.id}/impala`} className="small text-center text-nowrap">
            Última consulta<span className="visually-hidden"> de ${i.nome}</span><//>`}`}
    </div>`;
}

const COLUNAS_BASE = [
  { chave: 'id', titulo: 'ID', numerica: true },
  {
    chave: 'nome', titulo: 'Indicador', classe: 'celula-indicador',
    celula: (i) => html`
      <${Link} para=${`/indicadores/${i.id}`}>${i.nome}<//>
      <div className="celula-meta">${[i.eixo, i.unidade].filter(Boolean).join(' · ')}</div>`,
  },
  {
    chave: 'situacao', titulo: 'Situação',
    valor: (i) => ROTULO_CATEGORIA[categoriaDe(i)],
    celula: (i) => html`<${StatusTag} indicador=${i} />`,
  },
  {
    chave: 'impala', titulo: 'Impala × Sistema',
    valor: (i) => ROTULO_IMPALA[situacaoImpala(i)] ?? '',
    celula: (i) => html`<${ImpalaTags} impala=${i.impala} />`,
  },
  {
    chave: 'fonte', titulo: 'Fonte',
    celula: (i) => html`<${NomeFonte} indicador=${i} /><${LinksFonte} indicador=${i} />`,
  },
  { chave: 'temporalidade', titulo: 'Temporalidade' },
];

const COLUNAS_DETALHE = [
  { chave: 'descricao', titulo: 'Descrição', classe: 'celula-texto' },
  { chave: 'formula', titulo: 'Fórmula de cálculo', classe: 'celula-texto' },
  { chave: 'tabela_databricks', titulo: 'Tabela Databricks', celula: (i) => html`<code>${i.tabela_databricks}</code>` },
];

const COLUNA_ACOES = { chave: 'acoes', titulo: 'Ações', valor: (i) => (i.tem_dados ? 0 : 1), celula: (i) => html`<${Acoes} indicador=${i} />` };

export function Painel() {
  const { dados, erro, carregando } = useConsulta(api.indicadores, []);
  const [filtros, setFiltros] = useState(lerFiltros);
  useEffect(() => gravarFiltros(filtros), [filtros]);
  const alterar = (chave, valor) => setFiltros((f) => ({ ...f, [chave]: valor }));
  const alternar = (chave, valor) => () => setFiltros((f) => ({ ...f, [chave]: f[chave] === valor ? '' : valor }));
  const filtrando = ['q', 'eixo', 'situacao', 'impala'].some((c) => filtros[c]);

  const indicadores = dados?.indicadores ?? [];
  const eixos = useMemo(() => [...new Set(indicadores.map((i) => i.eixo || ''))].sort(comparar), [indicadores]);
  const contar = (categoria) => indicadores.filter((i) => categoriaDe(i) === categoria).length;
  const contarImpala = (situacao) => indicadores.filter((i) => situacaoImpala(i) === situacao).length;

  const filtrados = useMemo(() => {
    const termo = filtros.q.trim().toLowerCase();
    return indicadores.filter((i) => (!filtros.eixo || (i.eixo || '') === filtros.eixo)
      && (!filtros.situacao || categoriaDe(i) === filtros.situacao)
      && (!filtros.impala || situacaoImpala(i) === filtros.impala)
      && (!termo || CAMPOS_BUSCA.some((c) => String(i[c] ?? '').toLowerCase().includes(termo))));
  }, [indicadores, filtros]);

  const colunas = useMemo(
    () => [...COLUNAS_BASE, ...(filtros.detalhes ? COLUNAS_DETALHE : []), COLUNA_ACOES],
    [filtros.detalhes],
  );

  return html`
    <${Pagina}
      titulo="Painel de indicadores"
      migalhas=${[{ para: '/', rotulo: 'Início' }, { rotulo: 'Painel de indicadores' }]}
      subtitulo=${dados ? `Catálogo ${dados.arquivo} · ${plural(indicadores.length, 'indicador', 'indicadores')}` : 'Catálogo de indicadores'}>
      ${carregando && !dados && html`<${Carregando} />`}
      ${erro && html`<${Erro} erro=${erro} />`}
      ${dados && html`
        <div className="row g-3 mb-1">
          <div className="col-12 col-xl-6">
            <h2 className="secao-titulo">Situação no sistema</h2>
            <${CartoesResumo} rotulo="Filtrar por situação" itens=${[
              { valor: contar('ATUALIZADO'), rotulo: 'atualizados', tom: 'sucesso', aoClicar: alternar('situacao', 'ATUALIZADO'), ativo: filtros.situacao === 'ATUALIZADO' },
              { valor: contar('DESATUALIZADO'), rotulo: 'desatualizados', tom: 'perigo', aoClicar: alternar('situacao', 'DESATUALIZADO'), ativo: filtros.situacao === 'DESATUALIZADO' },
              { valor: contar('SEM_DADOS'), rotulo: 'sem dados', tom: 'neutro', aoClicar: alternar('situacao', 'SEM_DADOS'), ativo: filtros.situacao === 'SEM_DADOS' },
            ]} />
          </div>
          <div className="col-12 col-xl-6">
            <h2 className="secao-titulo">Comparação com o Impala</h2>
            <${CartoesResumo} rotulo="Filtrar pela comparação com o Impala" itens=${[
              { valor: contarImpala('ATUALIZADO'), rotulo: 'iguais ao Impala', tom: 'sucesso', aoClicar: alternar('impala', 'ATUALIZADO'), ativo: filtros.impala === 'ATUALIZADO' },
              { valor: contarImpala('DESATUALIZADO'), rotulo: 'diferentes do Impala', tom: 'perigo', aoClicar: alternar('impala', 'DESATUALIZADO'), ativo: filtros.impala === 'DESATUALIZADO' },
              { valor: contarImpala('SEM_COMPARACAO'), rotulo: 'sem comparação', tom: 'neutro', aoClicar: alternar('impala', 'SEM_COMPARACAO'), ativo: filtros.impala === 'SEM_COMPARACAO' },
            ]} />
          </div>
        </div>

        <form className="filtros" role="search" aria-label="Filtrar indicadores" onSubmit=${(e) => e.preventDefault()}>
          <div className="row g-3 align-items-end">
            <div className="col-12 col-lg-4">
              <label htmlFor="busca" className="form-label">Buscar</label>
              <input id="busca" type="search" className="form-control" value=${filtros.q}
                     placeholder="Indicador, fonte, tabela..." onChange=${(e) => alterar('q', e.target.value)} />
            </div>
            <div className="col-12 col-sm-6 col-lg-3">
              <label htmlFor="filtro-eixo" className="form-label">Bloco / eixo</label>
              <select id="filtro-eixo" className="form-select" value=${filtros.eixo} onChange=${(e) => alterar('eixo', e.target.value)}>
                <option value="">Todos os eixos</option>
                ${eixos.map((e) => html`<option key=${e} value=${e}>${e || '(sem eixo)'}</option>`)}
              </select>
            </div>
            <div className="col-12 col-sm-6 col-lg-2">
              <label htmlFor="filtro-situacao" className="form-label">Situação</label>
              <select id="filtro-situacao" className="form-select" value=${filtros.situacao} onChange=${(e) => alterar('situacao', e.target.value)}>
                <option value="">Todas</option>
                ${Object.entries(ROTULO_CATEGORIA).map(([valor, rotulo]) => html`<option key=${valor} value=${valor}>${rotulo}</option>`)}
              </select>
            </div>
            <div className="col-12 col-sm-6 col-lg-3">
              <label htmlFor="filtro-impala" className="form-label">Impala × Sistema</label>
              <select id="filtro-impala" className="form-select" value=${filtros.impala} onChange=${(e) => alterar('impala', e.target.value)}>
                <option value="">Todos</option>
                ${Object.entries(ROTULO_IMPALA).map(([valor, rotulo]) => html`<option key=${valor} value=${valor}>${rotulo}</option>`)}
              </select>
            </div>
          </div>
          <div className="d-flex flex-wrap align-items-center gap-3 mt-3">
            <p className="contagem mb-0" role="status">
              ${filtrando ? `${plural(filtrados.length, 'indicador', 'indicadores')} de ${indicadores.length}` : plural(filtrados.length, 'indicador', 'indicadores')}
            </p>
            ${filtrando && html`
              <button type="button" className="btn btn-outline-secondary btn-sm"
                      onClick=${() => setFiltros((f) => ({ ...FILTROS_VAZIOS, detalhes: f.detalhes }))}>Limpar filtros</button>`}
            <div className="form-check form-switch mb-0 ms-md-auto">
              <input className="form-check-input" type="checkbox" role="switch" id="mostrar-detalhes"
                     checked=${Boolean(filtros.detalhes)} onChange=${(e) => alterar('detalhes', e.target.checked ? '1' : '')} />
              <label className="form-check-label small fw-semibold" htmlFor="mostrar-detalhes">Mostrar descrição, fórmula e tabela</label>
            </div>
          </div>
        </form>

        ${filtrados.length === 0
          ? html`<div className="alert alert-info">Nenhum indicador corresponde aos filtros.</div>`
          : html`<${TabelaOrdenavel} id="tabela-indicadores" legenda="Indicadores do catálogo"
                   colunas=${colunas} linhas=${filtrados} chaveLinha=${(i) => i.id} />`}
      `}
    <//>`;
}
