"""Prévia fictícia do modelo PJ; não consulta/grava banco e não envia contrato."""
import hashlib
import io
import json
import sys
from datetime import date
from pathlib import Path
from zipfile import ZipFile

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(RAIZ))
from dsystem_erp.services.contratos_modelos import abrir_modelo, slots_modelo, preencher_cadastro, gerar_word
from dsystem_erp.services.contratos_vigencia import preencher_datas_word
from dsystem_erp.services.contratos_word_pdf import gerar_pdf_word
from dsystem_erp.services.contratos_pj import MODELO_PJ


def validar(inicio=date(2026,10,8), assinatura=None):
    from dsystem_erp.services.contratos_vigencia import fim_vigencia
    fim = fim_vigencia(inicio)
    pasta = RAIZ / 'tmp' / 'contratos-word-qa' / 'pj'
    pasta.mkdir(parents=True,exist_ok=True)
    original = abrir_modelo(MODELO_PJ)
    assert hashlib.sha256(original).hexdigest() == '599ae9a3783f42a10429253d7f6fd8db3730d731bd551ebea33ba473f4ed17f6'
    contratante = dict(nome='Dsystem Exemplo — dados fictícios',cnpj='00.000.000/0001-00',endereco='Rua de Exemplo, 30',cidade_estado='Sabará / MG',responsavel_legal='Representante Exemplo')
    contratada = dict(nome='Prestadora Exemplo — dados fictícios',cnpj='11.111.111/0001-11',endereco='Rua da Prestadora, 100, Contagem / MG',responsavel_legal='Prestador Exemplo',cpf_responsavel='000.000.000-00')
    slots = slots_modelo(MODELO_PJ)
    valores = preencher_cadastro(MODELO_PJ,slots,contratante,contratada)
    valores.update(preencher_datas_word(MODELO_PJ,slots,inicio,fim,assinatura=assinatura))
    for s in slots:
        if valores[s['chave']]:
            continue
        if s['paragrafo'] == 11:
            valor = {'[Valor mensal]':'2.500,00','[Horas por dia]':'8','[Deslocamento mensal]':'250,00','[Dia do pagamento]':'10'}[s['token']]
        elif s['paragrafo'] in (23,25):
            valor = 'Sabará / MG'
        elif s['paragrafo'] in (31,32):
            valor = 'Testemunha Exemplo ' + str(s['paragrafo']-30) if s['token'].startswith('Nome:') else '000.000.000-00'
        else:
            raise ValueError('Slot não preenchido: '+s['rotulo'])
        valores[s['chave']] = valor
    docx = gerar_word(MODELO_PJ,valores)
    with ZipFile(io.BytesIO(original)) as origem,ZipFile(io.BytesIO(docx)) as saida:
        inventario = [{'parte':n,'bytes':len(origem.read(n)),'sha256':hashlib.sha256(origem.read(n)).hexdigest(),
                       'tratamento':'campos preenchidos' if n == 'word/document.xml' else 'preservado byte a byte'} for n in origem.namelist()]
        (pasta / 'inventario-original.json').write_text(json.dumps(inventario,indent=2,ensure_ascii=False),encoding='utf-8')
        assert origem.namelist() == saida.namelist()
        for nome in origem.namelist():
            if nome != 'word/document.xml':
                assert origem.read(nome) == saida.read(nome),nome
    (pasta / 'contrato-pj-exemplo.docx').write_bytes(docx)
    pdf = gerar_pdf_word(MODELO_PJ,valores)
    (pasta / 'contrato-pj-exemplo.pdf').write_bytes(pdf)
    from pypdf import PdfReader
    leitor = PdfReader(io.BytesIO(pdf))
    texto = '\n'.join(p.extract_text() for p in leitor.pages)
    assert f'1 ano, de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}' in ' '.join(texto.split())
    assert 'R$ 250,00 em dinheiro' in ' '.join(texto.split())
    assert '____' not in texto and '``' not in texto
    print(f'PDF gerado: {len(leitor.pages)} páginas. Pacote original preservado fora dos slots.')
    print(pasta / 'contrato-pj-exemplo.pdf')


if __name__ == '__main__':
    validar()
