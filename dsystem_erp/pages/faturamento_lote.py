"""Ações individuais e em lote no histórico A faturar."""
from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.services.fiscal_automatico import processar_emissoes, tipos_fiscais
from dsystem_erp.services.fiscal_documentos import consultar_documentos_fiscais, resultado_emissao
from dsystem_erp.services.pacote_faturamento import juntar_documentos_pdf


def processar_selecao(registros, ids, emitir, faturar, emitir_faturado):
    permitidos = {int(r['id']): r for r in registros}
    resultados = []
    for item_id in dict.fromkeys(int(i) for i in ids):
        fat = permitidos.get(item_id)
        try:
            if not fat or fat.get('status') == 'Cancelado':
                raise ValueError('Lançamento indisponível nesta seleção.')
            if fat.get('modalidade_faturamento') == 'Por medição' and not fat.get('medicao_principal_id'):
                raise ValueError('Fature cada medição parcial, não o lançamento principal.')
            if fat.get('status') == 'Faturado':
                if not emitir:
                    raise ValueError('Já faturado; nenhuma nova baixa realizada.')
                resultado = emitir_faturado(fat)
            else:
                resultado = faturar(fat, emitir_automaticamente=emitir)
            resultados.append(dict(id=item_id, **resultado))
        except Exception as erro:
            resultados.append(dict(id=item_id, ok=False, mensagem=str(erro)))
    return resultados


def continuar_faturado(fat):
    conn = conectar_banco()
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM faturamento WHERE id=? FOR UPDATE', (fat['id'],))
        atual = c.fetchone()
        if not atual or atual.get('status') != 'Faturado' or not tipos_fiscais(atual):
            raise ValueError('Este lançamento não possui emissão fiscal pendente aplicável.')
        c.execute('UPDATE faturamento SET emitir_automaticamente=1 WHERE id=?', (fat['id'],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    estados = processar_emissoes(conectar_banco, fat['id'], config_sistema_val, salvar_retorno_nota_fiscal)
    resultado = resultado_emissao(conectar_banco, fat['id'])
    resultado['mensagem'] = 'Sem repetir financeiro/estoque. ' + resultado['mensagem']
    return dict(ok=True, **resultado)


def renderizar_resultados_faturar(registros):
    # Conserva o último resultado nos reruns de download, mas nunca exibe documentos
    # de um lançamento que saiu da lista autorizada ao usuário.
    permitidos = {int(r['id']): r for r in registros}
    for resultado in st.session_state.get('fat_lote_resultados', []):
        fat = permitidos.get(int(resultado['id']))
        if not fat:
            continue
        mostrar = st.error if not resultado['ok'] else st.warning if resultado.get('fiscal_pronto') is False else st.success
        mostrar(f"#{resultado['id']}: {resultado['mensagem']}")
        if resultado.get('fiscal_pronto'):
            try:
                estado = consultar_documentos_fiscais(conectar_banco, resultado['id'])
                if not estado['pronto']:
                    st.warning('Documentos indisponíveis: ' + ' | '.join(estado['pendencias']))
                    continue
                documentos = estado['documentos']
                pacote = juntar_documentos_pdf(documentos, resultado['id'], fat.get('cliente') or '')
                st.download_button('Baixar notas prontas juntas', data=pacote,
                    file_name=f"notas_faturamento_{resultado['id']}.pdf", mime='application/pdf',
                    key=f"fat_prontas_{resultado['id']}", type='primary')
                for doc in documentos:
                    st.download_button(doc.titulo, data=doc.arquivo, file_name=doc.nome_arquivo,
                        mime='application/pdf', key=f"fat_pronta_{resultado['id']}_{doc.codigo}")
                st.caption('As notas também estão em Faturado → Enviar documentos. Confira o ambiente: homologação não tem validade fiscal.')
            except Exception as erro:
                st.warning(f'Não foi possível carregar os PDFs: {erro}. As autorizações foram preservadas; não reemita as notas.')


def renderizar_acoes_faturar(ctx, registros):
    aplicar_contexto_pagina(ctx, globals())
    st.markdown('#### Mudar status para faturado')
    st.caption('Ao faturar, o lançamento vai para Contas a Receber e baixa o estoque de produtos. Com emissão automática, o sistema monta e envia as notas usando a configuração fiscal autorizada. Os PDFs autorizados ficam juntos em Faturado.')
    renderizar_resultados_faturar(registros)
    pode = tem_permissao('faturamento.edit') or tem_permissao('faturamento.faturado.edit')
    if pode:
        with st.expander('Configurar emissão automática para os próximos faturamentos', expanded=False):
            st.caption('Configuração inicial: autorize reutilizar os dados fiscais de uma nota conferida. Com reconhecimento por item, códigos são localizados pelo vínculo ou nome exato, inclusive em novas combinações dos itens conhecidos. Vale para o mesmo cliente, emitente e operação; não escolhe códigos por semelhança.')
            from dsystem_erp.services.fiscal_modelos import criar_modelo
            from dsystem_erp.services.fiscal_automatico import listar_emissoes
            modelos_disponiveis = []
            carregar_modelos = st.toggle('Carregar configurações fiscais disponíveis', key='fat_modelos_carregar')
            for origem in (registros if carregar_modelos else []):
                for emissao in listar_emissoes(conectar_banco, origem['id']):
                    if emissao.get('estado') in ('Pronta', 'Autorizada') and emissao.get('plano_json'):
                        modelos_disponiveis.append((origem, emissao))
            if modelos_disponiveis:
                import json
                indice_modelo = st.selectbox('Configuração fiscal de referência:', list(range(len(modelos_disponiveis))),
                    format_func=lambda i: f"#{modelos_disponiveis[i][0]['id']} — {modelos_disponiveis[i][0].get('cliente')} — {modelos_disponiveis[i][1]['tipo']} — {json.loads(modelos_disponiveis[i][1]['plano_json'])['dados']['ambiente']}",
                    key='fat_modelo_referencia')
                autorizar_modelo = st.checkbox('Autorizo reutilizar este enquadramento fiscal nos próximos faturamentos equivalentes. Estou ciente de que produção emite notas reais.', key='fat_modelo_autorizar')
                reconhecer_itens = st.checkbox('Autorizar também cada item individualmente: reutilizar seus códigos pelo cadastro ou nome exato em novas combinações compatíveis.', key='fat_modelo_por_item')
                if st.button('Salvar configuração para faturar e emitir em um clique', disabled=not autorizar_modelo, key='fat_modelo_salvar'):
                    try:
                        origem, emissao = modelos_disponiveis[indice_modelo]
                        modelo = criar_modelo(origem, emissao, st.session_state.get('username', ''), por_item=reconhecer_itens)
                        salvar_config_sistema(modelo['chave'], json.dumps(modelo, ensure_ascii=False, default=str), 'Modelo fiscal autorizado para emissão ao faturar')
                        st.success('Configuração salva. Nos próximos lançamentos equivalentes, marque Emitir nota automaticamente e fature; não será necessário preparar cada nota.')
                    except Exception as erro:
                        st.error(str(erro))
            else:
                st.info('É necessária uma configuração fiscal inicial conferida para cada cliente e conjunto de itens. Não há referência disponível nesta lista. Configure a primeira nota em Emissão de Nota; depois autorize aqui a reutilização.')
    if st.button('Cancelar seleção múltipla' if st.session_state.get('fat_lote_ativo') else 'Selecionar vários lançamentos', disabled=not pode, key='fat_lote_alternar'):
        st.session_state['fat_lote_ativo'] = not st.session_state.get('fat_lote_ativo', False)
        st.session_state.pop('fat_lote_ids', None)
        st.session_state.pop('fat_lote_confirmar', None)
        st.rerun()
    if st.session_state.get('fat_lote_ativo') and pode:
        emitir = st.checkbox('Emitir notas automaticamente dos selecionados', key='fat_lote_emitir')
        elegiveis = {int(r['id']): r for r in registros if r.get('status') != 'Cancelado'
            and not (r.get('modalidade_faturamento') == 'Por medição' and not r.get('medicao_principal_id'))
            and (r.get('status') != 'Faturado' or (emitir and tipos_fiscais(r)))}
        anteriores = st.session_state.get('fat_lote_ids', [])
        if any(i not in elegiveis for i in anteriores):
            st.session_state['fat_lote_ids'] = [i for i in anteriores if i in elegiveis]
        ids = st.multiselect('Selecione um ou mais lançamentos:', list(elegiveis),
            format_func=lambda i: f"#{i} — {elegiveis[i].get('cliente')} — {formatar_moeda_br(elegiveis[i].get('valor_total'))} — {elegiveis[i].get('status') or 'Aberto'}",
            key='fat_lote_ids')
        if emitir:
            st.warning('O sistema confere a configuração das duas espécies antes de faturar, envia no ambiente salvo e gera os PDFs no mesmo processamento. PRODUÇÃO gera notas reais. Sem configuração válida, não fatura. Autorizações e resultados incertos nunca são reenviados. Já faturados não repetem financeiro/estoque.')
        confirmar = st.checkbox('Confirmo o processamento dos lançamentos selecionados e a opção de emissão acima.', key='fat_lote_confirmar')
        if st.button('Processar selecionados', type='primary', disabled=not ids or not confirmar, key='fat_lote_processar'):
            with st.spinner('Processando os lançamentos selecionados...'):
                st.session_state['fat_lote_resultados'] = processar_selecao(registros, ids, emitir, faturar_lancamento_com_integracoes, continuar_faturado)
            st.session_state.pop('fat_lote_ids', None)
            st.session_state.pop('fat_lote_confirmar', None)
            st.rerun()
    for fat in registros:
        status = fat.get('status') or 'Aberto'
        a, b, c, d, e = st.columns([0.7, 2.4, 1.4, 1.3, 2])
        a.write(f"#{fat['id']}")
        b.write(fat.get('cliente') or '')
        c.write(formatar_moeda_br(fat.get('valor_total')))
        d.write(status)
        if status == 'Cancelado':
            e.caption('Cancelado')
        elif fat.get('modalidade_faturamento') == 'Por medição' and not fat.get('medicao_principal_id'):
            e.caption('Fature pelas medições parciais')
        elif status == 'Faturado':
            e.success('Já faturado')
        else:
            emitir = e.checkbox('Emitir nota automaticamente', value=bool(fat.get('emitir_automaticamente')),
                disabled=not pode or not tipos_fiscais(fat), key=f"fat_auto_hist_{fat['id']}")
            if e.button('Faturar e emitir nota' if emitir else 'Marcar como faturado', disabled=not pode, key=f"hist_faturar_{fat['id']}", width='stretch'):
                with st.spinner('Preparando, emitindo e gerando os PDFs...' if emitir else 'Faturando...'):
                    st.session_state['fat_lote_resultados'] = processar_selecao([fat], [fat['id']], emitir, faturar_lancamento_com_integracoes, continuar_faturado)
                st.rerun()
