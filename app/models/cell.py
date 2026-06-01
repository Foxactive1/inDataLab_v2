"""
Model: Cell – com tags JSON, índices compostos e soft delete consistente
"""

from datetime import datetime
import uuid
import hashlib

from sqlalchemy import Index

from app.database.db import db
from app.utils.json_utils import sanitize_json


CELL_TYPES = (
    'python',
    'sql',
    'markdown',
    'ai'
)

CELL_STATUS = (
    'idle',
    'running',
    'success',
    'error'
)

OUTPUT_TYPES = (
    'text',
    'html',
    'json',
    'table',
    'chart',
    'image',
    'markdown',
    'error',
    'html_path',
    'image_path'
)


class Cell(db.Model):

    __tablename__ = 'cells'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    uuid = db.Column(
        db.String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True
    )

    notebook_id = db.Column(
        db.Integer,
        db.ForeignKey('notebooks.id'),
        nullable=False,
        index=True
    )

    dataset_id = db.Column(
        db.Integer,
        db.ForeignKey('datasets.id'),
        nullable=True,
        index=True
    )

    cell_type = db.Column(
        db.Enum(
            *CELL_TYPES,
            name='cell_types'
        ),
        nullable=False,
        default='python',
        index=True
    )

    language = db.Column(
        db.String(50),
        default='python'
    )

    title = db.Column(
        db.String(255)
    )

    content = db.Column(
        db.Text,
        nullable=False,
        default=''
    )

    content_hash = db.Column(
        db.String(64),
        nullable=True,
        index=True
    )

    tags = db.Column(
        db.JSON,
        default=list
    )

    metadata_json = db.Column(
        db.JSON
    )

    ai_context = db.Column(
        db.Text
    )

    is_ai_generated = db.Column(
        db.Boolean,
        default=False
    )

    status = db.Column(
        db.Enum(
            *CELL_STATUS,
            name='cell_status'
        ),
        default='idle',
        nullable=False,
        index=True
    )

    execution_count = db.Column(
        db.Integer,
        default=0
    )

    execution_time = db.Column(
        db.Float
    )

    last_executed_at = db.Column(
        db.DateTime
    )

    sql_connection = db.Column(
        db.String(255),
        nullable=True
    )

    output_type = db.Column(
        db.Enum(
            *OUTPUT_TYPES,
            name='output_types'
        ),
        default='text'
    )

    output = db.Column(
        db.Text
    )

    output_json = db.Column(
        db.JSON
    )

    error_output = db.Column(
        db.Text
    )

    rows_returned = db.Column(
        db.Integer
    )

    query_plan = db.Column(
        db.Text
    )

    memory_usage = db.Column(
        db.Float
    )

    cpu_usage = db.Column(
        db.Float
    )

    position = db.Column(
        db.Integer,
        nullable=False,  # sem default — CellService sempre calcula max+1
        index=True
    )

    version = db.Column(
        db.Integer,
        default=1
    )

    is_hidden = db.Column(
        db.Boolean,
        default=False
    )

    is_collapsed = db.Column(
        db.Boolean,
        default=False
    )

    is_readonly = db.Column(
        db.Boolean,
        default=False
    )

    is_pinned = db.Column(
        db.Boolean,
        default=False
    )

    is_deleted = db.Column(
        db.Boolean,
        default=False,
        index=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    executions = db.relationship(
        'Execution',
        backref='cell',
        lazy=True,
        cascade='all, delete-orphan'
    )

    __table_args__ = (
        Index(
            'ix_cells_notebook_position',
            'notebook_id',
            'position'
        ),
    )

    def __init__(self, **kwargs):

        if 'tags' in kwargs:

            if kwargs['tags'] is None:
                kwargs['tags'] = []

            elif isinstance(
                kwargs['tags'],
                str
            ):
                kwargs['tags'] = [
                    t.strip()
                    for t in kwargs['tags'].split(',')
                    if t.strip()
                ]

        super().__init__(**kwargs)

        self._update_content_hash()

    def _update_content_hash(self):

        if self.content:
            self.content_hash = hashlib.sha256(
                self.content.encode('utf-8')
            ).hexdigest()
        else:
            self.content_hash = None

    def set_content(
        self,
        new_content
    ):
        self.content = new_content
        self._update_content_hash()

    def increment_execution(self):

        self.execution_count += 1
        self.last_executed_at = datetime.utcnow()

    def set_running(self):

        self.status = 'running'

    def set_success(
        self,
        output=None,
        output_json=None,
        execution_time=None,
        rows_returned=None
    ):

        self.status = 'success'
        self.output = output

        self.output_json = sanitize_json(
            output_json
        )

        self.error_output = None

        if execution_time is not None:
            self.execution_time = execution_time

        if rows_returned is not None:
            self.rows_returned = rows_returned

        self.increment_execution()

    def set_error(
        self,
        error_message
    ):

        self.status = 'error'
        self.error_output = error_message

        self.increment_execution()

    def reset_output(self):

        self.output = None
        self.output_json = None
        self.error_output = None

        self.rows_returned = None
        self.execution_time = None

        self.status = 'idle'

    def soft_delete(self):

        self.is_deleted = True

    @property
    def is_executed(self):

        return self.execution_count > 0

    def has_output(self):

        return (
            self.output is not None
            or self.output_json is not None
        )

    def to_dict(self):

        return {
            'id': self.id,
            'uuid': self.uuid,

            'notebook_id': self.notebook_id,
            'dataset_id': self.dataset_id,

            'cell_type': self.cell_type,
            'language': self.language,

            'title': self.title,
            'content': self.content,
            'content_hash': self.content_hash,

            'status': self.status,

            'execution_count': self.execution_count,
            'execution_time': self.execution_time,

            'output_type': self.output_type,
            'output': self.output,

            'output_json': sanitize_json(
                self.output_json
            ),

            'error_output': self.error_output,

            'rows_returned': self.rows_returned,

            'position': self.position,
            'version': self.version,

            'sql_connection': self.sql_connection,

            'tags': sanitize_json(
                self.tags
            ),

            'metadata_json': sanitize_json(
                self.metadata_json
            ),

            'is_hidden': self.is_hidden,
            'is_collapsed': self.is_collapsed,
            'is_readonly': self.is_readonly,
            'is_pinned': self.is_pinned,
            'is_deleted': self.is_deleted,

            'is_ai_generated': self.is_ai_generated,

            'created_at': (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),

            'updated_at': (
                self.updated_at.isoformat()
                if self.updated_at
                else None
            ),

            'last_executed_at': (
                self.last_executed_at.isoformat()
                if self.last_executed_at
                else None
            ),

            'memory_usage': self.memory_usage,
            'cpu_usage': self.cpu_usage,
            'query_plan': self.query_plan,
        }