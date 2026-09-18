"""Teste isolado na SEFAZ MG; não grava faturamento nem movimenta estoque."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datetime import datetime, timedelta
from scripts.consultar_parametros_nfse import configuracao_local
from dsystem_erp.services.nfe_produto import (
    gerar_xml_nfe_produto_400, assinar_xml_nfe_produto,
    enviar_xml_nfe_produto, analisar_retorno_nfe_produto, endpoint_autorizacao_nfe,
)

if __name__ == '__main__':
    config = configuracao_local()
    # Dados cadastrais confirmados em CadConsultaCadastro4 de homologação.
    dados = dict(ambiente='homologacao', emitente_cnpj='23524449000154',
        emitente_nome='D F PEREIRA INFORMATICA', emitente_fantasia='D- SYSTEM TECNOLOGIA',
        emitente_logradouro='RUA ALTO GUANDU', emitente_numero='106',
        emitente_bairro='SAO PAULO', emitente_municipio='BELO HORIZONTE', emitente_cep='31910230',
        inscricao_estadual='0026483460031', codigo_municipio='3106200', uf='MG',
        regime_tributario='3', serie=889, numero=int(sys.argv[1]), codigo_nf='11092026',
        data_emissao=datetime.now().astimezone()-timedelta(minutes=5),
        ncm='84716053', cfop='5102', unidade='UN',
        ibscbs=dict(cst='000',classificacao='000001',base=1,uf=0.1,municipal=0,cbs=0.9),
        destinatario=dict(logradouro='Um',numero='45',bairro='Goiania A',codigo_municipio='3106200',municipio='BELO HORIZONTE',uf='MG',cep='31950142'),
        observacoes='TESTE DE INTEGRACAO SEM VALOR FISCAL. PRODUTO E VALORES SIMULADOS.')
    cliente = dict(cliente='Associacao Comunitaria Da Vila Presidente Vargas', cnpj='20489373000185')
    if '--propria-empresa' in sys.argv:
        cliente = dict(cliente='D F PEREIRA INFORMATICA', cnpj='23524449000154')
        dados['destinatario'] = dict(logradouro='RUA ALTO GUANDU',numero='106',bairro='SAO PAULO',
            codigo_municipio='3106200',municipio='BELO HORIZONTE',uf='MG',cep='31910230',
            indicador_ie='1',ie='0026483460031')
    itens = [dict(desc='MOUSE - TESTE HOMOLOGACAO', qtd=1, vunit=1, vtotal=1)]
    xml = gerar_xml_nfe_produto_400(cliente, itens, dados)
    assinado = assinar_xml_nfe_produto(xml, config['NFSE_CERT_PFX_PATH'], config['NFSE_CERT_PASSWORD'])
    retorno = enviar_xml_nfe_produto(endpoint_autorizacao_nfe('MG','homologacao'), assinado,
        config['NFSE_CERT_PFX_PATH'], config['NFSE_CERT_PASSWORD'], timeout=25)
    print(analisar_retorno_nfe_produto(retorno))
