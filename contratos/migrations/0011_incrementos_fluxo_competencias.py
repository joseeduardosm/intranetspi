from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contratos', '0010_checklistpadraoglobal_checklistpadraoglobalitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='contrato',
            name='mes_reajuste',
            field=models.CharField(blank=True, choices=[('01', 'Janeiro'), ('02', 'Fevereiro'), ('03', 'Março'), ('04', 'Abril'), ('05', 'Maio'), ('06', 'Junho'), ('07', 'Julho'), ('08', 'Agosto'), ('09', 'Setembro'), ('10', 'Outubro'), ('11', 'Novembro'), ('12', 'Dezembro')], default='', max_length=2, verbose_name='Mês de reajuste'),
        ),
        migrations.AlterField(
            model_name='competenciapagamento',
            name='status',
            field=models.CharField(choices=[('BLOQUEADA', 'Bloqueada'), ('MEDICAO_PENDENTE', 'Medição pendente'), ('AVALIACAO_PENDENTE', 'Avaliação pendente'), ('CHECKLIST_PENDENTE', 'Checklist pendente'), ('DOWNLOAD_PENDENTE', 'Download pendente'), ('OB_PENDENTE', 'Ordem bancária pendente'), ('PAGA', 'Paga'), ('CANCELADA', 'Cancelada')], default='BLOQUEADA', max_length=30, verbose_name='Status'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='aceite_provisorio_arquivo',
            field=models.FileField(blank=True, upload_to='contratos/medicao/', verbose_name='Comprovação do aceite provisório'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='data_aceite_provisorio',
            field=models.DateField(blank=True, null=True, verbose_name='Data do aceite provisório'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='prazo_aceite_definitivo_dias',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Prazo para aceite definitivo (dias corridos)'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='aceite_definitivo_arquivo',
            field=models.FileField(blank=True, upload_to='contratos/medicao/', verbose_name='Comprovação do aceite definitivo'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='data_aceite_definitivo',
            field=models.DateField(blank=True, null=True, verbose_name='Data do aceite definitivo'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='prazo_pagamento_dias',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Prazo para pagamento (dias corridos)'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='numero_nota_fiscal',
            field=models.CharField(blank=True, max_length=120, verbose_name='Número da nota fiscal'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='nota_adicional_arquivo',
            field=models.FileField(blank=True, upload_to='contratos/pagamentos/', verbose_name='Nota Fiscal adicional'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='numero_nota_adicional',
            field=models.CharField(blank=True, max_length=120, verbose_name='Número da nota fiscal adicional'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='valor_nota_adicional',
            field=models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name='Valor da nota fiscal adicional'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='retencao_ir_adicional',
            field=models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name='Retenção IR da nota adicional'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='retencao_inss_adicional',
            field=models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name='Retenção INSS da nota adicional'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='retencao_iss_adicional',
            field=models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name='Retenção ISS da nota adicional'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='retencao_pis_pasep_adicional',
            field=models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name='Retenção PIS/PASEP da nota adicional'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='retencao_cofins_adicional',
            field=models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name='Retenção COFINS da nota adicional'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='valor_liquido_nota_adicional',
            field=models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name='Valor líquido da nota adicional'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='download_realizado_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Download realizado em'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='avaliacao_assinada',
            field=models.FileField(blank=True, upload_to='contratos/avaliacoes/', verbose_name='Avaliação de qualidade assinada'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='ordem_bancaria_arquivo',
            field=models.FileField(blank=True, upload_to='contratos/pagamentos/', verbose_name='Ordem bancária'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='observacoes_medicao',
            field=models.TextField(blank=True, verbose_name='Observações finais da medição'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='monitoramento_etapa',
            field=models.CharField(blank=True, max_length=80, verbose_name='Etapa monitorada'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='monitoramento_inicio',
            field=models.DateField(blank=True, null=True, verbose_name='Data inicial do monitoramento'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='monitoramento_limite',
            field=models.DateField(blank=True, null=True, verbose_name='Data limite do monitoramento'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='alerta_50_enviado_em',
            field=models.DateField(blank=True, null=True, verbose_name='Alerta de 50% enviado em'),
        ),
        migrations.AddField(
            model_name='competenciapagamento',
            name='alerta_75_ultimo_envio_em',
            field=models.DateField(blank=True, null=True, verbose_name='Último alerta diário enviado em'),
        ),
        migrations.AddField(
            model_name='checklistcompetenciaitem',
            name='categoria',
            field=models.CharField(choices=[('OFICIAL', 'Oficial'), ('NOTA_ADICIONAL', 'Nota adicional')], default='OFICIAL', max_length=20, verbose_name='Categoria do item'),
        ),
        migrations.AddField(
            model_name='exportacaodocumentoscompetencia',
            name='tipo_saida',
            field=models.CharField(default='unificado', max_length=20, verbose_name='Tipo de saída'),
        ),
    ]
