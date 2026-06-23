# Criado por José Eduardo Santana Martins e OpenAI Codex em 20/06/2026
# Objetivo: Registrar auditoria estrutural do Contratos V2 para contrato e cadastros relacionados.

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import (
    ChecklistModelo,
    ChecklistModeloItem,
    Contrato,
    ContratoAuditoriaEvento,
    ContratoItem,
    DocumentoImportanteContrato,
    EscalaNotaAvaliacao,
    FaixaLiberacaoAvaliacao,
    FormularioAvaliacao,
    GrupoAvaliacao,
    ItemAvaliacao,
    PrazoMonitoramento,
)
from .services import (
    CHECKLIST_MODELO_AUDITORIA_FIELD_LABELS,
    CHECKLIST_MODELO_ITEM_AUDITORIA_FIELD_LABELS,
    CONTRATO_AUDITORIA_FIELD_LABELS,
    CONTRATO_ITEM_AUDITORIA_FIELD_LABELS,
    DOCUMENTO_IMPORTANTE_AUDITORIA_FIELD_LABELS,
    ESCALA_NOTA_AUDITORIA_FIELD_LABELS,
    FAIXA_LIBERACAO_AUDITORIA_FIELD_LABELS,
    FORMULARIO_AVALIACAO_AUDITORIA_FIELD_LABELS,
    GRUPO_AVALIACAO_AUDITORIA_FIELD_LABELS,
    ITEM_AVALIACAO_AUDITORIA_FIELD_LABELS,
    PRAZO_MONITORAMENTO_AUDITORIA_FIELD_LABELS,
    audit_logging_is_suspended,
    build_changes_payload,
    build_creation_payload,
    build_deletion_payload,
    capture_instance_audit_state,
    get_current_audit_user,
    registrar_evento_contrato,
)


# O registro abaixo concentra tudo que pode ser auditado por sinal, preservando
# um único ponto para labels, resumos e associação com o contrato pai.
AUDIT_SIGNAL_REGISTRY = {
    Contrato: {
        'field_map': CONTRATO_AUDITORIA_FIELD_LABELS,
        'tipo_create': ContratoAuditoriaEvento.TipoEvento.CONTRATO_CRIADO,
        'tipo_update': ContratoAuditoriaEvento.TipoEvento.CONTRATO_ATUALIZADO,
        'tipo_delete': None,
        'resumo_create': 'criou o contrato',
        'resumo_update': 'atualizou dados do contrato',
        'resumo_delete': '',
        'get_contrato': lambda instance: instance,
    },
    ContratoItem: {
        'field_map': CONTRATO_ITEM_AUDITORIA_FIELD_LABELS,
        'tipo_create': ContratoAuditoriaEvento.TipoEvento.ITEM_CRIADO,
        'tipo_update': ContratoAuditoriaEvento.TipoEvento.ITEM_ATUALIZADO,
        'tipo_delete': ContratoAuditoriaEvento.TipoEvento.ITEM_EXCLUIDO,
        'resumo_create': 'cadastrou um item do contrato',
        'resumo_update': 'atualizou um item do contrato',
        'resumo_delete': 'excluiu um item do contrato',
        'get_contrato': lambda instance: instance.contrato,
    },
    DocumentoImportanteContrato: {
        'field_map': DOCUMENTO_IMPORTANTE_AUDITORIA_FIELD_LABELS,
        'tipo_create': ContratoAuditoriaEvento.TipoEvento.DOCUMENTO_CRIADO,
        'tipo_update': ContratoAuditoriaEvento.TipoEvento.DOCUMENTO_ATUALIZADO,
        'tipo_delete': ContratoAuditoriaEvento.TipoEvento.DOCUMENTO_EXCLUIDO,
        'resumo_create': 'cadastrou um documento importante',
        'resumo_update': 'atualizou um documento importante',
        'resumo_delete': 'excluiu um documento importante',
        'get_contrato': lambda instance: instance.contrato,
    },
    ChecklistModelo: {
        'field_map': CHECKLIST_MODELO_AUDITORIA_FIELD_LABELS,
        'tipo_create': ContratoAuditoriaEvento.TipoEvento.CHECKLIST_CRIADO,
        'tipo_update': ContratoAuditoriaEvento.TipoEvento.CHECKLIST_ATUALIZADO,
        'tipo_delete': ContratoAuditoriaEvento.TipoEvento.CHECKLIST_EXCLUIDO,
        'resumo_create': 'cadastrou uma versão de checklist',
        'resumo_update': 'atualizou uma versão de checklist',
        'resumo_delete': 'excluiu uma versão de checklist',
        'get_contrato': lambda instance: instance.contrato,
    },
    ChecklistModeloItem: {
        'field_map': CHECKLIST_MODELO_ITEM_AUDITORIA_FIELD_LABELS,
        'tipo_create': ContratoAuditoriaEvento.TipoEvento.CHECKLIST_ITEM_CRIADO,
        'tipo_update': ContratoAuditoriaEvento.TipoEvento.CHECKLIST_ITEM_ATUALIZADO,
        'tipo_delete': ContratoAuditoriaEvento.TipoEvento.CHECKLIST_ITEM_EXCLUIDO,
        'resumo_create': 'cadastrou um item de checklist',
        'resumo_update': 'atualizou um item de checklist',
        'resumo_delete': 'excluiu um item de checklist',
        'get_contrato': lambda instance: instance.modelo.contrato,
    },
    FormularioAvaliacao: {
        'field_map': FORMULARIO_AVALIACAO_AUDITORIA_FIELD_LABELS,
        'tipo_create': ContratoAuditoriaEvento.TipoEvento.FORMULARIO_CRIADO,
        'tipo_update': ContratoAuditoriaEvento.TipoEvento.FORMULARIO_ATUALIZADO,
        'tipo_delete': ContratoAuditoriaEvento.TipoEvento.FORMULARIO_EXCLUIDO,
        'resumo_create': 'cadastrou um formulário de avaliação',
        'resumo_update': 'atualizou um formulário de avaliação',
        'resumo_delete': 'excluiu um formulário de avaliação',
        'get_contrato': lambda instance: instance.contrato,
    },
    EscalaNotaAvaliacao: {
        'field_map': ESCALA_NOTA_AUDITORIA_FIELD_LABELS,
        'tipo_create': ContratoAuditoriaEvento.TipoEvento.ESCALA_CRIADA,
        'tipo_update': ContratoAuditoriaEvento.TipoEvento.ESCALA_ATUALIZADA,
        'tipo_delete': ContratoAuditoriaEvento.TipoEvento.ESCALA_EXCLUIDA,
        'resumo_create': 'cadastrou uma nota da escala de avaliação',
        'resumo_update': 'atualizou uma nota da escala de avaliação',
        'resumo_delete': 'excluiu uma nota da escala de avaliação',
        'get_contrato': lambda instance: instance.formulario.contrato,
    },
    FaixaLiberacaoAvaliacao: {
        'field_map': FAIXA_LIBERACAO_AUDITORIA_FIELD_LABELS,
        'tipo_create': ContratoAuditoriaEvento.TipoEvento.FAIXA_CRIADA,
        'tipo_update': ContratoAuditoriaEvento.TipoEvento.FAIXA_ATUALIZADA,
        'tipo_delete': ContratoAuditoriaEvento.TipoEvento.FAIXA_EXCLUIDA,
        'resumo_create': 'cadastrou uma faixa de liberação',
        'resumo_update': 'atualizou uma faixa de liberação',
        'resumo_delete': 'excluiu uma faixa de liberação',
        'get_contrato': lambda instance: instance.formulario.contrato,
    },
    GrupoAvaliacao: {
        'field_map': GRUPO_AVALIACAO_AUDITORIA_FIELD_LABELS,
        'tipo_create': ContratoAuditoriaEvento.TipoEvento.GRUPO_CRIADO,
        'tipo_update': ContratoAuditoriaEvento.TipoEvento.GRUPO_ATUALIZADO,
        'tipo_delete': ContratoAuditoriaEvento.TipoEvento.GRUPO_EXCLUIDO,
        'resumo_create': 'cadastrou um grupo de avaliação',
        'resumo_update': 'atualizou um grupo de avaliação',
        'resumo_delete': 'excluiu um grupo de avaliação',
        'get_contrato': lambda instance: instance.formulario.contrato,
    },
    ItemAvaliacao: {
        'field_map': ITEM_AVALIACAO_AUDITORIA_FIELD_LABELS,
        'tipo_create': ContratoAuditoriaEvento.TipoEvento.ITEM_AVALIACAO_CRIADO,
        'tipo_update': ContratoAuditoriaEvento.TipoEvento.ITEM_AVALIACAO_ATUALIZADO,
        'tipo_delete': ContratoAuditoriaEvento.TipoEvento.ITEM_AVALIACAO_EXCLUIDO,
        'resumo_create': 'cadastrou um item de avaliação',
        'resumo_update': 'atualizou um item de avaliação',
        'resumo_delete': 'excluiu um item de avaliação',
        'get_contrato': lambda instance: instance.grupo.formulario.contrato,
    },
    PrazoMonitoramento: {
        'field_map': PRAZO_MONITORAMENTO_AUDITORIA_FIELD_LABELS,
        'tipo_create': ContratoAuditoriaEvento.TipoEvento.PRAZO_CRIADO,
        'tipo_update': ContratoAuditoriaEvento.TipoEvento.PRAZO_ATUALIZADO,
        'tipo_delete': ContratoAuditoriaEvento.TipoEvento.PRAZO_EXCLUIDO,
        'resumo_create': 'cadastrou um prazo de monitoramento',
        'resumo_update': 'atualizou um prazo de monitoramento',
        'resumo_delete': 'excluiu um prazo de monitoramento',
        'get_contrato': lambda instance: instance.contrato,
    },
}


def _get_registry(sender):
    """Retorna a configuração de auditoria do model ou nada quando ele não participa."""

    return AUDIT_SIGNAL_REGISTRY.get(sender)


def _can_register_signal_event():
    """Evita ruído em ações sistêmicas e em execuções fora do contexto de escrita do usuário."""

    return not audit_logging_is_suspended() and get_current_audit_user() is not None


@receiver(pre_save)
def contratos_audit_pre_save(sender, instance, **kwargs):
    """Captura o estado anterior para compor o diff depois do save."""

    registry = _get_registry(sender)
    if not registry or not instance.pk or audit_logging_is_suspended():
        return
    previous = sender.objects.filter(pk=instance.pk).first()
    if previous is None:
        return
    instance._audit_before_state = capture_instance_audit_state(previous, registry['field_map'])


@receiver(post_save)
def contratos_audit_post_save(sender, instance, created, **kwargs):
    """Registra criações e edições estruturais com payload resumido."""

    registry = _get_registry(sender)
    if not registry or not _can_register_signal_event():
        return
    contrato = registry['get_contrato'](instance)
    if created:
        registrar_evento_contrato(
            contrato=contrato,
            tipo_evento=registry['tipo_create'],
            resumo=registry['resumo_create'],
            payload=build_creation_payload(instance, registry['field_map']),
        )
        return
    before_state = getattr(instance, '_audit_before_state', None)
    if not before_state:
        return
    payload = build_changes_payload(before_state, instance, registry['field_map'])
    if not payload.get('changes'):
        return
    registrar_evento_contrato(
        contrato=contrato,
        tipo_evento=registry['tipo_update'],
        resumo=registry['resumo_update'],
        payload=payload,
    )


@receiver(post_delete)
def contratos_audit_post_delete(sender, instance, **kwargs):
    """Registra exclusões quando elas partem de uma ação explícita do usuário."""

    registry = _get_registry(sender)
    if not registry or not _can_register_signal_event() or not registry.get('tipo_delete'):
        return
    registrar_evento_contrato(
        contrato=registry['get_contrato'](instance),
        tipo_evento=registry['tipo_delete'],
        resumo=registry['resumo_delete'],
        payload=build_deletion_payload(instance, registry['field_map']),
    )
