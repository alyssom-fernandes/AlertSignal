"""
demo_seed.py: dados fictícios para o modo demonstração.

Grava SEMPRE num banco separado (demo.db), nunca no zen.db de uso real.
O app chama popular() ao subir com --demo; também dá para rodar direto:

    python demo_seed.py            # recria o demo.db com o cenário completo
    python demo_seed.py --vazio    # recria só com os usuários (estados vazios)

As datas são relativas ao dia em que roda, então sempre há documentos
vencidos, a renovar e em dia. O sorteio usa semente fixa: a mesma data
gera sempre os mesmos dados.
"""

import os
import random
import sys
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database
from database import get_connection, init_db

SENHA_DEMO = 'demo2024'

USUARIOS = [
    # (nome, email, nivel)
    ('Administrador', 'admin@alertsignal.com',        'admin'),
    ('Marina Duarte', 'visualizador@alertsignal.com', 'visualizador'),
]

CATEGORIAS = ['Postos', 'Restaurantes', 'Holdings', 'Locadoras', 'Hotéis', 'TRRs', 'Autopeças']

# Documentos que cada ramo costuma ter
DOCS_POR_CATEGORIA = {
    'Postos':       ['AVCB', 'Licença de Operação', 'LAC - Licença de Transportes', 'Alvará Municipal',
                     'Alvará Sanitário', 'FEASPOL', 'IPTU', 'Alvará Policial'],
    'Restaurantes': ['AVCB', 'Licença de Operação', 'Alvará Municipal', 'Alvará Sanitário', 'IPTU'],
    'Holdings':     ['AVCB', 'Alvará Municipal', 'IPTU'],
    'Locadoras':    ['AVCB', 'LAC - Licença de Transportes', 'Alvará Municipal', 'IPTU'],
    'Hotéis':       ['AVCB', 'Alvará Municipal', 'Alvará Sanitário', 'CADASTUR', 'IPTU'],
    'TRRs':         ['AVCB', 'Licença de Operação', 'LAC - Licença de Transportes', 'Alvará Municipal',
                     'FEASPOL', 'Alvará Policial'],
    'Autopeças':    ['AVCB', 'Alvará Municipal', 'IPTU'],
}

EMPRESAS = [
    # (nome, cnpj, categoria, ativa, tem_documentos)
    ('Posto Vitória Ltda',                                         '12.345.678/0001-90', 'Postos',       1, True),
    ('Posto Central Combustíveis',                                 '23.456.789/0001-01', 'Postos',       1, True),
    ('Auto Posto Rodovia BR-101 Combustíveis e Conveniência Ltda', '34.567.890/0001-12', 'Postos',       1, True),
    ('Posto Estrela do Sul',                                       '45.678.901/0001-23', 'Postos',       1, True),
    ('Restaurante Sabor & Arte',                                   '56.789.012/0001-34', 'Restaurantes', 1, True),
    ("Cantina D'Ítalia",                                           '67.890.123/0001-45', 'Restaurantes', 1, True),
    ('Churrascaria Gaúcha Ltda',                                   '78.901.234/0001-56', 'Restaurantes', 1, True),
    ('Bistrô da Praça',                                            '89.012.345/0001-67', 'Restaurantes', 1, True),
    ('Holding Empresarial Norte',                                  '90.123.456/0001-78', 'Holdings',     1, True),
    ('Grupo Patrimonial Sul Ltda',                                 '01.234.567/0001-89', 'Holdings',     1, True),
    ('Locadora Rápida Veículos',                                   '11.222.333/0001-44', 'Locadoras',    1, True),
    ('Rent Express Ltda',                                          '22.333.444/0001-55', 'Locadoras',    1, True),
    ('Hotel Panorama',                                             '33.444.555/0001-66', 'Hotéis',       1, True),
    ('Pousada Serra Verde',                                        '44.555.666/0001-77', 'Hotéis',       1, True),
    ('TRR Combustíveis do Vale',                                   '55.666.777/0001-88', 'TRRs',         1, True),
    ('Nova Distribuidora TRR',                                     '66.777.888/0001-99', 'TRRs',         1, False),
    ('Autopeças Avenida',                                          '77.888.999/0001-00', 'Autopeças',    0, True),
]

RESPONSAVEIS = [
    ('Carlos Mendes',   'carlos.mendes@example.com'),
    ('Ana Paula Souza', 'ana.souza@example.com'),
    ('Roberto Lima',    'roberto.lima@example.com'),
    ('Fernanda Costa',  'fernanda.costa@example.com'),
    ('Juliana Ribeiro', 'juliana.ribeiro@example.com'),
]

PREFIXOS = {
    'AVCB': 'AVCB', 'Licença de Operação': 'LO', 'LAC - Licença de Transportes': 'LAC',
    'Alvará Municipal': 'AM', 'Alvará Sanitário': 'AS', 'FEASPOL': 'FSP',
    'CADASTUR': 'CAD', 'IPTU': 'IPTU', 'Alvará Policial': 'AP',
}

OBSERVACOES = [
    'Vistoria do Corpo de Bombeiros agendada.',
    'Aguardando boleto da taxa na prefeitura.',
    'Protocolo em análise na Vigilância Sanitária.',
    'Renovação depende do laudo elétrico atualizado.',
    'Pago em parcela única.',
    'Contato na prefeitura: setor de licenciamento, ramal 214.',
]

# Faixas de prazo, em dias a partir de hoje, e o peso de cada uma
FAIXAS = [
    ((-120, -1), 15),   # vencido
    ((0, 7),      6),   # crítico
    ((8, 30),    14),   # a renovar
    ((31, 90),   16),   # aviso antecipado
    ((91, 540),  41),   # em dia
    (None,        8),   # sem data (NÃO TEM)
]


def _status(dias):
    if dias is None:
        return 'NÃO TEM'
    if dias < 0:
        return 'VENCIDO'
    if dias <= 30:
        return 'RENOVAR'
    return 'OK'


def _limpar(conn):
    for t in ['documento_responsavel', 'historico', 'documentos', 'responsaveis',
              'empresas', 'categorias', 'usuarios', 'configuracoes']:
        conn.execute(f'DELETE FROM {t}')
    # Recomeça a numeração, para que /empresa/1 seja sempre a mesma empresa
    conn.execute('DELETE FROM sqlite_sequence')


def popular(cenario='completo'):
    """Apaga o banco de demonstração atual e grava o cenário pedido.

    cenario: 'completo' (padrão) ou 'vazio' (só usuários e configurações).
    """
    if os.path.basename(database.DB_PATH).lower() == 'zen.db':
        raise RuntimeError('demo_seed se recusa a gravar no zen.db (banco de uso real).')

    init_db()
    conn = get_connection()
    _limpar(conn)

    hoje = date.today()
    sorteio = random.Random(hoje.toordinal())

    senha = generate_password_hash(SENHA_DEMO)
    for nome, email, nivel in USUARIOS:
        conn.execute('INSERT INTO usuarios (nome, email, senha, nivel) VALUES (?,?,?,?)',
                     (nome, email, senha, nivel))

    for chave, valor in [('email_remetente', 'alertas@example.com'), ('email_senha_app', ''),
                         ('horario_envio', '08:00'), ('alerta_dias_90', '90'),
                         ('alerta_dias_30', '30'), ('alerta_dias_7', '7')]:
        conn.execute('INSERT INTO configuracoes (chave, valor) VALUES (?,?)', (chave, valor))

    if cenario == 'vazio':
        conn.commit()
        conn.close()
        return

    cat_ids = {}
    for nome in CATEGORIAS:
        cur = conn.execute('INSERT INTO categorias (nome) VALUES (?)', (nome,))
        cat_ids[nome] = cur.lastrowid

    resp_ids = []
    for nome, email in RESPONSAVEIS:
        cur = conn.execute('INSERT INTO responsaveis (nome, email) VALUES (?,?)', (nome, email))
        resp_ids.append(cur.lastrowid)

    faixas, pesos = zip(*FAIXAS)
    documentos = []   # (doc_id, empresa_id, empresa, tipo)
    for i, (nome, cnpj, cat, ativa, tem_docs) in enumerate(EMPRESAS):
        cur = conn.execute('INSERT INTO empresas (nome, cnpj, categoria_id, ativa) VALUES (?,?,?,?)',
                           (nome, cnpj, cat_ids[cat], ativa))
        emp_id = cur.lastrowid
        if not tem_docs:
            continue
        principal = resp_ids[i % len(resp_ids)]
        for tipo in DOCS_POR_CATEGORIA[cat]:
            faixa = sorteio.choices(faixas, pesos)[0]
            dias = None if faixa is None else sorteio.randint(*faixa)
            vencimento = None if dias is None else (hoje + timedelta(days=dias)).isoformat()
            protocolo = None
            if sorteio.random() > 0.15:
                ano = (hoje + timedelta(days=(dias or 0) - 365)).year
                protocolo = f'{PREFIXOS[tipo]}-{ano}-{sorteio.randint(10, 9999):04d}'
            obs = sorteio.choice(OBSERVACOES) if sorteio.random() < 0.2 else None
            cur = conn.execute(
                'INSERT INTO documentos (empresa_id, tipo, protocolo, vencimento, status, observacoes) '
                'VALUES (?,?,?,?,?,?)', (emp_id, tipo, protocolo, vencimento, _status(dias), obs))
            doc_id = cur.lastrowid
            documentos.append((doc_id, emp_id, nome, tipo))

            sorte = sorteio.random()
            if sorte < 0.08:
                continue   # documento ainda sem responsável
            conn.execute('INSERT INTO documento_responsavel VALUES (?,?)', (doc_id, principal))
            if sorte > 0.7:
                outro = sorteio.choice([r for r in resp_ids if r != principal])
                conn.execute('INSERT INTO documento_responsavel VALUES (?,?)', (doc_id, outro))

    # Histórico dos últimos 75 dias, do mais antigo para o mais novo
    admin_id = 1
    eventos = []
    for _ in range(64):
        quando = datetime.combine(hoje - timedelta(days=sorteio.randint(0, 75)), datetime.min.time()) \
            + timedelta(hours=sorteio.randint(8, 18), minutes=sorteio.randint(0, 59))
        doc_id, emp_id, empresa, tipo = sorteio.choice(documentos)
        tipo_evento = sorteio.choices(['email', 'renovado', 'protocolo', 'editado', 'vinculo'],
                                      [30, 20, 20, 15, 15])[0]
        if tipo_evento == 'email':
            nome = sorteio.choice(RESPONSAVEIS)[0]
            qtd = sorteio.randint(1, 4)
            eventos.append((quando, 'email_enviado',
                            f'Alerta enviado para {nome} ({qtd} documento{"s" if qtd > 1 else ""})',
                            None, None, None))
            continue
        texto = {
            'renovado':  f'Documento "{tipo}" renovado: {empresa}',
            'protocolo': f'Protocolo atualizado: {tipo}, {empresa}',
            'editado':   f'Documento "{tipo}" editado: {empresa}',
            'vinculo':   f'{sorteio.choice(RESPONSAVEIS)[0]} agora responde por {tipo}, {empresa}',
        }[tipo_evento]
        eventos.append((quando, 'tramite', texto, emp_id, doc_id, admin_id))

    for quando, tipo, texto, emp_id, doc_id, uid in sorted(eventos, key=lambda e: e[0]):
        conn.execute('INSERT INTO historico (tipo, descricao, empresa_id, documento_id, usuario_id, criado_em) '
                     'VALUES (?,?,?,?,?,?)', (tipo, texto, emp_id, doc_id, uid, quando.strftime('%Y-%m-%d %H:%M:%S')))

    conn.commit()
    conn.close()


if __name__ == '__main__':
    database.usar_banco(os.environ.get('ALERTSIGNAL_BANCO_DEMO')
                        or os.path.join(database.PASTA, 'demo.db'))
    popular('vazio' if '--vazio' in sys.argv else 'completo')
    conn = get_connection()
    contagem = dict(conn.execute('SELECT status, COUNT(*) FROM documentos GROUP BY status').fetchall())
    conn.close()
    print(f'Banco de demonstração gravado em {database.DB_PATH}')
    print(f'Documentos por status: {contagem}')
    print(f'Entrar: admin@alertsignal.com ou visualizador@alertsignal.com, senha {SENHA_DEMO}')
