"""Teste autorizado pelo usuário: faturamento novo local, somente homologação.

Idempotente pelo marcador: uma segunda execução apenas consulta o resultado.
Usa as funções reais do entrypoint sem executar a inicialização da interface.
"""
import ast
import base64
import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dsystem_erp.config import get_settings
from dsystem_erp.db import conectar_mysql
from dsystem_erp.services.fiscal_automatico import salvar_plano, listar_emissoes
from dsystem_erp.services.faturamento import itens_faturamento_lista
from dsystem_erp.services.faturamento_parcelas import gerar_parcelas_faturamento
from dsystem_erp.services.nfse_nacional import ENDPOINT_HOMOLOGACAO
from dsystem_erp.services.nfse_certificado import inspecionar_certificado_pfx, certificado_bate_com_cnpj
from dsystem_erp.utils.datas import agora_br, agora_sao_paulo, data_para_banco_br
from scripts.consultar_parametros_nfse import configuracao_local

MARCADOR = 'TESTE-AUTO-AFEB-HOMOLOGACAO-20260929'


def main():
    settings = get_settings().database
    if settings.host not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Este teste está limitado ao banco local.')
    conectar = lambda: conectar_mysql(settings.database)
    cfg = configuracao_local()
    conn = conectar()
    c = conn.cursor()
    c.execute('SELECT * FROM faturamento WHERE orc_ref=?', (MARCADOR,))
    existente = c.fetchone()
    if existente:
        print('Teste já existe, não será repetido:', existente['id'], existente['status'])
        print(json.dumps([{k:r.get(k) for k in ('tipo','estado','mensagem','nota_id')} for r in listar_emissoes(conectar,existente['id'])],ensure_ascii=False))
        conn.close()
        return
    c.execute('SELECT * FROM faturamento WHERE id=25')
    origem = c.fetchone()
    if not origem or origem['cliente'] != 'AFEB CONSTRUTORA ENGENHARIA LTDA':
        raise ValueError('Cliente de origem não corresponde ao autorizado.')
    c.execute("SELECT plano_json FROM fiscal_emissoes_auto WHERE faturamento_id=25 AND tipo='Serviço'")
    plano = json.loads(c.fetchone()['plano_json'])
    dados = plano['dados']
    if dados['ambiente'] != 'homologacao' or plano['endpoint'].rstrip('/') != ENDPOINT_HOMOLOGACAO:
        raise ValueError('Plano não é de homologação; operação bloqueada.')
    cert = inspecionar_certificado_pfx(cfg['NFSE_CERT_PFX_PATH'], cfg['NFSE_CERT_PASSWORD'])
    if cert['vencido'] or not certificado_bate_com_cnpj(cert,dados['cnpj_prestador']):
        raise ValueError('Certificado incompatível ou vencido.')
    descricao = 'TESTE DE EMISSAO AUTOMATICA - HOMOLOGACAO - SEM VALOR FISCAL'
    itens = [dict(desc=descricao,tipo_item='Serviço',qtd=1,vunit=1.0,vtotal=1.0)]
    dados.update(competencia=date.today().isoformat(), valor=1.0, descricao=descricao, observacoes=MARCADOR)
    c.execute('''INSERT INTO faturamento (data_lanc,cliente,cnpj,tipo,emite_nf,tipo_nota,forma_pag,
        itens,valor_total,parcelas,vencimento,orc_ref,obs_interna,obs_nota,status,
        documentos_entrega,emitir_automaticamente,modalidade_faturamento)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'Aberto','Nota e espelho',1,'Por item')''',
        (data_para_banco_br(date.today()),origem['cliente'],origem['cnpj'],'Eventual','Sim','Serviço',
         'Teste homologação',json.dumps(itens,ensure_ascii=False),1,'Não',data_para_banco_br(date.today()),
         MARCADOR,descricao,descricao))
    fat_id = c.lastrowid
    conn.commit()
    c.execute('SELECT * FROM faturamento WHERE id=?',(fat_id,))
    fat = dict(c.fetchone())
    conn.close()
    print('Faturamento de teste criado:',fat_id,flush=True)
    salvar_plano(conectar,fat_id,'Serviço',dados,[],fat,ENDPOINT_HOMOLOGACAO,'teste_autorizado_usuario')
    # Carrega somente funções, sem executar o app nem alterar configuração global.
    import dsystem_erp.services.audit_log as logs
    contexto = dict(json=json,base64=base64,date=date,conectar_banco=conectar,
        st=SimpleNamespace(session_state={'username':'teste_autorizado_usuario'}),
        agora_br=agora_br,agora_sao_paulo=agora_sao_paulo,data_para_banco_br=data_para_banco_br,
        itens_faturamento_lista=itens_faturamento_lista,gerar_parcelas_faturamento=gerar_parcelas_faturamento,
        config_sistema_val=lambda key,default='':cfg.get(key,default),
        inserir_log_cursor=logs.inserir_log_cursor,TABELA_LOG_SISTEMA='logs_sistema',TABELAS_SEM_LOG_AUTOMATICO=set())
    nomes = {'faturar_lancamento_com_integracoes','salvar_retorno_nota_fiscal','registrar_evento_sistema',
             'registrar_log_cursor','usuario_log_atual','pagina_log_atual'}
    arvore = ast.parse((Path(__file__).resolve().parents[1]/'orcamento.py').read_text(encoding='utf-8-sig'))
    funcs = [n for n in arvore.body if isinstance(n,ast.FunctionDef) and n.name in nomes]
    exec(compile(ast.Module(body=funcs,type_ignores=[]),'orcamento.py','exec'),contexto)
    resultado = contexto['faturar_lancamento_com_integracoes'](fat,emitir_automaticamente=True)
    print(json.dumps(resultado,ensure_ascii=False),flush=True)
    print(json.dumps([{k:r.get(k) for k in ('tipo','estado','mensagem','nota_id')} for r in listar_emissoes(conectar,fat_id)],ensure_ascii=False))


if __name__ == '__main__':
    main()
