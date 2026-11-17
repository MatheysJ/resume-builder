# resume-builder

Gera currículos em PDF a partir de **YAML**, com o visual definido em **CSS**. O HTML é montado com Jinja e convertido em PDF pelo [WeasyPrint](https://weasyprint.org/).

```bash
docker compose run --rm resume build examples/resume.yaml --theme sidebar --preview
# out/resume.pdf · 1 página · fonte 10.9 pt
```

## Por que assim

- **Conteúdo separado do layout.** Cada vaga é um YAML; o código não muda.
- **Temas em CSS.** `classic`, `minimal` e `sidebar` (duas colunas), ou qualquer `.css` seu com `--theme caminho/tema.css`.
- **Cabe no número de páginas pedido.** A fonte é ajustada por busca binária entre um mínimo e um máximo: cerca de 6 renderizações em vez de testar tamanho por tamanho.
- **Pronto para ATS.** Texto selecionável, links clicáveis, `lang` definido e a coluna principal antes da lateral na ordem de leitura.
- **Metadados controlados.** Título, autor, assunto e palavras-chave vêm do YAML. `Creator` e `Producer` identificam o projeto (`@MatheysJ/resume-builder`), no lugar de WeasyPrint e pypdf.
- **Legenda no fim do currículo.** Uma linha discreta diz que o PDF foi gerado com o `@MatheysJ/resume-builder`, com link para o repositório. O texto segue o `meta.lang` (português ou inglês). Use `credit: false` no YAML para removê-la.

## Como rodar

### Com Docker (recomendado)

O WeasyPrint depende do Pango e de fontes do sistema. A imagem traz tudo, inclusive a fonte **Carlito**, que tem as mesmas medidas da Calibri.

```bash
docker compose build
docker compose run --rm resume build examples/resume.yaml --preview
docker compose run --rm test
```

O projeto é montado em `/work`, então o PDF aparece em `out/` na sua máquina. O código de `src/` é lido direto da pasta: editar um tema não exige rebuild.

### Sem Docker

Requer Python 3.11+ e as [dependências de sistema do WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) (no Windows, o Pango via MSYS2).

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"     # Windows: .venv\Scripts\pip
resume-builder build examples/resume.yaml
pytest
```

Sem o Pango, os testes de PDF são pulados e o restante (modelo, HTML, ajuste de página) roda normalmente.

## Linha de comando

```
resume-builder build <arquivo.yaml> [opções]
resume-builder themes
```

| Opção | Padrão | O que faz |
| --- | --- | --- |
| `-o, --output` | `out/<nome>.pdf` | Arquivo de saída |
| `-t, --theme` | `classic` | Tema embutido ou caminho de um `.css` |
| `--pages` | `1` | Máximo de páginas |
| `--min-size` / `--max-size` | `8` / `12` | Limites da fonte, em pt |
| `--font-size` | | Tamanho fixo; desliga o ajuste |
| `--preview` | | Salva um PNG de cada página ao lado do PDF |

Códigos de saída: `1` para YAML ou tema inválido, `2` para opções inválidas (padrão do argparse) e `3` quando nem a fonte mínima cabe no limite de páginas.

## O YAML

Veja o exemplo completo em [`examples/resume.yaml`](examples/resume.yaml). Para os seus currículos, use a pasta `resumes/`, que fica fora do Git.

```yaml
meta:            # opcional; título e autor caem para o nome
  title: Currículo · Ana Souza

basics:
  name: Ana Souza
  headline: Engenheira de Software Back-end
  email: ana@example.com
  links:
    - { label: github.com/ana, url: https://github.com/ana }

summary: Texto com **negrito** e [links](https://exemplo.com).
credit: true     # legenda "gerado com @MatheysJ/resume-builder" no fim

sections:
  - title: Experiência
    kind: entries          # entries | skills | list | text
    items:
      - { title: Engenheira, org: Empresa, period: 2023 – atual, bullets: [...] }
  - title: Competências
    kind: skills
    column: side           # barra lateral no tema sidebar; fim da página nos outros
    items:
      - { label: Back-end, value: Java, Spring Boot }
```

Erros apontam o campo exato: `erro: sections[0].items[2].title: campo obrigatório`. Campos desconhecidos também são erro, então um erro de digitação (`bulets`) não some em silêncio.

## Temas

Todo tema é aplicado sobre [`_base.css`](src/resume_builder/themes/_base.css), que define a estrutura e as variáveis (`--color-accent`, `--font-body`, `--gap`…). Um tema novo costuma ser só um bloco `:root` com outras cores e fontes. Meça tudo em `em`/`rem`: o ajuste de página muda apenas `--font-size`.

## Estrutura

```
src/resume_builder/
├── model.py      # lê e valida o YAML (dataclasses imutáveis)
├── labels.py     # textos fixos por idioma (título padrão e legenda)
├── markup.py     # **negrito** e [links] com escape de HTML
├── render.py     # HTML via Jinja
├── theming.py    # carrega os temas
├── fit.py        # busca binária do tamanho da fonte (pura, sem WeasyPrint)
├── pdf.py        # WeasyPrint + metadados com pypdf
├── preview.py    # PNG das páginas com pypdfium2
├── cli.py
├── templates/resume.html.j2
└── themes/       # _base.css, classic.css, minimal.css, sidebar.css
```
