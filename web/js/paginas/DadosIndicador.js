// Ficha e dados (tabela_bi) de um indicador.
import { html, useMemo, useState } from '../lib.js';
import { api, urlJsonBruto, useConsulta } from '../api.js';
import { comparar, formatarData, formatarDecimal, formatarInteiro, formatarNumero, plural } from '../formato.js';
import { Link, useTitulo } from '../rotas.js';
import { CartoesResumo, Carregando, Erro } from '../componentes/Comuns.js';
import { NomeFonte, StatusTag, estaDesatualizado } from '../componentes/StatusTag.js';
import { TabelaOrdenavel } from '../componentes/TabelaOrdenavel.js';

const COLUNA_GRUPO = 'fecam';

function Ficha({ indicador }) {
  const itens = [
    ['Bloco / eixo', indicador.eixo],
    ['Descrição', indicador.descricao],
    ['Fórmula', indicador.formula],
    ['Unidade', indicador.unidade],
    ['Fonte', html`<${NomeFonte} indicador=${indicador} />`],
    ['Temporalidade', indicador.temporalidade],
    ['Tabela Databricks', html`<code>${indicador.tabela_databricks}</code>`],
  ];
  return html`
    <dl className="ficha card card-body mb-3">
      ${itens.map(([rotulo, valor]) => html`<div key=${rotulo} className="contents"><dt>${rotulo}</dt><dd>${valor}</dd></div>`)}
    </dl>`;
}

function AvisoDesatualizado({ situacao }) {
  return html`
    <div className="alert alert-danger">
      <strong>Dados desatualizados</strong>${situacao.desde && ` desde ${formatarData(situacao.desde)}`}.
      ${situacao.motivo && html` ${situacao.motivo}`}
    </div>`;
}

function Tabela({ indicador, tabela }) {
  const [busca, setBusca] = useState('');
  const [grupo, setGrupo] = useState('');
  // `anos` e as estatísticas por ano podem faltar se o servidor Python estiver
  // rodando uma versão anterior da API; nesse caso a tela funciona sem o filtro de ano.
  const anos = tabela.anos ?? [];
  // Séries históricas abrem no último ano com dado observado (não numa projeção);
  // '' mostra todos os anos. Séries com um registro por ano (ex.: só o total de SC)
  // abrem com todos os anos, senão a tabela mostraria uma única linha.
  const anoInicial = tabela.ano_referencia ?? anos.at(-1);
  const variosPorAno = tabela.registros.length > anos.length;
  const [ano, setAno] = useState(anos.length > 1 && variosPorAno ? String(anoInicial) : '');
  const temGrupo = tabela.colunas.includes(COLUNA_GRUPO);
  // Chave estável de cada linha (posição no arquivo), sem indexOf a cada renderização.
  const posicoes = useMemo(() => new Map(tabela.registros.map((r, i) => [r, i])), [tabela]);
  const grupos = useMemo(
    () => (temGrupo ? [...new Set(tabela.registros.map((r) => String(r[COLUNA_GRUPO] ?? '')))].sort(comparar) : []),
    [tabela, temGrupo],
  );

  const colunas = useMemo(() => tabela.colunas.map((chave) => {
    const metrica = tabela.colunas_numericas.includes(chave);
    return {
      chave,
      titulo: chave,
      numerica: metrica || tabela.registros.some((r) => typeof r[chave] === 'number'),
      celula: metrica ? (r) => formatarNumero(r[chave]) : undefined,
    };
  }), [tabela]);

  const filtrados = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return tabela.registros.filter((r) => (!ano || String(r.ano) === ano)
      && (!grupo || String(r[COLUNA_GRUPO] ?? '') === grupo)
      && (!termo || tabela.colunas.some((c) => String(r[c] ?? '').toLowerCase().includes(termo))));
  }, [tabela, busca, grupo, ano]);

  const est = tabela.estatisticas?.[ano || 'todos'];
  const unidade = indicador.unidade ? ` ${indicador.unidade}` : '';
  const periodo = ano ? ` em ${ano}` : (anos.length > 1 ? ' (todos os anos)' : '');

  return html`
    ${est && html`<${CartoesResumo} itens=${[
      est.valor_estado != null && { valor: formatarNumero(est.valor_estado), rotulo: `Santa Catarina (${est.coluna})` },
      { valor: formatarInteiro(est.total), rotulo: `registros${periodo}` },
      { valor: formatarDecimal(est.media), rotulo: `média de ${est.coluna}${unidade && ` (${unidade.trim()})`}` },
      { valor: formatarNumero(est.maior), rotulo: `maior: ${est.rotulo_maior}` },
      { valor: formatarNumero(est.menor), rotulo: `menor: ${est.rotulo_menor}` },
    ].filter(Boolean)} />`}

    <form className="card card-body mb-3" role="search" aria-label="Filtrar registros" onSubmit=${(e) => e.preventDefault()}>
      <div className="row g-2 align-items-end">
        <div className="col-12 col-lg-4">
          <label htmlFor="busca-dados" className="form-label">Buscar</label>
          <input id="busca-dados" type="search" className="form-control" value=${busca}
                 placeholder="Município, código IBGE..." onChange=${(e) => setBusca(e.target.value)} />
        </div>
        ${anos.length > 1 && html`
          <div className="col-12 col-sm-6 col-lg-2">
            <label htmlFor="filtro-ano" className="form-label">Ano</label>
            <select id="filtro-ano" className="form-select" value=${ano} onChange=${(e) => setAno(e.target.value)}>
              <option value="">Todos os anos</option>
              ${[...anos].reverse().map((a) => html`<option key=${a} value=${a}>${a}</option>`)}
            </select>
          </div>`}
        ${temGrupo && html`
          <div className="col-12 col-sm-6 col-lg-3">
            <label htmlFor="filtro-grupo" className="form-label">FECAM</label>
            <select id="filtro-grupo" className="form-select" value=${grupo} onChange=${(e) => setGrupo(e.target.value)}>
              <option value="">Todas as FECAM</option>
              ${grupos.map((g) => html`<option key=${g} value=${g}>${g}</option>`)}
            </select>
          </div>`}
        <div className="col-12 col-sm-6 col-lg-3">
          <p className="mb-2 small text-body-secondary" role="status" aria-live="polite">${plural(filtrados.length, 'registro', 'registros')}</p>
        </div>
      </div>
    </form>

    ${filtrados.length === 0
      ? html`<div className="alert alert-info">Nenhum registro corresponde aos filtros.</div>`
      : html`<${TabelaOrdenavel} id="tabela-dados" colunas=${colunas} linhas=${filtrados}
               chaveLinha=${(r) => posicoes.get(r)}
               legenda=${`Registros de ${tabela.arquivo}${unidade && ` · valores em${unidade}`}`} />`}`;
}

export function DadosIndicador({ id }) {
  const { dados, erro, carregando } = useConsulta(() => api.dados(id), [id]);
  const indicador = dados?.indicador;
  useTitulo(indicador?.nome ?? 'Indicador');

  return html`
    <p className="mb-2"><${Link} para="/painel">← Voltar ao painel<//></p>
    <div className="d-flex flex-wrap align-items-center gap-2 mb-1">
      <h1 className="h3 mb-0" tabIndex="-1">${indicador?.nome ?? 'Indicador'}</h1>
      ${indicador && html`<${StatusTag} indicador=${indicador} />`}
    </div>
    ${carregando && !dados && html`<${Carregando} />`}
    ${erro && html`<${Erro} erro=${erro} />`}
    ${indicador && html`
      <p className="text-body-secondary">
        ${[indicador.eixo, indicador.unidade].filter(Boolean).join(' · ')}
        ${dados.tabela && html` · <a href=${urlJsonBruto(id)} target="_blank" rel="noopener">JSON bruto<span className="visually-hidden"> (abre em nova aba)</span></a>`}
      </p>
      ${estaDesatualizado(indicador) && html`<${AvisoDesatualizado} situacao=${indicador.situacao} />`}
      <${Ficha} indicador=${indicador} />
      ${dados.tabela
        ? html`<${Tabela} indicador=${indicador} tabela=${dados.tabela} />`
        : html`<div className="alert alert-warning">Este indicador ainda não tem versão publicada.</div>`}
    `}`;
}
