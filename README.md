# ShoppingWebsite

A Persian, right-to-left multi-seller marketplace for Iran. Product prices are displayed in toman.

## Project status

Planning is approved. Milestones 1–9 have implementation in progress, Milestone 10 has a launch gate review, and Milestone 11 has a data-dependent decision record. No milestone has passed its completion checks yet.

See [the detailed milestone plan](docs/MILESTONES.md) for scope, order, dependencies, and completion checks.

## Release scope

The first release covers the buyer journey from product discovery through delivery or refund, with usable seller and administrator portals. Payment support is designed for a conventional online card gateway and provider adapters for Tara, SnappPay, and DigiPay, subject to merchant approval and each provider's current integration contract. Loyalty, subscriptions, ads, and advanced logistics follow the first release.

## Development stack

The Docker Compose stack has six services: Django API, PostgreSQL, Redis, Celery worker, Celery scheduler, and a separate Next.js frontend. The frontend includes account, administrator, product browsing, seller, and cart screens. See [the architecture decision](docs/product/ARCHITECTURE.md) and [product requirements](docs/product/REQUIREMENTS.md).

To start locally, copy `.env.example` to `.env`, set a strong unique `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`, then run `docker compose up --build`. The frontend is at `http://localhost:5067`, the Django health and readiness endpoints at `http://localhost:5068/health/` and `http://localhost:5068/ready/`, PostgreSQL is published on `localhost:5069`, and Redis on `localhost:5070`. Container-to-container connections continue to use the Docker service ports (`5432` and `6379`). For local phone-code development only, set `DJANGO_DEBUG=1` and `SMS_BACKEND=console`; the temporary code then appears in the API container logs. Production SMS is disabled until a provider is configured. The seller page verifies access; `/admin-panel` provides the first custom operations workspace.

For deployment, use a production `.env` with a strong secret and database password, set `DJANGO_DEBUG=0`, set `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` to the deployed hostnames, and configure production SMS and persistent media storage before accepting real users. Restrict PostgreSQL and Redis host ports to trusted networks or remove their `ports` mappings when external access is not needed. The included Compose API runs under Gunicorn; terminate public TLS at a trusted reverse proxy or load balancer.

The API container applies migrations and creates staff role groups on startup. To create the first administrator for local development, run `docker compose exec api python manage.py createsuperuser`, then use `http://localhost:8000/admin/`. Use Django admin to set a password for any account before assigning it a staff role in the custom panel. See [administrator progress and access](docs/admin/ADMIN_PANEL.md). Docker Engine must be running. The stack has not yet been executed end to end on this workstation because its Docker daemon is unavailable.

The public catalog is at `/products/`. To populate it for development, use Django admin to create a category, brand, published product, active variant, approved seller, and active offer with positive price and stock. A product can have offers from several sellers. Search suggestions, category and brand filtering, category-specific variant facets, price range and sorting, approved product images, variant selection, and seller offer comparison are available. Configure facet keys and choices in Django admin; variant attributes use those same keys and values. Product images can be uploaded in Django admin; the public image route checks approval and product availability. Production media storage and scalable delivery still need configuration. Cart, checkout, and location-based delivery estimates remain future work.

The seller portal is at `/seller-panel/`. A signed-in user can apply with a store name, legal name, business identifier, and contact phone; a marketplace manager reviews those details in the admin panel. Once approved, the owner can edit public profile details, find a published catalog variant, add an offer, and edit its price, stock, warranty, and active or paused state. Seller records and offers are restricted by membership in the API. The entered business details are not externally verified yet. Document verification, bulk import, order processing, and settlement reporting remain to be built.

Signed-in buyers can add offers to a persistent cart at `/cart/`, change quantities, remove lines, and save delivery addresses. The cart API recalculates current item prices and flags offers that are unavailable or short on stock. Staff can configure province and fulfillment shipping rules in Django admin; the cart shows a grouped shipping quote when rules exist. The checkout API can create a pending order with immutable item and shipping snapshots, reserve stock atomically, and return the same order for a repeated idempotency key. The scheduler expires unpaid orders after 15 minutes and releases stock. Buyer checkout remains disabled in the UI until payment is implemented; order creation through the API is for integration development. Discounts, tax rules, final delivery eligibility, and live payment remain pending. The payment module has a ledger and private verified-capture path; buyer-facing methods remain disabled pending certified provider integrations. See [payment integration status](docs/payments/INTEGRATIONS.md).
