// Barra superior branca (como a do Avança SC): marca, navegação principal e notificações.
import { html } from '../lib.js';
import { Link } from '../rotas.js';
import { Notificacoes } from './Notificacoes.js';

const ITENS = [
  { para: '/', rotulo: 'Início', ativo: (c) => c === '/' },
  { para: '/painel', rotulo: 'Painel de indicadores', ativo: (c) => /^\/(painel|indicadores)/.test(c) },
];

export function Cabecalho({ caminho }) {
  return html`
    <header className="topo">
      <div className="container-xxl topo-interno px-3 px-lg-4">
        <${Link} para="/" className="marca">
          <span className="marca-simbolo" aria-hidden="true"></span>
          <span>Seplan Indicadores<small>Secretaria de Estado do Planejamento · SC</small></span>
        <//>
        <nav aria-label="Principal" className="flex-grow-1">
          <ul className="menu">
            ${ITENS.map((item) => {
              const ativo = item.ativo(caminho);
              return html`
                <li key=${item.para}>
                  <${Link} para=${item.para} aria-current=${ativo ? 'page' : undefined}>${item.rotulo}<//>
                </li>`;
            })}
          </ul>
        </nav>
        <${Notificacoes} caminho=${caminho} />
      </div>
    </header>`;
}

export function Rodape() {
  return html`
    <footer className="rodape">
      <div className="container-xxl rodape-interno px-3 px-lg-4">
        <p className="mb-0">
          O <strong>Seplan Indicadores</strong> acompanha a atualização dos indicadores da Estratégia Catarinense de
          Desenvolvimento, comparando os dados publicados no sistema com as tabelas do Impala.
          Versão preliminar.
        </p>
        <p className="mb-0">
          <strong>Avança SC</strong><br />
          <a href="https://avanca.sc.gov.br/" target="_blank" rel="noopener">avanca.sc.gov.br<span className="visually-hidden"> (abre em nova aba)</span></a>
        </p>
      </div>
      <div className="container-xxl rodape-copy px-3 px-lg-4">SEPLAN · Secretaria de Estado do Planejamento de Santa Catarina</div>
    </footer>`;
}
