// Barra superior: marca, navegação principal e notificações.
import { html } from '../lib.js';
import { Link } from '../rotas.js';
import { Notificacoes } from './Notificacoes.js';

export function Cabecalho({ caminho }) {
  const painelAtivo = caminho === '/';
  return html`
    <header>
      <nav className="navbar navbar-expand navbar-dark bg-seplan" aria-label="Principal">
        <div className="container-fluid flex-wrap gap-2 px-3 px-lg-4">
          <${Link} para="/" className="navbar-brand fw-semibold">Seplan Indicadores<//>
          <ul className="navbar-nav me-auto">
            <li className="nav-item">
              <${Link} para="/" className=${`nav-link${painelAtivo ? ' active' : ''}`}
                       aria-current=${painelAtivo ? 'page' : undefined}>Painel<//>
            </li>
          </ul>
          <${Notificacoes} caminho=${caminho} />
        </div>
      </nav>
    </header>`;
}
