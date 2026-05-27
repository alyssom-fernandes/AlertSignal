# AlertSignal

**Sistema de monitoramento de vencimentos e alertas automáticos por e-mail.**

O AlertSignal é uma aplicação web local que acompanha alvarás, licenças e documentos regulatórios de empresas — notificando automaticamente os responsáveis antes que os prazos sejam perdidos.

Desenvolvido como substituto real de uma planilha mantida manualmente em um grupo multi-empresas, o AlertSignal introduz alertas automáticos, notificação para múltiplos responsáveis e registro completo de histórico — sem depender de nenhuma infraestrutura em nuvem.

---

## Funcionalidades

- **Alertas automáticos por e-mail** — verificação diária em horário configurável; notificações enviadas com 90, 30 e 7 dias de antecedência, além de lembretes contínuos para documentos já vencidos
- **Múltiplas empresas** — organizadas por categoria (postos, restaurantes, holdings, etc.) com controle de documentos por empresa
- **Múltiplos responsáveis por documento** — cada documento pode ter mais de um responsável, reduzindo o risco de alertas ignorados
- **Edição inline de protocolo** — atualiza o número do protocolo diretamente na tabela, sem navegar para outra tela
- **Histórico completo** — cada notificação enviada e trâmite registrado fica gravado com data e hora
- **Regras configuráveis** — limites de alerta e horário de envio ajustáveis pela interface, sem mexer em código
- **Importação do Excel** — os dados da planilha existente são importados automaticamente na primeira execução
- **Acesso protegido por login** — autenticação por sessão mantém o controle sobre quem acessa o sistema

---

## Tecnologias utilizadas

| Camada | Tecnologia |
|---|---|
| Backend | Python 3 + Flask |
| Banco de dados | SQLite (arquivo único, sem configuração) |
| Agendador | APScheduler |
| E-mail | smtplib + Gmail SMTP com SSL |
| Frontend | Templates Jinja2 + JavaScript puro |
| Fonte | Space Grotesk (Google Fonts) |
| Ícones | Tabler Icons |
| Importação de dados | pandas + openpyxl |

---

## Estrutura do projeto

```
alertsignal/
├── app.py                  # Servidor Flask — rotas e lógica de negócio
├── database.py             # Esquema SQLite e funções de acesso
├── importar_planilha.py    # Importador único do arquivo Excel
├── notificacoes.py         # Lógica de alertas e envio de e-mails
├── INICIAR.bat             # Atalho Windows (duplo clique para rodar)
├── static/
│   ├── img/logo.png
│   └── js/app.js
└── templates/
    ├── base.html           # Estilos globais e variáveis CSS
    ├── layout.html         # Layout com sidebar (herdado pelas páginas internas)
    ├── login.html
    ├── dashboard.html
    ├── empresas.html
    ├── empresa_detalhe.html
    ├── responsaveis.html
    ├── historico.html
    └── configuracoes.html
```

---

## Como rodar

### Requisitos

- Python 3.8 ou superior
- Conexão com internet na primeira execução (para instalar dependências)

### Instalação

1. Baixe e extraia a pasta do projeto
2. Coloque o arquivo `ALVARAS_GRUPO_ZEN.xlsx` dentro da pasta do projeto
3. No Windows, dê duplo clique em `INICIAR.bat`

O script instala as dependências automaticamente, sobe o servidor e abre o navegador.

### Inicialização manual (qualquer sistema operacional)

```bash
pip install flask apscheduler openpyxl pandas werkzeug
python app.py
```

Em seguida, acesse `http://localhost:5000` no navegador.

### Credenciais padrão

```
E-mail: admin@grupozen.com.br
Senha:  zen2024
```

Altere a senha após o primeiro acesso.

---

## Configuração de e-mail

O AlertSignal envia alertas por uma conta Gmail usando uma Senha de App — uma credencial separada gerada pelo Google que não expõe a senha principal da conta.

**Passo a passo:**

1. Acesse [myaccount.google.com](https://myaccount.google.com) → Segurança → Verificação em duas etapas (precisa estar ativada)
2. Procure por **Senhas de app** → crie uma com o nome "AlertSignal"
3. Copie a senha de 16 caracteres gerada
4. No AlertSignal, vá em **Configurações** e preencha o Gmail e a Senha de App
5. Use o botão **Enviar teste** para confirmar que está funcionando

---

## Estrutura do banco de dados

```
usuarios              — usuários do sistema (login)
categorias            — categorias de empresa (Postos, Restaurantes, etc.)
empresas              — empresas com CNPJ e categoria
documentos            — documentos por empresa (tipo, protocolo, vencimento, status)
responsaveis          — pessoas que recebem notificações
documento_responsavel — ligação N:N entre documentos e responsáveis
historico             — log de alertas enviados e trâmites registrados
configuracoes         — armazenamento de configurações em chave/valor
```

---

## Visual

O sistema segue o tema escuro Obsidiana + Vermelho com tipografia Space Grotesk. O fundo próximo ao preto puro (`#080808`) com superfícies em camadas sutis cria profundidade sem poluir a interface. Os cards de status usam o estilo pill horizontal com bordas coloridas por nível de urgência — vermelho para vencido, âmbar para renovar, verde para em dia.

---

## Licença

Uso privado. Desenvolvido para operações internas do Grupo Zen.

---

## Sobre o projeto

Primeiro projeto Python — desenvolvido para resolver um problema operacional real, demonstrando capacidade full-stack: lógica de backend, modelagem de banco de dados, tarefas agendadas e automação de e-mail.
