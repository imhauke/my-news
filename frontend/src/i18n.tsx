import { createContext, useContext } from "react";
import type { Lang } from "./types";

const es = {
  langGroup: "Idioma",
  themeGroup: "Tema",
  themeLight: "Claro",
  themeDark: "Oscuro",
  themeSystem: "Automático",
  footerLinks: "Enlaces",
  ourSources: "Nuestras fuentes",
  sources: {
    title: "Nuestras fuentes",
    intro:
      "MyNews reúne tres fuentes elegidas por dos razones: buscamos imparcialidad, hechos contados sin tomar partido, y una cobertura a la vez amplia y concreta. Juntas cubren la actualidad mundial, la tecnología explicada a fondo y lo que la comunidad de ingenieros está debatiendo.",
    items: [
      {
        name: "Reuters",
        sections: "Mundo y Tecnología",
        text: "Agencia de noticias internacional fundada en 1851. Sus Principios de Confianza la obligan a informar con independencia, integridad y sin sesgos, y sus despachos son la base de miles de medios de todo el espectro. Aporta hechos de primera mano y verificados, sin opinión, con corresponsales en todo el mundo y gran rapidez cuando algo ocurre.",
      },
      {
        name: "Ars Technica",
        sections: "IA, Biz & IT y Seguridad",
        text: "Publicación especializada en tecnología desde 1998, escrita por periodistas con formación técnica y científica. Explica con profundidad lo que otros medios resumen en un titular, contrasta las afirmaciones de la industria y es conocida por su escepticismo ante el bombo. Da contexto y detalle en inteligencia artificial, empresa tecnológica y ciberseguridad.",
      },
      {
        name: "Hacker News",
        sections: "Portada del día",
        text: "Comunidad de Y Combinator en la que ingenieros, investigadores y fundadores comparten y votan noticias. Usamos su portada del día anterior: una selección hecha por la propia comunidad técnica, sin algoritmo publicitario, con menos ruido que la portada en directo. Sus debates suman perspectivas de quienes trabajan en el tema, correcciones y recursos que no están en el artículo.",
      },
    ],
    closing:
      "Las tres se complementan: la agencia aporta los hechos con neutralidad, la prensa especializada la profundidad y la comunidad la mirada de quienes construyen la tecnología. MyNews solo muestra titulares, descripciones breves y enlaces: la noticia completa se lee siempre en su web original.",
  },
  dateline: (total: string, enriched: string) =>
    `${total} noticias de Reuters, Ars Technica y Hacker News; Gemini ha resumido y traducido ${enriched}.`,
  digestKinds: { general: "General", world: "Mundo", tech: "Tecnología" },
  digestGroup: "Tipo de resumen",
  important: "Lo importante hoy",
  latest: "Última hora",
  filterSource: "Filtrar por fuente",
  filterSection: "Filtrar por sección",
  all: "Todo",
  allOf: (source: string) => `Todo ${source}`,
  today: "Hoy",
  frontOf: (day: string) => `Portada de Hacker News del ${day}`,
  yesterday: "Ayer",
  minutesAgo: (n: number) => `hace ${n} min`,
  hoursAgo: (n: number) => `hace ${n} h`,
  daysAgo: (n: number) => `hace ${n} d`,
  points: (n: number) => `${n} ${n === 1 ? "punto" : "puntos"}`,
  comments: (n: number) => `${n} ${n === 1 ? "comentario" : "comentarios"}`,
  hideComments: "Ocultar discusión",
  replies: (n: number) => `${n} ${n === 1 ? "respuesta" : "respuestas"}`,
  deleted: "[eliminado]",
  read: "Leído",
  like: "Me interesa",
  dislike: "No me interesa",
  feedbackHint: "Tus valoraciones entrenarán tu feed «Para ti»",
  loadingNews: "Cargando noticias…",
  loadMore: "Cargar noticias anteriores",
  emptySource: "Aún no hay noticias aquí. Se actualizan cada 5 minutos.",
  feedError: (e: string) => `No se pudo cargar el feed: ${e}.`,
  retry: "Reintentar",
  loadingDiscussion: "Cargando y traduciendo la discusión…",
  loadingDiscussionEn: "Cargando la discusión…",
  discussionError: (e: string) => `No se pudo cargar la discusión: ${e}.`,
  noComments: "Este hilo todavía no tiene comentarios.",
  openOnHN: "Abrir el hilo en Hacker News",
  translatedNote: "Comentarios traducidos automáticamente con Gemini.",
  translating: "Mostrando el original mientras Gemini lo traduce…",
  expandPanel: "Leer a pantalla completa",
  collapsePanel: "Salir de pantalla completa",
  showOriginal: "Ver originales",
  showTranslation: "Ver traducción",
  untranslated: "Sin traducir todavía",
  discussionTitle: "Discusión en Hacker News",
  close: "Cerrar",
  colophon:
    "MyNews es código abierto con licencia MIT. Los titulares traducidos, las descripciones y la traducción de comentarios los genera Gemini y pueden contener errores: la noticia completa está siempre en su web original.",
};

type Dict = typeof es;

const en: Dict = {
  langGroup: "Language",
  themeGroup: "Theme",
  themeLight: "Light",
  themeDark: "Dark",
  themeSystem: "Automatic",
  footerLinks: "Links",
  ourSources: "Our sources",
  sources: {
    title: "Our sources",
    intro:
      "MyNews brings together three sources chosen for two reasons: we want impartiality, facts reported without taking sides, and coverage that is both broad and specific. Together they cover world affairs, technology explained in depth and what the engineering community is discussing.",
    items: [
      {
        name: "Reuters",
        sections: "World and Technology",
        text: "International news agency founded in 1851. Its Trust Principles commit it to independence, integrity and freedom from bias, and its wires underpin thousands of outlets across the spectrum. It brings first-hand, verified facts without opinion, with correspondents around the world and great speed when news breaks.",
      },
      {
        name: "Ars Technica",
        sections: "AI, Biz & IT and Security",
        text: "A technology publication since 1998, written by journalists with technical and scientific backgrounds. It explains in depth what other outlets reduce to a headline, checks industry claims and is known for its scepticism of hype. It adds context and detail on artificial intelligence, the tech business and cybersecurity.",
      },
      {
        name: "Hacker News",
        sections: "Daily front page",
        text: "Y Combinator's community, where engineers, researchers and founders share and vote on stories. We use its front page of the previous day: a selection made by the technical community itself, with no advertising algorithm and less noise than the live front page. Its discussions add the views of people who work on the subject, corrections and resources the article does not have.",
      },
    ],
    closing:
      "The three complement each other: the agency brings the facts with neutrality, specialist journalism the depth and the community the view of those who build the technology. MyNews only shows headlines, short descriptions and links: the full story is always read on the original site.",
  },
  dateline: (total, enriched) =>
    `${total} stories from Reuters, Ars Technica and Hacker News; Gemini has summarised and translated ${enriched}.`,
  digestKinds: { general: "General", world: "World", tech: "Technology" },
  digestGroup: "Overview",
  important: "Today's essentials",
  latest: "Latest",
  filterSource: "Filter by source",
  filterSection: "Filter by section",
  all: "All",
  allOf: (source) => `All ${source}`,
  today: "Today",
  frontOf: (day) => `Hacker News front page, ${day}`,
  yesterday: "Yesterday",
  minutesAgo: (n) => `${n} min ago`,
  hoursAgo: (n) => `${n} h ago`,
  daysAgo: (n) => `${n} d ago`,
  points: (n) => `${n} ${n === 1 ? "point" : "points"}`,
  comments: (n) => `${n} ${n === 1 ? "comment" : "comments"}`,
  hideComments: "Hide discussion",
  replies: (n) => `${n} ${n === 1 ? "reply" : "replies"}`,
  deleted: "[deleted]",
  read: "Read",
  like: "Interested",
  dislike: "Not interested",
  feedbackHint: "Your ratings will train your For You feed",
  loadingNews: "Loading stories…",
  loadMore: "Load earlier stories",
  emptySource: "No stories here yet. They are refreshed every 5 minutes.",
  feedError: (e) => `Couldn't load the feed: ${e}.`,
  retry: "Retry",
  loadingDiscussion: "Loading discussion…",
  loadingDiscussionEn: "Loading discussion…",
  discussionError: (e) => `Couldn't load the discussion: ${e}.`,
  noComments: "This thread has no comments yet.",
  openOnHN: "Open the thread on Hacker News",
  translatedNote: "Comments machine-translated with Gemini.",
  translating: "Showing the original while Gemini translates it…",
  expandPanel: "Read full screen",
  collapsePanel: "Exit full screen",
  showOriginal: "Show originals",
  showTranslation: "Show translation",
  untranslated: "Not translated yet",
  discussionTitle: "Hacker News discussion",
  close: "Close",
  colophon:
    "MyNews is open source under the MIT licence. Translated headlines, descriptions and comment translations are generated by Gemini and may contain mistakes: the full story is always on the original site.",
};

export const DICTS: Record<Lang, Dict> = { es, en };

export const SECTION_LABEL: Record<string, Record<Lang, string>> = {
  world: { es: "Mundo", en: "World" },
  technology: { es: "Tecnología", en: "Technology" },
  ai: { es: "IA", en: "AI" },
  "biz-it": { es: "Biz & IT", en: "Biz & IT" },
  security: { es: "Seguridad", en: "Security" },
  front: { es: "Portada", en: "Front page" },
};

export const LangContext = createContext<Lang>("es");
export const useLang = () => useContext(LangContext);
export const useT = () => DICTS[useLang()];
