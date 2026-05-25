# Generated manually for dynamic item marker support.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('licitacoes', '0007_etptic_usa_editor_dinamico_sessaoetptic_itemetptic'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemetptic',
            name='tipo',
            field=models.CharField(choices=[('NUMERICO', 'Item/Subitem'), ('SUBSECAO', 'Subsecao'), ('INCISO', 'Inciso')], default='NUMERICO', max_length=12),
        ),
        migrations.AlterField(
            model_name='itemtr',
            name='tipo',
            field=models.CharField(choices=[('NUMERICO', 'Item/Subitem'), ('INCISO', 'Inciso'), ('ALINEA', 'Alinea'), ('SUBSECAO', 'Subsecao')], default='NUMERICO', max_length=12),
        ),
    ]
