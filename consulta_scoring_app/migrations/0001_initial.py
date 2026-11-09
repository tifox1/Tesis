from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='EvaluacionScoring',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_hora', models.DateTimeField(auto_now_add=True)),
                ('entradas', models.JSONField()),
                ('pd', models.FloatField(help_text='Probabilidad estimada del evento objetivo.')),
                ('score', models.FloatField()),
                ('advertencias', models.JSONField(blank=True, default=list)),
                ('modelo_version', models.CharField(default='credit_score_v1', max_length=50)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='evaluaciones_scoring', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-fecha_hora']},
        ),
    ]
