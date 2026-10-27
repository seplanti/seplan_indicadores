// Barra superior: marca, navegação principal e notificações.
import { html } from '../lib.js';
import { Link } from '../rotas.js';
import { Notificacoes } from './Notificacoes.js';

const ITENS = [
  { para: '/', rotulo: 'Início', ativo: (c) => c === '/' },
  { para: '/painel', rotulo: 'Painel de indicadores', ativo: (c) => /^\/painel\/?$/.test(c) },
];

export function Cabecalho({ caminho }) {
  return html`
    <header>
      <nav className="navbar navbar-expand navbar-dark bg-seplan" aria-label="Principal">
        <div className="container-fluid flex-wrap gap-2 px-3 px-lg-4">
          <${Link} para="/" className="navbar-brand fw-semibold">Seplan Indicadores<//>
          <ul className="navbar-nav flex-wrap me-auto">
            ${ITENS.map((item) => {
              const ativo = item.ativo(caminho);
              return html`
                <li key=${item.para} className="nav-item">
                  <${Link} para=${item.para} className=${`nav-link${ativo ? ' active' : ''}`}
                           aria-current=${ativo ? 'page' : undefined}>${item.rotulo}<//>
                </li>`;
            })}
          </ul>
          <${Notificacoes} caminho=${caminho} />
        </div>
      </nav>
    </header>`;
}
