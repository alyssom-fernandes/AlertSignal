from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date, datetime
from functools import wraps
import os

from database import get_connection, init_db, inserir_configuracoes_padrao, get_config, set_config
from importar_planilha import importar
from notificacoes import executar_verificacao_diaria, calcular_dias, recalcular_status

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'zen-alvaras-chave-segura-2024')

TIPOS_DOC = [
    'AVCB', 'Licença de Operação', 'LAC - Licença de Transportes',
    'Alvará Municipal', 'Alvará Sanitário', 'FEASPOL',
    'CADASTUR', 'IPTU', 'Alvará Policial',
]

# ─── DECORADORES ──────────────────────────────────────────────────────────────

def login_obrigatorio(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def admin_obrigatorio(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        if session.get('usuario_nivel') != 'admin':
            flash('Acesso restrito a administradores.', 'erro')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrapper

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def criar_admin_padrao():
    conn = get_connection()
    total = conn.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0]
    if total == 0:
        conn.execute('INSERT INTO usuarios (nome, email, senha, nivel) VALUES (?,?,?,?)',
                     ('Administrador', 'admin@grupozen.com.br', generate_password_hash('zen2024'), 'admin'))
        conn.commit()
    conn.close()

def status_badge(status):
    return {'OK':'ok','RENOVAR':'warn','VENCIDO':'danger','NÃO TEM':'none'}.get(status,'none')

def registrar_historico(conn, descricao, tipo='tramite', empresa_id=None, documento_id=None):
    uid = session.get('usuario_id')
    conn.execute('INSERT INTO historico (tipo, descricao, empresa_id, documento_id, usuario_id) VALUES (?,?,?,?,?)',
                 (tipo, descricao, empresa_id, documento_id, uid))

def recalcular_todos(conn):
    docs = conn.execute("SELECT id, vencimento FROM documentos WHERE vencimento IS NOT NULL").fetchall()
    for doc in docs:
        dias = calcular_dias(doc['vencimento'])
        novo = recalcular_status(dias)
        conn.execute('UPDATE documentos SET status=? WHERE id=?', (novo, doc['id']))
    conn.commit()

def get_stats(conn):
    rows = conn.execute('SELECT status, COUNT(*) as total FROM documentos GROUP BY status').fetchall()
    stats = {'OK':0,'RENOVAR':0,'VENCIDO':0,'NÃO TEM':0}
    for r in rows:
        stats[r['status']] = r['total']
    return stats

# ─── CONTEXT PROCESSOR ────────────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    urgentes_count = 0
    if 'usuario_id' in session:
        try:
            conn = get_connection()
            urgentes_count = conn.execute(
                "SELECT COUNT(*) FROM documentos d JOIN empresas e ON e.id=d.empresa_id "
                "WHERE d.status IN ('VENCIDO','RENOVAR') AND e.ativa=1"
            ).fetchone()[0]
            conn.close()
        except Exception:
            pass
    return {'now': datetime.now(), 'urgentes_count': urgentes_count}

# ─── FILTROS JINJA ────────────────────────────────────────────────────────────

@app.template_filter('formatar_data')
def formatar_data(valor):
    if not valor: return '—'
    try: return datetime.strptime(valor, '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return valor

@app.template_filter('status_classe')
def status_classe(status):
    return status_badge(status)

@app.template_filter('dias_texto')
def dias_texto(dias):
    if dias is None: return '—'
    if dias < 0: return f'Vencido há {abs(dias)}d'
    return f'{dias}d'

# ─── AUTH ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'usuario_id' in session: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    erro = None
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        senha = request.form.get('senha','')
        conn = get_connection()
        u = conn.execute('SELECT * FROM usuarios WHERE email=? AND ativo=1', (email,)).fetchone()
        conn.close()
        if u and check_password_hash(u['senha'], senha):
            session['usuario_id']    = u['id']
            session['usuario_nome']  = u['nome']
            session['usuario_nivel'] = u['nivel']
            return redirect(url_for('dashboard'))
        erro = 'E-mail ou senha incorretos.'
    return render_template('login.html', erro=erro)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─── PERFIL ────────────────────────────────────────────────────────────────────

@app.route('/perfil', methods=['GET','POST'])
@login_obrigatorio
def perfil():
    conn = get_connection()
    u = conn.execute('SELECT * FROM usuarios WHERE id=?', (session['usuario_id'],)).fetchone()
    erro = ok = None
    if request.method == 'POST':
        acao = request.form.get('acao')
        if acao == 'nome':
            novo_nome = request.form.get('nome','').strip()
            if novo_nome:
                conn.execute('UPDATE usuarios SET nome=? WHERE id=?', (novo_nome, session['usuario_id']))
                conn.commit()
                session['usuario_nome'] = novo_nome
                ok = 'Nome atualizado.'
        elif acao == 'senha':
            atual = request.form.get('senha_atual','')
            nova  = request.form.get('senha_nova','')
            conf  = request.form.get('senha_conf','')
            if not check_password_hash(u['senha'], atual):
                erro = 'Senha atual incorreta.'
            elif len(nova) < 6:
                erro = 'Nova senha deve ter pelo menos 6 caracteres.'
            elif nova != conf:
                erro = 'As senhas não coincidem.'
            else:
                conn.execute('UPDATE usuarios SET senha=? WHERE id=?', (generate_password_hash(nova), session['usuario_id']))
                conn.commit()
                ok = 'Senha alterada com sucesso.'
        u = conn.execute('SELECT * FROM usuarios WHERE id=?', (session['usuario_id'],)).fetchone()
    conn.close()
    return render_template('perfil.html', usuario=u, erro=erro, ok=ok)

# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_obrigatorio
def dashboard():
    conn = get_connection()
    recalcular_todos(conn)
    stats = get_stats(conn)
    total_empresas = conn.execute('SELECT COUNT(*) FROM empresas WHERE ativa=1').fetchone()[0]
    urgentes_raw = conn.execute('''
        SELECT d.id, d.tipo, d.vencimento, d.status, e.nome as empresa, e.id as emp_id
        FROM documentos d JOIN empresas e ON e.id=d.empresa_id
        WHERE d.status IN ('VENCIDO','RENOVAR') AND d.vencimento IS NOT NULL
        ORDER BY d.vencimento LIMIT 20
    ''').fetchall()
    historico = conn.execute('''
        SELECT h.descricao, h.tipo, h.criado_em, e.nome as empresa_nome, u.nome as usuario_nome
        FROM historico h
        LEFT JOIN empresas e ON e.id=h.empresa_id
        LEFT JOIN usuarios u ON u.id=h.usuario_id
        ORDER BY h.id DESC LIMIT 10
    ''').fetchall()
    conn.close()
    urgentes = []
    for u in urgentes_raw:
        dias = calcular_dias(u['vencimento'])
        urgentes.append({'id':u['emp_id'],'doc_id':u['id'],'tipo':u['tipo'],'empresa':u['empresa'],'vencimento':u['vencimento'],'status':u['status'],'dias':dias})
    return render_template('dashboard.html', stats=stats, total_empresas=total_empresas,
                           urgentes=urgentes, historico=historico, hoje=date.today().strftime('%d/%m/%Y'))

# ─── EMPRESAS ─────────────────────────────────────────────────────────────────

@app.route('/empresas')
@login_obrigatorio
def empresas():
    conn = get_connection()
    recalcular_todos(conn)
    cats = conn.execute('SELECT * FROM categorias ORDER BY nome').fetchall()
    dados = []
    for cat in cats:
        emps = conn.execute('''
            SELECT e.id, e.nome, e.cnpj,
                   SUM(CASE WHEN d.status='VENCIDO' THEN 1 ELSE 0 END) as vencidos,
                   SUM(CASE WHEN d.status='RENOVAR' THEN 1 ELSE 0 END) as renovar,
                   SUM(CASE WHEN d.status='OK'      THEN 1 ELSE 0 END) as ok
            FROM empresas e
            LEFT JOIN documentos d ON d.empresa_id=e.id
            WHERE e.categoria_id=? AND e.ativa=1
            GROUP BY e.id ORDER BY e.nome
        ''', (cat['id'],)).fetchall()
        dados.append({'categoria':cat,'empresas':emps})
    total = sum(len(d['empresas']) for d in dados)
    conn.close()
    return render_template('empresas.html', dados=dados, total_empresas=total)

@app.route('/empresa/<int:emp_id>')
@login_obrigatorio
def empresa_detalhe(emp_id):
    conn = get_connection()
    empresa = conn.execute('SELECT e.*, c.nome as categoria FROM empresas e JOIN categorias c ON c.id=e.categoria_id WHERE e.id=?', (emp_id,)).fetchone()
    if not empresa: conn.close(); return redirect(url_for('empresas'))
    docs_raw = conn.execute('SELECT * FROM documentos WHERE empresa_id=? ORDER BY tipo', (emp_id,)).fetchall()
    documentos = []
    for doc in docs_raw:
        dias = calcular_dias(doc['vencimento'])
        resps = conn.execute('''SELECT r.id, r.nome, r.email FROM responsaveis r
            JOIN documento_responsavel dr ON dr.responsavel_id=r.id
            WHERE dr.documento_id=?''', (doc['id'],)).fetchall()
        documentos.append({'id':doc['id'],'tipo':doc['tipo'],'protocolo':doc['protocolo'],
                           'vencimento':doc['vencimento'],'status':doc['status'],
                           'observacoes':doc['observacoes'] or '','dias':dias,
                           'responsaveis':[dict(r) for r in resps]})
    todos_resp = conn.execute('SELECT * FROM responsaveis WHERE ativo=1 ORDER BY nome').fetchall()
    conn.close()
    return render_template('empresa_detalhe.html', empresa=empresa, documentos=documentos, todos_responsaveis=todos_resp)

# ─── CADASTROS ────────────────────────────────────────────────────────────────

@app.route('/cadastros')
@login_obrigatorio
def cadastros():
    conn = get_connection()
    categorias = conn.execute('SELECT c.*, COUNT(e.id) as total_empresas FROM categorias c LEFT JOIN empresas e ON e.categoria_id=c.id GROUP BY c.id ORDER BY c.nome').fetchall()
    empresas_ativas = conn.execute('''
        SELECT e.*, c.nome as categoria_nome, COUNT(d.id) as total_docs
        FROM empresas e JOIN categorias c ON c.id=e.categoria_id
        LEFT JOIN documentos d ON d.empresa_id=e.id
        WHERE e.ativa=1 GROUP BY e.id ORDER BY e.nome
    ''').fetchall()
    empresas_inativas = conn.execute('''
        SELECT e.*, c.nome as categoria_nome FROM empresas e
        JOIN categorias c ON c.id=e.categoria_id WHERE e.ativa=0 ORDER BY e.nome
    ''').fetchall()
    conn.close()
    return render_template('cadastros.html', categorias=categorias,
                           empresas_ativas=empresas_ativas, empresas_inativas=empresas_inativas,
                           tipos_doc=TIPOS_DOC)

@app.route('/empresa/nova', methods=['POST'])
@admin_obrigatorio
def empresa_nova():
    nome   = request.form.get('nome','').strip()
    cnpj   = request.form.get('cnpj','').strip() or None
    cat_id = request.form.get('categoria_id')
    if nome and cat_id:
        conn = get_connection()
        conn.execute('INSERT INTO empresas (nome, cnpj, categoria_id) VALUES (?,?,?)', (nome,cnpj,cat_id))
        conn.commit(); conn.close()
        flash('Empresa cadastrada com sucesso.', 'ok')
    return redirect(url_for('cadastros'))

@app.route('/empresa/<int:emp_id>/inativar', methods=['POST'])
@admin_obrigatorio
def empresa_inativar(emp_id):
    conn = get_connection()
    conn.execute('UPDATE empresas SET ativa=0 WHERE id=?', (emp_id,))
    conn.commit(); conn.close()
    flash('Empresa inativada.', 'ok')
    return redirect(url_for('cadastros'))

@app.route('/empresa/<int:emp_id>/reativar', methods=['POST'])
@admin_obrigatorio
def empresa_reativar(emp_id):
    conn = get_connection()
    conn.execute('UPDATE empresas SET ativa=1 WHERE id=?', (emp_id,))
    conn.commit(); conn.close()
    flash('Empresa reativada.', 'ok')
    return redirect(url_for('cadastros'))

@app.route('/empresa/<int:emp_id>/excluir', methods=['POST'])
@admin_obrigatorio
def empresa_excluir(emp_id):
    conn = get_connection()
    total = conn.execute('SELECT COUNT(*) FROM documentos WHERE empresa_id=?', (emp_id,)).fetchone()[0]
    if total > 0:
        conn.close(); flash('Não é possível excluir empresa com documentos vinculados.', 'erro')
        return redirect(url_for('cadastros'))
    conn.execute('DELETE FROM empresas WHERE id=?', (emp_id,))
    conn.commit(); conn.close()
    flash('Empresa excluída.', 'ok')
    return redirect(url_for('cadastros'))

@app.route('/categoria/nova', methods=['POST'])
@admin_obrigatorio
def categoria_nova():
    nome = request.form.get('nome','').strip()
    if nome:
        conn = get_connection()
        try:
            conn.execute('INSERT INTO categorias (nome) VALUES (?)', (nome,))
            conn.commit(); flash('Categoria criada.','ok')
        except: flash('Categoria já existe.','erro')
        finally: conn.close()
    return redirect(url_for('cadastros'))

@app.route('/categoria/<int:cat_id>/excluir', methods=['POST'])
@admin_obrigatorio
def categoria_excluir(cat_id):
    conn = get_connection()
    total = conn.execute('SELECT COUNT(*) FROM empresas WHERE categoria_id=?', (cat_id,)).fetchone()[0]
    if total > 0:
        conn.close(); flash('Categoria em uso por empresas.','erro')
        return redirect(url_for('cadastros'))
    conn.execute('DELETE FROM categorias WHERE id=?', (cat_id,))
    conn.commit(); conn.close()
    flash('Categoria excluída.','ok')
    return redirect(url_for('cadastros'))

@app.route('/cadastros/documento/novo', methods=['POST'])
@admin_obrigatorio
def documento_novo():
    emp_id    = request.form.get('empresa_id')
    tipo      = request.form.get('tipo','').strip()
    protocolo = request.form.get('protocolo','').strip() or None
    vencimento = request.form.get('vencimento') or None
    if emp_id and tipo:
        conn = get_connection()
        conn.execute('INSERT INTO documentos (empresa_id, tipo, protocolo, vencimento, status) VALUES (?,?,?,?,?)',
                     (emp_id, tipo, protocolo, vencimento, 'OK'))
        conn.commit(); conn.close()
        flash('Documento cadastrado.','ok')
    return redirect(url_for('cadastros'))

# ─── RESPONSÁVEIS ─────────────────────────────────────────────────────────────

@app.route('/responsaveis')
@login_obrigatorio
def responsaveis():
    conn = get_connection()
    lista = conn.execute('SELECT * FROM responsaveis WHERE ativo=1 ORDER BY nome').fetchall()
    conn.close()
    return render_template('responsaveis.html', responsaveis=lista)

@app.route('/responsaveis/novo', methods=['POST'])
@admin_obrigatorio
def responsavel_novo():
    nome  = request.form.get('nome','').strip()
    email = request.form.get('email','').strip()
    if nome and email:
        conn = get_connection()
        try:
            conn.execute('INSERT INTO responsaveis (nome, email) VALUES (?,?)', (nome,email))
            conn.commit(); flash('Responsável cadastrado.','ok')
        except: flash('E-mail já cadastrado.','erro')
        finally: conn.close()
    return redirect(url_for('responsaveis'))

@app.route('/responsaveis/<int:resp_id>/excluir', methods=['POST'])
@admin_obrigatorio
def responsavel_excluir(resp_id):
    conn = get_connection()
    conn.execute('UPDATE responsaveis SET ativo=0 WHERE id=?', (resp_id,))
    conn.commit(); conn.close()
    flash('Responsável removido.','ok')
    return redirect(url_for('responsaveis'))

# ─── HISTÓRICO ────────────────────────────────────────────────────────────────

@app.route('/historico')
@login_obrigatorio
def historico():
    page = int(request.args.get('page', 1))
    per  = 50
    conn = get_connection()
    total = conn.execute('SELECT COUNT(*) FROM historico').fetchone()[0]
    registros = conn.execute('''
        SELECT h.*, e.nome as empresa_nome, u.nome as usuario_nome
        FROM historico h
        LEFT JOIN empresas e ON e.id=h.empresa_id
        LEFT JOIN usuarios u ON u.id=h.usuario_id
        ORDER BY h.id DESC LIMIT ? OFFSET ?
    ''', (per, (page-1)*per)).fetchall()
    conn.close()
    import math
    total_pages = math.ceil(total / per)
    return render_template('historico.html', registros=registros,
                           page=page, total_pages=total_pages)

# ─── USUÁRIOS ─────────────────────────────────────────────────────────────────

@app.route('/usuarios')
@admin_obrigatorio
def usuarios():
    conn = get_connection()
    lista = conn.execute('SELECT * FROM usuarios ORDER BY nome').fetchall()
    conn.close()
    return render_template('usuarios.html', usuarios=lista)

@app.route('/usuarios/novo', methods=['POST'])
@admin_obrigatorio
def usuario_novo():
    nome  = request.form.get('nome','').strip()
    email = request.form.get('email','').strip()
    senha = request.form.get('senha','')
    nivel = request.form.get('nivel','visualizador')
    if len(senha) < 6:
        flash('Senha deve ter pelo menos 6 caracteres.','erro')
        return redirect(url_for('usuarios'))
    if nome and email:
        conn = get_connection()
        try:
            conn.execute('INSERT INTO usuarios (nome, email, senha, nivel) VALUES (?,?,?,?)',
                         (nome, email, generate_password_hash(senha), nivel))
            conn.commit(); flash('Usuário cadastrado.','ok')
        except: flash('E-mail já cadastrado.','erro')
        finally: conn.close()
    return redirect(url_for('usuarios'))

@app.route('/usuarios/<int:uid>/excluir', methods=['POST'])
@admin_obrigatorio
def usuario_excluir(uid):
    if uid == session.get('usuario_id'):
        flash('Você não pode excluir seu próprio usuário.','erro')
        return redirect(url_for('usuarios'))
    conn = get_connection()
    conn.execute('DELETE FROM usuarios WHERE id=?', (uid,))
    conn.commit(); conn.close()
    flash('Usuário removido.','ok')
    return redirect(url_for('usuarios'))

@app.route('/usuarios/<int:uid>/redefinir-senha', methods=['POST'])
@admin_obrigatorio
def usuario_redefinir_senha(uid):
    nova = request.form.get('senha_nova','')
    if len(nova) < 6:
        flash('Senha deve ter pelo menos 6 caracteres.','erro')
        return redirect(url_for('usuarios'))
    conn = get_connection()
    conn.execute('UPDATE usuarios SET senha=? WHERE id=?', (generate_password_hash(nova), uid))
    conn.commit(); conn.close()
    flash('Senha redefinida.','ok')
    return redirect(url_for('usuarios'))

# ─── CONFIGURAÇÕES ────────────────────────────────────────────────────────────

@app.route('/configuracoes', methods=['GET','POST'])
@admin_obrigatorio
def configuracoes():
    if request.method == 'POST':
        for campo in ['email_remetente','email_senha_app','horario_envio','alerta_dias_90','alerta_dias_30','alerta_dias_7']:
            valor = request.form.get(campo,'').strip()
            if valor: set_config(campo, valor)
        horario = get_config('horario_envio') or '08:00'
        hora, minuto = horario.split(':')
        try:
            scheduler.reschedule_job('verificacao_diaria', trigger='cron', hour=int(hora), minute=int(minuto))
        except: pass
        flash('Configurações salvas.','ok')
        return redirect(url_for('configuracoes'))
    cfg = {
        'email_remetente': get_config('email_remetente') or '',
        'horario_envio':   get_config('horario_envio') or '08:00',
        'alerta_dias_90':  get_config('alerta_dias_90') or '90',
        'alerta_dias_30':  get_config('alerta_dias_30') or '30',
        'alerta_dias_7':   get_config('alerta_dias_7') or '7',
    }
    return render_template('configuracoes.html', cfg=cfg)

@app.route('/api/testar-email', methods=['POST'])
@login_obrigatorio
def testar_email():
    from notificacoes import enviar_email
    conn = get_connection()
    u = conn.execute('SELECT email, nome FROM usuarios WHERE id=?', (session['usuario_id'],)).fetchone()
    conn.close()
    ok = enviar_email(u['email'], u['nome'], 'Grupo Zen — Teste de e-mail',
                      '<p>Se você recebeu este e-mail, a configuração está correta.</p>')
    return jsonify({'ok': ok})

# ─── API DOCUMENTOS ───────────────────────────────────────────────────────────

@app.route('/api/doc/<int:doc_id>/responsavel', methods=['POST'])
@login_obrigatorio
def vincular_responsavel(doc_id):
    data = request.get_json()
    resp_id = data.get('responsavel_id')
    conn = get_connection()
    try:
        conn.execute('INSERT OR IGNORE INTO documento_responsavel (documento_id, responsavel_id) VALUES (?,?)', (doc_id, resp_id))
        conn.commit(); resultado = {'ok': True}
    except Exception as e: resultado = {'ok': False, 'erro': str(e)}
    finally: conn.close()
    return jsonify(resultado)

@app.route('/api/doc/<int:doc_id>/responsavel/<int:resp_id>', methods=['DELETE'])
@login_obrigatorio
def desvincular_responsavel(doc_id, resp_id):
    conn = get_connection()
    conn.execute('DELETE FROM documento_responsavel WHERE documento_id=? AND responsavel_id=?', (doc_id, resp_id))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/doc/<int:doc_id>/protocolo', methods=['POST'])
@login_obrigatorio
def atualizar_protocolo(doc_id):
    data = request.get_json()
    protocolo = data.get('protocolo','').strip() or None
    conn = get_connection()
    conn.execute('UPDATE documentos SET protocolo=? WHERE id=?', (protocolo, doc_id))
    registrar_historico(conn, f'Protocolo atualizado (doc #{doc_id})', documento_id=doc_id)
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/doc/<int:doc_id>/editar', methods=['POST'])
@admin_obrigatorio
def editar_documento(doc_id):
    data = request.get_json()
    protocolo   = data.get('protocolo','').strip() or None
    vencimento  = data.get('vencimento') or None
    observacoes = data.get('observacoes','').strip() or None
    conn = get_connection()
    conn.execute('UPDATE documentos SET protocolo=?, vencimento=?, observacoes=? WHERE id=?',
                 (protocolo, vencimento, observacoes, doc_id))
    registrar_historico(conn, f'Documento #{doc_id} editado', documento_id=doc_id)
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/doc/<int:doc_id>/renovar', methods=['POST'])
@login_obrigatorio
def renovar_documento(doc_id):
    data = request.get_json()
    vencimento = data.get('vencimento')
    if not vencimento:
        return jsonify({'ok': False, 'erro': 'Data obrigatória'})
    conn = get_connection()
    conn.execute('UPDATE documentos SET vencimento=?, status=? WHERE id=?', (vencimento, 'OK', doc_id))
    doc = conn.execute('SELECT d.tipo, e.nome, e.id as emp_id FROM documentos d JOIN empresas e ON e.id=d.empresa_id WHERE d.id=?', (doc_id,)).fetchone()
    if doc:
        registrar_historico(conn, f'Documento "{doc["tipo"]}" renovado — {doc["nome"]}',
                            tipo='tramite', empresa_id=doc['emp_id'], documento_id=doc_id)
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/doc/<int:doc_id>/excluir', methods=['DELETE'])
@admin_obrigatorio
def excluir_documento(doc_id):
    conn = get_connection()
    conn.execute('DELETE FROM documento_responsavel WHERE documento_id=?', (doc_id,))
    conn.execute('DELETE FROM documentos WHERE id=?', (doc_id,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/doc/<int:doc_id>/reenviar-alerta', methods=['POST'])
@admin_obrigatorio
def reenviar_alerta(doc_id):
    from notificacoes import buscar_alertas, montar_html, enviar_email, registrar_historico as reg_hist
    conn = get_connection()
    doc = conn.execute('''
        SELECT d.*, e.nome as empresa FROM documentos d
        JOIN empresas e ON e.id=d.empresa_id WHERE d.id=?
    ''', (doc_id,)).fetchone()
    resps = conn.execute('''SELECT r.nome, r.email FROM responsaveis r
        JOIN documento_responsavel dr ON dr.responsavel_id=r.id
        WHERE dr.documento_id=? AND r.ativo=1''', (doc_id,)).fetchall()
    conn.close()
    if not doc or not resps:
        return jsonify({'ok': False, 'erro': 'Documento sem responsáveis'})
    dias = calcular_dias(doc['vencimento'])
    for r in resps:
        corpo = montar_html(r['nome'], [{'empresa':doc['empresa'],'documento':doc['tipo'],
                                         'vencimento':doc['vencimento'],'dias':dias,'nivel':'vencido' if dias and dias < 0 else 'critico'}])
        enviar_email(r['email'], r['nome'], f'Grupo Zen — Alerta: {doc["tipo"]}', corpo)
    reg_hist(f'Alerta reenviado manualmente: {doc["tipo"]} — {doc["empresa"]}')
    return jsonify({'ok': True})

# ─── EXPORTAR ─────────────────────────────────────────────────────────────────

@app.route('/exportar')
@login_obrigatorio
def exportar():
    import io, zipfile
    from flask import send_file
    conn = get_connection()
    recalcular_todos(conn)
    docs = conn.execute('''
        SELECT e.nome as empresa, c.nome as categoria, d.tipo, d.protocolo,
               d.vencimento, d.status, d.observacoes
        FROM documentos d
        JOIN empresas e ON e.id=d.empresa_id
        JOIN categorias c ON c.id=e.categoria_id
        WHERE e.ativa=1
        ORDER BY d.status, d.vencimento
    ''').fetchall()
    conn.close()

    lines = ['Empresa,Categoria,Documento,Protocolo,Vencimento,Status,Observações']
    for d in docs:
        obs = (d['observacoes'] or '').replace(',',';')
        lines.append(f"{d['empresa']},{d['categoria']},{d['tipo']},{d['protocolo'] or ''},{d['vencimento'] or ''},{d['status']},{obs}")

    output = io.StringIO()
    output.write('\n'.join(lines))
    output.seek(0)
    buf = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    buf.seek(0)
    return send_file(buf, mimetype='text/csv', as_attachment=True,
                     download_name=f'alertsignal_{date.today()}.csv')

# ─── AGENDADOR ────────────────────────────────────────────────────────────────

def iniciar_agendador():
    global scheduler
    scheduler = BackgroundScheduler(timezone='America/Bahia')
    horario = get_config('horario_envio') or '08:00'
    hora, minuto = horario.split(':')
    scheduler.add_job(executar_verificacao_diaria, trigger='cron',
                      hour=int(hora), minute=int(minuto),
                      id='verificacao_diaria', replace_existing=True)
    scheduler.start()

# ─── INICIALIZAÇÃO ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    inserir_configuracoes_padrao()
    criar_admin_padrao()
    xlsx = os.path.join(os.path.dirname(__file__), 'ALVARAS_GRUPO_ZEN.xlsx')
    importar(xlsx)
    iniciar_agendador()
    print('\n AlertSignal rodando em http://localhost:5000')
    print(' Login: admin@grupozen.com.br | Senha: zen2024\n')
    app.run(host='0.0.0.0', port=5000, debug=False)
    
import atexit
atexit.register(lambda: scheduler.shutdown(wait=False))