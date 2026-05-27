import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'zen.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        nome      TEXT NOT NULL,
        email     TEXT UNIQUE NOT NULL,
        senha     TEXT NOT NULL,
        nivel     TEXT NOT NULL DEFAULT 'admin',
        ativo     INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS categorias (
        id   INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS empresas (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        nome         TEXT NOT NULL,
        cnpj         TEXT,
        categoria_id INTEGER REFERENCES categorias(id),
        ativa        INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS documentos (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id   INTEGER REFERENCES empresas(id),
        tipo         TEXT NOT NULL,
        protocolo    TEXT,
        vencimento   TEXT,
        status       TEXT DEFAULT 'OK',
        observacoes  TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS responsaveis (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        nome  TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        ativo INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS documento_responsavel (
        documento_id   INTEGER REFERENCES documentos(id),
        responsavel_id INTEGER REFERENCES responsaveis(id),
        PRIMARY KEY (documento_id, responsavel_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS historico (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo         TEXT NOT NULL,
        descricao    TEXT NOT NULL,
        empresa_id   INTEGER REFERENCES empresas(id),
        documento_id INTEGER REFERENCES documentos(id),
        usuario_id   INTEGER REFERENCES usuarios(id),
        criado_em    TEXT DEFAULT (datetime('now','localtime'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS configuracoes (
        chave TEXT PRIMARY KEY,
        valor TEXT
    )''')

    # Migrações seguras para bancos existentes
    migrations = [
        'ALTER TABLE usuarios ADD COLUMN nivel TEXT NOT NULL DEFAULT "admin"',
        'ALTER TABLE documentos ADD COLUMN observacoes TEXT',
        'ALTER TABLE historico ADD COLUMN usuario_id INTEGER REFERENCES usuarios(id)',
        "ALTER TABLE historico ADD COLUMN criado_em TEXT DEFAULT (datetime('now','localtime'))",
    ]
    for m in migrations:
        try: c.execute(m)
        except: pass

    conn.commit()
    conn.close()

def inserir_configuracoes_padrao():
    conn = get_connection()
    c = conn.cursor()
    defaults = [
        ('email_remetente', ''),
        ('email_senha_app', ''),
        ('horario_envio', '08:00'),
        ('alerta_dias_90', '90'),
        ('alerta_dias_30', '30'),
        ('alerta_dias_7', '7'),
    ]
    for chave, valor in defaults:
        c.execute('INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES (?, ?)', (chave, valor))
    conn.commit()
    conn.close()

def get_config(chave):
    conn = get_connection()
    row = conn.execute('SELECT valor FROM configuracoes WHERE chave = ?', (chave,)).fetchone()
    conn.close()
    return row['valor'] if row else None

def set_config(chave, valor):
    conn = get_connection()
    conn.execute('INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)', (chave, valor))
    conn.commit()
    conn.close()
