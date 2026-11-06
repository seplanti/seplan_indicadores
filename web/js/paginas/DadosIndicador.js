// Ficha e dados (tabela_bi) de um indicador.
import { html, useMemo, useState } from '../lib.js';
import { api, urlJsonBruto, useConsulta } from '../api.js';
import { comparar, formatarData, formatarDecimal, formatarInteiro, formatarNumero, plural } from '../formato.js';
import { Link } from '../rotas.js';
import { Pagina } from '../componentes/Pagina.js';
import { CartoesResumo, Carregando, Erro } from '../componentes/Comuns.js';
import {
  ImpalaTags, NomeFonte, StatusTag, estaDesatualizado, formatarConsulta,
} from '../componentes/StatusTag.js';
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
    <dl className="ficha">
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

    <form className="filtros" role="search" aria-label="Filtrar registros" onSubmit=${(e) => e.preventDefault()}>
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

// Cartão Impala × Sistema: tags, última consulta e botão que consulta a tabela no Impala agora.
function ComparacaoImpala({ id, impala, aoAtualizar }) {
  const [estado, setEstado] = useState({ enviando: false, erro: null });
  if (!impala) {
    return html`
      <section className="card h-100" aria-labelledby="titulo-comparacao">
        <div className="card-body">
          <h2 id="titulo-comparacao" className="secao-titulo">Impala × Sistema</h2>
          <p className="small text-body-secondary mb-0">Este indicador não tem tabela no catálogo (tabela_databricks), então não é comparado com o Impala.</p>
        </div>
      </section>`;
  }
  const consultar = async () => {
    setEstado({ enviando: true, erro: null });
    try {
      await api.atualizarImpala(impala.tabela);
      setEstado({ enviando: false, erro: null });
      aoAtualizar();
    } catch (erro) {
      setEstado({ enviando: false, erro });
    }
  };
  const consultado = impala.impala.consultado_em;
  return html`
    <section className="card h-100" aria-labelledby="titulo-comparacao">
      <div className="card-body d-flex flex-column gap-2">
        <h2 id="titulo-comparacao" className="secao-titulo mb-0">Impala × Sistema</h2>
        <${ImpalaTags} impala=${impala} />
        <dl className="ficha small mt-1">
          <div className="contents"><dt>Tabela</dt><dd><code>${impala.tabela}</code></dd></div>
          <div className="contents"><dt>Última consulta</dt>
            <dd>${consultado ? `${formatarConsulta(consultado)} · ${plural(impala.impala.linhas ?? 0, 'linha', 'linhas')}` : 'ainda não consultado'}</dd></div>
          ${impala.sistema.motivo && html`<div className="contents"><dt>Resultado</dt><dd>${impala.sistema.motivo}</dd></div>`}
        </dl>
        <div className="d-flex flex-wrap gap-2 mt-auto pt-1">
          <button type="button" className="btn btn-primary btn-sm" onClick=${consultar} disabled=${estado.enviando}>
            ${estado.enviando ? 'Consultando o Impala…' : 'Consultar Impala agora'}
          </button>
          ${consultado && html`
            <${Link} para=${`/indicadores/${id}/impala`} className="btn btn-outline-primary btn-sm">Ver dados do Impala<//>`}
        </div>
        ${estado.erro && html`<div className="alert alert-danger mb-0" role="alert">${estado.erro.message}</div>`}
      </div>
    </section>`;
}

export function DadosIndicador({ id }) {
  const [versao, setVersao] = useState(0);
  const { dados, erro, carregando } = useConsulta(() => api.dados(id), [id, versao]);
  const indicador = dados?.indicador;

  return html`
    <${Pagina}
      titulo=${indicador?.nome ?? 'Indicador'}
      migalhas=${[{ para: '/', rotulo: 'Início' }, { para: '/painel', rotulo: 'Painel de indicadores' }, { rotulo: indicador?.nome ?? `Indicador ${id}` }]}
      tags=${indicador && html`<${StatusTag} indicador=${indicador} />`}
      subtitulo=${indicador && [indicador.eixo, indicador.unidade && `Unidade: ${indicador.unidade}`].filter(Boolean).join(' · ')}
      acoes=${indicador && html`
        ${indicador.impala && html`
          <${Link} para=${`/indicadores/${id}/impala?consultar=1`} className="btn btn-destaque btn-sm">Consultar Impala<//>`}
        ${dados.tabela && html`
          <a href=${urlJsonBruto(id)} target="_blank" rel="noopener" className="btn btn-faixa btn-sm">
            JSON do sistema<span className="visually-hidden"> (abre em nova aba)</span></a>`}`}>
      ${carregando && !dados && html`<${Carregando} />`}
      ${erro && html`<${Erro} erro=${erro} />`}
      ${indicador && html`
        ${estaDesatualizado(indicador) && html`<${AvisoDesatualizado} situacao=${indicador.situacao} />`}
        <div className="row g-3 mb-4">
          <div className="col-12 col-xl-7">
            <section className="card h-100" aria-labelledby="titulo-ficha">
              <div className="card-body">
                <h2 id="titulo-ficha" className="secao-titulo">Ficha técnica</h2>
                <${Ficha} indicador=${indicador} />
              </div>
            </section>
          </div>
          <div className="col-12 col-xl-5">
            <${ComparacaoImpala} id=${id} impala=${indicador.impala} aoAtualizar=${() => setVersao((v) => v + 1)} />
          </div>
        </div>
        <h2 className="secao-titulo">Dados do sistema <span className="fw-medium text-body-secondary small">(tabelas_bi)</span></h2>
        ${dados.tabela
          ? html`<${Tabela} indicador=${indicador} tabela=${dados.tabela} />`
          : html`<div className="alert alert-warning">Este indicador ainda não tem versão publicada.</div>`}
      `}
    <//>`;
}
