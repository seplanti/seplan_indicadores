// Tag de situação do indicador (atualizado, desatualizado ou sem dados). Texto + ícone, nunca só cor.
import { html } from '../lib.js';
import { formatarData } from '../formato.js';

// Rótulos de `categoria` (API): sem arquivo de dados prevalece sobre a situação de atualização.
export const ROTULO_CATEGORIA = { ATUALIZADO: 'Atualizado', DESATUALIZADO: 'Desatualizado', SEM_DADOS: 'Sem dados' };

const ESTILO_CATEGORIA = {
  ATUALIZADO: { icone: '✓', cores: 'text-success-emphasis bg-success-subtle border-success-subtle' },
  DESATUALIZADO: { icone: '⚠', cores: 'text-danger-emphasis bg-danger-subtle border-danger-subtle' },
  SEM_DADOS: { icone: '○', cores: 'text-secondary-emphasis bg-secondary-subtle border-secondary-subtle' },
};

export const estaDesatualizado = (indicador) => indicador.situacao.status === 'DESATUALIZADO';

// `categoria` vem da API; a mesma regra é repetida aqui para o caso de um servidor iniciado
// antes da mudança, que ainda não envia o campo.
export const categoriaDe = (indicador) => indicador.categoria
  ?? (indicador.tem_dados ? indicador.situacao.status : 'SEM_DADOS');

export function descreverSituacao(situacao) {
  return [situacao.motivo, situacao.desde && `desde ${formatarData(situacao.desde)}`].filter(Boolean).join(' — ');
}

export function StatusTag({ indicador }) {
  const categoria = categoriaDe(indicador);
  const { icone, cores } = ESTILO_CATEGORIA[categoria];
  const titulo = estaDesatualizado(indicador) ? descreverSituacao(indicador.situacao) : '';
  return html`
    <span className=${`badge border status-tag ${cores}`} title=${titulo || undefined}>
      <span aria-hidden="true">${icone}</span> ${ROTULO_CATEGORIA[categoria]}
    </span>`;
}

// Nome da fonte, em vermelho quando os dados do indicador estão desatualizados.
export function NomeFonte({ indicador }) {
  return html`<span className=${estaDesatualizado(indicador) ? 'fonte-desatualizada' : undefined}>${indicador.fonte}</span>`;
}
