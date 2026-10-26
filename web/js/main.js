import { html, ReactDOM } from './lib.js';
import { App } from './app.js';

ReactDOM.createRoot(document.getElementById('app')).render(html`<${App} />`);
