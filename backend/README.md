# Backend TrapSight

Execute os comandos desta página a partir de `backend/`. O ambiente Python
usa `uv sync`; o seed requer também o grupo existente `treino`
(`uv sync --group treino`).

## Dados de demonstração locais

O PostgreSQL local precisa estar ativo, com as migrações aplicadas
(`uv run alembic upgrade head`). Exporte as variáveis descritas em
`.env.example` por um mecanismo local seguro. O processo não carrega `.env`
automaticamente; não coloque senhas em comandos salvos ou versionados.

Copie o banco licenciado para fora do checkout, preservando `manifest.json`
e os caminhos relativos dos PNGs. `TRAPSIGHT_TRAINING_DATA_DIR` aceita a
pasta que contém `manifest.json` ou sua pasta pai quando o catálogo está em
`sprites/manifest.json`. Não versione o banco nem enfraqueça essa restrição.
Compare a contagem de entradas do manifesto com os arquivos e os hashes
SHA-256 da origem e da cópia. O `dataset/apoio/md5.txt` contém hashes dos
arquivos ZIP de origem, não dos sprites finais.

Com o ambiente já configurado para o banco de desenvolvimento local:

```powershell
$env:TRAPSIGHT_TRAINING_DATA_DIR = "E:\TrapSight-dados\sprites-final"
uv run python -m src.seed_demo
uv run python -m src.seed_demo
```

Confirme nas duas execuções 6 armadilhas, 8 refis e 32 análises. Os cenários
são ARM-001 (trocar), ARM-002 (projeção), ARM-003 (refil novo), ARM-004
(histórico), ARM-005 (sem análises) e ARM-006 (sem refil ativo).

Preserve o diretório persistente `UPLOADS_DIR` e seu manifesto
`.seed_demo_manifest.json`: a reexecução substitui apenas os registros de
propriedade do seed, sem duplicá-los. Não apague o manifesto para tentar
resolver conflitos com dados existentes.

O procedimento de hospedagem está em
[`deploy/vercel-supabase.md`](../deploy/vercel-supabase.md).
