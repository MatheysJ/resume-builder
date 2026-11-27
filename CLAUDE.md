# Notas para quem (pessoa ou agente) for trabalhar neste repositório

Dois pacotes em `src/`:

- `resume_builder`: YAML → HTML (Jinja) → PDF (WeasyPrint). Estável.
- `jobhunt`: busca vagas e prepara candidaturas a partir de um currículo mestre. Em construção; a especificação e o roteiro estão em [`docs/automacao-candidaturas.md`](docs/automacao-candidaturas.md). Comece pela seção "Estado e próximos passos".

## Comandos

```bash
uv venv .venv && uv pip install -e ".[dev,jobhunt]"   # ou: python -m venv .venv && .venv/bin/pip install -e ".[dev,jobhunt]"
.venv/bin/pytest -q
.venv/bin/ruff check .
docker compose run --rm test                           # mesma suíte, com Pango e fontes
```

## Convenções

- Código, identificadores, chaves de YAML e colunas do banco em inglês; mensagens ao usuário, documentação e commits em português.
- Entrada do usuário é validada de forma estrita: campo desconhecido é erro, e a mensagem aponta o caminho exato (`search.sites[1]: ...`).
- Dados imutáveis (dataclasses `frozen`, modelos pydantic `frozen`) e funções puras sempre que possível. Rede, modelo de linguagem e navegador ficam nas bordas, para que o resto seja testável sem eles.
- Testes não acessam rede nem chamam modelo. Adaptadores de sites são testados contra HTML ou JSON salvos em `tests/`.
- Banco: SQLite com migrações em `jobhunt/db.py` (`MIGRATIONS`). Nunca edite uma migração já publicada; acrescente outra no fim.
- Dependência nova só com motivo claro. As do `jobhunt` ficam no extra `jobhunt`, para o `resume_builder` continuar leve.
- Dados pessoais (`data/`, `resumes/`, `out/`) nunca vão para o Git.
