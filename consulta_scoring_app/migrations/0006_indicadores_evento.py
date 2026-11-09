from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('consulta_scoring_app', '0005_seguimiento_crediticio'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventoauditoria',
            name='accion',
            field=models.CharField(
                choices=[
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
                    ('INDICADORES_CONSULTADOS', 'Indicadores consultados'),
                ],
                db_index=True, max_length=40,
            ),
        ),
    ]
