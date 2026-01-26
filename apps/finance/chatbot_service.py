"""
Serviço de Chatbot com LangChain para consulta de orçamento e transações financeiras.
"""
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, List
from django.db.models import Q, Sum
from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_core.messages import SystemMessage

# Tentar importar Google Gemini
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    ChatGoogleGenerativeAI = None

# Tentar importar create_react_agent, se não estiver disponível, usar alternativa
try:
    from langchain.agents import create_react_agent
except ImportError:
    try:
        from langchain.agents.react.base import create_react_agent
    except ImportError:
        create_react_agent = None

from .models import Category, Subcategory, Budget, Transaction


def check_ollama_available(base_url: str = 'http://localhost:11434') -> bool:
    """Verifica se o Ollama está disponível na URL especificada."""
    try:
        import requests
        response = requests.get(f"{base_url}/api/tags", timeout=2)
        return response.status_code == 200
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, Exception):
        return False


def get_llm():
    """Retorna o LLM configurado baseado nas variáveis de ambiente."""
    llm_provider = os.getenv('LLM_PROVIDER', 'gemini').lower()
    
    if llm_provider == 'openai':
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY não configurada no .env")
        return ChatOpenAI(
            model=os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
            temperature=0,
            api_key=api_key
        )
    elif llm_provider == 'gemini':
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "langchain-google-genai não está instalado. "
                "Instale com: pip install langchain-google-genai"
            )
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY não configurada no .env\n\n"
                "Para obter uma chave gratuita:\n"
                "1. Acesse: https://makersuite.google.com/app/apikey\n"
                "2. Crie uma API key gratuita\n"
                "3. Adicione no .env: GOOGLE_API_KEY=sua-chave-aqui"
            )
        model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            google_api_key=api_key
        )
    else:  # ollama
        ollama_base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        ollama_model = os.getenv('OLLAMA_MODEL', 'llama3.1')
        
        # Verificar se Ollama está disponível
        if not check_ollama_available(ollama_base_url):
            raise ConnectionError(
                f"Ollama não está disponível em {ollama_base_url}.\n\n"
                "Para usar o chatbot, configure uma das opções no arquivo .env:\n\n"
                "Opção 1 - Google Gemini (GRATUITO, recomendado):\n"
                "LLM_PROVIDER=gemini\n"
                "GOOGLE_API_KEY=sua-chave-api\n"
                "(Obter chave em: https://makersuite.google.com/app/apikey)\n\n"
                "Opção 2 - OpenAI:\n"
                "LLM_PROVIDER=openai\n"
                "OPENAI_API_KEY=sua-chave-api\n\n"
                "Opção 3 - Ollama (local):\n"
                "LLM_PROVIDER=ollama\n"
                "(Requer instalação do Ollama)"
            )
        
        return ChatOllama(
            base_url=ollama_base_url,
            model=ollama_model,
            temperature=0
        )


@tool
def get_budget_by_subcategory(subcategory_name: str, year: int, month: Optional[int] = None) -> str:
    """
    Consulta o orçamento de uma subcategoria.
    
    Args:
        subcategory_name: Nome da subcategoria (ex: "Alimentação", "Transporte")
        year: Ano (ex: 2025)
        month: Mês (1-12). Se None, retorna o total do ano.
    
    Returns:
        String formatada com o orçamento encontrado.
    """
    try:
        # Buscar subcategoria (pode ter múltiplas com mesmo nome)
        subcategories = Subcategory.objects.filter(subcategory__icontains=subcategory_name)
        
        if not subcategories.exists():
            return f"Nenhuma subcategoria encontrada com o nome '{subcategory_name}'."
        
        if subcategories.count() > 1:
            # Múltiplas subcategorias encontradas
            names = [str(sub) for sub in subcategories]
            return f"Múltiplas subcategorias encontradas: {', '.join(names)}. Por favor, seja mais específico."
        
        subcategory = subcategories.first()
        
        if month:
            budget_date = date(year, month, 1)
            budgets = Budget.objects.filter(
                subcategory=subcategory,
                budget_date=budget_date
            )
            total = sum(b.amount for b in budgets)
            return f"Orçamento de '{subcategory}' para {month:02d}/{year}: R$ {total:.2f}"
        else:
            budgets = Budget.objects.filter(
                subcategory=subcategory,
                budget_date__year=year
            )
            total = sum(b.amount for b in budgets)
            return f"Orçamento total de '{subcategory}' para {year}: R$ {total:.2f}"
    
    except Exception as e:
        return f"Erro ao consultar orçamento: {str(e)}"


@tool
def get_budget_by_category(category_name: str, year: int, month: Optional[int] = None) -> str:
    """
    Consulta o orçamento de uma categoria (soma de todas as subcategorias).
    
    Args:
        category_name: Nome da categoria (ex: "Despesas", "Receitas")
        year: Ano (ex: 2025)
        month: Mês (1-12). Se None, retorna o total do ano.
    
    Returns:
        String formatada com o orçamento encontrado.
    """
    try:
        categories = Category.objects.filter(category__icontains=category_name)
        
        if not categories.exists():
            return f"Nenhuma categoria encontrada com o nome '{category_name}'."
        
        if categories.count() > 1:
            names = [c.category for c in categories]
            return f"Múltiplas categorias encontradas: {', '.join(names)}. Por favor, seja mais específico."
        
        category = categories.first()
        
        if month:
            budget_date = date(year, month, 1)
            budgets = Budget.objects.filter(
                subcategory__category=category,
                budget_date=budget_date
            )
            total = sum(b.amount for b in budgets)
            return f"Orçamento de '{category.category}' para {month:02d}/{year}: R$ {total:.2f}"
        else:
            budgets = Budget.objects.filter(
                subcategory__category=category,
                budget_date__year=year
            )
            total = sum(b.amount for b in budgets)
            return f"Orçamento total de '{category.category}' para {year}: R$ {total:.2f}"
    
    except Exception as e:
        return f"Erro ao consultar orçamento: {str(e)}"


@tool
def get_transactions_by_subcategory(subcategory_name: str, start_date: str, end_date: str) -> str:
    """
    Consulta transações de uma subcategoria em um período.
    
    Args:
        subcategory_name: Nome da subcategoria
        start_date: Data inicial no formato YYYY-MM-DD
        end_date: Data final no formato YYYY-MM-DD
    
    Returns:
        String formatada com o total e lista de transações.
    """
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        subcategories = Subcategory.objects.filter(subcategory__icontains=subcategory_name)
        
        if not subcategories.exists():
            return f"Nenhuma subcategoria encontrada com o nome '{subcategory_name}'."
        
        if subcategories.count() > 1:
            names = [str(sub) for sub in subcategories]
            return f"Múltiplas subcategorias encontradas: {', '.join(names)}. Por favor, seja mais específico."
        
        subcategory = subcategories.first()
        
        date_filter = Q(
            Q(transaction_date__gte=start, transaction_date__lte=end) |
            Q(transaction_date__isnull=True, due_date__gte=start, due_date__lte=end)
        )
        
        transactions = Transaction.objects.filter(
            subcategory=subcategory
        ).filter(date_filter).order_by('-transaction_date', '-due_date')
        
        total = Decimal('0')
        transaction_list = []
        
        for trans in transactions:
            if trans.transaction_type == 'CR':
                total += trans.value
            elif trans.transaction_type == 'DB':
                total -= trans.value
            
            trans_date = trans.transaction_date or trans.due_date or 'Sem data'
            if isinstance(trans_date, date):
                trans_date = trans_date.strftime('%d/%m/%Y')
            
            transaction_list.append(
                f"  - {trans_date}: {trans.get_transaction_type_display()} R$ {trans.value:.2f}"
            )
        
        result = f"Transações de '{subcategory}' entre {start_date} e {end_date}:\n"
        result += f"Total: R$ {total:.2f}\n"
        result += f"Quantidade: {len(transactions)}\n"
        
        if transaction_list:
            result += "\nDetalhes:\n" + "\n".join(transaction_list[:10])  # Limitar a 10 transações
            if len(transactions) > 10:
                result += f"\n... e mais {len(transactions) - 10} transações."
        else:
            result += "\nNenhuma transação encontrada neste período."
        
        return result
    
    except ValueError as e:
        return f"Erro no formato de data. Use YYYY-MM-DD. Erro: {str(e)}"
    except Exception as e:
        return f"Erro ao consultar transações: {str(e)}"


@tool
def get_transactions_by_category(category_name: str, start_date: str, end_date: str) -> str:
    """
    Consulta transações de uma categoria em um período.
    
    Args:
        category_name: Nome da categoria
        start_date: Data inicial no formato YYYY-MM-DD
        end_date: Data final no formato YYYY-MM-DD
    
    Returns:
        String formatada com o total de transações.
    """
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        categories = Category.objects.filter(category__icontains=category_name)
        
        if not categories.exists():
            return f"Nenhuma categoria encontrada com o nome '{category_name}'."
        
        if categories.count() > 1:
            names = [c.category for c in categories]
            return f"Múltiplas categorias encontradas: {', '.join(names)}. Por favor, seja mais específico."
        
        category = categories.first()
        
        date_filter = Q(
            Q(transaction_date__gte=start, transaction_date__lte=end) |
            Q(transaction_date__isnull=True, due_date__gte=start, due_date__lte=end)
        )
        
        transactions = Transaction.objects.filter(
            subcategory__category=category
        ).filter(date_filter)
        
        total = Decimal('0')
        for trans in transactions:
            if trans.transaction_type == 'CR':
                total += trans.value
            elif trans.transaction_type == 'DB':
                total -= trans.value
        
        count = transactions.count()
        return f"Transações de '{category.category}' entre {start_date} e {end_date}:\nTotal: R$ {total:.2f}\nQuantidade: {count}"
    
    except ValueError as e:
        return f"Erro no formato de data. Use YYYY-MM-DD. Erro: {str(e)}"
    except Exception as e:
        return f"Erro ao consultar transações: {str(e)}"


@tool
def compare_budget_vs_spending(subcategory_name: str, year: int, month: Optional[int] = None) -> str:
    """
    Compara orçamento vs. gastos reais de uma subcategoria.
    
    Args:
        subcategory_name: Nome da subcategoria
        year: Ano (ex: 2025)
        month: Mês (1-12). Se None, compara o ano inteiro.
    
    Returns:
        String formatada com a comparação orçamento vs. gastos.
    """
    try:
        subcategories = Subcategory.objects.filter(subcategory__icontains=subcategory_name)
        
        if not subcategories.exists():
            return f"Nenhuma subcategoria encontrada com o nome '{subcategory_name}'."
        
        if subcategories.count() > 1:
            names = [str(sub) for sub in subcategories]
            return f"Múltiplas subcategorias encontradas: {', '.join(names)}. Por favor, seja mais específico."
        
        subcategory = subcategories.first()
        
        # Calcular orçamento
        if month:
            budget_date = date(year, month, 1)
            budgets = Budget.objects.filter(
                subcategory=subcategory,
                budget_date=budget_date
            )
            budget_total = sum(b.amount for b in budgets)
            
            # Calcular gastos do mês
            start = date(year, month, 1)
            if month == 12:
                end = date(year, 12, 31)
            else:
                end = date(year, month + 1, 1) - timedelta(days=1)
        else:
            budgets = Budget.objects.filter(
                subcategory=subcategory,
                budget_date__year=year
            )
            budget_total = sum(b.amount for b in budgets)
            
            # Calcular gastos do ano
            start = date(year, 1, 1)
            end = date(year, 12, 31)
        
        # Calcular gastos reais
        date_filter = Q(
            Q(transaction_date__gte=start, transaction_date__lte=end) |
            Q(transaction_date__isnull=True, due_date__gte=start, due_date__lte=end)
        )
        
        transactions = Transaction.objects.filter(
            subcategory=subcategory
        ).filter(date_filter)
        
        spent_total = Decimal('0')
        for trans in transactions:
            if trans.transaction_type == 'CR':
                spent_total += trans.value
            elif trans.transaction_type == 'DB':
                spent_total -= trans.value
        
        # Calcular diferença
        difference = budget_total - abs(spent_total)
        if budget_total > 0:
            percentage = (abs(spent_total) / budget_total) * 100
        else:
            percentage = 0
        
        period = f"{month:02d}/{year}" if month else str(year)
        result = f"Comparação para '{subcategory}' em {period}:\n"
        result += f"Orçamento: R$ {budget_total:.2f}\n"
        result += f"Gastos: R$ {abs(spent_total):.2f}\n"
        result += f"Diferença: R$ {difference:.2f}\n"
        result += f"Percentual utilizado: {percentage:.1f}%"
        
        if difference < 0:
            result += f"\n⚠️ Orçamento ultrapassado em R$ {abs(difference):.2f}"
        elif percentage > 90:
            result += f"\n⚠️ Atenção: próximo do limite do orçamento"
        
        return result
    
    except Exception as e:
        return f"Erro ao comparar orçamento vs. gastos: {str(e)}"


@tool
def list_categories() -> str:
    """
    Lista todas as categorias disponíveis no sistema.
    
    Returns:
        String formatada com a lista de categorias.
    """
    try:
        categories = Category.objects.all().order_by('category')
        
        if not categories.exists():
            return "Nenhuma categoria cadastrada no sistema."
        
        result = "Categorias disponíveis:\n"
        for cat in categories:
            subcategories_count = cat.subcategory_set.count()
            result += f"  - {cat.category} ({subcategories_count} subcategorias)\n"
        
        return result
    
    except Exception as e:
        return f"Erro ao listar categorias: {str(e)}"


@tool
def list_subcategories(category_name: Optional[str] = None) -> str:
    """
    Lista subcategorias. Se category_name for fornecido, lista apenas dessa categoria.
    
    Args:
        category_name: Nome da categoria (opcional)
    
    Returns:
        String formatada com a lista de subcategorias.
    """
    try:
        if category_name:
            categories = Category.objects.filter(category__icontains=category_name)
            
            if not categories.exists():
                return f"Nenhuma categoria encontrada com o nome '{category_name}'."
            
            if categories.count() > 1:
                names = [c.category for c in categories]
                return f"Múltiplas categorias encontradas: {', '.join(names)}. Por favor, seja mais específico."
            
            category = categories.first()
            subcategories = Subcategory.objects.filter(category=category).order_by('subcategory')
            
            if not subcategories.exists():
                return f"Nenhuma subcategoria encontrada na categoria '{category.category}'."
            
            result = f"Subcategorias de '{category.category}':\n"
            for sub in subcategories:
                result += f"  - {sub.subcategory}\n"
            
            return result
        else:
            subcategories = Subcategory.objects.all().order_by('category__category', 'subcategory')
            
            if not subcategories.exists():
                return "Nenhuma subcategoria cadastrada no sistema."
            
            result = "Todas as subcategorias:\n"
            current_category = None
            for sub in subcategories:
                if current_category != sub.category.category:
                    current_category = sub.category.category
                    result += f"\n{current_category}:\n"
                result += f"  - {sub.subcategory}\n"
            
            return result
    
    except Exception as e:
        return f"Erro ao listar subcategorias: {str(e)}"


def create_chatbot_agent():
    """Cria e retorna um agente LangChain configurado para consultas financeiras."""
    
    # Definir tools
    tools = [
        get_budget_by_subcategory,
        get_budget_by_category,
        get_transactions_by_subcategory,
        get_transactions_by_category,
        compare_budget_vs_spending,
        list_categories,
        list_subcategories,
    ]
    
    # Obter LLM
    llm = get_llm()
    llm_provider = os.getenv('LLM_PROVIDER', 'gemini').lower()
    
    # Prompt do sistema
    system_prompt = """Você é um assistente especializado em consultas financeiras. 
Você ajuda usuários a consultar orçamentos e transações financeiras.

Contexto do sistema:
- O sistema possui Categorias e Subcategorias
- Cada Subcategoria pode ter orçamentos mensais (Budget)
- Transações (Transaction) são registradas com subcategorias
- Orçamentos são armazenados por mês/ano (sempre dia 1)
- Transações têm datas de vencimento (due_date) ou transação (transaction_date)

Instruções:
- Sempre responda em português brasileiro
- Use formato de data YYYY-MM-DD quando necessário
- Seja claro e objetivo nas respostas
- Quando houver ambiguidade (múltiplas categorias/subcategorias com mesmo nome), informe ao usuário
- Use os tools disponíveis para consultar dados reais do sistema
- Formate valores monetários como R$ X.XX

Quando o usuário perguntar sobre orçamento ou gastos:
1. Identifique se é categoria ou subcategoria
2. Identifique o período (mês, ano, ou range de datas)
3. Use os tools apropriados para consultar
4. Apresente os resultados de forma clara

Se não tiver certeza sobre qual categoria/subcategoria o usuário quer, liste as opções disponíveis."""
    
    # Criar agente baseado no provider
    if llm_provider in ['openai', 'gemini']:
        # Usar OpenAI tools agent (funciona para OpenAI e Gemini)
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        agent = create_openai_tools_agent(llm, tools, prompt)
    else:
        # Para Ollama, tentar usar create_openai_tools_agent se ChatOllama suportar
        # Caso contrário, usar uma abordagem mais simples
        try:
            # Tentar usar OpenAI tools agent mesmo com Ollama (se suportar)
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            agent = create_openai_tools_agent(llm, tools, prompt)
        except Exception:
            # Fallback: usar ReAct agent se disponível
            if create_react_agent:
                prompt = PromptTemplate.from_template("""{system_prompt}

Você tem acesso às seguintes ferramentas:

{tools}

Use o seguinte formato:

Question: a pergunta de entrada que você precisa responder
Thought: você deve pensar sobre o que fazer
Action: a ação a tomar, deve ser uma das [{tool_names}]
Action Input: a entrada para a ação
Observation: o resultado da ação
... (este Thought/Action/Action Input/Observation pode repetir N vezes)
Thought: Agora sei a resposta final
Final Answer: a resposta final à pergunta original

Question: {input}
Thought: {agent_scratchpad}""")
                prompt = prompt.partial(system_prompt=system_prompt)
                agent = create_react_agent(llm, tools, prompt)
            else:
                # Último fallback: criar executor simples
                from langchain.agents import initialize_agent, AgentType
                executor = initialize_agent(
                    tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True
                )
                return executor
    
    # Criar executor (se agent não for já um executor)
    if isinstance(agent, AgentExecutor):
        return agent
    
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)
    
    return executor


def get_chatbot_response(query: str, chat_history: Optional[List] = None) -> str:
    """
    Processa uma query do usuário e retorna a resposta do chatbot.
    
    Args:
        query: Pergunta do usuário
        chat_history: Histórico de mensagens (opcional)
    
    Returns:
        Resposta do chatbot
    """
    try:
        executor = create_chatbot_agent()
        
        # Preparar histórico (se necessário)
        # Converter histórico de dict para formato LangChain se necessário
        history = []
        if chat_history:
            from langchain_core.messages import HumanMessage, AIMessage
            for msg in chat_history[-10:]:  # Manter últimas 10 mensagens
                if isinstance(msg, dict):
                    if msg.get('role') == 'user':
                        history.append(HumanMessage(content=msg.get('content', '')))
                    elif msg.get('role') == 'assistant':
                        history.append(AIMessage(content=msg.get('content', '')))
        
        # Executar query
        llm_provider = os.getenv('LLM_PROVIDER', 'gemini').lower()
        
        if llm_provider in ['openai', 'gemini']:
            result = executor.invoke({
                "input": query,
                "chat_history": history
            })
        else:
            # Para Ollama, não usar chat_history no invoke (pode não ser suportado)
            result = executor.invoke({
                "input": query
            })
        
        return result.get("output", "Desculpe, não consegui processar sua pergunta.")
    
    except ConnectionError as e:
        # Erro de conexão (Ollama não disponível)
        return f"⚠️ {str(e)}"
    except ValueError as e:
        # Erro de configuração (API key faltando, etc)
        return f"⚠️ Erro de configuração: {str(e)}\n\nVerifique as configurações no arquivo .env"
    except Exception as e:
        import traceback
        error_msg = str(e)
        
        # Detectar se é erro de conexão com Ollama
        if 'ConnectionRefusedError' in str(type(e).__name__) or 'localhost:11434' in error_msg:
            return (
                "⚠️ Ollama não está disponível.\n\n"
                "Para usar o chatbot, configure uma das opções no arquivo .env:\n\n"
                "Opção 1 - Google Gemini (GRATUITO, recomendado):\n"
                "LLM_PROVIDER=gemini\n"
                "GOOGLE_API_KEY=sua-chave-api\n"
                "(Obter chave em: https://makersuite.google.com/app/apikey)\n\n"
                "Opção 2 - OpenAI:\n"
                "LLM_PROVIDER=openai\n"
                "OPENAI_API_KEY=sua-chave-api\n\n"
                "Opção 3 - Ollama (local):\n"
                "LLM_PROVIDER=ollama\n"
                "(Requer instalação do Ollama)"
            )
        
        # Log do erro completo em desenvolvimento
        if os.getenv('DEBUG', 'False') == 'True':
            error_msg += f"\n\nDetalhes: {traceback.format_exc()}"
        return f"Erro ao processar consulta: {error_msg}"
