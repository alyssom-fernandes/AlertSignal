# DeepChat — Chat com Validação Cruzada de IAs

Uma interface de chat que consulta o **DeepSeek** para obter respostas e usa o **ChatGPT como revisor crítico** — sem backend, sem servidor, sem instalação.

A ideia é direta: em vez de confiar em um único modelo de IA, cada resposta passa por um segundo modelo que avalia a precisão, aponta pontos fortes, identifica lacunas e sugere melhorias.

---

## Como funciona

Ao enviar uma mensagem:

1. O DeepSeek gera uma resposta detalhada
2. O ChatGPT recebe tanto a pergunta quanto a resposta do DeepSeek e produz uma revisão crítica estruturada, cobrindo precisão factual, pontos positivos, áreas a melhorar e uma versão revisada quando necessário

Há também um **modo invertido**, em que o ChatGPT responde primeiro e o DeepSeek atua como revisor.

---

## Como usar

Você precisará de chaves de API de ambas as plataformas. As duas oferecem planos gratuitos adequados para testes.

**DeepSeek**
1. Crie uma conta em [platform.deepseek.com](https://platform.deepseek.com)
2. Acesse **API Keys** e gere uma nova chave

**OpenAI**
1. Crie uma conta em [platform.openai.com](https://platform.openai.com)
2. Acesse **API Keys** e gere uma nova chave secreta

Com as duas chaves em mãos, abra o `index.html` no navegador ou acesse a demo, insira suas credenciais e comece a conversar.

Sem etapa de build, sem gerenciador de pacotes, sem dependências.

---

## Privacidade

Todas as credenciais são armazenadas exclusivamente no `localStorage` do seu navegador. Nenhum dado é enviado para qualquer servidor além das próprias APIs do DeepSeek e da OpenAI. A aplicação não possui analytics, telemetria ou requisições externas além das chamadas de IA que você explicitamente dispara.

> Atenção: se você compartilha o dispositivo ou perfil de navegador com outras pessoas, limpe o localStorage antes de fazê-lo.

---

## Funcionalidades

- Validação por dois modelos com formato de revisão estruturado
- Modo invertido (ChatGPT responde, DeepSeek revisa)
- Histórico de conversas salvo localmente com busca
- Exportação da conversa em Markdown
- Anexo de arquivos: imagens, texto puro, CSV, Markdown (até 5 MB)
- Regeneração de respostas sem reiniciar a conversa
- Resposta a mensagens específicas
- Seletor de modelo (GPT-4o-mini / GPT-4o)
- Cancelamento de requisições com controle de timeout
- Detecção de ausência de conexão
- Interface adaptada para mobile com menu de contexto por pressão longa

---

## Estrutura do projeto

```
deepchat/
├── index.html        # Marcação e layout
├── css/
│   └── style.css     # Todos os estilos
└── js/
    ├── api.js        # Comunicação com as APIs (DeepSeek e OpenAI)
    └── app.js        # Lógica da aplicação, estado e interface
```

Desenvolvido com HTML, CSS e JavaScript puro. Sem frameworks, sem dependências.

---

## Custo estimado por conversa

| Modelo | Custo por pergunta + revisão |
|---|---|
| GPT-4o-mini (padrão) | ~$0,001 |
| GPT-4o | ~$0,005 |
| DeepSeek | ~$0,0001 |

Valores aproximados. Consulte os preços atuais em cada plataforma.

---

## Próximos passos

- Respostas em streaming
- Suporte a modelos adicionais (Claude, Gemini)
- Tema claro
- Suporte a PWA

---

## Licença

MIT
