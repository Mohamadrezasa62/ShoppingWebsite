# ShoppingWebsite

A Persian, right-to-left multi-seller marketplace for Iran. Product prices are displayed in toman.

## Project status

Planning is approved. Milestones 1–4 have implementation in progress. No milestone has passed its completion checks yet.

See [the detailed milestone plan](docs/MILESTONES.md) for scope, order, dependencies, and completion checks.

## Release scope

The first release covers the buyer journey from product discovery through delivery or refund, with usable seller and administrator portals. Payment support is designed for a conventional online card gateway and provider adapters for Tara, SnappPay, and DigiPay, subject to merchant approval and each provider's current integration contract. Loyalty, subscriptions, ads, and advanced logistics follow the first release.

## Development stack

The initial Docker Compose stack has five services: Django API, PostgreSQL, Redis, Celery worker, and a separate Next.js frontend. The frontend includes account, administrator, and initial product browsing screens. See [the architecture decision](docs/product/ARCHITECTURE.md) and [product requirements](docs/product/REQUIREMENTS.md).

To start locally, copy `.env.example` to `.env`, replace both placeholder secrets, then run `docker compose up --build`. The frontend is at `http://localhost:3000`, the Django health and readiness endpoints at `http://localhost:8000/health/` and `http://localhost:8000/ready/`. Visit `/login` to enter by phone. With `DJANGO_DEBUG=1` and `SMS_BACKEND=console`, the temporary code appears in the API container logs. Staff also enter their password after the one-time code. Production SMS is intentionally disabled until a provider is configured. The seller page verifies access; `/admin-panel` provides the first custom operations workspace.

The API container applies migrations and creates staff role groups on startup. To create the first administrator for local development, run `docker compose exec api python manage.py createsuperuser`, then use `http://localhost:8000/admin/`. Use Django admin to set a password for any account before assigning it a staff role in the custom panel. See [administrator progress and access](docs/admin/ADMIN_PANEL.md). Docker Engine must be running. The stack has not yet been executed end to end on this workstation because its Docker daemon is unavailable.

The public catalog is at `/products/`. To populate it for development, use Django admin to create a category, brand, published product, active variant, approved seller, and active offer with positive price and stock. A product can have offers from several sellers. Catalog search, category filtering, price sorting, and seller offer comparison are available; cart and checkout remain future milestones.
