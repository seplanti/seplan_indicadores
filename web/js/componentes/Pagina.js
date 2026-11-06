// Estrutura comum das telas: faixa verde-petróleo com migalhas, título, tags e ações (como o hero do
// Avança SC) e, abaixo, o conteúdo da tela.
//
// migalhas: [{ para?, rotulo }] — o último item é a tela atual (sem link)
import { html } from '../lib.js';
import { Link, useTitulo } from '../rotas.js';

export function Pagina({ titulo, tituloAba, subtitulo, migalhas, tags, acoes, faixaExtra, children }) {
  useTitulo(tituloAba ?? titulo);
  return html`
    <section className="faixa" aria-labelledby="titulo-pagina">
      <div className="container-xxl faixa-interna px-3 px-lg-4">
        ${migalhas?.length > 0 && html`
          <nav aria-label="Você está em">
            <ol className="migalhas">
              ${migalhas.map((m, i) => html`
                <li key=${m.rotulo}>
                  ${m.para && i < migalhas.length - 1
                    ? html`<${Link} para=${m.para}>${m.rotulo}<//>`
                    : html`<span aria-current="page">${m.rotulo}</span>`}
                </li>`)}
            </ol>
          </nav>`}
        <div className="d-flex flex-wrap align-items-center gap-2 gap-md-3">
          <h1 id="titulo-pagina" tabIndex="-1">${titulo}</h1>
          ${tags}
        </div>
        ${subtitulo && html`<p className="subtitulo">${subtitulo}</p>`}
        ${faixaExtra}
        ${acoes && html`<div className="faixa-acoes">${acoes}</div>`}
      </div>
    </section>
    <div className="container-xxl corpo px-3 px-lg-4">${children}</div>`;
}
