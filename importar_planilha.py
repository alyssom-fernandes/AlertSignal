"""
importar_planilha.py — Lê o arquivo .xlsx original e popula o banco de dados.

Pandas é uma biblioteca Python especializada em ler e manipular tabelas de dados.
Aqui usamos ela para extrair as informações da planilha que já existia.

Este script é executado UMA VEZ (na primeira rodada do sistema).
Se o banco já tiver dados, ele pula a importação automaticamente.
"""

import pandas as pd
import re
from datetime import datetime
from database import get_connection, init_db

# Mapeamento: nome da aba no Excel → nome da categoria no sistema
ABAS = {
    'POSTOS':       'Postos',
    'RESTAURANTES': 'Restaurantes',
    'HOLDINGS':     'Holdings',
    'LOCADORAS':    'Locadoras',
    'AUTOPECAS':    'Autopeças',
    'TRRs':         'TRRs',
    'HOTEIS':       'Hotéis',
}

# Tipos de documento que existem em cada empresa (na ordem da planilha)
TIPOS_DOC = [
    'AVCB',
    'Licença de Operação',
    'LAC - Licença de Transportes',
    'Alvará Municipal',
    'Alvará Sanitário',
    'FEASPOL',
    'CADASTUR',
    'IPTU',
    'Alvará Policial',
]


def extrair_nome_cnpj(celula_texto):
    """
    A planilha guarda o nome e CNPJ juntos numa célula com quebras de linha.
    Ex: "POSTO ROSARIO LTDA\nCNPJ: 13.615.307/0001-49"
    
    Aqui separamos os dois usando expressão regular (regex).
    re.search busca um padrão dentro de um texto.
    """
    texto = str(celula_texto).strip()

    # Procura o padrão de CNPJ (dois dígitos, ponto, etc.)
    match_cnpj = re.search(r'CNPJ:\s*([\d./-]+)', texto)
    cnpj = match_cnpj.group(1).strip() if match_cnpj else None

    # Remove a parte do CNPJ para ficar só com o nome
    nome = re.sub(r'\n?CNPJ:.*', '', texto).replace('\n', ' ').strip()
    nome = re.sub(r'\s+', ' ', nome)  # remove espaços duplos

    return nome, cnpj


def formatar_data(valor):
    """
    Converte a data que o pandas leu (pode ser datetime ou NaN)
    para o formato de texto ISO: "2026-05-07".
    Retorna None se não houver data.
    """
    if pd.isna(valor) or valor is None:
        return None
    if isinstance(valor, datetime):
        # Datas muito antigas são lixo da planilha (células "NÃO TEM")
        if valor.year < 2000:
            return None
        return valor.strftime('%Y-%m-%d')
    return None


def importar(caminho_xlsx):
    """
    Função principal: lê o Excel e popula o banco.
    """
    conn = get_connection()
    c = conn.cursor()

    # Verifica se já existe dados importados
    total = c.execute('SELECT COUNT(*) FROM empresas').fetchone()[0]
    if total > 0:
        print("Banco já populado. Pulando importação.")
        conn.close()
        return

    print("Iniciando importação da planilha...")

    for aba_excel, nome_categoria in ABAS.items():
        # Insere a categoria (Postos, Restaurantes, etc.)
        c.execute('INSERT OR IGNORE INTO categorias (nome) VALUES (?)', (nome_categoria,))
        cat_id = c.execute('SELECT id FROM categorias WHERE nome = ?',
                           (nome_categoria,)).fetchone()['id']

        # Lê a aba sem cabeçalho — header=None trata tudo como dados brutos
        df = pd.read_excel(caminho_xlsx, sheet_name=aba_excel, header=None)

        # A coluna 4 (índice 4) tem os dados principais
        # Percorremos linha por linha procurando células com "CNPJ:"
        empresa_id = None
        doc_index = 0  # controla qual documento estamos lendo dentro de uma empresa

        for i, row in df.iterrows():
            celula = str(row[4]) if not pd.isna(row[4]) else ''

            # Se a célula contém "CNPJ:" é o cabeçalho de uma nova empresa
            if 'CNPJ:' in celula:
                nome, cnpj = extrair_nome_cnpj(celula)
                c.execute(
                    'INSERT INTO empresas (nome, cnpj, categoria_id) VALUES (?, ?, ?)',
                    (nome, cnpj, cat_id)
                )
                # lastrowid = id da linha que acabamos de inserir
                empresa_id = c.lastrowid
                doc_index = 0
                print(f"  + {nome_categoria}: {nome}")
                continue

            # Se é um tipo de documento conhecido, lemos seus dados
            if empresa_id and celula.strip().upper() in [t.upper() for t in TIPOS_DOC]:
                # Normaliza o nome do documento
                tipo_normalizado = next(
                    (t for t in TIPOS_DOC if t.upper() == celula.strip().upper()),
                    celula.strip()
                )
                # Coluna 5 = protocolo, coluna 8 = data, coluna 10 = status
                protocolo = str(row[5]).strip() if not pd.isna(row[5]) else None
                if protocolo in ('nan', 'None', ''):
                    protocolo = None
                vencimento = formatar_data(row[8])
                status_raw = str(row[10]).strip().upper() if not pd.isna(row[10]) else 'NÃO TEM'

                # Normaliza status
                status_map = {
                    'OK': 'OK',
                    'RENOVAR': 'RENOVAR',
                    'VENCIDO': 'VENCIDO',
                    'NÃO TEM': 'NÃO TEM',
                    'NAO TEM': 'NÃO TEM',
                }
                status = status_map.get(status_raw, 'NÃO TEM')

                c.execute(
                    '''INSERT INTO documentos (empresa_id, tipo, protocolo, vencimento, status)
                       VALUES (?, ?, ?, ?, ?)''',
                    (empresa_id, tipo_normalizado, protocolo, vencimento, status)
                )
                doc_index += 1

    conn.commit()
    conn.close()
    print("Importação concluída.")


if __name__ == '__main__':
    # Permite rodar direto: python importar_planilha.py
    import os
    init_db()
    xlsx = os.path.join(os.path.dirname(__file__), 'ALVARAS_GRUPO_ZEN.xlsx')
    importar(xlsx)
