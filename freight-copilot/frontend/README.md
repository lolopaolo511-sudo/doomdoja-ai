# Frontend

The **MVP UI is server-rendered** by the backend (FastAPI + Jinja2 + Tailwind),
so the whole app runs with one command and zero front-end build. See the pages
under `backend/app/templates/` and routes in `backend/app/web/views.py`.

## Production target (roadmap)

The production front-end is planned as **Next.js + TypeScript + React + Tailwind**
consuming the JSON API exposed under `/api` (see `docs/ARCHITECTURE.md` and
`docs/ROADMAP.md`). The JSON API is already in place, so the React app can be
added without changing the backend domain model.

Until then, this directory is intentionally a placeholder describing the plan.
