from django.db import migrations


def reset_usuario_setores(apps, schema_editor):
    UsuarioPerfil = apps.get_model('usuarios', 'UsuarioPerfil')
    UsuarioPerfil.objects.all().update(setor='', ultimo_recadastro_em=None)


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0004_alter_usuarioperfil_andar'),
        ('setores', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(reset_usuario_setores, migrations.RunPython.noop),
    ]
