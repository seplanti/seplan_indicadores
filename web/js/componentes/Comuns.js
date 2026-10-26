// Componentes pequenos reutilizados pelas telas.
import { html } from '../lib.js';

// Cartões de resumo. itens: [{ valor, rotulo, classe? }]
export function CartoesResumo({ itens }) {
  return html`
    <ul className="cartoes-resumo list-unstyled d-flex flex-wrap gap-3 mb-3">
      ${itens.map((item) => html`
        <li key=${item.rotulo} className="card card-body py-2 px-3">
          <span className=${`valor ${item.classe ?? ''}`}>${item.valor}</span>
          <span className="small text-body-secondary">${item.rotulo}</span>
        </li>`)}
    </ul>`;
}

export function Carregando() {
  return html`
    <div className="d-flex align-items-center gap-2 my-3">
      <div className="spinner-border spinner-border-sm text-primary" role="status">
        <span className="visually-hidden">Carregando…</span>
      </div>
      <span aria-hidden="true">Carregando…</span>
    </div>`;
}

export function Erro({ erro }) {
  return html`<div className="alert alert-danger" role="alert">Não foi possível carregar os dados: ${erro.message}</div>`;
}
