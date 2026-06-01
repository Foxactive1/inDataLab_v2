import os
import csv
import json
import chardet
from werkzeug.utils import secure_filename
from flask import current_app
from app.database.db import db
from app.models.dataset import Dataset
from app.models.notebook import Notebook  # Adicionada importação do Notebook

# Extensões permitidas
ALLOWED_EXTENSIONS = {'csv', 'txt', 'json', 'xlsx', 'db'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def detect_encoding(file_path):
    """Detecta encoding do arquivo usando chardet (útil para CSV/TXT/JSON)"""
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(50000)
            result = chardet.detect(raw_data)
            return result.get('encoding', 'utf-8')
    except Exception:
        return 'utf-8'

def _get_xlsx_metadata(filepath):
    """Lê metadados de arquivo XLSX usando pandas (se disponível)"""
    try:
        import pandas as pd
        df = pd.read_excel(filepath, nrows=0)  # lê apenas cabeçalho
        rows = len(pd.read_excel(filepath))    # número total de linhas
        cols = len(df.columns)
        column_names = list(df.columns)
        return rows, cols, column_names
    except ImportError:
        raise ValueError("Para arquivos XLSX, instale pandas e openpyxl: pip install pandas openpyxl")
    except Exception as e:
        raise ValueError(f"Erro ao ler XLSX: {str(e)}")

def save_dataset(file, notebook_id, user_id):
    """Salva arquivo, lê metadados, registra no banco e associa ao notebook se for .db"""
    if not allowed_file(file.filename):
        raise ValueError("Apenas arquivos .csv, .txt, .json, .xlsx, .db são permitidos")

    original_name = secure_filename(file.filename)
    base, ext = os.path.splitext(original_name)
    ext_lower = ext.lower()

    # Diretório de uploads
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(notebook_id))
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, original_name)
    file.save(filepath)
    file_size = os.path.getsize(filepath)

    # Inicializa metadados padrão
    rows, cols, column_names = 0, 0, []
    is_sql_db = False

    try:
        if ext_lower == '.db':
            # Arquivo SQLite – não ler conteúdo, apenas registrar
            rows, cols, column_names = 0, 0, []
            is_sql_db = True
        elif ext_lower == '.xlsx':
            rows, cols, column_names = _get_xlsx_metadata(filepath)
        elif ext_lower == '.csv':
            encoding = detect_encoding(filepath)
            with open(filepath, 'r', encoding=encoding) as f:
                sample = f.read(1024)
                f.seek(0)
                has_header = False
                try:
                    has_header = csv.Sniffer().has_header(sample)
                except:
                    has_header = False

                if has_header:
                    reader = csv.DictReader(f)
                    rows = sum(1 for _ in reader)
                    f.seek(0)
                    reader = csv.DictReader(f)
                    column_names = list(reader.fieldnames) if reader.fieldnames else []
                    cols = len(column_names)
                else:
                    reader = csv.reader(f)
                    data = list(reader)
                    rows = len(data)
                    cols = len(data[0]) if rows > 0 else 0
                    column_names = [f"col_{i+1}" for i in range(cols)]
        elif ext_lower == '.json':
            encoding = detect_encoding(filepath)
            with open(filepath, 'r', encoding=encoding) as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    rows = len(data)
                    if isinstance(data[0], dict):
                        column_names = list(data[0].keys())
                        cols = len(column_names)
                    else:
                        cols = 1
                        column_names = ['value']
                else:
                    rows = 1
                    cols = 1
                    column_names = ['data']
        else:  # .txt
            encoding = detect_encoding(filepath)
            with open(filepath, 'r', encoding=encoding) as f:
                lines = [line.strip() for line in f if line.strip()]
                rows = len(lines)
                if rows:
                    first_line = lines[0]
                    cols = len(first_line.split()) if first_line.split() else 1
                    column_names = [f"col_{i+1}" for i in range(cols)]
                else:
                    cols = 0
    except Exception as e:
        # Em caso de erro, remove o arquivo físico
        if os.path.exists(filepath):
            os.remove(filepath)
        raise ValueError(f"Erro ao processar arquivo: {str(e)}")

    # Criar registro do dataset
    dataset = Dataset(
        notebook_id=notebook_id,
        filename=original_name,
        file_type=ext_lower[1:],
        file_path=filepath,
        file_size=file_size,
        rows=rows,
        columns=cols,
        column_names=json.dumps(column_names) if column_names else None,
        description=f"Importado de {original_name}",
        is_public=False,
        is_sql_database=is_sql_db,   # ← ESSENCIAL para .db
        extra_metadata=json.dumps({"user_id": user_id})
    )
    db.session.add(dataset)

    # --- AUTOMAÇÃO: Se for arquivo .db, define imediatamente como conexão do notebook ---
    if is_sql_db:
        notebook = Notebook.query.get(notebook_id)
        if notebook:
            notebook.default_sql_connection = filepath

    db.session.commit()
    return dataset

def load_dataset_data(dataset_id, user_id, notebook_id):
    """
    Carrega os dados do dataset para exibição no frontend.
    """
    dataset = Dataset.query.filter_by(id=dataset_id, notebook_id=notebook_id).first()
    if not (dataset):
        raise ValueError("Dataset não encontrado")

    file_type = dataset.file_type.lower()
    filepath = dataset.file_path

    if file_type == 'db':
        raise ValueError("Arquivo de banco de dados SQLite – não é possível visualizar o conteúdo diretamente. Use consultas SQL.")

    if file_type == 'xlsx':
        try:
            import pandas as pd
            df = pd.read_excel(filepath, nrows=100)  # máximo 100 linhas
            return df.to_dict(orient='records')
        except ImportError:
            raise ValueError("Visualização de XLSX requer pandas instalado.")
        except Exception as e:
            raise ValueError(f"Erro ao ler XLSX: {str(e)}")

    encoding = detect_encoding(filepath)

    if file_type == 'csv':
        with open(filepath, 'r', encoding=encoding) as f:
            sample = f.read(1024)
            f.seek(0)
            has_header = False
            try:
                has_header = csv.Sniffer().has_header(sample)
            except:
                has_header = False
            if has_header:
                reader = csv.DictReader(f)
                return list(reader)
            else:
                reader = csv.reader(f)
                return [row for row in reader]
    elif file_type == 'json':
        with open(filepath, 'r', encoding=encoding) as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                return [data]
    elif file_type == 'txt':
        with open(filepath, 'r', encoding=encoding) as f:
            return [line.strip() for line in f if line.strip()]
    else:
        raise ValueError(f"Tipo de arquivo não suportado para visualização: {file_type}")
