from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('consulta_scoring_app', '0002_reglas_crediticias'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Solicitante',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cedula', models.CharField(db_index=True, max_length=12, unique=True)),
                ('nombres', models.CharField(max_length=120)),
                ('apellidos', models.CharField(max_length=120)),
                ('fecha_nacimiento', models.DateField()),
                ('ciudad', models.CharField(max_length=100)),
                ('ocupacion', models.CharField(max_length=120)),
                ('situacion_laboral', models.CharField(choices=[
                    ('DEPENDIENTE', 'Empleado dependiente'),
                    ('INDEPENDIENTE', 'Trabajador independiente'),
                    ('DESEMPLEADO', 'Desempleado'),
                    ('JUBILADO', 'Jubilado'),
                    ('OTRO', 'Otro'),
                ], max_length=20)),
                ('fecha_registro', models.DateTimeField(auto_now_add=True)),
                ('creado_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                 related_name='solicitantes_registrados', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['apellidos', 'nombres', 'id']},
        ),
        migrations.AddField(
            model_name='evaluacionscoring', name='solicitante',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='evaluaciones', to='consulta_scoring_app.solicitante'),
        ),
        migrations.CreateModel(
            name='DecisionCredito',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado', models.CharField(choices=[
                    ('APROBADA', 'Aprobada (simulada)'),
                    ('CONDICIONAL', 'Condicional (simulada)'),
                    ('RECHAZADA', 'Rechazada (simulada)'),
                ], max_length=12)),
                ('producto_codigo', models.CharField(blank=True, default='', max_length=32)),
                ('motivo', models.TextField(max_length=1200)),
                ('fecha_hora', models.DateTimeField(auto_now_add=True)),
                ('evaluacion', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                                                   related_name='decision_crediticia',
                                                   to='consulta_scoring_app.evaluacionscoring')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                             related_name='decisiones_registradas', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-fecha_hora']},
        ),
    ]
