from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='NavbarItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=120, verbose_name='Titulo')),
                ('url', models.CharField(max_length=500, verbose_name='URL')),
                ('ordem', models.PositiveIntegerField(default=1)),
                ('ativo', models.BooleanField(default=True)),
                ('abrir_nova_aba', models.BooleanField(default=False, verbose_name='Abrir em nova aba')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='filhos', to='navbar.navbaritem', verbose_name='Item pai')),
            ],
            options={
                'verbose_name': 'Item da navbar',
                'verbose_name_plural': 'Itens da navbar',
                'ordering': ['ordem', 'titulo', 'id'],
            },
        ),
    ]
