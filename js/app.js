/**
 * app.js — DeepChat
 * Lógica principal: estado, renderização, fluxo de respostas,
 * eventos de UI, histórico, exportação e anexos.
 */

// =========================================================
// ESTADO GLOBAL
// =========================================================
const STATE = {
  deepseekKey:           '',
  chatgptKey:            '',
  chatgptModel:          CONFIG.CHATGPT_MODEL_DEFAULT,
  mensagens:             [],
  ultimaPergunta:        '',
  modoInvertido:         false,
  somAtivo:              true,
  replyingTo:            null,   // { sender, text, id }
  contextTarget:         null,   // { id, sender }
  cancelTimer:           null,
  pendingRepeatCallback: null,
  conversaAtual: {
    id:        Date.now().toString(),
    data:      new Date().toISOString(),
    titulo:    'Nova conversa',
    mensagens: []
  }
};

// =========================================================
// DOM HELPERS
// =========================================================
const DOM = {
  loginScreen:    () => document.getElementById('loginScreen'),
  chatScreen:     () => document.getElementById('chatScreen'),
  deepseekKey:    () => document.getElementById('deepseekKey'),
  chatgptKey:     () => document.getElementById('chatgptKey'),
  saveKeys:       () => document.getElementById('saveKeys'),
  btnEnter:       () => document.getElementById('btnEnter'),
  loginError:     () => document.getElementById('loginError'),
  messagesArea:   () => document.getElementById('messagesArea'),
  typingArea:     () => document.getElementById('typingArea'),
  messageInput:   () => document.getElementById('messageInput'),
  btnSend:        () => document.getElementById('btnSend'),
  charCounter:    () => document.getElementById('charCounter'),
  groupStatus:    () => document.getElementById('groupStatus'),
  replyBar:       () => document.getElementById('replyBar'),
  replyBarLabel:  () => document.getElementById('replyBarLabel'),
  replyBarText:   () => document.getElementById('replyBarText'),
  dropdownMenu:   () => document.getElementById('dropdownMenu'),
  cancelBtn:      () => document.getElementById('cancelBtn'),
  repeatToast:    () => document.getElementById('repeatToast'),
  offlineBanner:  () => document.getElementById('offlineBanner'),
  soundToggle:    () => document.getElementById('soundToggle'),
  modelBadge:     () => document.getElementById('modelBadge'),
  invertedBadge:  () => document.getElementById('invertedBadge'),
  btnInverter:    () => document.getElementById('btnInverter'),
  contextMenu:    () => document.getElementById('contextMenu'),
  historicoModal: () => document.getElementById('historicoModal'),
  historicoLista: () => document.getElementById('historicoLista'),
};

// =========================================================
// ARMAZENAMENTO (localStorage)
// =========================================================

function salvarChaves() {
  if (DOM.saveKeys().checked) {
    localStorage.setItem(CONFIG.LS_DEEPSEEK_KEY, STATE.deepseekKey);
    localStorage.setItem(CONFIG.LS_CHATGPT_KEY,  STATE.chatgptKey);
  }
}

function carregarChavesSalvas() {
  const ds  = localStorage.getItem(CONFIG.LS_DEEPSEEK_KEY);
  const gpt = localStorage.getItem(CONFIG.LS_CHATGPT_KEY);
  if (ds)       DOM.deepseekKey().value = ds;
  if (gpt)      DOM.chatgptKey().value  = gpt;
  if (ds || gpt) DOM.saveKeys().checked = true;
  atualizarBtnEnter();
}

function salvarNoHistorico() {
  const historico = carregarHistorico();
  const primeira  = STATE.mensagens.find(m => m.sender === 'user');
  if (primeira) {
    STATE.conversaAtual.titulo = primeira.text.substring(0, 60) +
      (primeira.text.length > 60 ? '...' : '');
  }
  STATE.conversaAtual.mensagens = [...STATE.mensagens];
  const idx = historico.findIndex(h => h.id === STATE.conversaAtual.id);
  if (idx >= 0) historico[idx] = STATE.conversaAtual;
  else          historico.unshift(STATE.conversaAtual);
  localStorage.setItem(CONFIG.LS_HISTORICO, JSON.stringify(historico.slice(0, 50)));
}

function carregarHistorico() {
  try { return JSON.parse(localStorage.getItem(CONFIG.LS_HISTORICO) || '[]'); }
  catch { return []; }
}

function deletarDoHistorico(id) {
  const h = carregarHistorico().filter(c => c.id !== id);
  localStorage.setItem(CONFIG.LS_HISTORICO, JSON.stringify(h));
}

function salvarPreferencias() {
  localStorage.setItem(CONFIG.LS_INVERTED, STATE.modoInvertido ? '1' : '0');
  localStorage.setItem(CONFIG.LS_SOUND,    STATE.somAtivo      ? '1' : '0');
  localStorage.setItem(CONFIG.LS_MODEL,    STATE.chatgptModel);
}

function carregarPreferencias() {
  STATE.modoInvertido = localStorage.getItem(CONFIG.LS_INVERTED) === '1';
  STATE.somAtivo      = localStorage.getItem(CONFIG.LS_SOUND)    !== '0';
  const model = localStorage.getItem(CONFIG.LS_MODEL);
  if (model) STATE.chatgptModel = model;
}

// =========================================================
// RENDERIZAÇÃO — UTILITÁRIOS
// =========================================================

/** Converte Markdown básico em HTML seguro */
function renderMarkdown(text) {
  if (!text) return '';
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/```(\w*)\n?([\s\S]*?)```/g, (_, _l, code) => `<pre><code>${code.trim()}</code></pre>`)
    .replace(/`([^`]+)`/g,             '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g,       '<strong>$1</strong>')
    .replace(/__([^_]+)__/g,           '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g,           '<em>$1</em>')
    .replace(/_([^_]+)_/g,             '<em>$1</em>')
    .replace(/^### (.+)$/gm,           '<h3>$1</h3>')
    .replace(/^## (.+)$/gm,            '<h2>$1</h2>')
    .replace(/^# (.+)$/gm,             '<h1>$1</h1>')
    .replace(/^&gt; (.+)$/gm,          '<blockquote>$1</blockquote>')
    .replace(/^---$/gm,                '<hr>')
    .replace(/^[•\-\*] (.+)$/gm,       '<li>$1</li>')
    .replace(/^\d+\. (.+)$/gm,         '<li>$1</li>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/(<li>.*<\/li>\n?)+/g,    m => `<ul>${m}</ul>`)
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g,   '<br>');
  if (!html.trim().startsWith('<')) html = `<p>${html}</p>`;
  return html;
}

function getHoraAtual() {
  return new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

function gerarId() {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
}

// =========================================================
// RENDERIZAÇÃO — MENSAGENS
// =========================================================

const SVG_DEEPSEEK = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12 C4 6, 8 4, 12 4 C16 4, 20 7, 22 12"/><path d="M2 12 C4 16, 8 18, 12 18"/><path d="M12 18 L14 22 L16 18"/><path d="M18 8 L20 4 L22 8"/><circle cx="8" cy="10" r="1" fill="currentColor"/></svg>`;
const SVG_CHATGPT  = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 8V5"/><circle cx="12" cy="4" r="1" fill="currentColor"/><rect x="8" y="12" width="3" height="3" rx="0.5"/><rect x="13" y="12" width="3" height="3" rx="0.5"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/></svg>`;
const SVG_USER     = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
const SVG_CHECKS   = `<svg width="16" height="10" viewBox="0 0 20 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1,6 5,10 13,2"/><polyline points="7,10 15,2"/></svg>`;

function adicionarMensagemUsuario(texto, replyTo = null, anexo = null) {
  const hora = getHoraAtual();
  const id   = gerarId();

  const replyHtml = replyTo ? `
    <div class="reply-preview-in-bubble">
      <div class="reply-sender">${replyTo.sender}</div>
      <div class="reply-text">${replyTo.text.substring(0, 80)}${replyTo.text.length > 80 ? '...' : ''}</div>
    </div>` : '';

  const anexoHtml = anexo ? gerarHtmlAnexo(anexo) : '';

  const wrapper = document.createElement('div');
  wrapper.className = 'message-wrapper user';
  wrapper.dataset.id     = id;
  wrapper.dataset.sender = 'user';
  wrapper.dataset.text   = texto;

  wrapper.innerHTML = `
    <div class="msg-header">
      <span class="msg-sender" style="color:#8b8b9e">Você</span>
      <span style="display:flex;align-items:center;color:rgba(255,255,255,0.5)">${SVG_USER}</span>
    </div>
    <div class="bubble" oncontextmenu="abrirContextMenu(event,'${id}','user')" onclick="onBubbleClick(event,'${id}','user')">
      ${replyHtml}${anexoHtml}
      <div class="bubble-content">${renderMarkdown(texto)}</div>
      <span class="msg-time">${hora}</span>
      <span class="msg-checks">${SVG_CHECKS}</span>
    </div>`;

  DOM.messagesArea().appendChild(wrapper);
  scrollParaBaixo();
  STATE.mensagens.push({ id, sender: 'user', text: texto, hora, replyTo });
  return id;
}

function adicionarMensagemIA(sender, texto, regenFor = null) {
  const hora       = getHoraAtual();
  const id         = gerarId();
  const isDeepSeek = sender === 'deepseek';
  const isInv      = STATE.modoInvertido;

  const avatar      = isDeepSeek ? SVG_DEEPSEEK : SVG_CHATGPT;
  const nome        = isDeepSeek ? (isInv ? 'DeepSeek Revisor' : 'DeepSeek') : (isInv ? 'ChatGPT' : 'ChatGPT Revisor');
  const cssClass    = isDeepSeek ? 'deepseek-msg' : 'chatgpt-msg';
  const senderClass = isDeepSeek ? 'deepseek'     : 'chatgpt';

  const mostrarBtn  = (!isInv && isDeepSeek) || (isInv && !isDeepSeek);
  const btnNova     = mostrarBtn
    ? `<div class="bubble-actions"><button class="btn-new-response" onclick="pedirNovaResposta('${id}')">↺ Nova resposta</button></div>`
    : '';

  const wrapper = document.createElement('div');
  wrapper.className      = `message-wrapper ai ${cssClass}`;
  wrapper.dataset.id     = id;
  wrapper.dataset.sender = sender;
  wrapper.dataset.text   = texto;
  if (regenFor) wrapper.dataset.regenFor = regenFor;

  wrapper.innerHTML = `
    <div class="msg-header">
      <div class="msg-avatar-circle ${senderClass}">${avatar}</div>
      <span class="msg-sender ${senderClass}">${nome}</span>
      <span style="font-size:11px;color:var(--text-secondary)">${hora}</span>
    </div>
    <div class="bubble" oncontextmenu="abrirContextMenu(event,'${id}','${sender}')" onclick="onBubbleClick(event,'${id}','${sender}')">
      <div class="bubble-content">${renderMarkdown(texto)}</div>
      <span class="msg-time">${hora}</span>
      ${btnNova}
    </div>`;

  DOM.messagesArea().appendChild(wrapper);
  scrollParaBaixo();
  if (STATE.somAtivo) tocarSom();
  STATE.mensagens.push({ id, sender, text: texto, hora });
  return id;
}

function adicionarMensagemErro(titulo, detalhe, permiteRelogin = false) {
  const actions = permiteRelogin
    ? `<div class="error-action"><button class="btn-error-action" onclick="irParaConfig()">Verificar chave da API</button></div>`
    : '';
  const div = document.createElement('div');
  div.className = 'error-message';
  div.innerHTML = `<strong>⚠ ${titulo}</strong><br><span style="font-size:12px;opacity:0.8">${detalhe}</span>${actions}`;
  DOM.messagesArea().appendChild(div);
  scrollParaBaixo();
}

function adicionarMensagemSistema(texto) {
  const div = document.createElement('div');
  div.className = 'date-divider';
  div.innerHTML = `<span style="font-size:12px">${texto}</span>`;
  DOM.messagesArea().appendChild(div);
  scrollParaBaixo();
}

// =========================================================
// INDICADOR "DIGITANDO..."
// =========================================================

function mostrarDigitando(who) {
  esconderDigitando();
  const isDS  = who === 'deepseek';
  const avatar = isDS ? SVG_DEEPSEEK : SVG_CHATGPT;
  const nome   = isDS
    ? (STATE.modoInvertido ? 'DeepSeek Revisor' : 'DeepSeek')
    : (STATE.modoInvertido ? 'ChatGPT' : 'ChatGPT Revisor');
  const cor = isDS ? '#64b5f6' : '#a78bfa';

  const div = document.createElement('div');
  div.className = 'typing-indicator';
  div.id        = 'typingIndicator';
  div.innerHTML = `
    <span style="display:flex;align-items:center;color:${cor}">${avatar}</span>
    <div>
      <span class="ti-name" style="color:${cor}">${nome} está digitando...</span>
      <div class="typing-dots"><span></span><span></span><span></span></div>
    </div>`;

  DOM.typingArea().appendChild(div);
  atualizarStatus(`${nome} está digitando...`, true);
  scrollParaBaixo();
}

function esconderDigitando() {
  document.getElementById('typingIndicator')?.remove();
  atualizarStatus(
    STATE.modoInvertido ? 'ChatGPT + DeepSeek Revisor' : 'DeepSeek + ChatGPT Revisor',
    false
  );
}

function scrollParaBaixo() {
  requestAnimationFrame(() => { DOM.messagesArea().scrollTop = DOM.messagesArea().scrollHeight; });
}

function atualizarStatus(texto, isTyping = false) {
  const el = DOM.groupStatus();
  if (!el) return;
  el.textContent = texto;
  el.className   = 'group-status' + (isTyping ? ' typing' : '');
}

function mostrarCancelBtn() { DOM.cancelBtn().classList.add('visible'); }
function ocultarCancelBtn()  {
  DOM.cancelBtn().classList.remove('visible');
  if (STATE.cancelTimer) { clearTimeout(STATE.cancelTimer); STATE.cancelTimer = null; }
}

function tocarSom() {
  try {
    const ctx  = new (window.AudioContext || window.webkitAudioContext)();
    const osc  = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain); gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(660, ctx.currentTime + 0.1);
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.3);
  } catch (_) {}
}

// =========================================================
// FLUXO PRINCIPAL DE RESPOSTA
// =========================================================

async function processarFluxoCompleto(pergunta, replyTo = null, anexo = null) {
  bloqueiarInput(true);
  STATE.cancelTimer = setTimeout(mostrarCancelBtn, CONFIG.CANCEL_BTN_DELAY);

  try {
    if (STATE.modoInvertido) await fluxoInvertido(pergunta, anexo);
    else                     await fluxoNormal(pergunta, replyTo, anexo);
    salvarNoHistorico();
  } catch (e) {
    esconderDigitando();
    tratarErro(e, 'Geral');
  } finally {
    bloqueiarInput(false);
    ocultarCancelBtn();
    esconderDigitando();
  }
}

/** Modo normal: DeepSeek responde → ChatGPT revisa */
async function fluxoNormal(pergunta, replyTo, anexo) {
  mostrarDigitando('deepseek');
  let respostaDS;
  try {
    respostaDS = await consultarDeepSeek(
      pergunta,
      STATE.mensagens.filter(m => m.sender !== 'chatgpt'),
      'Você é um assistente útil, preciso e detalhado. Responda sempre em português.',
      anexo
    );
  } catch (e) { esconderDigitando(); tratarErro(e, 'DeepSeek'); return; }
  esconderDigitando();
  adicionarMensagemIA('deepseek', respostaDS);

  mostrarDigitando('chatgpt');
  let revisao;
  try {
    revisao = await consultarOpenAI([
      { role: 'system', content: 'Você é um revisor crítico especializado. Seja preciso, imparcial e construtivo. Responda em português.' },
      { role: 'user',   content: PROMPT_REVISAO(pergunta, respostaDS, gerarContextoFormatado(STATE.mensagens), 'DeepSeek') }
    ], 0.5);
  } catch (e) { esconderDigitando(); tratarErro(e, 'ChatGPT Revisor'); return; }
  esconderDigitando();
  adicionarMensagemIA('chatgpt', revisao);
}

/** Modo invertido: ChatGPT responde → DeepSeek revisa */
async function fluxoInvertido(pergunta, anexo) {
  mostrarDigitando('chatgpt');
  let respostaGPT;
  try {
    respostaGPT = await consultarOpenAI([
      { role: 'system', content: 'Você é um assistente útil, preciso e detalhado. Responda sempre em português.' },
      ...STATE.mensagens.slice(-CONFIG.MAX_HISTORICO_CONTEXTO).map(m => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text
      })),
      { role: 'user', content: pergunta }
    ], 0.7);
  } catch (e) { esconderDigitando(); tratarErro(e, 'ChatGPT'); return; }
  esconderDigitando();
  adicionarMensagemIA('chatgpt', respostaGPT);

  mostrarDigitando('deepseek');
  let revisao;
  try {
    revisao = await consultarDeepSeek(
      PROMPT_REVISAO(pergunta, respostaGPT, gerarContextoFormatado(STATE.mensagens), 'ChatGPT'),
      [],
      'Você é um revisor crítico especializado. Responda em português.'
    );
  } catch (e) { esconderDigitando(); tratarErro(e, 'DeepSeek Revisor'); return; }
  esconderDigitando();
  adicionarMensagemIA('deepseek', revisao);
}

/** Trata erros de API com mensagens amigáveis */
function tratarErro(erro, origem) {
  const msg = erro.message || 'Erro desconhecido';
  if (msg.startsWith('CHAVE_INVALIDA:')) {
    adicionarMensagemErro(`Chave inválida — ${origem}`, 'Chave API inválida ou expirada. Verifique nas configurações.', true);
    return;
  }
  if (msg === 'TIMEOUT') {
    adicionarMensagemErro(`Tempo limite — ${origem}`, 'A requisição demorou mais de 45 segundos. Tente novamente.');
    return;
  }
  if (msg === 'COTA_EXCEDIDA') {
    adicionarMensagemErro(`Cota excedida — ${origem}`, 'Limite de uso da API atingido. Verifique seu plano ou aguarde.', true);
    return;
  }
  if (msg.includes('cancelado') || msg.includes('AbortError')) return;
  if (!navigator.onLine) {
    adicionarMensagemErro('Sem conexão', 'Verifique sua internet e tente novamente.');
    return;
  }
  adicionarMensagemErro(`Erro — ${origem}`, msg.length > 150 ? msg.substring(0, 150) + '...' : msg);
}

function bloqueiarInput(bloquear) {
  DOM.messageInput().disabled = bloquear;
  DOM.btnSend().disabled      = bloquear || !DOM.messageInput().value.trim();
  if (!bloquear) DOM.messageInput().focus();
}

// =========================================================
// NOVA RESPOSTA (regenerar)
// =========================================================

async function pedirNovaResposta(msgId) {
  const idx = STATE.mensagens.findIndex(m => m.id === msgId);
  if (idx < 0) return;
  const pergunta = STATE.mensagens.slice(0, idx).reverse().find(m => m.sender === 'user');
  if (!pergunta) return;

  bloqueiarInput(true);
  STATE.cancelTimer = setTimeout(mostrarCancelBtn, CONFIG.CANCEL_BTN_DELAY);

  try {
    if (!STATE.modoInvertido) {
      mostrarDigitando('deepseek');
      const nova = await consultarDeepSeek(
        pergunta.text + '\n\n[Gere uma resposta alternativa e diferente]',
        STATE.mensagens.slice(0, idx).filter(m => m.sender !== 'chatgpt')
      );
      esconderDigitando();
      adicionarMensagemIA('deepseek', nova, msgId);
      mostrarDigitando('chatgpt');
      const rev = await consultarOpenAI([
        { role: 'system', content: 'Você é um revisor crítico. Responda em português.' },
        { role: 'user', content: PROMPT_REVISAO(pergunta.text, nova, gerarContextoFormatado(STATE.mensagens), 'DeepSeek') }
      ], 0.5);
      esconderDigitando();
      adicionarMensagemIA('chatgpt', rev);
    } else {
      mostrarDigitando('chatgpt');
      const nova = await consultarOpenAI([
        { role: 'system', content: 'Você é um assistente útil. Responda em português com uma resposta alternativa.' },
        { role: 'user', content: pergunta.text }
      ], 0.9);
      esconderDigitando();
      adicionarMensagemIA('chatgpt', nova, msgId);
      mostrarDigitando('deepseek');
      const rev = await consultarDeepSeek(
        PROMPT_REVISAO(pergunta.text, nova, gerarContextoFormatado(STATE.mensagens), 'ChatGPT'),
        [],
        'Você é um revisor crítico. Responda em português.'
      );
      esconderDigitando();
      adicionarMensagemIA('deepseek', rev);
    }
    salvarNoHistorico();
  } catch (e) {
    esconderDigitando(); tratarErro(e, 'Nova resposta');
  } finally {
    bloqueiarInput(false); ocultarCancelBtn();
  }
}

// =========================================================
// EVENTOS DE INPUT
// =========================================================

function onInputChange() {
  const input = DOM.messageInput();
  const len   = input.value.length;
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 96) + 'px';
  const counter = DOM.charCounter();
  counter.textContent = `${len}/${CONFIG.MAX_CHARS}`;
  counter.className   = 'char-counter' + (len > 3800 ? ' limit' : len > 3500 ? ' warning' : '');
  DOM.btnSend().disabled = len === 0 || input.disabled;
}

function onKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!DOM.btnSend().disabled) enviarMensagem();
  }
}

function enviarMensagem() {
  const texto = DOM.messageInput().value.trim();
  if (!texto) return;
  const replyTo = STATE.replyingTo ? { ...STATE.replyingTo } : null;

  if (texto.toLowerCase() === STATE.ultimaPergunta.toLowerCase() && STATE.ultimaPergunta) {
    STATE.pendingRepeatCallback = () => finalizarEnvio(texto, replyTo);
    mostrarToastRepetida();
    return;
  }
  finalizarEnvio(texto, replyTo);
}

function finalizarEnvio(texto, replyTo) {
  const anexo = anexoAtual ? { ...anexoAtual } : null;
  adicionarMensagemUsuario(texto, replyTo, anexo);
  STATE.ultimaPergunta = texto;
  cancelarResposta();
  removerAnexo();
  DOM.messageInput().value = '';
  DOM.messageInput().style.height = 'auto';
  onInputChange();
  processarFluxoCompleto(texto, replyTo, anexo);
}

// =========================================================
// CONTEXT MENU
// =========================================================

function abrirContextMenu(e, msgId, sender) {
  e.preventDefault(); e.stopPropagation();
  STATE.contextTarget = { id: msgId, sender };
  const ctxNova = document.getElementById('ctxNovaResposta');
  ctxNova.style.display = ((!STATE.modoInvertido && sender === 'deepseek') || (STATE.modoInvertido && sender === 'chatgpt'))
    ? 'flex' : 'none';
  const menu = DOM.contextMenu();
  menu.style.left = Math.min(e.clientX, window.innerWidth  - 170) + 'px';
  menu.style.top  = Math.min(e.clientY, window.innerHeight - 120) + 'px';
  menu.classList.add('open');
}

function onBubbleClick() { fecharContextMenu(); fecharDropdown(); }

function contextResponder() {
  if (!STATE.contextTarget) return;
  const el = document.querySelector(`[data-id="${STATE.contextTarget.id}"]`);
  if (!el) { fecharContextMenu(); return; }
  const nomes = { user: 'Você', deepseek: 'DeepSeek', chatgpt: 'ChatGPT Revisor' };
  STATE.replyingTo = { id: STATE.contextTarget.id, sender: nomes[el.dataset.sender] || 'IA', text: el.dataset.text || '' };
  DOM.replyBarLabel().textContent = `Respondendo a ${STATE.replyingTo.sender}`;
  DOM.replyBarText().textContent  = STATE.replyingTo.text.substring(0, 100);
  DOM.replyBar().classList.add('visible');
  DOM.messageInput().focus();
  fecharContextMenu();
}

function contextNovaResposta() {
  if (!STATE.contextTarget) { fecharContextMenu(); return; }
  pedirNovaResposta(STATE.contextTarget.id);
  fecharContextMenu();
}

function contextCopiar() {
  if (!STATE.contextTarget) return;
  const el = document.querySelector(`[data-id="${STATE.contextTarget.id}"]`);
  if (el) navigator.clipboard.writeText(el.dataset.text || '').catch(() => {});
  fecharContextMenu();
}

function fecharContextMenu() { DOM.contextMenu().classList.remove('open'); STATE.contextTarget = null; }
function cancelarResposta()   { STATE.replyingTo = null; DOM.replyBar().classList.remove('visible'); }

// =========================================================
// UI — LOGIN, MENU, MODAIS
// =========================================================

function toggleEye(fieldId, btn) {
  const field = document.getElementById(fieldId);
  const isHidden = field.type === 'password';
  field.type  = isHidden ? 'text' : 'password';
  btn.innerHTML = isHidden
    ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`
    : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
}

function toggleInstructions() {
  document.getElementById('instructionsToggle').classList.toggle('open');
  document.getElementById('instructionsCard').classList.toggle('open');
}

function atualizarBtnEnter() {
  DOM.btnEnter().disabled = !(DOM.deepseekKey().value.trim() && DOM.chatgptKey().value.trim());
}

document.getElementById('deepseekKey').addEventListener('input', atualizarBtnEnter);
document.getElementById('chatgptKey').addEventListener('input',  atualizarBtnEnter);

function entrarNoGrupo() {
  const ds  = DOM.deepseekKey().value.trim();
  const gpt = DOM.chatgptKey().value.trim();
  const err = DOM.loginError();

  if (!ds || !gpt)     { err.textContent = 'Preencha ambas as chaves antes de continuar.'; err.classList.add('visible'); return; }
  if (ds.length  < 10) { err.textContent = 'A chave do DeepSeek parece inválida.';          err.classList.add('visible'); return; }
  if (gpt.length < 10) { err.textContent = 'A chave do ChatGPT parece inválida.';           err.classList.add('visible'); return; }

  err.classList.remove('visible');
  STATE.deepseekKey = ds;
  STATE.chatgptKey  = gpt;
  salvarChaves();
  DOM.loginScreen().classList.add('hidden');
  DOM.chatScreen().classList.remove('hidden');
  inicializarChat();
}

function irParaConfig() {
  fecharDropdown();
  DOM.chatScreen().classList.add('hidden');
  DOM.loginScreen().classList.remove('hidden');
}

function toggleMenu()    { DOM.dropdownMenu().classList.toggle('open'); }
function fecharDropdown() { DOM.dropdownMenu().classList.remove('open'); }

function toggleSound() {
  STATE.somAtivo = !STATE.somAtivo;
  const btn = DOM.soundToggle();
  btn.innerHTML = STATE.somAtivo
    ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`
    : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13.73 21a2 2 0 0 1-3.46 0"/><path d="M18.63 13A17.89 17.89 0 0 1 18 8"/><path d="M6.26 6.26A5.86 5.86 0 0 0 6 8c0 7-3 9-3 9h14"/><path d="M18 8a6 6 0 0 0-9.33-5"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`;
  btn.classList.toggle('muted', !STATE.somAtivo);
  salvarPreferencias();
}

function toggleModel() {
  STATE.chatgptModel = STATE.chatgptModel === CONFIG.CHATGPT_MODEL_DEFAULT
    ? CONFIG.CHATGPT_MODEL_ALT : CONFIG.CHATGPT_MODEL_DEFAULT;
  DOM.modelBadge().textContent = STATE.chatgptModel === CONFIG.CHATGPT_MODEL_DEFAULT ? 'GPT-4o-mini' : 'GPT-4o';
  salvarPreferencias();
}

function inverterOrdem() {
  STATE.modoInvertido = !STATE.modoInvertido;
  fecharDropdown();
  DOM.invertedBadge().style.display = STATE.modoInvertido ? 'inline' : 'none';
  DOM.btnInverter().classList.toggle('active-mode', STATE.modoInvertido);
  adicionarMensagemSistema(STATE.modoInvertido
    ? 'Modo invertido — ChatGPT responde primeiro, DeepSeek revisa.'
    : 'Modo padrão — DeepSeek responde primeiro, ChatGPT revisa.');
  salvarPreferencias();
}

function novaConversa() {
  fecharDropdown();
  if (STATE.mensagens.length > 0) salvarNoHistorico();
  STATE.mensagens      = [];
  STATE.ultimaPergunta = '';
  STATE.replyingTo     = null;
  STATE.conversaAtual  = { id: Date.now().toString(), data: new Date().toISOString(), titulo: 'Nova conversa', mensagens: [] };
  const area = DOM.messagesArea();
  area.innerHTML = '<div class="date-divider"><span>HOJE</span></div>';
  adicionarBoasVindas();
  cancelarResposta();
}

function adicionarBoasVindas() {
  const hora = getHoraAtual();
  const id   = gerarId();
  const wrapper = document.createElement('div');
  wrapper.className      = 'message-wrapper ai deepseek-msg';
  wrapper.dataset.id     = id;
  wrapper.dataset.sender = 'deepseek';
  wrapper.dataset.text   = 'Olá! Faça sua pergunta e receba uma resposta do DeepSeek revisada criticamente pelo ChatGPT.';
  wrapper.innerHTML = `
    <div class="msg-header">
      <div class="msg-avatar-circle deepseek">${SVG_DEEPSEEK}</div>
      <span class="msg-sender deepseek">DeepSeek</span>
      <span style="font-size:11px;color:var(--text-secondary)">${hora}</span>
    </div>
    <div class="bubble">
      <div class="bubble-content">
        <p>Olá! Sou o <strong>DeepSeek</strong>. 👋</p>
        <p>Faça sua pergunta e você receberá:</p>
        <p>1️⃣ Minha resposta detalhada<br>
           2️⃣ Uma revisão crítica do <strong>ChatGPT</strong> com pontos fortes, melhorias e sugestões</p>
        <p>Pode perguntar!</p>
      </div>
      <span class="msg-time">${hora}</span>
    </div>`;
  DOM.messagesArea().appendChild(wrapper);
}

function fecharModal(id) { document.getElementById(id).classList.remove('open'); }

// =========================================================
// HISTÓRICO
// =========================================================

function abrirHistorico() {
  fecharDropdown();
  renderizarHistorico('');
  DOM.historicoModal().classList.add('open');
}

function renderizarHistorico(filtro) {
  const historico = carregarHistorico();
  const lista     = DOM.historicoLista();
  lista.innerHTML = '';
  const filtrado  = filtro
    ? historico.filter(h =>
        h.titulo.toLowerCase().includes(filtro.toLowerCase()) ||
        h.mensagens.some(m => m.text.toLowerCase().includes(filtro.toLowerCase())))
    : historico;

  if (!filtrado.length) { lista.innerHTML = '<div class="history-empty">Nenhuma conversa encontrada</div>'; return; }

  filtrado.forEach(conv => {
    const data = new Date(conv.data).toLocaleDateString('pt-BR', { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' });
    const item = document.createElement('div');
    item.className = 'history-item';
    item.innerHTML = `
      <div class="history-item-info">
        <div class="history-item-date">${data}</div>
        <div class="history-item-title">${conv.titulo || 'Conversa sem título'}</div>
        <div class="history-item-count">${conv.mensagens.length} mensagens</div>
      </div>
      <button class="btn-history-delete" onclick="event.stopPropagation();excluirConversa('${conv.id}')" title="Excluir">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
      </button>`;
    item.addEventListener('click', () => carregarConversa(conv));
    lista.appendChild(item);
  });
}

function filtrarHistorico(valor) { renderizarHistorico(valor); }

function carregarConversa(conv) {
  fecharModal('historicoModal');
  if (STATE.mensagens.length > 0) salvarNoHistorico();
  STATE.mensagens     = [...conv.mensagens];
  STATE.conversaAtual = { ...conv };
  const area = DOM.messagesArea();
  area.innerHTML = '';
  const data = new Date(conv.data).toLocaleDateString('pt-BR', { day:'2-digit', month:'long', year:'numeric' });
  area.innerHTML = `<div class="date-divider"><span>${data.toUpperCase()}</span></div>`;
  conv.mensagens.forEach(m => area.appendChild(m.sender === 'user' ? criarWrapperUsuario(m) : criarWrapperIA(m)));
  scrollParaBaixo();
}

function criarWrapperUsuario(m) {
  const el = document.createElement('div');
  el.className = 'message-wrapper user';
  el.dataset.id = m.id; el.dataset.sender = 'user'; el.dataset.text = m.text;
  el.innerHTML = `
    <div class="msg-header">
      <span class="msg-sender" style="color:#8b8b9e">Você</span>
      <span style="display:flex;align-items:center;color:rgba(255,255,255,0.5)">${SVG_USER}</span>
    </div>
    <div class="bubble" oncontextmenu="abrirContextMenu(event,'${m.id}','user')" onclick="onBubbleClick()">
      <div class="bubble-content">${renderMarkdown(m.text)}</div>
      <span class="msg-time">${m.hora || ''}</span>
      <span class="msg-checks">${SVG_CHECKS}</span>
    </div>`;
  return el;
}

function criarWrapperIA(m) {
  const isDS      = m.sender === 'deepseek';
  const cssClass  = isDS ? 'deepseek-msg' : 'chatgpt-msg';
  const senderCls = isDS ? 'deepseek'     : 'chatgpt';
  const nome      = isDS ? 'DeepSeek'     : 'ChatGPT Revisor';
  const avatar    = isDS ? SVG_DEEPSEEK   : SVG_CHATGPT;
  const el = document.createElement('div');
  el.className = `message-wrapper ai ${cssClass}`;
  el.dataset.id = m.id; el.dataset.sender = m.sender; el.dataset.text = m.text;
  el.innerHTML = `
    <div class="msg-header">
      <div class="msg-avatar-circle ${senderCls}">${avatar}</div>
      <span class="msg-sender ${senderCls}">${nome}</span>
      <span style="font-size:11px;color:var(--text-secondary)">${m.hora || ''}</span>
    </div>
    <div class="bubble" oncontextmenu="abrirContextMenu(event,'${m.id}','${m.sender}')" onclick="onBubbleClick()">
      <div class="bubble-content">${renderMarkdown(m.text)}</div>
      <span class="msg-time">${m.hora || ''}</span>
    </div>`;
  return el;
}

function excluirConversa(id) {
  deletarDoHistorico(id);
  renderizarHistorico(document.getElementById('historicoSearch').value);
}

// =========================================================
// EXPORTAR MARKDOWN
// =========================================================

function exportarMarkdown() {
  fecharDropdown();
  if (!STATE.mensagens.length) { adicionarMensagemSistema('Nenhuma mensagem para exportar.'); return; }
  const data = new Date().toLocaleDateString('pt-BR', { day:'2-digit', month:'long', year:'numeric', hour:'2-digit', minute:'2-digit' });
  let md = `# DeepChat — Conversa Exportada\n**Data:** ${data}\n**Modo:** ${STATE.modoInvertido ? 'Invertido' : 'Normal'}\n\n---\n\n`;
  STATE.mensagens.forEach(m => {
    const nome = m.sender === 'user' ? 'Usuário' : m.sender === 'deepseek' ? 'DeepSeek' : 'ChatGPT Revisor';
    md += `## ${nome} [${m.hora || ''}]\n\n${m.text}\n\n---\n\n`;
  });
  const url = URL.createObjectURL(new Blob([md], { type: 'text/markdown;charset=utf-8' }));
  Object.assign(document.createElement('a'), { href: url, download: `deepchat-${Date.now()}.md` }).click();
  URL.revokeObjectURL(url);
}

// =========================================================
// TOAST (pergunta repetida)
// =========================================================

function mostrarToastRepetida() { DOM.repeatToast().classList.add('visible'); }
function toastConfirmar() {
  DOM.repeatToast().classList.remove('visible');
  if (STATE.pendingRepeatCallback) { STATE.pendingRepeatCallback(); STATE.pendingRepeatCallback = null; }
}
function toastCancelar() {
  DOM.repeatToast().classList.remove('visible');
  STATE.pendingRepeatCallback = null;
  DOM.messageInput().value = ''; DOM.messageInput().style.height = 'auto'; onInputChange();
}

// =========================================================
// DETECTAR CONEXÃO
// =========================================================
window.addEventListener('online',  () => DOM.offlineBanner().classList.remove('visible'));
window.addEventListener('offline', () => DOM.offlineBanner().classList.add('visible'));

// =========================================================
// FECHAR MENUS AO CLICAR FORA
// =========================================================
document.addEventListener('click', e => {
  const dropdown = DOM.dropdownMenu();
  const menuBtn  = document.querySelector('.menu-dots-btn');
  if (dropdown.classList.contains('open') && !dropdown.contains(e.target) && !menuBtn.contains(e.target)) fecharDropdown();
  const ctx = DOM.contextMenu();
  if (ctx.classList.contains('open') && !ctx.contains(e.target)) fecharContextMenu();
});

// Long press mobile
let longPressTimer = null;
document.addEventListener('touchstart', e => {
  const bubble = e.target.closest('.bubble');
  if (!bubble) return;
  longPressTimer = setTimeout(() => {
    const wrapper = bubble.closest('.message-wrapper');
    if (!wrapper) return;
    const touch = e.touches[0];
    abrirContextMenu(
      { preventDefault:()=>{}, stopPropagation:()=>{}, clientX: touch.clientX, clientY: touch.clientY },
      wrapper.dataset.id, wrapper.dataset.sender
    );
  }, 500);
}, { passive: true });
document.addEventListener('touchend',  () => { clearTimeout(longPressTimer); longPressTimer = null; }, { passive: true });
document.addEventListener('touchmove', () => { clearTimeout(longPressTimer); longPressTimer = null; }, { passive: true });

// =========================================================
// ANEXO DE ARQUIVO
// =========================================================
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB

const FILE_ICONS = {
  pdf: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`,
  txt: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
  csv: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/><line x1="15" y1="3" x2="15" y2="21"/></svg>`,
  img: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`
};

let anexoAtual = null;

const lerBase64 = file => new Promise((res, rej) => {
  const r = new FileReader();
  r.onload  = () => res(r.result.split(',')[1]);
  r.onerror = () => rej(new Error('Falha ao ler arquivo'));
  r.readAsDataURL(file);
});

const lerTexto = file => new Promise((res, rej) => {
  const r = new FileReader();
  r.onload  = () => res(r.result);
  r.onerror = () => rej(new Error('Falha ao ler arquivo'));
  r.readAsText(file, 'UTF-8');
});

function formatBytes(b) {
  if (b < 1024)       return b + ' B';
  if (b < 1024*1024)  return (b/1024).toFixed(1) + ' KB';
  return (b/(1024*1024)).toFixed(1) + ' MB';
}

async function onFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;
  event.target.value = '';
  if (file.size > MAX_FILE_SIZE) {
    adicionarMensagemErro('Arquivo muito grande', `Limite: 5 MB. Seu arquivo: ${formatBytes(file.size)}.`);
    return;
  }
  const ext     = file.name.split('.').pop().toLowerCase();
  const isImage = file.type.startsWith('image/');
  const isText  = ['txt','md','csv','markdown'].includes(ext);
  const isPdf   = ext === 'pdf';
  try {
    let base64 = null, text = null, previewUrl = null;
    const mediaType = file.type || 'application/octet-stream';
    if (isImage)     { base64 = await lerBase64(file); previewUrl = `data:${file.type};base64,${base64}`; }
    else if (isText) { text   = await lerTexto(file); }
    else if (isPdf)  { base64 = await lerBase64(file); }
    anexoAtual = { name: file.name, size: file.size, type: ext, mediaType, base64, text, previewUrl, isImage };
    mostrarFilePreview();
  } catch (err) { adicionarMensagemErro('Erro ao ler arquivo', err.message); }
}

function mostrarFilePreview() {
  if (!anexoAtual) return;
  const icon = document.getElementById('filePreviewIcon');
  document.getElementById('filePreviewName').textContent = anexoAtual.name;
  document.getElementById('filePreviewSize').textContent = formatBytes(anexoAtual.size);
  icon.innerHTML = (anexoAtual.isImage && anexoAtual.previewUrl)
    ? `<img src="${anexoAtual.previewUrl}" alt="preview">`
    : FILE_ICONS[['csv','pdf'].includes(anexoAtual.type) ? anexoAtual.type : 'txt'];
  document.getElementById('filePreviewBar').classList.add('visible');
  DOM.messageInput().focus();
}

function removerAnexo() {
  anexoAtual = null;
  document.getElementById('filePreviewBar').classList.remove('visible');
}

function gerarHtmlAnexo(anexo) {
  if (anexo.isImage) {
    return `<div class="attachment-bubble"><img class="attachment-image" src="${anexo.previewUrl}" alt="${anexo.name}" onclick="this.requestFullscreen&&this.requestFullscreen()"></div>`;
  }
  const iconKey = ['csv','pdf'].includes(anexo.type) ? anexo.type : 'txt';
  return `<div class="attachment-bubble"><div class="attachment-file"><div class="attachment-file-icon">${FILE_ICONS[iconKey]}</div><div class="attachment-file-info"><div class="attachment-file-name">${anexo.name}</div><div class="attachment-file-type">${anexo.type.toUpperCase()} · ${formatBytes(anexo.size)}</div></div></div></div>`;
}

function montarConteudoComAnexo(textoUsuario, anexo) {
  if (anexo.isImage) {
    return [
      { type: 'image_url', image_url: { url: `data:${anexo.mediaType};base64,${anexo.base64}` } },
      ...(textoUsuario ? [{ type: 'text', text: textoUsuario }] : [])
    ];
  }
  if (anexo.text !== null) {
    const prefixo = `[Arquivo: ${anexo.name}]\n\`\`\`\n${anexo.text.substring(0, 12000)}${anexo.text.length > 12000 ? '\n...(truncado)' : ''}\n\`\`\`\n\n`;
    return [{ type: 'text', text: prefixo + (textoUsuario || 'Analise o arquivo acima.') }];
  }
  return [{ type: 'text', text: `[PDF: ${anexo.name}] — ${textoUsuario || 'Analise este documento.'}` }];
}

// =========================================================
// INICIALIZAÇÃO
// =========================================================

function inicializarChat() {
  carregarPreferencias();
  const btn = DOM.soundToggle();
  btn.innerHTML = STATE.somAtivo
    ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`
    : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13.73 21a2 2 0 0 1-3.46 0"/><path d="M18.63 13A17.89 17.89 0 0 1 18 8"/><path d="M6.26 6.26A5.86 5.86 0 0 0 6 8c0 7-3 9-3 9h14"/><path d="M18 8a6 6 0 0 0-9.33-5"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`;
  btn.classList.toggle('muted', !STATE.somAtivo);
  DOM.modelBadge().textContent         = STATE.chatgptModel === CONFIG.CHATGPT_MODEL_DEFAULT ? 'GPT-4o-mini' : 'GPT-4o';
  DOM.invertedBadge().style.display    = STATE.modoInvertido ? 'inline' : 'none';
  DOM.btnInverter().classList.toggle('active-mode', STATE.modoInvertido);
  atualizarStatus(STATE.modoInvertido ? 'ChatGPT + DeepSeek Revisor' : 'DeepSeek + ChatGPT Revisor');
  adicionarBoasVindas();
  scrollParaBaixo();
  setTimeout(() => DOM.messageInput().focus(), 100);
  if (!navigator.onLine) DOM.offlineBanner().classList.add('visible');
}

function init() {
  carregarChavesSalvas();
  const ds  = localStorage.getItem(CONFIG.LS_DEEPSEEK_KEY);
  const gpt = localStorage.getItem(CONFIG.LS_CHATGPT_KEY);
  if (ds && gpt && ds.length > 5 && gpt.length > 5) {
    STATE.deepseekKey = ds;
    STATE.chatgptKey  = gpt;
    DOM.loginScreen().classList.add('hidden');
    DOM.chatScreen().classList.remove('hidden');
    inicializarChat();
  }
}

window.addEventListener('DOMContentLoaded', init);
