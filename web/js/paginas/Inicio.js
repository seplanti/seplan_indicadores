// Tela inicial: quantos indicadores estão atualizados, desatualizados e sem dados, com a lista de cada
// grupo, e o resumo da comparação com o Impala.
import { html } from '../lib.js';
import { api, useConsulta } from '../api.js';
import { comparar, plural } from '../formato.js';
import { Link, navegar } from '../rotas.js';
import { CartoesResumo, Carregando, Erro } from '../componentes/Comuns.js';
import { Pagina } from '../componentes/Pagina.js';
import { categoriaDe, descreverSituacao, situacaoImpala } from '../componentes/StatusTag.js';

// A ordem define a ordem dos cartões e dos trechos da barra de proporção.
const GRUPOS = [
  {
    categoria: 'ATUALIZADO', titulo: 'Atualizados', icone: '✓', classe: 'grupo-atualizado',
    descricao: 'Com arquivo de dados e sem pendência de atualização.',
    vazio: 'Nenhum indicador atualizado.',
  },
  {
    categoria: 'DESATUALIZADO', titulo: 'Desatualizados', icone: '⚠', classe: 'grupo-desatualizado',
    descricao: 'Com arquivo de dados, mas a fonte ou o Impala têm dados mais recentes.',
    vazio: 'Nenhum indicador desatualizado.',
  },
  {
    categoria: 'SEM_DADOS', titulo: 'Sem dados', icone: '○', classe: 'grupo-sem-dados',
    descricao: 'Ainda sem arquivo em Dados/tabelas_bi.',
    vazio: 'Todos os indicadores têm arquivo de dados.',
  },
];

const percentual = (parte, total) => (total ? Math.round((100 * parte) / total) : 0);

function BarraProporcao({ grupos, total }) {
  return html`
    <div className="mt-4" style=${{ maxWidth: '46rem' }}>
      <div className="barra-proporcao" aria-hidden="true">
        ${grupos.filter((g) => g.itens.length).map((g) => html`
          <span key=${g.categoria} className=${g.classe} style=${{ flexGrow: g.itens.length }}></span>`)}
      </div>
      <ul className="legenda-barra">
        ${grupos.map((g) => html`
          <li key=${g.categoria} className=${g.classe}>
            <span aria-hidden="true"></span>${g.titulo}: <strong>${g.itens.length}</strong> (${percentual(g.itens.length, total)}%)
          </li>`)}
      </ul>
    </div>`;
}

function CartaoGrupo({ grupo, total }) {
  const id = `grupo-${grupo.categoria.toLowerCase()}`;
  return html`
    <section className=${`card h-100 cartao-grupo ${grupo.classe}`} aria-labelledby=${id}>
      <div className="card-body flex-grow-0 pb-3">
        <h2 id=${id} className="text-uppercase mb-2">
          <span aria-hidden="true" className="me-1">${grupo.icone}</span>${grupo.titulo}
        </h2>
        <p className="mb-2 d-flex align-items-baseline gap-2">
          <span className="quantidade">${grupo.itens.length}</span>
          <span className="text-body-secondary small fw-semibold">${percentual(grupo.itens.length, total)}% do total</span>
        </p>
        <p className="small text-body-secondary mb-2">${grupo.descricao}</p>
        ${grupo.itens.length > 0 && html`
          <${Link} para=${`/painel?situacao=${grupo.categoria}`} className="small fw-semibold">
            Ver no painel<span className="visually-hidden"> os indicadores ${grupo.titulo.toLowerCase()}</span> →<//>`}
      </div>
      ${grupo.itens.length === 0
        ? html`<p className="px-3 pb-3 small text-body-secondary mb-0">${grupo.vazio}</p>`
        : html`
          <ul className="list-group list-group-flush lista-grupo" tabIndex="0" aria-label=${`Indicadores ${grupo.titulo.toLowerCase()}`}>
            ${grupo.itens.map((i) => html`
              <li key=${i.id} className="list-group-item py-2">
                <${Link} para=${`/indicadores/${i.id}`} className="fw-semibold">${i.nome}<//>
                ${(() => {
                  const detalhe = [i.eixo, grupo.categoria === 'DESATUALIZADO' && descreverSituacao(i.situacao)].filter(Boolean).join(' · ');
                  return html`<div className="small text-body-secondary detalhe" title=${detalhe}>${detalhe}</div>`;
                })()}
              </li>`)}
          </ul>`}
    </section>`;
}

function ResumoImpala({ indicadores }) {
  const contar = (s) => indicadores.filter((i) => situacaoImpala(i) === s).length;
  const ir = (filtro) => () => navegar(`/painel?impala=${filtro}`);
  return html`
    <section className="mt-4" aria-labelledby="titulo-impala">
      <h2 id="titulo-impala" className="secao-titulo">Comparação com o Impala</h2>
      <p className="text-body-secondary small mb-3">
        A última consulta de cada tabela no Impala (via Hue) é comparada com os dados do sistema. Clique num número
        para ver os indicadores no painel.
      </p>
      <${CartoesResumo} rotulo="Comparação com o Impala" itens=${[
        { valor: contar('ATUALIZADO'), rotulo: 'sistema igual ao Impala', tom: 'sucesso', aoClicar: ir('ATUALIZADO') },
        { valor: contar('DESATUALIZADO'), rotulo: 'sistema diferente do Impala', tom: 'perigo', aoClicar: ir('DESATUALIZADO') },
        { valor: contar('SEM_COMPARACAO'), rotulo: 'sem comparação', tom: 'neutro', aoClicar: ir('SEM_COMPARACAO') },
      ]} />
    </section>`;
}

export function Inicio() {
  const { dados, erro, carregando } = useConsulta(api.indicadores, []);
  const indicadores = dados?.indicadores ?? [];
  const grupos = GRUPOS.map((g) => ({
    ...g,
    itens: indicadores.filter((i) => categoriaDe(i) === g.categoria).sort((a, b) => comparar(a.nome, b.nome)),
  }));

  return html`
    <${Pagina}
      titulo="Situação dos indicadores"
      tituloAba="Início"
      subtitulo=${dados ? `${plural(indicadores.length, 'indicador', 'indicadores')} da Estratégia Catarinense de Desenvolvimento` : 'Estratégia Catarinense de Desenvolvimento'}
      faixaExtra=${dados && html`<${BarraProporcao} grupos=${grupos} total=${indicadores.length} />`}
      acoes=${html`<${Link} para="/painel" className="btn btn-destaque">Abrir painel de indicadores <span aria-hidden="true">→</span><//>`}>
      ${carregando && !dados && html`<${Carregando} />`}
      ${erro && html`<${Erro} erro=${erro} />`}
      ${dados && html`
        <div className="row g-3">
          ${grupos.map((g) => html`
            <div key=${g.categoria} className="col-12 col-lg-4">
              <${CartaoGrupo} grupo=${g} total=${indicadores.length} />
            </div>`)}
        </div>
        <${ResumoImpala} indicadores=${indicadores} />`}
    <//>`;
}
