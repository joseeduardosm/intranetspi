from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('regulariza_sgi', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='imovel',
            name='bairro',
            field=models.CharField(default='', max_length=120, verbose_name='Bairro'),
            preserve_default=False,
        ),
    ]
