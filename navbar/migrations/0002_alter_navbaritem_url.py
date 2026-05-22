from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('navbar', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='navbaritem',
            name='url',
            field=models.CharField(blank=True, max_length=500, verbose_name='URL'),
        ),
    ]
