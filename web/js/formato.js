// Formatação no padrão brasileiro.
const decimal = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const inteiro = new Intl.NumberFormat('pt-BR');
const data = new Intl.DateTimeFormat('pt-BR');

export const formatarDecimal = (valor) => (valor == null ? '' : decimal.format(valor));
export const formatarInteiro = (valor) => (valor == null ? '' : inteiro.format(valor));
// Inteiros sem casas decimais (contagens como população), demais com duas.
export const formatarNumero = (valor) => (Number.isInteger(valor) ? formatarInteiro(valor) : formatarDecimal(valor));

export function formatarData(iso) {
  if (!iso) return '';
  const valor = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(valor.getTime()) ? iso : data.format(valor);
}

export const plural = (n, singular, pluralTexto) => `${formatarInteiro(n)} ${n === 1 ? singular : pluralTexto}`;

export const comparar = (a, b) => String(a).localeCompare(String(b), 'pt-BR', { numeric: true });
