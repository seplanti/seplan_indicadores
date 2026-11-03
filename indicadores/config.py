"""Caminhos e constantes do projeto."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Dados
DADOS_DIR = BASE_DIR / "Dados"
ARQUIVO_INDICADORES = DADOS_DIR / "dados_de_base_indicadores-v5.json"
ARQUIVO_STATUS = DADOS_DIR / "status_indicadores.json"
ARQUIVO_MUNICIPIOS = DADOS_DIR / "municipios_sc.json"
TABELAS_DIR = DADOS_DIR / "tabelas_bi"

# Interface web (React), servida como arquivos estáticos
WEB_DIR = BASE_DIR / "web"

# Servidor
HOST = "127.0.0.1"
PORTA_PADRAO = 8000



def _carregar_env(arquivo):
    """Lê CHAVE=valor do .env sem sobrescrever variáveis já definidas no ambiente."""
    if not arquivo.is_file():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        chave, separador, valor = linha.strip().partition("=")
        if separador and not chave.startswith("#"):
            os.environ.setdefault(chave.strip(), valor.strip().strip("\"'"))


_carregar_env(BASE_DIR / ".env")

# API do Hue (Impala/HDFS): atendida pelo painel em /api/queries e /api/files e, se preferir,
# pelo gateway avulso (python gateway.py, porta 8001). Credenciais no .env (fora do git).
PORTA_GATEWAY = 8001
HUE_URL = os.environ.get("HUE_URL", "https://boavista-dados.ciasc.sc.gov.br")
HUE_USUARIO = os.environ.get("HUE_USUARIO")
HUE_SENHA = os.environ.get("HUE_SENHA")
HUE_DIALETO_PADRAO = os.environ.get("HUE_DIALETO", "impala")
HUE_BANCO_PADRAO = os.environ.get("HUE_BANCO", "seplan_avancasc")
HUE_LIMITE_MAXIMO = int(os.environ.get("HUE_LIMITE_MAXIMO", 10000))  # linhas por SELECT em /api/tabelas
HUE_TEMPO_MAXIMO = int(os.environ.get("HUE_TEMPO_MAXIMO", 120))  # segundos esperando a consulta
