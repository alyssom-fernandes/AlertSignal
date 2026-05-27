// app.js — comportamentos globais do sistema

// Fecha modal clicando fora da caixa
document.addEventListener('click', function(e) {
  const overlay = document.getElementById('modal');
  if (overlay && e.target === overlay) {
    overlay.classList.remove('open');
  }
});

// Fecha modal com ESC
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    const overlay = document.getElementById('modal');
    if (overlay) overlay.classList.remove('open');
  }
});
