from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('consulta_scoring_app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='evaluacionscoring',
            name='banda',
            field=models.CharField(blank=True, default='', max_length=1),
        ),
        migrations.AddField(
            model_name='evaluacionscoring',
            name='nivel_riesgo',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='evaluacionscoring',
            name='cuota_maxima_estimada_gs',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='evaluacionscoring',
            name='ofertas',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
