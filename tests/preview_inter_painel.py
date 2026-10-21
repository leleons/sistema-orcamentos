"""Prévia visual isolada: streamlit run tests/preview_inter_painel.py.

Somente SQLite temporário e dados fictícios; não usa MySQL, cofre ou API reais.
"""
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st
from dsystem_erp.repositories.inter import criar_repositorio_demo
from dsystem_erp.services.inter_painel import PainelInter, BRASILIA
from tests.test_inter_painel import usuario_teste, credencial_ficticia
from dsystem_erp.pages.banco_inter import renderizar_banco_inter
from dsystem_erp.pages.banco_inter_painel import renderizar_painel


class ConsultasFicticias:
    def __init__(self, repo=None):
        pass

    def consultar(self, empresa, usuario, operacao, *, params=None):
        if operacao == 'saldo':
            return {'disponivel': '18542.75'}
        if operacao != 'extrato':
            raise AssertionError('Prévia não permite operações bancárias.')
        hoje = datetime.now(BRASILIA).date()
        linhas = [
            ('C', '4800.00', 'PIX', 'Recebimento de contrato de suporte', 0),
            ('D', '650.00', 'PAGAMENTO', 'Fornecedor de equipamentos', 0),
            ('C', '1250.00', 'BOLETO_COBRANCA', 'Mensalidade de serviços de TI', 1),
            ('D', '85.90', 'TARIFA', 'Tarifas bancárias do período', 2),
            ('C', '340.00', 'PIX', 'Atendimento técnico avulso', 3),
        ]
        transacoes = [{'idTransacao': str(i), 'dataTransacao': (hoje-timedelta(days=dias)).isoformat(),
                       'tipoOperacao': direcao, 'valor': valor, 'tipoTransacao': tipo, 'descricao': desc}
                      for i, (direcao, valor, tipo, desc, dias) in enumerate(linhas)]
        return {'transacoes': transacoes, 'totalPaginas': 1, 'totalElementos': len(transacoes)}

    def fechar(self):
        pass


st.set_page_config(layout='wide', page_title='Prévia fictícia — Banco Inter')
st.session_state.update(usuario_teste())
if '_preview_repo' not in st.session_state:
    pasta = tempfile.TemporaryDirectory(prefix='inter_preview_')
    repo = criar_repositorio_demo(Path(pasta.name)/'painel.sqlite', 'teste')
    credencial_ficticia(repo)
    painel = PainelInter(repo, ConsultasFicticias(), obter_usuario=lambda _: usuario_teste(), chave=lambda: b'x'*32)
    painel.configurar_agenda(1, usuario_teste(), ativo=True)
    painel.atualizar(1, usuario_teste())
    st.session_state['_preview_repo'] = (pasta, repo)
st.caption('PRÉVIA VISUAL · Todos os valores e transações são fictícios.')
with patch('dsystem_erp.services.inter_runtime.repositorio_configuracao', return_value=st.session_state['_preview_repo'][1]), \
     patch('dsystem_erp.services.inter_runtime.ConsultasInterProducao', ConsultasFicticias), \
     patch('dsystem_erp.services.inter_runtime.chave_mestra', return_value=b'x'*32), \
     patch('dsystem_erp.pages.banco_inter_painel.carregar_usuario', return_value=usuario_teste()):
    st.title('Banco Inter')
    # Não registrar o timer na prévia: os patches terminam após cada renderização.
    # Assim interações causam rerun completo e nunca consultam o usuário/cofre reais.
    renderizar_painel.__wrapped__(st.session_state['_preview_repo'][1], ConsultasFicticias(), 1,
        'Empresa fictícia — DEMO', 'preview_', lambda funcao: funcao())
