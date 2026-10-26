// Painel: todos os indicadores do catálogo com a situação de atualização de cada um.
import { html, useMemo, useState } from '../lib.js';
import { api, useConsulta } from '../api.js';
import { comparar, plural } from '../formato.js';
import { Link, useTitulo } from '../rotas.js';
import { CartoesResumo, Carregando, Erro } from '../componentes/Comuns.js';
import { NomeFonte, ROTULO_STATUS, StatusTag, estaDesatualizado } from '../componentes/StatusTag.js';
import { TabelaOrdenavel } from '../componentes/TabelaOrdenavel.js';

const CAMPOS_BUSCA = ['nome', 'eixo', 'descricao', 'formula', 'unidade', 'fonte', 'temporalidade', 'tabela_databricks'];

function LinksFonte({ indicador }) {
  return indicador.fontes_publicas.map((url, i) => html`
    <a key=${url} href=${url} target="_blank" rel="noopener" className="ms-1">
      fonte${indicador.fontes_publicas.length > 1 ? ` ${i + 1}` : ''}
      <span className="visually-hidden"> de ${indicador.nome} (abre em nova aba)</span>
    </a>`);
}

const COLUNAS = [
  { chave: 'id', titulo: 'ID', numerica: true },
  {
    chave: 'situacao', titulo: 'Situação',
    valor: (i) => ROTULO_STATUS[i.situacao.status],
    celula: (i) => html`<${StatusTag} situacao=${i.situacao} />`,
  },
  {
    chave: 'dados', titulo: 'Dados',
    valor: (i) => (i.tem_dados ? 0 : 1),
    celula: (i) => (i.tem_dados
      ? html`<${Link} para=${`/indicadores/${i.id}`} className="btn btn-success btn-sm text-nowrap">
               Visualizar dados<span className="visually-hidden"> de ${i.nome}</span><//>`
      : html`<span className="text-body-secondary small text-nowrap">Sem arquivo</span>`),
  },
  { chave: 'eixo', titulo: 'Bloco / Eixo' },
  {
    chave: 'nome', titulo: 'Indicador',
    celula: (i) => html`<${Link} para=${`/indicadores/${i.id}`} className="fw-semibold">${i.nome}<//>`,
  },
  { chave: 'descricao', titulo: 'Descrição' },
  { chave: 'formula', titulo: 'Fórmula de cálculo' },
  { chave: 'unidade', titulo: 'Unidade' },
  {
    chave: 'fonte', titulo: 'Fonte',
    celula: (i) => html`<${NomeFonte} indicador=${i} /><${LinksFonte} indicador=${i} />`,
  },
  { chave: 'temporalidade', titulo: 'Temporalidade' },
  { chave: 'tabela_databricks', titulo: 'Tabela Databricks', celula: (i) => html`<code>${i.tabela_databricks}</code>` },
];

export function Painel() {
  useTitulo('Painel de indicadores');
  const { dados, erro, carregando } = useConsulta(api.indicadores, []);
  const [busca, setBusca] = useState('');
  const [eixo, setEixo] = useState('');
  const [status, setStatus] = useState('');

  const indicadores = dados?.indicadores ?? [];
  const eixos = useMemo(() => [...new Set(indicadores.map((i) => i.eixo || ''))].sort(comparar), [indicadores]);
  const desatualizados = indicadores.filter(estaDesatualizado).length;

  const filtrados = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return indicadores.filter((i) => (!eixo || (i.eixo || '') === eixo)
      && (!status || i.situacao.status === status)
      && (!termo || CAMPOS_BUSCA.some((c) => String(i[c] ?? '').toLowerCase().includes(termo))));
  }, [indicadores, busca, eixo, status]);

  return html`
    <h1 className="h3 mb-1" tabIndex="-1">Painel de indicadores</h1>
    <p className="text-body-secondary">${dados ? `Catálogo ${dados.arquivo}` : ' '}</p>
    ${carregando && !dados && html`<${Carregando} />`}
    ${erro && html`<${Erro} erro=${erro} />`}
    ${dados && html`
      <${CartoesResumo} itens=${[
        { valor: indicadores.length, rotulo: 'indicadores' },
        { valor: eixos.length, rotulo: 'blocos / eixos' },
        { valor: indicadores.filter((i) => i.tem_dados).length, rotulo: 'com dados disponíveis' },
        { valor: indicadores.length - desatualizados, rotulo: 'atualizados', classe: 'text-success-emphasis' },
        { valor: desatualizados, rotulo: 'desatualizados', classe: desatualizados ? 'text-danger-emphasis' : '' },
      ]} />

      <form className="card card-body mb-3" role="search" aria-label="Filtrar indicadores" onSubmit=${(e) => e.preventDefault()}>
        <div className="row g-2 align-items-end">
          <div className="col-12 col-lg-5">
            <label htmlFor="busca" className="form-label">Buscar</label>
            <input id="busca" type="search" className="form-control" value=${busca}
                   placeholder="Indicador, fonte, tabela..." onChange=${(e) => setBusca(e.target.value)} />
          </div>
          <div className="col-12 col-sm-6 col-lg-3">
            <label htmlFor="filtro-eixo" className="form-label">Bloco / eixo</label>
            <select id="filtro-eixo" className="form-select" value=${eixo} onChange=${(e) => setEixo(e.target.value)}>
              <option value="">Todos os eixos</option>
              ${eixos.map((e) => html`<option key=${e} value=${e}>${e || '(sem eixo)'}</option>`)}
            </select>
          </div>
          <div className="col-12 col-sm-6 col-lg-2">
            <label htmlFor="filtro-situacao" className="form-label">Situação</label>
            <select id="filtro-situacao" className="form-select" value=${status} onChange=${(e) => setStatus(e.target.value)}>
              <option value="">Todas</option>
              ${Object.entries(ROTULO_STATUS).map(([valor, rotulo]) => html`<option key=${valor} value=${valor}>${rotulo}</option>`)}
            </select>
          </div>
          <div className="col-12 col-lg-2">
            <p className="mb-2 small text-body-secondary" role="status">${plural(filtrados.length, 'indicador', 'indicadores')}</p>
          </div>
        </div>
      </form>

      ${filtrados.length === 0
        ? html`<div className="alert alert-info">Nenhum indicador corresponde aos filtros.</div>`
        : html`<${TabelaOrdenavel} id="tabela-indicadores" legenda="Indicadores do catálogo"
                 colunas=${COLUNAS} linhas=${filtrados} chaveLinha=${(i) => i.id} />`}
    `}`;
}
