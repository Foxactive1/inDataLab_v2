"""
Service: AI (Groq) - v2.0 REFORMULADO
======================================

Gerencia requisições para Groq API com:
- Logging estruturado (não print)
- Type hints completos
- Tratamento de erro diferenciado
- Retry automático com backoff exponencial
- Context window management
- Validação de entrada
- Métricas para observabilidade
- Configuração centralizada
- Context manager para cleanup

Autor: InNovaIdeia
Data: 2026-05-16
"""

import os
import logging
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

try:
    from groq import Groq, APIError, RateLimitError, APIConnectionError, AuthenticationError
except ImportError:
    Groq = None
    APIError = Exception  # Fallback
    RateLimitError = Exception
    APIConnectionError = Exception
    AuthenticationError = Exception

try:
    import tenacity
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False

try:
    from prometheus_client import Counter, Histogram
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from flask import current_app
from app.database.db import db
from app.models.ai_conversation import AIConversation

# ============================================================================
# CONFIGURAÇÃO E LOGGING
# ============================================================================

logger = logging.getLogger(__name__)

# Modelo mais recente conhecido (atualizar quando descontinuado)
GROQ_MODELS = {
    'llama-3.3-70b-versatile': {'status': 'active', 'deprecated': None},
    'llama-3.1-70b-versatile': {'status': 'deprecated', 'deprecated': '2025-05-01'},
    'llama-3.1-8b-instant': {'status': 'active', 'deprecated': None},
    'mixtral-8x7b-32768': {'status': 'deprecated', 'deprecated': '2025-05-01'},
}

# ============================================================================
# CONFIGURAÇÃO CENTRALIZADA
# ============================================================================

class AIServiceConfig:
    """
    Gerenciador de configuração com prioridade clara:
    1. Flask app.config (mais alta)
    2. Variáveis de ambiente
    3. Arquivo .env
    4. Valores padrão (mais baixa)
    """
    
    DEFAULTS = {
        'GROQ_API_KEY': None,  # Obrigatória
        'GROQ_MODEL': 'llama-3.3-70b-versatile',
        'GROQ_TEMPERATURE': 0.7,
        'GROQ_MAX_TOKENS': 2048,
        'GROQ_TIMEOUT': 30,
        'GROQ_RETRY_ATTEMPTS': 3,
        'GROQ_RETRY_BASE_WAIT': 2,
    }
    
    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        Obtém valor de configuração com prioridade clara.
        
        Args:
            key: Chave da configuração
            default: Valor padrão se não encontrado
        
        Returns:
            Valor da configuração
        """
        
        # 1. Flask config (prioridade máxima)
        try:
            if val := current_app.config.get(key):
                logger.debug(f"Config {key} carregada de Flask: {val[:20] if isinstance(val, str) else val}...")
                return val
        except RuntimeError:
            pass  # Fora de contexto Flask
        
        # 2. Variáveis de ambiente
        if val := os.environ.get(key):
            logger.debug(f"Config {key} carregada de env: {val[:20] if isinstance(val, str) else val}...")
            return val
        
        # 3. Valor padrão
        default_val = cls.DEFAULTS.get(key, default)
        if default_val is not None:
            logger.debug(f"Config {key} usando padrão: {default_val}")
        
        return default_val


# ============================================================================
# MÉTRICAS (PROMETHEUS)
# ============================================================================

def _init_metrics():
    """Inicializa métricas Prometheus se disponível."""
    if not PROMETHEUS_AVAILABLE:
        return {}
    
    return {
        'requests_total': Counter(
            'groq_requests_total',
            'Total requisições Groq',
            ['model', 'status']
        ),
        'request_duration_ms': Histogram(
            'groq_request_duration_ms',
            'Latência requisição Groq',
            ['model'],
            buckets=(100, 250, 500, 1000, 2000, 5000)
        ),
        'tokens_used': Counter(
            'groq_tokens_used_total',
            'Total tokens consumidos',
            ['model', 'token_type']
        ),
        'errors_total': Counter(
            'groq_errors_total',
            'Total erros Groq',
            ['error_type']
        ),
    }

METRICS = _init_metrics()


# ============================================================================
# SERVIÇO AI
# ============================================================================

class AIService:
    """
    Serviço para integração com Groq API.
    
    Features:
    - Logging estruturado (não print)
    - Retry automático com exponential backoff
    - Context window management
    - Type hints completos
    - Validação de entrada
    - Métricas de observabilidade
    - Context manager para cleanup
    
    Exemplo de uso:
    ```python
    with AIService() as ai:
        result = ai.chat_completion(
            user_id=1,
            content="Olá",
            system_prompt="Você é um assistente..."
        )
        print(result['content'])
    ```
    """
    
    def __init__(self):
        """
        Inicializa serviço Groq.
        
        Raises:
            ImportError: Se biblioteca groq não está instalada
            ValueError: Se GROQ_API_KEY não configurada
        """
        
        if not Groq:
            raise ImportError(
                "Biblioteca 'groq' não encontrada. Execute: pip install groq"
            )
        
        # Obtém API key com fallback
        api_key = AIServiceConfig.get('GROQ_API_KEY')
        if not api_key:
            # Tenta carregar de .env manualmente
            try:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.environ.get('GROQ_API_KEY')
            except ImportError:
                pass
        
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY não configurada. "
                "Defina variável de ambiente ou arquivo .env"
            )
        
        # Inicializa cliente
        self.client = Groq(api_key=api_key)
        self._lock = threading.Lock()  # Para thread-safety
        
        # Configurações
        self.model = AIServiceConfig.get('GROQ_MODEL')
        self.temperature = float(AIServiceConfig.get('GROQ_TEMPERATURE', 0.7))
        self.max_tokens = int(AIServiceConfig.get('GROQ_MAX_TOKENS', 2048))
        self.timeout = int(AIServiceConfig.get('GROQ_TIMEOUT', 30))
        self.retry_attempts = int(AIServiceConfig.get('GROQ_RETRY_ATTEMPTS', 3))
        self.retry_base_wait = int(AIServiceConfig.get('GROQ_RETRY_BASE_WAIT', 2))
        
        # Validações de configuração
        self._validate_config()
        
        logger.info(
            f"AIService inicializado: model={self.model}, "
            f"temperature={self.temperature}, max_tokens={self.max_tokens}"
        )
    
    def _validate_config(self) -> None:
        """Valida configuração durante inicialização."""
        
        if self.model not in GROQ_MODELS:
            logger.warning(f"Modelo '{self.model}' não está na lista conhecida")
        elif GROQ_MODELS[self.model]['status'] == 'deprecated':
            deprecated_date = GROQ_MODELS[self.model]['deprecated']
            logger.warning(
                f"Modelo '{self.model}' foi descontinuado em {deprecated_date}. "
                f"Considere migrar para '{self._get_active_model()}'"
            )
        
        if not (0 <= self.temperature <= 2):
            logger.warning(f"temperature={self.temperature} fora do range [0, 2]")
        
        if self.max_tokens < 256:
            logger.warning(f"max_tokens={self.max_tokens} muito baixo, mínimo recomendado: 256")
    
    def _get_active_model(self) -> str:
        """Retorna primeiro modelo ativo disponível."""
        for model, info in GROQ_MODELS.items():
            if info['status'] == 'active':
                return model
        return self.model
    
    def _validate_input(
        self,
        user_id: int,
        content: str,
        temperature: Optional[float] = None
    ) -> None:
        """
        Valida parâmetros de entrada.
        
        Raises:
            ValueError: Se validação falhar
        """
        
        if not user_id or user_id <= 0:
            raise ValueError(f"user_id inválido: {user_id}")
        
        if not content or not content.strip():
            raise ValueError("content não pode ser vazio")
        
        if temperature is not None:
            if not (0 <= temperature <= 2):
                raise ValueError(f"temperature deve estar em [0, 2], recebeu {temperature}")
    
    def _estimate_token_count(self, text: str) -> int:
        """
        Estima quantidade de tokens em um texto.
        
        Args:
            text: Texto para estimar
        
        Returns:
            Número estimado de tokens
        """
        
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except Exception:
            # Fallback: aproximadamente 1 token por 4 caracteres
            return max(1, len(text) // 4)
    
    def _prepare_messages(
        self,
        system_prompt: Optional[str],
        history: List[Dict[str, str]],
        user_content: str
    ) -> Tuple[List[Dict[str, str]], int]:
        """
        Prepara lista de mensagens respeitando context window.
        
        Args:
            system_prompt: Prompt do sistema
            history: Histórico de conversação
            user_content: Mensagem do usuário
        
        Returns:
            (messages, total_estimated_tokens)
        """
        
        messages: List[Dict[str, str]] = []
        
        # Orçamento de tokens (75% do max, reserva 25% para resposta)
        token_budget = int(self.max_tokens * 0.75)
        tokens_used = 0
        
        # System prompt (obrigatório se fornecido)
        if system_prompt and system_prompt.strip():
            system_tokens = self._estimate_token_count(system_prompt)
            messages.append({"role": "system", "content": system_prompt})
            tokens_used += system_tokens
        
        # User message (obrigatória)
        user_tokens = self._estimate_token_count(user_content)
        tokens_used += user_tokens
        
        if tokens_used > token_budget:
            logger.warning(
                f"User message sozinha excede budget: {tokens_used} > {token_budget}. "
                f"Truncando..."
            )
            # Trunca user message para ~50%
            truncated_content = user_content[:int(len(user_content) * 0.5)] + "...[truncado]"
            user_tokens = self._estimate_token_count(truncated_content)
            user_content = truncated_content
            tokens_used = user_tokens
            if system_prompt:
                tokens_used += self._estimate_token_count(system_prompt)
        
        # Adiciona histórico em ordem reversa (mais recente primeiro)
        # Mas após system prompt
        system_prompt_len = 1 if system_prompt else 0
        for msg in reversed(history):
            msg_tokens = self._estimate_token_count(msg['content'])
            
            if tokens_used + msg_tokens > token_budget:
                logger.debug(
                    f"Context window completo ({tokens_used}/{token_budget} tokens). "
                    f"Parando de adicionar histórico."
                )
                break
            
            # Insere após system prompt
            messages.insert(system_prompt_len, msg)
            tokens_used += msg_tokens
        
        # Adiciona user message no final
        messages.append({"role": "user", "content": user_content})
        
        return messages, tokens_used
    
    def _call_groq_with_retry(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float
    ) -> Any:
        """
        Chama Groq API com retry automático.
        
        Args:
            messages: Lista de mensagens
            model: Modelo a usar
            temperature: Temperatura
        
        Returns:
            Response object da Groq
        
        Raises:
            Exception: Se todos os retries falharem
        """
        
        if not TENACITY_AVAILABLE:
            # Sem tenacity, faz chamada simples
            logger.warning("Tenacity não disponível, retry desabilidado")
            return self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
            )
        
        # Com tenacity, configura retry
        @tenacity.retry(
            retry=tenacity.retry_if_exception_type(
                (RateLimitError, APIConnectionError)
            ),
            wait=tenacity.wait_exponential(
                multiplier=self.retry_base_wait,
                min=self.retry_base_wait,
                max=10
            ),
            stop=tenacity.stop_after_attempt(self.retry_attempts),
            before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def _call():
            return self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
            )
        
        return _call()
    
    def _save_conversation(
        self,
        user_id: int,
        user_content: str,
        assistant_content: str,
        notebook_id: Optional[int],
        cell_id: Optional[int],
        conversation_session_id: Optional[str],
        model: str,
        temperature: float,
        tokens: Dict[str, int],
        processing_time: float,
        groq_request_id: Optional[str] = None
    ) -> Optional[int]:
        """
        Salva mensagens de conversa no banco de dados.
        
        Args:
            user_id: ID do usuário
            user_content: Mensagem do usuário
            assistant_content: Resposta da IA
            notebook_id: ID do notebook (opcional)
            cell_id: ID da célula (opcional)
            conversation_session_id: ID da sessão
            model: Modelo utilizado
            temperature: Temperatura utilizada
            tokens: Dict com total, prompt, completion
            processing_time: Tempo de processamento em ms
            groq_request_id: ID da requisição Groq
        
        Returns:
            ID da mensagem salva, ou None se falhar
        """
        
        try:
            with self._lock:
                # Salva mensagem do usuário
                user_msg = AIConversation(
                    user_id=user_id,
                    notebook_id=notebook_id,
                    cell_id=cell_id,
                    conversation_session_id=conversation_session_id,
                    role='user',
                    content=user_content,
                    model=model,
                    temperature=temperature,
                )
                db.session.add(user_msg)
                
                # Salva resposta da IA
                assistant_msg = AIConversation(
                    user_id=user_id,
                    notebook_id=notebook_id,
                    cell_id=cell_id,
                    conversation_session_id=conversation_session_id,
                    role='assistant',
                    content=assistant_content,
                    model=model,
                    temperature=temperature,
                    tokens_used=tokens['total'],
                    input_tokens=tokens['prompt'],
                    output_tokens=tokens['completion'],
                    processing_time=processing_time,
                    groq_request_id=groq_request_id,
                )
                db.session.add(assistant_msg)
                db.session.commit()
                
                logger.debug(
                    f"Conversa salva: user_id={user_id}, "
                    f"session_id={conversation_session_id}, msg_id={assistant_msg.id}"
                )
                
                return assistant_msg.id
        
        except Exception as e:
            db.session.rollback()
            logger.error(
                f"Erro ao salvar conversa no banco de dados: {str(e)}",
                exc_info=True
            )
            return None
    
    def chat_completion(
        self,
        user_id: int,
        content: str,
        notebook_id: Optional[int] = None,
        cell_id: Optional[int] = None,
        conversation_session_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Realiza chat completion com Groq.
        
        **Validações**:
        - user_id > 0
        - content não vazio
        - temperature em [0, 2]
        
        **Tratamento de erro diferenciado**:
        - RateLimitError: Retorna com retry_after
        - AuthenticationError: Erro crítico, sem retry
        - APIConnectionError: Transiente, com retry automático
        - Outras: Erro genérico
        
        Args:
            user_id: ID do usuário
            content: Mensagem do usuário
            notebook_id: ID do notebook (contexto)
            cell_id: ID da célula (contexto)
            conversation_session_id: ID da sessão
            system_prompt: Prompt do sistema
            temperature: Temperatura (0-2)
            model: Modelo a usar
        
        Returns:
            Dict com:
            - success: bool
            - content: str (se sucesso)
            - message_id: int (se sucesso)
            - tokens: dict (se sucesso)
            - processing_time_ms: float (se sucesso)
            - error: str (se erro)
            - error_type: str (se erro)
            - retry_after: int (se RateLimitError)
        """
        
        start_time = time.time()
        
        try:
            # ========== VALIDAÇÕES ==========
            self._validate_input(user_id, content, temperature)
            
            # Usa temperatura fornecida ou padrão
            temp = temperature or self.temperature
            
            # Usa modelo fornecido ou padrão
            m = model or self.model
            
            # Valida modelo
            if m not in GROQ_MODELS:
                logger.warning(f"Modelo '{m}' não reconhecido, usando padrão")
                m = self._get_active_model()
            elif GROQ_MODELS[m]['status'] == 'deprecated':
                logger.warning(f"Modelo '{m}' descontinuado, usando '{self._get_active_model()}'")
                m = self._get_active_model()
            
            # ========== HISTÓRICO ==========
            history = self._get_conversation_history(conversation_session_id, limit=10)
            
            # ========== PREPARAÇÃO DE MENSAGENS ==========
            messages, tokens_estimated = self._prepare_messages(
                system_prompt,
                history,
                content
            )
            
            logger.debug(
                f"Mensagens preparadas: {len(messages)} mensagens, "
                f"~{tokens_estimated} tokens estimados"
            )
            
            # ========== CHAMADA GROQ ==========
            response = self._call_groq_with_retry(messages, m, temp)
            
            assistant_content = response.choices[0].message.content
            processing_time = (time.time() - start_time) * 1000  # ms
            
            tokens = {
                'total': response.usage.total_tokens,
                'prompt': response.usage.prompt_tokens,
                'completion': response.usage.completion_tokens,
            }
            
            groq_request_id = getattr(response, 'id', None)
            
            # ========== SALVAR CONVERSA ==========
            message_id = self._save_conversation(
                user_id=user_id,
                user_content=content,
                assistant_content=assistant_content,
                notebook_id=notebook_id,
                cell_id=cell_id,
                conversation_session_id=conversation_session_id,
                model=m,
                temperature=temp,
                tokens=tokens,
                processing_time=processing_time,
                groq_request_id=groq_request_id
            )
            
            # ========== MÉTRICAS ==========
            if PROMETHEUS_AVAILABLE:
                METRICS['requests_total'].labels(model=m, status='success').inc()
                METRICS['request_duration_ms'].labels(model=m).observe(processing_time)
                METRICS['tokens_used'].labels(model=m, token_type='prompt').inc(tokens['prompt'])
                METRICS['tokens_used'].labels(model=m, token_type='completion').inc(tokens['completion'])
            
            logger.info(
                f"Chat concluído: user_id={user_id}, model={m}, "
                f"tokens={tokens['total']}, time={processing_time:.0f}ms"
            )
            
            return {
                'success': True,
                'content': assistant_content,
                'message_id': message_id,
                'tokens': tokens,
                'processing_time_ms': processing_time,
                'model': m,
            }
        
        # ========== TRATAMENTO DE ERRO DIFERENCIADO ==========
        
        except ValueError as e:
            logger.warning(f"Validação falhou: {str(e)}")
            if PROMETHEUS_AVAILABLE:
                METRICS['errors_total'].labels(error_type='VALIDATION_ERROR').inc()
            return {
                'success': False,
                'error': str(e),
                'error_type': 'VALIDATION_ERROR',
            }
        
        except RateLimitError as e:
            logger.warning(f"Rate limit Groq: {str(e)}")
            if PROMETHEUS_AVAILABLE:
                METRICS['errors_total'].labels(error_type='RATE_LIMIT').inc()
            retry_after = getattr(e, 'retry_after', 30)
            return {
                'success': False,
                'error': 'Limite de requisições atingido. Tente novamente em alguns segundos.',
                'error_type': 'RATE_LIMIT',
                'retry_after': retry_after,
            }
        
        except AuthenticationError as e:
            logger.critical(f"Erro de autenticação Groq: chave inválida ou expirada")
            if PROMETHEUS_AVAILABLE:
                METRICS['errors_total'].labels(error_type='AUTH_ERROR').inc()
            return {
                'success': False,
                'error': 'Erro de configuração (contate administrador)',
                'error_type': 'AUTH_ERROR',
            }
        
        except APIConnectionError as e:
            logger.error(f"Erro de conexão com Groq API: {str(e)}", exc_info=True)
            if PROMETHEUS_AVAILABLE:
                METRICS['errors_total'].labels(error_type='CONNECTION_ERROR').inc()
            return {
                'success': False,
                'error': 'Serviço temporariamente indisponível. Tente novamente.',
                'error_type': 'CONNECTION_ERROR',
            }
        
        except Exception as e:
            logger.exception(f"Erro inesperado em chat_completion")
            if PROMETHEUS_AVAILABLE:
                METRICS['errors_total'].labels(error_type='UNKNOWN_ERROR').inc()
            return {
                'success': False,
                'error': 'Erro ao processar requisição',
                'error_type': type(e).__name__,
            }
    
    def _get_conversation_history(
        self,
        session_id: Optional[str],
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """
        Busca histórico de conversa (uso interno).
        
        Args:
            session_id: ID da sessão
            limit: Limite de mensagens
        
        Returns:
            Lista de dicts com role e content
        """
        
        if not session_id:
            return []
        
        try:
            conversations = AIConversation.query.filter_by(
                conversation_session_id=session_id
            ).order_by(AIConversation.created_at.asc()).limit(limit).all()
            
            return [
                {"role": conv.role, "content": conv.content}
                for conv in conversations
            ]
        
        except Exception as e:
            logger.error(f"Erro ao buscar histórico: {str(e)}")
            return []
    
    def get_conversation_history(
        self,
        user_id: int,
        session_id: Optional[str] = None,
        notebook_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Busca histórico de conversas do usuário (API pública).
        
        Args:
            user_id: ID do usuário
            session_id: ID da sessão (filtro)
            notebook_id: ID do notebook (filtro)
            limit: Limite de registros
        
        Returns:
            Lista de conversas serializadas
        """
        
        try:
            query = AIConversation.query.filter_by(user_id=user_id)
            
            if session_id:
                query = query.filter_by(conversation_session_id=session_id)
            
            if notebook_id:
                query = query.filter_by(notebook_id=notebook_id)
            
            conversations = query.order_by(
                AIConversation.created_at.desc()
            ).limit(limit).all()
            
            return [conv.to_dict() for conv in conversations]
        
        except Exception as e:
            logger.error(f"Erro ao buscar histórico do usuário: {str(e)}")
            return []
    
    def close(self) -> None:
        """
        Limpa recursos e finaliza serviço.
        
        Deve ser chamado ao finalizar, ou usar context manager.
        """
        try:
            if hasattr(self.client, 'close'):
                self.client.close()
            logger.info("AIService finalizado")
        except Exception as e:
            logger.error(f"Erro ao finalizar AIService: {str(e)}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup garantido."""
        self.close()
        return False
    
    def __del__(self):
        """Fallback para cleanup se não usar context manager."""
        try:
            self.close()
        except Exception:
            pass
