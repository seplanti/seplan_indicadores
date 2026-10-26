// Acesso à API REST/JSON do back-end Python.
import { useEffect, useState } from './lib.js';

async function obter(caminho) {
  const resposta = await fetch(caminho, { headers: { Accept: 'application/json' } });
  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) throw new Error(corpo?.erro || `Erro ${resposta.status} ao consultar ${caminho}`);
  return corpo;
}

export const api = {
  indicadores: () => obter('/api/indicadores'),
  dados: (id) => obter(`/api/indicadores/${encodeURIComponent(id)}/dados`),
  notificacoes: () => obter('/api/notificacoes'),
};

export const urlJsonBruto = (id) => `/api/indicadores/${encodeURIComponent(id)}/json`;

// Executa `carregar` sempre que as dependências mudam e devolve { carregando, dados, erro }.
export function useConsulta(carregar, dependencias) {
  const [estado, setEstado] = useState({ carregando: true, dados: null, erro: null });
  useEffect(() => {
    let ativo = true;
    setEstado((anterior) => ({ ...anterior, carregando: true, erro: null }));
    carregar().then(
      (dados) => ativo && setEstado({ carregando: false, dados, erro: null }),
      (erro) => ativo && setEstado({ carregando: false, dados: null, erro }),
    );
    return () => { ativo = false; };
  }, dependencias);
  return estado;
}
