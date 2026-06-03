from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone


ESTADOS = [
    ('AC', 'Acre'),
    ('AL', 'Alagoas'),
    ('AP', 'Amapá'),
    ('AM', 'Amazonas'),
    ('BA', 'Bahia'),
    ('CE', 'Ceará'),
    ('DF', 'Distrito Federal'),
    ('ES', 'Espírito Santo'),
    ('GO', 'Goiás'),
    ('MA', 'Maranhão'),
    ('MT', 'Mato Grosso'),
    ('MS', 'Mato Grosso do Sul'),
    ('MG', 'Minas Gerais'),
    ('PA', 'Pará'),
    ('PB', 'Paraíba'),
    ('PR', 'Paraná'),
    ('PE', 'Pernambuco'),
    ('PI', 'Piauí'),
    ('RJ', 'Rio de Janeiro'),
    ('RN', 'Rio Grande do Norte'),
    ('RS', 'Rio Grande do Sul'),
    ('RO', 'Rondônia'),
    ('RR', 'Roraima'),
    ('SC', 'Santa Catarina'),
    ('SP', 'São Paulo'),
    ('SE', 'Sergipe'),
    ('TO', 'Tocantins'),
]

MUNICIPIOS_POR_UF = {
    'SP': [
        'Araçatuba',
        'Araraquara',
        'Barretos',
        'Bauru',
        'Botucatu',
        'Campinas',
        'Caraguatatuba',
        'Catanduva',
        'Cotia',
        'Diadema',
        'Franca',
        'Guarujá',
        'Guarulhos',
        'Itapecerica da Serra',
        'Itapevi',
        'Jundiaí',
        'Marília',
        'Mauá',
        'Mogi das Cruzes',
        'Osasco',
        'Piracicaba',
        'Praia Grande',
        'Presidente Prudente',
        'Ribeirão Preto',
        'Santo André',
        'Santos',
        'São Bernardo do Campo',
        'São Caetano do Sul',
        'São José do Rio Preto',
        'São José dos Campos',
        'São Paulo',
        'Sorocaba',
        'Suzano',
        'Taubaté',
    ],
}

TIMELINE_COLOR_GREEN = 'verde'
TIMELINE_COLOR_YELLOW = 'amarelo'
TIMELINE_COLOR_RED = 'vermelho'
TIMELINE_COLOR_NEUTRAL = 'neutro'


@dataclass
class SegmentoPrazo:
    inicio: date
    fim: date


@dataclass
class TimelineEdge:
    titulo: str
    data: date | None
    legenda: str
    usuario: str
    tipo: str = ''


def today_local():
    return timezone.localdate()


def add_years_safe(base_date: date, years: int) -> date:
    try:
        return base_date.replace(year=base_date.year + years)
    except ValueError:
        return base_date.replace(month=2, day=28, year=base_date.year + years)


def municipio_choices(uf: str | None):
    return [(nome, nome) for nome in MUNICIPIOS_POR_UF.get(uf or '', [])]


def format_date(value):
    if not value:
        return ''
    return value.strftime('%d/%m/%Y')


def timeline_color(progress_percent: float | None):
    if progress_percent is None:
        return TIMELINE_COLOR_NEUTRAL
    if progress_percent < 75:
        return TIMELINE_COLOR_GREEN
    if progress_percent < 90:
        return TIMELINE_COLOR_YELLOW
    return TIMELINE_COLOR_RED


def progress_percent_for_segment(segmento: SegmentoPrazo | None, reference_date: date | None = None):
    if not segmento:
        return None
    reference_date = reference_date or today_local()
    total_days = (segmento.fim - segmento.inicio).days
    if total_days <= 0:
        return 100.0
    consumed = (reference_date - segmento.inicio).days
    percent = (consumed / total_days) * 100
    return max(0.0, min(percent, 100.0))


def current_cycle(imovel):
    return imovel.ciclos.order_by('-numero', '-id').first()


def ciclo_segmento_ativo(ciclo):
    if not ciclo:
        return None
    if not ciclo.data_protocolo:
        return SegmentoPrazo(ciclo.data_inicio, ciclo.data_inicio + timedelta(days=30))
    if ciclo.resultado == ciclo.Resultado.INDEFERIDO and ciclo.data_contrarrazao_limite:
        return SegmentoPrazo(ciclo.data_manifestacao or ciclo.data_protocolo, ciclo.data_contrarrazao_limite)
    if ciclo.resultado == ciclo.Resultado.DEFERIDO and ciclo.data_renovacao_prevista:
        return SegmentoPrazo(ciclo.data_manifestacao or ciclo.data_protocolo, ciclo.data_renovacao_prevista)
    if ciclo.data_manifestacao_prevista and not ciclo.data_manifestacao:
        return SegmentoPrazo(ciclo.data_protocolo, ciclo.data_manifestacao_prevista)
    return None


def ciclo_status(ciclo):
    hoje = today_local()
    if not ciclo:
        return 'Cadastrado'
    if not ciclo.data_protocolo:
        return 'Cadastrado' if ciclo.tipo == ciclo.Tipo.INICIAL else 'Aguardando Protocolo'
    if not ciclo.data_manifestacao:
        if ciclo.data_protocolo == hoje:
            return 'Protocolado'
        if ciclo.prorrogacao_dias:
            return 'Em Prorrogação'
        return 'Aguardando Manifestação'
    if ciclo.resultado == ciclo.Resultado.INDEFERIDO:
        if ciclo.data_contrarrazao_limite and hoje <= ciclo.data_contrarrazao_limite:
            return 'Em Contrarrazão'
        return 'Indeferido'
    if ciclo.resultado == ciclo.Resultado.DEFERIDO:
        if ciclo.data_renovacao_prevista and hoje >= ciclo.data_renovacao_prevista:
            return 'Renovação Necessária'
        if ciclo.data_vencimento_imunidade and hoje <= ciclo.data_vencimento_imunidade:
            return 'Imunidade Vigente'
        return 'Deferido'
    return 'Aguardando Manifestação'


def ciclo_badges(imovel, ciclo):
    badges = [ciclo_status(ciclo)]
    if imovel.possui_cadin_ativo:
        badges.append('CADIN')
    return badges


def usuario_display(usuario):
    return usuario or 'Sistema'


def timeline_edges(ciclo):
    if not ciclo:
        return None, None
    if not ciclo.data_protocolo:
        return (
            TimelineEdge(
                titulo='Cadastro do Imóvel',
                data=ciclo.data_inicio,
                legenda='Marco atual',
                usuario='Sistema',
                tipo='CADASTRO',
            ),
            TimelineEdge(
                titulo='Protocolo',
                data=ciclo.data_inicio + timedelta(days=30),
                legenda='Data limite',
                usuario='Sistema',
                tipo='PROTOCOLO_PREVISTO',
            ),
        )
    if not ciclo.data_manifestacao:
        titulo_atual = 'Prorrogação' if ciclo.prorrogacao_dias and ciclo.data_prorrogacao else 'Protocolo'
        data_atual = ciclo.data_prorrogacao if ciclo.prorrogacao_dias and ciclo.data_prorrogacao else ciclo.data_protocolo
        tipo_atual = 'PRORROGACAO' if ciclo.prorrogacao_dias and ciclo.data_prorrogacao else 'PROTOCOLO'
        return (
            TimelineEdge(
                titulo=titulo_atual,
                data=data_atual,
                legenda='Marco atual',
                usuario='Sistema',
                tipo=tipo_atual,
            ),
            TimelineEdge(
                titulo='Manifestação',
                data=ciclo.data_manifestacao_prevista,
                legenda='Data limite',
                usuario='Sistema',
                tipo='MANIFESTACAO_PREVISTA',
            ),
        )
    if ciclo.resultado == ciclo.Resultado.INDEFERIDO and ciclo.data_contrarrazao_limite:
        return (
            TimelineEdge(
                titulo='Indeferimento',
                data=ciclo.data_manifestacao,
                legenda='Marco atual',
                usuario='Sistema',
                tipo='INDEFERIMENTO',
            ),
            TimelineEdge(
                titulo='Prazo para Contrarrazão',
                data=ciclo.data_contrarrazao_limite,
                legenda='Data limite',
                usuario='Sistema',
                tipo='CONTRARRAZAO',
            ),
        )
    if ciclo.resultado == ciclo.Resultado.DEFERIDO and ciclo.data_renovacao_prevista:
        return (
            TimelineEdge(
                titulo='Deferimento',
                data=ciclo.data_manifestacao,
                legenda='Marco atual',
                usuario='Sistema',
                tipo='DEFERIMENTO',
            ),
            TimelineEdge(
                titulo='Renovação',
                data=ciclo.data_renovacao_prevista,
                legenda='Data limite',
                usuario='Sistema',
                tipo='RENOVACAO',
            ),
        )
    return None, None


def compute_timeline_context(imovel):
    ciclo = current_cycle(imovel)
    segmento = ciclo_segmento_ativo(ciclo)
    progress_percent = progress_percent_for_segment(segmento)
    color = timeline_color(progress_percent)
    historico = []
    marker_percent = progress_percent if progress_percent is not None else 0
    current_edge, next_edge = timeline_edges(ciclo)
    if ciclo:
        historico = list(imovel.ciclos.exclude(pk=ciclo.pk).order_by('-numero', '-id'))
        marco_map = {marco.tipo: marco for marco in ciclo.marcos.all()}
        if current_edge and current_edge.tipo in marco_map:
            current_edge.usuario = usuario_display(marco_map[current_edge.tipo].usuario_responsavel)
        if next_edge and next_edge.tipo in marco_map:
            next_edge.usuario = usuario_display(marco_map[next_edge.tipo].usuario_responsavel)
    prazo_total_dias = (segmento.fim - segmento.inicio).days if segmento else None
    dias_consumidos = max(0, (today_local() - segmento.inicio).days) if segmento else None
    historico_marcos = []
    if ciclo:
        historico_marcos = list(
            imovel.ciclos.order_by('-numero', 'id').prefetch_related('marcos')
        )
    return {
        'ciclo_atual': ciclo,
        'historico': historico,
        'historico_marcos': historico_marcos,
        'status': ciclo_status(ciclo),
        'badges': ciclo_badges(imovel, ciclo),
        'color': color,
        'progress_percent': progress_percent,
        'marker_percent': marker_percent,
        'dias_desde_cadastro': (today_local() - imovel.criado_em.date()).days,
        'marco_atual': current_edge,
        'proximo_marco': next_edge,
        'prazo_total_dias': prazo_total_dias,
        'dias_consumidos_trecho': dias_consumidos,
    }


def sync_ciclo(ciclo, usuario=None, tipo_evento=None):
    if ciclo.data_protocolo and ciclo.prazo_resposta_dias:
        ciclo.data_manifestacao_prevista = ciclo.data_protocolo + timedelta(
            days=ciclo.prazo_resposta_dias + ciclo.prorrogacao_dias
        )
    else:
        ciclo.data_manifestacao_prevista = None

    if ciclo.resultado == ciclo.Resultado.DEFERIDO and ciclo.data_manifestacao and ciclo.prazo_imunidade_anos:
        ciclo.data_vencimento_imunidade = add_years_safe(ciclo.data_manifestacao, ciclo.prazo_imunidade_anos)
        ciclo.data_renovacao_prevista = ciclo.data_vencimento_imunidade - timedelta(days=180)
        ciclo.data_contrarrazao_limite = None
    elif ciclo.resultado == ciclo.Resultado.INDEFERIDO and ciclo.data_manifestacao:
        ciclo.data_contrarrazao_limite = ciclo.data_manifestacao + timedelta(days=3)
        ciclo.data_vencimento_imunidade = None
        ciclo.data_renovacao_prevista = None
        ciclo.prazo_imunidade_anos = None
    else:
        ciclo.data_contrarrazao_limite = None
        ciclo.data_vencimento_imunidade = None
        ciclo.data_renovacao_prevista = None
        if ciclo.resultado != ciclo.Resultado.DEFERIDO:
            ciclo.prazo_imunidade_anos = None

    ciclo.save()
    rebuild_marcos(ciclo, usuario=usuario, tipo_evento=tipo_evento)


def rebuild_marcos(ciclo, usuario=None, tipo_evento=None):
    usuario_evento = usuario_display(usuario)
    anteriores = {marco.tipo: marco.usuario_responsavel for marco in ciclo.marcos.all()}
    ciclo.marcos.all().delete()
    marcos = [
        ('CADASTRO', 'Cadastro do Imóvel', ciclo.data_inicio, ciclo.data_inicio, 0, 'Sistema'),
    ]
    marcos.append(
        (
            'PROTOCOLO_PREVISTO',
            'Protocolo',
            None,
            ciclo.data_inicio + timedelta(days=30),
            30,
            'Sistema',
        )
    )
    if ciclo.data_protocolo:
        marcos.append(
            (
                'PROTOCOLO',
                'Protocolo',
                ciclo.data_protocolo,
                ciclo.data_protocolo,
                None,
                usuario_evento if tipo_evento == 'PROTOCOLO' else anteriores.get('PROTOCOLO', 'Sistema'),
            )
        )
    if ciclo.data_prorrogacao and ciclo.prorrogacao_dias:
        marcos.append(
            (
                'PRORROGACAO',
                'Prorrogação',
                ciclo.data_prorrogacao,
                ciclo.data_prorrogacao,
                ciclo.prorrogacao_dias,
                usuario_evento if tipo_evento == 'PRORROGACAO' else anteriores.get('PRORROGACAO', 'Sistema'),
            )
        )
    if ciclo.data_manifestacao_prevista:
        marcos.append(
            (
                'MANIFESTACAO_PREVISTA',
                'Manifestação',
                None,
                ciclo.data_manifestacao_prevista,
                ciclo.prazo_resposta_dias + ciclo.prorrogacao_dias,
                'Sistema',
            )
        )
    if ciclo.data_manifestacao:
        titulo = 'Deferimento' if ciclo.resultado == ciclo.Resultado.DEFERIDO else 'Indeferimento'
        tipo = 'DEFERIMENTO' if ciclo.resultado == ciclo.Resultado.DEFERIDO else 'INDEFERIMENTO'
        marcos.append(
            (
                tipo,
                titulo,
                ciclo.data_manifestacao,
                ciclo.data_manifestacao,
                None,
                usuario_evento if tipo_evento == tipo else anteriores.get(tipo, 'Sistema'),
            )
        )
    if ciclo.data_contrarrazao_limite:
        marcos.append(
            (
                'CONTRARRAZAO',
                'Prazo para Contrarrazão',
                None,
                ciclo.data_contrarrazao_limite,
                3,
                'Sistema',
            )
        )
    if ciclo.data_renovacao_prevista:
        marcos.append(
            (
                'RENOVACAO',
                'Renovação',
                None,
                ciclo.data_renovacao_prevista,
                None,
                'Sistema',
            )
        )
    if ciclo.data_vencimento_imunidade:
        marcos.append(
            (
                'VENCIMENTO_IMUNIDADE',
                'Vencimento da Imunidade',
                None,
                ciclo.data_vencimento_imunidade,
                None,
                'Sistema',
            )
        )
    for ordem, (tipo, titulo, data_real, data_prevista, prazo_dias, usuario_responsavel) in enumerate(marcos, start=1):
        ciclo.marcos.create(
            tipo=tipo,
            titulo=titulo,
            ordem=ordem,
            data_real=data_real,
            data_prevista=data_prevista,
            prazo_dias=prazo_dias,
            usuario_responsavel=usuario_responsavel or 'Sistema',
        )


def create_initial_cycle(imovel):
    if imovel.ciclos.exists():
        return current_cycle(imovel)
    ciclo = imovel.ciclos.create(
        numero=1,
        tipo='inicial',
        data_inicio=imovel.criado_em.date(),
    )
    rebuild_marcos(ciclo)
    return ciclo


def create_followup_cycle(imovel, tipo, usuario=None):
    ciclo_atual = current_cycle(imovel)
    next_number = (ciclo_atual.numero if ciclo_atual else 0) + 1
    ciclo = imovel.ciclos.create(
        numero=next_number,
        tipo=tipo,
        data_inicio=today_local(),
    )
    rebuild_marcos(ciclo, usuario=usuario)
    return ciclo


def area_display(value: Decimal | None):
    if value is None:
        return ''
    return f'{value:.2f}'.replace('.', ',')
