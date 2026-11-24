# Generated migration for custom permission

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='StagedMosque',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ],
            options={
                'db_table': 'staged_mosque',
                'managed': False,
                'permissions': [('review_stagedmosque', 'Can review staged mosques')],
            },
        ),
    ]
