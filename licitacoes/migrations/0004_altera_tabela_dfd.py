# Generated manually to preserve DFD table data while changing its columns.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('licitacoes', '0003_dfd_dfditemtabela'),
    ]

    operations = [
        migrations.RenameField(
            model_name='dfditemtabela',
            old_name='equipamento',
            new_name='especificacao',
        ),
        migrations.RemoveField(
            model_name='dfditemtabela',
            name='descricao',
        ),
        migrations.RemoveField(
            model_name='dfditemtabela',
            name='item',
        ),
        migrations.RemoveField(
            model_name='dfditemtabela',
            name='siafisico',
        ),
        migrations.AddField(
            model_name='dfditemtabela',
            name='unidade_medida',
            field=models.CharField(blank=True, max_length=120, verbose_name='Unidade de medida'),
        ),
        migrations.AddField(
            model_name='dfditemtabela',
            name='valor_unitario',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Valor unitario'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='dfditemtabela',
            name='valor_total',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Valor total'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='dfditemtabela',
            name='quantidade',
            field=models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Quantidade'),
        ),
        migrations.AlterField(
            model_name='dfditemtabela',
            name='especificacao',
            field=models.TextField(verbose_name='Especificacao'),
        ),
    ]
