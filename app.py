"""Seplan Indicadores (versão preliminar).

Servidor Python que expõe a API REST/JSON (/api/...) com o catálogo
Dados/dados_de_base_indicadores-v5.json, as tabelas de Dados/tabelas_bi e a situação
de atualização de Dados/status_indicadores.json, e serve a interface React da pasta web/.

Uso:  python app.py [--porta 8000] [--sem-navegador]
"""

import argparse
import threading

from indicadores import config
from indicadores.api import ConsultaIndicadores
from indicadores.navegador import abrir_no_chrome
from indicadores.repositorio import CatalogoIndicadores, RegistroStatus
from indicadores.servidor import Aplicacao, ArquivosEstaticos, Servidor


def criar_aplicacao():
    catalogo = CatalogoIndicadores(config.ARQUIVO_INDICADORES, config.TABELAS_DIR)
    consulta = ConsultaIndicadores(catalogo, RegistroStatus(config.ARQUIVO_STATUS))
    return Aplicacao(consulta, ArquivosEstaticos(config.WEB_DIR))


def main():
    parser = argparse.ArgumentParser(description="Visualizador de indicadores SEPLAN")
    parser.add_argument("--porta", type=int, default=config.PORTA_PADRAO)
    parser.add_argument("--sem-navegador", action="store_true", help="não abre o Chrome")
    args = parser.parse_args()

    servidor = Servidor(criar_aplicacao(), config.HOST, args.porta)
    print(f"Servidor em {servidor.url}  (Ctrl+C para encerrar)")
    if not args.sem_navegador:
        threading.Timer(0.5, abrir_no_chrome, args=(servidor.url,)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
