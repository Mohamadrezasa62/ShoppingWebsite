from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ContentHistoryMigrationTests(TransactionTestCase):
    def test_existing_page_gets_truthful_baseline_without_republishing(self):
        old_target = [("operations", "0006_supportticket_is_escalated_supportticket_priority_and_more")]
        new_target = [("operations", "0008_content_revision_baselines")]
        executor = MigrationExecutor(connection)
        try:
            executor.migrate(old_target)
            old_apps = executor.loader.project_state(old_target).apps
            page = old_apps.get_model("operations", "ContentPage").objects.create(title="Existing policy", slug="migration-policy", body="Keep original text", kind="policy", is_published=False)
            published = old_apps.get_model("operations", "ContentPage").objects.create(title="Existing live guide", slug="migration-live-guide", body="Keep published text", is_published=True)
            executor = MigrationExecutor(connection)
            executor.migrate(new_target)
            apps = executor.loader.project_state(new_target).apps
            migrated = apps.get_model("operations", "ContentPage").objects.get(pk=page.pk)
            revision = apps.get_model("operations", "ContentRevision").objects.get(page_id=page.pk, version=1)
            self.assertEqual(migrated.body, "Keep original text")
            self.assertFalse(migrated.is_published)
            self.assertIsNone(migrated.publish_after)
            self.assertIsNone(migrated.publish_until)
            self.assertIsNone(revision.actor_id)
            self.assertEqual(revision.snapshot["body"], "Keep original text")
            self.assertFalse(revision.snapshot["is_published"])
            self.assertIn("Baseline", revision.reason)
            live = apps.get_model("operations", "ContentPage").objects.get(pk=published.pk)
            live_revision = apps.get_model("operations", "ContentRevision").objects.get(page_id=published.pk, version=1)
            self.assertTrue(live.is_published)
            self.assertTrue(live_revision.snapshot["is_published"])
            self.assertEqual(live.body, "Keep published text")
        finally:
            MigrationExecutor(connection).migrate(new_target)
