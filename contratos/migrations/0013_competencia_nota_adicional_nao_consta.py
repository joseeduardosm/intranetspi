from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contratos', '0012_competencia_auditoria_por_secao'),
    ]

    operations = [
        migrations.AddField(
            model_name='competenciapagamento',
            name='nota_adicional_nao_consta',
            field=models.BooleanField(default=False, verbose_name='Nota fiscal adicional não consta'),
        ),
    ]
