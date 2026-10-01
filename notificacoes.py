"""
notificacoes.py: verifica vencimentos e envia e-mails de alerta.

smtplib é a biblioteca nativa do Python para enviar e-mails via SMTP.
email.mime é usada para montar o conteúdo do e-mail (texto, html, etc).
"""

import os
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
    try:
        venc = datetime.strptime(vencimento_str, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None
    return (venc - date.today()).days


def recalcular_status(dias, limite_renovar=None):
    """Recalcula o status com base nos dias atuais (ignora o status da planilha)."""
    if dias is None:
        return 'NÃO TEM'
    if dias < 0:
        return 'VENCIDO'
    if limite_renovar is None:
        limite_renovar = int(get_config('alerta_dias_30') or 30)
    if dias <= limite_renovar:
        return 'RENOVAR'
    return 'OK'


def nivel_alerta(dias):
    """Nível do alerta pelas regras configuradas (None = fora de qualquer janela)."""
    if dias is None:
        return None
    if dias < 0:
        return 'vencido'
    if dias <= int(get_config('alerta_dias_7') or 7):
        return 'critico'
    if dias <= int(get_config('alerta_dias_30') or 30):
        return 'renovar'
    if dias <= int(get_config('alerta_dias_90') or 90):
        return 'antecipado'
    return None


def buscar_alertas():
    """
    Busca todos os documentos que precisam de alerta hoje.
    Retorna uma lista de dicionários com os dados para o e-mail.
    """
    conn = get_connection()


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
          AND e.ativa = 1
        ORDER BY d.vencimento
    ''').fetchall()

    conn.close()

    alertas = {}  # agrupa por responsável para mandar um e-mail único por pessoa

    for doc in docs:
        dias = calcular_dias(doc['vencimento'])
        if dias is None:
            continue

        nivel = nivel_alerta(dias)

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


NIVEIS_EMAIL = [
    # nível, título do grupo, cor do texto, cor do fundo, rótulo da etiqueta
    ('vencido',    'Vencidos',                 '#B42318', '#FDECEC', 'Vencido'),
    ('critico',    'Vencem nos próximos dias', '#B54708', '#FFEAD5', 'Vence em breve'),
    ('renovar',    'Hora de renovar',          '#8A5300', '#FEF4E2', 'Renovar'),
    ('antecipado', 'Avisos antecipados',       '#067647', '#E8F7EF', 'Aviso antecipado'),
]


def _prazo(dias):
    if dias < -1: return f'Vencido há {abs(dias)} dias'
    if dias == -1: return 'Venceu ontem'
    if dias == 0: return 'Vence hoje'
    if dias == 1: return 'Vence amanhã'
    return f'Vence em {dias} dias'


def _data_br(iso):
    try: return datetime.strptime(iso, '%Y-%m-%d').strftime('%d/%m/%Y')
    except (TypeError, ValueError): return iso or ''


def _resumo(total):
    return f'{total}\u00a0documento precisa' if total == 1 else f'{total}\u00a0documentos precisam'


def montar_html(nome_destinatario, itens, url_sistema=None):
    """Monta o corpo do e-mail em HTML.

    Fundo claro, tabelas e cores também em atributos (bgcolor), que o Gmail,
    o Outlook e os apps de celular mostram do mesmo jeito. Todo texto vindo
    do banco é escapado antes de entrar no HTML. Com url_sistema, o e-mail
    ganha um botão para abrir o AlertSignal.
    """
    from html import escape

    grupos = ''
    for nivel, titulo, cor, fundo, rotulo in NIVEIS_EMAIL:
        doc_nivel = [i for i in itens if i['nivel'] == nivel]
        if not doc_nivel:
            continue
        grupos += f"""
          <tr><td colspan="2" style="padding:18px 14px 6px;font-size:12px;font-weight:700;color:{cor};text-transform:uppercase;letter-spacing:.6px">{titulo} ({len(doc_nivel)})</td></tr>"""
        for item in doc_nivel:
            grupos += f"""
          <tr>
            <td style="padding:12px 14px;border-top:1px solid #EAEAEE;vertical-align:top">
              <div style="font-size:14px;font-weight:600;color:#111113">{escape(item["documento"])}</div>
              <div style="font-size:13px;color:#5B5B63;margin-top:2px">{escape(item["empresa"])}</div>
            </td>
            <td align="right" style="padding:12px 14px;border-top:1px solid #EAEAEE;vertical-align:top;white-space:nowrap">
              <table role="presentation" cellpadding="0" cellspacing="0" align="right"><tr>
                <td bgcolor="{fundo}" style="background:{fundo};color:{cor};font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px">{rotulo}</td>
              </tr></table>
              <div style="clear:both;font-size:13px;color:#111113;padding-top:6px">{escape(_prazo(item["dias"]))}</div>
              <div style="font-size:12px;color:#5B5B63;margin-top:2px">{_data_br(item["vencimento"])}</div>
            </td>
          </tr>"""

    if not itens:
        grupos = """
          <tr><td colspan="2" style="padding:16px 14px;border-top:1px solid #EAEAEE;font-size:13px;color:#5B5B63">
            Nenhum documento precisa de atenção hoje.
          </td></tr>"""

    botao = ''
    if url_sistema:
        botao = f"""
        <tr>
          <td style="padding:4px 24px 24px">
            <table role="presentation" cellpadding="0" cellspacing="0"><tr>
              <td bgcolor="#E03030" style="background:#E03030;border-radius:8px">
                <a href="{escape(url_sistema)}" style="display:inline-block;padding:11px 20px;font-size:14px;font-weight:700;color:#FFFFFF;text-decoration:none">Abrir no AlertSignal</a>
              </td>
            </tr></table>
          </td>
        </tr>"""

    total = len(itens)
    previa = f'{_resumo(total)} de atenção.' if total else 'Nenhum documento precisa de atenção hoje.'
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light"><title>AlertSignal</title></head>
<body style="margin:0;padding:0;background:#F3F3F5;font-family:'Segoe UI',Roboto,Arial,sans-serif;color:#111113">
  <div style="display:none;max-height:0;overflow:hidden">{escape(previa)}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#F3F3F5" style="background:#F3F3F5;padding:24px 12px">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF"
             style="max-width:620px;background:#FFFFFF;border:1px solid #E2E2E6;border-top:4px solid #E03030;border-radius:12px">
        <tr>
          <td style="padding:22px 24px 6px">
            <div style="font-size:18px;font-weight:700;color:#111113">AlertSignal</div>
            <div style="font-size:12px;color:#5B5B63;margin-top:2px">Controle de alvarás e licenças</div>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 24px 0">
            <p style="font-size:15px;margin:0 0 6px">Olá, <strong>{escape(nome_destinatario)}</strong>.</p>
            <p style="font-size:14px;color:#3F3F46;margin:0">{previa}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:0 10px 14px">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{grupos}
            </table>
          </td>
        </tr>{botao}
        <tr>
          <td bgcolor="#FAFAFB" style="padding:14px 24px;background:#FAFAFB;border-top:1px solid #EAEAEE;border-radius:0 0 12px 12px">
            <p style="font-size:12px;color:#5B5B63;margin:0">
              Mensagem automática do AlertSignal. Você recebe porque está cadastrado como responsável por estes documentos.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def montar_texto(nome_destinatario, itens, url_sistema=None):
    """Versão em texto simples do mesmo e-mail (programas sem HTML e filtros de spam)."""
    linhas = [f'Olá, {nome_destinatario}.', '']
    if not itens:
        linhas.append('Nenhum documento precisa de atenção hoje.')
    else:
        linhas.append(f'{_resumo(len(itens))} de atenção.'.replace('\u00a0', ' '))
        for nivel, titulo, *_ in NIVEIS_EMAIL:
            doc_nivel = [i for i in itens if i['nivel'] == nivel]
            if not doc_nivel:
                continue
            linhas += ['', f'{titulo} ({len(doc_nivel)})']
            for i in doc_nivel:
                linhas.append(f"- {i['documento']}, {i['empresa']}: {_prazo(i['dias'])} ({_data_br(i['vencimento'])})")
    if url_sistema:
        linhas += ['', f'Abrir no AlertSignal: {url_sistema}']
    linhas += ['', 'Mensagem automática do AlertSignal.']
    return '\n'.join(linhas)


def enviar_email(destinatario_email, destinatario_nome, assunto, corpo_html, corpo_texto=None):
    """Envia um e-mail via Gmail SMTP com SSL."""
    if os.environ.get('ALERTSIGNAL_DEMO') == '1':
        print(f"[demonstração] e-mail para {destinatario_email} não enviado.")
        return False

    remetente = get_config('email_remetente')
    senha     = get_config('email_senha_app')

    if not remetente or not senha:
        print("E-mail não configurado. Pulando envio.")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = assunto
    msg['From']    = f'AlertSignal <{remetente}>'
    msg['To']      = destinatario_email

    # Texto simples primeiro e HTML depois: o programa de e-mail mostra a
    # última versão que souber exibir
    if corpo_texto:
        msg.attach(MIMEText(corpo_texto, 'plain', 'utf-8'))
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
        assunto = f"AlertSignal: {qtd} documento{'s' if qtd > 1 else ''} precisa{'m' if qtd > 1 else ''} de atenção"
        url = get_config('url_sistema')
        corpo = montar_html(destinatario['nome'], destinatario['itens'], url)
        texto = montar_texto(destinatario['nome'], destinatario['itens'], url)

        ok = enviar_email(destinatario['email'], destinatario['nome'], assunto, corpo, texto)

        if ok:
            desc = f"Alerta enviado para {destinatario['nome']} ({qtd}\u00a0documento{'s' if qtd > 1 else ''})"
            registrar_historico(desc)
