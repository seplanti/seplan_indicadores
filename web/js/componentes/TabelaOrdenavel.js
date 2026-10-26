// Tabela com ordenação por coluna (clique no cabeçalho), usada no painel e nos dados do indicador.
//
// colunas: [{ chave, titulo, valor?(linha), celula?(linha), numerica?, classe? }]
//   valor  — valor usado na ordenação (padrão: linha[chave])
//   celula — conteúdo exibido (padrão: o próprio valor)
import { html, useMemo, useState } from '../lib.js';
import { comparar } from '../formato.js';

const vazio = (v) => v === null || v === undefined || v === '';

function compararValores(a, b) {
  if (vazio(a) || vazio(b)) return vazio(a) - vazio(b);
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return comparar(a, b);
}

export function TabelaOrdenavel({ id, legenda, colunas, linhas, chaveLinha }) {
  const [ordem, setOrdem] = useState(null); // { chave, crescente }

  const valorDe = (coluna) => coluna.valor ?? ((linha) => linha[coluna.chave]);

  const ordenadas = useMemo(() => {
    if (!ordem) return linhas;
    const valor = valorDe(colunas.find((c) => c.chave === ordem.chave));
    const sinal = ordem.crescente ? 1 : -1;
    return [...linhas].sort((a, b) => sinal * compararValores(valor(a), valor(b)));
  }, [linhas, colunas, ordem]);

  const alternar = (chave) => setOrdem((atual) => ({
    chave,
    crescente: atual?.chave === chave ? !atual.crescente : true,
  }));

  const cabecalho = (coluna) => {
    const ativa = ordem?.chave === coluna.chave;
    const sentido = ativa && (ordem.crescente ? 'ascending' : 'descending');
    return html`
      <th key=${coluna.chave} scope="col" aria-sort=${sentido || undefined}
          className=${coluna.numerica ? 'text-end' : undefined}>
        <button type="button" className="btn-ordenar" onClick=${() => alternar(coluna.chave)}>
          ${coluna.titulo}
          <span aria-hidden="true" className="seta">${ativa ? (ordem.crescente ? ' ▲' : ' ▼') : ''}</span>
        </button>
      </th>`;
  };

  return html`
    <div className="tabela-wrap" tabIndex="0" role="region" aria-labelledby=${`${id}-legenda`}>
      <table className="table table-hover table-sm mb-0" id=${id}>
        <caption id=${`${id}-legenda`} className="caption-top px-2">${legenda}</caption>
        <thead><tr>${colunas.map(cabecalho)}</tr></thead>
        <tbody>
          ${ordenadas.map((linha) => html`
            <tr key=${chaveLinha(linha)}>
              ${colunas.map((c) => html`
                <td key=${c.chave} className=${[c.numerica && 'text-end num', c.classe].filter(Boolean).join(' ') || undefined}>
                  ${c.celula ? c.celula(linha) : valorDe(c)(linha)}
                </td>`)}
            </tr>`)}
        </tbody>
      </table>
    </div>`;
}
