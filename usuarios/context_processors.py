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
    
    # Busca aniversariantes ativos do mês atual para a barra global da intranet.
    perfis_aniversariantes = UsuarioPerfil.objects.filter(
        data_nascimento__month=mes_atual,
        user__is_active=True
    ).order_by('data_nascimento__day', 'nome_completo')
    
    aniversariantes_list = []
    for perfil in perfis_aniversariantes:
        # O template espera dia e mês já formatados com dois dígitos.
        dia = str(perfil.data_nascimento.day).zfill(2)
        mes = str(perfil.data_nascimento.month).zfill(2)
        nome = perfil.nome_completo or perfil.user.username
        aniversariantes_list.append({
            'nome': nome,
            'dia': dia,
            'mes': mes
        })
        
    ctx['aniversariantes'] = aniversariantes_list
    return ctx

