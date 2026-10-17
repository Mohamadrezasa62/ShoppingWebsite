# گزیناو / Gozinav — design notes

## Direction and references

The working identity is a calm, Persian RTL marketplace that helps people compare sellers and understand their choices. Its voice follows the Guide and Everyperson archetypes: clear, approachable and specific. Gozinav is a provisional name; the earlier exact-name search did not establish trademark or domain availability.

The visual reference is [Nixtio's IVR dashboard on Dribbble](https://dribbble.com/shots/27709197-IVR-Call-Center-Communication-Dashboard-UI-Design). The adaptation uses its dark navigation rail, light workspace, pastel cards, rounded surfaces, thin dividers and pill controls. The reference is a rendered image; these are original marketplace tokens and layouts, not an extraction of its private component library. Apple Design System and UI UX Pro Max skill guidance informed hierarchy, action color, spacing, accessibility and responsive behavior.

## Tokens and components

- Canvas `#ECECED`; white surfaces; ink `#252628`; secondary text `#59636E`.
- Action blue `#0066CC`; powder blue `#CFDDE8`, lilac `#E3DAEC` and sand `#F6DC89` are supporting surfaces.
- Typography: Tahoma, Arial and system sans-serif; weight ladder 400 / 600 / 700.
- Spacing scale: 4, 8, 12, 16, 20, 24, 32, 40 and 48 pixels.
- Corner radii: 12, 24, 32 pixels and pill controls. Surface changes and hairlines provide most separation.
- Shared implementation: `AppShell`, `Brand`, `BrandMark`, `UiIcon` and `PromoBanner`; tokens and responsive rules live in `frontend/app/gozinav.css`.
- Keyboard focus, visible form labels, native modal focus behavior and reduced-motion preferences are supported.

The original geometric G mark is reused in the favicon, navigation, hero and banners. Campaigns are text-led and contain no characters, fabricated statistics, discounts or commercial guarantees. Banner themes cover seller comparison, order tracking, support and seller operations. Editable SVG exports are in `frontend/public/brand`; live React banners keep their text readable and adaptive.

## Responsive layouts and Figma

[Open the editable Figma file](https://www.figma.com/design/DGcCzSUrREINw0xia8JUDE).

The file was authored through the user's signed-in Figma website by pasting manually constructed SVG primitives as editable vectors and text, without Figma AI. It contains 27 route layouts at 390, 1024 and 1440 pixels, a brand board and a route relationship board. The connections form a clickable screen-review sequence in each size. They do **not** constitute a complete prototype of all field states, navigation hotspots, permissions or backend behavior. The frontend is the functional implementation.

Implementation breakpoints are 600, 900, 1200 and 1500 pixels. Phones use bottom navigation, a modal page menu, collapsible catalog filters and adaptive forms/cards. Larger screens use the dark rail, split hero/authentication layouts and denser grids. Wide comparison content scrolls within its container.

See `system.json` for the token record and route groups, `journeys.svg` for the route relationship asset, and `previews/` for captured interface images.

## Authentication changes included in this revision

Buyers have both phone-code and email/password access. Email registration creates an ordinary buyer with an optional phone number; nonempty emails have case-insensitive uniqueness. Staff email login cannot bypass the existing phone challenge and password requirement. Accounts are not automatically merged by identity.

Migration `accounts.0004_user_email_login` must be applied. Existing duplicate email addresses need review before migration. Email ownership verification and password-recovery delivery remain unconfigured. Production still requires HTTPS, the appropriate cookie/origin settings, a working SMS provider and certified payment integration before public commerce.

## Local verification recorded on 2026-10-17

- 31 authentication/security tests passed, including the new email access tests.
- TypeScript checking and the optimized Next.js production build passed.
- Django system checks and migration drift checks passed.
- Seven main routes were checked in browser viewports of 360, 768, 1024 and 1440 pixels without document-level horizontal overflow in the observed renders. Home, login and cart were also inspected at 390 pixels.
- Email sign-in, adding a seller offer to the cart, the mobile page menu and collapsible product filters were exercised locally.

These checks used local SQLite/demo data. They are not certification of every endpoint, every privileged workflow, PostgreSQL concurrency or a production deployment.
