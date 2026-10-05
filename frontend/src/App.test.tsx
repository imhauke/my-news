import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";
import App, { POLL_MS } from "./App";
import { reloadLocalState } from "./local";
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
  beforeEach(() => {
    localStorage.clear();
    reloadLocalState();
  });
  afterEach(() => vi.restoreAllMocks());

  it("renders everything in Spanish by default: headlines, descriptions, sections and UI", async () => {
    mockApi({
      "/feed/important": [lead],
      "/feed/latest": [hn],
      "/metrics": { articles_total: 240, articles_enriched: 240, last_ingest_at: null },
      "/digest": { text_es: "Hoy destaca la segunda vuelta en Brasil.", text_en: "Brazil heads to a runoff.",
                   article_ids: [2], created_at: "2026-10-05T12:00:00Z" },
    });
    render(<App />);
    const important = await screen.findByRole("region", { name: "Lo importante hoy" });
    expect(within(important).getByRole("link", { name: "Se reanudan las conversaciones en Ginebra" })).toBeInTheDocument();
    expect(await screen.findByText("Hoy destaca la segunda vuelta en Brasil.")).toBeInTheDocument();
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
    const sources = screen.getByRole("group", { name: "Filtrar por fuente" });
    fireEvent.click(within(sources).getByRole("button", { name: "Ars Technica" }));
    const sections = await screen.findByRole("group", { name: "Filtrar por sección" });
    fireEvent.click(within(sections).getByRole("button", { name: "Seguridad" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("source=ars") && c.url.includes("section=security"))).toBe(true));
    expect(within(sources).getByRole("button", { name: "Ars Technica" })).toHaveAttribute("aria-pressed", "true");
    expect(within(sections).getByRole("button", { name: "Todo" })).toBeInTheDocument();
  });

  it("shows Hacker News in /front order, grouped by day and numbered", async () => {
    const ranked = [
      { ...hn, id: 10, title_es: "Primera", hn_front_day: "2026-10-04", hn_front_rank: 1 },
      { ...hn, id: 11, title_es: "Segunda", hn_front_day: "2026-10-04", hn_front_rank: 2 },
    ];
    const calls = mockApi({ "/feed/latest": ranked });
    render(<App />);
    fireEvent.click(within(await screen.findByRole("group", { name: "Filtrar por fuente" })).getByRole("button", { name: "Hacker News" }));
    expect(await screen.findByRole("heading", { name: "Portada de Hacker News del 4 de octubre" })).toBeInTheDocument();
    expect(screen.getByText("1.")).toBeInTheDocument();
    expect(screen.getByText("2.")).toBeInTheDocument();
    expect(calls.some((c) => c.url.includes("source=hn"))).toBe(true);
  });

  it("stores a vote in this browser, sends it to the API and hides the controls for good", async () => {
    const calls = mockApi({ "/feed/latest": [hn] });
    const { unmount } = render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Me interesa" }));
    // the chosen thumb celebrates for a moment before the controls fold away
    await waitFor(() => expect(screen.queryByRole("button", { name: "Me interesa" })).not.toBeInTheDocument(),
      { timeout: 3000 });
    expect(screen.queryByRole("button", { name: "No me interesa" })).not.toBeInTheDocument();
    // the controls fade out in place: their slot stays so the meta line does not shift
    expect(document.querySelector(".feedback")).toHaveAttribute("aria-hidden", "true");

    const stored = JSON.parse(localStorage.getItem("mynews.votes.v1")!);
    expect(stored[hn.id]).toMatchObject({ value: 1, source: "hn", section: "front", topics: ["rust"] });
    expect(calls.filter((c) => c.method === "PUT").map((c) => JSON.parse(c.body!).value)).toEqual([1]);

    unmount();
    render(<App />); // a later visit: still rated, so no voting controls
    await screen.findByRole("link", { name: "Sale Rust 2.0" });
    expect(screen.queryByRole("button", { name: "Me interesa" })).not.toBeInTheDocument();
  });

  it("marks opened stories as read and remembers it", async () => {
    mockApi({ "/feed/latest": [hn] });
    const { unmount } = render(<App />);
    const link = await screen.findByRole("link", { name: "Sale Rust 2.0" });
    expect(screen.queryByText("Leído")).not.toBeInTheDocument();
    fireEvent.click(link);
    expect(await screen.findByText("Leído")).toBeInTheDocument();
    unmount();
    render(<App />);
    expect(await screen.findByText("Leído")).toBeInTheDocument();
  });

  it("applies an explicit light or dark theme over the system preference", async () => {
    mockApi({});
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Claro" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    fireEvent.click(screen.getByRole("button", { name: "Automático" }));
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("opens any story's thread in one non-modal side panel and switches threads in place", async () => {
    const other: Article = { ...hn, id: 7, title_es: "Otro hilo", hn_story_id: 77, hn_comment_count: 3 };
    mockApi({ "/feed/important": [hn], "/feed/latest": [other], "/comments": [] });
    render(<App />);
    const important = await screen.findByRole("region", { name: "Lo importante hoy" });

    // from the front lane
    fireEvent.click(within(important).getByRole("button", { name: /42 comentarios/ }));
    const panel = await screen.findByRole("complementary", { name: "Sale Rust 2.0" });
    expect(await within(panel).findByText("Este hilo todavía no tiene comentarios.")).toBeInTheDocument();
    expect(within(important).getByRole("button", { name: /42 comentarios/ })).toHaveAttribute("aria-expanded", "true");

    // the page is still usable: a story below opens its thread in the same panel
    fireEvent.click(screen.getByRole("button", { name: /3 comentarios/ }));
    expect(await screen.findByRole("complementary", { name: "Otro hilo" })).toBeInTheDocument();
    expect(screen.getAllByRole("complementary")).toHaveLength(1);

    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("complementary")).not.toBeInTheDocument());
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
