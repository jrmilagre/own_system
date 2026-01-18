# Generated manually - Remove unique_together constraint to allow multiple budgets per subcategory/month

from django.db import migrations


def remove_unique_constraint(apps, schema_editor):
    """Remove a constraint unique_together do banco de dados SQLite"""
    if 'sqlite' in schema_editor.connection.vendor:
        with schema_editor.connection.cursor() as cursor:
            # No SQLite, unique_together cria um índice único
            # Precisamos encontrar e remover esse índice
            cursor.execute("""
                SELECT name, sql FROM sqlite_master 
                WHERE type='index' 
                AND tbl_name='finance_budget'
                AND sql LIKE '%UNIQUE%'
            """)
            indexes = cursor.fetchall()
            for index_name, index_sql in indexes:
                if index_name and index_sql and ('subcategory' in str(index_sql).lower() and 'budget_date' in str(index_sql).lower()):
                    try:
                        cursor.execute(f"DROP INDEX IF EXISTS {index_name}")
                    except Exception:
                        # Se falhar, tentar sem IF EXISTS
                        try:
                            cursor.execute(f"DROP INDEX {index_name}")
                        except:
                            pass


def reverse_remove_constraint(apps, schema_editor):
    """Reverter: recriar a constraint (não implementado - seria complexo)"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0032_add_notes_to_budget'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='budget',
            unique_together=set(),
        ),
        migrations.RunPython(remove_unique_constraint, reverse_remove_constraint, atomic=False),
    ]
