"""Testes das rotas do AlertSignal, no modo demonstração (banco temporário).

    python -m unittest discover -s tests -v
"""

import csv
import io
import os
import re
import sys
import tempfile
import unittest
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.environ['ALERTSIGNAL_DEMO'] = '1'

import database                      # noqa: E402
from demo_seed import popular        # noqa: E402
import app as aplicacao              # noqa: E402

PASTA = tempfile.mkdtemp(prefix='alertsignal-testes-')
database.usar_banco(os.path.join(PASTA, 'demo.db'))


def token(resp_html):
    m = re.search(r'name="csrf-token" content="([^"]+)"', resp_html)
    return m.group(1) if m else ''


class Base(unittest.TestCase):
    perfil = 'admin'

    def setUp(self):
        popular('completo')
        aplicacao.app.config['TESTING'] = True
        self.c = aplicacao.app.test_client()
        html = self.c.get('/login').get_data(as_text=True)
        self.csrf = token(html)
        r = self.c.post('/demo/entrar', data={'perfil': self.perfil, '_csrf': self.csrf})
        self.assertEqual(r.status_code, 302)
        # entrar limpa a sessão (e o token); as páginas seguintes trazem um novo
        self.csrf = token(self.c.get('/perfil').get_data(as_text=True))

    def post_json(self, url, dados=None, metodo='POST'):
        return self.c.open(url, method=metodo, json=dados or {}, headers={'X-CSRF-Token': self.csrf})


class TestPaginas(Base):
    def test_paginas_abrem_sem_erro(self):
        for url in ['/dashboard', '/empresas', '/empresa/1', '/empresa/6', '/empresa/16', '/relatorio',
                    '/relatorio?status=atencao', '/relatorio?status=vencidos&categoria=1', '/relatorio?empresa=3',
                    '/cadastros', '/cadastros?aba=inativos', '/responsaveis', '/historico', '/historico?page=2',
                    '/historico?page=abc', '/historico?page=-5', '/usuarios', '/configuracoes', '/perfil', '/demo/email']:
            with self.subTest(url=url):
                r = self.c.get(url)
                self.assertEqual(r.status_code, 200, url)

    def test_scripts_da_pagina_aparecem_uma_vez(self):
        html = self.c.get('/empresa/1').get_data(as_text=True)
        self.assertEqual(html.count('let linhaAtual'), 1)

    def test_erros_proprios(self):
        r = self.c.get('/nao-existe')
        self.assertEqual(r.status_code, 404)
        self.assertIn('Página não encontrada', r.get_data(as_text=True))
        self.assertEqual(self.c.get('/empresa/9999').status_code, 404)
        r = self.c.get('/api/doc/9999/editar')
        self.assertEqual(r.status_code, 405)
        self.assertEqual(r.get_json()['ok'], False)

    def test_apostrofo_nao_vai_para_javascript(self):
        html = self.c.get('/cadastros').get_data(as_text=True)
        self.assertNotIn("onsubmit=\"return confirm('", html)
        self.assertIn('Cantina D&#39;Ítalia', html)


class TestCsrf(Base):
    def test_post_sem_token_e_recusado(self):
        r = self.c.post('/api/doc/1/protocolo', json={'protocolo': 'X'})
        self.assertEqual(r.status_code, 400)
        r = self.c.post('/categoria/nova', data={'nome': 'Nova'})
        self.assertEqual(r.status_code, 302)
        conn = database.get_connection()
        self.assertIsNone(conn.execute("SELECT 1 FROM categorias WHERE nome='Nova'").fetchone())
        conn.close()

    def test_post_com_token_funciona(self):
        r = self.post_json('/api/doc/1/protocolo', {'protocolo': 'AVCB-TESTE'})
        self.assertTrue(r.get_json()['ok'])


class TestDocumentos(Base):
    def test_renovar_exige_data_futura(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        self.assertEqual(self.post_json('/api/doc/1/renovar', {'vencimento': ontem}).status_code, 400)
        futuro = (date.today() + timedelta(days=200)).isoformat()
        self.assertTrue(self.post_json('/api/doc/1/renovar', {'vencimento': futuro}).get_json()['ok'])
        conn = database.get_connection()
        self.assertEqual(conn.execute('SELECT status FROM documentos WHERE id=1').fetchone()[0], 'OK')
        conn.close()

    def test_documento_sem_data_fica_sem_data(self):
        r = self.c.post('/cadastros/documento/novo', data={'empresa_id': 16, 'tipo': 'IPTU', '_csrf': self.csrf})
        self.assertEqual(r.status_code, 302)
        conn = database.get_connection()
        self.assertEqual(conn.execute("SELECT status FROM documentos WHERE empresa_id=16").fetchone()[0], 'NÃO TEM')
        conn.close()

    def test_historico_descreve_o_documento(self):
        self.post_json('/api/doc/1/protocolo', {'protocolo': 'P-1'})
        conn = database.get_connection()
        texto = conn.execute('SELECT descricao FROM historico ORDER BY id DESC LIMIT 1').fetchone()[0]
        conn.close()
        self.assertIn('Protocolo atualizado:', texto)
        self.assertNotIn('#', texto)

    def test_email_de_alerta(self):
        from notificacoes import montar_html, montar_texto
        itens = [{'empresa': "Cantina D'Ítalia <b>", 'documento': 'AVCB', 'vencimento': '2026-01-01', 'dias': -3, 'nivel': 'vencido'}]
        html = montar_html('Ana', itens, 'http://servidor:5000')
        self.assertIn('&lt;b&gt;', html)                      # nome escapado
        self.assertIn('Abrir no AlertSignal', html)
        self.assertIn('01/01/2026', html)
        self.assertNotIn('Abrir no AlertSignal', montar_html('Ana', itens))
        self.assertIn('Vencido há 3 dias', montar_texto('Ana', itens))

    def test_empresa_ordena_por_urgencia(self):
        html = self.c.get('/empresa/1').get_data(as_text=True)
        status = re.findall(r'data-status="([^"]+)"', html)
        ordem = {'VENCIDO': 0, 'RENOVAR': 1, 'NÃO TEM': 2, 'OK': 3}
        self.assertEqual(status, sorted(status, key=ordem.get))

    def test_alerta_nao_sai_no_demo(self):
        r = self.post_json('/api/testar-email').get_json()
        self.assertFalse(r['ok'])
        self.assertTrue(r.get('demo'))


class TestRegrasDaConferencia(Base):
    """Defeitos apontados na revisão de código final, para não voltarem."""

    def test_login_ignora_maiusculas(self):
        self.c.post('/usuarios/novo', data={'nome': 'Maria', 'email': 'Maria.Silva@Empresa.com', 'senha': 'abcdef',
                                            'nivel': 'visualizador', '_csrf': self.csrf})
        c2 = aplicacao.app.test_client()
        tok = token(c2.get('/login').get_data(as_text=True))
        r = c2.post('/login', data={'email': 'Maria.Silva@Empresa.com', 'senha': 'abcdef', '_csrf': tok})
        self.assertEqual(r.status_code, 302)

    def test_empresa_inativa_nao_gera_alerta(self):
        from notificacoes import buscar_alertas
        empresas = {i['empresa'] for a in buscar_alertas() for i in a['itens']}
        self.assertNotIn('Autopeças Avenida', empresas)

    def test_data_invalida_e_recusada(self):
        r = self.post_json('/api/doc/1/editar', {'vencimento': '31/12/2027'})
        self.assertEqual(r.status_code, 400)
        conn = database.get_connection()
        self.assertIsNotNone(conn.execute('SELECT vencimento FROM documentos WHERE id=1').fetchone()[0])
        conn.close()

    def test_remover_responsavel_apaga_vinculos(self):
        self.c.post('/responsaveis/1/excluir', data={'_csrf': self.csrf})
        conn = database.get_connection()
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM documento_responsavel WHERE responsavel_id=1').fetchone()[0], 0)
        conn.close()

    def test_ficha_de_empresa_inativa_exporta(self):
        r = self.c.get('/exportar?fmt=csv&empresa=17')
        self.assertGreater(len(r.data.decode('utf-8-sig').strip().splitlines()), 1)


class TestExportacao(Base):
    def test_excel(self):
        from openpyxl import load_workbook
        r = self.c.get('/exportar?fmt=xlsx&status=atencao')
        self.assertEqual(r.status_code, 200)
        ws = load_workbook(io.BytesIO(r.data)).active
        self.assertEqual(ws['A5'].value, 'Empresa')
        self.assertIn('Vencidos:', ws['A3'].value)
        self.assertNotEqual(ws['A7'].fill.fgColor.rgb, '00111111')   # zebra não pode ser preta
        self.assertEqual(ws['F6'].number_format, 'DD/MM/YYYY')
        self.assertEqual(ws['G5'].value, 'Dias para vencer')

    def test_csv_com_ponto_e_virgula(self):
        r = self.c.get('/exportar?fmt=csv&empresa=6')
        texto = r.data.decode('utf-8-sig')
        linhas = list(csv.reader(io.StringIO(texto), delimiter=';'))
        self.assertEqual(linhas[0][0], 'Empresa')
        self.assertTrue(all(len(l) == len(linhas[0]) for l in linhas))
        self.assertTrue(all(l[0] == "Cantina D'Ítalia" for l in linhas[1:]))


class TestVisualizador(Base):
    perfil = 'visualizador'

    def test_consulta_funciona(self):
        for url in ['/dashboard', '/empresas', '/empresa/1', '/relatorio', '/cadastros', '/responsaveis', '/historico', '/perfil']:
            with self.subTest(url=url):
                self.assertEqual(self.c.get(url).status_code, 200)

    def test_nao_ve_acoes_de_admin(self):
        html = self.c.get('/empresa/1').get_data(as_text=True)
        self.assertNotIn('data-acao="editar"', html)
        self.assertNotIn('id="modal-editar"', html)

    def test_servidor_bloqueia_alteracoes(self):
        for url, metodo in [('/api/doc/1/protocolo', 'POST'), ('/api/doc/1/renovar', 'POST'),
                            ('/api/doc/1/responsavel', 'POST'), ('/api/doc/1/responsavel/1', 'DELETE'),
                            ('/api/doc/1/editar', 'POST'), ('/api/doc/1/excluir', 'DELETE'),
                            ('/api/testar-email', 'POST')]:
            with self.subTest(url=url):
                self.assertEqual(self.post_json(url, {'vencimento': '2099-01-01'}, metodo).status_code, 403)
        self.assertEqual(self.c.get('/usuarios').status_code, 302)


if __name__ == '__main__':
    unittest.main()
