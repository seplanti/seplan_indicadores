// Tag de situação de atualização do indicador. Texto + ícone, nunca só cor.
import { html } from '../lib.js';
import { formatarData } from '../formato.js';

export const ROTULO_STATUS = { ATUALIZADO: 'Atualizado', DESATUALIZADO: 'Desatualizado' };

export const estaDesatualizado = (indicador) => indicador.situacao.status === 'DESATUALIZADO';

export function descreverSituacao(situacao) {
  return [situacao.motivo, situacao.desde && `desde ${formatarData(situacao.desde)}`].filter(Boolean).join(' — ');
}

export function StatusTag({ situacao }) {
  const desatualizado = situacao.status === 'DESATUALIZADO';
  const cores = desatualizado
    ? 'text-danger-emphasis bg-danger-subtle border-danger-subtle'
    : 'text-success-emphasis bg-success-subtle border-success-subtle';
  return html`
    <span className=${`badge border status-tag ${cores}`} title=${(desatualizado && descreverSituacao(situacao)) || undefined}>
      <span aria-hidden="true">${desatualizado ? '⚠' : '✓'}</span> ${ROTULO_STATUS[situacao.status]}
    </span>`;
}

// Nome da fonte, em vermelho quando os dados do indicador estão desatualizados.
export function NomeFonte({ indicador }) {
  return html`<span className=${estaDesatualizado(indicador) ? 'fonte-desatualizada' : undefined}>${indicador.fonte}</span>`;
}
