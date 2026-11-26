# Automação de candidaturas: especificação

Estado: base do projeto pronta (§10) · Fontes: LinkedIn, Indeed, Glassdoor e Gupy · Pacote: `jobhunt`, neste repositório

## 1. Veredito

O projeto é viável se for um **copiloto de candidaturas**. Como robô que se candidata sozinho e em massa, não é recomendável. As etapas têm níveis de risco bem diferentes:

| Etapa | Viabilidade | Complexidade | Risco principal |
| --- | --- | --- | --- |
| Buscar vagas | Alta | Média | Fontes não oficiais (JobSpy, API da Gupy) quebram quando os sites mudam; os termos dos sites proíbem scraping |
| Ler requisitos e benefícios | Alta | Baixa | Nenhum relevante |
| Estimar compatibilidade | Alta | Baixa | Score "no chute" se ficar só a cargo do modelo (ver §5.3) |
| Estimar salário | Média | Média | Poucos dados públicos confiáveis no Brasil; o Glassdoor ajuda |
| Gerar currículo sob medida | Alta | Baixa | Alucinação de experiências (resolvido por design, §5.6) |
| Acessar o site e preencher | Média | Alta | Layout muda, captcha, perguntas imprevistas |
| Submeter | Média | Alta | **LinkedIn proíbe automação e restringe contas**; na Gupy, os testes precisam ser feitos por você |

Cerca de 80% do valor está nas cinco primeiras linhas, que são baratas e estáveis. As duas últimas concentram quase todo o risco e a manutenção. Por isso a proposta é: **o sistema prepara tudo e preenche o formulário, e você revisa e clica em enviar.** O envio automático existe como opção, desligado por padrão (§5.7).

Custo estimado do modelo: **US$ 2–15/mês** para triar ~100 vagas/dia e gerar ~10 currículos/dia (§6.2).

## 2. Princípios

1. **Modelo só onde código não resolve.** Filtros, deduplicação, cálculo de score, salário e montagem do currículo são determinísticos. O modelo extrai informação de texto livre, escolhe o que destacar e responde perguntas novas.
2. **Uma fonte da verdade.** Um currículo mestre (YAML do resume-builder) com tudo o que você já fez. Todo currículo enviado é um recorte dele, e o modelo não escreve fatos novos.
3. **Você aprova antes de enviar.** O sistema para na tela de revisão.
4. **Sem infraestrutura nova.** Python, SQLite (um arquivo), Playwright e a CLI. Sem servidor, fila, banco vetorial ou framework de agentes.
5. **Tudo idempotente e auditável.** Cada vaga tem um status no banco, cada chamada ao modelo registra tokens e custo, e cada candidatura guarda o PDF, as respostas e um screenshot.
6. **Código aberto e simples.** Código, chaves de YAML e banco em inglês; mensagens e documentação em português. Validação estrita da entrada, funções puras testáveis sem rede, CI com lint e testes (convenções em [`CLAUDE.md`](../CLAUDE.md)).

## 3. Fluxo

```
          ┌──────── data/profile.yaml + data/master.yaml (você edita) ────────┐
          │                                                                   │
 search ──► filter ──► analyze ──► salary ──► review ──► tailor ──────► apply
 (JobSpy,   (regras)    (modelo)    (código)   (você)     (modelo +      (Playwright,
  Gupy)                                                    resume-        para antes
                                                           builder)       de enviar)
          └─────────────────────── data/jobhunt.db (SQLite) ──────────────────┘
```

Cada seta é um subcomando de `jobhunt` que lê as vagas de um status e as move para o seguinte:

`new → discarded | filtered → analyzed → approved | rejected → tailored → filled → submitted | failed`

`search → filter → analyze` pode rodar todo dia por cron (ou Agendador de Tarefas no Windows). De `review` em diante, a execução é sua, na sua máquina.

## 4. Dados

Tudo fica em `data/`, fora do Git. `jobhunt init` cria a pasta, e `jobhunt check` valida o conteúdo.

### 4.1 Currículo mestre e perfil

**`data/master.yaml`** é um YAML comum do resume-builder, só que com **todas** as experiências, projetos e bullets, inclusive os que não cabem numa página. Você já conhece o formato, e o `resume-builder build` continua funcionando com ele.

Para o modelo apontar itens sem copiar texto, o código numera o currículo no momento de cada chamada: `s0.e1.b2` é o terceiro bullet do segundo item da primeira seção. Você não mantém IDs nem tags à mão. Se o currículo mudar, as análises antigas são invalidadas pelo hash (§6.3).

**`data/profile.yaml`** guarda o resto: termos de busca, filtros, anos por competência e respostas reutilizáveis. O modelo comentado está em [`src/jobhunt/templates/profile.yaml`](../src/jobhunt/templates/profile.yaml):

```yaml
resume: master.yaml
search:
  terms: [desenvolvedor back-end java, engenheiro de software]
  location: São Paulo, SP
  sites: [linkedin, indeed, glassdoor, gupy]
  hours_old: 72
  results_per_term: 30
filters:
  seniority: [mid, senior]
  work_model: [remote, hybrid]
  min_salary: 12000        # CLT, mensal, bruto
  pj_factor: 1.4
  exclude_terms: [estágio, php]
skills:
  - { name: Java, years: 6, aliases: [Java 17, JVM] }
answers:
  - { question: Qual a sua disponibilidade para início?, answer: 30 dias }
```

### 4.2 Banco (`data/jobhunt.db`)

SQLite com `sqlite3` da biblioteca padrão. As tabelas entram por migrações (`jobhunt/db.py`, versão em `PRAGMA user_version`), conforme cada etapa for implementada:

| Tabela | Colunas principais | Estado |
| --- | --- | --- |
| `jobs` | `site`, `external_id`, `url`, `title`, `company`, `location`, `description`, `dedup_key`, `status`, `found_at` | criada |
| `jobs` (novas colunas) | `analysis` (JSON), `score`, `salary_min/max`, `salary_source` | com `analyze` e `salary` |
| `applications` | `job_id`, `resume_path`, `pdf_path`, `answers` (JSON), `screenshot_path`, `status`, `submitted_at` | com `tailor` e `apply` |
| `answers` | `question_key`, `question`, `answer`, `origin` (profile · model · you), `reviewed` | com `apply` |
| `model_usage` | `step`, `model`, `input_tokens`, `cache_tokens`, `output_tokens`, `cost_usd`, `at` | com o primeiro uso do modelo |

`UNIQUE(site, external_id)` impede repetir a mesma vaga do mesmo site. `dedup_key` (empresa + título + local, sem acentos nem pontuação) permite ao `filter` marcar a mesma vaga publicada em dois sites.

## 5. Etapas

### 5.1 Buscar

Cada fonte é um módulo em `jobhunt/sources/` com uma única função, `search(profile) -> list[Posting]`. Nenhum outro módulo conhece JobSpy ou Gupy.

**LinkedIn, Indeed e Glassdoor: [JobSpy](https://pypi.org/project/python-jobspy/).** Uma chamada de `scrape_jobs()` busca nos três sites, sem login, e devolve uma tabela com título, empresa, local, URL, descrição, faixa salarial (`min_amount`, `max_amount`, `interval`, `salary_source`) e, no Glassdoor, nota e porte da empresa. A versão 1.5 cobre o Brasil no Indeed e no Glassdoor (`country_indeed="brazil"` usa o glassdoor.com.br). Pontos de atenção:

- No LinkedIn, a descrição só vem com `fetch_description=True`, que faz uma requisição a mais por vaga. Mantenha `results_per_term` baixo.
- LinkedIn e Indeed aceitam só um filtro "especial" por busca: `hours_old` **ou** `easy_apply` (só candidatura simplificada) **ou** tipo de vaga e remoto.
- O LinkedIn costuma limitar por volta da 10ª página de resultados. Em uso pessoal, isso não chega a ser um problema.
- É uma biblioteca não oficial e quebra quando os sites mudam: fixe a versão no `pyproject.toml` e teste o adaptador contra uma resposta salva em `tests/`.
- Traz dependências pesadas (pandas, curl-cffi). Elas ficam isoladas no extra `jobhunt` e no módulo `sources/jobspy.py`.

**Gupy: adaptador próprio.** O portal `portal.gupy.io` usa uma API JSON pública e não documentada (hoje `portal.api.gupy.io/api/v1/jobs`, paginada por `offset`/`limit` e filtrável por nome da vaga). A página de cada vaga (`<empresa>.gupy.io/jobs/<id>`) traz descrição, responsabilidades, requisitos e informações adicionais em campos separados. Confirme os parâmetros nas ferramentas de desenvolvedor do navegador antes de implementar. Os termos da Gupy proíbem "agregar, copiar ou duplicar partes" da plataforma. Para uso pessoal, em baixo volume e sem republicar nada, o risco é pequeno, mas existe.

**Alternativa sem scraping:** e-mails de alerta do LinkedIn e da Gupy, lidos por IMAP (biblioteca padrão). Fica como plano B, se o JobSpy parar de funcionar.

**VPN e proxies.** O JobSpy acessa os sites sem login, então a sua conta não participa da busca. O pior caso é o seu IP receber um bloqueio temporário (HTTP 429).

- Em volume pessoal (algumas buscas por dia), isso raramente acontece num IP residencial. A VPN não é necessária.
- VPNs comerciais como a NordVPN usam IPs compartilhados por muitos usuários. Esses IPs costumam já ser limitados ou desafiados com captcha, principalmente no Glassdoor e no LinkedIn. A VPN pode piorar em vez de ajudar.
- Se aparecer 429: reduza `results_per_term`, espace as buscas e, só então, use o parâmetro `proxies` do JobSpy, que afeta só a busca.
- **Na candidatura (logado), não use VPN.** Logins que mudam de IP e de país disparam verificações de segurança no LinkedIn e aumentam o risco da conta. Se a NordVPN ficar ligada o tempo todo, use o split tunneling do aplicativo (se o seu sistema tiver) para tirar o navegador da candidatura da VPN.
- A VPN não muda nada em relação aos termos de uso.

### 5.2 Filtrar (sem modelo)

Regras de `profile.filters`, aplicadas sobre os campos estruturados e o título:

- já vista em outro site (`dedup_key`) ou já candidatada;
- empresa ou termo excluído (sem diferenciar maiúsculas nem acentos);
- senioridade incompatível, por regex no título (`estágio|júnior|jr\b|trainee`);
- modelo de trabalho e local;
- salário publicado abaixo do mínimo (com o fator PJ aplicado).

Em buscas amplas, essas regras costumam descartar boa parte das vagas antes de gastar qualquer token.

### 5.3 Analisar: extração e compatibilidade (uma chamada por vaga)

Entrada:
- o texto da vaga já limpo (HTML convertido em texto, sem os blocos genéricos de "sobre nós", LGPD e "venha fazer parte"; na Gupy, só os campos relevantes);
- um **perfil compacto** com ~600–800 tokens, gerado por código a partir do currículo mestre e do perfil (competências com anos, cargos e preferências).

Saída em **JSON com schema** (structured outputs), curta e sem prosa:

```json
{
  "role": "engenheiro de software back-end",
  "seniority": "senior",
  "work_model": "remote",
  "contract": "CLT",
  "salary": { "min": 14000, "max": 18000, "period": "month" },
  "benefits": ["plano de saúde", "VR/VA", "PLR"],
  "requirements": [
    { "text": "Java 17+", "required": true, "match": "yes", "evidence": "s0.e0.b1" },
    { "text": "Kafka", "required": false, "match": "partial", "evidence": "s0.e1.b0" },
    { "text": "Go", "required": true, "match": "no", "evidence": null }
  ],
  "warnings": ["exige inglês avançado"],
  "summary": "Back-end Java em fintech, time de pagamentos."
}
```

**O score é calculado em código**, não pelo modelo. Requisitos obrigatórios pesam 3 e desejáveis pesam 1. `yes` vale 1, `partial` vale 0,5 e `no` vale 0. Alertas aplicam penalidades configuráveis. O resultado vai de 0 a 100. Assim o score é estável, explicável (você vê por que deu 72) e ajustável sem mudar o prompt. `evidence` aponta para um item do currículo mestre, o que permite conferir cada "sim".

### 5.4 Salário (sem modelo)

Em ordem, até encontrar um valor:

1. **Faixa publicada na vaga** (pela extração ou pelos campos do JobSpy). Confiança alta.
2. **Mediana do próprio banco**: vagas com faixa publicada e o mesmo cargo e senioridade (e região, se houver), quando houver pelo menos 5. O Glassdoor e o Indeed alimentam bem essa base. Melhora sozinha com o tempo. Confiança média.
3. **Tabela de referência** importada uma vez por ano em `data/salaries.csv`, a partir de guias salariais públicos (Robert Half, Michael Page, Hays) ou de dados do CAGED (salario.com.br). Confiança baixa a média.
4. Sem dados: "sem estimativa". **Não peça ao modelo para adivinhar salário.** Ele responde com confiança e sem base.

Tudo é normalizado para "CLT mensal equivalente", com o `pj_factor`. Quando o JobSpy marca `salary_source` como estimativa do site, e não como valor publicado, a confiança cai um nível.

### 5.5 Revisar (você)

`jobhunt review` lista as analisadas em ordem de score: empresa, cargo, score, faixa salarial com a fonte, requisitos não atendidos e alertas. Você aprova ou rejeita cada uma. Uma alternativa é gerar um relatório HTML estático com Jinja (a mesma base de templates do resume-builder) e marcar as aprovadas na CLI.

### 5.6 Currículo sob medida

O modelo **não reescreve o currículo**. Ele devolve um **plano de seleção** que aponta itens do currículo mestre:

```json
{
  "headline": "Engenheira de Software Back-end · Java e AWS",
  "summary": "2–3 frases com o vocabulário da vaga.",
  "keep": { "s0.e0": [1, 0, 3], "s0.e1": [0], "s1.e0": [] },
  "rewrite": { "s0.e0.b1": "Mesmo fato, com os termos que a vaga usa." }
}
```

`keep` lista os itens que ficam, com os bullets na ordem desejada. Itens fora de `keep` saem. Seções de competências, listas e textos curtos ficam inteiras.

Depois, o código:
1. valida o plano: todo ID existe, só há reescrita de bullets mantidos, há limite de caracteres e **todo número numa reescrita precisa aparecer no bullet original** (uma regex simples barra métricas inventadas);
2. monta o recorte com `dataclasses.replace` sobre o `Resume` do currículo mestre e chama o `build_pdf()` que já existe, com o ajuste de páginas do `fit.py`;
3. salva `data/out/<vaga>.yaml` e `.pdf`. O YAML pode ser editado à mão antes de reconstruir o PDF.

Saída de ~500–800 tokens em vez de ~3.000 para um currículo inteiro, e nenhuma experiência inventada.

**Formato por site:**
- **LinkedIn (candidatura simplificada):** upload de PDF por candidatura (aceita PDF de até 2 MB). Os PDFs do resume-builder ficam bem abaixo disso.
- **Gupy:** o currículo é o seu **perfil estruturado**, compartilhado entre todas as candidaturas. Reescrevê-lo a cada vaga não faz sentido e é arriscado. Mantenha o perfil da Gupy completo a partir do currículo mestre (a IA da Gupy ranqueia por ele) e concentre a personalização nas perguntas da vaga.
- **Campos de texto livre** ("fale sobre você", carta): adicionar `render_text(resume)` ao resume-builder, que gera texto ou markdown a partir do mesmo `Resume`. É uma mudança pequena.

### 5.7 Candidatar (Playwright, assistido)

- **Sessão:** `launch_persistent_context(data/browser/)`. Você faz login à mão uma vez, e o sistema nunca guarda senha. Se aparecer captcha, você resolve.
- **Um adaptador por site** (`apply/linkedin.py`, `apply/gupy.py`), com seletores e passos fixos. Para cada campo, o adaptador extrai `{rótulo, tipo, opções, obrigatório}`, que é um texto compacto, sem screenshot, e resolve o valor nesta ordem:
  1. **dados do currículo mestre** (nome, e-mail, telefone, links);
  2. **regras determinísticas**, como "Quantos anos de experiência com X?" respondido com `skills[].years` (é a pergunta mais comum do LinkedIn);
  3. **respostas salvas**: pergunta normalizada (minúsculas, sem acento nem pontuação, com `jobhunt.text.normalize`), igualdade exata e depois `difflib` com similaridade ≥ 0,9;
  4. **modelo**, só para perguntas novas. Ele recebe o perfil compacto e a pergunta e responde dentro das opções do campo. A resposta é salva com `reviewed = false`, e você a confirma na revisão.
- **Para antes de enviar** e mostra a tela de revisão. Você confere e clica. O sistema registra screenshot, PDF e respostas.
- **Gupy:** se houver testes (lógica, perfil, inglês) ou vídeo, o sistema para. Isso é com você, e automatizar essas etapas configura "fornecer informações falsas" nos termos.
- **Candidatura externa** (o botão do LinkedIn ou do Glassdoor leva para Workday, Greenhouse, Lever etc.): fora do escopo. O sistema abre a URL e entrega o PDF e as respostas prontas para colar.
- **`--submit` (opcional, desligado por padrão):** envia sozinho só quando todos os campos foram resolvidos pelos passos 1–3, sem nenhuma pergunta nova, com limite diário (por exemplo, 5) e intervalos humanos entre candidaturas. Mesmo assim, no LinkedIn isso viola os termos de uso. A decisão é sua.

## 6. Modelo e economia de tokens

### 6.1 Modelo por etapa

| Etapa | Modelo sugerido | Preço (US$ por 1M tokens, entrada / saída) | Por quê |
| --- | --- | --- | --- |
| Analisar | Claude Haiku 5.5 (`claude-haiku-5-5`), effort `low` | 0,10 / 0,50 | Extração com schema, alto volume |
| Currículo | Claude Sonnet 5.5 (`claude-sonnet-5-5`) | 2 / 10 | Precisa de julgamento sobre o que destacar |
| Perguntas novas | Claude Haiku 5.5 ou Sonnet 5.5 | — | Curtas e raras depois do primeiro mês |
| (alternativa) | Claude Opus 5.5 (`claude-opus-5-5`) | 4 / 20 | Se a qualidade do currículo com o Sonnet não bastar: cerca de 2× o custo |

O modelo de cada etapa fica no `profile.yaml` (chave `models`, a criar com a primeira etapa que usar o modelo). Antes de fixar as escolhas, rode 10 vagas reais em cada modelo e compare.

### 6.2 Custo estimado (cenário alto: 100 vagas analisadas/dia, 10 currículos/dia)

| Etapa | Tokens por item (entrada / saída) | Por item | Por mês |
| --- | --- | --- | --- |
| Analisar (Haiku, Batch API) | ~3.000 / ~500 | ~US$ 0,0003 | **~US$ 1** (3.000 vagas) |
| Currículo (Sonnet) | ~7.600 / ~2.300 | ~US$ 0,04 | **~US$ 11** (300 currículos) |
| Currículo (Opus, alternativa) | ~7.600 / ~2.300 | ~US$ 0,08 | ~US$ 23 |
| Perguntas novas | ~1.500 / ~300 | < US$ 0,01 | < US$ 2, caindo com o tempo |

Com 3 candidaturas por dia, o total fica em **~US$ 5/mês**. Para comparar: um agente de navegador movido a screenshots (computer use) gasta dezenas a centenas de milhares de tokens por candidatura, na ordem de **US$ 0,50–1 por candidatura**, e é mais lento e menos previsível que um adaptador Playwright.

As estimativas usam os preços da API em nov/2026 e incluem uma margem para tokens de raciocínio. Os valores reais ficam na tabela `model_usage`.

### 6.3 Táticas, por ordem de impacto

1. **Filtros antes do modelo** (§5.2): a vaga descartada não custa nada.
2. **Nunca reprocessar.** A análise fica guardada por hash do texto da vaga + versão do prompt + hash do perfil compacto.
3. **Texto limpo e perfil compacto** na triagem, em vez de HTML e currículo completo. A entrada fica várias vezes menor.
4. **Uma chamada por vaga** (extrai e avalia ao mesmo tempo), com saída em JSON com schema, enums e campos curtos. O score é calculado em código.
5. **Batch API na triagem diária:** 50% de desconto. O resultado é assíncrono, o que não faz diferença num cron.
6. **Plano de seleção por IDs** no currículo (§5.6): saída cerca de 5 vezes menor.
7. **Respostas salvas e regras** (§5.7): depois de algumas semanas, quase nenhuma pergunta chega ao modelo.
8. **Cache de prompt** no currículo: as instruções e o currículo mestre (~7 mil tokens) vêm primeiro e sem variação, então ao gerar vários currículos na mesma sessão a releitura custa 10% do preço. Na triagem, o prefixo é curto demais para o cache valer a pena, então não conte com ele ali.
9. **Orçamento:** cada chamada grava `usage` em `model_usage`, e a CLI aborta se passar do limite diário configurado.
10. **Sem agente de navegador por screenshot e sem web search do modelo para buscar vagas.** Os adaptadores HTTP e Playwright fazem isso de graça.

## 7. Tecnologias

**Em uso:**
- Python 3.11+ (3.12 no Docker e no CI). O resume-builder é usado como biblioteca (`load_resume`, `build_pdf`).
- `pydantic` para validar o perfil, com mensagens em português e o caminho exato do campo.
- `sqlite3` da biblioteca padrão, com migrações próprias.
- `ruff` (lint) e `pytest`, rodando no GitHub Actions a cada push.

**A seguir:**
- `python-jobspy` para LinkedIn, Indeed e Glassdoor; `httpx` para a API da Gupy.
- `anthropic`, o SDK oficial, com structured outputs (`output_config.format`), Batch API e cache de prompt.
- `playwright`, só no passo de candidatura e rodando na sua máquina, com navegador visível. Vai num extra separado (`apply`), porque é pesado.
- Cron, ou o Agendador de Tarefas no Windows, para `search → filter → analyze`. Essa parte pode rodar no Docker (`docker compose run --rm jobhunt ...`).

As dependências do `jobhunt` ficam em extras (`pip install -e ".[jobhunt]"`), para que o resume-builder continue leve.

**Não usar (por ora):** LangChain/LlamaIndex, banco vetorial ou embeddings (`difflib` resolve as respostas salvas), ORM, servidor web, fila, Redis, Kubernetes, agentes autônomos e computer use.

## 8. Estrutura de código

```
src/
├── resume_builder/          # existente; ganha render_text()
└── jobhunt/
    ├── cli.py               # init · check | search · filter · analyze · review · tailor · apply · usage
    ├── profile.py           # perfil validado (pydantic)
    ├── db.py                # SQLite: migrações e consultas
    ├── text.py              # normalização para comparar títulos, empresas e perguntas
    ├── templates/profile.yaml
    ├── sources/
    │   ├── jobspy.py        # LinkedIn, Indeed, Glassdoor → Posting
    │   └── gupy.py
    ├── filters.py           # regras determinísticas e deduplicação entre sites
    ├── analyze.py           # chamada de triagem + cálculo do score
    ├── salary.py
    ├── tailor.py            # numeração do currículo mestre, plano de seleção, validação, build
    ├── answers.py           # regras e respostas salvas
    ├── apply/
    │   ├── linkedin.py      # Playwright: candidatura simplificada
    │   └── gupy.py
    ├── llm.py               # cliente, batch, registro de uso, orçamento
    └── prompts/             # analyze.md, tailor.md, answer.md
data/                        # fora do Git: profile.yaml, master.yaml, jobhunt.db, salaries.csv, browser/, out/
```

Hoje existem `cli.py` (com `init` e `check`), `profile.py`, `db.py`, `text.py` e o modelo do perfil; o resto entra conforme o roteiro (§10). A estimativa é de 1.500 a 2.500 linhas no total, de duas a três vezes o resume-builder atual. Os testes ficam em `tests/jobhunt/`: as funções puras (filtros, score, salário, validação do plano, normalização) são testadas sem rede e sem modelo, e os adaptadores rodam contra respostas salvas.

## 9. Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Restrição da conta no LinkedIn (os termos proíbem bots, extensões e automação) | Busca sem login (JobSpy); candidatura assistida com envio manual; baixo volume; sem VPN na sessão logada |
| Bloqueio de IP na busca (HTTP 429) | Volume baixo, buscas espaçadas; proxy só na busca, se precisar (§5.1) |
| JobSpy ou API da Gupy quebram | Versão fixada; um adaptador por fonte; testes com respostas salvas; plano B por e-mail de alerta |
| Suspensão na Gupy (uso "impróprio", agregação de conteúdo) | Baixo volume, uso pessoal, testes feitos por você, informações sempre verdadeiras |
| Mudança de layout quebra o adaptador de candidatura | Seletores por rótulo e papel (`get_by_role`, `get_by_label`) em vez de classes CSS; falha explícita com screenshot; testes com HTML salvo |
| Captcha ou verificação | Navegador visível; você resolve; o sistema espera |
| Currículo com informação falsa | Plano por IDs, validação de números e YAML editável antes do PDF |
| Resposta errada a uma pergunta com consequência (pretensão salarial, disponibilidade, "possui CNH?") | Respostas do modelo ficam `reviewed = false` e são confirmadas por você antes do envio |
| Candidatura em massa piora a taxa de retorno | Score mínimo, limite diário e revisão humana: menos candidaturas, melhores |
| Dados pessoais | Tudo local em `data/`, fora do Git; ao modelo vão só o perfil e o texto da vaga; a API não usa os dados para treino por padrão |

## 10. Estado e próximos passos

**Feito:**

- [x] Pacote `jobhunt` neste repositório, com extra próprio e o comando `jobhunt`
- [x] Perfil validado (`profile.py`) e modelo comentado em `templates/profile.yaml`
- [x] Banco com migrações e a tabela `jobs` (`db.py`), com `Posting` e `add_postings`
- [x] `jobhunt init` (cria `data/`, o perfil e o banco, sem sobrescrever nada) e `jobhunt check` (valida perfil e currículo mestre)
- [x] Lint (`ruff`) e testes no GitHub Actions

**Roteiro:**

| Fase | Entrega | Complexidade | Esforço aproximado |
| --- | --- | --- | --- |
| 0 | `llm.py` e `tailor.py`: `jobhunt tailor --text vaga.txt` gera análise e PDF sob medida a partir de uma vaga colada | Baixa | 1–2 dias |
| 1 | `sources/jobspy.py` e `filters.py`: `jobhunt search` e `jobhunt filter` (LinkedIn, Indeed, Glassdoor) | Média | 2–3 dias |
| 2 | `analyze.py`, `salary.py` e `jobhunt review`: triagem em lote, score e faixa salarial | Média | 3–4 dias |
| 3 | `sources/gupy.py` | Média | 1–2 dias |
| 4 | `answers.py` e `apply/linkedin.py`: candidatura assistida no LinkedIn | Alta | 3–5 dias, mais manutenção |
| 5 | `apply/gupy.py`: candidatura assistida na Gupy | Alta | 3–5 dias, mais manutenção |
| — | ATS externos (Workday, Greenhouse, Lever…) | Muito alta | Fora do escopo |

A fase 0 sozinha já entrega boa parte do ganho e valida os prompts antes de qualquer scraping. As fases 0 e 1 são independentes e podem ser feitas em qualquer ordem. As fases 4 e 5 valem a pena só se o volume de candidaturas justificar a manutenção.

## 11. Decisões

**Tomadas:**
- Mesmo repositório, pacote `jobhunt` com dependências opcionais.
- LinkedIn, Indeed e Glassdoor pelo JobSpy; Gupy por adaptador próprio; e-mails de alerta como plano B.
- Código e dados em inglês, interface e documentação em português (as mesmas convenções do resume-builder).

**Em aberto:**
1. Envio automático (`--submit`): fica como opção ou sai do projeto?
2. Modelo do currículo: Sonnet 5.5 ou Opus 5.5 (decidir depois do teste com 10 vagas da fase 0).
3. **Licença.** Sem um arquivo `LICENSE`, o código não é aberto de fato: por padrão, todos os direitos ficam reservados. MIT é a opção mais simples; GPL-3.0 obriga quem distribuir versões modificadas a abrir o código.
4. VPN: a recomendação é não usar na busca enquanto o volume for baixo, e nunca na candidatura (§5.1).

## Fontes

- [Termos de uso da Gupy para pessoas candidatas](https://www.gupy.io/termos-de-uso-recrutamento-e-selecao-candidatos): condutas proibidas, suspensão de cadastro e uso de IA no ranqueamento.
- [LinkedIn: software e extensões proibidos](https://www.linkedin.com/help/linkedin/answer/a1341387) e [Automated activity on LinkedIn](https://www.linkedin.com/help/linkedin/answer/90586). O User Agreement (§8.2) proíbe bots e métodos automatizados não autorizados.
- [JobSpy (`python-jobspy`)](https://pypi.org/project/python-jobspy/): busca não oficial em LinkedIn, Indeed, Glassdoor e outros. A cobertura do Brasil foi conferida no código da versão 1.5.0.
- [Scrapers públicos da Gupy (Apify)](https://apify.com/parsebird/gupy-io-jobs-scraper): referência sobre a API `portal.api.gupy.io`, que não é documentada.
- Preços da API Claude: [platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing) (valores de nov/2026).
