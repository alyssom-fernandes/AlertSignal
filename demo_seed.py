"""
demo_seed.py — Popula o banco com dados fictícios para demonstração.

Execute UMA VEZ após inicializar o banco:
    python demo_seed.py

Para resetar e recriar os dados demo:
    python demo_seed.py --reset
"""

import sys
import os
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(__file__))
from database import get_connection, init_db

def delta(dias):
    return (date.today() + timedelta(days=dias)).strftime('%Y-%m-%d')

CATEGORIAS = [
    'Postos',
    'Restaurantes',
    'Holdings',
    'Locadoras',
    'Hotéis',
]

EMPRESAS = [
    # (nome, cnpj, categoria)
    ('Posto Vitória Ltda',          '12.345.678/0001-90', 'Postos'),
    ('Posto Central Combustíveis',  '23.456.789/0001-01', 'Postos'),
    ('Posto Estrela do Sul',        '34.567.890/0001-12', 'Postos'),
    ('Restaurante Sabor & Arte',    '45.678.901/0001-23', 'Restaurantes'),
    ('Churrascaria Gaúcha Ltda',    '56.789.012/0001-34', 'Restaurantes'),
    ('Bistrô da Praça',             '67.890.123/0001-45', 'Restaurantes'),
    ('Holding Empresarial Norte',   '78.901.234/0001-56', 'Holdings'),
    ('Grupo Patrimonial Sul Ltda',  '89.012.345/0001-67', 'Holdings'),
    ('Locadora Rápida Veículos',    '90.123.456/0001-78', 'Locadoras'),
    ('Rent Express Ltda',           '01.234.567/0001-89', 'Locadoras'),
    ('Hotel Panorama',              '11.222.333/0001-44', 'Hotéis'),
    ('Pousada Serra Verde',         '22.333.444/0001-55', 'Hotéis'),
]

# Documentos por empresa: (tipo, protocolo, dias_para_vencimento)
# dias negativo = já vencido, positivo = vence em X dias
DOCUMENTOS_TEMPLATE = [
    ('AVCB',                        'AVCB-2024-001',  -15),   # vencido
    ('Licença de Operação',         'LO-2024-042',     8),    # crítico
    ('LAC - Licença de Transportes','LAC-2023-789',   -45),   # vencido
    ('Alvará Municipal',            'AM-2024-156',    25),    # renovar
    ('Alvará Sanitário',            'AS-2024-203',    180),   # ok
    ('FEASPOL',                     None,             -5),    # vencido
    ('CADASTUR',                    'CAD-2024-077',   365),   # ok
    ('IPTU',                        'IPTU-2024',      90),    # ok
    ('Alvará Policial',             'AP-2024-033',    12),    # crítico
]

RESPONSAVEIS = [
    ('Carlos Mendes',     'carlos.mendes@demo.com'),
    ('Ana Paula Souza',   'ana.paula@demo.com'),
    ('Roberto Lima',      'roberto.lima@demo.com'),
    ('Fernanda Costa',    'fernanda.costa@demo.com'),
]

HISTORICO_ITEMS = [
    ('email_enviado', 'Alerta enviado para Carlos Mendes (3 documentos)'),
    ('email_enviado', 'Alerta enviado para Ana Paula Souza (1 documento)'),
    ('tramite',       'Documento "AVCB" renovado — Posto Vitória Ltda'),
    ('tramite',       'Protocolo atualizado (doc #3)'),
    ('email_enviado', 'Alerta enviado para Roberto Lima (2 documentos)'),
    ('tramite',       'Documento "Alvará Municipal" renovado — Restaurante Sabor & Arte'),
    ('tramite',       'Protocolo atualizado (doc #7)'),
    ('email_enviado', 'Alerta de teste enviado — configuração verificada'),
]


def resetar(conn):
    tabelas = ['documento_responsavel', 'historico', 'documentos',
               'responsaveis', 'empresas', 'categorias', 'usuarios']
    for t in tabelas:
        conn.execute(f'DELETE FROM {t}')
    conn.commit()
    print('Banco resetado.')


def seed():
    init_db()
    conn = get_connection()

    reset = '--reset' in sys.argv
    if reset:
        resetar(conn)

    # Verifica se já tem dados
    total = conn.execute('SELECT COUNT(*) FROM empresas').fetchone()[0]
    if total > 0 and not reset:
        print('Banco já tem dados. Use --reset para recriar.')
        conn.close()
        return

    print('Populando banco com dados de demonstração...')

    # ── Usuário admin demo ────────────────────────────────────────────────────
    conn.execute('''
        INSERT OR IGNORE INTO usuarios (nome, email, senha, nivel)
        VALUES (?, ?, ?, ?)
    ''', ('Administrador', 'admin@alertsignal.com',
          generate_password_hash('demo2024'), 'admin'))

    # ── Categorias ────────────────────────────────────────────────────────────
    cat_ids = {}
    for nome in CATEGORIAS:
        conn.execute('INSERT OR IGNORE INTO categorias (nome) VALUES (?)', (nome,))
        row = conn.execute('SELECT id FROM categorias WHERE nome=?', (nome,)).fetchone()
        cat_ids[nome] = row['id']
    print(f'  {len(CATEGORIAS)} categorias criadas')

    # ── Empresas ──────────────────────────────────────────────────────────────
    emp_ids = {}
    for nome, cnpj, cat in EMPRESAS:
        conn.execute(
            'INSERT INTO empresas (nome, cnpj, categoria_id) VALUES (?,?,?)',
            (nome, cnpj, cat_ids[cat])
        )
        emp_ids[nome] = conn.execute(
            'SELECT id FROM empresas WHERE nome=?', (nome,)
        ).fetchone()['id']
    print(f'  {len(EMPRESAS)} empresas criadas')

    # ── Documentos ────────────────────────────────────────────────────────────
    doc_count = 0
    doc_ids_por_empresa = {}
    for emp_nome, emp_id in emp_ids.items():
        doc_ids_por_empresa[emp_id] = []
        # Distribui documentos de forma variada por empresa
        # Nem toda empresa tem todos os documentos
        cat_emp = next(c for n, _, c in EMPRESAS if n == emp_nome)

        # Postos e Restaurantes têm mais documentos
        qtd = len(DOCUMENTOS_TEMPLATE) if cat_emp in ('Postos', 'Restaurantes') else 5

        for tipo, protocolo, dias in DOCUMENTOS_TEMPLATE[:qtd]:
            vencimento = delta(dias)

            if dias < 0:
                status = 'VENCIDO'
            elif dias <= 30:
                status = 'RENOVAR'
            else:
                status = 'OK'

            conn.execute(
                '''INSERT INTO documentos
                   (empresa_id, tipo, protocolo, vencimento, status)
                   VALUES (?,?,?,?,?)''',
                (emp_id, tipo, protocolo, vencimento, status)
            )
            doc_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            doc_ids_por_empresa[emp_id].append(doc_id)
            doc_count += 1

    print(f'  {doc_count} documentos criados')

    # ── Responsáveis ─────────────────────────────────────────────────────────
    resp_ids = []
    for nome, email in RESPONSAVEIS:
        conn.execute(
            'INSERT OR IGNORE INTO responsaveis (nome, email) VALUES (?,?)',
            (nome, email)
        )
        row = conn.execute(
            'SELECT id FROM responsaveis WHERE email=?', (email,)
        ).fetchone()
        resp_ids.append(row['id'])
    print(f'  {len(RESPONSAVEIS)} responsáveis criados')

    # ── Vínculos documento-responsável ────────────────────────────────────────
    vinculos = 0
    for i, (emp_nome, emp_id) in enumerate(emp_ids.items()):
        docs = doc_ids_por_empresa[emp_id]
        resp = resp_ids[i % len(resp_ids)]
        for doc_id in docs[:3]:  # vincula até 3 docs por responsável
            conn.execute(
                'INSERT OR IGNORE INTO documento_responsavel VALUES (?,?)',
                (doc_id, resp)
            )
            vinculos += 1
    print(f'  {vinculos} vínculos documento-responsável criados')

    # ── Histórico ─────────────────────────────────────────────────────────────
    for tipo, descricao in HISTORICO_ITEMS:
        conn.execute(
            'INSERT INTO historico (tipo, descricao) VALUES (?,?)',
            (tipo, descricao)
        )
    print(f'  {len(HISTORICO_ITEMS)} registros de histórico criados')

    # ── Configurações padrão ──────────────────────────────────────────────────
    defaults = [
        ('email_remetente', ''),
        ('email_senha_app', ''),
        ('horario_envio',   '08:00'),
        ('alerta_dias_90',  '90'),
        ('alerta_dias_30',  '30'),
        ('alerta_dias_7',   '7'),
    ]
    for chave, valor in defaults:
        conn.execute(
            'INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES (?,?)',
            (chave, valor)
        )

    conn.commit()
    conn.close()

    print('\nDemo populado com sucesso!')
    print('Login: admin@alertsignal.com  |  Senha: demo2024')
    print('\nEstatísticas:')

    conn2 = get_connection()
    vencidos = conn2.execute("SELECT COUNT(*) FROM documentos WHERE status='VENCIDO'").fetchone()[0]
    renovar  = conn2.execute("SELECT COUNT(*) FROM documentos WHERE status='RENOVAR'").fetchone()[0]
    ok       = conn2.execute("SELECT COUNT(*) FROM documentos WHERE status='OK'").fetchone()[0]
    conn2.close()

    print(f'  Vencidos:  {vencidos}')
    print(f'  Renovar:   {renovar}')
    print(f'  OK:        {ok}')


if __name__ == '__main__':
    seed()
