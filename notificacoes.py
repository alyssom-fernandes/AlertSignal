"""
notificacoes.py — Verifica vencimentos e envia e-mails de alerta.

smtplib é a biblioteca nativa do Python para enviar e-mails via SMTP.
email.mime é usada para montar o conteúdo do e-mail (texto, html, etc).
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date, datetime, timedelta
from database import get_connection, get_config


def calcular_dias(vencimento_str):
    """
    Calcula quantos dias faltam (ou passaram) para uma data de vencimento.
    Valor positivo = ainda não venceu. Valor negativo = já venceu.
    """
    if not vencimento_str:
        return None
    venc = datetime.strptime(vencimento_str, '%Y-%m-%d').date()
    return (venc - date.today()).days


def recalcular_status(dias):
    """Recalcula o status com base nos dias atuais (ignora o status da planilha)."""
    if dias is None:
        return 'NÃO TEM'
    if dias < 0:
        return 'VENCIDO'
    limite_renovar = int(get_config('alerta_dias_30') or 30)
    if dias <= limite_renovar:
        return 'RENOVAR'
    return 'OK'


def buscar_alertas():
    """
    Busca todos os documentos que precisam de alerta hoje.
    Retorna uma lista de dicionários com os dados para o e-mail.
    """
    conn = get_connection()

    limite_90 = int(get_config('alerta_dias_90') or 90)
    limite_30 = int(get_config('alerta_dias_30') or 30)
    limite_7  = int(get_config('alerta_dias_7')  or 7)

    # Busca documentos COM data de vencimento e com responsáveis cadastrados
    # JOIN conecta tabelas relacionadas pela chave estrangeira
    docs = conn.execute('''
        SELECT
            d.id           AS doc_id,
            d.tipo         AS doc_tipo,
            d.vencimento,
            d.status,
            e.nome         AS empresa,
            r.nome         AS responsavel_nome,
            r.email        AS responsavel_email
        FROM documentos d
        JOIN empresas e ON e.id = d.empresa_id
        JOIN documento_responsavel dr ON dr.documento_id = d.id
        JOIN responsaveis r ON r.id = dr.responsavel_id
        WHERE d.vencimento IS NOT NULL
          AND r.ativo = 1
        ORDER BY d.vencimento
    ''').fetchall()

    conn.close()

    alertas = {}  # agrupa por responsável para mandar um e-mail único por pessoa

    for doc in docs:
        dias = calcular_dias(doc['vencimento'])
        if dias is None:
            continue

        nivel = None
        if dias < 0:
            nivel = 'vencido'
        elif dias <= limite_7:
            nivel = 'critico'
        elif dias <= limite_30:
            nivel = 'renovar'
        elif dias <= limite_90:
            nivel = 'antecipado'

        if nivel is None:
            continue  # fora de qualquer janela de alerta

        email = doc['responsavel_email']
        if email not in alertas:
            alertas[email] = {
                'nome': doc['responsavel_nome'],
                'email': email,
                'itens': []
            }

        alertas[email]['itens'].append({
            'empresa': doc['empresa'],
            'documento': doc['doc_tipo'],
            'vencimento': doc['vencimento'],
            'dias': dias,
            'nivel': nivel,
        })

    return list(alertas.values())


def montar_html(nome_destinatario, itens):
    """Monta o corpo do e-mail em HTML com visual limpo."""

    cores = {
        'vencido':    ('#D94F4F', '#2D0000', 'Vencido'),
        'critico':    ('#D4890A', '#2D1A00', 'Vencimento iminente'),
        'renovar':    ('#D4890A', '#2D1A00', 'Renovar'),
        'antecipado': ('#1A8C66', '#001A0F', 'Aviso antecipado'),
    }

    linhas = ''
    for item in itens:
        cor_texto, _, rotulo = cores.get(item['nivel'], ('#888', '#111', ''))
        dias_texto = (
            f"Vencido há {abs(item['dias'])} dia(s)"
            if item['dias'] < 0
            else f"Vence em {item['dias']} dia(s)"
        )
        linhas += f'''
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #1E1E1E;font-size:13px">{item["empresa"]}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #1E1E1E;font-size:13px">{item["documento"]}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #1E1E1E;font-size:13px">{item["vencimento"]}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #1E1E1E;font-size:13px">
            <span style="color:{cor_texto};font-weight:600">{dias_texto}</span>
          </td>
          <td style="padding:10px 12px;border-bottom:1px solid #1E1E1E;font-size:12px;color:{cor_texto}">{rotulo}</td>
        </tr>
        '''

    return f'''
    <html><body style="margin:0;padding:0;background:#080808;font-family:'Segoe UI',Arial,sans-serif;color:#EDEAE5">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#080808;padding:32px 0">
      <tr><td align="center">
        <table width="620" cellpadding="0" cellspacing="0"
               style="background:#101010;border:1px solid #1E1E1E;border-radius:8px;overflow:hidden">
          <tr>
            <td style="background:#8B0000;padding:20px 28px">
              <span style="font-size:18px;font-weight:600;color:#fff">Grupo Zen</span>
              <span style="font-size:12px;color:rgba(255,255,255,.6);display:block;margin-top:2px">
                Controle de Alvarás e Licenças
              </span>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 28px">
              <p style="font-size:14px;margin:0 0 20px">Olá, <strong>{nome_destinatario}</strong>.</p>
              <p style="font-size:13px;color:#888;margin:0 0 20px">
                Abaixo estão os documentos que precisam de atenção hoje:
              </p>
              <table width="100%" cellpadding="0" cellspacing="0"
                     style="border:1px solid #1E1E1E;border-radius:6px;overflow:hidden">
                <thead>
                  <tr style="background:#171717">
                    <th style="padding:8px 12px;font-size:11px;text-align:left;color:#555;font-weight:500;text-transform:uppercase;letter-spacing:.5px">Empresa</th>
                    <th style="padding:8px 12px;font-size:11px;text-align:left;color:#555;font-weight:500;text-transform:uppercase;letter-spacing:.5px">Documento</th>
                    <th style="padding:8px 12px;font-size:11px;text-align:left;color:#555;font-weight:500;text-transform:uppercase;letter-spacing:.5px">Vencimento</th>
                    <th style="padding:8px 12px;font-size:11px;text-align:left;color:#555;font-weight:500;text-transform:uppercase;letter-spacing:.5px">Prazo</th>
                    <th style="padding:8px 12px;font-size:11px;text-align:left;color:#555;font-weight:500;text-transform:uppercase;letter-spacing:.5px">Status</th>
                  </tr>
                </thead>
                <tbody>{linhas}</tbody>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 28px;border-top:1px solid #1E1E1E">
              <p style="font-size:11px;color:#444;margin:0">
                Mensagem automática — AlertSignal · Grupo Zen
              </p>
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
    </body></html>
    '''


def enviar_email(destinatario_email, destinatario_nome, assunto, corpo_html):
    """Envia um e-mail via Gmail SMTP com SSL."""
    remetente = get_config('email_remetente')
    senha     = get_config('email_senha_app')

    if not remetente or not senha:
        print("E-mail não configurado. Pulando envio.")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = assunto
    msg['From']    = f'Grupo Zen Alvarás <{remetente}>'
    msg['To']      = destinatario_email

    # Anexa o corpo como HTML
    msg.attach(MIMEText(corpo_html, 'html', 'utf-8'))

    try:
        # ssl.create_default_context() cria uma conexão segura (criptografada)
        contexto = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=contexto) as server:
            server.login(remetente, senha)
            server.sendmail(remetente, destinatario_email, msg.as_string())
        print(f"E-mail enviado para {destinatario_email}")
        return True
    except Exception as e:
        print(f"Erro ao enviar para {destinatario_email}: {e}")
        return False


def registrar_historico(descricao, empresa_id=None, documento_id=None, tipo='email_enviado'):
    """Grava um registro no histórico do sistema."""
    conn = get_connection()
    conn.execute(
        '''INSERT INTO historico (tipo, descricao, empresa_id, documento_id)
           VALUES (?, ?, ?, ?)''',
        (tipo, descricao, empresa_id, documento_id)
    )
    conn.commit()
    conn.close()


def executar_verificacao_diaria():
    """
    Função principal chamada todo dia pelo agendador.
    Verifica alertas e dispara os e-mails.
    """
    print(f"[{datetime.now().strftime('%H:%M')}] Verificando vencimentos...")

    alertas = buscar_alertas()
    if not alertas:
        print("Nenhum alerta para enviar hoje.")
        return

    for destinatario in alertas:
        qtd = len(destinatario['itens'])
        assunto = f"Grupo Zen — {qtd} documento(s) requerem atenção"
        corpo = montar_html(destinatario['nome'], destinatario['itens'])

        ok = enviar_email(destinatario['email'], destinatario['nome'], assunto, corpo)

        if ok:
            desc = f"Alerta enviado para {destinatario['nome']} ({qtd} documento(s))"
            registrar_historico(desc)
