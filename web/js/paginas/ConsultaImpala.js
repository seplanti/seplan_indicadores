// Resultado da consulta ao Impala de um indicador (Dados/tabelas_impala), em tabela ou JSON.
// Aberta com ?consultar=1 (botão do painel), consulta o Impala ao carregar.
import { html, useEffect, useMemo, useRef, useState } from '../lib.js';
import { api, useConsulta } from '../api.js';
import { formatarNumero, plural } from '../formato.js';
import { Link } from '../rotas.js';
import { Pagina } from '../componentes/Pagina.js';
import { Carregando, CartoesResumo, Erro } from '../componentes/Comuns.js';
import { ImpalaTags, formatarConsulta } from '../componentes/StatusTag.js';
import { TabelaOrdenavel } from '../componentes/TabelaOrdenavel.js';

const CHAVE_MODO = 'seplan:modo-impala';
const MODOS = { tabela: 'Tabela', json: 'JSON' };
// O JSON na tela fica legível até este número de linhas; o completo abre pelo link "JSON bruto".
const LIMITE_JSON = 1000;
const COLUNAS_SEM_FORMATO = /^(ano|year|month|mes|id|cod|codigo|co_|cd_)/i;

// ?modo=json ou ?modo=tabela na URL; senão a última escolha do usuário.
function lerModo() {
  const daUrl = new URLSearchParams(location.search).get('modo');
  if (MODOS[daUrl]) return daUrl;
  try { return MODOS[localStorage.getItem(CHAVE_MODO)] ? localStorage.getItem(CHAVE_MODO) : 'tabela'; } catch { return 'tabela'; }
}

function gravarModo(modo) {
  try { localStorage.setItem(CHAVE_MODO, modo); } catch { /* sem armazenamento: só não lembra a escolha */ }
}

function SeletorModo({ modo, setModo }) {
  return html`
    <div className="btn-group" role="group" aria-labelledby="rotulo-modo">
      ${Object.entries(MODOS).map(([valor, rotulo]) => html`
        <input key=${`i-${valor}`} type="radio" className="btn-check" name="modo-impala" id=${`modo-${valor}`}
               checked=${modo === valor} onChange=${() => setModo(valor)} />
        <label key=${`l-${valor}`} className="btn btn-outline-primary btn-sm" htmlFor=${`modo-${valor}`}>${rotulo}</label>`)}
    </div>`;
}

function VistaTabela({ consulta, linhas }) {
  const posicoes = useMemo(() => new Map(consulta.rows.map((r, i) => [r, i])), [consulta]);
  const colunas = useMemo(() => consulta.columns.map((chave) => {
    const numerica = consulta.rows.some((r) => typeof r[chave] === 'number');
    // Anos e códigos aparecem como vieram (2000, não 2.000).
    const semFormato = COLUNAS_SEM_FORMATO.test(chave);
    return {
      chave, titulo: chave, numerica,
      celula: (r) => (typeof r[chave] === 'number' && !semFormato ? formatarNumero(r[chave]) : r[chave]),
    };
  }), [consulta]);
  return html`<${TabelaOrdenavel} id="tabela-impala" colunas=${colunas} linhas=${linhas}
    chaveLinha=${(r) => posicoes.get(r)} legenda=${`Linhas de ${consulta.database}.${consulta.tabela}`} />`;
}

function VistaJson({ consulta, linhas, idIndicador }) {
  const exibidas = linhas.slice(0, LIMITE_JSON);
  const texto = useMemo(
    () => JSON.stringify({ ...consulta, rows: exibidas }, null, 2),
    [consulta, linhas],
  );
  const [copiado, setCopiado] = useState(false);
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch { setCopiado(false); }
  };
  return html`
    <div className="d-flex flex-wrap align-items-center gap-2 mb-2">
      <button type="button" className="btn btn-outline-secondary btn-sm" onClick=${copiar}>
        ${copiado ? 'Copiado' : 'Copiar JSON'}
      </button>
      <a className="btn btn-outline-secondary btn-sm" href=${`/api/indicadores/${idIndicador}/impala/json`}
         target="_blank" rel="noopener">JSON bruto completo<span className="visually-hidden"> (abre em nova aba)</span></a>
      <span className="small text-body-secondary" role="status">
        ${linhas.length > LIMITE_JSON
          ? `Mostrando ${formatarNumero(LIMITE_JSON)} de ${plural(linhas.length, 'linha', 'linhas')}; o arquivo completo está no JSON bruto.`
          : plural(linhas.length, 'linha', 'linhas')}
      </span>
    </div>
    <pre className="json-impala" tabIndex="0" aria-label="Resultado da consulta em JSON">${texto}</pre>`;
}

export function ConsultaImpala({ id }) {
  const [versao, setVersao] = useState(0);
  const { dados, erro, carregando } = useConsulta(() => api.dadosImpala(id), [id, versao]);
  const [envio, setEnvio] = useState({ enviando: false, erro: null });
  const [modo, setModoEstado] = useState(lerModo);
  const [busca, setBusca] = useState('');
  const pedidoInicial = useRef(new URLSearchParams(location.search).get('consultar') === '1');

  const indicador = dados?.indicador;
  const consulta = dados?.consulta;

  const setModo = (valor) => { setModoEstado(valor); gravarModo(valor); };

  const consultar = async () => {
    if (!indicador?.impala) return;
    setEnvio({ enviando: true, erro: null });
    try {
      await api.atualizarImpala(indicador.impala.tabela);
      setEnvio({ enviando: false, erro: null });
    } catch (e) {
      setEnvio({ enviando: false, erro: e });
    }
    setVersao((v) => v + 1);
  };

  // Vindo do botão do painel: consulta uma vez e tira o ?consultar=1, para recarregar a página não repetir.
  useEffect(() => {
    if (pedidoInicial.current && indicador) {
      pedidoInicial.current = false;
      history.replaceState(null, '', location.pathname);
      consultar();
    }
  }, [indicador]);

  const linhas = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    const todas = consulta?.rows ?? [];
    if (!termo) return todas;
    return todas.filter((r) => Object.values(r).some((v) => String(v ?? '').toLowerCase().includes(termo)));
  }, [consulta, busca]);

  const nome = indicador?.nome ?? `Indicador ${id}`;
  const botaoConsultar = indicador?.impala && html`
    <button type="button" className="btn btn-destaque btn-sm" onClick=${consultar} disabled=${envio.enviando}>
      ${envio.enviando ? 'Consultando o Impala…' : (consulta ? 'Consultar novamente' : 'Consultar Impala')}
    </button>`;

  return html`
    <${Pagina}
      titulo=${indicador ? indicador.nome : 'Consulta ao Impala'}
      tituloAba=${indicador ? `Impala — ${indicador.nome}` : 'Consulta ao Impala'}
      migalhas=${[{ para: '/', rotulo: 'Início' }, { para: '/painel', rotulo: 'Painel de indicadores' },
                  { para: `/indicadores/${id}`, rotulo: nome }, { rotulo: 'Consulta ao Impala' }]}
      tags=${indicador && html`<${ImpalaTags} impala=${indicador.impala} />`}
      subtitulo=${indicador?.impala ? html`Consulta ao Impala via Hue · tabela <code className="text-white">${indicador.impala.tabela}</code>` : 'Consulta ao Impala via Hue'}
      acoes=${indicador && html`
        ${botaoConsultar}
        <${Link} para=${`/indicadores/${id}`} className="btn btn-faixa btn-sm">Dados do sistema<//>
        ${consulta && html`
          <a className="btn btn-faixa btn-sm" href=${`/api/indicadores/${id}/impala/json`} target="_blank" rel="noopener">
            JSON bruto<span className="visually-hidden"> (abre em nova aba)</span></a>`}`}>
      ${carregando && !dados && html`<${Carregando} />`}
      ${erro && html`<${Erro} erro=${erro} />`}
      ${envio.enviando && html`<div className="alert alert-info d-flex align-items-center gap-2" role="status">
        <span className="spinner-border spinner-border-sm" aria-hidden="true"></span>
        Consultando a tabela inteira no Impala. Tabelas grandes podem levar alguns segundos.</div>`}
      ${envio.erro && html`<div className="alert alert-danger" role="alert">A consulta falhou: ${envio.erro.message}</div>`}
      ${indicador && !indicador.impala && html`
        <div className="alert alert-warning">Este indicador não tem tabela no catálogo (tabela_databricks), então não há o que consultar no Impala.</div>`}
      ${indicador?.impala && html`
        ${indicador.impala.sistema.motivo && html`
          <div className=${`alert ${indicador.impala.sistema.status === 'DESATUALIZADO' ? 'alert-danger' : 'alert-info'}`}>
            <strong>Comparação com o sistema:</strong> ${indicador.impala.sistema.motivo}</div>`}

        ${consulta && html`
          <${CartoesResumo} rotulo="Resumo da consulta" itens=${[
            { valor: formatarNumero(consulta.total), rotulo: 'linhas' },
            { valor: consulta.columns.length, rotulo: 'colunas' },
            { valor: formatarConsulta(consulta.consultado_em), rotulo: 'consultado em', texto: true },
            { valor: consulta.database, rotulo: 'banco', texto: true },
          ]} />
          <p className="small text-body-secondary mb-3">SQL executado: <code>${consulta.sql}</code></p>`}

        ${!consulta && !envio.enviando && html`
          <div className="alert alert-info">O Impala ainda não foi consultado para este indicador. Use o botão “Consultar Impala” acima.</div>`}
        ${consulta?.has_more && html`
          <div className="alert alert-warning">A tabela passa de ${formatarNumero(consulta.total)} linhas (HUE_LIMITE_SINCRONIZACAO): o resultado está incompleto e as linhas não foram gravadas.</div>`}

        ${consulta && consulta.rows.length > 0 && html`
          <form className="filtros" role="search" aria-label="Filtrar linhas" onSubmit=${(e) => e.preventDefault()}>
            <div className="row g-3 align-items-end">
              <div className="col-12 col-md-6">
                <label htmlFor="busca-impala" className="form-label">Buscar</label>
                <input id="busca-impala" type="search" className="form-control" value=${busca}
                       placeholder="Qualquer valor das linhas..." onChange=${(e) => setBusca(e.target.value)} />
              </div>
              <div className="col-auto">
                <span className="form-label d-block" id="rotulo-modo">Exibir como</span>
                <${SeletorModo} modo=${modo} setModo=${setModo} />
              </div>
              <div className="col-auto">
                <p className="contagem mb-2" role="status">${plural(linhas.length, 'linha', 'linhas')}</p>
              </div>
            </div>
          </form>
          ${linhas.length === 0
            ? html`<div className="alert alert-info">Nenhuma linha corresponde à busca.</div>`
            : modo === 'json'
              ? html`<${VistaJson} consulta=${consulta} linhas=${linhas} idIndicador=${id} />`
              : html`<${VistaTabela} consulta=${consulta} linhas=${linhas} />`}`}
      `}
    <//>`;
}
