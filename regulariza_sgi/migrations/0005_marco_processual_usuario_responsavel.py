from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('regulariza_sgi', '0004_alter_imovel_area'),
    ]

    operations = [
        migrations.AddField(
            model_name='marcoprocessual',
            name='usuario_responsavel',
            field=models.CharField(blank=True, max_length=150, verbose_name='Usuário responsável'),
        ),
    ]
