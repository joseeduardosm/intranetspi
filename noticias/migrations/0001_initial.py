from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Noticia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('imagem_destaque', models.ImageField(upload_to='noticias/destaques/', verbose_name='Imagem destaque')),
                ('titulo', models.CharField(max_length=220, verbose_name='Titulo')),
                ('texto_noticia', models.TextField(verbose_name='Texto da noticia')),
                ('data_publicacao', models.DateTimeField(blank=True, null=True, verbose_name='Data de publicacao')),
                ('status', models.CharField(choices=[('RASCUNHO', 'Rascunho'), ('AGENDADA', 'Agendada'), ('PUBLICADA', 'Publicada')], default='RASCUNHO', max_length=20)),
                ('fixada', models.BooleanField(default=False, verbose_name='Fixada')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Noticia',
                'verbose_name_plural': 'Noticias',
                'ordering': ['-fixada', '-data_publicacao', '-id'],
            },
        ),
    ]
