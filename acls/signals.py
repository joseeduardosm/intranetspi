# Criado por José Eduardo Santana Martins em 04/06/2026

from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.apps import apps


@receiver(post_migrate)
def sync_local_apps_as_recursos(sender, **kwargs):
    """Cadastra apps locais como recursos protegíveis após as migrações do ACL."""

    # Executado apenas quando o app 'acls' finaliza suas migrações.
    if sender.name != 'acls':
        return

    from acls.models import Recurso

    for app_config in apps.get_app_configs():
        # Considera locais os apps do projeto, ignorando dependências e ambiente virtual.
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
                        'descricao': f"Aplicativo local auto-detectado: {nome}",
                        'url_base': getattr(app_config, 'acl_url_base', ''),
                    }
                )
                url_base = getattr(app_config, 'acl_url_base', '')
                if not created and url_base and recurso.url_base != url_base:
                    recurso.url_base = url_base
                    recurso.save(update_fields=['url_base'])
                if created:
                    print(f"ACL: Novo app local '{nome}' auto-detectado e cadastrado como recurso.")
