// Fixa o timezone para datas determinísticas nos testes (date-fns usa o fuso local).
process.env.TZ = "UTC";

import "@testing-library/jest-dom";

// Polyfill fetch (jsdom) — LoginPage e outras telas chamam fetch no mount.
globalThis.fetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    json: async () => ({ google: { id: "google", name: "Google" } }),
    text: async () => "",
  }),
);

// Polyfills para componentes Radix (Select, Dialog) em jsdom, que não
// implementa Pointer Capture nem scrollIntoView nem matchMedia/ResizeObserver.
if (typeof window !== "undefined") {
  window.HTMLElement.prototype.scrollIntoView = jest.fn();
  window.HTMLElement.prototype.hasPointerCapture = jest.fn();
  window.HTMLElement.prototype.releasePointerCapture = jest.fn();

  if (!window.matchMedia) {
    window.matchMedia = jest.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }));
  }

  if (!window.ResizeObserver) {
    window.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
}
