"""Empacota localmente ou aplica a atualização consolidada no servidor.

Empacotar não conecta ao servidor. Aplicar só roda quando chamado pelo usuário.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED

ARQUIVOS = (
    'scripts/inter_configurar_servidor.py', 'configurar_inter_servidor.ps1',
    'tests/test_inter_configurar_servidor.py',
    'deploy.ps1',
    'scripts/fiscal_ativar_producao.py', 'scripts/inter_agendar_servidor.py',
    'tests/test_preparacao_servidor.py', 'ENVIO_SERVIDOR_INTER_NOTAS.md',
    'dsystem_erp/pages/cadastros_planilha.py', 'dsystem_erp/services/cadastros_planilha.py',
    'tests/test_cadastros_planilha.py', 'IMPORTACAO_CADASTROS.md',
    'dsystem_erp/pages/impostos.py', 'dsystem_erp/services/impostos_importacao.py',
    'tests/test_impostos_importacao.py',
    'dsystem_erp/services/impostos_cadastro.py', 'dsystem_erp/services/impostos_notas.py',
    'dsystem_erp/services/impostos_simples.py', 'tests/test_impostos_v14.py',
    'IMPOSTOS_V14.md',
    'orcamento.py', 'requirements.txt',
    'dsystem_erp/pages/banco_inter.py', 'dsystem_erp/repositories/inter.py',
    'dsystem_erp/pages/banco_inter_operacoes.py', 'dsystem_erp/services/inter_producao.py',
    'tests/test_inter_producao.py',
    'dsystem_erp/pages/banco_inter_painel.py', 'dsystem_erp/services/inter_painel.py',
    'scripts/inter_atualizar_painel.py', 'scripts/inter_agendar_painel.ps1',
    'tests/test_inter_painel.py', 'tests/preview_inter_painel.py',
    'dsystem_erp/services/inter_api.py', 'dsystem_erp/services/inter_financeiro.py',
    'dsystem_erp/services/inter_conciliacao.py', 'dsystem_erp/services/inter_runtime.py',
    'dsystem_erp/services/inter_titulos.py', 'scripts/inter_preparar_teste.py',
    'dsystem_erp/services/inter_pendente.py', 'scripts/inter_preparar_local.py',
    'dsystem_erp/services/inter_acessos.py',
    'tests/test_inter_api.py', 'tests/test_inter_financeiro.py', 'tests/test_inter_pagina.py',
    'INTEGRACAO_INTER.md',
    'dsystem_erp/pages/atendimentos.py', 'dsystem_erp/pages/agenda_visual.py',
    'dsystem_erp/pages/classificacao_financeira.py', 'dsystem_erp/pages/financeiro.py',
    'dsystem_erp/pages/faturamento.py', 'dsystem_erp/pages/nfe_tributacao_item.py',
    'dsystem_erp/services/database_init.py', 'dsystem_erp/services/faturamento_medicoes.py',
    'dsystem_erp/services/fiscal_automatico.py', 'dsystem_erp/services/fiscal_modelos.py',
    'dsystem_erp/services/nfe_produto.py', 'dsystem_erp/services/nfe_tributacao_item.py',
    'ATUALIZACAO_AGENDA_FINANCEIRO.md', 'ATUALIZACAO_TAXAS_AUTOMATICAS.md',
    'dsystem_erp/pages/contratos.py', 'dsystem_erp/pages/contratos_gerar.py',
    'dsystem_erp/services/contratos.py', 'dsystem_erp/services/contrato_pdf.py',
    'dsystem_erp/services/contratos_modelos.py', 'dsystem_erp/services/contratos_vigencia.py',
    'dsystem_erp/services/contratos_word_pdf.py', 'ATUALIZACAO_CONTRATOS.md',
    'dsystem_erp/services/contratos_word.py', 'ATUALIZACAO_CONTRATOS_WORD.md',
    'dsystem_erp/pages/contratos_download.py',
    'modelos_contratos/CONTRATOS/Contrato_Suporte_Tecnologico_DSystem.pdf',
    'modelos_contratos/CONTRATOS/Contrato_Corporativo_CLT_DSystem.pdf',
    'modelos_contratos/CONTRATOS/Contrato_Estagio_DSystem_Auditoria_Premium.pdf',
    'modelos_contratos/WORD/tecnologia_infraestrutura.docx',
    'modelos_contratos/WORD/servicos_locacao.docx',
    'modelos_contratos/WORD/contrato_dsystem_pj.docx',
    'dsystem_erp/pages/estoque.py', 'dsystem_erp/repositories/estoque.py',
    'dsystem_erp/services/estoque_importacao.py', 'dsystem_erp/services/estoque_notas.py',
    'dsystem_erp/services/estoque_emprestimos.py', 'dsystem_erp/services/estoque_fiscal.py',
    'dsystem_erp/services/estoque_qr.py', 'dsystem_erp/services/precificacao_estoque.py',
    'ATUALIZACAO_ESTOQUE_PREVIA.md',
    'dsystem_erp/pages/usuarios.py', 'dsystem_erp/pages/funcionario_pj.py',
    'dsystem_erp/services/contratos_pj.py', 'ATUALIZACAO_FUNCIONARIOS_PJ.md',
    'dsystem_erp/services/dados_publicos.py', 'dsystem_erp/pages/clientes.py',
    'ATUALIZACAO_CONSULTA_CNPJ.md',
    'dsystem_erp/services/recepcao_kanban.py', 'dsystem_erp/pages/recepcao_kanban.py',
    'dsystem_erp/pages/ordens_servico.py', 'dsystem_erp/pages/etiquetas_os.py',
    'ATUALIZACAO_QR_OS.md', 'ATUALIZACAO_PORTAL_FUNCIONARIOS.md',
)
# Lista explícita: a validação no servidor não depende dos arquivos já instalados.
ARQUIVOS = tuple(dict.fromkeys(ARQUIVOS + (
    'dsystem_erp/__init__.py',
    'dsystem_erp/app_context.py',
    'dsystem_erp/components/kanban/index.html',
    'dsystem_erp/config.py',
    'dsystem_erp/db.py',
    'dsystem_erp/kanban_component.py',
    'dsystem_erp/migrations.py',
    'dsystem_erp/navigation.py',
    'dsystem_erp/pages/__init__.py',
    'dsystem_erp/pages/acesso_softwares.py',
    'dsystem_erp/pages/agenda_visual.py',
    'dsystem_erp/pages/atendimentos.py',
    'dsystem_erp/pages/chamados.py',
    'dsystem_erp/pages/classificacao_financeira.py',
    'dsystem_erp/pages/clientes.py',
    'dsystem_erp/pages/cobrancas.py',
    'dsystem_erp/pages/compras.py',
    'dsystem_erp/pages/contratos.py',
    'dsystem_erp/pages/contratos_download.py',
    'dsystem_erp/pages/contratos_gerar.py',
    'dsystem_erp/pages/dashboard.py',
    'dsystem_erp/pages/emails.py',
    'dsystem_erp/pages/estoque.py',
    'dsystem_erp/pages/etiquetas_os.py',
    'dsystem_erp/pages/faturado_documentos.py',
    'dsystem_erp/pages/faturamento.py',
    'dsystem_erp/pages/faturamento_lote.py',
    'dsystem_erp/pages/faturamento_manual.py',
    'dsystem_erp/pages/financeiro.py',
    'dsystem_erp/pages/funcionario_pj.py',
    'dsystem_erp/pages/gerador_orcamentos.py',
    'dsystem_erp/pages/infraestrutura.py',
    'dsystem_erp/pages/login.py',
    'dsystem_erp/pages/logs.py',
    'dsystem_erp/pages/medicoes.py',
    'dsystem_erp/pages/nfe_destinatario.py',
    'dsystem_erp/pages/nfe_tributacao_item.py',
    'dsystem_erp/pages/ordens_servico.py',
    'dsystem_erp/pages/portal_cliente.py',
    'dsystem_erp/pages/portal_sections.py',
    'dsystem_erp/pages/recepcao_kanban.py',
    'dsystem_erp/pages/simples.py',
    'dsystem_erp/pages/system_tools.py',
    'dsystem_erp/pages/uber.py',
    'dsystem_erp/pages/usuarios.py',
    'dsystem_erp/repositories/__init__.py',
    'dsystem_erp/repositories/clientes.py',
    'dsystem_erp/repositories/estoque.py',
    'dsystem_erp/repositories/faturamento.py',
    'dsystem_erp/repositories/financeiro.py',
    'dsystem_erp/repositories/uber.py',
    'dsystem_erp/services/__init__.py',
    'dsystem_erp/services/agenda_recorrencia.py',
    'dsystem_erp/services/alertas_atendimento.py',
    'dsystem_erp/services/audit.py',
    'dsystem_erp/services/audit_log.py',
    'dsystem_erp/services/clientes.py',
    'dsystem_erp/services/cobrancas_recorrentes.py',
    'dsystem_erp/services/compras.py',
    'dsystem_erp/services/conciliacao.py',
    'dsystem_erp/services/contas_receber.py',
    'dsystem_erp/services/contrato_pdf.py',
    'dsystem_erp/services/contratos.py',
    'dsystem_erp/services/contratos_modelos.py',
    'dsystem_erp/services/contratos_pj.py',
    'dsystem_erp/services/contratos_vigencia.py',
    'dsystem_erp/services/contratos_word.py',
    'dsystem_erp/services/contratos_word_pdf.py',
    'dsystem_erp/services/dados_publicos.py',
    'dsystem_erp/services/danfse.py',
    'dsystem_erp/services/danfse_local.py',
    'dsystem_erp/services/dashboard.py',
    'dsystem_erp/services/database_init.py',
    'dsystem_erp/services/documentos.py',
    'dsystem_erp/services/email.py',
    'dsystem_erp/services/email_exports.py',
    'dsystem_erp/services/estoque_emprestimos.py',
    'dsystem_erp/services/estoque_fiscal.py',
    'dsystem_erp/services/estoque_importacao.py',
    'dsystem_erp/services/estoque_notas.py',
    'dsystem_erp/services/estoque_qr.py',
    'dsystem_erp/services/faturamento.py',
    'dsystem_erp/services/faturamento_espelho.py',
    'dsystem_erp/services/faturamento_medicoes.py',
    'dsystem_erp/services/faturamento_parcelas.py',
    'dsystem_erp/services/fiscal_automatico.py',
    'dsystem_erp/services/fiscal_documentos.py',
    'dsystem_erp/services/fiscal_modelos.py',
    'dsystem_erp/services/garantias.py',
    'dsystem_erp/services/health.py',
    'dsystem_erp/services/nfe_cadastro_automatico.py',
    'dsystem_erp/services/nfe_cliente.py',
    'dsystem_erp/services/nfe_documento.py',
    'dsystem_erp/services/nfe_item_cadastro.py',
    'dsystem_erp/services/nfe_produto.py',
    'dsystem_erp/services/nfe_tributacao_item.py',
    'dsystem_erp/services/nfse.py',
    'dsystem_erp/services/nfse_catalogo_ti.py',
    'dsystem_erp/services/nfse_certificado.py',
    'dsystem_erp/services/nfse_item_cadastro.py',
    'dsystem_erp/services/nfse_nacional.py',
    'dsystem_erp/services/nfse_pdf.py',
    'dsystem_erp/services/nfse_retorno.py',
    'dsystem_erp/services/nfse_sequencia.py',
    'dsystem_erp/services/nfse_settings.py',
    'dsystem_erp/services/nfse_signature.py',
    'dsystem_erp/services/nfse_soap.py',
    'dsystem_erp/services/nfse_validacao.py',
    'dsystem_erp/services/nfse_workflow.py',
    'dsystem_erp/services/nfse_xml.py',
    'dsystem_erp/services/orcamento_pdf.py',
    'dsystem_erp/services/orcamentos.py',
    'dsystem_erp/services/pacote_faturamento.py',
    'dsystem_erp/services/permissions.py',
    'dsystem_erp/services/portal_cliente.py',
    'dsystem_erp/services/precificacao_estoque.py',
    'dsystem_erp/services/recepcao_kanban.py',
    'dsystem_erp/services/security.py',
    'dsystem_erp/services/session.py',
    'dsystem_erp/services/settings.py',
    'dsystem_erp/services/simples.py',
    'dsystem_erp/services/streamlit_static.py',
    'dsystem_erp/services/usuarios.py',
    'dsystem_erp/services/whatsapp.py',
    'dsystem_erp/technical_logs.py',
    'dsystem_erp/ui.py',
    'dsystem_erp/ui_consulta.py',
    'dsystem_erp/utils/__init__.py',
    'dsystem_erp/utils/datas.py',
    'dsystem_erp/utils/formatadores.py',
    'modules/__init__.py',
    'modules/estoque.py',
    'modules/faturamento.py',
    'modules/infraestrutura.py',
    'modules/registry.py',
    'scripts/backup_mysql.py',
    'scripts/pacote_agenda_financeiro_taxas.py',
    'tests/preview_danfse_local.py',
    'tests/preview_espelho.py',
    'tests/preview_nfse_pdf.py',
    'tests/preview_produto_comensoli.py',
    'tests/test_agenda_classificacao.py',
    'tests/test_agenda_filtro_status.py',
    'tests/test_agenda_recorrencia.py',
    'tests/test_alertas_atendimento.py',
    'tests/test_app_context.py',
    'tests/test_audit.py',
    'tests/test_audit_log.py',
    'tests/test_backup_mysql.py',
    'tests/test_cadastro_bancario.py',
    'tests/test_chamados_page.py',
    'tests/test_clientes.py',
    'tests/test_clientes_page.py',
    'tests/test_clientes_pesquisa.py',
    'tests/test_clientes_repository.py',
    'tests/test_cnpj_indisponibilidade.py',
    'tests/test_cobrancas_recorrentes.py',
    'tests/test_compras.py',
    'tests/test_conciliacao.py',
    'tests/test_contas_receber.py',
    'tests/test_contrato_pdf.py',
    'tests/test_contratos_data_assinatura.py',
    'tests/test_contratos_modelos.py',
    'tests/test_contratos_vigencia_pdf.py',
    'tests/test_contratos_word.py',
    'tests/test_dados_publicos.py',
    'tests/test_danfse.py',
    'tests/test_danfse_local.py',
    'tests/test_dashboard.py',
    'tests/test_dashboard_uber_pages.py',
    'tests/test_database_init.py',
    'tests/test_db.py',
    'tests/test_documentos.py',
    'tests/test_documentos_erp.py',
    'tests/test_email_service.py',
    'tests/test_estoque_cadastro_formulario.py',
    'tests/test_estoque_emprestimos.py',
    'tests/test_estoque_financeiro_repositories.py',
    'tests/test_estoque_fiscal.py',
    'tests/test_estoque_importacao.py',
    'tests/test_estoque_notas.py',
    'tests/test_estoque_qr.py',
    'tests/test_estoque_selecao.py',
    'tests/test_estoque_uso_interno.py',
    'tests/test_extra_pages_import.py',
    'tests/test_faturado_documentos_auto.py',
    'tests/test_faturamento_auto_integracao.py',
    'tests/test_faturamento_espelho.py',
    'tests/test_faturamento_lote.py',
    'tests/test_faturamento_manual.py',
    'tests/test_faturamento_page.py',
    'tests/test_faturamento_parcelas.py',
    'tests/test_faturamento_repository.py',
    'tests/test_faturar_ate_pdfs.py',
    'tests/test_financeiro_comparativo.py',
    'tests/test_financeiro_page.py',
    'tests/test_fiscal_automatico.py',
    'tests/test_fiscal_modelos.py',
    'tests/test_funcionario_pj.py',
    'tests/test_garantias.py',
    'tests/test_gerador_orcamentos_page.py',
    'tests/test_health.py',
    'tests/test_impressao_orcamento.py',
    'tests/test_infra_exclusao.py',
    'tests/test_infra_hardware_pc.py',
    'tests/test_infraestrutura_page.py',
    'tests/test_infraestrutura_selecao.py',
    'tests/test_kanban_component.py',
    'tests/test_login_page.py',
    'tests/test_logs_page.py',
    'tests/test_medicoes_estornos.py',
    'tests/test_migrations.py',
    'tests/test_navigation.py',
    'tests/test_nfe_assinatura_interoperabilidade.py',
    'tests/test_nfe_cadastro_automatico.py',
    'tests/test_nfe_cliente.py',
    'tests/test_nfe_documento.py',
    'tests/test_nfe_ibscbs.py',
    'tests/test_nfe_item_cadastro.py',
    'tests/test_nfe_produto.py',
    'tests/test_nfe_taxas_automaticas.py',
    'tests/test_nfse_catalogo_ti.py',
    'tests/test_nfse_certificado.py',
    'tests/test_nfse_im_automatica.py',
    'tests/test_nfse_item_cadastro.py',
    'tests/test_nfse_modules.py',
    'tests/test_nfse_nacional.py',
    'tests/test_nfse_pdf_layout.py',
    'tests/test_nfse_protecao_envio.py',
    'tests/test_nfse_sequencia.py',
    'tests/test_nfse_xml_service.py',
    'tests/test_orcamentos.py',
    'tests/test_os_qr_dinamico.py',
    'tests/test_os_tipo_estado.py',
    'tests/test_pacote_agenda_taxas.py',
    'tests/test_pacote_faturamento.py',
    'tests/test_permissions.py',
    'tests/test_portal_cliente.py',
    'tests/test_portal_sections.py',
    'tests/test_precificacao_estoque.py',
    'tests/test_recepcao_kanban.py',
    'tests/test_recorrencias_cadastro.py',
    'tests/test_security.py',
    'tests/test_services.py',
    'tests/test_session.py',
    'tests/test_settings.py',
    'tests/test_simples.py',
    'tests/test_startup_performance.py',
    'tests/test_streamlit_static.py',
    'tests/test_system_tools_page.py',
    'tests/test_uber.py',
    'tests/test_ui.py',
    'tests/test_ui_consulta.py',
    'tests/verificar_nfe_dotnet.ps1',
)))
NOME_PACOTE = 'atualizacao-agenda-financeiro-taxas.zip'


def empacotar():
    raiz = Path(__file__).resolve().parents[1]
    destino = raiz / NOME_PACOTE
    conteudos = {nome: (raiz / nome).read_bytes() for nome in ARQUIVOS}
    manifesto = {nome: hashlib.sha256(dados).hexdigest() for nome, dados in conteudos.items()}
    with ZipFile(destino, 'w', ZIP_DEFLATED) as pacote:
        for nome, dados in conteudos.items():
            pacote.writestr(nome, dados)
        pacote.writestr('manifesto.json', json.dumps(manifesto, indent=2))
    print(f'Pacote local: {destino} ({len(conteudos)} arquivos). Nenhum envio realizado.')


def aplicar(arquivo, raiz, reiniciar=False):
    raiz = Path(raiz).resolve(strict=True)
    if not (raiz / 'orcamento.py').is_file():
        raise ValueError('O diretório informado não contém o projeto orcamento.py.')
    python = raiz / '.venv/bin/python'
    if not python.is_file():
        raise ValueError('Ambiente virtual .venv/bin/python não encontrado no projeto.')
    with ZipFile(arquivo) as pacote:
        if set(pacote.namelist()) != set(ARQUIVOS) | {'manifesto.json'} or len(pacote.namelist()) != len(ARQUIVOS) + 1:
            raise ValueError('O pacote não corresponde aos arquivos desta atualização.')
        manifesto = json.loads(pacote.read('manifesto.json'))
        conteudos = {nome: pacote.read(nome) for nome in ARQUIVOS}
    for nome, dados in conteudos.items():
        if hashlib.sha256(dados).hexdigest() != manifesto.get(nome):
            raise ValueError(f'Arquivo alterado/incompleto no pacote: {nome}')
        if not (raiz / nome).resolve().is_relative_to(raiz):
            raise ValueError(f'Destino fora do projeto: {nome}')
        if nome.endswith('.py'):
            compile(dados, nome, 'exec')
    backups = raiz / 'backups_codigo'
    if not backups.resolve().is_relative_to(raiz):
        raise ValueError('Pasta de backup fora do projeto.')
    backups.mkdir(exist_ok=True)
    backup = backups / f'agenda-financeiro-taxas-{datetime.now():%Y%m%d-%H%M%S-%f}.zip'
    with ZipFile(backup, 'w', ZIP_DEFLATED) as zip_backup:
        for nome in ARQUIVOS:
            anterior = raiz / nome
            if anterior.is_file():
                zip_backup.write(anterior, nome)
    for nome, dados in conteudos.items():
        destino = raiz / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        anterior_stat = destino.stat() if destino.exists() else None
        modo = anterior_stat.st_mode & 0o777 if anterior_stat else 0o644
        with tempfile.NamedTemporaryFile(dir=destino.parent, delete=False) as temporario:
            temporario.write(dados)
            caminho_temporario = Path(temporario.name)
        try:
            os.chmod(caminho_temporario, modo)
            if anterior_stat and hasattr(os, 'chown'):
                os.chown(caminho_temporario, anterior_stat.st_uid, anterior_stat.st_gid)
            os.replace(caminho_temporario, destino)
        finally:
            caminho_temporario.unlink(missing_ok=True)
    print(f'Arquivos atualizados. Backup do código anterior: {backup}')
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(raiz / 'requirements.txt')], check=True)
    subprocess.run([str(python), '-c',
                    'import dsystem_erp.pages.atendimentos, dsystem_erp.pages.financeiro, dsystem_erp.pages.faturamento, dsystem_erp.pages.contratos_gerar, dsystem_erp.pages.estoque, dsystem_erp.pages.usuarios'],
                   cwd=raiz, check=True)
    if reiniciar:
        unidades = subprocess.run(['systemctl', 'list-units', '--type=service', '--all', '--plain', '--no-legend'],
                                  capture_output=True, text=True, check=True)
        nomes = [linha.split()[0] for linha in unidades.stdout.splitlines() if linha.split()]
        candidatos = []
        for nome in nomes:
            info = subprocess.run(['systemctl', 'show', nome, '--property=WorkingDirectory', '--property=ExecStart'],
                                  capture_output=True, text=True, check=True).stdout
            pasta_trabalho = next((linha.split('=', 1)[1] for linha in info.splitlines()
                                   if linha.startswith('WorkingDirectory=')), '')
            if ((pasta_trabalho == str(raiz) and 'streamlit' in info.lower())
                    or str(raiz / 'orcamento.py') in info):
                candidatos.append(nome)
        if len(candidatos) == 1:
            subprocess.run(['systemctl', 'restart', candidatos[0]], check=True)
            subprocess.run(['systemctl', 'is-active', candidatos[0]], check=True)
            print(f'Serviço reiniciado: {candidatos[0]}')
        else:
            print('Reinicie o serviço do site manualmente; não foi identificado um único serviço deste projeto.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('acao', choices=('empacotar', 'aplicar'))
    parser.add_argument('pacote', nargs='?')
    parser.add_argument('raiz', nargs='?', default='/opt/orcamento')
    parser.add_argument('--reiniciar', action='store_true')
    args = parser.parse_args()
    if args.acao == 'empacotar':
        empacotar()
    elif not args.pacote:
        parser.error('Informe o pacote para aplicar.')
    else:
        aplicar(args.pacote, args.raiz, args.reiniciar)
