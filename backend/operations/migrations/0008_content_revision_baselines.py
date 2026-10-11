from django.db import migrations


def capture_baselines(apps, schema_editor):
    Page = apps.get_model("operations", "ContentPage")
    Revision = apps.get_model("operations", "ContentRevision")
    alias = schema_editor.connection.alias
    batch = []
    for page in Page.objects.using(alias).order_by("pk").iterator(chunk_size=200):
        batch.append(Revision(page_id=page.pk, version=page.version, actor_id=None,
                              reason="Baseline captured during revision history migration",
                              snapshot={"title": page.title, "slug": page.slug, "body": page.body,
                                        "kind": page.kind, "is_published": page.is_published,
                                        "version": page.version,
                                        "publish_after": page.publish_after.isoformat() if page.publish_after else None,
                                        "publish_until": page.publish_until.isoformat() if page.publish_until else None}))
        if len(batch) >= 200:
            Revision.objects.using(alias).bulk_create(batch)
            batch = []
    if batch:
        Revision.objects.using(alias).bulk_create(batch)


class Migration(migrations.Migration):
    dependencies = [("operations", "0007_contentrevision_contentpage_publish_after_and_more")]
    operations = [migrations.RunPython(capture_baselines, migrations.RunPython.noop)]
