// Componente raiz: link de pular conteúdo, cabeçalho e a tela da rota atual.
import { Component, html, useEffect, useRef } from './lib.js';
import { Link, useCaminho, useTitulo } from './rotas.js';
import { Cabecalho } from './componentes/Cabecalho.js';
import { Painel } from './paginas/Painel.js';
import { DadosIndicador } from './paginas/DadosIndicador.js';

function NaoEncontrado() {
  useTitulo('Página não encontrada');
  return html`
    <h1 className="h3" tabIndex="-1">Página não encontrada</h1>
    <p><${Link} para="/">Voltar ao painel<//></p>`;
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
      <div className="alert alert-danger" role="alert">
        <h1 className="h5" tabIndex="-1">Não foi possível exibir esta tela</h1>
        <p className="mb-2">${this.state.erro.message}</p>
        <p className="mb-0">Se o servidor foi atualizado há pouco, reinicie o app (python app.py) e recarregue a página.
          <${Link} para="/" className="ms-1">Voltar ao painel<//></p>
      </div>`;
  }
}

function telaDa(caminho) {
  if (caminho === '/') return html`<${Painel} />`;
  const indicador = caminho.match(/^\/indicadores\/(\d+)\/?$/);
  if (indicador) return html`<${DadosIndicador} key=${indicador[1]} id=${indicador[1]} />`;
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
    <main id="conteudo" tabIndex="-1" className="container-fluid py-3 px-3 px-lg-4">
      <${BarreiraDeErro} key=${caminho}>${telaDa(caminho)}<//>
    </main>
    <footer className="container-fluid px-3 px-lg-4 pb-3 small text-body-secondary">Seplan Indicadores · versão preliminar</footer>`;
}
