from django.db import migrations


def update_resource_name(apps, schema_editor):
    """Alinha slug e nome exibido do recurso ACL ao novo nome do módulo."""

    Recurso = apps.get_model("acls", "Recurso")
    Recurso.objects.filter(slug="reservas_recursos").update(
        slug="reserva_espacos",
        nome="Reserva de Espaços",
    )
    Recurso.objects.filter(slug="reserva_espacos").update(nome="Reserva de Espaços")


def revert_resource_name(apps, schema_editor):
    """Restaura o slug e o nome anteriores caso a migração seja revertida."""

    Recurso = apps.get_model("acls", "Recurso")
    Recurso.objects.filter(slug="reserva_espacos").update(
        slug="reservas_recursos",
        nome="Reservas de Recursos",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("acls", "0004_regraacesso_multiplos_alvos"),
        ("reservas_recursos", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(update_resource_name, revert_resource_name),
    ]
