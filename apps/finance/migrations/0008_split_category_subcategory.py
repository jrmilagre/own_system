# Generated migration to split Category into Category and Subcategory

from django.db import migrations, models
import django.db.models.deletion


def migrate_category_to_subcategory(apps, schema_editor):
    """Migrate existing Category data to new Category and Subcategory models"""
    Category = apps.get_model('finance', 'Category')
    Subcategory = apps.get_model('finance', 'Subcategory')
    Transaction = apps.get_model('finance', 'Transaction')
    Scheduler = apps.get_model('finance', 'Scheduler')
    
    # Create a mapping of old Category IDs to new Subcategory IDs
    category_map = {}  # old_category_id -> new_subcategory_id
    
    # Get all unique category names and create simplified Category records
    unique_categories = {}  # category_name -> new_category_instance
    db_alias = schema_editor.connection.alias
    
    # First pass: collect unique category names and create Category records
    # Note: Category model still has old fields at this point, so we create with them
    for old_cat in Category.objects.using(db_alias).all().order_by('id'):
        cat_name = old_cat.category
        if cat_name not in unique_categories:
            # Check if a Category with this name already exists (from previous iteration)
            existing = Category.objects.using(db_alias).filter(category=cat_name).first()
            if existing and existing.id not in [c.id for c in unique_categories.values()]:
                # Use existing Category
                unique_categories[cat_name] = existing
            else:
                # Create new simplified Category (with old fields, will be cleaned later)
                new_cat = Category.objects.using(db_alias).create(
                    category=cat_name,
                    subcategory='',  # Temporary empty value
                    default_transaction_type='DB',  # Temporary default
                    created_at=old_cat.created_at,
                    updated_at=old_cat.updated_at
                )
                unique_categories[cat_name] = new_cat
    
    # Second pass: create Subcategory records
    for old_cat in Category.objects.using(db_alias).all():
        cat_name = old_cat.category
        new_cat = unique_categories[cat_name]
        
        # Create Subcategory
        new_subcat = Subcategory.objects.using(db_alias).create(
            category=new_cat,
            subcategory=old_cat.subcategory,
            default_transaction_type=old_cat.default_transaction_type,
            created_at=old_cat.created_at,
            updated_at=old_cat.updated_at
        )
        
        category_map[old_cat.id] = new_subcat.id
    
    # Update Transaction records
    for transaction in Transaction.objects.using(db_alias).all():
        if transaction.category_id in category_map:
            subcategory_id = category_map[transaction.category_id]
            old_cat = Category.objects.using(db_alias).get(id=transaction.category_id)
            transaction.subcategory_id = subcategory_id
            transaction.transaction_type = old_cat.default_transaction_type
            transaction.save(using=db_alias)
    
    # Update Scheduler records
    for scheduler in Scheduler.objects.using(db_alias).all():
        if scheduler.category_id in category_map:
            subcategory_id = category_map[scheduler.category_id]
            old_cat = Category.objects.using(db_alias).get(id=scheduler.category_id)
            scheduler.subcategory_id = subcategory_id
            scheduler.transaction_type = old_cat.default_transaction_type
            scheduler.save(using=db_alias)
    
    # Delete old Category records that were migrated
    # Keep only the new simplified ones we created
    new_category_ids = [c.id for c in unique_categories.values()]
    Category.objects.using(db_alias).exclude(id__in=new_category_ids).delete()


def reverse_migration(apps, schema_editor):
    """Reverse migration - not fully implemented as it's complex"""
    # This would need to merge Subcategory back into Category
    # For now, we'll just pass as this is a one-way migration
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0007_scheduler'),
    ]

    operations = [
        # Step 1: Create Subcategory model
        migrations.CreateModel(
            name='Subcategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True)),
                ('subcategory', models.CharField(max_length=200, verbose_name='Subcategoria')),
                ('default_transaction_type', models.CharField(choices=[('CR', 'Crédito'), ('DB', 'Débito')], default='DB', max_length=2, verbose_name='Tipo de transação padrão')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='finance.category', verbose_name='Categoria')),
            ],
            options={
                'verbose_name': 'Subcategoria',
                'verbose_name_plural': 'Subcategorias',
                'ordering': ('category', 'subcategory'),
            },
        ),
        # Step 2: Add transaction_type and subcategory fields to Transaction (nullable for now)
        migrations.AddField(
            model_name='transaction',
            name='subcategory',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='finance.subcategory', verbose_name='Subcategoria'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='transaction_type',
            field=models.CharField(choices=[('CR', 'Crédito'), ('DB', 'Débito')], default='DB', max_length=2, null=True, verbose_name='Tipo de transação'),
        ),
        # Step 3: Add transaction_type and subcategory fields to Scheduler (nullable for now)
        migrations.AddField(
            model_name='scheduler',
            name='subcategory',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='finance.subcategory', verbose_name='Subcategoria'),
        ),
        migrations.AddField(
            model_name='scheduler',
            name='transaction_type',
            field=models.CharField(choices=[('CR', 'Crédito'), ('DB', 'Débito')], default='DB', max_length=2, null=True, verbose_name='Tipo de transação'),
        ),
        # Step 4: Migrate data
        migrations.RunPython(migrate_category_to_subcategory, reverse_migration),
        # Step 5: Remove old category field from Transaction and make subcategory required
        migrations.RemoveField(
            model_name='transaction',
            name='category',
        ),
        migrations.AlterField(
            model_name='transaction',
            name='subcategory',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='finance.subcategory', verbose_name='Subcategoria'),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='transaction_type',
            field=models.CharField(choices=[('CR', 'Crédito'), ('DB', 'Débito')], default='DB', max_length=2, verbose_name='Tipo de transação'),
        ),
        # Step 6: Remove old category field from Scheduler and make subcategory required
        migrations.RemoveField(
            model_name='scheduler',
            name='category',
        ),
        migrations.AlterField(
            model_name='scheduler',
            name='subcategory',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='finance.subcategory', verbose_name='Subcategoria'),
        ),
        migrations.AlterField(
            model_name='scheduler',
            name='transaction_type',
            field=models.CharField(choices=[('CR', 'Crédito'), ('DB', 'Débito')], default='DB', max_length=2, verbose_name='Tipo de transação'),
        ),
        # Step 7: Remove old fields from Category model
        migrations.RemoveField(
            model_name='category',
            name='subcategory',
        ),
        migrations.RemoveField(
            model_name='category',
            name='default_transaction_type',
        ),
        # Step 8: Update Category Meta
        migrations.AlterModelOptions(
            name='category',
            options={'ordering': ('category',), 'verbose_name': 'Categoria', 'verbose_name_plural': 'Categorias'},
        ),
    ]

