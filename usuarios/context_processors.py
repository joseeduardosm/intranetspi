from django.utils import timezone
from .models import UsuarioPerfil
from .services import profile_update_context


def usuario_profile_state(request):
    ctx = profile_update_context(request)
    
    hoje = timezone.now()
    mes_atual = hoje.month
    
    # Query matching the current month for active users
    perfis_aniversariantes = UsuarioPerfil.objects.filter(
        data_nascimento__month=mes_atual,
        user__is_active=True
    ).order_by('data_nascimento__day', 'nome_completo')
    
    aniversariantes_list = []
    for perfil in perfis_aniversariantes:
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


