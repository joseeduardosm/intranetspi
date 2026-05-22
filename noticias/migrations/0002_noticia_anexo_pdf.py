from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('noticias', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='noticia',
            name='anexo_pdf',
            field=models.FileField(blank=True, upload_to='noticias/anexos/', verbose_name='PDF anexo'),
        ),
    ]
