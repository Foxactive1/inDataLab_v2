"""
AI Runtime – Executor de células do tipo 'ai' com contexto completo do notebook.
Integra com kernel_manager para obter variáveis, datasets e histórico.
"""

import time
import re
import json
from typing import Dict, Any, List, Optional

from app.executor.runtimes.base import BaseRuntime
from app.services.ai_service import AIService
from app.executor.kernel_manager import get_session, list_session_variables
from app.models.cell import Cell
from app.models.notebook import Notebook
from app.models.dataset import Dataset
from app.database.db import db


class AIRuntime(BaseRuntime):
    """
    Executa células de IA (Groq) com contexto completo:
    - Datasets do notebook
    - Variáveis do kernel (tipos + schemas de DataFrames)
    - Histórico das últimas células
    - Sessão de conversa persistente por notebook
    """

    # Limite de células a incluir no contexto
    MAX_CELLS_IN_CONTEXT = 10
    # Limite de caracteres por saída de célula
    MAX_OUTPUT_LENGTH = 500
    # Número de linhas de exemplo para DataFrame
    DATAFRAME_PREVIEW_ROWS = 2

    def execute(self, cell: Cell) -> Dict[str, Any]:
        start_time = time.perf_counter()

        # 1. Obter user_id via notebook
        user_id = self._get_user_id(cell)
        if not user_id:
            return self._error_response("Usuário não identificado", start_time)

        # 2. Validar conteúdo
        prompt = cell.content.strip()
        if not prompt:
            return self._error_response("Prompt vazio", start_time)

        try:
            # 3. Construir contexto rico
            context = self._build_context(cell.notebook_id, user_id)

            # 4. Montar system prompt
            system_prompt = self._build_system_prompt(context)

            # 5. Chamar AIService com sessão unificada por notebook
            with AIService() as ai:
                result = ai.chat_completion(
                    user_id=user_id,
                    content=prompt,
                    notebook_id=cell.notebook_id,
                    cell_id=cell.id,
                    conversation_session_id=f"notebook_{cell.notebook_id}",
                    system_prompt=system_prompt,
                    temperature=getattr(cell, 'ai_temperature', 0.7),
                    model=getattr(cell, 'ai_model', None)
                )

            # 6. Processar resposta
            if not result.get("success"):
                return self._error_response(
                    result.get("error", "Erro na IA"),
                    start_time,
                    error_type=result.get("error_type")
                )

            # 7. Extrair código Python da resposta (se houver)
            assistant_content = result["content"]
            suggested_code = self._extract_python_code(assistant_content)

            response = {
                "success": True,
                "output": assistant_content,
                "output_type": "text",
                "execution_time": result.get("processing_time_ms", 0) / 1000,
                "tokens": result.get("tokens"),
                "message_id": result.get("message_id")
            }

            if suggested_code:
                response["suggested_code"] = suggested_code

            return response

        except Exception as e:
            return self._error_response(f"Erro ao chamar AIService: {str(e)}", start_time)

    # ======================================================================
    # Métodos auxiliares
    # ======================================================================

    def _get_user_id(self, cell: Cell) -> Optional[int]:
        """Obtém o user_id a partir da célula ou notebook associado."""
        if cell.notebook and cell.notebook.user_id:
            return cell.notebook.user_id
        # Fallback: buscar notebook diretamente
        notebook = Notebook.query.get(cell.notebook_id)
        return notebook.user_id if notebook else None

    def _build_context(self, notebook_id: int, user_id: int) -> Dict[str, Any]:
        """
        Constrói dicionário com todo o contexto relevante:
        - datasets
        - variáveis do kernel (com schemas de DataFrames)
        - histórico de células (últimas N)
        """
        context = {
            "datasets": self._get_datasets_info(notebook_id),
            "kernel_variables": self._get_kernel_variables(notebook_id),
            "recent_cells": self._get_recent_cells(notebook_id, user_id),
        }
        return context

    def _get_datasets_info(self, notebook_id: int) -> List[Dict]:
        """Retorna lista de datasets anexados ao notebook."""
        datasets = Dataset.query.filter_by(notebook_id=notebook_id).all()
        result = []
        for ds in datasets:
            info = {
                "filename": ds.filename,
                "rows": ds.rows,
                "columns": ds.columns,
                "file_type": ds.file_type,
            }
            if ds.column_names:
                try:
                    cols = json.loads(ds.column_names)
                    info["column_names"] = cols[:20]  # limita a 20 colunas
                except:
                    pass
            result.append(info)
        return result

    def _get_kernel_variables(self, notebook_id: int) -> List[Dict]:
        """
        Obtém variáveis do kernel via kernel_manager.
        Para DataFrames, inclui colunas e amostra (2 primeiras linhas).
        """
        try:
            var_summary = list_session_variables(notebook_id)  # nome -> tipo
            namespace = get_session(notebook_id)
            variables = []
            for name, type_name in var_summary.items():
                var_info = {"name": name, "type": type_name}
                # Se for DataFrame, extrai schema
                if type_name == "DataFrame" and name in namespace:
                    df = namespace[name]
                    try:
                        # Colunas
                        var_info["columns"] = list(df.columns)[:20]
                        # Amostra (primeiras 2 linhas como dicionário)
                        preview = df.head(self.DATAFRAME_PREVIEW_ROWS).to_dict(orient="records")
                        var_info["preview"] = preview
                        var_info["shape"] = df.shape
                    except Exception:
                        pass
                variables.append(var_info)
            return variables
        except Exception as e:
            return [{"error": f"Erro ao acessar kernel: {str(e)}"}]

    def _get_recent_cells(self, notebook_id: int, user_id: int) -> List[Dict]:
        """
        Busca as últimas MAX_CELLS_IN_CONTEXT células do notebook.
        Inclui tipo, conteúdo e saída (para células de código).
        """
        cells = Cell.query.filter_by(notebook_id=notebook_id) \
            .order_by(Cell.position.desc()) \
            .limit(self.MAX_CELLS_IN_CONTEXT) \
            .all()
        cells.reverse()  # ordem cronológica (mais antigas primeiro)
        result = []
        for c in cells:
            cell_info = {
                "type": c.cell_type,
                "content": c.content[:1000],  # limite de segurança
            }
            if c.cell_type == "code" and c.output:
                output = c.output[:self.MAX_OUTPUT_LENGTH]
                if len(c.output) > self.MAX_OUTPUT_LENGTH:
                    output += "..."
                cell_info["output"] = output
            result.append(cell_info)
        return result

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """Constrói o prompt do sistema com todo o contexto."""
        lines = [
            "Você é o Copilot do InDataLab, um assistente de análise de dados e programação.",
            "",
            "## Contexto do Notebook",
            ""
        ]

        # Datasets
        if context["datasets"]:
            lines.append("### Datasets anexados:")
            for ds in context["datasets"]:
                line = f"- {ds['filename']} ({ds['rows']} linhas, {ds['columns']} colunas)"
                if ds.get("column_names"):
                    cols = ", ".join(ds["column_names"][:10])
                    line += f"\n  Colunas: {cols}"
                lines.append(line)
        else:
            lines.append("Nenhum dataset anexado.")

        lines.append("")

        # Variáveis do kernel
        kernel_vars = context["kernel_variables"]
        if kernel_vars:
            lines.append("### Variáveis ativas no kernel:")
            for var in kernel_vars:
                if "error" in var:
                    lines.append(f"- Erro: {var['error']}")
                    continue
                base = f"- `{var['name']}`: {var['type']}"
                if var["type"] == "DataFrame":
                    base += f" (shape: {var.get('shape', 'desconhecido')})"
                    lines.append(base)
                    if var.get("columns"):
                        cols = ", ".join(var["columns"][:15])
                        lines.append(f"  - Colunas: {cols}")
                    if var.get("preview"):
                        preview = var["preview"][:2]
                        lines.append(f"  - Amostra: {preview}")
                else:
                    lines.append(base)
        else:
            lines.append("### Nenhuma variável definida no kernel ainda.")

        lines.append("")

        # Células recentes
        if context["recent_cells"]:
            lines.append("### Últimas células executadas:")
            for i, cell in enumerate(context["recent_cells"], 1):
                lines.append(f"\n**Célula {i} ({cell['type']})**")
                lines.append(f"```{cell['type']}")
                lines.append(cell['content'][:300])
                lines.append("```")
                if cell.get("output"):
                    lines.append(f"**Saída:**\n```\n{cell['output']}\n```")
        else:
            lines.append("Nenhuma célula executada ainda.")

        # Regras
        lines.extend([
            "",
            "## Regras obrigatórias",
            "",
            "1. Responda sempre em português.",
            "2. Utilize o contexto acima sempre que possível.",
            "3. Para acessar datasets use o dicionário `_datasets['nome_do_arquivo']['path']`.",
            "4. Nunca invente caminhos de arquivos. Use apenas os caminhos fornecidos.",
            "5. Reutilize DataFrames e variáveis já existentes no kernel.",
            "6. Quando fornecer código Python, coloque-o dentro de um bloco ```python ... ```.",
            "7. Se não souber a resposta, diga que precisa de mais informações.",
            "8. Seja objetivo e direto. Evite explicações excessivas quando o código for suficiente.",
            "",
            "Agora responda à mensagem do usuário com base neste contexto."
        ])

        return "\n".join(lines)

    def _extract_python_code(self, text: str) -> Optional[str]:
        """
        Extrai o primeiro bloco de código Python da resposta da IA.
        Procura por ```python ... ``` ou ``` ... ``` com conteúdo que parece Python.
        """
        # Padrão: ```python\n(.*?)```
        match = re.search(r"```python\s*\n(.*?)```", text, re.DOTALL)
        if not match:
            # Tentar blocos sem linguagem especificada
            match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
            if not match:
                return None
        code = match.group(1).strip()
        # Validação simples: se contém palavras-chave prováveis de Python
        if re.search(r"\b(def|import|from|print|if|for|while|return|pd\.|plt\.|df|_datasets)\b", code):
            return code
        # Se não parecer Python, não retorna
        return None

    def _error_response(self, error_msg: str, start_time: float, error_type: str = None) -> Dict:
        """Formata resposta de erro padronizada."""
        return {
            "success": False,
            "error": error_msg,
            "error_type": error_type,
            "execution_time": time.perf_counter() - start_time,
        }