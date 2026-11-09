from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('consulta_scoring_app', '0003_solicitantes_y_decisiones'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventoAuditoria',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('usuario_nombre', models.CharField(help_text='Usuario al momento del evento.', max_length=150)),
                ('fecha_hora', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('accion', models.CharField(choices=[('SOLICITANTE_CREADO', 'Ficha creada'), ('SOLICITANTE_CONSULTADO', 'Ficha consultada'), ('EVALUACION_CREADA', 'Evaluación creada'), ('EVALUACION_CONSULTADA', 'Evaluación consultada'), ('HISTORIAL_CONSULTADO', 'Historial consultado'), ('DECISION_CREADA', 'Decisión registrada'), ('USUARIO_CREADO', 'Usuario creado'), ('ROL_MODIFICADO', 'Rol modificado'), ('ACCESO_DENEGADO', 'Acceso denegado'), ('AUDITORIA_CONSULTADA', 'Auditoría consultada')], db_index=True, max_length=40)),
                ('resultado', models.CharField(choices=[('EXITO', 'Realizada'), ('DENEGADO', 'Denegada')], default='EXITO', max_length=8)),
                ('recurso', models.CharField(blank=True, default='', max_length=35)),
                ('objeto_id', models.PositiveBigIntegerField(blank=True, null=True)),
                ('detalle', models.CharField(blank=True, default='', help_text='Resumen técnico, sin cédula ni datos sensibles.', max_length=180)),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='eventos_auditoria', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Evento de auditoría', 'verbose_name_plural': 'Eventos de auditoría', 'ordering': ['-fecha_hora', '-id']},
        ),
        migrations.AddIndex(
            model_name='eventoauditoria',
            index=models.Index(fields=['recurso', 'objeto_id'], name='audit_recurso_obj_idx'),
        ),
    ]
