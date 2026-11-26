# Automação de candidaturas: especificação

Estado: proposta · Escopo: LinkedIn (candidatura simplificada) e Gupy · Nome provisório do pacote: `vagas`

## 1. Veredito

O projeto é viável se for um **copiloto de candidaturas**. Como robô que se candidata sozinho e em massa, não é recomendável. As etapas têm níveis de risco bem diferentes:

| Etapa | Viabilidade | Complexidade | Risco principal |
| --- | --- | --- | --- |
| Buscar vagas | Alta (Gupy) · Média (LinkedIn) | Média | LinkedIn não tem API para candidatos; termos proíbem scraping |
| Ler requisitos e benefícios | Alta | Baixa | Nenhum relevante |
| Estimar compatibilidade | Alta | Baixa | Score "no chute" se ficar só a cargo do modelo (ver §5.3) |
| Estimar salário | Média | Média | Poucos dados públicos confiáveis no Brasil |
| Gerar currículo sob medida | Alta | Baixa | Alucinação de experiências (resolvido por design, §5.6) |
| Acessar o site e preencher | Média | Alta | Layout muda, captcha, perguntas imprevistas |
| Submeter | Média | Alta | **LinkedIn proíbe automação e restringe contas**; na Gupy, os testes precisam ser feitos por você |

Cerca de 80% do valor está nas cinco primeiras linhas, que são baratas e estáveis. As duas últimas concentram quase todo o risco e a manutenção. Por isso a proposta é: **o sistema prepara tudo e preenche o formulário, e você revisa e clica em enviar.** O envio automático existe como opção, desligado por padrão (§5.7).

Custo estimado do modelo: **US$ 2–15/mês** para triar ~100 vagas/dia e gerar ~10 currículos/dia (§6.2).

## 2. Princípios

1. **Modelo só onde código não resolve.** Filtros, deduplicação, cálculo de score, salário e montagem do currículo são determinísticos. O modelo extrai informação de texto livre, escolhe o que destacar e responde perguntas novas.
2. **Uma fonte da verdade.** Um perfil mestre em YAML com tudo o que você já fez. Todo currículo é um recorte dele, e o modelo não escreve fatos novos.
3. **Você aprova antes de enviar.** O sistema para na tela de revisão.
4. **Sem infraestrutura nova.** Python, SQLite (um arquivo), Playwright e a CLI. Sem servidor, fila, banco vetorial ou framework de agentes.
5. **Tudo idempotente e auditável.** Cada vaga tem um status no banco, cada chamada ao modelo registra tokens e custo, e cada candidatura guarda o PDF, as respostas e um screenshot.

## 3. Fluxo

```
            ┌────────────── perfil.yaml (você edita) ───────────────┐
            │                                                        │
 buscar ──► filtrar ──► analisar ──► salário ──► revisar ──► currículo ──► candidatar
 (HTTP)    (regras)    (modelo)     (código)    (você)      (modelo +     (Playwright,
                                                             resume-       para antes
                                                             builder)      de enviar)
            └──────────────────────── vagas.db (SQLite) ─────────────────────────┘
```

Cada seta é um subcomando da CLI que lê as vagas de um status e as move para o seguinte:

`nova → descartada | filtrada → analisada → aprovada | rejeitada → curriculo_pronto → preenchida → enviada | falhou`

`buscar → filtrar → analisar` pode rodar todo dia por cron (ou Agendador de Tarefas no Windows). De `revisar` em diante, a execução é sua, na sua máquina.

## 4. Dados

### 4.1 Perfil mestre (`data/perfil.yaml`, fora do Git)

É um superconjunto do YAML atual do resume-builder, com **IDs estáveis** e **tags** em cada item. Os IDs permitem que o modelo responda com referências em vez de texto.

```yaml
pessoa:                       # vira `basics` no currículo
  name: Ana Souza
  email: ana@example.com
  links: [...]

preferencias:                 # alimenta os filtros (§5.2)
  cargos: [back-end, engenheira de software, desenvolvedora java]
  senioridade: [pleno, senior]
  modelo: [remoto, "hibrido:São Paulo"]
  contrato: [CLT, PJ]
  salario_minimo_clt: 12000   # mensal, bruto
  fator_pj: 1.4               # PJ equivalente = CLT × fator
  excluir_empresas: [Empresa X]
  excluir_termos: [estágio, PHP, "inglês fluente"]

competencias:
  - { id: java, nome: Java, anos: 6, nivel: avancado, sinonimos: [Java 17, Java 21, JVM] }
  - { id: aws, nome: AWS, anos: 4, nivel: intermediario, sinonimos: [EKS, SQS, S3] }

experiencias:
  - id: pagamentos
    title: Engenheira de Software Sênior
    org: Pagamentos Exemplo S.A.
    period: jan 2023 – atual
    bullets:
      - { id: pag-migracao, tags: [java, aws, microsservicos], text: "Desenhei a migração ..." }
      - { id: pag-conciliacao, tags: [java, sqs, performance], text: "Reduzi o tempo de conciliação de **4 h para 35 min** ..." }

projetos: [...]
formacao: [...]

respostas:                    # banco de respostas reutilizáveis (§5.7)
  - { pergunta: "pretensão salarial", resposta: "14000" }
  - { pergunta: "disponibilidade para início", resposta: "30 dias" }
```

### 4.2 Banco (`data/vagas.db`, SQLite com `sqlite3` da biblioteca padrão)

| Tabela | Colunas principais |
| --- | --- |
| `vagas` | `id`, `fonte`, `id_externo`, `url`, `empresa`, `titulo`, `texto`, `hash_texto`, `status`, `analise` (JSON), `score`, `salario_min/max`, `salario_fonte`, `criada_em` |
| `candidaturas` | `vaga_id`, `yaml_path`, `pdf_path`, `respostas` (JSON), `screenshot_path`, `status`, `enviada_em` |
| `respostas` | `pergunta_normalizada`, `pergunta_original`, `resposta`, `origem` (perfil · modelo · você), `revisada` |
| `uso_modelo` | `etapa`, `modelo`, `tokens_entrada`, `tokens_cache`, `tokens_saida`, `custo_usd`, `quando` |

A deduplicação usa `UNIQUE(fonte, id_externo)` mais o hash de `empresa + título normalizado`, que pega a mesma vaga publicada na Gupy e no LinkedIn.

## 5. Etapas

### 5.1 Buscar

Cada fonte é um módulo com uma única função, `buscar(consulta) -> list[VagaBruta]`.

**Gupy.** O portal `portal.gupy.io` usa uma API JSON pública e não documentada (hoje `portal.api.gupy.io/api/v1/jobs`, paginada por `offset`/`limit` e filtrável por nome da vaga). A página de cada vaga (`<empresa>.gupy.io/jobs/<id>`) traz descrição, responsabilidades, requisitos e informações adicionais em campos separados. Como a API não é documentada, confirme os parâmetros nas ferramentas de desenvolvedor do navegador. Os termos da Gupy proíbem "agregar, copiar ou duplicar partes" da plataforma. Para uso pessoal, em baixo volume e sem republicar nada, o risco é pequeno, mas existe.

**LinkedIn.** Não há API de busca para candidatos, e os termos proíbem bots e scraping. Em ordem de preferência:

1. **E-mails de alerta de vagas**, lidos por IMAP (biblioteca padrão). Você configura os alertas no LinkedIn (e na Gupy, se quiser), e o sistema lê título, empresa e link sem tocar no site. É a opção mais segura.
2. **Página pública da vaga** (`linkedin.com/jobs/view/<id>`), aberta sem login e com poucas requisições por dia, só para obter a descrição.
3. **Opcional:** [JobSpy](https://pypi.org/project/python-jobspy/) (`python-jobspy`), uma biblioteca que busca no LinkedIn, Indeed e Glassdoor. É não oficial, quebra com frequência e tem as mesmas ressalvas de termos de uso.

Nunca use a sua sessão logada para buscar em volume: é o caminho mais rápido para ter a conta restrita.

### 5.2 Filtrar (sem modelo)

Regras do `perfil.preferencias`, aplicadas sobre os campos estruturados e o título:

- já vista ou já candidatada (hash);
- empresa ou termo excluído;
- senioridade incompatível, por regex no título (`estágio|júnior|jr\b|trainee`);
- modelo de trabalho e local;
- salário publicado abaixo do mínimo (com o fator PJ aplicado).

Em buscas amplas, essas regras costumam descartar boa parte das vagas antes de gastar qualquer token.

### 5.3 Analisar: extração e compatibilidade (uma chamada por vaga)

Entrada:
- o texto da vaga já limpo (HTML convertido em texto, sem os blocos genéricos de "sobre nós", LGPD e "venha fazer parte"; na Gupy, só os campos relevantes);
- um **perfil compacto** com ~600–800 tokens, gerado por código a partir do perfil mestre (competências com anos, cargos e preferências).

Saída em **JSON com schema** (structured outputs), curta e sem prosa:

```json
{
  "cargo_canonico": "engenheiro de software back-end",
  "senioridade": "senior",
  "modelo": "remoto",
  "contrato": "CLT",
  "salario": { "min": 14000, "max": 18000, "periodo": "mensal" },
  "beneficios": ["plano de saúde", "VR/VA", "PLR"],
  "requisitos": [
    { "texto": "Java 17+", "obrigatorio": true, "atende": "sim", "evidencia": "java" },
    { "texto": "Kafka", "obrigatorio": false, "atende": "parcial", "evidencia": "pag-conciliacao" },
    { "texto": "Go", "obrigatorio": true, "atende": "nao", "evidencia": null }
  ],
  "alertas": ["exige inglês avançado"],
  "resumo": "Back-end Java em fintech, time de pagamentos."
}
```

**O score é calculado em código**, não pelo modelo. Requisitos obrigatórios pesam 3 e desejáveis pesam 1. `sim` vale 1, `parcial` vale 0,5 e `nao` vale 0. Alertas aplicam penalidades configuráveis. O resultado vai de 0 a 100. Assim o score é estável, explicável (você vê por que deu 72) e ajustável sem mudar o prompt. `evidencia` aponta para um ID do perfil, o que permite conferir cada "sim".

### 5.4 Salário (sem modelo)

Em ordem, até encontrar um valor:

1. **Faixa publicada na vaga** (veio da extração). Confiança alta.
2. **Mediana do próprio banco**: vagas com faixa publicada e o mesmo `cargo_canonico` + `senioridade` (+ região, se houver), quando houver pelo menos 5. Melhora sozinha com o tempo. Confiança média.
3. **Tabela de referência** importada uma vez por ano em `data/salarios.csv`, a partir de guias salariais públicos (Robert Half, Michael Page, Hays) ou de dados do CAGED (salario.com.br). Confiança baixa a média.
4. Sem dados: "sem estimativa". **Não peça ao modelo para adivinhar salário.** Ele responde com confiança e sem base.

Tudo é normalizado para "CLT mensal equivalente", com o `fator_pj`.

### 5.5 Revisar (você)

`vagas revisar` lista as analisadas em ordem de score: empresa, cargo, score, faixa salarial com a fonte, requisitos não atendidos e alertas. Você aprova ou rejeita cada uma. Uma alternativa é gerar um relatório HTML estático com Jinja (a mesma base de templates do resume-builder) e marcar as aprovadas na CLI.

### 5.6 Currículo sob medida

O modelo **não reescreve o currículo**. Ele devolve um **plano de seleção** com IDs do perfil mestre:

```json
{
  "headline": "Engenheira de Software Back-end · Java e AWS",
  "resumo": "2–3 frases com o vocabulário da vaga.",
  "experiencias": [ { "id": "pagamentos", "bullets": ["pag-conciliacao", "pag-migracao"] } ],
  "reescritas": { "pag-conciliacao": "Mesmo fato, com os termos que a vaga usa." },
  "competencias": ["java", "aws", "kafka"],
  "palavras_chave": ["microsserviços", "mensageria"]
}
```

Depois, o código:
1. valida o plano: todo ID existe, só há reescrita de bullets selecionados, há limite de caracteres e **todo número numa reescrita precisa aparecer no bullet original** (uma regex simples barra métricas inventadas);
2. monta o dicionário no formato do resume-builder e chama `parse_resume()` e `build_pdf()`, que já existem, com o ajuste de páginas do `fit.py`;
3. salva `data/out/<vaga>.yaml` e `.pdf`. O YAML pode ser editado à mão antes de reconstruir o PDF.

Saída de ~500–800 tokens em vez de ~3.000 para um currículo inteiro, e nenhuma experiência inventada.

**Formato por site:**
- **LinkedIn (candidatura simplificada):** upload de PDF por candidatura (aceita PDF de até 2 MB). Os PDFs do resume-builder ficam bem abaixo disso.
- **Gupy:** o currículo é o seu **perfil estruturado**, compartilhado entre todas as candidaturas. Reescrevê-lo a cada vaga não faz sentido e é arriscado. Mantenha o perfil da Gupy completo a partir do perfil mestre (a IA da Gupy ranqueia por ele) e concentre a personalização nas perguntas da vaga.
- **Campos de texto livre** ("fale sobre você", carta): adicionar `render_text(resume)` ao resume-builder, que gera texto ou markdown a partir do mesmo `Resume`. É uma mudança pequena.

### 5.7 Candidatar (Playwright, assistido)

- **Sessão:** `launch_persistent_context(data/navegador/)`. Você faz login à mão uma vez, e o sistema nunca guarda senha. Se aparecer captcha, você resolve.
- **Um adaptador por site** (`apply/linkedin.py`, `apply/gupy.py`), com seletores e passos fixos. Para cada campo, o adaptador extrai `{rótulo, tipo, opções, obrigatório}`, que é um texto compacto, sem screenshot, e resolve o valor nesta ordem:
  1. **dados do perfil** (nome, e-mail, telefone, links);
  2. **regras determinísticas**, como "Quantos anos de experiência com X?" respondido com `competencias[].anos` (é a pergunta mais comum do LinkedIn);
  3. **banco de respostas**: pergunta normalizada (minúsculas, sem acento nem pontuação), igualdade exata e depois `difflib` com similaridade ≥ 0,9;
  4. **modelo**, só para perguntas novas. Ele recebe o perfil compacto e a pergunta e responde dentro das opções do campo. A resposta é salva com `revisada = false`, e você a confirma na revisão.
- **Para antes de enviar** e mostra a tela de revisão. Você confere e clica. O sistema registra screenshot, PDF e respostas.
- **Gupy:** se houver testes (lógica, perfil, inglês) ou vídeo, o sistema para. Isso é com você, e automatizar essas etapas configura "fornecer informações falsas" nos termos.
- **Candidatura externa** (o botão do LinkedIn leva para Workday, Greenhouse, Lever etc.): fora do escopo. O sistema abre a URL e entrega o PDF e as respostas prontas para colar.
- **`--enviar` (opcional, desligado por padrão):** envia sozinho só quando todos os campos foram resolvidos pelos passos 1–3, sem nenhuma pergunta nova, com limite diário (por exemplo, 5) e intervalos humanos entre candidaturas. Mesmo assim, no LinkedIn isso viola os termos de uso. A decisão é sua.

## 6. Modelo e economia de tokens

### 6.1 Modelo por etapa

| Etapa | Modelo sugerido | Preço (US$ por 1M tokens, entrada / saída) | Por quê |
| --- | --- | --- | --- |
| Analisar | Claude Haiku 5.5 (`claude-haiku-5-5`), effort `low` | 0,10 / 0,50 | Extração com schema, alto volume |
| Currículo | Claude Sonnet 5.5 (`claude-sonnet-5-5`) | 2 / 10 | Precisa de julgamento sobre o que destacar |
| Perguntas novas | Claude Haiku 5.5 ou Sonnet 5.5 | — | Curtas e raras depois do primeiro mês |
| (alternativa) | Claude Opus 5.5 (`claude-opus-5-5`) | 4 / 20 | Se a qualidade do currículo com o Sonnet não bastar: cerca de 2× o custo |

O modelo de cada etapa fica no `perfil.yaml` ou numa variável de ambiente. Antes de fixar as escolhas, rode 10 vagas reais em cada modelo e compare.

### 6.2 Custo estimado (cenário alto: 100 vagas analisadas/dia, 10 currículos/dia)

| Etapa | Tokens por item (entrada / saída) | Por item | Por mês |
| --- | --- | --- | --- |
| Analisar (Haiku, Batch API) | ~3.000 / ~500 | ~US$ 0,0003 | **~US$ 1** (3.000 vagas) |
| Currículo (Sonnet) | ~7.600 / ~2.300 | ~US$ 0,04 | **~US$ 11** (300 currículos) |
| Currículo (Opus, alternativa) | ~7.600 / ~2.300 | ~US$ 0,08 | ~US$ 23 |
| Perguntas novas | ~1.500 / ~300 | < US$ 0,01 | < US$ 2, caindo com o tempo |

Com 3 candidaturas por dia, o total fica em **~US$ 5/mês**. Para comparar: um agente de navegador movido a screenshots (computer use) gasta dezenas a centenas de milhares de tokens por candidatura, na ordem de **US$ 0,50–1 por candidatura**, e é mais lento e menos previsível que um adaptador Playwright.

As estimativas usam os preços da API em nov/2026 e incluem uma margem para tokens de raciocínio. Os valores reais ficam na tabela `uso_modelo`.

### 6.3 Táticas, por ordem de impacto

1. **Filtros antes do modelo** (§5.2): a vaga descartada não custa nada.
2. **Nunca reprocessar.** A análise fica guardada por `hash_texto + versão do prompt + versão do perfil compacto`.
3. **Texto limpo e perfil compacto** na triagem, em vez de HTML e perfil completo. A entrada fica várias vezes menor.
4. **Uma chamada por vaga** (extrai e avalia ao mesmo tempo), com saída em JSON com schema, enums e campos curtos. O score é calculado em código.
5. **Batch API na triagem diária:** 50% de desconto. O resultado é assíncrono, o que não faz diferença num cron.
6. **Plano de seleção por IDs** no currículo (§5.6): saída cerca de 5 vezes menor.
7. **Banco de respostas e regras** (§5.7): depois de algumas semanas, quase nenhuma pergunta chega ao modelo.
8. **Cache de prompt** no currículo: as instruções e o perfil mestre (~7 mil tokens) vêm primeiro e sem variação, então ao gerar vários currículos na mesma sessão a releitura custa 10% do preço. Na triagem, o prefixo é curto demais para o cache valer a pena, então não conte com ele ali.
9. **Orçamento:** cada chamada grava `usage` em `uso_modelo`, e a CLI aborta se passar de `ORCAMENTO_DIARIO_USD`.
10. **Sem agente de navegador por screenshot e sem web search do modelo para buscar vagas.** Os adaptadores HTTP e Playwright fazem isso de graça.

## 7. Tecnologias

**Usar:**
- Python 3.12, a mesma base do repositório. O resume-builder é usado como biblioteca (`parse_resume`, `build_pdf`).
- `sqlite3` e `imaplib` da biblioteca padrão.
- `httpx` para HTTP e `selectolax` ou BeautifulSoup para HTML. `trafilatura` é opcional, para remover boilerplate.
- `playwright`, só no passo de candidatura e rodando na sua máquina, com navegador visível.
- `anthropic`, o SDK oficial, com structured outputs (`output_config.format`), Batch API e cache de prompt.
- Cron, ou o Agendador de Tarefas no Windows, para `buscar → filtrar → analisar`. Essa parte pode rodar no Docker que já existe.

As novas dependências entram como opcionais (`pip install -e ".[vagas]"`), para que o resume-builder continue leve.

**Não usar (por ora):** LangChain/LlamaIndex, banco vetorial ou embeddings (`difflib` resolve o banco de respostas), ORM, servidor web, fila, Redis, Kubernetes, agentes autônomos e computer use.

## 8. Estrutura de código

```
src/
├── resume_builder/          # existente; ganha render_text()
└── vagas/
    ├── cli.py               # buscar | filtrar | analisar | revisar | curriculo | candidatar | custo
    ├── db.py                # schema e consultas SQLite
    ├── perfil.py            # perfil mestre → perfil compacto · plano → dict do resume-builder
    ├── fontes/
    │   ├── gupy.py
    │   └── linkedin.py      # alertas por e-mail + página pública
    ├── filtros.py           # regras determinísticas
    ├── analise.py           # chamada de triagem + cálculo do score
    ├── salario.py
    ├── curriculo.py         # plano de seleção, validação, build
    ├── respostas.py         # normalização, regras, banco de respostas
    ├── candidatura/
    │   ├── linkedin.py      # Playwright: candidatura simplificada
    │   └── gupy.py
    ├── llm.py               # cliente, batch, registro de uso, orçamento
    └── prompts/             # analise.md, curriculo.md, pergunta.md
data/                        # fora do Git: perfil.yaml, vagas.db, salarios.csv, navegador/, out/
```

São de 1.500 a 2.500 linhas no total, de duas a três vezes o resume-builder atual. Os testes seguem o padrão do repositório: as funções puras (filtros, score, salário, validação do plano, normalização de perguntas) são testadas sem rede e sem modelo, e os adaptadores rodam contra HTML salvo em `tests/fixtures/`.

## 9. Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Restrição da conta no LinkedIn (os termos proíbem bots, extensões e automação) | Buscar por e-mail de alerta; candidatura assistida com envio manual; baixo volume; nada de sessão logada para buscar |
| Suspensão na Gupy (uso "impróprio", agregação de conteúdo) | Baixo volume, uso pessoal, testes feitos por você, informações sempre verdadeiras |
| Mudança de layout quebra o adaptador | Seletores por rótulo e papel (`get_by_role`, `get_by_label`) em vez de classes CSS; falha explícita com screenshot; testes com HTML salvo |
| Captcha ou verificação | Navegador visível; você resolve; o sistema espera |
| Currículo com informação falsa | Plano por IDs, validação de números e YAML editável antes do PDF |
| Resposta errada a uma pergunta com consequência (pretensão salarial, disponibilidade, "possui CNH?") | Respostas do modelo ficam `revisada = false` e são confirmadas por você antes do envio |
| Candidatura em massa piora a taxa de retorno | Score mínimo, limite diário e revisão humana: menos candidaturas, melhores |
| Dados pessoais | Tudo local; ao modelo vão só o perfil e o texto da vaga; a API não usa os dados para treino por padrão |

## 10. Plano em fases

| Fase | Entrega | Complexidade | Esforço aproximado |
| --- | --- | --- | --- |
| 0 | Perfil mestre e `vagas curriculo --texto vaga.txt`: você cola a vaga e recebe a análise e o PDF sob medida | Baixa | 1–2 dias |
| 1 | SQLite, fonte Gupy, filtros, triagem em lote, `revisar` | Média | 3–5 dias |
| 2 | Fonte LinkedIn (alertas por e-mail e página pública), salário | Média | 2–4 dias |
| 3 | Candidatura assistida no LinkedIn (candidatura simplificada) e banco de respostas | Alta | 3–5 dias, mais manutenção |
| 4 | Candidatura assistida na Gupy | Alta | 3–5 dias, mais manutenção |
| — | ATS externos (Workday, Greenhouse, Lever…) | Muito alta | Fora do escopo |

A fase 0 sozinha já entrega a maior parte do ganho por hora investida e valida os prompts antes de qualquer scraping. As fases 3 e 4 valem a pena só se o volume de candidaturas justificar a manutenção.

## 11. Decisões em aberto

1. Envio automático (`--enviar`): fica como opção ou sai do projeto?
2. LinkedIn: só e-mails de alerta, ou também JobSpy ou a página pública?
3. Modelo do currículo: Sonnet 5.5 ou Opus 5.5 (decidir depois do teste com 10 vagas da fase 0).
4. Mesmo repositório (pacote `vagas` com dependências opcionais, como proposto) ou repositório separado que importa o resume-builder?

## Fontes

- [Termos de uso da Gupy para pessoas candidatas](https://www.gupy.io/termos-de-uso-recrutamento-e-selecao-candidatos): condutas proibidas, suspensão de cadastro e uso de IA no ranqueamento.
- [LinkedIn: software e extensões proibidos](https://www.linkedin.com/help/linkedin/answer/a1341387) e [Automated activity on LinkedIn](https://www.linkedin.com/help/linkedin/answer/90586). O User Agreement (§8.2) proíbe bots e métodos automatizados não autorizados.
- [Scrapers públicos da Gupy (Apify)](https://apify.com/parsebird/gupy-io-jobs-scraper): referência sobre a API `portal.api.gupy.io`, que não é documentada.
- [JobSpy (`python-jobspy`)](https://pypi.org/project/python-jobspy/): busca não oficial no LinkedIn, Indeed e Glassdoor.
- Preços da API Claude: [platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing) (valores de nov/2026).
