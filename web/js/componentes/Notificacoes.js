// Botão de notificações do topo da tela, com painel que lista os indicadores desatualizados.
import { html, useEffect, useRef, useState } from '../lib.js';
import { api, useConsulta } from '../api.js';
import { formatarData, plural } from '../formato.js';
import { Link } from '../rotas.js';

const Sino = html`
  <svg aria-hidden="true" focusable="false" width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
    <path d="M8 16a2 2 0 0 0 2-2H6a2 2 0 0 0 2 2zm.995-14.901a1 1 0 1 0-1.99 0A5.002 5.002 0 0 0 3 6c0 1.098-.5 6-2 7h14c-1.5-1-2-5.902-2-7 0-2.42-1.72-4.44-4.005-4.901z"/>
  </svg>`;

// `caminho` faz a lista ser recarregada a cada troca de tela.
export function Notificacoes({ caminho }) {
  const { dados, erro } = useConsulta(api.notificacoes, [caminho]);
  const [aberto, setAberto] = useState(false);
  const raiz = useRef(null);
  const botao = useRef(null);
  const lista = dados?.notificacoes ?? [];

  useEffect(() => {
    if (!aberto) return undefined;
    const clicarFora = (e) => { if (!raiz.current.contains(e.target)) setAberto(false); };
    const teclar = (e) => {
      if (e.key !== 'Escape') return;
      setAberto(false);
      botao.current.focus();
    };
    document.addEventListener('mousedown', clicarFora);
    document.addEventListener('keydown', teclar);
    return () => {
      document.removeEventListener('mousedown', clicarFora);
      document.removeEventListener('keydown', teclar);
    };
  }, [aberto]);

  let conteudo;
  if (erro) {
    conteudo = html`<p className="p-3 mb-0 text-danger-emphasis">Não foi possível carregar as notificações: ${erro.message}</p>`;
  } else if (lista.length === 0) {
    conteudo = html`<p className="p-3 mb-0">Nenhuma notificação. Todos os indicadores estão atualizados.</p>`;
  } else {
    conteudo = html`
      <ul className="list-group list-group-flush">
        ${lista.map((n) => html`
          <li key=${n.id} className="list-group-item">
            <div className="small fw-semibold text-danger-emphasis">Dados desatualizados</div>
            <${Link} para=${`/indicadores/${n.indicador_id}`} className="fw-semibold" onClick=${() => setAberto(false)}>
              ${n.indicador}
            <//>
            <div className="small">Fonte: <span className="fonte-desatualizada">${n.fonte}</span></div>
            <div className="small">${n.mensagem}</div>
            ${n.desde && html`<div className="small text-body-secondary">Desde ${formatarData(n.desde)}</div>`}
          </li>`)}
      </ul>`;
  }

  return html`
    <div className="notificacoes" ref=${raiz}>
      <button ref=${botao} type="button" className="btn btn-outline-light d-inline-flex align-items-center gap-2"
              aria-expanded=${aberto} aria-controls="painel-notificacoes" onClick=${() => setAberto(!aberto)}>
        ${Sino}
        <span>Notificações</span>
        ${lista.length > 0 && html`
          <span className="badge rounded-pill text-bg-danger">
            ${lista.length}<span className="visually-hidden"> (${plural(lista.length, 'indicador desatualizado', 'indicadores desatualizados')})</span>
          </span>`}
      </button>
      ${aberto && html`
        <div id="painel-notificacoes" className="painel-notificacoes card shadow" role="region" aria-labelledby="titulo-notificacoes">
          <h2 id="titulo-notificacoes" className="card-header h6 mb-0">Notificações</h2>
          ${conteudo}
        </div>`}
    </div>`;
}
