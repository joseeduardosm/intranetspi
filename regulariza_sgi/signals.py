# Criado por José Eduardo Santana Martins em 04/06/2026
# Atualizado por Codex em 09/06/2026
# Objetivo: Criar ciclo inicial e alimentar a timeline geral do imóvel.

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Imovel, ImovelAnexo, ImovelObservacao, ImovelProcessoSEI
from .services import create_initial_cycle, registrar_evento_timeline


@receiver(post_save, sender=Imovel)
def create_imovel_initial_cycle(sender, instance, created, **kwargs):
    """Garante que todo imóvel novo comece com um ciclo inicial e com evento de timeline."""

    if created:
        create_initial_cycle(instance)
        registrar_evento_timeline(
            instance,
            'cadastro',
            'Imóvel cadastrado no módulo Regulariza SGI.',
            usuario=getattr(instance, '_timeline_user', 'Sistema'),
        )
        return

    if getattr(instance, '_skip_timeline_event', False):
        instance._skip_timeline_event = False
        return

    registrar_evento_timeline(
        instance,
        'edicao',
        'Dados cadastrais do imóvel foram atualizados.',
        usuario=getattr(instance, '_timeline_user', 'Sistema'),
    )


@receiver(post_save, sender=ImovelProcessoSEI)
def registrar_timeline_processo_sei_save(sender, instance, created, **kwargs):
    """Registra inclusão e edição de processo SEI na timeline consolidada."""

    registrar_evento_timeline(
        instance.imovel,
        'processo_sei',
        'Processo SEI adicionado ao imóvel.' if created else 'Processo SEI atualizado.',
        usuario=getattr(instance, '_timeline_user', 'Sistema'),
        processo_sei=instance,
    )


@receiver(post_delete, sender=ImovelProcessoSEI)
def registrar_timeline_processo_sei_delete(sender, instance, **kwargs):
    """Registra exclusão de processo SEI mesmo após a remoção do vínculo."""

    registrar_evento_timeline(
        instance.imovel,
        'processo_sei',
        'Processo SEI removido do imóvel.',
        usuario=getattr(instance, '_timeline_user', 'Sistema'),
    )


@receiver(post_save, sender=ImovelAnexo)
def registrar_timeline_anexo_save(sender, instance, created, **kwargs):
    """Registra inclusão e edição de anexos do imóvel."""

    registrar_evento_timeline(
        instance.imovel,
        'anexo',
        'Documento anexado ao imóvel.' if created else 'Documento do imóvel atualizado.',
        usuario=getattr(instance, '_timeline_user', 'Sistema'),
        anexo=instance,
    )


@receiver(post_delete, sender=ImovelAnexo)
def registrar_timeline_anexo_delete(sender, instance, **kwargs):
    """Registra exclusão de anexos na timeline do imóvel."""

    registrar_evento_timeline(
        instance.imovel,
        'anexo',
        'Documento removido do imóvel.',
        usuario=getattr(instance, '_timeline_user', 'Sistema'),
    )


@receiver(post_save, sender=ImovelObservacao)
def registrar_timeline_observacao_save(sender, instance, created, **kwargs):
    """Mantém a timeline geral ciente da criação de observações funcionais."""

    if not created:
        return
    registrar_evento_timeline(
        instance.imovel,
        'observacao',
        'Observação adicionada ao imóvel.',
        usuario=instance.usuario_responsavel,
        observacao=instance,
    )
