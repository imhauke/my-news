# Contribuir

¡Gracias por el interés! Antes de abrir un pull request:

1. Haz un fork y crea una rama desde `main`.
2. Backend: `ruff check .` y `pytest` en `backend/`. Frontend: `npm run lint` y `npm test` en `frontend/`.
3. Si cambias el modelo de datos, añade una migración de Alembic (`alembic revision --autogenerate`); el CI comprueba que no haya deriva entre modelos y migraciones.
4. Añade tests: los parsers con respuestas grabadas, el cliente de Gemini siempre simulado (nunca llames a la API real en los tests).
5. Nunca incluyas claves ni ficheros `.env` en commits ni en issues.

Los nombres de variables, mensajes de log y documentación están en español; el código y los identificadores, en inglés.
