/* AlertSignal: comportamentos globais.
   Funções usadas pelas páginas: api(), showToast(), abrirModal(), fecharModal(),
   confirmar(), toggleTheme(), toggleSidebar(), abrirSidebarMobile(),
   fecharSidebarMobile(). */

(function () {
  'use strict';

  // ─── API ──────────────────────────────────────────────────────────────────
  // fetch com JSON, token CSRF e erro amigável. Sempre resolve: {ok, erro?, ...}
  window.api = async function (url, opcoes) {
    opcoes = opcoes || {};
    const metodo = (opcoes.method || 'GET').toUpperCase();
    const cabecalhos = Object.assign({ 'Accept': 'application/json' }, opcoes.headers || {});
    let corpo = opcoes.body;
    if (corpo && typeof corpo === 'object' && !(corpo instanceof FormData)) {
      cabecalhos['Content-Type'] = 'application/json';
      corpo = JSON.stringify(corpo);
    }
    if (metodo !== 'GET') {
      const meta = document.querySelector('meta[name="csrf-token"]');
      if (meta) cabecalhos['X-CSRF-Token'] = meta.content;
    }
    let resp;
    try {
      resp = await fetch(url, { method: metodo, headers: cabecalhos, body: corpo, credentials: 'same-origin' });
    } catch (e) {
      return { ok: false, erro: 'Sem conexão com o servidor. Tente de novo.' };
    }
    let dados;
    try { dados = await resp.json(); } catch (e) { dados = {}; }
    if (dados.ok === undefined) dados.ok = resp.ok;
    if (!dados.ok && !dados.erro) dados.erro = 'Não foi possível concluir a ação (' + resp.status + ').';
    return dados;
  };

  // ─── TOAST ────────────────────────────────────────────────────────────────
  const ICONES_TOAST = { ok: 'ti-circle-check', erro: 'ti-alert-circle', info: 'ti-info-circle' };
  let temporizadorToast = null;
  window.showToast = function (msg, tipo) {
    tipo = tipo || 'ok';
    const t = document.getElementById('toast');
    const m = document.getElementById('toast-msg');
    if (!t || !m) return;
    m.textContent = msg;
    t.querySelector('i').className = 'ti ' + (ICONES_TOAST[tipo] || ICONES_TOAST.info);
    t.className = 'show t-' + tipo;
    clearTimeout(temporizadorToast);
    temporizadorToast = setTimeout(function () { t.className = 't-' + tipo; }, tipo === 'erro' ? 5000 : 3200);
  };

  // ─── MODAIS (dialog nativo) ───────────────────────────────────────────────
  // showModal() já prende o foco e fecha com Esc; aqui cuidamos do clique
  // fora da caixa e de devolver o foco a quem abriu.
  const origemDoFoco = new WeakMap();

  window.abrirModal = function (id, gatilho) {
    const d = document.getElementById(id);
    if (!d || d.open) return;
    origemDoFoco.set(d, gatilho || document.activeElement);
    d.showModal();
    const alvo = d.querySelector('[autofocus]') || d.querySelector('input:not([type=hidden]), select, textarea');
    if (alvo) alvo.focus();
  };

  window.fecharModal = function (id) {
    const d = typeof id === 'string' ? document.getElementById(id) : id;
    if (d && d.open) d.close();
  };

  function prepararModal(d) {
    if (d.dataset.pronto) return;
    d.dataset.pronto = '1';
    let pressionouFora = false;
    d.addEventListener('mousedown', function (e) { pressionouFora = e.target === d; });
    d.addEventListener('click', function (e) {
      if (e.target === d && pressionouFora) d.close('fora');
      const botao = e.target.closest('[data-fechar]');
      if (botao) d.close('fechar');
    });
    d.addEventListener('close', function () {
      const origem = origemDoFoco.get(d);
      if (origem && typeof origem.focus === 'function' && document.contains(origem)) origem.focus();
    });
  }

  // ─── CONFIRMAÇÃO ──────────────────────────────────────────────────────────
  // confirmar({titulo, texto, botao, perigo}) → Promise<boolean>
  window.confirmar = function (opcoes) {
    opcoes = opcoes || {};
    const d = document.getElementById('modal-confirmar');
    if (!d) return Promise.resolve(window.confirm(opcoes.texto || 'Confirmar?'));
    document.getElementById('confirmar-titulo').textContent = opcoes.titulo || 'Confirmar';
    document.getElementById('confirmar-texto').textContent = opcoes.texto || '';
    const sim = document.getElementById('confirmar-sim');
    sim.textContent = opcoes.botao || 'Confirmar';
    sim.className = 'btn ' + (opcoes.perigo ? 'btn-perigo' : 'btn-primary');
    const icone = document.getElementById('confirmar-icone');
    if (icone) icone.hidden = !opcoes.perigo;
    return new Promise(function (resolver) {
      let resposta = false;
      function aoClicar(e) {
        const b = e.target.closest('[data-resposta]');
        if (!b) return;
        resposta = b.dataset.resposta === 'sim';
        d.close();
      }
      d.addEventListener('click', aoClicar);
      d.addEventListener('close', function aoFechar() {
        d.removeEventListener('click', aoClicar);
        d.removeEventListener('close', aoFechar);
        resolver(resposta);
      });
      abrirModal('modal-confirmar');
      (opcoes.perigo ? d.querySelector('[data-resposta="nao"]') : sim).focus();
    });
  };

  // Formulários com data-confirmar pedem confirmação antes de enviar
  document.addEventListener('submit', async function (e) {
    const form = e.target;
    if (!form.dataset || !form.dataset.confirmar || form.dataset.confirmado) return;
    e.preventDefault();
    const ok = await confirmar({
      titulo: form.dataset.confirmarTitulo || 'Confirmar',
      texto: form.dataset.confirmar,
      botao: form.dataset.confirmarBotao || 'Confirmar',
      perigo: form.dataset.perigo !== undefined,
    });
    if (ok) { form.dataset.confirmado = '1'; form.requestSubmit ? form.requestSubmit() : form.submit(); }
  });

  // Botões dentro de formulários mostram que estão trabalhando
  document.addEventListener('submit', function (e) {
    if (e.defaultPrevented) return;
    const botao = e.submitter || e.target.querySelector('[type=submit]');
    if (botao) setTimeout(function () { botao.disabled = true; }, 0);
  });

  // Voltando pelo histórico (cache do navegador), os botões voltam a funcionar
  window.addEventListener('pageshow', function (e) {
    if (!e.persisted) return;
    document.querySelectorAll('form [type=submit]').forEach(function (b) { b.disabled = false; });
    document.querySelectorAll('form[data-confirmado]').forEach(function (f) { delete f.dataset.confirmado; });
  });

  // ─── ABAS ─────────────────────────────────────────────────────────────────
  function prepararAbas(lista) {
    const abas = Array.from(lista.querySelectorAll('[role="tab"]'));
    function selecionar(aba, focar) {
      abas.forEach(function (a) {
        const ativa = a === aba;
        a.setAttribute('aria-selected', ativa ? 'true' : 'false');
        a.tabIndex = ativa ? 0 : -1;
        const painel = document.getElementById(a.getAttribute('aria-controls'));
        if (painel) painel.hidden = !ativa;
      });
      if (focar) aba.focus();
      if (lista.dataset.parametro && aba.dataset.valor) {
        const url = new URL(location.href);
        url.searchParams.set(lista.dataset.parametro, aba.dataset.valor);
        history.replaceState(null, '', url);
      }
      lista.dispatchEvent(new CustomEvent('aba-trocada', { detail: aba }));
    }
    abas.forEach(function (aba, i) {
      aba.addEventListener('click', function () { selecionar(aba, false); });
      aba.addEventListener('keydown', function (e) {
        let j = null;
        if (e.key === 'ArrowRight') j = (i + 1) % abas.length;
        if (e.key === 'ArrowLeft') j = (i - 1 + abas.length) % abas.length;
        if (e.key === 'Home') j = 0;
        if (e.key === 'End') j = abas.length - 1;
        if (j !== null) { e.preventDefault(); selecionar(abas[j], true); }
      });
    });
  }

  // ─── TEMA ─────────────────────────────────────────────────────────────────
  function atualizarBotoesTema() {
    const claro = document.documentElement.getAttribute('data-theme') === 'light';
    document.querySelectorAll('.theme-toggle').forEach(function (b) {
      b.setAttribute('aria-label', claro ? 'Usar tema escuro' : 'Usar tema claro');
      b.title = claro ? 'Usar tema escuro' : 'Usar tema claro';
      const i = b.querySelector('i');
      if (i) i.className = 'ti ' + (claro ? 'ti-moon' : 'ti-sun');
    });
  }
  window.toggleTheme = function () {
    const html = document.documentElement;
    const proximo = html.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    html.setAttribute('data-theme', proximo);
    try { localStorage.setItem('theme', proximo); } catch (e) {}
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', proximo === 'light' ? '#f4f4f6' : '#050505');
    atualizarBotoesTema();
  };

  // ─── MENU LATERAL ─────────────────────────────────────────────────────────
  // Dica com o nome do item quando o menu está recolhido. Fica fora do menu
  // (position: fixed) para não ser cortada pela borda arredondada dele.
  let dicaMenu = null, temporizadorDica = null;
  function mostrarDicaMenu(alvo) {
    const sb = document.getElementById('sidebar');
    if (!sb || !sb.classList.contains('collapsed') || window.innerWidth <= 900) return;
    const texto = alvo.dataset.label || alvo.getAttribute('aria-label');
    if (!texto) return;
    if (!dicaMenu) {
      dicaMenu = document.createElement('div');
      dicaMenu.className = 'dica-menu';
      dicaMenu.setAttribute('aria-hidden', 'true');
      document.body.appendChild(dicaMenu);
    }
    clearTimeout(temporizadorDica);
    temporizadorDica = setTimeout(function () {
      const r = alvo.getBoundingClientRect(), caixa = sb.getBoundingClientRect();
      dicaMenu.textContent = texto;
      dicaMenu.style.left = (caixa.right + 10) + 'px';
      dicaMenu.style.top = (r.top + r.height / 2) + 'px';
      dicaMenu.classList.add('visivel');
    }, 120);
  }
  function esconderDicaMenu() {
    clearTimeout(temporizadorDica);
    if (dicaMenu) dicaMenu.classList.remove('visivel');
  }

  window.toggleSidebar = function () {
    const sb = document.getElementById('sidebar');
    const ma = document.getElementById('main-area');
    if (!sb) return;
    esconderDicaMenu();
    const recolhido = sb.classList.toggle('collapsed');
    if (ma) ma.classList.toggle('collapsed', recolhido);
    const b = document.querySelector('.sb-toggle-btn');
    if (b) {
      b.setAttribute('aria-expanded', recolhido ? 'false' : 'true');
      b.setAttribute('aria-label', recolhido ? 'Expandir menu' : 'Recolher menu');
      b.title = recolhido ? 'Expandir menu' : 'Recolher menu';
    }
    try { localStorage.setItem('sidebarCollapsed', recolhido ? '1' : '0'); } catch (e) {}
  };

  window.abrirSidebarMobile = function () {
    const sb = document.getElementById('sidebar');
    if (!sb) return;
    sb.classList.add('mobile-open');
    document.getElementById('sb-overlay').classList.add('active');
    document.querySelectorAll('.mobile-menu-btn').forEach(function (b) { b.setAttribute('aria-expanded', 'true'); });
    const primeiro = sb.querySelector('.nav-item');
    if (primeiro) primeiro.focus();
  };

  window.fecharSidebarMobile = function () {
    const sb = document.getElementById('sidebar');
    if (!sb || !sb.classList.contains('mobile-open')) return;
    sb.classList.remove('mobile-open');
    document.getElementById('sb-overlay').classList.remove('active');
    document.querySelectorAll('.mobile-menu-btn').forEach(function (b) { b.setAttribute('aria-expanded', 'false'); b.focus(); });
  };

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') fecharSidebarMobile();
  });

  // ─── INÍCIO ───────────────────────────────────────────────────────────────
  function iniciar() {
    atualizarBotoesTema();
    // Aviso guardado antes de recarregar a página (ex.: "documento renovado")
    try {
      const pendente = sessionStorage.getItem('toast');
      if (pendente) { sessionStorage.removeItem('toast'); showToast(pendente); }
    } catch (e) {}
    document.querySelectorAll('dialog.modal').forEach(prepararModal);
    document.querySelectorAll('.sidebar .nav-item, .sb-foot-collapsed .icone-btn').forEach(function (el) {
      el.addEventListener('mouseenter', function () { mostrarDicaMenu(el); });
      el.addEventListener('focus', function () { mostrarDicaMenu(el); });
      el.addEventListener('mouseleave', esconderDicaMenu);
      el.addEventListener('blur', esconderDicaMenu);
    });
    document.querySelectorAll('[role="tablist"]').forEach(prepararAbas);
    // Mostrar/ocultar senha
    document.querySelectorAll('[data-ver-senha]').forEach(function (b) {
      b.addEventListener('click', function () {
        const campo = document.getElementById(b.dataset.verSenha);
        const mostrar = campo.type === 'password';
        campo.type = mostrar ? 'text' : 'password';
        b.setAttribute('aria-label', mostrar ? 'Ocultar senha' : 'Mostrar senha');
        b.setAttribute('aria-pressed', mostrar ? 'true' : 'false');
        b.querySelector('i').className = 'ti ' + (mostrar ? 'ti-eye-off' : 'ti-eye');
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
