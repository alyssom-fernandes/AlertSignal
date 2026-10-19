"""Regra dos alertas por e-mail, com a data fixa, e o agendador.

    python -m unittest discover -s tests -v

Nenhum e-mail sai: o envio é trocado por um falso que só conta as chamadas.
"""

import contextlib
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['ALERTSIGNAL_DEMO'] = '1'

import database                      # noqa: E402
import notificacoes                  # noqa: E402
from demo_seed import popular        # noqa: E402
from test_rotas import Base          # noqa: E402
import app as aplicacao              # noqa: E402

PASTA = tempfile.mkdtemp(prefix='alertsignal-alertas-')
HOJE = date(2030, 1, 10)


class Cenario(unittest.TestCase):
    """Banco só com uma empresa, dois responsáveis e os documentos de cada teste."""

    def setUp(self):
        self.banco_anterior = database.DB_PATH
        database.usar_banco(os.path.join(PASTA, 'alertas.db'))
        popular('vazio')
        conn = database.get_connection()
        cat = conn.execute("INSERT INTO categorias (nome) VALUES ('Teste')").lastrowid
        self.empresa = conn.execute("INSERT INTO empresas (nome, categoria_id) VALUES ('Empresa Exemplo', ?)",
                                    (cat,)).lastrowid
        self.ana = conn.execute("INSERT INTO responsaveis (nome, email) VALUES ('Ana', 'ana@example.com')").lastrowid
        self.bruno = conn.execute("INSERT INTO responsaveis (nome, email) VALUES ('Bruno', 'bruno@example.com')").lastrowid
        conn.commit()
        conn.close()
        self.falhar_para = set()     # e-mails cujo envio deve falhar
        self.enviados = []           # (dia, e-mail) de cada envio que deu certo

    def tearDown(self):
        database.usar_banco(self.banco_anterior)

    def documento(self, dias, responsaveis=None, tipo='AVCB'):
        venc = (HOJE + timedelta(days=dias)).isoformat()
        conn = database.get_connection()
        doc = conn.execute('INSERT INTO documentos (empresa_id, tipo, vencimento) VALUES (?,?,?)',
                           (self.empresa, tipo, venc)).lastrowid
        for r in (responsaveis or [self.ana]):
            conn.execute('INSERT INTO documento_responsavel VALUES (?,?)', (doc, r))
        conn.commit()
        conn.close()
        return doc

    def rodar(self, dia):
        """Roda a verificação como se fosse `dia` e devolve {(doc, resp): marco} do que saiu."""
        def enviar_falso(email, nome, assunto, corpo, texto=None):
            if email in self.falhar_para:
                return False
            self.enviados.append((dia, email))
            return True
        with mock.patch.object(notificacoes, 'enviar_email', side_effect=enviar_falso),                 contextlib.redirect_stdout(io.StringIO()):
            notificacoes.executar_verificacao_diaria(dia)
        conn = database.get_connection()
        linhas = conn.execute('SELECT documento_id, responsavel_id, marco FROM alerta_enviado WHERE data=?',
                              (dia.isoformat(),)).fetchall()
        conn.close()
        return {(l[0], l[1]): l[2] for l in linhas}

    def simular(self, doc, de, ate):
        """Roda um dia de cada vez e devolve {dias para vencer: marco} dos dias com aviso."""
        conn = database.get_connection()
        venc = date.fromisoformat(conn.execute('SELECT vencimento FROM documentos WHERE id=?', (doc,)).fetchone()[0])
        conn.close()
        avisos = {}
        for d in range(de, ate + 1):
            dia = HOJE + timedelta(days=d)
            saiu = self.rodar(dia)
            if (doc, self.ana) in saiu:
                avisos[(venc - dia).days] = saiu[(doc, self.ana)]
        return avisos


class TestMarcos(Cenario):

    def test_um_aviso_por_marco_e_lembrete_diario_depois_de_vencido(self):
        doc = self.documento(100)
        avisos = self.simular(doc, 0, 103)          # de 100 dias antes até 3 dias depois
        self.assertEqual(avisos, {90: 'antecipado', 30: 'renovar', 7: 'critico',
                                  -1: 'vencido', -2: 'vencido', -3: 'vencido'})
        self.assertEqual(len(self.enviados), 6)

    def test_rodar_duas_vezes_no_mesmo_dia_nao_repete(self):
        self.documento(90)
        self.documento(-4, tipo='IPTU')
        self.assertEqual(len(self.rodar(HOJE)), 2)
        self.assertEqual(len(self.enviados), 1)     # um e-mail só, com os dois documentos
        self.rodar(HOJE)
        self.assertEqual(len(self.enviados), 1)

    def test_vencido_recebe_um_lembrete_por_dia(self):
        doc = self.documento(-5)
        self.assertEqual(self.rodar(HOJE), {(doc, self.ana): 'vencido'})
        self.rodar(HOJE)
        self.assertEqual(self.rodar(HOJE + timedelta(days=1)), {(doc, self.ana): 'vencido'})
        self.assertEqual(len(self.enviados), 2)

    def test_verificacao_atrasada_envia_so_o_marco_ultrapassado_uma_vez(self):
        a = self.documento(84)                      # a verificação não rodou no dia dos 90
        b = self.documento(25, tipo='IPTU')         # passou dos 90 e dos 30 sem verificação
        self.assertEqual(self.rodar(HOJE), {(a, self.ana): 'antecipado', (b, self.ana): 'renovar'})
        self.assertEqual(self.rodar(HOJE + timedelta(days=1)), {})
        self.assertEqual(self.simular(b, 2, 25)[7], 'critico')

    def test_vence_hoje_sem_aviso_extra(self):
        doc = self.documento(7)
        self.assertEqual(self.rodar(HOJE), {(doc, self.ana): 'critico'})
        self.assertEqual(self.simular(doc, 1, 7), {})

    def test_documento_renovado_recebe_os_marcos_do_novo_prazo(self):
        doc = self.documento(90)
        self.assertEqual(self.rodar(HOJE), {(doc, self.ana): 'antecipado'})
        conn = database.get_connection()
        conn.execute('UPDATE documentos SET vencimento=? WHERE id=?', ((HOJE + timedelta(days=190)).isoformat(), doc))
        conn.commit()
        conn.close()
        self.assertEqual(self.rodar(HOJE + timedelta(days=1)), {})
        self.assertEqual(self.rodar(HOJE + timedelta(days=100)), {(doc, self.ana): 'antecipado'})
        conn = database.get_connection()
        vencimentos = {r[0] for r in conn.execute('SELECT vencimento FROM alerta_enviado')}
        conn.close()
        self.assertEqual(vencimentos, {(HOJE + timedelta(days=190)).isoformat()})   # o registro antigo saiu

    def test_faixas_configuraveis(self):
        database.set_config('alerta_dias_90', '60')
        database.set_config('alerta_dias_30', '15')
        database.set_config('alerta_dias_7', '3')
        doc = self.documento(70)
        self.assertEqual(self.simular(doc, 0, 71), {60: 'antecipado', 15: 'renovar', 3: 'critico', -1: 'vencido'})

    def test_nivel_alerta_com_faixas(self):
        faixas = {'antecipado': 60, 'renovar': 15, 'critico': 3}
        casos = {61: None, 60: 'antecipado', 16: 'antecipado', 15: 'renovar', 4: 'renovar',
                 3: 'critico', 0: 'critico', -1: 'vencido', None: None}
        for dias, esperado in casos.items():
            with self.subTest(dias=dias):
                self.assertEqual(notificacoes.nivel_alerta(dias, faixas), esperado)

    def test_envio_que_falhou_volta_no_dia_seguinte(self):
        doc = self.documento(90)
        self.falhar_para = {'ana@example.com'}
        self.assertEqual(self.rodar(HOJE), {})
        self.falhar_para = set()
        self.assertEqual(self.rodar(HOJE + timedelta(days=1)), {(doc, self.ana): 'antecipado'})

    def test_cada_responsavel_tem_o_seu_registro(self):
        doc = self.documento(30, responsaveis=[self.ana, self.bruno])
        self.falhar_para = {'ana@example.com'}
        self.assertEqual(self.rodar(HOJE), {(doc, self.bruno): 'renovar'})
        self.falhar_para = set()
        self.assertEqual(self.rodar(HOJE + timedelta(days=1)), {(doc, self.ana): 'renovar'})

    def test_responsavel_novo_recebe_o_marco_atual(self):
        doc = self.documento(30)
        self.rodar(HOJE)
        conn = database.get_connection()
        conn.execute('INSERT INTO documento_responsavel VALUES (?,?)', (doc, self.bruno))
        conn.commit()
        conn.close()
        self.assertEqual(self.rodar(HOJE + timedelta(days=1)), {(doc, self.bruno): 'renovar'})

    def test_fora_da_janela_nao_avisa(self):
        self.documento(91)
        self.assertEqual(self.rodar(HOJE), {})
        self.assertEqual(self.enviados, [])

    def test_excluir_documento_apaga_os_registros(self):
        doc = self.documento(90)
        self.rodar(HOJE)
        conn = database.get_connection()
        conn.execute('DELETE FROM documento_responsavel WHERE documento_id=?', (doc,))
        conn.execute('DELETE FROM documentos WHERE id=?', (doc,))
        conn.commit()
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM alerta_enviado').fetchone()[0], 0)
        conn.close()


class TestMigracao(unittest.TestCase):
    """Um banco criado antes dos marcos ganha a tabela e a coluna nova sem perder nada."""

    def test_banco_antigo(self):
        caminho = os.path.join(PASTA, 'antigo.db')
        if os.path.exists(caminho):
            os.remove(caminho)
        conn = sqlite3.connect(caminho)
        conn.executescript('''
            CREATE TABLE usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL, senha TEXT NOT NULL, nivel TEXT NOT NULL DEFAULT 'admin',
                ativo INTEGER DEFAULT 1);
            INSERT INTO usuarios (nome, email, senha) VALUES ('Antigo', 'antigo@example.com', 'x');
        ''')
        conn.commit()
        conn.close()
        anterior = database.DB_PATH
        database.usar_banco(caminho)
        try:
            database.init_db()
            database.init_db()       # rodar de novo não quebra
            conn = database.get_connection()
            u = conn.execute('SELECT nome, sessao_versao FROM usuarios').fetchone()
            self.assertEqual((u['nome'], u['sessao_versao']), ('Antigo', 0))
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM alerta_enviado').fetchone()[0], 0)
            conn.close()
        finally:
            database.usar_banco(anterior)


class TestAgendador(Base):
    """O job diário nasce no horário configurado e muda quando o horário é salvo."""

    def setUp(self):
        super().setUp()
        self.addCleanup(self.parar)

    def parar(self):
        if aplicacao.scheduler:
            aplicacao.scheduler.shutdown(wait=False)
        aplicacao.scheduler = None

    def horario_do_job(self):
        job = aplicacao.scheduler.get_job('verificacao_diaria')
        campos = {f.name: str(f) for f in job.trigger.fields}
        return f"{int(campos['hour']):02d}:{int(campos['minute']):02d}"

    def salvar(self, **campos):
        dados = {'email_remetente': '', 'email_senha_app': '', 'horario_envio': '', 'url_sistema': '',
                 'alerta_dias_90': '', 'alerta_dias_30': '', 'alerta_dias_7': '', '_csrf': self.csrf}
        dados.update(campos)
        return self.c.post('/configuracoes', data=dados)

    def test_inicia_no_horario_configurado(self):
        database.set_config('horario_envio', '07:45')
        aplicacao.iniciar_agendador()
        self.assertEqual(self.horario_do_job(), '07:45')

    def test_salvar_horario_reagenda_o_job(self):
        aplicacao.iniciar_agendador()
        self.assertEqual(self.horario_do_job(), '08:00')
        self.assertEqual(self.salvar(horario_envio='09:30').status_code, 302)
        self.assertEqual(self.horario_do_job(), '09:30')
        self.salvar(horario_envio='25:00')           # inválido: fica o anterior
        self.assertEqual(self.horario_do_job(), '09:30')
        self.assertEqual(database.get_config('horario_envio'), '09:30')

    def test_salvar_faixas_muda_os_marcos(self):
        self.salvar(alerta_dias_90='120', alerta_dias_30='45', alerta_dias_7='10')
        self.assertEqual(notificacoes.faixas_de_alerta(), {'antecipado': 120, 'renovar': 45, 'critico': 10})
        self.salvar(alerta_dias_90='0')              # fora de 1 a 730: recusado
        self.assertEqual(notificacoes.faixas_de_alerta()['antecipado'], 120)



class TestStatusDoDia(Cenario):
    """O status gravado é atualizado pela verificação diária, sem depender das páginas."""

    def status(self, doc):
        conn = database.get_connection()
        valor = conn.execute('SELECT status FROM documentos WHERE id=?', (doc,)).fetchone()[0]
        conn.close()
        return valor

    def test_verificacao_diaria_atualiza_o_status(self):
        doc = self.documento(31)
        conn = database.get_connection()
        conn.execute("UPDATE documentos SET status='OK' WHERE id=?", (doc,))
        conn.commit()
        conn.close()
        self.rodar(HOJE)
        self.assertEqual(self.status(doc), 'OK')
        self.rodar(HOJE + timedelta(days=1))           # faltam 30 dias
        self.assertEqual(self.status(doc), 'RENOVAR')
        self.rodar(HOJE + timedelta(days=32))          # venceu ontem
        self.assertEqual(self.status(doc), 'VENCIDO')


class TestStatusNasPaginas(Base):
    """As páginas regravam o status uma vez por dia, ou quando o prazo de renovar muda."""

    def setUp(self):
        super().setUp()
        aplicacao._status_conferido.clear()

    def test_uma_varredura_por_dia(self):
        with mock.patch.object(aplicacao, 'atualizar_status', wraps=notificacoes.atualizar_status) as varrer:
            for url in ['/dashboard', '/empresas', '/relatorio', '/empresa/1']:
                self.assertEqual(self.c.get(url).status_code, 200)
        self.assertEqual(varrer.call_count, 1)

    def test_mudar_o_prazo_de_renovar_atualiza_o_status(self):
        venc = (date.today() + timedelta(days=40)).isoformat()
        conn = database.get_connection()
        conn.execute("UPDATE documentos SET vencimento=?, status='OK' WHERE id=1", (venc,))
        conn.commit()
        conn.close()
        self.c.get('/dashboard')
        database.set_config('alerta_dias_30', '45')
        self.c.get('/dashboard')
        conn = database.get_connection()
        self.assertEqual(conn.execute('SELECT status FROM documentos WHERE id=1').fetchone()[0], 'RENOVAR')
        conn.close()


if __name__ == '__main__':
    unittest.main()
