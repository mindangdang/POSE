declare module 'react-dom/client' {
  import { ReactNode } from 'react';

  export function createRoot(container: Element | Document | DocumentFragment | null): {
    render(children: ReactNode): void;
    unmount(): void;
  };
}