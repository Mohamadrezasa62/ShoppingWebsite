from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_accountclosure")]
    operations = [
        migrations.AlterField(model_name="user", name="phone", field=models.CharField(blank=True, max_length=16, null=True, unique=True)),
        migrations.AddConstraint(model_name="user", constraint=models.UniqueConstraint(Lower("email"), condition=~models.Q(email=""), name="account_email_case_insensitive_unique")),
    ]
