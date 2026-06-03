from django.db import migrations


SETORES = [
    ("Secretaria de Parcerias em Investimentos", None),
    ("Secretaria Executiva", "Secretaria de Parcerias em Investimentos"),
    ("Chefia de Gabinete", "Secretaria de Parcerias em Investimentos"),
    ("Consultoria Jurídica", "Secretaria de Parcerias em Investimentos"),
    ("Ouvidoria", "Secretaria de Parcerias em Investimentos"),
    ("Grupo Setorial de Planejamento, Orçamento e Finanças Públicas – GSPOFP", "Secretaria de Parcerias em Investimentos"),
    ("Grupo Setorial de Transformação Digital e Tecnologia da Informação e Comunicação - GSTD-TIC", "Secretaria de Parcerias em Investimentos"),
    ("Subsecretaria de Gestão de Parcerias de Estado", "Secretaria de Parcerias em Investimentos"),
    ("Diretoria de Estruturação de Parcerias", "Subsecretaria de Gestão de Parcerias de Estado"),
    ("Coordenadoria de Estruturação de Parcerias em Rodovias", "Diretoria de Estruturação de Parcerias"),
    ("Coordenadoria de Estruturação de Parcerias em Mobilidade Urbana", "Diretoria de Estruturação de Parcerias"),
    ("Coordenadoria de Estruturação de Parcerias em Água e Energia", "Diretoria de Estruturação de Parcerias"),
    ("Coordenadoria de Estruturação de Parcerias Sociais", "Diretoria de Estruturação de Parcerias"),
    ("Diretoria de Gestão de Parcerias em Transporte", "Subsecretaria de Gestão de Parcerias de Estado"),
    ("Coordenadoria de Gestão de Parcerias em Rodovias", "Diretoria de Gestão de Parcerias em Transporte"),
    ("Coordenadoria de Gestão de Parcerias em Mobilidade Urbana", "Diretoria de Gestão de Parcerias em Transporte"),
    ("Diretoria de Gestão de Parcerias em Serviços", "Subsecretaria de Gestão de Parcerias de Estado"),
    ("Coordenadoria de Gestão de Água e Energia", "Diretoria de Gestão de Parcerias em Serviços"),
    ("Coordenadoria de Gestão de Parcerias Sociais", "Diretoria de Gestão de Parcerias em Serviços"),
    ("Subsecretaria de Gestão Corporativa", "Secretaria de Parcerias em Investimentos"),
    ("Serviço de Apoio Administrativo", "Subsecretaria de Gestão Corporativa"),
    ("Diretoria de Orçamento e Finanças", "Subsecretaria de Gestão Corporativa"),
    ("Coordenadoria de Orçamento, Metas e Acompanhamento", "Diretoria de Orçamento e Finanças"),
    ("Coordenadoria de Finanças", "Diretoria de Orçamento e Finanças"),
    ("Diretoria de Gestão Administrativa", "Subsecretaria de Gestão Corporativa"),
    ("Coordenadoria de Gestão e Infraestrutura", "Diretoria de Gestão Administrativa"),
    ("Coordenadoria de Gestão de Pessoas", "Diretoria de Gestão Administrativa"),
    ("Coordenadoria de Contratação e Convênios", "Diretoria de Gestão Administrativa"),
]


def seed_setores(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    SetorNode = apps.get_model("setores", "SetorNode")

    nodes_by_name = {}

    for nome, _parent_name in SETORES:
        group, _ = Group.objects.get_or_create(name=nome)
        setor, _ = SetorNode.objects.get_or_create(group=group, defaults={"ativo": True})
        if not setor.ativo:
            setor.ativo = True
            setor.save(update_fields=["ativo", "atualizado_em"])
        nodes_by_name[nome] = setor

    for nome, parent_name in SETORES:
        setor = nodes_by_name[nome]
        parent = nodes_by_name.get(parent_name) if parent_name else None
        if setor.parent_id != (parent.id if parent else None):
            setor.parent = parent
            setor.save(update_fields=["parent", "atualizado_em"])


class Migration(migrations.Migration):

    dependencies = [
        ("setores", "0002_reset_setores_usuarios"),
    ]

    operations = [
        migrations.RunPython(seed_setores, migrations.RunPython.noop),
    ]
