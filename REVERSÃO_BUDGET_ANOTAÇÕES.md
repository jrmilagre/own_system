# Documento de Reversão - Sistema de Anotações Múltiplas para Orçamentos

## Estado Antes das Mudanças

### Modelo Budget
- `unique_together = [['subcategory', 'budget_date']]` - Restrição que impede múltiplos orçamentos para mesma subcategoria/mês
- Campo `notes` existe mas não é usado como diferenciador

### View budget_manage
- Agrupa orçamentos apenas por subcategoria
- Processa campos no formato: `budget_{subcategory_id}_{month}`
- Não considera notes no agrupamento

### Template budget_manage.html
- Uma linha por subcategoria
- Sem coluna de anotações
- Campos no formato: `budget_{subcategory_id}_{month}`

## Mudanças Implementadas

### 1. Migração 0033_remove_unique_together_budget.py
- Remove a constraint `unique_together` do modelo Budget
- Permite múltiplos Budgets para mesma subcategoria/mês

### 2. Modelo Budget (apps/finance/models.py)
- Removido: `unique_together = [['subcategory', 'budget_date']]`
- Mantido: Campo `notes` e demais campos

### 3. View budget_manage (apps/finance/views.py)
- GET: Agrupa orçamentos por `(subcategory, notes)` em vez de apenas `subcategory`
- POST: Processa campos no formato: `budget_{subcategory_id}_{row_hash}_{month}` e `notes_{subcategory_id}_{row_hash}`

### 4. Template budget_manage.html
- Adicionada coluna "Anotações"
- Múltiplas linhas por subcategoria (agrupadas por notes)
- Botão para adicionar novas linhas
- JavaScript para gerenciar linhas dinamicamente

## Como Reverter

### Passo 1: Reverter Migração
```bash
python manage.py migrate finance 0032
```

### Passo 2: Restaurar unique_together no modelo
No arquivo `apps/finance/models.py`, linha 266, adicionar de volta:
```python
unique_together = [['subcategory', 'budget_date']]
```

### Passo 3: Reverter View
Restaurar a lógica de agrupamento apenas por subcategoria (sem considerar notes)

### Passo 4: Reverter Template
Remover coluna de anotações e voltar para uma linha por subcategoria

### Passo 5: Limpar Dados (Opcional)
Se houver múltiplos Budgets para mesma subcategoria/mês, será necessário consolidar ou remover duplicatas antes de reverter a migração.

## Arquivos Modificados
- apps/finance/models.py
- apps/finance/views.py (função budget_manage)
- apps/finance/templates/finance/budget_manage.html
- apps/finance/migrations/0033_remove_unique_together_budget.py (nova migração)

## Data da Implementação
2026-01-XX

## Status
✅ Implementação concluída

## Mudanças Implementadas

### 1. Modelo Budget
- ✅ Removido `unique_together = [['subcategory', 'budget_date']]`
- ✅ Adicionado índice composto: `['subcategory', 'budget_date', 'notes']`
- ✅ Campo `notes` mantido (já existia)

### 2. Migração 0033
- ✅ Criada migração para remover constraint unique_together

### 3. View budget_manage (GET)
- ✅ Agrupa orçamentos por `(subcategory, notes)` em vez de apenas `subcategory`
- ✅ Usa hash MD5 das anotações como identificador único da linha
- ✅ Estrutura de dados: `budget_data` agora contém `rows` (lista de linhas) por subcategoria

### 4. View budget_manage (POST)
- ✅ Processa campos no formato: `budget_{subcategory_id}_{notes_hash}_{month}`
- ✅ Processa anotações: `notes_{subcategory_id}_{notes_hash}`
- ✅ Cria/atualiza Budgets incluindo notes
- ✅ Remove Budgets quando linhas são deletadas

### 5. Template budget_manage.html
- ✅ Adicionada coluna "Anotações" no cabeçalho
- ✅ Adicionada coluna "Ações" para botão remover
- ✅ Múltiplas linhas por subcategoria (loop `item.rows`)
- ✅ Campo de texto inline para editar anotações
- ✅ Botão "Adicionar Linha" para criar novas linhas
- ✅ Botão "Remover Linha" em cada linha
- ✅ JavaScript para gerenciar linhas dinamicamente
- ✅ Cálculos atualizados para múltiplas linhas

## Como Testar

1. Acessar `/finance/budgets/manage/`
2. Verificar se há múltiplas linhas para mesma subcategoria (se houver dados com notes diferentes)
3. Clicar em "Adicionar Linha" para criar nova linha
4. Preencher anotações e valores
5. Salvar e verificar se múltiplos Budgets foram criados

## Notas de Implementação
- Removida restrição unique_together do modelo Budget
- Sistema agora permite múltiplas linhas por subcategoria/ano
- Cada linha é identificada por subcategoria + hash das anotações
- Interface permite adicionar/remover linhas dinamicamente
- Cálculos atualizados para funcionar com múltiplas linhas
- Compatibilidade: Orçamentos existentes sem notes continuam funcionando (agrupados como linha única)
