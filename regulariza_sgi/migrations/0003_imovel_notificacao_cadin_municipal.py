from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('regulariza_sgi', '0002_imovel_bairro'),
    ]

    operations = [
        migrations.AddField(
            model_name='imovel',
            name='notificacao_cadin_municipal',
            field=models.CharField(blank=True, max_length=180, verbose_name='Notificação CADIN Municipal'),
        ),
    ]
