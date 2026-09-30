# ShoppingWebsite

A planned Persian, right-to-left, multi-seller shopping marketplace for Iran. Prices are shown in toman. This repository currently contains the product and delivery plan; implementation has not started.

## Scope

The first public release covers the full buyer journey from discovery to delivery or refund, plus seller and administrator tools. Loyalty, subscriptions, credit, advertising, and rapid delivery are later expansions.

## Milestones

| # | Milestone | Deliverables | Done when |
| --- | --- | --- | --- |
| 1 | Product and design specification | Buyer, seller, and admin journeys; page map; roles; catalog and seller-offer model; wireframes; design system; provider decisions | Workflows and data model are reviewed and approved. |
| 2 | Platform foundation | Responsive RTL web app, API, database, authentication, permissions, media storage, deployment pipeline, monitoring | Buyer, seller, and admin roles can sign in to a working test environment. |
| 3 | Catalog and discovery | Categories, brands, products, variants, images, specifications, search, filters, sorting, product pages | Buyers can find a product and compare offers from multiple sellers. |
| 4 | Seller and admin portals | Seller onboarding and approval, offers, pricing, stock, catalog moderation, commissions, basic reports | An approved seller can list and maintain an offer without developer help. |
| 5 | Cart and checkout | Cart, addresses, delivery options, discounts, payment integration, order creation | A test buyer can complete a paid order with accurate totals and reserved stock. |
| 6 | Fulfillment and customer service | Seller order handling, shipment status, tracking, cancellation, returns, refunds, notifications | An order can be followed from placement through delivery or refund. |
| 7 | Trust and merchandising | Ratings, verified-purchase reviews, questions, wishlists, comparison, promotions, homepage management | Admins can run a campaign and buyers can use the trust and comparison tools. |
| 8 | Launch readiness | Security, performance, accessibility and mobile QA; analytics; support procedures; seller pilot | Pilot orders succeed end to end and launch-blocking issues are resolved. |
| 9 | Expansion | Recommendations, loyalty, membership, seller ads, wallet or credit, advanced logistics | Features are prioritized from measured customer and seller demand. |

Milestones 1–8 comprise the first public release. Milestone 9 is a separate expansion program.

## Delivery and Git checkpoints

For each milestone, keep its work in a dedicated branch, review the completion criteria, run relevant checks, and commit all files required for that milestone before merging to `main`. Tag the merged commit `milestone-N` after acceptance. A milestone is complete only when its implementation, documentation, and required configuration are committed and pushed; a plan entry alone does not mark it complete.

The product → variant → seller offer → inventory model is the first design dependency. Payment, SMS, and shipping providers should be chosen in milestone 1 so checkout and fulfillment can be designed around their real requirements.
