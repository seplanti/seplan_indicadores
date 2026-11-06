"""Gateway local para a API do Hue (consultas Impala e arquivos do HDFS).

Roda em porta própria (padrão 8001) ao lado do painel (python app.py, porta 8000).
As credenciais vêm das variáveis de ambiente HUE_USUARIO e HUE_SENHA.

Uso:  python gateway.py [--porta 8000] [--hue-url https://...]
"""

import argparse
import os

from indicadores import config
from indicadores.gateway import AplicacaoGateway, CatalogoHue, ClienteHue, criar_servidor
from indicadores.impala import RepositorioImpala


def main():
    parser = argparse.ArgumentParser(description="Gateway local para a API do Hue")
    parser.add_argument("--porta", type=int, default=config.PORTA_GATEWAY)
    parser.add_argument("--hue-url", default=os.environ.get("HUE_URL", config.HUE_URL))
    args = parser.parse_args()

    hue = ClienteHue(args.hue_url, os.environ.get("HUE_USUARIO"), os.environ.get("HUE_SENHA"))
    if not (hue.usuario and hue.senha):
        print("Aviso: HUE_USUARIO/HUE_SENHA não definidos; as rotas responderão 503.")

    aplicacao = AplicacaoGateway(hue, config.HUE_DIALETO_PADRAO, config.HUE_BANCO_PADRAO,
                                 config.HUE_LIMITE_MAXIMO, config.HUE_TEMPO_MAXIMO,
                                 catalogo=CatalogoHue.carregar(config.ARQUIVO_ENDPOINTS_HUE),
                                 repositorio_impala=RepositorioImpala(config.TABELAS_IMPALA_DIR),
                                 limite_sincronizacao=config.HUE_LIMITE_SINCRONIZACAO)
    servidor = criar_servidor(aplicacao, config.HOST, args.porta)
    print(f"Gateway em {servidor.url} -> {hue.url_base}  (Ctrl+C para encerrar)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
