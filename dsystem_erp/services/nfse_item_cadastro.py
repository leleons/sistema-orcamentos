"""Localiza o código salvo por vínculo ou nome exato; não classifica por palavras."""
from dsystem_erp.services.nfe_item_cadastro import nome_normalizado
from dsystem_erp.services.nfse_catalogo_ti import codigo_nacional_salvo


def buscar_servico_dos_itens(itens, catalogo):
    selecionados = []
    for item in itens:
        if (item.get('tipo_item') or 'Serviço') != 'Serviço':
            continue
        identificador = item.get('servico_id') or item.get('nfse_servico_id')
        nome = nome_normalizado(item.get('desc'))
        candidatos = [s for s in catalogo if s.get('ativo', 'Sim') == 'Sim' and
            (str(s.get('id')) == str(identificador) if identificador else
             bool(nome) and nome_normalizado(s.get('nome')) == nome)]
        if len(candidatos) != 1 or not codigo_nacional_salvo(candidatos[0]):
            return dict(servico=None, mensagem=f"{item.get('desc') or 'Serviço'}: sem código nacional único no cadastro. Vincule ou cadastre o serviço uma vez.")
        candidato = candidatos[0]
        if item.get('codigo_servico') and codigo_nacional_salvo(item) != codigo_nacional_salvo(candidato):
            return dict(servico=None, mensagem='Código do item diverge do cadastro de serviço. Confira antes de emitir.')
        selecionados.append(candidato)
    if not selecionados:
        return dict(servico=None, mensagem='')
    if len({str(s['id']) for s in selecionados}) != 1:
        return dict(servico=None, mensagem='Há serviços de cadastros diferentes. Confira a separação e o enquadramento das NFS-e; nenhum código foi escolhido automaticamente.')
    return dict(servico=selecionados[0], mensagem='Código nacional preenchido automaticamente pelo serviço cadastrado. O desdobramento municipal usa a configuração salva para município e ambiente.')
