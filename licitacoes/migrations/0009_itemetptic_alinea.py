# Generated manually for dynamic ETP alinea marker support.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('licitacoes', '0008_item_tipos_subsecao_etp'),
    ]

    operations = [
        migrations.AlterField(
            model_name='itemetptic',
            name='tipo',
            field=models.CharField(choices=[('NUMERICO', 'Item/Subitem'), ('SUBSECAO', 'Subsecao'), ('INCISO', 'Inciso'), ('ALINEA', 'Alinea')], default='NUMERICO', max_length=12),
        ),
    ]
