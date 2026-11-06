// Componente raiz: link de pular conteúdo, cabeçalho e a tela da rota atual.
import { Component, html, useEffect, useRef } from './lib.js';
import { Link, useCaminho } from './rotas.js';
import { Cabecalho, Rodape } from './componentes/Cabecalho.js';
import { Pagina } from './componentes/Pagina.js';
import { Inicio } from './paginas/Inicio.js';
import { Painel } from './paginas/Painel.js';
import { DadosIndicador } from './paginas/DadosIndicador.js';
import { ConsultaImpala } from './paginas/ConsultaImpala.js';

function NaoEncontrado() {
  return html`
    <${Pagina} titulo="Página não encontrada" subtitulo="O endereço não corresponde a nenhuma tela do Seplan Indicadores.">
      <${Link} para="/" className="btn btn-primary">Voltar ao início<//>
    <//>`;
}

// Um erro ao desenhar a tela mostra um aviso no lugar dela, em vez de apagar a página inteira.
// `key` (o caminho) recria a barreira ao trocar de tela, limpando o erro anterior.
class BarreiraDeErro extends Component {
  constructor(props) {
    super(props);
    this.state = { erro: null };
  }

  static getDerivedStateFromError(erro) {
    return { erro };
  }

  componentDidCatch(erro, info) {
    console.error(erro, info.componentStack);
  }

  render() {
    if (!this.state.erro) return this.props.children;
    return html`
      <div className="container-xxl corpo px-3 px-lg-4"><div className="alert alert-danger" role="alert">
        <h1 className="h5" tabIndex="-1">Não foi possível exibir esta tela</h1>
        <p className="mb-2">${this.state.erro.message}</p>
        <p className="mb-0">Se o servidor foi atualizado há pouco, reinicie o app (python app.py) e recarregue a página.
          <${Link} para="/" className="ms-1">Voltar ao início<//></p>
      </div></div>`;
  }
}

function telaDa(caminho) {
  if (caminho === '/') return html`<${Inicio} />`;
  if (/^\/painel\/?$/.test(caminho)) return html`<${Painel} />`;
  const indicador = caminho.match(/^\/indicadores\/(\d+)\/?$/);
  if (indicador) return html`<${DadosIndicador} key=${indicador[1]} id=${indicador[1]} />`;
  const impala = caminho.match(/^\/indicadores\/(\d+)\/impala\/?$/);
  if (impala) return html`<${ConsultaImpala} key=${impala[1]} id=${impala[1]} />`;
  return html`<${NaoEncontrado} />`;
}

export function App() {
  const caminho = useCaminho();
  const primeiraTela = useRef(true);

  // Ao trocar de tela, volta ao topo e leva o foco ao título da nova tela.
  useEffect(() => {
    if (primeiraTela.current) {
      primeiraTela.current = false;
      return;
    }
    window.scrollTo(0, 0);
    document.querySelector('#conteudo h1')?.focus();
  }, [caminho]);

  return html`
    <a className="visually-hidden-focusable pular-conteudo" href="#conteudo">Pular para o conteúdo</a>
    <${Cabecalho} caminho=${caminho} />
    <main id="conteudo" tabIndex="-1" className="flex-grow-1">
      <${BarreiraDeErro} key=${caminho}>${telaDa(caminho)}<//>
    </main>
    <${Rodape} />`;
}
