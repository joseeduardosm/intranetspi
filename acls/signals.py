from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.apps import apps

@receiver(post_migrate)
def sync_local_apps_as_recursos(sender, **kwargs):
    # Executado apenas quando o app 'acls' finaliza suas migrações
    if sender.name != 'acls':
        return

    from acls.models import Recurso

    for app_config in apps.get_app_configs():
        # Considera como locais os apps dentro do diretório do projeto e que NÃO estão no ambiente virtual
        if app_config.path.startswith('/root/aplicacoesspi') and '/.venv/' not in app_config.path:
            # Ignora os apps padrão do Django
            if not app_config.name.startswith('django.'):
                slug = app_config.name
                # Tenta gerar um nome amigável a partir do verbose_name ou nome da pasta
                nome = getattr(app_config, 'verbose_name', None) or slug.replace('_', ' ').title()
                
                # Garante o cadastro do recurso
                recurso, created = Recurso.objects.get_or_create(
                    slug=slug,
                    defaults={
                        'nome': nome,
                        'descricao': f"Aplicativo local auto-detectado: {nome}"
                    }
                )
                if created:
                    print(f"ACL: Novo app local '{nome}' auto-detectado e cadastrado como recurso.")

    # Garante o recurso extra 'organograma' de forma segregada
    from acls.models import Recurso
    Recurso.objects.get_or_create(
        slug='organograma',
        defaults={
            'nome': 'Organograma',
            'descricao': 'Organograma institucional dos setores'
        }
    )
