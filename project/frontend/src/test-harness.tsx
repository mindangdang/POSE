import React from 'react';
import ReactDOM from 'react-dom/client';

import { GenericSearchPage } from './components/tabs/Search/GenericSearchPage';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <GenericSearchPage onUseLegacy={() => undefined} />,
);
