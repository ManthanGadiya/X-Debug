# XDebug Backend

FastAPI backend for the XDebug explainable AI debugging assistant.

## Requirements

* Python 3.12+

## Setup

The virtual environment lives at the **project root** (`.venv/`), shared by the
whole repo. From the repository root:

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # Linux/macOS
pip install -e "backend[dev]"
```

Then run the backend from the `backend/` directory:

Copy `.env.example` to `.env` to override any setting:

```bash
copy .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for the interactive OpenAPI documentation.

## Checks

```bash
ruff check app tests
black --check app tests
mypy app
pytest
```

## Layout

The package follows the layered architecture defined in `docs/ARCHITECTURE.md`:

```text
app/
├── api/        # API layer: routers and route handlers
├── core/       # configuration, logging, structured errors, middleware
├── schemas/    # public request/response models
├── services/   # application layer: use-case orchestration
└── container.py# dependency-injection container
```

The analysis, graph, and storage layers (`app/analysis`, `app/graph`,
`app/storage`) are added in later roadmap phases.
