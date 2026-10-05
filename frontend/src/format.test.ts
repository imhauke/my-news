import { description, groupByDay, headline, timeAgo } from "./format";
import type { Article } from "./types";

const now = new Date("2026-10-05T12:00:00");

describe("timeAgo", () => {
  const t = now.getTime();
  it("formats minutes, hours and days in both languages", () => {
    expect(timeAgo(new Date(t - 30 * 60_000).toISOString(), "es", t)).toBe("hace 30 min");
    expect(timeAgo(new Date(t - 3 * 3_600_000).toISOString(), "en", t)).toBe("3 h ago");
    expect(timeAgo(new Date(t - 48 * 3_600_000).toISOString(), "es", t)).toBe("hace 2 d");
  });
  it("never goes negative for future dates", () => {
    expect(timeAgo(new Date(t + 5 * 60_000).toISOString(), "es", t)).toBe("hace 0 min");
  });
});

const art = (id: number, published_at: string, extra: Partial<Article> = {}): Article => ({
  id, source: "ars", url: "", title: "", title_es: null, summary: null, ai_summary_en: null, ai_summary_es: null,
  section: null, author: null, published_at, hn_points: null, hn_comment_count: null, topics: [], topics_es: [],
  hn_story_id: null, feedback: 0, ...extra,
});

describe("groupByDay", () => {
  it("groups consecutive articles under today, yesterday and named days", () => {
    const list = [
      art(1, "2026-10-05T10:00:00"), art(2, "2026-10-05T08:00:00"),
      art(3, "2026-10-04T22:00:00"), art(4, "2026-10-02T09:00:00"),
    ];
    expect(groupByDay(list, "es", now).map((g) => [g.label, g.items.length]))
      .toEqual([["Hoy", 2], ["Ayer", 1], ["Viernes, 2 de octubre", 1]]);
    expect(groupByDay(list, "en", now).map((g) => g.label)).toEqual(["Today", "Yesterday", "Friday 2 October"]);
  });
});

describe("headline and description", () => {
  it("use the chosen language and fall back to the original", () => {
    const a = art(1, "2026-10-05T10:00:00", { title: "Hi", title_es: "Hola", ai_summary_es: "es", summary: "raw" });
    expect([headline(a, "es"), headline(a, "en")]).toEqual(["Hola", "Hi"]);
    expect(headline({ ...a, title_es: null }, "es")).toBe("Hi");
    expect(description(a, "es")).toBe("es");
    expect(description(a, "en")).toBe("raw");
  });
});
