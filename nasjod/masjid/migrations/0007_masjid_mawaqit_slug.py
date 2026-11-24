# Generated migration for adding mawaqit_slug field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("masjid", "0006_masjid_name_ar"),
    ]

    operations = [
        migrations.AddField(
            model_name="masjid",
            name="mawaqit_slug",
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
    ]
