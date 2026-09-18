import unittest
from streamlit.testing.v1 import AppTest


def dashboard_app():
    import streamlit as st
    from dsystem_erp.pages.dashboard import renderizar_dashboard
    class Banco:
        def cursor(self):
            return self
        def execute(self, sql):
            st.session_state.setdefault('consultas', []).append(sql)
        def fetchall(self):
            return []
        def close(self):
            pass
    renderizar_dashboard(dict(st=st, conectar_banco=Banco,
        tem_permissao=lambda p: st.session_state.get('completo', True) or p == 'dashboard.view',
        filtrar_registros_por_empresa=lambda rows, *campos: rows,
        formatar_moeda_br=lambda v: f'R$ {v:.2f}'))


def uber_app():
    import streamlit as st
    from dsystem_erp.pages.uber import renderizar_uber
    st.session_state['uber_schema_verificado'] = True
    def salvar(conectar, dados, usuario, corrida_id, clientes_permitidos):
        from dsystem_erp.repositories.uber import validar_corrida
        st.session_state['salvo'] = validar_corrida(dados)
        return 1
    renderizar_uber(dict(st=st, conectar_banco=lambda: None,
        tem_permissao=lambda p: True, buscar_clientes=lambda: [{'id': 1, 'nome': 'Cliente A'}],
        listar_funcionarios_sistema=lambda: [{'username': 'tecnico', 'label': 'Técnico'}],
        listar_corridas=lambda conectar: [], salvar_corrida=salvar,
        formatar_moeda_br=lambda v: f'R$ {v:.2f}'))


class DashboardUberPageTests(unittest.TestCase):
    def test_dashboard_renderiza_e_atualiza(self):
        app = AppTest.from_function(dashboard_app).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 15)
        app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)

    def test_dashboard_nao_consulta_modulos_sem_permissao(self):
        app = AppTest.from_function(dashboard_app)
        app.session_state['completo'] = False
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 0)
        self.assertNotIn('consultas', app.session_state)

    def test_uber_salva_e_limpa_formulario(self):
        app = AppTest.from_function(uber_app).run()
        self.assertEqual(len(app.exception), 0)
        app.multiselect[0].set_value([1])
        app.number_input[0].set_value(50.0)
        next(w for w in app.text_input if 'Produto(s)' in w.label).set_value('Impressora')
        next(b for b in app.button if b.label == 'Salvar corrida').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state['salvo']['cliente_ids'], [1])
        self.assertEqual(app.number_input[0].value, 0.0)
        self.assertEqual(app.multiselect[0].value, [])
        self.assertEqual(len(app.success), 1)
