import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";
import App, { POLL_MS } from "./App";
import type { Article } from "./types";

const hn: Article = {
  id: 1, source: "hn", url: "https://example.com/a", title: "Rust 2.0 released", title_es: "Sale Rust 2.0",
  summary: "Raw excerpt", ai_summary_en: "Rust ships a new major version.",
  ai_summary_es: "Rust publica una nueva versión mayor.", section: "front", author: "pg",
  published_at: new Date().toISOString(), hn_points: 321, hn_comment_count: 42, topics: ["rust"],
  topics_es: ["rust"], hn_story_id: 99, feedback: 0,
};
const lead: Article = {
  ...hn, id: 2, source: "reuters", section: "world", title: "Talks resume in Geneva",
  title_es: "Se reanudan las conversaciones en Ginebra", hn_points: null, hn_comment_count: null, hn_story_id: null,
  ai_summary_es: "Las partes vuelven a negociar.", ai_summary_en: "The parties return to talks.",
};

type Routes = Record<string, unknown>;

function mockApi(routes: Routes, { failLatest = false } = {}) {
  const calls: { url: string; method: string; body?: string }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    calls.push({ url, method: init?.method ?? "GET", body: init?.body as string | undefined });
    if (failLatest && url.includes("/feed/latest")) return new Response("", { status: 500 });
    if (url.endsWith("/session")) return new Response(JSON.stringify({ user_id: 1 }));
    if (url.includes("/feedback")) return new Response(JSON.stringify({ feedback: JSON.parse(String(init?.body)).value }));
    const key = Object.keys(routes).find((k) => url.includes(k));
    return new Response(JSON.stringify(key ? routes[key] : []));
  });
  return calls;
}

describe("App", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it("renders everything in Spanish by default: headlines, descriptions, sections and UI", async () => {
    mockApi({
      "/feed/important": [lead],
      "/feed/latest": [hn],
      "/metrics": { articles_total: 240, articles_enriched: 240, last_ingest_at: null },
    });
    render(<App />);
    const important = await screen.findByRole("region", { name: "Lo importante hoy" });
    expect(within(important).getByRole("link", { name: "Se reanudan las conversaciones en Ginebra" })).toBeInTheDocument();
    expect(within(important).getByText("Mundo")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Sale Rust 2.0" })).toHaveAttribute("href", hn.url);
    expect(screen.getByText("Rust publica una nueva versión mayor.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /42 comentarios/ })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("es");
  });

  it("switches the whole interface to English and remembers it", async () => {
    mockApi({ "/feed/latest": [hn] });
    render(<App />);
    await screen.findByRole("link", { name: "Sale Rust 2.0" });
    fireEvent.click(screen.getByRole("button", { name: "English" }));
    expect(screen.getByRole("link", { name: "Rust 2.0 released" })).toBeInTheDocument();
    expect(screen.getByText("Rust ships a new major version.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Latest" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /42 comments/ })).toBeInTheDocument();
    expect(localStorage.getItem("mynews.lang")).toBe("en");
  });

  it("filters by source and then by section", async () => {
    const calls = mockApi({ "/feed/latest": [hn] });
    render(<App />);
    await screen.findByRole("link", { name: "Sale Rust 2.0" });
    fireEvent.click(screen.getByRole("button", { name: "Ars Technica" }));
    fireEvent.click(await screen.findByRole("button", { name: "Seguridad" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("source=ars") && c.url.includes("section=security"))).toBe(true));
    expect(screen.getByRole("button", { name: "Todo Ars Technica" })).toBeInTheDocument();
  });

  it("shows Hacker News in /front order, grouped by day and numbered", async () => {
    const ranked = [
      { ...hn, id: 10, title_es: "Primera", hn_front_day: "2026-10-04", hn_front_rank: 1 },
      { ...hn, id: 11, title_es: "Segunda", hn_front_day: "2026-10-04", hn_front_rank: 2 },
    ];
    const calls = mockApi({ "/feed/latest": ranked });
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Hacker News" }));
    expect(await screen.findByRole("heading", { name: "Portada de Hacker News del 4 de octubre" })).toBeInTheDocument();
    expect(screen.getByText("1.")).toBeInTheDocument();
    expect(screen.getByText("2.")).toBeInTheDocument();
    expect(calls.some((c) => c.url.includes("source=hn"))).toBe(true);
  });

  it("sends thumbs up, and a second click clears it", async () => {
    const calls = mockApi({ "/feed/latest": [hn] });
    render(<App />);
    const up = await screen.findByRole("button", { name: "Me interesa" });
    fireEvent.click(up);
    await waitFor(() => expect(up).toHaveAttribute("aria-pressed", "true"));
    fireEvent.click(up);
    await waitFor(() => expect(up).toHaveAttribute("aria-pressed", "false"));
    const bodies = calls.filter((c) => c.method === "PUT").map((c) => JSON.parse(c.body!).value);
    expect(bodies).toEqual([1, 0]);
  });

  it("applies an explicit light or dark theme over the system preference", async () => {
    mockApi({});
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Claro" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    fireEvent.click(screen.getByRole("button", { name: "Automático" }));
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("opens the discussion of a front-page HN story", async () => {
    mockApi({ "/feed/important": [hn], "/comments": [] });
    HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) { this.open = true; };
    render(<App />);
    const important = await screen.findByRole("region", { name: "Lo importante hoy" });
    fireEvent.click(within(important).getByRole("button", { name: /42 comentarios/ }));
    expect(await screen.findByText("Este hilo todavía no tiene comentarios.")).toBeInTheDocument();
  });

  it("refreshes itself while visible, adding new stories on top", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let latest: Article[] = [hn];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/session")) return new Response(JSON.stringify({ user_id: 1 }));
      return new Response(JSON.stringify(url.includes("/feed/latest") ? latest : []));
    });
    render(<App />);
    await screen.findByRole("link", { name: "Sale Rust 2.0" });
    latest = [{ ...hn, id: 5, title_es: "Noticia nueva" }, hn];
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(await screen.findByRole("link", { name: "Noticia nueva" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Sale Rust 2.0" })).toHaveLength(1);
    vi.useRealTimers();
  });

  it("explains the failure and offers a retry when the API fails", async () => {
    mockApi({}, { failLatest: true });
    render(<App />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("HTTP 500");
    expect(within(alert).getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});
