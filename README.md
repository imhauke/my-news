# MyNews

Feed de noticias con IA, de código abierto. Agrega **Reuters** (World y Technology), **Ars Technica** (AI, Biz & IT y Security) y **Hacker News** (su [`/front`](https://news.ycombinator.com/front), el resumen de la portada del día anterior, con el árbol de comentarios de cada hilo) y, como objetivo principal, construye para cada usuario un feed **«Para ti»** personalizado que aprende de lo que le interesa.

> **Estado: fases 0–1 completas y fase 2 en curso (enriquecimiento con Gemini y «Lo importante hoy»).** El agregador funciona de extremo a extremo; el motor «Para ti», las evals, los experimentos, el servidor MCP y el agente de briefing están en la [hoja de ruta](#hoja-de-ruta).

## Arquitectura

```mermaid
flowchart LR
    R[Reuters<br/>RSS Google News] --> I
    A[Ars Technica<br/>RSS por sección] --> I
    H[Hacker News<br/>Firebase + Algolia] --> I
    subgraph VPS · Docker Compose
        I[Worker<br/>ingesta · APScheduler] --> DB[(PostgreSQL 16<br/>+ pgvector)]
        API[API FastAPI] --> DB
        C[Caddy · HTTPS] --> API
        C --> F[Frontend<br/>React + TS estáticos]
    end
    I -. fase 2+ .-> G[Gemini API<br/>free tier]
```

Solo Caddy expone puertos (80/443); PostgreSQL y la API viven en la red interna de Docker.

| Capa | Tecnología |
| --- | --- |
| Backend | Python 3.12 · FastAPI asíncrono · Pydantic · httpx · APScheduler |
| Frontend | TypeScript · React · Vite |
| Datos | PostgreSQL 16 + pgvector · Alembic |
| IA | Gemini API (free tier): Flash-Lite, Flash y Embedding, tras una interfaz común |
| Infra | Docker Compose · Caddy · GitHub Actions |

## Qué hay implementado

- **Ingesta concurrente e idempotente** de las tres fuentes (`httpx` con semáforo, timeouts y reintentos con espera exponencial). Upsert por `(fuente, id externo)`: repetir una ingesta no duplica nada.
- **Deduplicación** por URL normalizada y por similitud de titulares. Solo se guardan metadatos; el artículo completo se lee en la web original.
- **Comentarios de Hacker News** como árbol: descarga completa desde Algolia en varias pasadas (a las 2, 8, 24 y 48 h), upsert por id con marca de borrados y reconstrucción con consulta SQL recursiva.
- **Etapa 0 de enriquecimiento** (`app/enrich`): Gemini Flash-Lite procesa lotes de 25 noticias y devuelve, validado con Pydantic, el titular traducido, una descripción breve en inglés y en español, temas en ambos idiomas y una nota de relevancia global. Usa como contexto el extracto del RSS o la `og:description` de la página original. Cada artículo se procesa una sola vez; si se agota la cuota, lo pendiente espera a la siguiente ejecución.
- **Bilingüe de punta a punta**: la interfaz, los titulares, las descripciones, las secciones y los comentarios de HN cambian entre español e inglés. Los comentarios se traducen bajo demanda por tramos (en orden de lectura) y se guardan para no traducir nada dos veces.
- **Valoraciones para «Para ti»**: pulgar arriba/abajo en cada noticia. Cada navegador es un usuario anónimo (cookie HttpOnly, solo se guarda el hash del token); el estado vigente vive en `article_feedback` y cada cambio queda en `events`.
- **Comentarios bajo demanda**: un hilo que aún no se ha descargado se baja de Algolia la primera vez que alguien lo abre, y se refresca cada 10 min mientras sigue vivo (48 h).
- **API** (`/session`, `/feed/important`, `/feed/latest?source=&section=`, `/articles/{id}`, `/articles/{id}/feedback`, `/articles/{id}/comments?lang=`, `/events`, `/metrics`, `/health`) y **frontend** editorial: portada «Lo importante hoy» (con la discusión de HN en un panel lateral), cronología «Última hora» por día con filtro por fuente y sección, modo claro, oscuro o automático, y captura de eventos (Intersection Observer + `sendBeacon`).
- **Cliente de IA intercambiable** (`app/ai`): interfaz común (generar, generar JSON validado con Pydantic, embeddings), implementación de Gemini, un limitador por modelo (token bucket + contador diario con reinicio a medianoche del Pacífico), cola de prioridades, reintentos ante `429` y registro de uso en `ai_usage`.
- Esquema completo de la sección 3.5 de la especificación en una migración de Alembic.

## Puesta en marcha

Requisitos: Docker y Docker Compose.

```bash
cp .env.example backend/.env      # y edita las contraseñas
docker compose -f infra/docker-compose.yml up --build
```

Si los puertos 5432 u 8000 ya están ocupados: `DB_PORT=5433 API_PORT=8001 docker compose -f infra/docker-compose.yml up --build`.

- API: <http://localhost:8000/docs>
- El worker hace una primera ingesta al arrancar y después cada 30–90 min.

Frontend en local (con proxy a la API):

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
# con la API en otro puerto: VITE_API_TARGET=http://localhost:8001 npm run dev -- --port 5174
```

### Tests

```bash
# Backend (necesita PostgreSQL con pgvector; define TEST_DATABASE_URL)
cd backend && pip install -e ".[dev]" && ruff check . && pytest

# Frontend
cd frontend && npm test && npm run lint
```

Los parsers se prueban con respuestas grabadas (`backend/tests/fixtures`) y el cliente de Gemini se simula con `respx`; los tests de base de datos corren contra PostgreSQL real.

## Configuración

Toda la configuración va por variables de entorno; consulta [.env.example](.env.example). **`backend/.env` está en `.gitignore`: nunca lo subas.** La clave de Gemini es un secreto fuera del repositorio.

Los modelos de Gemini se configuran por variable de entorno (`GEMINI_MODEL_LITE`, `GEMINI_MODEL_FLASH`, `GEMINI_MODEL_EMBEDDING`) porque Google publica versiones nuevas a menudo.

> **Privacidad:** en el free tier Google puede usar el contenido enviado para mejorar sus productos. MyNews solo enviará noticias públicas y descripciones de intereses; nunca emails ni datos personales.

## CI/CD

- **CI** (`.github/workflows/ci.yml`, en cada push y pull request): lint y tests del backend contra PostgreSQL + pgvector, migraciones aplicadas desde cero sin deriva con los modelos, tipos, tests y build del frontend, y construcción de las dos imágenes Docker.
- **CD** (`.github/workflows/deploy.yml`, tras un CI en verde en `main`): publica las imágenes en GHCR con la etiqueta del SHA del commit y `latest`. Si la variable de repositorio `DEPLOY_ENABLED` vale `true`, despliega por SSH en el VPS usando el environment `production` (secretos `SSH_HOST`, `SSH_USER`, `SSH_KEY`, `SSH_KNOWN_HOSTS`; variables `DEPLOY_PATH` y `PUBLIC_URL`) y comprueba `/api/health`. Para volver atrás, lanza el workflow a mano con el SHA anterior.
- **Dependabot** actualiza semanalmente las dependencias de pip, npm, Docker y Actions.

También hay scripts manuales: [scripts/deploy.sh](scripts/deploy.sh) y [scripts/backup.sh](scripts/backup.sh) (`pg_dump` fuera del VPS). Caddy obtiene el certificado HTTPS automáticamente para `DOMAIN`.

## Hoja de ruta

| Fase | Contenido | Estado |
| --- | --- | --- |
| 0 · Setup | Repo, Compose, esqueletos, CI, Caddy | ✅ |
| 1 · Agregador | Ingesta, dedup, esquema, feed cronológico, comentarios de HN | ✅ |
| 2 · Base de IA | Cliente con limitador/cola ✅ · enriquecimiento global ✅ · «Lo importante hoy» ✅ · embeddings | 🚧 |
| 3 · «Para ti» | Evals y harness, registro y perfil, vectores de interés, pipeline de 3 etapas, MMR, exploración | ⬜ |
| 4 · Experimentos | A/B e interleaving, puerta de evals en CI, análisis de hilos HN, búsqueda semántica | ⬜ |
| 5 · Agentes | Servidor MCP, agente de briefing con trazas, panel de métricas, alertas | ⬜ |

## Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md). Licencia [MIT](LICENSE).
