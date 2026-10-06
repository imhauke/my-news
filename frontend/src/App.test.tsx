import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";
import App, { POLL_MS } from "./App";
import { resetConsent } from "./consent";
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
    const route = key ? routes[key] : [];
    return typeof route === "function" ? (route as () => Response)() : new Response(JSON.stringify(route));
  });
  return calls;
}

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem("mynews.consent.v1", "declined"); // a returning reader who already chose
    reloadLocalState();
    resetConsent();
  });
  afterEach(() => vi.restoreAllMocks());

  it("renders everything in Spanish by default: headlines, descriptions, sections and UI", async () => {
    mockApi({
      "/feed/important": [lead],
      "/feed/latest": [hn],
      "/metrics": { articles_total: 240, articles_enriched: 240, last_ingest_at: null },
      "/digest": { kind: "general", text_es: "Hoy destaca la segunda vuelta en Brasil. En tecnología, Rust 2.0.",
                   text_en: "Brazil heads to a runoff. In tech, Rust 2.0.", article_ids: [2, 1],
                   created_at: "2026-10-05T12:00:00Z" },
    });
    render(<App />);
    const important = await screen.findByRole("region", { name: "Lo importante hoy" });
    expect(within(important).getByRole("link", { name: "Se reanudan las conversaciones en Ginebra" })).toBeInTheDocument();
    const overview = await screen.findByText("Hoy destaca la segunda vuelta en Brasil. En tecnología, Rust 2.0.");
    await waitFor(() => expect(overview).toBeVisible(), { timeout: 2000 }); // once the masthead has entered
    // one brief, labelled as a summary of the stories below, with no selector
    expect(screen.getByText("lo esencial de las noticias de abajo", { exact: false })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /resumen/i })).not.toBeInTheDocument();
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
    // (the list is remounted when the HN page arrives, so look again until it settles)
    await waitFor(() => expect(screen.getByRole("heading", { name: "Portada de Hacker News del 4 de octubre" })).toBeInTheDocument());
    expect(screen.getByText("1.")).toBeInTheDocument();
    expect(screen.getByText("2.")).toBeInTheDocument();
    expect(calls.some((c) => c.url.includes("source=hn"))).toBe(true);
  });

  it("asks first-time readers about personalisation and remembers the answer", async () => {
    localStorage.removeItem("mynews.consent.v1");
    resetConsent();
    mockApi({});
    const { unmount } = render(<App />);
    const note = await screen.findByRole("complementary", { name: "Nota al lector" }, { timeout: 3000 });
    fireEvent.click(within(note).getByRole("button", { name: "Ahora no" }));
    await waitFor(() => expect(screen.queryByRole("complementary", { name: "Nota al lector" })).not.toBeInTheDocument());
    expect(localStorage.getItem("mynews.consent.v1")).toBe("declined");
    unmount();
    render(<App />); // a later visit: not asked again
    await new Promise((r) => setTimeout(r, 1500));
    expect(screen.queryByRole("complementary", { name: "Nota al lector" })).not.toBeInTheDocument();
  });

  it("stores a vote in this browser and only sends it to the API once the reader agrees", async () => {
    localStorage.removeItem("mynews.consent.v1");
    resetConsent();
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
    // without consent nothing identifies the reader: no session, no rating on the server
    expect(calls.some((c) => c.url.endsWith("/session") || c.method === "PUT")).toBe(false);
    // agreeing in the note uploads the earlier rating
    const note = await screen.findByRole("complementary", { name: "Nota al lector" }, { timeout: 3000 });
    fireEvent.click(within(note).getByRole("button", { name: "Sí, personalizar" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT").map((c) => JSON.parse(c.body!).value)).toEqual([1]));
    expect(calls.some((c) => c.url.endsWith("/session") && c.method === "POST")).toBe(true);
    expect(localStorage.getItem("mynews.consent.v1")).toBe("granted");
    await waitFor(() => expect(screen.queryByRole("complementary", { name: "Nota al lector" })).not.toBeInTheDocument());

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

  it("answers questions about a story in the side panel, streaming the reply", async () => {
    const reuters: Article = { ...lead, id: 3 };
    const answer = [
      'event: delta\ndata: {"text": "El **Nobel** se concede"}\n\n',
      'event: delta\ndata: {"text": " cada año.\\n\\n- Química\\n- Física"}\n\n',
      'event: done\ndata: {"model": "lite"}\n\n',
    ].join("");
    let reply: () => Response = () => new Response(answer, { headers: { "content-type": "text/event-stream" } });
    const calls = mockApi({ "/feed/latest": [reuters], "/chat": () => reply() });
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Preguntar a la IA sobre esta noticia" }));
    const panel = await screen.findByRole("complementary", { name: "Se reanudan las conversaciones en Ginebra" });
    expect(within(panel).getByText("Pregunta sobre la noticia")).toBeInTheDocument();

    fireEvent.click(within(panel).getByRole("button", { name: "¿Por qué es importante?" }));
    expect(await within(panel).findByText("Nobel")).toHaveProperty("tagName", "STRONG");
    expect(within(panel).getByText("Física")).toBeInTheDocument(); // list item
    const sent = JSON.parse(calls.find((c) => c.url.endsWith("/articles/3/chat"))!.body!);
    expect(sent).toEqual({ messages: [{ role: "user", text: "¿Por qué es importante?" }], lang: "es" });

    // a follow-up carries the conversation; a refusal from the server is explained in place
    reply = () => new Response(JSON.stringify({ detail: "rate_limited" }), { status: 429 });
    const box = within(panel).getByRole("textbox", { name: "Escribe tu pregunta…" });
    fireEvent.change(box, { target: { value: "¿Y quién lo decide?" } });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(await within(panel).findByRole("alert")).toHaveTextContent("Has hecho muchas preguntas seguidas");
    const followUp = JSON.parse(calls.filter((c) => c.url.endsWith("/chat")).at(-1)!.body!);
    expect(followUp.messages.map((m: { role: string }) => m.role)).toEqual(["user", "model", "user"]);
  });

  it("shows what the community says above a Hacker News thread", async () => {
    const insight = {
      tone: "divided", summary_en: "Split on the licence.", summary_es: "Opiniones divididas sobre la licencia.",
      points: [{ title_en: "Licence", title_es: "Licencia", text_en: "Some like it.", text_es: "A unos les gusta." }],
      contributions: [{ author: "ada", text_en: "Ran it in prod.", text_es: "Lo usó en producción." }],
      resources: [{ title: "Benchmarks", url: "https://bench.example/run" }],
      comments_covered: 120, created_at: "2026-10-06T10:00:00Z",
    };
    // (another id than the other tests: insights are cached per story for a couple of minutes)
    mockApi({ "/feed/latest": [{ ...hn, id: 21 }], "/insight": insight, "/comments": [] });
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /42 comentarios/ }));
    const card = await screen.findByRole("region", { name: "Lo que dice la comunidad" });
    expect(within(card).getByText("Dividida")).toBeInTheDocument();
    expect(within(card).getByText("Opiniones divididas sobre la licencia.")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: /Benchmarks/ })).toHaveAttribute("href", "https://bench.example/run");
    expect(within(card).getByText(/120 comentarios/)).toBeInTheDocument();
  });

  it("searches by meaning and goes back to the timeline when cleared", async () => {
    const result: Article = { ...lead, id: 8, title_es: "Brasil irá a segunda vuelta" };
    const calls = mockApi({ "/feed/latest": [hn], "/search": [result] });
    render(<App />);
    await screen.findByRole("link", { name: "Sale Rust 2.0" });
    const box = screen.getByRole("searchbox", { name: "Buscar noticias" });
    fireEvent.change(box, { target: { value: "elecciones" } });
    fireEvent.submit(box.closest("form")!);
    expect(await screen.findByRole("heading", { name: "Resultados para «elecciones»" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("link", { name: "Brasil irá a segunda vuelta" })).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: "Sale Rust 2.0" })).not.toBeInTheDocument();
    expect(calls.some((c) => c.url.endsWith("/search?q=elecciones"))).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Borrar la búsqueda" }));
    expect(await screen.findByRole("link", { name: "Sale Rust 2.0" })).toBeInTheDocument();
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

  it("links the author's pages in the footer and explains the sources in a dialog", async () => {
    mockApi({});
    HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) { this.open = true; };
    render(<App />);
    const links = screen.getByRole("navigation", { name: "Enlaces" });
    expect(within(links).getByRole("link", { name: /GitHub/ })).toHaveAttribute("href", "https://github.com/imhauke/my-news");
    expect(within(links).getByRole("link", { name: /janguzman\.com/ })).toHaveAttribute("href", "https://janguzman.com");
    expect(screen.queryByRole("link", { name: /Código/ })).not.toBeInTheDocument(); // no longer in the masthead

    fireEvent.click(within(links).getByRole("button", { name: "Nuestras fuentes" }));
    const dialog = await screen.findByRole("dialog", { name: "Nuestras fuentes" });
    for (const name of ["Reuters", "Ars Technica", "Hacker News"]) {
      expect(within(dialog).getByRole("heading", { name })).toBeInTheDocument();
    }
    expect(within(dialog).getByText(/imparcialidad/)).toBeInTheDocument();
  });

  it("lets the reader withdraw consent from the privacy notice, which deletes their data", async () => {
    localStorage.setItem("mynews.consent.v1", "granted");
    resetConsent();
    const calls = mockApi({});
    HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) { this.open = true; };
    render(<App />);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/session") && c.method === "POST")).toBe(true));
    fireEvent.click(within(screen.getByRole("navigation", { name: "Enlaces" })).getByRole("button", { name: "Privacidad" }));
    const dialog = await screen.findByRole("dialog", { name: "Privacidad" });
    expect(within(dialog).getByText("La personalización está activada.")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Desactivar y borrar mis datos" }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/session") && c.method === "DELETE")).toBe(true));
    expect(within(dialog).getByText("La personalización está desactivada.")).toBeInTheDocument();
    expect(localStorage.getItem("mynews.consent.v1")).toBe("declined");
  });

  it("explains the failure and offers a retry when the API fails", async () => {
    mockApi({}, { failLatest: true });
    render(<App />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("HTTP 500");
    expect(within(alert).getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});
