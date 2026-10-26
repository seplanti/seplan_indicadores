"""Caminhos e constantes do projeto."""

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
