"""Seplan Indicadores (versão preliminar).

Servidor Python que expõe a API REST/JSON (/api/...) com o catálogo
Dados/dados_de_base_indicadores-v5.json, as tabelas de Dados/tabelas_bi e a situação
de atualização de Dados/status_indicadores.json, e serve a interface React da pasta web/.
Também atende as rotas do Hue (/api/queries e /api/files), com credenciais do arquivo .env.

Uso:  python app.py [--porta 8000] [--sem-navegador]
"""

import argparse
import threading

from indicadores import config
from indicadores.api import ConsultaIndicadores
from indicadores.gateway import AplicacaoGateway, ClienteHue
from indicadores.navegador import abrir_no_chrome
from indicadores.repositorio import CatalogoIndicadores, RegistroStatus
from indicadores.servidor import Aplicacao, ArquivosEstaticos, Servidor


def criar_aplicacao():
    catalogo = CatalogoIndicadores(config.ARQUIVO_INDICADORES, config.TABELAS_DIR)
    consulta = ConsultaIndicadores(catalogo, RegistroStatus(config.ARQUIVO_STATUS))
    hue = ClienteHue(config.HUE_URL, config.HUE_USUARIO, config.HUE_SENHA)
    gateway = AplicacaoGateway(hue, config.HUE_DIALETO_PADRAO, config.HUE_BANCO_PADRAO,
                               config.HUE_LIMITE_MAXIMO, config.HUE_TEMPO_MAXIMO)
    return Aplicacao(consulta, ArquivosEstaticos(config.WEB_DIR), gateway)


def main():
    parser = argparse.ArgumentParser(description="Visualizador de indicadores SEPLAN")
    parser.add_argument("--porta", type=int, default=config.PORTA_PADRAO)
    parser.add_argument("--sem-navegador", action="store_true", help="não abre o Chrome")
    args = parser.parse_args()

    servidor = Servidor(criar_aplicacao(), config.HOST, args.porta)
    print(f"Servidor em {servidor.url}  (Ctrl+C para encerrar)")
    if config.HUE_USUARIO and config.HUE_SENHA:
        print(f"Hue: /api/queries e /api/files -> {config.HUE_URL} (usuário {config.HUE_USUARIO})")
    else:
        print(f"Aviso: HUE_USUARIO/HUE_SENHA vazios em {config.BASE_DIR / '.env'}; "
              "/api/queries e /api/files responderão 503.")
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
