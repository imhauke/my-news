import "@testing-library/jest-dom/vitest";

// jsdom has no IntersectionObserver; Motion's whileInView and impression tracking need one.
class ImmediateIntersectionObserver {
  constructor(private callback: IntersectionObserverCallback) {}
  observe(target: Element) {
    this.callback([{ isIntersecting: true, target } as IntersectionObserverEntry], this as unknown as IntersectionObserver);
  }
  unobserve() {}
  disconnect() {}
  takeRecords() { return []; }
}
globalThis.IntersectionObserver ??= ImmediateIntersectionObserver as unknown as typeof IntersectionObserver;
