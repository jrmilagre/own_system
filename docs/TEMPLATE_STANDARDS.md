# Padrão de Templates - Filtros e Tabelas

Este documento define o padrão para criação de templates de listagem com filtros e tabelas, baseado no template de transações (`apps/finance/templates/finance/transaction_list.html`).

## Índice

1. [Estrutura Geral](#estrutura-geral)
2. [Filtros com Dropdowns e Checkboxes](#filtros-com-dropdowns-e-checkboxes)
3. [Tabelas com Ordenação Múltipla](#tabelas-com-ordenação-múltipla)
4. [Estilos CSS Padrão](#estilos-css-padrão)
5. [JavaScript Padrão](#javascript-padrão)
6. [Formulários Django](#formulários-django)
7. [Views Django](#views-django)
8. [Boas Práticas](#boas-práticas)

---

## Estrutura Geral

### Blocos do Template

```django
{% extends 'finance/base.html' %}

{% block section_name %}Nome da Seção{% endblock %}
{% block title %}Título da Página{% endblock %}

{% block content %}
    <!-- Conteúdo principal -->
{% endblock %}

{% block extra_css %}
    <!-- Estilos adicionais -->
{% endblock %}

{% block extra_js %}
    <!-- Scripts JavaScript -->
{% endblock %}
```

### Estrutura da Página

1. **Cabeçalho com ações** (botões de criar, etc.)
2. **Card de Filtros** (com dropdowns e checkboxes)
3. **Card de Tabela** (com ordenação múltipla)
4. **Paginação** (se aplicável)

---

## Filtros com Dropdowns e Checkboxes

### Estrutura do Card de Filtros

```django
<!-- Formulário de Filtros -->
<div class="card shadow-sm border-0 mb-3">
    <div class="card-header bg-light">
        <h5 class="mb-0"><i class="fas fa-filter me-2"></i>Filtros</h5>
    </div>
    <div class="card-body">
        <form method="get" action="{% url 'app:view_name' %}" class="row g-3">
            <!-- Campos de filtro aqui -->
            
            <div class="col-12">
                <button type="submit" class="btn btn-primary btn-sm">
                    <i class="fas fa-search me-1"></i>Filtrar
                </button>
                <a href="{% url 'app:view_name' %}" class="btn btn-secondary btn-sm">
                    <i class="fas fa-times me-1"></i>Limpar
                </a>
            </div>
        </form>
    </div>
</div>
```

### Dropdown com Checkboxes (Seleção Múltipla)

**Template:**

```django
<div class="col-md-6 col-lg-2">
    <label class="form-label">{{ filter_form.field_name.label }}</label>
    <div class="dropdown">
        <button class="btn btn-outline-secondary form-control dropdown-toggle text-start" 
                type="button" 
                id="fieldNameDropdown" 
                data-bs-toggle="dropdown" 
                aria-expanded="false">
            <span class="selected-count" data-field="field_name">Selecione...</span>
        </button>
        <ul class="dropdown-menu" 
            aria-labelledby="fieldNameDropdown" 
            style="max-height: 300px; overflow-y: auto; overflow-x: visible; min-width: 100%;">
            <li>
                <div class="px-3 py-2 border-bottom">
                    <button type="button" 
                            class="btn btn-sm btn-link p-0 select-all-btn" 
                            data-field="field_name">
                        <i class="fas fa-check-double me-1"></i>Selecionar todas
                    </button>
                </div>
            </li>
            {% for checkbox in filter_form.field_name %}
            <li>
                <div class="form-check py-1">
                    {{ checkbox.tag }}
                    <label class="form-check-label w-100" for="{{ checkbox.id_for_label }}">
                        {{ checkbox.choice_label }}
                    </label>
                </div>
            </li>
            {% endfor %}
        </ul>
    </div>
</div>
```

**Características:**
- Dropdown com botão que mostra contagem de selecionados
- Lista de checkboxes dentro do dropdown
- Botão "Selecionar todas" no topo
- Scroll automático para listas longas
- Contagem dinâmica no botão do dropdown

### Campos de Data

```django
<div class="col-md-6 col-lg-2">
    <label for="{{ filter_form.date_start.id_for_label }}" class="form-label">
        {{ filter_form.date_start.label }}
    </label>
    {{ filter_form.date_start }}
</div>
```

---

## Tabelas com Ordenação Múltipla

### Estrutura da Tabela

```django
{% if items %}
<div class="card shadow-sm border-0">
    <div class="card-body p-0">
        <div class="table-responsive">
            <table class="table table-hover table-sm mb-0" style="font-size: 0.9rem;">
                <thead class="table-light">
                    <tr>
                        <!-- Cabeçalhos com ordenação -->
                    </tr>
                </thead>
                <tbody>
                    <!-- Linhas da tabela -->
                </tbody>
                <tfoot class="table-light">
                    <!-- Rodapé (opcional) -->
                </tfoot>
            </table>
        </div>
    </div>
</div>
{% else %}
<div class="alert alert-info">
    <i class="fas fa-info-circle me-2"></i>Nenhum item cadastrado.
</div>
{% endif %}
```

### Cabeçalho com Ordenação Múltipla

```django
<th class="ps-3 sortable-header" data-sort="field_name" style="cursor: pointer;">
    Nome da Coluna
    {% if 'field_name' in sort_info %}
        <span class="badge bg-primary ms-1">{{ sort_info.field_name.priority }}</span>
        <i class="fas fa-sort-{% if sort_info.field_name.order == 'asc' %}up{% else %}down{% endif %} ms-1"></i>
    {% else %}
        <i class="fas fa-sort ms-1" style="opacity: 0.3;"></i>
    {% endif %}
</th>
```

**Características:**
- Clique normal: define ordenação principal
- Shift+Click: adiciona ordenação secundária
- Badge numérico mostra prioridade (1, 2, 3...)
- Ícones indicam direção (up/down)

### Linhas da Tabela

```django
{% for item in items %}
<tr class="table-row-compact">
    <td class="ps-3 py-1">
        <!-- Conteúdo da célula -->
    </td>
    <!-- Mais células -->
    <td class="pe-3 py-1">
        <div class="btn-group btn-group-sm compact-buttons" role="group">
            <a href="{% url 'app:update' item.pk %}" 
               class="btn btn-sm btn-outline-primary compact-btn" 
               title="Editar">
                <i class="fas fa-edit"></i>
            </a>
            <a href="{% url 'app:delete' item.pk %}" 
               class="btn btn-sm btn-outline-danger compact-btn" 
               title="Excluir">
                <i class="fas fa-trash"></i>
            </a>
        </div>
    </td>
</tr>
{% endfor %}
```

### Rodapé da Tabela (Opcional)

```django
<tfoot class="table-light">
    <tr>
        <td colspan="X" class="text-end fw-bold">Subtotal (página):</td>
        <td class="text-end fw-bold">R$ {{ subtotal|floatformat:2 }}</td>
        <td colspan="Y"></td>
    </tr>
</tfoot>
```

---

## Estilos CSS Padrão

### Estilos para Dropdowns com Checkboxes

```css
<style>
    .dropdown-menu {
        padding: 0.5rem 0 !important;
    }
    .dropdown-menu .form-check {
        padding-left: 2rem !important;
        padding-right: 1rem !important;
        margin-bottom: 0;
    }
    .dropdown-menu .form-check-input {
        position: absolute;
        left: 0.75rem;
        margin-top: 0.25rem;
        margin-left: 0;
    }
    .dropdown-menu li {
        overflow: visible !important;
        position: relative;
    }
    .dropdown-menu .form-check-label {
        padding-left: 0.5rem;
    }
</style>
```

### Estilos para Tabelas

```css
<style>
.table-row-compact td {
    padding-top: 0.25rem !important;
    padding-bottom: 0.25rem !important;
    vertical-align: middle;
}

.compact-buttons .compact-btn {
    padding: 0.15rem 0.4rem !important;
    font-size: 0.75rem;
    line-height: 1.2;
}

.compact-buttons .compact-btn i {
    font-size: 0.75rem;
}

.sortable-header {
    user-select: none;
    transition: background-color 0.2s;
}

.sortable-header:hover {
    background-color: rgba(0, 0, 0, 0.05) !important;
}
</style>
```

---

## JavaScript Padrão

### Função de Atualização de Contagem

```javascript
function updateSelectedCount(fieldName) {
    const checkboxes = document.querySelectorAll(`input[name="${fieldName}"]`);
    const checked = Array.from(checkboxes).filter(cb => cb.checked);
    const countSpan = document.querySelector(`.selected-count[data-field="${fieldName}"]`);
    
    if (checked.length === 0) {
        countSpan.textContent = 'Selecione...';
    } else if (checked.length === checkboxes.length) {
        countSpan.textContent = `Todos (${checked.length})`;
    } else {
        countSpan.textContent = `${checked.length} selecionado(s)`;
    }
}
```

### Inicialização de Contadores

```javascript
// Atualizar contagem inicial para cada campo
['field1', 'field2', 'field3'].forEach(fieldName => {
    updateSelectedCount(fieldName);
    
    // Atualizar contagem quando checkboxes mudarem
    document.querySelectorAll(`input[name="${fieldName}"]`).forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            updateSelectedCount(fieldName);
        });
    });
});
```

### Botão "Selecionar Todas"

```javascript
document.querySelectorAll('.select-all-btn').forEach(button => {
    button.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const fieldName = this.getAttribute('data-field');
        const checkboxes = document.querySelectorAll(`input[name="${fieldName}"]`);
        const allChecked = Array.from(checkboxes).every(cb => cb.checked);
        
        // Alternar: se todos estão marcados, desmarcar todos; caso contrário, marcar todos
        checkboxes.forEach(checkbox => {
            checkbox.checked = !allChecked;
        });
        
        // Atualizar texto do botão
        if (!allChecked) {
            this.innerHTML = '<i class="fas fa-times me-1"></i>Desmarcar todas';
        } else {
            this.innerHTML = '<i class="fas fa-check-double me-1"></i>Selecionar todas';
        }
        
        // Atualizar contagem
        updateSelectedCount(fieldName);
    });
});
```

### Prevenir Fechamento do Dropdown

```javascript
// Prevenir que o dropdown feche ao clicar nos checkboxes
document.querySelectorAll('.dropdown-menu').forEach(menu => {
    menu.addEventListener('click', function(e) {
        if (e.target.type === 'checkbox' || e.target.closest('.form-check')) {
            e.stopPropagation();
        }
    });
});
```

### Ordenação Múltipla

```javascript
document.querySelectorAll('.sortable-header').forEach(header => {
    header.addEventListener('click', function(event) {
        const sortField = this.getAttribute('data-sort');
        const urlParams = new URLSearchParams(window.location.search);
        
        // Obter ordenações atuais
        const currentSorts = urlParams.get('sort') ? urlParams.get('sort').split(',') : [];
        const currentOrders = urlParams.get('order') ? urlParams.get('order').split(',') : [];
        
        let newSorts = [];
        let newOrders = [];
        
        if (event.shiftKey && currentSorts.length > 0) {
            // Shift+Click: adicionar como ordenação secundária
            newSorts = [...currentSorts];
            newOrders = [...currentOrders];
            
            // Verificar se o campo já está na lista
            const existingIndex = newSorts.indexOf(sortField);
            if (existingIndex >= 0) {
                // Se já existe, alterna a ordem
                newOrders[existingIndex] = newOrders[existingIndex] === 'asc' ? 'desc' : 'asc';
            } else {
                // Adicionar novo campo
                newSorts.push(sortField);
                newOrders.push('desc');
            }
        } else {
            // Clique normal: definir como ordenação principal
            const existingIndex = currentSorts.indexOf(sortField);
            if (existingIndex === 0 && currentSorts.length > 0) {
                // Se é a primeira coluna, alterna a ordem
                newSorts = [sortField];
                newOrders = [currentOrders[0] === 'asc' ? 'desc' : 'asc'];
            } else {
                // Nova ordenação principal
                newSorts = [sortField];
                newOrders = ['desc'];
            }
        }
        
        // Atualizar parâmetros
        urlParams.set('sort', newSorts.join(','));
        urlParams.set('order', newOrders.join(','));
        urlParams.set('page', '1');
        
        // Redirecionar
        window.location.href = '?' + urlParams.toString();
    });
});
```

---

## Formulários Django

### Formulário com Seleção Múltipla

```python
from django import forms

class MyFilterForm(forms.Form):
    """Formulário de filtros para a lista"""
    field_name = forms.ModelMultipleChoiceField(
        queryset=MyModel.objects.all().order_by('name'),
        required=False,
        label='Nome do Campo',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    date_start = forms.DateField(
        required=False,
        label='Data início',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    date_end = forms.DateField(
        required=False,
        label='Data fim',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forçar avaliação dos querysets para evitar problemas com cursor do banco
        if self.fields['field_name'].queryset:
            list(self.fields['field_name'].queryset)
```

---

## Views Django

### View com Filtros Múltiplos e Ordenação Múltipla

```python
def my_list_view(request):
    """Lista de itens com filtros e paginação"""
    # Inicializar formulário de filtros
    filter_form = MyFilterForm(request.GET)
    
    # Query base
    items = MyModel.objects.all().select_related('related_field')
    
    # Aplicar filtros
    if filter_form.is_valid():
        field_values = filter_form.cleaned_data.get('field_name')
        date_start = filter_form.cleaned_data.get('date_start')
        date_end = filter_form.cleaned_data.get('date_end')
        
        if field_values:
            items = items.filter(field_name__in=field_values)
        
        if date_start or date_end:
            # Lógica de filtro de data
            pass
    
    # Ordenar - suporte para múltiplas colunas
    sort_fields_str = request.GET.get('sort', '')
    sort_orders_str = request.GET.get('order', 'desc')
    
    # Mapeamento de campos de ordenação
    sort_mapping = {
        'field1': 'field1__name',
        'field2': 'field2__name',
        'date': 'created_at',
    }
    
    # Processar múltiplos campos de ordenação (separados por vírgula)
    sort_fields = [f.strip() for f in sort_fields_str.split(',') if f.strip()] if sort_fields_str else []
    sort_orders = [o.strip() for o in sort_orders_str.split(',')] if sort_orders_str else []
    
    # Validar e aplicar ordenações
    order_fields = []
    valid_sorts = []
    valid_orders = []
    
    for i, sort_field in enumerate(sort_fields):
        if sort_field in sort_mapping:
            sort_order = sort_orders[i] if i < len(sort_orders) else 'desc'
            if sort_order not in ['asc', 'desc']:
                sort_order = 'desc'
            
            order_prefix = '' if sort_order == 'asc' else '-'
            order_fields.append(f"{order_prefix}{sort_mapping[sort_field]}")
            
            valid_sorts.append(sort_field)
            valid_orders.append(sort_order)
    
    if order_fields:
        items = items.order_by(*order_fields)
    else:
        # Ordenação padrão
        items = items.order_by('-created_at')
    
    # Paginação
    paginator = Paginator(items, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Criar dicionário com prioridade de cada campo ordenado
    sort_info = {}
    for idx, sort_field in enumerate(valid_sorts):
        sort_info[sort_field] = {
            'priority': idx + 1,
            'order': valid_orders[idx] if idx < len(valid_orders) else 'desc'
        }
    
    return render(request, 'app/my_list.html', {
        'items': page_obj,
        'filter_form': filter_form,
        'page_obj': page_obj,
        'sort_info': sort_info,
    })
```

---

## Paginação

### Template de Paginação

```django
{% if page_obj.has_other_pages %}
<nav aria-label="Paginação" class="mt-3">
    <ul class="pagination justify-content-center">
        {% if page_obj.has_previous %}
            <li class="page-item">
                <a class="page-link" href="?{% for key, value in request.GET.items %}{% if key != 'page' %}{{ key }}={{ value }}&{% endif %}{% endfor %}page=1">
                    <i class="fas fa-angle-double-left"></i> Primeira
                </a>
            </li>
            <li class="page-item">
                <a class="page-link" href="?{% for key, value in request.GET.items %}{% if key != 'page' %}{{ key }}={{ value }}&{% endif %}{% endfor %}page={{ page_obj.previous_page_number }}">
                    <i class="fas fa-angle-left"></i> Anterior
                </a>
            </li>
        {% endif %}
        
        <li class="page-item active">
            <span class="page-link">
                Página {{ page_obj.number }} de {{ page_obj.paginator.num_pages }}
            </span>
        </li>
        
        {% if page_obj.has_next %}
            <li class="page-item">
                <a class="page-link" href="?{% for key, value in request.GET.items %}{% if key != 'page' %}{{ key }}={{ value }}&{% endif %}{% endfor %}page={{ page_obj.next_page_number }}">
                    Próxima <i class="fas fa-angle-right"></i>
                </a>
            </li>
            <li class="page-item">
                <a class="page-link" href="?{% for key, value in request.GET.items %}{% if key != 'page' %}{{ key }}={{ value }}&{% endif %}{% endfor %}page={{ page_obj.paginator.num_pages }}">
                    Última <i class="fas fa-angle-double-right"></i>
                </a>
            </li>
        {% endif %}
    </ul>
    <div class="text-center text-muted small">
        Mostrando {{ page_obj.start_index }} a {{ page_obj.end_index }} de {{ page_obj.paginator.count }} item(ns)
    </div>
</nav>
{% endif %}
```

---

## Boas Práticas

### 1. Nomenclatura

- Use nomes descritivos para IDs de dropdowns: `{fieldName}Dropdown`
- Use `data-field` para identificar campos nos botões: `data-field="field_name"`
- Use `data-sort` para identificar campos de ordenação: `data-sort="field_name"`

### 2. Acessibilidade

- Sempre inclua `aria-labelledby` nos dropdowns
- Use `aria-label` na paginação
- Mantenha labels associados aos campos

### 3. Responsividade

- Use classes Bootstrap para grid: `col-md-6 col-lg-2`
- Use `table-responsive` para tabelas
- Teste em diferentes tamanhos de tela

### 4. Performance

- Use `select_related()` e `prefetch_related()` nas queries
- Limite o número de itens por página (25-50)
- Use paginação para grandes volumes de dados

### 5. UX

- Mostre contagem de selecionados nos dropdowns
- Use ícones FontAwesome consistentemente
- Mantenha feedback visual (hover, active states)
- Use cores consistentes (primary, secondary, success, danger)

### 6. Manutenibilidade

- Mantenha estilos CSS organizados
- Use funções JavaScript reutilizáveis
- Documente código complexo
- Siga o padrão estabelecido neste documento

---

## Checklist para Novos Templates

- [ ] Estrutura geral do template (extends, blocks)
- [ ] Card de filtros com header
- [ ] Dropdowns com checkboxes para seleção múltipla
- [ ] Botões "Selecionar todas" funcionando
- [ ] Contagem dinâmica nos dropdowns
- [ ] Campos de data (se necessário)
- [ ] Botões Filtrar e Limpar
- [ ] Tabela responsiva
- [ ] Cabeçalhos com ordenação múltipla
- [ ] Badges de prioridade nas colunas ordenadas
- [ ] Ícones de ordenação (up/down)
- [ ] Linhas da tabela com classe `table-row-compact`
- [ ] Botões de ação compactos
- [ ] Rodapé da tabela (se necessário)
- [ ] Mensagem quando não há itens
- [ ] Paginação preservando filtros
- [ ] Estilos CSS padrão incluídos
- [ ] JavaScript para filtros incluído
- [ ] JavaScript para ordenação incluído
- [ ] View processando filtros múltiplos
- [ ] View processando ordenação múltipla
- [ ] Formulário usando `ModelMultipleChoiceField`
- [ ] Testes de responsividade

---

## Exemplo Completo

Veja o template de referência em: `apps/finance/templates/finance/transaction_list.html`

---

**Última atualização:** {{ data_atual }}
**Versão:** 1.0
