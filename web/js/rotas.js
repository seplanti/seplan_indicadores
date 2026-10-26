// Roteamento mínimo pela History API. O servidor devolve o index.html para
// qualquer caminho sem extensão, então /indicadores/1 pode ser aberto direto.
import { html, useEffect, useState } from './lib.js';

const EVENTO_NAVEGACAO = 'seplan:navegacao';

export function navegar(caminho) {
  history.pushState(null, '', caminho);
  window.dispatchEvent(new Event(EVENTO_NAVEGACAO));
}

export function useCaminho() {
  const [caminho, setCaminho] = useState(location.pathname);
  useEffect(() => {
    const atualizar = () => setCaminho(location.pathname);
    window.addEventListener('popstate', atualizar);
    window.addEventListener(EVENTO_NAVEGACAO, atualizar);
    return () => {
      window.removeEventListener('popstate', atualizar);
      window.removeEventListener(EVENTO_NAVEGACAO, atualizar);
    };
  }, []);
  return caminho;
}

// Título da aba no formato "Tela — Seplan Indicadores".
export function useTitulo(titulo) {
  useEffect(() => { document.title = `${titulo} — Seplan Indicadores`; }, [titulo]);
}

// <a> que navega sem recarregar a página; Ctrl/Shift+clique continuam abrindo em nova aba.
export function Link({ para, onClick, children, ...props }) {
  const aoClicar = (evento) => {
    onClick?.(evento);
    if (evento.button !== 0 || evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return;
    evento.preventDefault();
    navegar(para);
  };
  return html`<a href=${para} ...${props} onClick=${aoClicar}>${children}</a>`;
}
