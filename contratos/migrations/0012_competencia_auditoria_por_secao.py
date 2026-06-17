from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contratos', '0011_incrementos_fluxo_competencias'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='competenciapagamento',
            name='aceite_definitivo_preenchida_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Aceite definitivo preenchido em'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='aceite_definitivo_preenchida_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='competencias_v2_aceite_definitivo_preenchidas', to=settings.AUTH_USER_MODEL, verbose_name='Aceite definitivo preenchido por'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='aceite_provisorio_preenchida_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Aceite provisório preenchido em'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='aceite_provisorio_preenchida_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='competencias_v2_aceite_provisorio_preenchidas', to=settings.AUTH_USER_MODEL, verbose_name='Aceite provisório preenchido por'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='medicao_preenchida_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Medição preenchida em'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='medicao_preenchida_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='competencias_v2_medicao_preenchidas', to=settings.AUTH_USER_MODEL, verbose_name='Medição preenchida por'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='nota_adicional_preenchida_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Nota adicional preenchida em'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='nota_adicional_preenchida_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='competencias_v2_nota_adicional_preenchidas', to=settings.AUTH_USER_MODEL, verbose_name='Nota adicional preenchida por'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='nota_principal_preenchida_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Nota principal preenchida em'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='nota_principal_preenchida_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='competencias_v2_nota_principal_preenchidas', to=settings.AUTH_USER_MODEL, verbose_name='Nota principal preenchida por'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='observacoes_finais_preenchida_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Observações finais preenchidas em'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='observacoes_finais_preenchida_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='competencias_v2_observacoes_finais_preenchidas', to=settings.AUTH_USER_MODEL, verbose_name='Observações finais preenchidas por'),
        ),
    ]
