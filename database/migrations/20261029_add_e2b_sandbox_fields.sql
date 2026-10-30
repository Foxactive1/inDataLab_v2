-- ============================================================
-- InDataLab v2 - Migração incremental para sessões E2B
-- Execute uma vez no Neon SQL Editor, no schema public.
-- Não remove nem altera dados existentes.
-- ============================================================

BEGIN;

ALTER TABLE public.notebooks
    ADD COLUMN IF NOT EXISTS e2b_sandbox_id VARCHAR(120);

ALTER TABLE public.notebooks
    ADD COLUMN IF NOT EXISTS e2b_sandbox_expires_at TIMESTAMP WITHOUT TIME ZONE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_notebooks_e2b_sandbox_id
    ON public.notebooks (e2b_sandbox_id)
    WHERE e2b_sandbox_id IS NOT NULL;

COMMIT;

-- Verificação
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'notebooks'
  AND column_name IN ('e2b_sandbox_id', 'e2b_sandbox_expires_at')
ORDER BY column_name;
