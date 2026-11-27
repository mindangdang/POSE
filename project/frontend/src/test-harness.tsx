import React from 'react';
import ReactDOM from 'react-dom/client';

import { GenericSearchPage } from './features/generic-search/GenericSearchPage';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <GenericSearchPage onUseLegacy={() => undefined} />,
);
