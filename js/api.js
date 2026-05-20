/**
 * api.js — DeepChat
 * Responsável por toda comunicação com as APIs de IA.
 * Exporta: consultarDeepSeek, consultarOpenAI, cancelarRequest
 */

// =========================================================
// CONFIGURAÇÕES
// =========================================================
const CONFIG = {
  DEEPSEEK_ENDPOINT:    'https://api.deepseek.com/v1/chat/completions',
  OPENAI_ENDPOINT:      'https://api.openai.com/v1/chat/completions',
  DEEPSEEK_MODEL:       'deepseek-chat',
  CHATGPT_MODEL_DEFAULT:'gpt-4o-mini',
  CHATGPT_MODEL_ALT:    'gpt-4o',
  MAX_HISTORICO_CONTEXTO: 10,
  TIMEOUT_MS:           45000,   // 45 segundos
  CANCEL_BTN_DELAY:     10000,   // Mostra botão cancelar após 10s
  MAX_CHARS:            4000,

  // Chaves do localStorage
  LS_DEEPSEEK_KEY: 'ds_api_key',
  LS_CHATGPT_KEY:  'gpt_api_key',
  LS_HISTORICO:    'historico_conversas',
  LS_INVERTED:     'modo_invertido',
  LS_SOUND:        'som_ativo',
  LS_MODEL:        'chatgpt_model',
};

// =========================================================
// PROMPTS
// =========================================================

/**
 * Gera o prompt de revisão crítica.
 * @param {string} pergunta      - Pergunta original do usuário
 * @param {string} resposta      - Resposta da IA a ser revisada
 * @param {string} contexto      - Histórico formatado da conversa
 * @param {string} quemRespondeu - Nome da IA respondente ('DeepSeek' | 'ChatGPT')
 */
const PROMPT_REVISAO = (pergunta, resposta, contexto, quemRespondeu = 'DeepSeek') => `
Atue como revisor crítico especializado em validação de informações.

PERGUNTA ORIGINAL: ${pergunta}

RESPOSTA DO ${quemRespondeu.toUpperCase()} A SER ANALISADA:
${resposta}

CONTEXTO DA CONVERSA:
${contexto}

INSTRUÇÕES DE REVISÃO:
1. Avalie a precisão factual
2. Destaque pontos fortes específicos
3. Aponte imprecisões ou lacunas com detalhes
4. Sugira melhorias concretas
5. Se necessário, forneça versão aprimorada

FORMATO DA RESPOSTA:

✅ PRECISÃO: [texto]

💪 PONTOS FORTES:
• [item 1]
• [item 2]

⚠️ PONTOS A MELHORAR:
• [item 1]
• [item 2]

💡 SUGESTÕES:
[texto]

✨ VERSÃO REVISADA (opcional):
[texto]
`.trim();

// =========================================================
// ESTADO COMPARTILHADO DE API
// =========================================================
let _abortController = null;

/** Retorna o AbortController ativo (para uso externo) */
function getAbortController() { return _abortController; }

// =========================================================
// HELPERS INTERNOS
// =========================================================

/**
 * Cria e registra um AbortController com timeout automático.
 * @returns {{ controller: AbortController, timeoutId: number }}
 */
function _criarAbort() {
  _abortController = new AbortController();
  const timeoutId = setTimeout(
    () => _abortController.abort('timeout'),
    CONFIG.TIMEOUT_MS
  );
  return { controller: _abortController, timeoutId };
}

/** Limpa o AbortController após cada requisição */
function _limparAbort(timeoutId) {
  clearTimeout(timeoutId);
  _abortController = null;
}

/**
 * Trata erros de resposta HTTP e lança erros padronizados.
 * @param {Response} response
 */
async function _verificarResposta(response) {
  if (response.ok) return;
  const err = await response.json().catch(() => ({}));
  const msg = err?.error?.message || `HTTP ${response.status}`;
  if (response.status === 401) throw new Error('CHAVE_INVALIDA:' + msg);
  if (response.status === 429) throw new Error('COTA_EXCEDIDA');
  throw new Error(msg);
}

// =========================================================
// API PÚBLICA
// =========================================================

/**
 * Cancela a requisição em andamento.
 */
function cancelarRequest() {
  if (_abortController) _abortController.abort('cancelado');
}

/**
 * Consulta o DeepSeek com uma pergunta e histórico de contexto.
 *
 * @param {string}      pergunta     - Pergunta do usuário
 * @param {Array}       historico    - Array de mensagens anteriores
 * @param {string}      systemPrompt - Prompt de sistema
 * @param {object|null} anexo        - Objeto de arquivo anexado (opcional)
 * @returns {Promise<string>} Resposta em texto
 */
async function consultarDeepSeek(
  pergunta,
  historico = [],
  systemPrompt = 'Você é um assistente útil, preciso e detalhado. Responda sempre em português.',
  anexo = null
) {
  const mensagensContexto = historico
    .slice(-CONFIG.MAX_HISTORICO_CONTEXTO)
    .map(m => ({
      role: m.sender === 'user' ? 'user' : 'assistant',
      content: m.text
    }));

  // Monta conteúdo com ou sem anexo
  let userContent = anexo ? montarConteudoComAnexo(pergunta, anexo) : pergunta;
  // Simplifica para string se for apenas texto
  if (Array.isArray(userContent) && userContent.length === 1 && userContent[0].type === 'text') {
    userContent = userContent[0].text;
  }

  const body = {
    model: CONFIG.DEEPSEEK_MODEL,
    messages: [
      { role: 'system', content: systemPrompt },
      ...mensagensContexto,
      { role: 'user', content: userContent }
    ],
    temperature: 0.7
  };

  const { controller, timeoutId } = _criarAbort();

  try {
    const response = await fetch(CONFIG.DEEPSEEK_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${STATE.deepseekKey}`
      },
      body: JSON.stringify(body),
      signal: controller.signal
    });

    await _verificarResposta(response);
    const data = await response.json();
    return data.choices?.[0]?.message?.content || '(Sem resposta)';

  } catch (e) {
    if (e.name === 'AbortError' || e.message === 'timeout') throw new Error('TIMEOUT');
    throw e;
  } finally {
    _limparAbort(timeoutId);
  }
}

/**
 * Consulta a API da OpenAI (ChatGPT).
 *
 * @param {Array}  mensagens   - Array de mensagens no formato OpenAI
 * @param {number} temperature - Temperatura de geração (0–1)
 * @returns {Promise<string>} Resposta em texto
 */
async function consultarOpenAI(mensagens, temperature = 0.7) {
  const body = {
    model: STATE.chatgptModel,
    messages: mensagens,
    temperature
  };

  const { controller, timeoutId } = _criarAbort();

  try {
    const response = await fetch(CONFIG.OPENAI_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${STATE.chatgptKey}`
      },
      body: JSON.stringify(body),
      signal: controller.signal
    });

    await _verificarResposta(response);
    const data = await response.json();
    return data.choices?.[0]?.message?.content || '(Sem resposta)';

  } catch (e) {
    if (e.name === 'AbortError' || e.message === 'timeout') throw new Error('TIMEOUT');
    throw e;
  } finally {
    _limparAbort(timeoutId);
  }
}

/**
 * Formata as últimas mensagens do histórico como texto para contexto.
 * @param {Array} historico - Array de mensagens
 * @returns {string}
 */
function gerarContextoFormatado(historico) {
  return historico.slice(-6).map(m => {
    const nome = m.sender === 'user' ? 'Usuário'
      : m.sender === 'deepseek' ? 'DeepSeek' : 'ChatGPT';
    return `${nome}: ${m.text.substring(0, 200)}${m.text.length > 200 ? '...' : ''}`;
  }).join('\n\n');
}
