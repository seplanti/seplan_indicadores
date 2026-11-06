// Tag de situação do indicador (atualizado, desatualizado ou sem dados). Texto + ícone, nunca só cor.
import { html } from '../lib.js';
import { formatarData } from '../formato.js';

// Rótulos de `categoria` (API): sem arquivo de dados prevalece sobre a situação de atualização.
export const ROTULO_CATEGORIA = { ATUALIZADO: 'Atualizado', DESATUALIZADO: 'Desatualizado', SEM_DADOS: 'Sem dados' };

const ESTILO_CATEGORIA = {
  ATUALIZADO: { icone: '✓', cores: 'tag-sucesso' },
  DESATUALIZADO: { icone: '⚠', cores: 'tag-perigo' },
  SEM_DADOS: { icone: '○', cores: 'tag-neutro' },
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
    <span className=${`status-tag ${cores}`} title=${titulo || undefined}>
      <span aria-hidden="true">${icone}</span> ${ROTULO_CATEGORIA[categoria]}
    </span>`;
}

// Comparação da última consulta ao Impala (Dados/tabelas_impala) com a tabela do sistema (tabelas_bi).
const TAGS_IMPALA = {
  ATUALIZADO: { texto: 'Atualizado', ...ESTILO_CATEGORIA.ATUALIZADO },
  SEM_CONSULTA: { texto: 'Sem consulta', ...ESTILO_CATEGORIA.SEM_DADOS },
};
const TAGS_SISTEMA = {
  ATUALIZADO: { texto: 'Atualizado', ...ESTILO_CATEGORIA.ATUALIZADO },
  DESATUALIZADO: { texto: 'Desatualizado', ...ESTILO_CATEGORIA.DESATUALIZADO },
  SEM_COMPARACAO: { texto: 'Sem comparação', ...ESTILO_CATEGORIA.SEM_DADOS },
};

export const ROTULO_IMPALA = {
  ATUALIZADO: 'Sistema igual ao Impala',
  DESATUALIZADO: 'Sistema diferente do Impala',
  SEM_COMPARACAO: 'Sem comparação',
};

// Situação do sistema frente ao Impala: ATUALIZADO, DESATUALIZADO, SEM_COMPARACAO ou null (sem tabela).
export const situacaoImpala = (indicador) => indicador.impala?.sistema.status ?? null;

// "2026-11-06T10:00:00" -> "06/11/2026 10:00"
export const formatarConsulta = (iso) => (iso ? `${formatarData(iso.slice(0, 10))} ${iso.slice(11, 16)}` : '');

function Tag({ estilo, origem, titulo }) {
  return html`
    <span className=${`status-tag ${estilo.cores}`} title=${titulo || undefined}>
      <span aria-hidden="true">${estilo.icone}</span> ${estilo.texto}/${origem}
    </span>`;
}

export function ImpalaTags({ impala }) {
  if (!impala) return html`<span className="status-tag tag-neutro" title="Indicador sem tabela_databricks no catálogo">Sem tabela no Impala</span>`;
  const consulta = impala.impala.consultado_em
    ? `Consultado em ${formatarConsulta(impala.impala.consultado_em)} (${impala.impala.linhas} linhas)`
    : 'O Impala ainda não foi consultado';
  return html`
    <span className="tags">
      <${Tag} estilo=${TAGS_IMPALA[impala.impala.status]} origem="Impala" titulo=${consulta} />
      <${Tag} estilo=${TAGS_SISTEMA[impala.sistema.status]} origem="Sistema" titulo=${impala.sistema.motivo} />
    </span>`;
}

// Nome da fonte, em vermelho quando os dados do indicador estão desatualizados.
export function NomeFonte({ indicador }) {
  return html`<span className=${estaDesatualizado(indicador) ? 'fonte-desatualizada' : undefined}>${indicador.fonte}</span>`;
}
