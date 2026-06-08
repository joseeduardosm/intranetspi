# Criado por José Eduardo Santana Martins em 04/06/2026
# Injeta no template base o estado de recadastro e a lista mensal de aniversariantes.
from django.utils import timezone
from .models import UsuarioPerfil
from .services import profile_update_context


def usuario_profile_state(request):
    """Combina bloqueio de perfil com aniversariantes do mês para todos os templates."""

    ctx = profile_update_context(request)
    
    hoje = timezone.now()
    mes_atual = hoje.month
    
    # Busca aniversariantes ativos do mês atual com os dados necessários para
    # abrir o cartão de contato diretamente da barra global da intranet.
    perfis_aniversariantes = UsuarioPerfil.objects.filter(
        data_nascimento__month=mes_atual,
        user__is_active=True
    ).select_related('user').order_by('data_nascimento__day', 'nome_completo')
    
    aniversariantes_list = []
    for perfil in perfis_aniversariantes:
        # O template espera dia e mês já formatados com dois dígitos.
        dia = str(perfil.data_nascimento.day).zfill(2)
        mes = str(perfil.data_nascimento.month).zfill(2)
        nome = perfil.nome_completo or perfil.user.username
        aniversariantes_list.append({
            'id': perfil.pk,
            'nome': nome,
            'dia': dia,
            'mes': mes,
            'iniciais': ''.join(parte[0].upper() for parte in nome.split()[:2] if parte) or nome[:1].upper(),
            'cargo': perfil.cargo or '-',
            'setor': perfil.setor or '-',
            'email': perfil.user.email or '-',
            'ramal': perfil.ramal or '-',
            'celular': perfil.celular or '',
            'whatsapp': perfil.whatsapp_url or '',
            'local': perfil.andar_bloco_display or '-',
            'foto_url': perfil.foto.url if perfil.foto else '',
        })
        
    ctx['aniversariantes'] = aniversariantes_list
    return ctx
