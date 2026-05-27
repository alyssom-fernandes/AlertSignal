<p align="center">
  <img src="static/img/logo.png" alt="AlertSignal" height="60">
</p>

<p align="center">
  <strong>Sistema de controle de vencimento de documentos e alertas automáticos por e-mail.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Flask-3.0-000000?style=flat&logo=flask&logoColor=white">
  <img src="https://img.shields.io/badge/SQLite-embedded-003B57?style=flat&logo=sqlite&logoColor=white">
  <img src="https://img.shields.io/badge/APScheduler-automatizado-4CAF50?style=flat">
  <img src="https://img.shields.io/badge/licença-privada-red?style=flat">
</p>

---

AlertSignal é uma aplicação web local que rastreia licenças, alvarás e documentos regulatórios de empresas — notificando automaticamente os responsáveis antes que os prazos sejam perdidos.

Construído como substituto real de uma planilha mantida manualmente, o AlertSignal introduz alertas automáticos, notificação para múltiplos responsáveis e trilha de auditoria completa, sem necessidade de infraestrutura em nuvem.

---

## Screenshots

<p align="center">
  <img src="docs/screenshots/login.png" alt="Login" width="700">
</p>
<p align="center"><em>Tela de login</em></p>

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="Dashboard" width="700">
</p>
<p align="center"><em>Dashboard — visão geral de status e documentos urgentes</em></p>

<p align="center">
  <img src="docs/screenshots/empresas.png" alt="Empresas" width="700">
</p>
<p align="center"><em>Empresas — organizadas por categoria com indicadores de status</em></p>

<p align="center">
  <img src="docs/screenshots/empresa_detalhe.png" alt="Detalhe da empresa" width="700">
</p>
<p align="center"><em>Detalhe da empresa — tabela de documentos com rastreamento de vencimento</em></p>

<p align="center">
  <img src="docs/screenshots/historico.png" alt="Histórico" width="700">
</p>
<p align="center"><em>Histórico — registro completo de alertas e trâmites</em></p>

---

## Funcionalidades

- **Alertas automáticos por e-mail** — verificação diária em horário configurável; notificações disparadas com 90, 30 e 7 dias antes do vencimento, além de lembretes contínuos para documentos já vencidos
- **Suporte a múltiplas empresas** — empresas organizadas por categoria com rastreamento de documentos individual
- **Múltiplos responsáveis por documento** — cada documento pode ter mais de um responsável, reduzindo o risco de alertas perdidos
- **Edição inline de protocolo** — atualiza o número do protocolo diretamente na tabela, sem sair da página
- **Histórico completo** — cada notificação enviada e trâmite registrado fica gravado com data e hora
- **Regras configuráveis** — limites de alerta e horário de envio ajustáveis pela interface, sem alterar código
- **Exportação para Excel** — exporta todos os documentos em `.xlsx` formatado com status colorido
- **Acesso protegido por login** — autenticação por sessão com níveis admin e visualizador
- **Sidebar recolhível** — layout responsivo que funciona em qualquer tamanho de tela

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python 3 + Flask |
| Banco de dados | SQLite (arquivo único, zero configuração) |
| Agendador | APScheduler |
| E-mail | smtplib + Gmail SMTP over SSL |
| Frontend | Jinja2 templates + vanilla JS |
| Fontes | Plus Jakarta Sans + JetBrains Mono |
| Ícones | Tabler Icons |
| Importação | pandas + openpyxl |

---

## Decisões técnicas

**SQLite em vez de PostgreSQL** — aplicação local, máquina única, sem escritas concorrentes. SQLite significa zero configuração, um único arquivo para fazer backup e nenhum servidor para manter. A ferramenta certa para o caso de uso.

**APScheduler em vez de cron** — roda dentro do processo Flask, funciona em qualquer plataforma incluindo Windows, e permite configurar o horário de envio pela interface sem tocar no servidor.

**Sem ORM** — SQL direto com queries parametrizadas mantém o código simples e explícito. Com um schema desse tamanho, um ORM adicionaria abstração sem agregar valor.

**Vanilla JS sem framework** — os requisitos de interatividade (modais, edição inline, notificações toast) são modestos o suficiente para não justificar um framework. O resultado é um frontend sem dependências externas.

---

## Estrutura do projeto

```
alertsignal/
├── app.py                  # Servidor Flask — todas as rotas e lógica de negócio
├── database.py             # Schema SQLite e helpers de conexão
├── importar_planilha.py    # Importador Excel (execução única)
├── notificacoes.py         # Lógica de alertas e envio de e-mails
├── demo_seed.py            # Populador de dados fictícios para demo
├── requirements.txt        # Dependências Python
├── .env                    # Variáveis de ambiente (não commitado)
├── INICIAR.bat             # Launcher Windows
├── static/
│   ├── img/                # Logo e OG image
│   ├── js/app.js
│   └── favicon/            # Pacote de favicons
├── docs/
│   └── screenshots/        # Screenshots da interface
└── templates/
    ├── base.html           # Estilos globais e variáveis CSS
    ├── layout.html         # Layout com sidebar recolhível
    ├── login.html
    ├── dashboard.html
    ├── empresas.html
    ├── empresa_detalhe.html
    ├── cadastros.html
    ├── responsaveis.html
    ├── historico.html
    ├── configuracoes.html
    ├── perfil.html
    └── usuarios.html
```

---

## Como rodar

### Requisitos

- Python 3.8 ou superior
- Conexão com internet na primeira execução (para instalar dependências)

### Instalação

1. Clone o repositório
2. Crie um arquivo `.env` na raiz do projeto:
   ```
   SECRET_KEY=sua-chave-secreta-longa-aqui
   ```
3. No Windows, dê duplo clique em `INICIAR.bat`

O launcher instala todas as dependências, sobe o servidor e abre o navegador automaticamente.

### Execução manual (qualquer SO)

```bash
pip install -r requirements.txt
python app.py
```

Acesse `http://localhost:5000` no navegador.

### Credenciais da demo

O repositório inclui um banco de dados pré-populado com dados fictícios:

```
E-mail:  admin@alertsignal.com
Senha:   demo2024
```

Para resetar e recriar os dados demo:

```bash
python demo_seed.py --reset
```

---

## Configuração de e-mail

O AlertSignal envia alertas através de uma conta Gmail usando uma Senha de App.

1. Acesse [myaccount.google.com](https://myaccount.google.com) → Segurança → Verificação em duas etapas
2. Procure **Senhas de app** → crie uma chamada "AlertSignal"
3. Copie a senha de 16 caracteres
4. No AlertSignal, acesse **Configurações** e preencha o e-mail e a Senha de App
5. Use **Enviar teste** para verificar

---

## Schema do banco de dados

```
usuarios              — usuários do sistema (login)
categorias            — categorias de empresas
empresas              — empresas com CNPJ e categoria
documentos            — documentos por empresa (tipo, protocolo, vencimento, status)
responsaveis          — pessoas que recebem notificações
documento_responsavel — vínculo N:N entre documentos e responsáveis
historico             — registro de alertas enviados e trâmites
configuracoes         — configurações em chave/valor
```

---

## Limitações conhecidas

- Sem proteção CSRF nos formulários — aceitável para aplicação local protegida por login; adicionaria Flask-WTF antes de qualquer deploy público
- Senha de App armazenada em texto puro no banco — usaria `cryptography.fernet` para uso em produção

---

## Autor

Desenvolvido por **Alyssom Fernandes** — primeiro projeto Python, construído para resolver um problema operacional real e demonstrar capacidade full-stack em lógica de backend, modelagem de banco de dados, tarefas agendadas e automação de e-mail.
