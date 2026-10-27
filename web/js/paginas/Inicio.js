// Tela inicial: quantos indicadores estão atualizados, desatualizados e sem dados, com a lista de cada grupo.
import { html } from '../lib.js';
import { api, useConsulta } from '../api.js';
import { comparar, plural } from '../formato.js';
import { Link, useTitulo } from '../rotas.js';
import { Carregando, Erro } from '../componentes/Comuns.js';
import { categoriaDe, descreverSituacao } from '../componentes/StatusTag.js';

// A ordem define a ordem dos cartões e dos trechos da barra de proporção.
const GRUPOS = [
  {
    categoria: 'ATUALIZADO', titulo: 'Atualizados', icone: '✓', classe: 'grupo-atualizado',
    descricao: 'Com arquivo de dados e sem pendência de atualização.',
    vazio: 'Nenhum indicador atualizado.',
  },
  {
    categoria: 'DESATUALIZADO', titulo: 'Desatualizados', icone: '⚠', classe: 'grupo-desatualizado',
    descricao: 'Com arquivo de dados, mas a fonte publicou dados mais recentes.',
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
    <div className="barra-proporcao mb-4" aria-hidden="true">
      ${grupos.filter((g) => g.itens.length).map((g) => html`
        <span key=${g.categoria} className=${g.classe} style=${{ flexGrow: g.itens.length }}
              title=${`${g.titulo}: ${g.itens.length} de ${total}`}></span>`)}
    </div>`;
}

function CartaoGrupo({ grupo, total }) {
  const id = `grupo-${grupo.categoria.toLowerCase()}`;
  return html`
    <section className=${`card h-100 cartao-grupo ${grupo.classe}`} aria-labelledby=${id}>
      <div className="card-body flex-grow-0 pb-2">
        <h2 id=${id} className="h6 text-uppercase mb-1">
          <span aria-hidden="true" className="me-1">${grupo.icone}</span>${grupo.titulo}
        </h2>
        <p className="mb-1">
          <span className="quantidade">${grupo.itens.length}</span>
          <span className="text-body-secondary ms-2">${percentual(grupo.itens.length, total)}% do total</span>
        </p>
        <p className="small text-body-secondary mb-0">${grupo.descricao}</p>
      </div>
      ${grupo.itens.length === 0
        ? html`<p className="px-3 pb-3 small text-body-secondary mb-0">${grupo.vazio}</p>`
        : html`
          <ul className="list-group list-group-flush lista-grupo" tabIndex="0" aria-label=${`Indicadores ${grupo.titulo.toLowerCase()}`}>
            ${grupo.itens.map((i) => html`
              <li key=${i.id} className="list-group-item py-2">
                <${Link} para=${`/indicadores/${i.id}`}>${i.nome}<//>
                <div className="small text-body-secondary">
                  ${[i.eixo, grupo.categoria === 'DESATUALIZADO' && descreverSituacao(i.situacao)].filter(Boolean).join(' · ')}
                </div>
              </li>`)}
          </ul>`}
    </section>`;
}

export function Inicio() {
  useTitulo('Início');
  const { dados, erro, carregando } = useConsulta(api.indicadores, []);
  const indicadores = dados?.indicadores ?? [];
  const grupos = GRUPOS.map((g) => ({
    ...g,
    itens: indicadores.filter((i) => categoriaDe(i) === g.categoria).sort((a, b) => comparar(a.nome, b.nome)),
  }));

  return html`
    <div className="d-flex flex-wrap align-items-start justify-content-between gap-3 mb-3">
      <div>
        <h1 className="h3 mb-1" tabIndex="-1">Situação dos indicadores</h1>
        <p className="text-body-secondary text-break mb-0">
          ${dados ? `${plural(indicadores.length, 'indicador', 'indicadores')} no catálogo ${dados.arquivo}` : ' '}
        </p>
      </div>
      <${Link} para="/painel" className="btn btn-primary btn-lg">Abrir painel de indicadores <span aria-hidden="true">→</span><//>
    </div>
    ${carregando && !dados && html`<${Carregando} />`}
    ${erro && html`<${Erro} erro=${erro} />`}
    ${dados && html`
      <${BarraProporcao} grupos=${grupos} total=${indicadores.length} />
      <div className="row g-3">
        ${grupos.map((g) => html`
          <div key=${g.categoria} className="col-12 col-lg-4">
            <${CartaoGrupo} grupo=${g} total=${indicadores.length} />
          </div>`)}
      </div>`}`;
}
