"""Prévia local com dados fictícios: nunca conecta ao banco ou envia documentos."""
import hashlib
import sys
from datetime import date
from pathlib import Path
from pypdf import PdfReader

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(RAIZ))
from dsystem_erp.services.contrato_pdf import MODELOS_CONTRATO, gerar_contrato_pdf, caminho_modelo_contrato
from dsystem_erp.services.contratos_modelos import WORD, abrir_modelo, slots_modelo, preencher_cadastro
from dsystem_erp.services.contratos_vigencia import preencher_datas_word
from dsystem_erp.services.contratos_word_pdf import gerar_pdf_word
from dsystem_erp.services.contratos_word_pdf import pdf_do_word
from dsystem_erp.services.contratos_word import gerar_contrato_word


def gerar_previa():
    pasta = RAIZ / 'tmp' / 'contratos-word-qa' / 'previews'
    pasta.mkdir(parents=True,exist_ok=True)
    cliente = dict(nome='Cliente Exemplo — dados fictícios',cnpj='00.000.000/0001-00',endereco='Rua Exemplo',numero='100',bairro='Centro',cidade_estado='Contagem / MG',cep='32000-000',telefone='(31) 0000-0000',email='cliente@example.com',responsavel_legal='Maria Exemplo',cpf_responsavel='000.000.000-00')
    empresa = dict(cliente,nome='Empresa Exemplo — dados fictícios',endereco='Avenida de Teste',responsavel_legal='José Exemplo')
    hashes = []
    for indice,tipo in enumerate(list(MODELOS_CONTRATO) + list(WORD),1):
        valores, dados = {}, {}
        if tipo in WORD:
            slots = slots_modelo(tipo)
            valores = preencher_cadastro(tipo,slots,cliente,empresa)
            for slot in slots:
                if not valores[slot['chave']]:
                    valores[slot['chave']] = {'[Valor]':'1.500,00','[Dia]':'10','[0.000,00]':'1.500,00','[Número]':'1000','[0, 00]':'0,10','[Ex: 30%]':'30%'}.get(slot['token'],'Condição de exemplo confirmada pelas partes')
            valores.update(preencher_datas_word(tipo,slots,date(2026,10,7),date(2027,10,7)))
            pdf = gerar_pdf_word(tipo,valores)
            original = abrir_modelo(tipo)
        else:
            dados = dict(cliente,data_contrato='07/10/2026',valor_contrato='R$ 1.500,00',dia_vencimento='10',forma_pagamento='PIX',cargo='Técnico em informática',rg_mei='00.000.000',instituicao_ensino='Instituição de Ensino Exemplo',curso='Tecnologia da Informação',jornada='30 horas')
            campos = PdfReader(str(caminho_modelo_contrato(tipo))).get_fields()
            for nome,campo in campos.items():
                if nome.startswith('assinatura_') or nome == 'data_assinatura':
                    continue
                if campo.get('/FT') == '/Btn' and nome not in {'jornada_20','jornada_30'}:
                    dados[nome] = nome in {'atendimento_remoto','manutencao_preventiva'}
                elif nome in {'razao_social','cnpj_empresa','cnpj_concedente','endereco_empresa','endereco_concedente','representante_legal','supervisor','cpf_representante','cpf_supervisor','jornada_colaborador','escopo_especifico','atividades_especificas','atividades_complementares','beneficios','reajuste','condicoes_adicionais','periodo_experiencia','observacoes_seguranca','observacoes_politicas','observacoes_controles','avaliacao_observacoes'}:
                    dados[nome] = {'razao_social':empresa['nome'],'cnpj_empresa':empresa['cnpj'],'cnpj_concedente':empresa['cnpj'],'jornada_colaborador':'40 horas semanais','representante_legal':'José Exemplo','supervisor':'José Exemplo','cpf_representante':'000.000.000-00','cpf_supervisor':'000.000.000-00'}.get(nome,'Condição de exemplo confirmada pelas partes.')
            pdf = gerar_contrato_pdf(tipo,dados)
            original = caminho_modelo_contrato(tipo).read_bytes()
        destino = pasta / f'{indice}-contrato.pdf'
        destino.write_bytes(pdf)  # saída derivada de QA, não altera código/modelos
        word = gerar_contrato_word(tipo,dados,valores=valores,pdf=pdf)
        (pasta / f'{indice}-contrato.docx').write_bytes(word)
        if tipo not in WORD:
            (pasta / f'{indice}-word-previa.pdf').write_bytes(pdf_do_word(word,tipo))
        hashes.append(f'- {tipo}: SHA-256 original `{hashlib.sha256(original).hexdigest()}`; prévia `{destino.name}`.')
        print(destino)
    (pasta.parent / 'previews-evidencia.md').write_text('''# Verificação dos contratos

Seis modelos existentes são a referência. Originais não alterados. Campos de cadastro,
condições e datas preenchidos com dados fictícios; assinaturas e declarações não simuladas.
Não houve acesso ao banco nem envio de contrato.

Word: A4, margens 2,5 cm vertical / 3 cm horizontal; corpo 12 pt, espaçamento
original, ênfases e listas preservadas. Partes do pacote DOCX são copiadas sem alterações,
exceto word/document.xml para substituição dos slots e seleção das opções.
Fonte Aptos substituída por Vera incorporada no PDF. Quebras de página podem diferir.
LibreOffice não está disponível no runtime: render_docx.py não pôde renderizar os
originais. PDF final é produzido com ReportLab sem dependência de conversor no servidor.

PDFs originais: formulários nativos preservados, aparências atualizadas, fonte ajustada
ao campo. Vigência adicionada na área livre da capa; cláusulas permanecem intactas.
Todos exceto locação têm 1 ano a partir da data de início. Locação mantém prazo configurável.

## Referências
''' + '\n'.join(hashes),encoding='utf-8')


if __name__ == '__main__':
    gerar_previa()
