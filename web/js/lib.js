// Ponte para as bibliotecas carregadas no index.html (React 18 UMD e htm).
// html`...` faz o papel do JSX sem precisar de etapa de build.
const { React, ReactDOM, htm } = window;

export const { Component, useEffect, useMemo, useRef, useState } = React;
export const html = htm.bind(React.createElement);
export { ReactDOM };
