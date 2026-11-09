from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('consulta_scoring_app', '0004_evento_auditoria'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SeguimientoCredito',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_otorgamiento', models.DateField(help_text='Fecha simulada de otorgamiento.')),
                ('fecha_cierre_prevista', models.DateField(help_text='Vencimiento previsto; no representa un resultado observado.')),
                ('fecha_observacion', models.DateField(help_text='Fecha hasta la cual se declara observado el crédito ficticio.')),
                ('estado', models.CharField(choices=[('VIGENTE', 'Vigente (simulado)'), ('VENCIDO', 'Vencido (simulado)'), ('CANCELADO', 'Cancelado (simulado)')], default='VIGENTE', max_length=12)),
                ('max_dias_mora', models.PositiveIntegerField(default=0, help_text='Máximo de días en mora reportados hasta la observación.')),
                ('observaciones', models.TextField(blank=True, default='', max_length=500)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True)),
                ('decision', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='seguimiento', to='consulta_scoring_app.decisioncredito')),
                ('creado_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='seguimientos_creados', to=settings.AUTH_USER_MODEL)),
                ('actualizado_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='seguimientos_actualizados', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-fecha_actualizacion', '-id'],
                'verbose_name': 'Seguimiento académico',
                'verbose_name_plural': 'Seguimientos académicos',
            },
        ),
        migrations.AlterField(
            model_name='eventoauditoria', name='accion',
            field=models.CharField(max_length=40, db_index=True, choices=[
                ('SOLICITANTE_CREADO', 'Ficha creada'),
                ('SOLICITANTE_CONSULTADO', 'Ficha consultada'),
                ('EVALUACION_CREADA', 'Evaluación creada'),
                ('EVALUACION_CONSULTADA', 'Evaluación consultada'),
                ('HISTORIAL_CONSULTADO', 'Historial consultado'),
                ('DECISION_CREADA', 'Decisión registrada'),
                ('SEGUIMIENTO_CREADO', 'Seguimiento creado'),
                ('SEGUIMIENTO_ACTUALIZADO', 'Seguimiento actualizado'),
                ('SEGUIMIENTO_CONSULTADO', 'Seguimiento consultado'),
                ('USUARIO_CREADO', 'Usuario creado'),
                ('ROL_MODIFICADO', 'Rol modificado'),
                ('ACCESO_DENEGADO', 'Acceso denegado'),
                ('AUDITORIA_CONSULTADA', 'Auditoría consultada'),
            ]),
        ),
    ]
