# Administrator panel progress

Milestone 3 is in progress. The custom panel is available at `/admin-panel` for authenticated staff. Its current workspace includes:

- Summary counts for seller review, approved sellers, categories, and staff.
- Seller application review, approval, rejection, suspension, and reinstatement with transition rules and a required reason.
- Category creation and editing, including parent selection and cycle validation.
- Staff search and role assignment by system administrators. A staff account needs a usable password before a role can be assigned.
- An audit view for administrator changes. Events record actor, time, action, target, reason, and before/after values.

Staff sign-in requires both the phone one-time code and the account password. The initial superuser is created with `python manage.py createsuperuser`. Set passwords for other staff accounts in Django admin before assigning roles through the custom panel. The `seed_roles` command creates the role groups.

The API enforces role permissions, session authentication, and CSRF protection for changes. Seller decisions, category edits, and role assignments are written with their audit events in one database transaction. The lists currently return a limited first page; search, pagination, and filters need further work.

The remaining Milestone 3 modules depend on later marketplace data models: product moderation, commissions, order intervention, returns and refunds, campaigns and content, shipping and payment provider configuration, finance and settlements, support queues, exports, and alerts. They remain open under [the milestone acceptance criteria](../MILESTONES.md). This branch is progress toward Milestone 3, not its accepted completion.
