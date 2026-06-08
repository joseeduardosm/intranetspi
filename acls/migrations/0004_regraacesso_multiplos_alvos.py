from django.conf import settings
from django.db import migrations, models


def migrar_alvos_existentes(apps, schema_editor):
    """Copia os alvos legados de usuário/grupo para os novos relacionamentos múltiplos."""

    RegraAcesso = apps.get_model('acls', 'RegraAcesso')

    for regra in RegraAcesso.objects.exclude(usuario_id=None):
        regra.usuarios.add(regra.usuario_id)

    for regra in RegraAcesso.objects.exclude(grupo_id=None):
        regra.grupos.add(regra.grupo_id)


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('acls', '0003_alter_regraacesso_grupo_alter_regraacesso_usuario'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='regraacesso',
            name='grupos',
            field=models.ManyToManyField(
                blank=True,
                help_text='Selecione zero ou vários grupos/setores para aplicar a regra.',
                related_name='regras_acesso',
                to='auth.group',
                verbose_name='Grupos/Setores',
            ),
        ),
        migrations.AddField(
            model_name='regraacesso',
            name='usuarios',
            field=models.ManyToManyField(
                blank=True,
                help_text='Selecione zero ou vários usuários para aplicar a regra.',
                related_name='regras_acesso',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Usuários',
            ),
        ),
        migrations.RunPython(migrar_alvos_existentes, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='regraacesso',
            name='grupo',
        ),
        migrations.RemoveField(
            model_name='regraacesso',
            name='usuario',
        ),
    ]
