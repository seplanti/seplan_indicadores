// Componentes pequenos reutilizados pelas telas.
import { html } from '../lib.js';

// Cartões de resumo. itens: [{ valor, rotulo, tom?: 'sucesso'|'perigo'|'neutro', texto?, aoClicar?, ativo? }]
// texto: valor textual (data, nome) — fonte menor e cartão mais largo.
// Com `aoClicar`, o cartão vira um botão de filtro (aria-pressed indica se está aplicado).
export function CartoesResumo({ itens, rotulo }) {
  return html`
    <ul className="cartoes-resumo" aria-label=${rotulo}>
      ${itens.map((item) => {
        const classe = `cartao-numero${item.tom ? ` tom-${item.tom}` : ''}${item.texto ? ' cartao-texto' : ''}`;
        const conteudo = html`<span className="valor">${item.valor}</span><span className="rotulo">${item.rotulo}</span>`;
        return html`
          <li key=${item.rotulo} className=${item.texto ? 'item-largo' : undefined}>
            ${item.aoClicar
              ? html`<button type="button" className=${classe} aria-pressed=${Boolean(item.ativo)} onClick=${item.aoClicar}
                             title=${item.ativo ? 'Clique para remover o filtro' : 'Clique para filtrar'}>${conteudo}</button>`
              : html`<div className=${classe}>${conteudo}</div>`}
          </li>`;
      })}
    </ul>`;
}

export function Carregando({ texto = 'Carregando…' }) {
  return html`
    <div className="d-flex align-items-center gap-2 my-3">
      <div className="spinner-border spinner-border-sm text-success" role="status">
        <span className="visually-hidden">${texto}</span>
      </div>
      <span aria-hidden="true">${texto}</span>
    </div>`;
}

export function Erro({ erro }) {
  return html`<div className="alert alert-danger" role="alert">Não foi possível carregar os dados: ${erro.message}</div>`;
}
