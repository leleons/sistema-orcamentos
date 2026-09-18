"""Telas de contas, lançamentos e cadastros financeiros."""

from __future__ import annotations

from datetime import date, timedelta

from dsystem_erp.app_context import aplicar_contexto_pagina
from dsystem_erp.ui_consulta import tabela_clicavel_id, tabela_clicavel_registro
from dsystem_erp.services.conciliacao import esta_baixado
from dsystem_erp.services.permissions import usuario_eh_gerencial


TIPOS_CONTA_EMPRESA = ("Conta bancária", "Caixa físico", "Boleto", "Cartão de crédito")
CAMPOS_BANCARIOS = {"banco": "Banco", "agencia": "Agência", "numero_conta": "Número da conta / dígito",
    "titular": "Titular", "documento_titular": "CPF/CNPJ do titular", "chave_pix": "Chave PIX"}


def campos_bancarios(registro, prefixo):
    colunas = st.columns(3)
    return {campo: colunas[i % 3].text_input(rotulo + ":", value=registro.get(campo) or "", key=f"{prefixo}_{campo}")
            for i, (campo, rotulo) in enumerate(CAMPOS_BANCARIOS.items())}


def selecionar_conta(coluna, rotulo, opcoes, atual, chave, bloqueado=False):
    if not usuario_eh_gerencial(st.session_state):
        coluna.caption("Conta da empresa: acesso restrito ao gerencial.")
        return atual
    escolhas = [""] + list(opcoes)
    if atual and atual not in escolhas:
        escolhas.append(atual)
    return coluna.selectbox(rotulo, escolhas, index=escolhas.index(atual or ""),
        format_func=lambda v: v or "Selecione uma conta cadastrada", key=chave, disabled=bloqueado)


def lancamento_esta_conciliado(registro: dict | None) -> bool:
    return str((registro or {}).get("conciliado") or "Não").strip().casefold() in {
        "sim", "1", "true", "yes",
    }


def total_itens_fatura_cartao(itens: list[dict] | None) -> float:
    return round(sum(max(0.0, float(item.get("valor") or 0)) for item in (itens or [])), 2)


def validar_prestador_terceirizado(
    ativo: bool,
    prestador: str,
    valor: float,
    historico: str,
) -> str | None:
    if not ativo:
        return None
    if not str(prestador or "").strip():
        return "Informe o prestador de serviço terceirizado."
    if float(valor or 0) <= 0:
        return "Informe um valor maior que zero para o prestador terceirizado."
    if not str(historico or "").strip():
        return "Informe o histórico do serviço prestado pelo terceiro."
    return None


def opcoes_contas_financeiras(registros: list[dict] | None) -> list[str]:
    opcoes = []
    for registro in registros or []:
        nome = str(registro.get("nome") or "").strip()
        tipo = str(registro.get("tipo") or "Conta financeira").strip()
        if nome:
            rotulo = f"{tipo} — {nome}"
            if rotulo not in opcoes:
                opcoes.append(rotulo)
    return opcoes


def montar_comparativo_pagar_receber(registros, parse_data) -> list[dict]:
    """Agrupa títulos não cancelados por mês de vencimento para o gráfico."""
    meses: dict[str, dict[str, float | str]] = {}
    for registro in registros or []:
        if (registro.get("status") or "") == "Cancelado":
            continue
        vencimento = parse_data(registro.get("data_vencimento"))
        chave = vencimento.strftime("%Y-%m") if vencimento else "Sem vencimento"
        linha = meses.setdefault(chave, {"Período": chave, "A pagar": 0.0, "A receber": 0.0})
        coluna = "A pagar" if registro.get("origem") == "Pagar" else "A receber"
        linha[coluna] = float(linha[coluna]) + float(registro.get("valor_total") or 0)
    return [meses[chave] for chave in sorted(meses, key=lambda item: (item == "Sem vencimento", item))]


def _renderizar_baixa_ou_cancelamento(
    registro: dict,
    *,
    tabela: str,
    eh_pagar: bool,
    prefixo: str,
) -> None:
    """Mostra ações seguras para um título selecionado no painel financeiro."""
    campo_parte = "fornecedor" if eh_pagar else "cliente"
    parte = registro.get(campo_parte) or "Não informado"
    registro_id = int(registro.get("id") or 0)
    status_atual = registro.get("status") or "Aberto"
    st.markdown(f"#### Lançamento #{registro_id} — {parte}")
    detalhe1, detalhe2, detalhe3 = st.columns(3)
    detalhe1.metric("Valor", formatar_moeda_br(registro.get("valor_total") or 0))
    detalhe2.metric("Vencimento", data_para_br(registro.get("data_vencimento")) or "Não informado")
    detalhe3.metric("Status", status_atual)

    if lancamento_esta_conciliado(registro):
        st.warning(
            f"Lançamento conciliado em {data_para_br(registro.get('data_conciliacao')) or 'data não informada'}. "
            "Ele está bloqueado para qualquer alteração."
        )
        return

    if status_atual in ("Pago", "Recebido", "Cancelado", "Baixado por perda"):
        st.info("Este lançamento já está encerrado. Os dados permanecem disponíveis no histórico.")
        return

    acao = st.radio(
        "O que deseja fazer?",
        ["Baixar lançamento", "Cancelar lançamento"],
        horizontal=True,
        key=f"{prefixo}_acao_{registro_id}",
    )
    if acao == "Baixar lançamento":
        baixa1, baixa2 = st.columns(2)
        data_baixa = baixa1.date_input(
            "Data da baixa:", value=date.today(), key=f"{prefixo}_data_{registro_id}"
        )
        valor_total = float(registro.get("valor_total") or 0)
        valor_baixa = baixa2.number_input(
            "Valor baixado R$:", min_value=0.01, value=max(0.01, valor_total),
            step=0.01, format="%.2f", key=f"{prefixo}_valor_{registro_id}",
        )
        observacao = st.text_area(
            "Observação da baixa:", key=f"{prefixo}_observacao_{registro_id}"
        )
        if st.button(
            "Confirmar baixa", type="primary", width="stretch",
            key=f"{prefixo}_confirmar_baixa_{registro_id}",
        ):
            status_final = "Pago" if eh_pagar else "Recebido"
            if valor_baixa < valor_total:
                status_final = "Pago parcial" if eh_pagar else "Recebido parcial"
            usuario = st.session_state.get("username", "")
            conn_acao = conectar_banco()
            c_acao = conn_acao.cursor()
            c_acao.execute(
                f"""UPDATE {tabela} SET status=?, data_baixa=?, valor_baixado=?,
                    observacao_baixa=?, baixado_por=?, alterado_por=?, alterado_em=? WHERE id=?""",
                (status_final, data_para_banco_br(data_baixa), valor_baixa, observacao,
                 usuario, usuario, agora_br(), registro_id),
            )
            conn_acao.commit()
            conn_acao.close()
            registrar_evento_sistema(
                "update", tabela, registro_id, parte,
                {"acao": "Baixa financeira", "status": status_final, "valor": valor_baixa},
            )
            st.session_state.pop(f"financeiro_dashboard_selecionado_{tabela}", None)
            st.success("Baixa registrada com sucesso.")
            st.rerun()
    else:
        motivo = st.text_area(
            "Motivo do cancelamento:", key=f"{prefixo}_motivo_cancelamento_{registro_id}"
        )
        confirmar = st.checkbox(
            "Confirmo que desejo cancelar este lançamento.",
            key=f"{prefixo}_confirmar_cancelamento_{registro_id}",
        )
        if st.button(
            "Cancelar lançamento", width="stretch", disabled=not confirmar,
            key=f"{prefixo}_cancelar_{registro_id}",
        ):
            if not motivo.strip():
                st.error("Informe o motivo do cancelamento.")
            else:
                usuario = st.session_state.get("username", "")
                conn_acao = conectar_banco()
                c_acao = conn_acao.cursor()
                c_acao.execute(
                    f"""UPDATE {tabela} SET status='Cancelado', cancelado_por=?,
                        motivo_cancelamento=?, alterado_por=?, alterado_em=? WHERE id=?""",
                    (usuario, motivo.strip(), usuario, agora_br(), registro_id),
                )
                conn_acao.commit()
                conn_acao.close()
                registrar_evento_sistema(
                    "update", tabela, registro_id, parte,
                    {"acao": "Cancelamento financeiro", "status": "Cancelado", "motivo": motivo.strip()},
                )
                st.session_state.pop(f"financeiro_dashboard_selecionado_{tabela}", None)
                st.success("Lançamento cancelado e mantido no histórico.")
                st.rerun()

def renderizar_conta_financeira(ctx, tipo):
    aplicar_contexto_pagina(ctx, globals())
    eh_pagar = tipo == "pagar"
    tabela = "contas_pagar" if eh_pagar else "contas_receber"
    permissao = "financeiro.pagar" if eh_pagar else "financeiro.receber"
    titulo = "Contas a Pagar" if eh_pagar else "Contas a Receber"
    parte_label = "Fornecedor" if eh_pagar else "Cliente"
    status_opcoes = (
        ["Aberto", "Agendado", "Aprovado", "Reprovado", "Pago", "Pago parcial", "Vencido", "Cancelado", "Renegociado"]
        if eh_pagar else
        ["Aberto", "Recebido", "Recebido parcial", "Vencido", "Em cobrança", "Renegociado", "Cancelado", "Protestado", "Baixado por perda"]
    )
    status_baixa = "Pago" if eh_pagar else "Recebido"
    forma_label = "Forma de pagamento" if eh_pagar else "Forma de recebimento"

    if not tem_permissao(permissao):
        st.error("Você não tem permissão para acessar este módulo.")
        return

    st.title(titulo)
    nomes_abas = ["Dashboard", "Novo lançamento", "Histórico e baixa", "Recorrências"]
    if not eh_pagar:
        nomes_abas.append("Cobrança e renegociação")
    aba_destino = st.session_state.pop(f"{tabela}_aba_destino", None)
    if aba_destino in nomes_abas:
        st.session_state[f"{tabela}_aba_ativa"] = aba_destino
    abas_fin = st.tabs(nomes_abas, key=f"{tabela}_aba_ativa", on_change="rerun")
    aba_dash, aba1, aba2, aba_rec = abas_fin[:4]
    aba_cobranca = abas_fin[4] if not eh_pagar else None

    clientes = buscar_clientes()
    conn_contas = conectar_banco()
    cursor_contas = conn_contas.cursor()
    cursor_contas.execute(
        """SELECT * FROM financeiro_cadastros_aux
           WHERE ativo='Sim' AND tipo IN ('Conta bancária', 'Caixa físico', 'Boleto', 'Cartão de crédito')
           ORDER BY tipo, nome"""
    )
    cadastros_contas = [dict(item) for item in cursor_contas.fetchall()]
    if not usuario_eh_gerencial(st.session_state):
        cadastros_contas = []
    conn_contas.close()
    contas_financeiras = opcoes_contas_financeiras(cadastros_contas)
    with aba_dash:
        conn_dash = conectar_banco()
        cdash = conn_dash.cursor()
        cdash.execute(f"SELECT * FROM {tabela} ORDER BY id DESC")
        dados_dash = [dict(r) for r in cdash.fetchall()]
        conn_dash.close()
        hoje = date.today()
        abertos = [r for r in dados_dash if r.get("status") not in ("Pago", "Recebido", "Cancelado", "Baixado por perda")]
        vencidos = [r for r in abertos if parse_data_flex(r.get("data_vencimento")) and parse_data_flex(r.get("data_vencimento")) < hoje]
        do_dia = [r for r in abertos if parse_data_flex(r.get("data_vencimento")) == hoje]
        previsto = sum(float(r.get("valor_total") or 0) for r in abertos)
        realizado = sum(float(r.get("valor_baixado") or 0) for r in dados_dash)
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Saldo previsto", formatar_moeda_br(previsto))
        d2.metric("Saldo realizado", formatar_moeda_br(realizado))
        d3.metric("Títulos vencidos", len(vencidos), formatar_moeda_br(sum(float(r.get("valor_total") or 0) for r in vencidos)))
        d4.metric("Vencimentos hoje", len(do_dia), formatar_moeda_br(sum(float(r.get("valor_total") or 0) for r in do_dia)))
        st.markdown("#### Lançamentos por vencimento")
        campo_parte_dash = "fornecedor" if eh_pagar else "cliente"
        fd1, fd2, fd3 = st.columns(3)
        filtro_parte_dash = fd1.text_input(
            f"Filtrar por {parte_label.lower()}:", key=f"{tabela}_dashboard_parte"
        ).strip().casefold()
        filtro_venc_inicio_dash = fd2.date_input(
            "Vencimento inicial:", value=None, key=f"{tabela}_dashboard_venc_inicio"
        )
        filtro_venc_fim_dash = fd3.date_input(
            "Vencimento final:", value=None, key=f"{tabela}_dashboard_venc_fim"
        )
        abertos_filtrados = []
        for registro in abertos:
            vencimento_registro = parse_data_flex(registro.get("data_vencimento"))
            if filtro_parte_dash and filtro_parte_dash not in str(registro.get(campo_parte_dash) or "").casefold():
                continue
            if filtro_venc_inicio_dash and (not vencimento_registro or vencimento_registro < filtro_venc_inicio_dash):
                continue
            if filtro_venc_fim_dash and (not vencimento_registro or vencimento_registro > filtro_venc_fim_dash):
                continue
            abertos_filtrados.append(registro)
        painel_lancamentos = [
            {
                "ID": registro.get("id"),
                parte_label: registro.get(campo_parte_dash) or "Não informado",
                "Vencimento": data_para_br(registro.get("data_vencimento")) or "Sem vencimento",
                "Valor": formatar_moeda_br(registro.get("valor_total") or 0),
                "Status": registro.get("status") or "Aberto",
                "Conciliado": registro.get("conciliado") or "Não",
            }
            for registro in sorted(
                abertos_filtrados,
                key=lambda item: (
                    parse_data_flex(item.get("data_vencimento")) or date.max,
                    str(item.get(campo_parte_dash) or "").lower(),
                ),
            )
        ]
        if painel_lancamentos:
            id_dashboard_clicado = tabela_clicavel_id(
                st, painel_lancamentos, f"{tabela}_dashboard_grade", "ID"
            )
            if id_dashboard_clicado is not None:
                st.session_state[f"financeiro_historico_selecionado_{tabela}"] = int(id_dashboard_clicado)
                st.session_state[f"{tabela}_aba_destino"] = "Histórico e baixa"
                st.rerun()
            st.caption(
                f"Este painel é somente para consulta. Clique em um lançamento para abri-lo na tela de histórico, "
                f"onde ficam as ações permitidas. A coluna {parte_label} identifica a pessoa ou empresa."
            )
        else:
            st.info("Nenhum lançamento aberto no momento.")
        st.download_button(
            "Baixar relatório financeiro",
            data=gerar_excel_tabela([
                {k: v for k, v in dict(r).items() if k not in ("anexo", "comprovante")}
                for r in dados_dash
            ], titulo),
            file_name=f"{tabela}.xls",
            mime="application/vnd.ms-excel",
            width="stretch",
        )

    with aba1:
        impostos_personalizados = []
        if not eh_pagar:
            conn_imp = conectar_banco()
            cimp = conn_imp.cursor()
            cimp.execute("SELECT * FROM financeiro_impostos_taxas WHERE ativo='Sim' ORDER BY nome")
            impostos_personalizados = [dict(item) for item in cimp.fetchall()]
            conn_imp.close()
            with st.expander("Cadastrar taxa ou imposto reutilizável", expanded=False):
                ci1, ci2, ci3 = st.columns(3)
                novo_imp_nome = ci1.text_input("Nome da taxa/imposto:", key="rec_novo_imp_nome")
                novo_imp_tipo = ci2.selectbox("Tipo:", ["Imposto", "Taxa"], key="rec_novo_imp_tipo")
                novo_imp_aliquota = ci3.number_input("Alíquota padrão (%):", min_value=0.0, max_value=100.0, step=0.01, format="%.4f", key="rec_novo_imp_aliquota")
                if st.button("Salvar para os próximos lançamentos", key="rec_salvar_imposto_taxa"):
                    if not novo_imp_nome.strip():
                        st.error("Informe o nome da taxa ou imposto.")
                    else:
                        conn_nimp = conectar_banco()
                        cnimp = conn_nimp.cursor()
                        cnimp.execute(
                            """INSERT INTO financeiro_impostos_taxas
                               (nome, tipo, aliquota_padrao, ativo, criado_por, criado_em)
                               VALUES (?,?,?,?,?,?)
                               ON DUPLICATE KEY UPDATE tipo=VALUES(tipo), aliquota_padrao=VALUES(aliquota_padrao), ativo='Sim'""",
                            (novo_imp_nome.strip(), novo_imp_tipo, novo_imp_aliquota, "Sim", st.session_state.get("username", ""), agora_br()),
                        )
                        conn_nimp.commit()
                        conn_nimp.close()
                        st.success("Taxa/imposto salvo para reutilização.")
                        st.rerun()

        fatura_cartao_ativa = False
        quantidade_itens_fatura = 0
        if eh_pagar:
            fatura_cartao_ativa = st.toggle(
                "Este lançamento é uma fatura de cartão de crédito",
                key="pagar_fatura_cartao_ativa",
            )
            if fatura_cartao_ativa:
                quantidade_itens_fatura = st.number_input(
                    "Quantidade de itens da fatura:", min_value=1, max_value=100,
                    value=1, step=1, key="pagar_fatura_cartao_qtd",
                )

        contexto_lancamento = st.form(f"form_{tabela}", clear_on_submit=True) if eh_pagar else st.container()
        with contexto_lancamento:
            p1, p2, p3 = st.columns(3)
            if eh_pagar:
                parte = p1.text_input("Fornecedor:")
                parte_id = None
                cpf_cnpj = p2.text_input("CNPJ/CPF:")
            else:
                parte = p1.selectbox("Cliente:", ["-- Selecionar --"] + [c["nome"] for c in clientes])
                cliente_sel = next((c for c in clientes if c["nome"] == parte), None)
                parte_id = cliente_sel.get("id") if cliente_sel else None
                cpf_cnpj = p2.text_input("CNPJ/CPF:", value=(cliente_sel.get("cnpj") or "") if cliente_sel else "")
            numero_documento = p3.text_input("Número do documento:")

            q1, q2, q3, q4 = st.columns(4)
            tipo_doc = q1.selectbox("Tipo de documento:" if eh_pagar else "Tipo de receita:", ["Boleto", "Nota fiscal", "Recibo", "Fatura", "Contrato", "Imposto", "Folha", "Serviço", "Produto", "Mensalidade", "Outro"])
            categoria = q2.text_input("Categoria financeira:")
            centro = q3.text_input("Centro de custo:" if eh_pagar else "Centro de receita:")
            plano = q4.text_input("Plano de contas:")

            r1, r2, r3, r4 = st.columns(4)
            conta_bancaria = selecionar_conta(r1, "Conta financeira:", contas_financeiras, "", f"{tabela}_conta_nova")
            data_emissao = r2.date_input("Data de emissão:", value=date.today())
            data_competencia = r3.date_input("Data de competência:", value=date.today())
            data_vencimento = r4.date_input("Data de vencimento:", value=date.today())

            v1, v2, v3, v4, v5 = st.columns(5)
            valor_original = v1.number_input(
                "Valor original R$:", min_value=0.0, step=0.01, format="%.2f",
                disabled=bool(eh_pagar and fatura_cartao_ativa),
                help="Em uma fatura de cartão, este valor é calculado pela soma dos itens.",
            )
            desconto = v2.number_input("Desconto R$:", min_value=0.0, step=0.01, format="%.2f")
            juros = v3.number_input("Juros R$:", min_value=0.0, step=0.01, format="%.2f")
            multa = v4.number_input("Multa R$:", min_value=0.0, step=0.01, format="%.2f")
            valor_total = max(0.0, valor_original - desconto + juros + multa)
            v5.metric("Valor total", formatar_moeda_br(valor_total))

            itens_fatura_cartao = []
            cartao_credito = ""
            if eh_pagar and fatura_cartao_ativa:
                st.markdown("#### Itens da fatura do cartão")
                cartoes_cadastrados = opcoes_contas_financeiras([
                    item for item in cadastros_contas if item.get("tipo") == "Cartão de crédito"
                ])
                cartao_credito = st.selectbox(
                    "Cartão da fatura:",
                    ["-- Selecione o cartão --"] + cartoes_cadastrados,
                    key="pagar_cartao_credito",
                )
                if cartao_credito == "-- Selecione o cartão --":
                    cartao_credito = ""
                for indice_item in range(int(quantidade_itens_fatura)):
                    fi1, fi2, fi3, fi4 = st.columns([3, 1.3, 1.8, 1.3])
                    descricao_item = fi1.text_input(
                        f"Descrição do item {indice_item + 1}:", key=f"pagar_fatura_desc_{indice_item}"
                    )
                    data_item = fi2.date_input(
                        f"Data {indice_item + 1}:", value=date.today(), key=f"pagar_fatura_data_{indice_item}"
                    )
                    categoria_item = fi3.text_input(
                        f"Categoria {indice_item + 1}:", key=f"pagar_fatura_categoria_{indice_item}"
                    )
                    valor_item = fi4.number_input(
                        f"Valor R$ {indice_item + 1}:", min_value=0.0, step=0.01,
                        format="%.2f", key=f"pagar_fatura_valor_{indice_item}"
                    )
                    if descricao_item or valor_item:
                        itens_fatura_cartao.append({
                            "descricao": descricao_item.strip(),
                            "data_compra": data_para_banco_br(data_item),
                            "categoria": categoria_item.strip(),
                            "valor": float(valor_item),
                        })
                valor_original = total_itens_fatura_cartao(itens_fatura_cartao)
                valor_total = max(0.0, valor_original - desconto + juros + multa)
                st.metric("Total composto pelos itens da fatura", formatar_moeda_br(valor_original))

            regime_tributario = "Normal"
            impostos_json = "[]"
            taxas_personalizadas_json = "[]"
            simples_aliquota = simples_valor = valor_impostos = 0.0
            valor_liquido = valor_total
            parcelado_txt = "Não"
            quantidade_parcelas = 1
            meio_parcelamento = ""
            parcelas_json = "[]"
            bandeira_cartao = ""
            custo_tipo = ""
            pedido_compra_id = None
            fornecedor_custo = ""
            custo_unitario = custo_total = lucro_estimado = margem_lucro_percentual = 0.0
            quantidade_custo = 1.0
            tem_terceiro = False
            terceiro_prestador = terceiro_documento = terceiro_historico = ""
            terceiro_valor = 0.0
            terceiro_vencimento = date.today()

            if not eh_pagar:
                st.markdown("#### Impostos e retenções")
                simples_nacional = st.checkbox(
                    "Optante pelo Simples Nacional",
                    key="rec_simples_nacional",
                    help="Ao marcar, os demais impostos e taxas ficam desabilitados neste lançamento.",
                )
                regime_tributario = "Simples Nacional" if simples_nacional else "Normal"
                simples_aliquota = st.number_input(
                    "Alíquota do Simples Nacional (%):", min_value=0.0, max_value=100.0,
                    step=0.01, format="%.4f", disabled=not simples_nacional, key="rec_simples_aliquota",
                )
                nomes_personalizados = [item["nome"] for item in impostos_personalizados]
                impostos_selecionados = st.multiselect(
                    "Impostos aplicáveis:", list(IMPOSTOS_PADRAO),
                    disabled=simples_nacional, key="rec_impostos_selecionados",
                )
                personalizados_selecionados = st.multiselect(
                    "Taxas/impostos personalizados:", nomes_personalizados,
                    disabled=simples_nacional, key="rec_personalizados_selecionados",
                )
                aliquotas_impostos = {}
                todos_selecionados = [(nome, 0.0, False) for nome in impostos_selecionados]
                todos_selecionados += [
                    (nome, float(next((x.get("aliquota_padrao") or 0 for x in impostos_personalizados if x.get("nome") == nome), 0)), True)
                    for nome in personalizados_selecionados
                ]
                if todos_selecionados:
                    colunas_aliquotas = st.columns(min(3, len(todos_selecionados)))
                    for indice_imp, (nome_imp, aliquota_padrao, _) in enumerate(todos_selecionados):
                        aliquotas_impostos[nome_imp] = colunas_aliquotas[indice_imp % len(colunas_aliquotas)].number_input(
                            f"{nome_imp} (%):", min_value=0.0, max_value=100.0,
                            value=aliquota_padrao, step=0.01, format="%.4f",
                            disabled=simples_nacional, key=f"rec_aliquota_{re.sub(r'[^A-Za-z0-9]+', '_', nome_imp)}",
                        )
                if simples_nacional:
                    simples_valor = round(valor_total * simples_aliquota / 100, 2)
                    valor_impostos = simples_valor
                    impostos_calculados = []
                    taxas_calculadas = []
                else:
                    impostos_padrao_calc = {nome: aliquotas_impostos.get(nome, 0) for nome in impostos_selecionados}
                    taxas_calc = {nome: aliquotas_impostos.get(nome, 0) for nome in personalizados_selecionados}
                    impostos_calculados, total_padrao = calcular_impostos(valor_total, impostos_padrao_calc)
                    taxas_calculadas, total_personalizado = calcular_impostos(valor_total, taxas_calc)
                    valor_impostos = round(total_padrao + total_personalizado, 2)
                valor_liquido = max(0.0, round(valor_total - valor_impostos, 2))
                impostos_json = json.dumps(impostos_calculados, ensure_ascii=False)
                taxas_personalizadas_json = json.dumps(taxas_calculadas, ensure_ascii=False)
                im1, im2, im3 = st.columns(3)
                im1.metric("Valor bruto", formatar_moeda_br(valor_total))
                im2.metric("Impostos/retenções", formatar_moeda_br(valor_impostos))
                im3.metric("Valor líquido previsto", formatar_moeda_br(valor_liquido))

                st.markdown("#### Custo do fornecedor e margem de lucro")
                custo_tipo = st.radio(
                    "Origem da venda:", ["Produto", "Serviço"], horizontal=True,
                    key="rec_custo_tipo", help="O lucro é calculado após descontar os impostos e o custo do fornecedor.",
                )
                if custo_tipo == "Produto":
                    conn_custos = conectar_banco()
                    ccustos = conn_custos.cursor()
                    ccustos.execute("""SELECT pc.id AS pedido_id, pc.produto, pc.quantidade_solicitada,
                                              COALESCE(cc.fornecedor, pc.fornecedor) AS fornecedor,
                                              cc.valor_item AS custo_unitario
                                       FROM pedidos_compra pc
                                       JOIN cotacoes_compra cc ON cc.pedido_compra_id=pc.id AND cc.escolhida=1
                                       ORDER BY pc.id DESC""")
                    compras_escolhidas = [dict(item) for item in ccustos.fetchall()]
                    ccustos.execute("SELECT id, produto, fornecedor, valor_custo FROM estoque ORDER BY produto")
                    produtos_estoque_custo = [dict(item) for item in ccustos.fetchall()]
                    conn_custos.close()
                    fontes_produto = {}
                    for compra in compras_escolhidas:
                        fontes_produto[f"Compra #{compra['pedido_id']} — {compra.get('produto')} — {compra.get('fornecedor')}"] = {
                            "pedido_id": compra.get("pedido_id"), "fornecedor": compra.get("fornecedor") or "",
                            "custo": float(compra.get("custo_unitario") or 0),
                        }
                    for produto_custo in produtos_estoque_custo:
                        fontes_produto[f"Estoque #{produto_custo['id']} — {produto_custo.get('produto')}"] = {
                            "pedido_id": None, "fornecedor": produto_custo.get("fornecedor") or "",
                            "custo": float(decimal_valor(produto_custo.get("valor_custo"))),
                        }
                    if fontes_produto:
                        fonte_label = st.selectbox("Produto/compra de origem:", list(fontes_produto), key="rec_produto_origem")
                        fonte_produto = fontes_produto[fonte_label]
                        pedido_compra_id = fonte_produto["pedido_id"]
                        fornecedor_custo = fonte_produto["fornecedor"]
                        custo_unitario = fonte_produto["custo"]
                        cp1, cp2, cp3 = st.columns(3)
                        cp1.text_input("Fornecedor original:", value=fornecedor_custo, disabled=True, key=f"rec_fornecedor_prod_{fonte_label}")
                        cp2.number_input("Custo unitário original (R$):", value=custo_unitario, disabled=True, format="%.2f", key=f"rec_custo_prod_{fonte_label}")
                        quantidade_custo = cp3.number_input("Quantidade vendida:", min_value=0.001, value=1.0, step=1.0, format="%.3f", key="rec_quantidade_custo")
                    else:
                        st.warning("Não há produto no estoque nem compra com cotação escolhida. Cadastre o produto ou finalize uma cotação no módulo Compras.")
                else:
                    cs1, cs2, cs3 = st.columns(3)
                    fornecedor_custo = cs1.text_input("Fornecedor do serviço:", key="rec_fornecedor_servico")
                    custo_unitario = cs2.number_input("Custo original do serviço (R$):", min_value=0.0, step=0.01, format="%.2f", key="rec_custo_servico")
                    quantidade_custo = cs3.number_input("Quantidade do serviço:", min_value=0.001, value=1.0, step=1.0, format="%.3f", key="rec_quantidade_servico")

                margem_calculada = calcular_margem_lucro(valor_total, valor_impostos, custo_unitario, quantidade_custo)
                custo_total = float(margem_calculada["custo_total"])
                lucro_estimado = float(margem_calculada["lucro_estimado"])
                margem_lucro_percentual = float(margem_calculada["margem_percentual"])
                ml1, ml2, ml3, ml4 = st.columns(4)
                ml1.metric("Receita líquida", formatar_moeda_br(margem_calculada["receita_liquida"]))
                ml2.metric("Custo do fornecedor", formatar_moeda_br(custo_total))
                ml3.metric("Lucro estimado", formatar_moeda_br(lucro_estimado))
                ml4.metric("Margem líquida", f"{margem_lucro_percentual:.2f}%".replace(".", ","))
                if lucro_estimado < 0:
                    st.error("Atenção: este lançamento está com margem negativa após impostos e custo do fornecedor.")

                st.markdown("#### Prestador de serviço terceirizado")
                tem_terceiro = st.checkbox(
                    "Este recebimento possui um prestador terceirizado a pagar",
                    key="rec_tem_terceiro",
                    help="Ao salvar, será criado automaticamente um lançamento vinculado em Contas a Pagar.",
                )
                if tem_terceiro:
                    terceiros_cadastrados = [
                        cliente for cliente in clientes
                        if str(cliente.get("tipo") or "").casefold() in {"fornecedor", "ambos"}
                    ]
                    terceiro_opcao = st.selectbox(
                        "Prestador cadastrado:",
                        ["-- Digitar prestador manualmente --"] + [item.get("nome") or "" for item in terceiros_cadastrados],
                        key="rec_terceiro_cadastro",
                    )
                    terceiro_cadastrado = next(
                        (item for item in terceiros_cadastrados if item.get("nome") == terceiro_opcao), None
                    )
                    ter1, ter2, ter3 = st.columns(3)
                    if terceiro_cadastrado:
                        terceiro_prestador = terceiro_cadastrado.get("nome") or ""
                        terceiro_documento = terceiro_cadastrado.get("cnpj") or ""
                        ter1.text_input(
                            "Prestador de serviço:", value=terceiro_prestador, disabled=True,
                            key=f"rec_terceiro_prestador_cadastrado_{terceiro_cadastrado.get('id')}",
                        )
                        ter2.text_input(
                            "CPF/CNPJ do prestador:", value=terceiro_documento, disabled=True,
                            key=f"rec_terceiro_documento_cadastrado_{terceiro_cadastrado.get('id')}",
                        )
                    else:
                        terceiro_prestador = ter1.text_input(
                            "Prestador de serviço:", key="rec_terceiro_prestador_manual"
                        )
                        terceiro_documento = ter2.text_input(
                            "CPF/CNPJ do prestador:", key="rec_terceiro_documento_manual"
                        )
                    terceiro_valor = ter3.number_input(
                        "Valor a pagar ao prestador R$:", min_value=0.0, step=0.01,
                        format="%.2f", key="rec_terceiro_valor",
                    )
                    ter4, ter5 = st.columns([1, 3])
                    terceiro_vencimento = ter4.date_input(
                        "Vencimento do pagamento:", value=date.today(), key="rec_terceiro_vencimento"
                    )
                    terceiro_historico = ter5.text_area(
                        "Histórico do serviço prestado:", height=90, key="rec_terceiro_historico"
                    )

                st.markdown("#### Parcelamento")
                parcelado = st.checkbox("Recebimento parcelado", key="rec_parcelado")
                parcelado_txt = "Sim" if parcelado else "Não"
                par1, par2, par3 = st.columns(3)
                quantidade_parcelas = par1.number_input(
                    "Quantidade de parcelas:", min_value=1, max_value=48, value=1,
                    step=1, disabled=not parcelado, key="rec_quantidade_parcelas",
                )
                meio_parcelamento = par2.selectbox(
                    "Meio das parcelas:", ["Boleto", "Cartão de crédito"],
                    disabled=not parcelado, key="rec_meio_parcelamento",
                )
                bandeira_cartao = par3.selectbox(
                    "Bandeira do cartão:", ["Visa", "Mastercard", "Elo", "American Express", "Hipercard", "Outra"],
                    disabled=not parcelado or meio_parcelamento != "Cartão de crédito", key="rec_bandeira_cartao",
                )
                parcelas_geradas = gerar_parcelas(
                    valor_total, int(quantidade_parcelas if parcelado else 1), data_vencimento,
                    meio_parcelamento if parcelado else "À vista",
                )
                parcelas_json = json.dumps(parcelas_geradas, ensure_ascii=False)
                if parcelado:
                    st.dataframe([
                        {"Parcela": f"{p['numero']}/{quantidade_parcelas}", "Vencimento": p["vencimento"], "Valor": formatar_moeda_br(p["valor"]), "Meio": p["meio"]}
                        for p in parcelas_geradas
                    ], width="stretch", hide_index=True)

            s1, s2 = st.columns(2)
            forma = s1.selectbox(forma_label + ":", ["PIX", "Boleto", "Transferência", "TED", "Cartão de crédito", "Dinheiro", "Outro"])
            status = s2.selectbox("Status:", status_opcoes)

            conciliado_novo = False
            data_conciliacao_nova = None
            st.caption("A conciliação fica disponível no Histórico e baixa, após registrar a baixa integral.")

            if eh_pagar:
                x1, x2 = st.columns(2)
                extra1 = x1.text_input("Código de barras:")
                extra2 = x2.text_input("Chave PIX:")
            else:
                x1, x2 = st.columns(2)
                extra1 = x1.text_input("Nota fiscal vinculada:")
                extra2 = x2.text_input("Boleto vinculado:")
            observacoes = st.text_area("Observações:", height=90)
            anexo_lancamento = st.file_uploader("Anexo do lançamento (nota, boleto, contrato ou comprovante):", key=f"{tabela}_anexo_novo")

            salvar = st.form_submit_button("Salvar lançamento", type="primary", width="stretch") if eh_pagar else st.button("Salvar lançamento", type="primary", width="stretch", key="salvar_conta_receber")
            if salvar:
                parte_valida = parte and parte != "-- Selecionar --"
                fatura_invalida = bool(
                    eh_pagar and fatura_cartao_ativa
                    and (not cartao_credito or not itens_fatura_cartao or valor_original <= 0)
                )
                erro_terceiro = validar_prestador_terceirizado(
                    bool(not eh_pagar and tem_terceiro),
                    terceiro_prestador,
                    terceiro_valor,
                    terceiro_historico,
                )
                if not parte_valida or valor_total <= 0:
                    st.error(f"Informe {parte_label.lower()} e um valor maior que zero.")
                elif fatura_invalida:
                    st.error("Selecione o cartão e informe pelo menos um item com valor na fatura.")
                elif erro_terceiro:
                    st.error(erro_terceiro)
                else:
                    if anexo_lancamento and not upload_dentro_limite(anexo_lancamento):
                        erro_upload_grande("anexo")
                        st.stop()
                    anexo_dados, anexo_nome, anexo_mime = dados_upload(anexo_lancamento)
                    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
                    usuario = st.session_state.get("username", "")
                    conn = conectar_banco()
                    c = conn.cursor()
                    conciliado_txt = "Sim" if conciliado_novo else "Não"
                    data_conciliacao_txt = data_para_banco_br(data_conciliacao_nova) if conciliado_novo else ""
                    conciliado_por = usuario if conciliado_novo else ""
                    if eh_pagar:
                        tipo_doc_salvar = "Fatura de cartão de crédito" if fatura_cartao_ativa else tipo_doc
                        forma_salvar = "Cartão de crédito" if fatura_cartao_ativa else forma
                        c.execute("""INSERT INTO contas_pagar
                            (fornecedor, cpf_cnpj, numero_documento, tipo_documento, categoria, centro_custo,
                             plano_contas, conta_bancaria, data_emissao, data_competencia, data_vencimento,
                             valor_original, desconto, juros, multa, valor_total, forma_pagamento,
                             codigo_barras, chave_pix, status, observacoes, criado_por, criado_em,
                             anexo_nome, anexo_mime, anexo, solicitante, status_aprovacao,
                             conciliado, data_conciliacao, conciliado_por, fatura_cartao,
                             cartao_credito, itens_fatura_cartao)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (parte, cpf_cnpj, numero_documento, tipo_doc_salvar, categoria, centro, plano, conta_bancaria,
                             data_para_banco_br(data_emissao), data_para_banco_br(data_competencia), data_para_banco_br(data_vencimento),
                             valor_original, desconto, juros, multa, valor_total, forma_salvar, extra1, extra2, status, observacoes,
                             usuario, agora, anexo_nome, anexo_mime, anexo_dados, usuario, "Pendente",
                             conciliado_txt, data_conciliacao_txt, conciliado_por,
                             "Sim" if fatura_cartao_ativa else "Não", cartao_credito,
                             json.dumps(itens_fatura_cartao, ensure_ascii=False)))
                        conta_pagar_id = c.lastrowid
                        if fatura_cartao_ativa:
                            for item_fatura in itens_fatura_cartao:
                                c.execute(
                                    """INSERT INTO financeiro_fatura_cartao_itens
                                       (conta_pagar_id, descricao, data_compra, categoria, valor, criado_por, criado_em)
                                       VALUES (?,?,?,?,?,?,?)""",
                                    (conta_pagar_id, item_fatura["descricao"], item_fatura["data_compra"],
                                     item_fatura["categoria"], item_fatura["valor"], usuario, agora),
                                )
                    else:
                        c.execute("""INSERT INTO contas_receber
                            (cliente_id, cliente, cpf_cnpj, numero_documento, tipo_receita, categoria, centro_receita,
                             plano_contas, conta_bancaria, data_emissao, data_competencia, data_vencimento,
                             valor_original, desconto, juros, multa, valor_total, forma_recebimento,
                             nota_fiscal, boleto, status, observacoes, criado_por, criado_em,
                             anexo_nome, anexo_mime, anexo, regime_tributario, impostos,
                             simples_aliquota, simples_valor, taxas_personalizadas, valor_impostos,
                             valor_liquido, parcelado, quantidade_parcelas, meio_parcelamento,
                             parcelas_detalhes, bandeira_cartao, custo_tipo, pedido_compra_id,
                             fornecedor_custo, custo_unitario, quantidade_custo, custo_total,
                             lucro_estimado, margem_lucro_percentual, conciliado,
                             data_conciliacao, conciliado_por, tem_terceiro,
                             terceiro_prestador, terceiro_documento, terceiro_valor,
                             terceiro_historico, terceiro_vencimento)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (parte_id, parte, cpf_cnpj, numero_documento, tipo_doc, categoria, centro, plano, conta_bancaria,
                             data_para_banco_br(data_emissao), data_para_banco_br(data_competencia), data_para_banco_br(data_vencimento),
                             valor_original, desconto, juros, multa, valor_total, forma, extra1, extra2, status, observacoes,
                             usuario, agora, anexo_nome, anexo_mime, anexo_dados, regime_tributario,
                             impostos_json, simples_aliquota, simples_valor, taxas_personalizadas_json,
                             valor_impostos, valor_liquido, parcelado_txt, int(quantidade_parcelas),
                             meio_parcelamento, parcelas_json, bandeira_cartao, custo_tipo, pedido_compra_id,
                             fornecedor_custo, custo_unitario, quantidade_custo, custo_total,
                             lucro_estimado, margem_lucro_percentual, conciliado_txt,
                             data_conciliacao_txt, conciliado_por, "Sim" if tem_terceiro else "Não",
                             terceiro_prestador.strip(), terceiro_documento.strip(), terceiro_valor,
                             terceiro_historico.strip(), data_para_banco_br(terceiro_vencimento) if tem_terceiro else ""))
                        conta_receber_id = c.lastrowid
                        if tem_terceiro:
                            c.execute(
                                """INSERT INTO contas_pagar
                                   (fornecedor, cpf_cnpj, numero_documento, tipo_documento, categoria,
                                    centro_custo, plano_contas, conta_bancaria, data_emissao,
                                    data_competencia, data_vencimento, valor_original, desconto,
                                    juros, multa, valor_total, forma_pagamento, status, observacoes,
                                    criado_por, criado_em, solicitante, status_aprovacao, conciliado,
                                    conta_receber_origem_id)
                                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                (terceiro_prestador.strip(), terceiro_documento.strip(),
                                 f"TERC-REC-{conta_receber_id}", "Serviço terceirizado",
                                 "Serviço terceirizado", centro, plano, "",
                                 data_para_banco_br(date.today()), data_para_banco_br(data_competencia),
                                 data_para_banco_br(terceiro_vencimento), terceiro_valor, 0, 0, 0,
                                 terceiro_valor, "", "Aberto",
                                 f"Gerado pelo Contas a Receber #{conta_receber_id}. "
                                 f"Histórico: {terceiro_historico.strip()}",
                                 usuario, agora, usuario, "Pendente", "Não", conta_receber_id),
                            )
                            conta_pagar_terceiro_id = c.lastrowid
                            c.execute(
                                """UPDATE contas_receber
                                   SET terceiro_conta_pagar_id=?
                                   WHERE id=? AND terceiro_conta_pagar_id IS NULL""",
                                (conta_pagar_terceiro_id, conta_receber_id),
                            )
                    conn.commit()
                    conn.close()
                    st.success("Lançamento salvo.")
                    st.rerun()

    with aba2:
        f1, f2, f3 = st.columns(3)
        filtro_status = f1.selectbox("Filtrar por status:", ["Todos"] + status_opcoes, key=f"{tabela}_status")
        busca = f2.text_input(f"Buscar {parte_label.lower()}/documento:", key=f"{tabela}_busca")
        filtro_vencimento = f3.date_input("Vencimento até:", value=None, key=f"{tabela}_venc")
        filtro_conciliacao = st.selectbox("Filtrar por conciliação:",
            ["Todos", "Baixados — pendentes de conciliação", "Conciliados", "Não conciliados"],
            key=f"{tabela}_filtro_conciliacao")

        conn = conectar_banco()
        c = conn.cursor()
        c.execute(f"SELECT * FROM {tabela} ORDER BY id DESC")
        registros = [dict(r) for r in c.fetchall()]
        conn.close()
        campo_parte = "fornecedor" if eh_pagar else "cliente"
        if filtro_conciliacao == "Baixados — pendentes de conciliação":
            registros = [r for r in registros if esta_baixado(r) and not lancamento_esta_conciliado(r)]
        elif filtro_conciliacao == "Conciliados":
            registros = [r for r in registros if lancamento_esta_conciliado(r)]
        elif filtro_conciliacao == "Não conciliados":
            registros = [r for r in registros if not lancamento_esta_conciliado(r)]
        if filtro_status != "Todos":
            registros = [r for r in registros if r.get("status") == filtro_status]
        if busca.strip():
            termo = busca.strip().lower()
            registros = [r for r in registros if termo in f"{r.get(campo_parte, '')} {r.get('numero_documento', '')}".lower()]
        if filtro_vencimento:
            registros = [r for r in registros if parse_data_flex(r.get("data_vencimento")) and parse_data_flex(r.get("data_vencimento")) <= filtro_vencimento]

        resumo = [{
            "ID": r.get("id"), parte_label: r.get(campo_parte), "Documento": r.get("numero_documento"),
            "Vencimento": data_para_br(r.get("data_vencimento")), "Valor": formatar_moeda_br(r.get("valor_total")),
            "Conciliado": r.get("conciliado") or "Não",
            "Data da conciliação": data_para_br(r.get("data_conciliacao")),
            "Conciliado por": r.get("conciliado_por") or "",
            **({
                "Regime": r.get("regime_tributario") or "Normal",
                "Impostos": formatar_moeda_br(r.get("valor_impostos") or 0),
                "Líquido": formatar_moeda_br(r.get("valor_liquido") or r.get("valor_total") or 0),
                "Parcelas": r.get("quantidade_parcelas") or 1,
                "Meio": r.get("meio_parcelamento") or r.get("forma_recebimento") or "",
                "Origem": r.get("custo_tipo") or "",
                "Fornecedor do custo": r.get("fornecedor_custo") or "",
                "Custo": formatar_moeda_br(r.get("custo_total") or 0),
                "Lucro estimado": formatar_moeda_br(r.get("lucro_estimado") or 0),
                "Margem líquida": f"{float(r.get('margem_lucro_percentual') or 0):.2f}%".replace(".", ","),
                "Prestador terceiro": r.get("terceiro_prestador") or "",
                "Valor do terceiro": formatar_moeda_br(r.get("terceiro_valor") or 0),
                "Conta a pagar vinculada": r.get("terceiro_conta_pagar_id") or "",
            } if not eh_pagar else {}),
            "Status": r.get("status"), "Baixado": formatar_moeda_br(r.get("valor_baixado")),
        } for r in registros]
        id_financeiro_selecionado = None
        if resumo:
            id_financeiro_clicado = tabela_clicavel_id(st, resumo, f"{tabela}_grade_consulta", "ID")
            if id_financeiro_clicado is not None:
                st.session_state[f"financeiro_historico_selecionado_{tabela}"] = int(id_financeiro_clicado)
            id_financeiro_selecionado = st.session_state.get(f"financeiro_historico_selecionado_{tabela}")
            ids_financeiros_visiveis = {int(item.get("id") or 0) for item in registros}
            if int(id_financeiro_selecionado or 0) not in ids_financeiros_visiveis:
                st.session_state.pop(f"financeiro_historico_selecionado_{tabela}", None)
                id_financeiro_selecionado = None
            st.caption("Clique em qualquer informação do lançamento para abrir a consulta, baixa ou cancelamento.")
        else:
            st.info("Nenhum lançamento encontrado.")

        if registros and tem_permissao(f"{permissao}.edit"):
            st.write("---")
            if not id_financeiro_selecionado:
                st.info("Clique em um lançamento da tabela para baixar ou cancelar.")
            id_baixa = int(id_financeiro_selecionado or 0)
            registro = next((r for r in registros if int(r.get("id") or 0) == int(id_baixa)), None)
            if registro:
                bloqueado_conciliacao = lancamento_esta_conciliado(registro)
                if bloqueado_conciliacao:
                    st.warning(
                        f"Este lançamento foi conciliado em "
                        f"{data_para_br(registro.get('data_conciliacao')) or 'data não informada'} e está bloqueado para alterações."
                    )
                if registro.get("anexo"):
                    st.download_button(
                        f"Baixar anexo: {registro.get('anexo_nome') or 'arquivo'}",
                        data=registro.get("anexo"),
                        file_name=registro.get("anexo_nome") or "anexo",
                        mime=registro.get("anexo_mime") or "application/octet-stream",
                        key=f"{tabela}_baixar_anexo_{id_baixa}",
                    )
                if eh_pagar and registro.get("fatura_cartao") == "Sim":
                    st.markdown(f"**Fatura do cartão:** {registro.get('cartao_credito') or 'Não informado'}")
                    try:
                        itens_fatura_salvos = json.loads(registro.get("itens_fatura_cartao") or "[]")
                    except (TypeError, ValueError, json.JSONDecodeError):
                        itens_fatura_salvos = []
                    if itens_fatura_salvos:
                        st.dataframe([
                            {
                                "Descrição": item.get("descricao"),
                                "Data": data_para_br(item.get("data_compra")),
                                "Categoria": item.get("categoria"),
                                "Valor": formatar_moeda_br(item.get("valor") or 0),
                            }
                            for item in itens_fatura_salvos
                        ], width="stretch", hide_index=True)

                if eh_pagar and registro.get("conta_receber_origem_id"):
                    conta_receber_origem_id = int(registro.get("conta_receber_origem_id") or 0)
                    st.info(
                        f"Este pagamento foi gerado pelo prestador terceirizado do "
                        f"Contas a Receber #{conta_receber_origem_id}."
                    )
                    if st.button(
                        f"Abrir Contas a Receber #{conta_receber_origem_id}",
                        key=f"abrir_receber_origem_{id_baixa}",
                    ):
                        st.session_state["financeiro_historico_selecionado_contas_receber"] = conta_receber_origem_id
                        st.session_state["contas_receber_aba_destino"] = "Histórico e baixa"
                        st.session_state["pagina_atual"] = "Contas a Receber"
                        st.rerun()

                if not eh_pagar:
                    conta_pagar_terceiro_id = int(registro.get("terceiro_conta_pagar_id") or 0)
                    if conta_pagar_terceiro_id:
                        st.markdown("#### Prestador terceirizado vinculado")
                        ter_info1, ter_info2, ter_info3 = st.columns(3)
                        ter_info1.metric("Prestador", registro.get("terceiro_prestador") or "Não informado")
                        ter_info2.metric("Valor a pagar", formatar_moeda_br(registro.get("terceiro_valor") or 0))
                        ter_info3.metric(
                            "Vencimento",
                            data_para_br(registro.get("terceiro_vencimento")) or "Não informado",
                        )
                        st.caption(
                            f"Histórico: {registro.get('terceiro_historico') or 'Não informado'} · "
                            f"Contas a Pagar #{conta_pagar_terceiro_id}"
                        )
                        if st.button(
                            f"Abrir Contas a Pagar #{conta_pagar_terceiro_id}",
                            key=f"abrir_pagar_terceiro_{id_baixa}",
                        ):
                            st.session_state["financeiro_historico_selecionado_contas_pagar"] = conta_pagar_terceiro_id
                            st.session_state["contas_pagar_aba_destino"] = "Histórico e baixa"
                            st.session_state["pagina_atual"] = "Contas a Pagar"
                            st.rerun()
                    elif not bloqueado_conciliacao:
                        with st.expander("Adicionar prestador terceirizado a este recebimento", expanded=False):
                            ter_exist1, ter_exist2, ter_exist3 = st.columns(3)
                            terceiro_existente_prestador = ter_exist1.text_input(
                                "Prestador de serviço:", key=f"terceiro_existente_nome_{id_baixa}"
                            )
                            terceiro_existente_documento = ter_exist2.text_input(
                                "CPF/CNPJ:", key=f"terceiro_existente_doc_{id_baixa}"
                            )
                            terceiro_existente_valor = ter_exist3.number_input(
                                "Valor a pagar R$:", min_value=0.0, step=0.01, format="%.2f",
                                key=f"terceiro_existente_valor_{id_baixa}",
                            )
                            ter_exist4, ter_exist5 = st.columns([1, 3])
                            terceiro_existente_vencimento = ter_exist4.date_input(
                                "Vencimento:", value=date.today(),
                                key=f"terceiro_existente_venc_{id_baixa}",
                            )
                            terceiro_existente_historico = ter_exist5.text_area(
                                "Histórico do serviço:", height=90,
                                key=f"terceiro_existente_hist_{id_baixa}",
                            )
                            if st.button(
                                "Gerar Contas a Pagar do prestador", type="primary", width="stretch",
                                key=f"gerar_pagar_terceiro_{id_baixa}",
                            ):
                                erro_terceiro_existente = validar_prestador_terceirizado(
                                    True, terceiro_existente_prestador,
                                    terceiro_existente_valor, terceiro_existente_historico,
                                )
                                if erro_terceiro_existente:
                                    st.error(erro_terceiro_existente)
                                else:
                                    usuario_terceiro = st.session_state.get("username", "")
                                    agora_terceiro = agora_br()
                                    conn_terceiro = conectar_banco()
                                    cursor_terceiro = conn_terceiro.cursor()
                                    try:
                                        cursor_terceiro.execute(
                                            """SELECT terceiro_conta_pagar_id, conciliado
                                               FROM contas_receber WHERE id=? FOR UPDATE""",
                                            (id_baixa,),
                                        )
                                        estado_terceiro = cursor_terceiro.fetchone() or {}
                                        if estado_terceiro.get("terceiro_conta_pagar_id"):
                                            raise ValueError("Este recebimento já possui um pagamento de terceiro vinculado.")
                                        if lancamento_esta_conciliado(estado_terceiro):
                                            raise ValueError("O recebimento foi conciliado e não pode mais ser alterado.")
                                        cursor_terceiro.execute(
                                            """INSERT INTO contas_pagar
                                               (fornecedor, cpf_cnpj, numero_documento, tipo_documento,
                                                categoria, centro_custo, plano_contas, conta_bancaria,
                                                data_emissao, data_competencia, data_vencimento,
                                                valor_original, desconto, juros, multa, valor_total,
                                                forma_pagamento, status, observacoes, criado_por, criado_em,
                                                solicitante, status_aprovacao, conciliado, conta_receber_origem_id)
                                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                            (terceiro_existente_prestador.strip(), terceiro_existente_documento.strip(),
                                             f"TERC-REC-{id_baixa}", "Serviço terceirizado",
                                             "Serviço terceirizado", registro.get("centro_receita") or "",
                                             registro.get("plano_contas") or "", "", data_para_banco_br(date.today()),
                                             registro.get("data_competencia") or data_para_banco_br(date.today()),
                                             data_para_banco_br(terceiro_existente_vencimento),
                                             terceiro_existente_valor, 0, 0, 0, terceiro_existente_valor,
                                             "", "Aberto", f"Gerado pelo Contas a Receber #{id_baixa}. "
                                             f"Histórico: {terceiro_existente_historico.strip()}",
                                             usuario_terceiro, agora_terceiro, usuario_terceiro,
                                             "Pendente", "Não", id_baixa),
                                        )
                                        novo_pagar_terceiro_id = cursor_terceiro.lastrowid
                                        cursor_terceiro.execute(
                                            """UPDATE contas_receber SET tem_terceiro='Sim',
                                               terceiro_prestador=?, terceiro_documento=?, terceiro_valor=?,
                                               terceiro_historico=?, terceiro_vencimento=?,
                                               terceiro_conta_pagar_id=?, alterado_por=?, alterado_em=?
                                               WHERE id=? AND terceiro_conta_pagar_id IS NULL
                                               AND COALESCE(conciliado, 'Não') <> 'Sim'""",
                                            (terceiro_existente_prestador.strip(), terceiro_existente_documento.strip(),
                                             terceiro_existente_valor, terceiro_existente_historico.strip(),
                                             data_para_banco_br(terceiro_existente_vencimento),
                                             novo_pagar_terceiro_id, usuario_terceiro, agora_terceiro, id_baixa),
                                        )
                                        if cursor_terceiro.rowcount != 1:
                                            raise ValueError("Não foi possível vincular o prestador ao recebimento.")
                                        conn_terceiro.commit()
                                    except Exception as erro_vinculo:
                                        conn_terceiro.rollback()
                                        st.error(str(erro_vinculo))
                                    else:
                                        registrar_evento_sistema(
                                            "update", "contas_receber", id_baixa,
                                            registro.get("cliente") or "",
                                            {"evento": "Prestador terceirizado vinculado",
                                             "conta_pagar_id": novo_pagar_terceiro_id,
                                             "prestador": terceiro_existente_prestador.strip(),
                                             "valor": terceiro_existente_valor},
                                        )
                                        st.success("Prestador vinculado e Contas a Pagar gerado.")
                                        st.rerun()
                                    finally:
                                        conn_terceiro.close()

                with st.expander("Editar valor, vencimento, conta e conciliação", expanded=False):
                    ed1, ed2, ed3 = st.columns(3)
                    valor_original_editado = ed1.number_input(
                        "Valor original R$:", min_value=0.0,
                        value=float(registro.get("valor_original") or 0), step=0.01, format="%.2f",
                        disabled=bloqueado_conciliacao, key=f"{tabela}_editar_valor_{id_baixa}",
                    )
                    vencimento_atual = parse_data_flex(registro.get("data_vencimento")) or date.today()
                    vencimento_editado = ed2.date_input(
                        "Data de vencimento:", value=vencimento_atual,
                        disabled=bloqueado_conciliacao, key=f"{tabela}_editar_vencimento_{id_baixa}",
                    )
                    conta_atual = registro.get("conta_bancaria") or ""
                    conta_editada = selecionar_conta(ed3, "Conta financeira:", contas_financeiras,
                        conta_atual, f"{tabela}_editar_conta_{id_baixa}", bloqueado_conciliacao)
                    ec1, ec2 = st.columns(2)
                    marcar_conciliado = ec1.checkbox(
                        "Marcar como conciliado e bloquear o lançamento",
                        value=bloqueado_conciliacao, disabled=bloqueado_conciliacao or not esta_baixado(registro),
                        key=f"{tabela}_editar_conciliado_{id_baixa}",
                    )
                    data_conciliacao_editada = ec2.date_input(
                        "Data da conciliação:",
                        value=parse_data_flex(registro.get("data_conciliacao")) or date.today(),
                        disabled=bloqueado_conciliacao or not marcar_conciliado,
                        key=f"{tabela}_editar_data_conciliacao_{id_baixa}",
                    )
                    if not esta_baixado(registro) and not bloqueado_conciliacao:
                        st.caption("Registre a baixa integral para habilitar a conciliação. Baixas parciais não encerram o lançamento.")
                    if st.button(
                        "Salvar dados do lançamento", type="primary", width="stretch",
                        disabled=bloqueado_conciliacao, key=f"{tabela}_salvar_dados_{id_baixa}",
                    ):
                        if marcar_conciliado and (not esta_baixado(registro) or not data_conciliacao_editada):
                            st.error("Conciliação exige lançamento baixado integralmente e data da conciliação.")
                            st.stop()
                        desconto_atual = float(registro.get("desconto") or 0)
                        juros_atual = float(registro.get("juros") or 0)
                        multa_atual = float(registro.get("multa") or 0)
                        valor_total_editado = max(
                            0.0, valor_original_editado - desconto_atual + juros_atual + multa_atual
                        )
                        usuario_edicao = st.session_state.get("username", "")
                        conn_edicao = conectar_banco()
                        cursor_edicao = conn_edicao.cursor()
                        cursor_edicao.execute(
                            f"""UPDATE {tabela} SET valor_original=?, valor_total=?, data_vencimento=?,
                                conta_bancaria=?, conciliado=?, data_conciliacao=?, conciliado_por=?,
                                alterado_por=?, alterado_em=?
                                WHERE id=?""",
                            (valor_original_editado, valor_total_editado, data_para_banco_br(vencimento_editado),
                             "" if conta_editada == "-- Sem conta financeira --" else conta_editada,
                             "Sim" if marcar_conciliado else "Não",
                             data_para_banco_br(data_conciliacao_editada) if marcar_conciliado else "",
                             usuario_edicao if marcar_conciliado else "", usuario_edicao, agora_br(), id_baixa),
                        )
                        conn_edicao.commit()
                        conn_edicao.close()
                        registrar_evento_sistema(
                            "update", tabela, id_baixa, registro.get(campo_parte) or "",
                            {"evento": "Dados financeiros alterados", "conciliado": marcar_conciliado,
                             "valor_original": valor_original_editado,
                             "data_vencimento": data_para_banco_br(vencimento_editado)},
                        )
                        st.success("Lançamento atualizado." if not marcar_conciliado else "Lançamento conciliado e bloqueado.")
                        st.rerun()
                if eh_pagar:
                    st.markdown("**Aprovação do pagamento**")
                    ap1, ap2 = st.columns(2)
                    status_aprovacao = ap1.selectbox("Status da aprovação:", ["Pendente", "Aprovado", "Reprovado"], index=["Pendente", "Aprovado", "Reprovado"].index(registro.get("status_aprovacao") or "Pendente"), disabled=bloqueado_conciliacao, key=f"{tabela}_aprovacao")
                    motivo_reprovacao = ap2.text_input("Motivo da reprovação:", value=registro.get("motivo_reprovacao") or "", disabled=bloqueado_conciliacao, key=f"{tabela}_motivo_reprovacao")
                    if st.button(
                        "Registrar aprovação", key=f"{tabela}_registrar_aprovacao",
                        disabled=bloqueado_conciliacao,
                    ):
                        conn_ap = conectar_banco()
                        cap = conn_ap.cursor()
                        cap.execute("""UPDATE contas_pagar SET status_aprovacao=?, motivo_reprovacao=?, aprovador=?,
                                      data_aprovacao=?, alterado_por=?, alterado_em=? WHERE id=?""",
                                   (status_aprovacao, motivo_reprovacao, st.session_state.get("username", ""),
                                    datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state.get("username", ""),
                                    datetime.now().strftime("%d/%m/%Y %H:%M"), id_baixa))
                        conn_ap.commit()
                        conn_ap.close()
                        st.success("Aprovação registrada.")
                        st.rerun()
                b1, b2, b3 = st.columns(3)
                data_baixa = b1.date_input("Data da baixa:", value=date.today(), disabled=bloqueado_conciliacao, key=f"{tabela}_data_baixa")
                valor_baixa = b2.number_input("Valor baixado R$:", min_value=0.0, value=float(registro.get("valor_total") or 0), step=0.01, format="%.2f", disabled=bloqueado_conciliacao, key=f"{tabela}_valor_baixa")
                novo_status = b3.selectbox("Novo status:", status_opcoes, index=status_opcoes.index(status_baixa), disabled=bloqueado_conciliacao, key=f"{tabela}_novo_status")
                bb1, bb2, bb3, bb4 = st.columns(4)
                conta_baixa = selecionar_conta(bb1, "Conta bancária / caixa / boleto da baixa:", contas_financeiras,
                    registro.get("conta_baixa") or registro.get("conta_bancaria") or "",
                    f"{tabela}_conta_baixa_{id_baixa}", bloqueado_conciliacao)
                forma_baixa = bb2.text_input("Forma da baixa:", value=registro.get("forma_baixa") or registro.get("forma_pagamento") or registro.get("forma_recebimento") or "", disabled=bloqueado_conciliacao, key=f"{tabela}_forma_baixa")
                taxas_baixa = bb3.number_input("Taxas R$:", min_value=0.0, value=float(registro.get("taxas_baixa") or 0), step=0.01, disabled=bloqueado_conciliacao, key=f"{tabela}_taxas_baixa")
                juros_baixa = bb4.number_input("Juros da baixa R$:", min_value=0.0, value=float(registro.get("juros_baixa") or 0), step=0.01, disabled=bloqueado_conciliacao, key=f"{tabela}_juros_baixa")
                bc1, bc2 = st.columns(2)
                desconto_baixa = bc1.number_input("Desconto da baixa R$:", min_value=0.0, value=float(registro.get("desconto_baixa") or 0), step=0.01, disabled=bloqueado_conciliacao, key=f"{tabela}_desconto_baixa")
                observacao_baixa = bc2.text_input("Observação da baixa:", value=registro.get("observacao_baixa") or "", disabled=bloqueado_conciliacao, key=f"{tabela}_obs_baixa")
                comprovante_baixa = st.file_uploader("Comprovante da baixa:", disabled=bloqueado_conciliacao, key=f"{tabela}_comprovante_baixa")
                if st.button(
                    "Registrar baixa/alteração", type="primary", key=f"{tabela}_baixar",
                    disabled=bloqueado_conciliacao,
                ):
                    if comprovante_baixa and not upload_dentro_limite(comprovante_baixa):
                        erro_upload_grande("comprovante")
                        st.stop()
                    comprovante_dados, comprovante_nome, comprovante_mime = dados_upload(comprovante_baixa)
                    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
                    usuario = st.session_state.get("username", "")
                    conn = conectar_banco()
                    c = conn.cursor()
                    campos_comp = ", comprovante_nome=?, comprovante_mime=?, comprovante=?" if comprovante_dados is not None else ""
                    params_baixa = [data_para_banco_br(data_baixa), valor_baixa, novo_status, usuario, usuario, agora,
                                    conta_baixa, forma_baixa, taxas_baixa, juros_baixa, desconto_baixa, observacao_baixa]
                    if comprovante_dados is not None:
                        params_baixa.extend([comprovante_nome, comprovante_mime, comprovante_dados])
                    params_baixa.append(id_baixa)
                    c.execute(f"""UPDATE {tabela} SET data_baixa=?, valor_baixado=?, status=?, baixado_por=?,
                                  alterado_por=?, alterado_em=?, conta_baixa=?, forma_baixa=?, taxas_baixa=?,
                                  juros_baixa=?, desconto_baixa=?, observacao_baixa=?{campos_comp} WHERE id=?""", tuple(params_baixa))
                    conn.commit()
                    conn.close()
                    registrar_evento_sistema("update", tabela, id_baixa, registro.get(campo_parte) or "", {"evento": "Baixa financeira", "status": novo_status, "valor": valor_baixa})
                    st.success("Baixa registrada.")
                    st.rerun()

                with st.expander("Cancelar lançamento", expanded=False):
                    motivo_cancelamento = st.text_area(
                        "Motivo do cancelamento:", disabled=bloqueado_conciliacao,
                        key=f"{tabela}_motivo_cancelar_{id_baixa}",
                    )
                    confirmar_cancelamento = st.checkbox(
                        "Confirmo o cancelamento deste lançamento.",
                        disabled=bloqueado_conciliacao,
                        key=f"{tabela}_confirmar_cancelar_{id_baixa}",
                    )
                    if st.button(
                        "Cancelar lançamento", width="stretch",
                        disabled=(bloqueado_conciliacao or not confirmar_cancelamento),
                        key=f"{tabela}_cancelar_lancamento_{id_baixa}",
                    ):
                        if not motivo_cancelamento.strip():
                            st.error("Informe o motivo do cancelamento.")
                        else:
                            usuario_cancelamento = st.session_state.get("username", "")
                            conn_cancelamento = conectar_banco()
                            cursor_cancelamento = conn_cancelamento.cursor()
                            cursor_cancelamento.execute(
                                f"""UPDATE {tabela} SET status='Cancelado', cancelado_por=?,
                                    motivo_cancelamento=?, alterado_por=?, alterado_em=?
                                    WHERE id=? AND COALESCE(conciliado, 'Não') <> 'Sim'""",
                                (usuario_cancelamento, motivo_cancelamento.strip(), usuario_cancelamento,
                                 agora_br(), id_baixa),
                            )
                            conn_cancelamento.commit()
                            conn_cancelamento.close()
                            registrar_evento_sistema(
                                "update", tabela, id_baixa, registro.get(campo_parte) or "",
                                {"evento": "Cancelamento financeiro", "motivo": motivo_cancelamento.strip()},
                            )
                            st.success("Lançamento cancelado.")
                            st.rerun()

        if registros and tem_permissao(f"{permissao}.delete"):
            with st.expander("Excluir lançamento"):
                id_excluir = st.number_input("ID para excluir:", min_value=1, step=1, key=f"{tabela}_id_excluir")
                registro_excluir = next(
                    (r for r in registros if int(r.get("id") or 0) == int(id_excluir)),
                    None,
                )
                if registro_excluir:
                    st.warning(
                        f"Você está prestes a excluir o lançamento #{id_excluir} de "
                        f"{registro_excluir.get(campo_parte) or 'cadastro não informado'}, no valor de "
                        f"{formatar_moeda_br(registro_excluir.get('valor_total'))}."
                    )
                    if lancamento_esta_conciliado(registro_excluir):
                        st.error("Este lançamento está conciliado e não pode ser excluído.")
                confirmar_exclusao = st.checkbox(
                    "Confirmo que desejo excluir permanentemente este lançamento.",
                    key=f"{tabela}_confirmar_exclusao_{id_excluir}",
                )
                if st.button(
                    "Excluir permanentemente",
                    key=f"{tabela}_excluir",
                    disabled=(not confirmar_exclusao or not registro_excluir
                              or lancamento_esta_conciliado(registro_excluir)),
                ):
                    deletar_registro(tabela, "id", id_excluir)
                    st.success("Lançamento excluído.")
                    st.rerun()

    with aba_rec:
        st.subheader("Lançamentos Recorrentes")
        with st.form(f"form_recorrencia_{tipo}", clear_on_submit=True):
            rr1, rr2, rr3 = st.columns(3)
            rec_parte = rr1.text_input(f"{parte_label}:")
            rec_documento = rr2.text_input("CPF/CNPJ:")
            rec_descricao = rr3.text_input("Descrição:")
            rr4, rr5, rr6 = st.columns(3)
            rec_valor = rr4.number_input("Valor R$:", min_value=0.0, step=0.01, format="%.2f")
            rec_frequencia = rr5.selectbox("Frequência:", ["Mensal", "Semanal", "Anual"])
            rec_dia = rr6.number_input("Dia de vencimento:", min_value=1, max_value=31, value=10)
            rr7, rr8, rr9 = st.columns(3)
            rec_inicio = rr7.date_input("Data inicial:", value=date.today())
            rec_final = rr8.date_input("Data final:", value=None)
            rec_auto = rr9.selectbox("Gerar automaticamente:", ["Sim", "Não"])
            rr10, rr11 = st.columns(2)
            rec_centro = rr10.text_input("Centro de custo/receita:")
            rec_categoria = rr11.text_input("Categoria:")
            if st.form_submit_button("Salvar recorrência", type="primary", width="stretch"):
                if not rec_parte or not rec_descricao or rec_valor <= 0:
                    st.error(f"Informe {parte_label.lower()}, descrição e valor.")
                else:
                    conn_rec = conectar_banco()
                    crec = conn_rec.cursor()
                    crec.execute("""INSERT INTO financeiro_recorrencias_v2
                                   (tipo, parte, cpf_cnpj, descricao, valor, frequencia, dia_vencimento,
                                    data_inicial, data_final, centro, categoria, gerar_automaticamente,
                                    ativo, criado_por, criado_em)
                                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                 (tipo, rec_parte, rec_documento, rec_descricao, rec_valor, rec_frequencia, rec_dia,
                                  data_para_banco_br(rec_inicio), data_para_banco_br(rec_final), rec_centro, rec_categoria,
                                  rec_auto, "Sim", st.session_state.get("username", ""), datetime.now().strftime("%d/%m/%Y %H:%M")))
                    conn_rec.commit()
                    conn_rec.close()
                    st.success("Recorrência salva.")
                    st.rerun()
        recorrencias = repo_listar_recorrencias(conectar_banco, tipo)
        if recorrencias:
            st.dataframe(recorrencias, width="stretch", hide_index=True)
            id_gerar_rec = st.number_input("ID da recorrência para gerar lançamento:", min_value=1, step=1, key=f"gerar_rec_{tipo}")
            rec_gerar = next((r for r in recorrencias if int(r.get("id") or 0) == int(id_gerar_rec)), None)
            if rec_gerar and st.button("Gerar lançamento desta recorrência", type="primary", key=f"btn_gerar_rec_{tipo}"):
                venc_rec = date.today().replace(day=min(int(rec_gerar.get("dia_vencimento") or 1), 28))
                usuario_rec = st.session_state.get("username", "")
                agora_rec = datetime.now().strftime("%d/%m/%Y %H:%M")
                conn_gr = conectar_banco()
                cgr = conn_gr.cursor()
                if eh_pagar:
                    cgr.execute("""INSERT INTO contas_pagar
                                   (fornecedor, cpf_cnpj, numero_documento, tipo_documento, categoria, centro_custo,
                                    data_emissao, data_competencia, data_vencimento, valor_original, valor_total,
                                    status, observacoes, criado_por, criado_em, solicitante, status_aprovacao)
                                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                (rec_gerar.get("parte"), rec_gerar.get("cpf_cnpj"), f"REC-{rec_gerar.get('id')}",
                                 "Recorrência", rec_gerar.get("categoria"), rec_gerar.get("centro"),
                                 data_para_banco_br(date.today()), data_para_banco_br(date.today()),
                                 data_para_banco_br(venc_rec), rec_gerar.get("valor"), rec_gerar.get("valor"),
                                 "Aberto", rec_gerar.get("descricao"), usuario_rec, agora_rec, usuario_rec, "Pendente"))
                else:
                    cgr.execute("""INSERT INTO contas_receber
                                   (cliente, cpf_cnpj, numero_documento, tipo_receita, categoria, centro_receita,
                                    data_emissao, data_competencia, data_vencimento, valor_original, valor_total,
                                    status, observacoes, criado_por, criado_em)
                                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                (rec_gerar.get("parte"), rec_gerar.get("cpf_cnpj"), f"REC-{rec_gerar.get('id')}",
                                 "Recorrência", rec_gerar.get("categoria"), rec_gerar.get("centro"),
                                 data_para_banco_br(date.today()), data_para_banco_br(date.today()),
                                 data_para_banco_br(venc_rec), rec_gerar.get("valor"), rec_gerar.get("valor"),
                                 "Aberto", rec_gerar.get("descricao"), usuario_rec, agora_rec))
                cgr.execute("UPDATE financeiro_recorrencias_v2 SET ultima_geracao=? WHERE id=?", (data_para_banco_br(date.today()), id_gerar_rec))
                conn_gr.commit()
                conn_gr.close()
                st.success("Lançamento recorrente gerado.")
                st.rerun()

    if aba_cobranca is not None:
        with aba_cobranca:
            st.subheader("Cobrança e Renegociação")
            conn_cob = conectar_banco()
            ccob = conn_cob.cursor()
            ccob.execute("SELECT * FROM contas_receber ORDER BY id DESC")
            contas_cob = [dict(r) for r in ccob.fetchall()]
            conn_cob.close()
            vencidas_cob = [r for r in contas_cob if parse_data_flex(r.get("data_vencimento")) and parse_data_flex(r.get("data_vencimento")) < date.today() and r.get("status") not in ("Recebido", "Cancelado", "Baixado por perda") and not lancamento_esta_conciliado(r)]
            if vencidas_cob:
                st.dataframe([{"ID": r.get("id"), "Cliente": r.get("cliente"), "Vencimento": r.get("data_vencimento"), "Dias em atraso": (date.today() - parse_data_flex(r.get("data_vencimento"))).days, "Valor": formatar_moeda_br(r.get("valor_total")), "Status": r.get("status")} for r in vencidas_cob], width="stretch", hide_index=True)
                id_cob = st.number_input("ID do título para registrar cobrança:", min_value=1, step=1, key="fin_id_cobranca")
                titulo_cob = next((r for r in vencidas_cob if int(r.get("id") or 0) == id_cob), None)
                if titulo_cob:
                    cob1, cob2, cob3 = st.columns(3)
                    status_cob = cob1.selectbox("Status da cobrança:", ["Pendente", "Em contato", "Negociado", "Protestado", "Pago"])
                    proxima_cob = cob2.date_input("Próxima ação:", value=date.today())
                    valor_cob = cob3.number_input("Valor atualizado R$:", min_value=0.0, value=float(titulo_cob.get("valor_total") or 0), step=0.01)
                    historico_cob = st.text_area("Histórico/observações da cobrança:")
                    if st.button("Registrar cobrança", type="primary"):
                        conn_ic = conectar_banco()
                        cic = conn_ic.cursor()
                        cic.execute("""INSERT INTO financeiro_cobrancas_v2
                                      (conta_receber_id, cliente, dias_atraso, valor_atualizado, historico,
                                       status, proxima_acao, responsavel, observacoes, criado_em, alterado_em)
                                      VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                                    (id_cob, titulo_cob.get("cliente"), (date.today() - parse_data_flex(titulo_cob.get("data_vencimento"))).days,
                                     valor_cob, historico_cob, status_cob, data_para_banco_br(proxima_cob),
                                     st.session_state.get("username", ""), historico_cob,
                                     datetime.now().strftime("%d/%m/%Y %H:%M"), datetime.now().strftime("%d/%m/%Y %H:%M")))
                        cic.execute("UPDATE contas_receber SET status='Em cobrança' WHERE id=?", (id_cob,))
                        conn_ic.commit()
                        conn_ic.close()
                        st.success("Cobrança registrada.")
                        st.rerun()
            else:
                st.info("Nenhum título vencido para cobrança.")

            with st.expander("Registrar renegociação", expanded=False):
                ren1, ren2, ren3 = st.columns(3)
                ren_titulo_id = ren1.number_input("ID do título original:", min_value=1, step=1, key="ren_titulo_id")
                ren_titulo = next((r for r in contas_cob if int(r.get("id") or 0) == int(ren_titulo_id)), None)
                ren_bloqueado = lancamento_esta_conciliado(ren_titulo)
                if ren_bloqueado:
                    st.warning("Este lançamento está conciliado e não pode ser renegociado.")
                ren_valor_original = float(ren_titulo.get("valor_total") or 0) if ren_titulo else 0.0
                ren_valor = ren2.number_input("Valor renegociado R$:", min_value=0.0, value=ren_valor_original, step=0.01, disabled=ren_bloqueado, key="ren_valor")
                ren_entrada = ren3.number_input("Entrada R$:", min_value=0.0, step=0.01, disabled=ren_bloqueado, key="ren_entrada")
                ren4, ren5, ren6 = st.columns(3)
                ren_parcelas = ren4.number_input("Parcelas:", min_value=1, value=1, step=1, key="ren_parcelas")
                ren_primeiro_venc = ren5.date_input("Primeiro vencimento:", value=date.today(), key="ren_primeiro_venc")
                ren_status = ren6.selectbox("Status:", ["Ativo", "Quitado", "Cancelado"], key="ren_status")
                ren_obs = st.text_area("Observações da negociação:", key="ren_obs")
                if st.button("Salvar renegociação", type="primary", disabled=ren_bloqueado, key="salvar_renegociacao"):
                    if not ren_titulo or ren_valor <= 0:
                        st.error("Informe um título válido e o novo valor.")
                    else:
                        conn_ren = conectar_banco()
                        cren = conn_ren.cursor()
                        cren.execute("""INSERT INTO financeiro_renegociacoes_v2
                                       (tipo, parte, titulos_originais, valor_original, valor_renegociado, entrada,
                                        parcelas, primeiro_vencimento, status, observacoes, criado_por, criado_em)
                                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                                     ("receber", ren_titulo.get("cliente"), str(ren_titulo_id), ren_valor_original,
                                      ren_valor, ren_entrada, ren_parcelas, data_para_banco_br(ren_primeiro_venc),
                                      ren_status, ren_obs, st.session_state.get("username", ""), datetime.now().strftime("%d/%m/%Y %H:%M")))
                        cren.execute("UPDATE contas_receber SET status='Renegociado', alterado_por=?, alterado_em=? WHERE id=?",
                                     (st.session_state.get("username", ""), datetime.now().strftime("%d/%m/%Y %H:%M"), ren_titulo_id))
                        conn_ren.commit()
                        conn_ren.close()
                        st.success("Renegociação registrada.")
                        st.rerun()

def renderizar_cadastros_financeiros(ctx):
    aplicar_contexto_pagina(ctx, globals())
    if not tem_permissao("financeiro.cadastros"):
        st.error("Você não tem permissão para acessar estes cadastros.")
        return
    st.title("Cadastros Financeiros")
    tipos = [
        "Conta bancária", "Caixa físico", "Boleto", "Cartão de crédito",
        "Centro de custo", "Categoria financeira", "Plano de contas", "Imposto",
    ]
    gerencial = usuario_eh_gerencial(st.session_state)
    if not gerencial:
        tipos = [tipo for tipo in tipos if tipo not in TIPOS_CONTA_EMPRESA]
        st.caption("O cadastro bancário da empresa é exclusivo do acesso gerencial.")
    st.caption(
        "Cadastre aqui bancos, caixas físicos, boletos e cartões. Somente cadastros ativos aparecem nos lançamentos."
    )
    with st.form("form_cadastro_financeiro", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        tipo = c1.selectbox("Tipo:", tipos)
        nome = c2.text_input("Nome:")
        codigo = c3.text_input("Código:")
        observacoes = st.text_area("Observações:", height=80)
        dados_bancarios = campos_bancarios({}, "fin_banco_novo") if gerencial else {}
        ativo = st.selectbox("Ativo:", ["Sim", "Não"])
        if st.form_submit_button("Salvar cadastro", type="primary", width="stretch"):
            if not nome.strip():
                st.error("Informe o nome.")
            else:
                conn = conectar_banco()
                c = conn.cursor()
                c.execute("""INSERT INTO financeiro_cadastros_aux
                           (tipo, nome, codigo, ativo, observacoes, criado_por, criado_em)
                           VALUES (?,?,?,?,?,?,?)""",
                          (tipo, nome.strip(), codigo.strip(), ativo, observacoes,
                           st.session_state.get("username", ""), agora_br()))
                if gerencial and tipo in TIPOS_CONTA_EMPRESA:
                    cadastro_id = c.lastrowid
                    c.execute("UPDATE financeiro_cadastros_aux SET banco=?, agencia=?, numero_conta=?, titular=?, documento_titular=?, chave_pix=? WHERE id=?",
                        tuple(dados_bancarios.values()) + (cadastro_id,))
                conn.commit()
                conn.close()
                st.success("Cadastro financeiro salvo.")
                st.rerun()

    conn = conectar_banco()
    c = conn.cursor()
    c.execute("SELECT * FROM financeiro_cadastros_aux ORDER BY tipo, nome")
    registros = [dict(r) for r in c.fetchall()]
    if not gerencial:
        registros = [{k: v for k, v in r.items() if k not in CAMPOS_BANCARIOS}
                     for r in registros if r.get("tipo") not in TIPOS_CONTA_EMPRESA]
    conn.close()
    if registros:
        pesquisa_aux = st.text_input(
            "Pesquisar cadastro financeiro:",
            placeholder="Nome, tipo, código ou observação",
            key="fin_aux_pesquisa",
        ).strip().casefold()
        registros_filtrados_aux = [
            registro for registro in registros
            if not pesquisa_aux or pesquisa_aux in " ".join(str(valor or "") for valor in registro.values()).casefold()
        ]
        id_aux_clicado = tabela_clicavel_id(
            st, registros_filtrados_aux, "fin_aux_grade", campo_id="id"
        ) if registros_filtrados_aux else None
        if id_aux_clicado:
            st.session_state["fin_aux_id_ativo"] = int(id_aux_clicado)
        if gerencial or tem_permissao("financeiro.cadastros.edit"):
            id_aux = int(st.session_state.get("fin_aux_id_ativo") or 0)
            if not id_aux:
                st.caption("Clique em qualquer informação do cadastro para editar.")
            else:
              with st.expander("Editar / excluir cadastro", expanded=True):
                registro = next((r for r in registros if int(r.get("id") or 0) == int(id_aux)), None)
                if registro:
                    e1, e2, e3 = st.columns(3)
                    tipo_e = e1.selectbox("Tipo:", tipos, index=tipos.index(registro.get("tipo")) if registro.get("tipo") in tipos else 0, key=f"fin_aux_tipo_e_{id_aux}")
                    nome_e = e2.text_input("Nome:", value=registro.get("nome") or "", key=f"fin_aux_nome_e_{id_aux}")
                    codigo_e = e3.text_input("Código:", value=registro.get("codigo") or "", key=f"fin_aux_codigo_e_{id_aux}")
                    ativo_e = st.selectbox("Ativo:", ["Sim", "Não"], index=0 if registro.get("ativo") != "Não" else 1, key=f"fin_aux_ativo_e_{id_aux}")
                    obs_e = st.text_area("Observações:", value=registro.get("observacoes") or "", key=f"fin_aux_obs_e_{id_aux}")
                    dados_bancarios_e = campos_bancarios(registro, f"fin_banco_{id_aux}") if gerencial else {}
                    a1, a2 = st.columns(2)
                    if a1.button("Salvar alteração", type="primary", width="stretch", key=f"fin_aux_salvar_e_{id_aux}"):
                        conn_e = conectar_banco()
                        ce = conn_e.cursor()
                        ce.execute("""UPDATE financeiro_cadastros_aux SET tipo=?, nome=?, codigo=?, ativo=?,
                                    observacoes=?, alterado_por=?, alterado_em=? WHERE id=?""",
                                   (tipo_e, nome_e, codigo_e, ativo_e, obs_e,
                                    st.session_state.get("username", ""), agora_br(), id_aux))
                        if gerencial:
                            ce.execute("UPDATE financeiro_cadastros_aux SET banco=?, agencia=?, numero_conta=?, titular=?, documento_titular=?, chave_pix=? WHERE id=?",
                                tuple(dados_bancarios_e.values()) + (id_aux,))
                        conn_e.commit()
                        conn_e.close()
                        st.success("Cadastro alterado.")
                        st.rerun()
                    if a2.button("Excluir cadastro", width="stretch", key=f"fin_aux_excluir_e_{id_aux}"):
                        deletar_registro("financeiro_cadastros_aux", "id", id_aux)
                        st.success("Cadastro excluído.")
                        st.rerun()
    else:
        st.info("Nenhum cadastro financeiro registrado ainda.")

def renderizar_lancamentos_financeiros(ctx):
    aplicar_contexto_pagina(ctx, globals())
    if not tem_permissao("financeiro.lancamentos"):
        st.error("Você não tem permissão para acessar os lançamentos financeiros.")
        return
    st.title("Lançamentos Financeiros")
    f1, f2, f3, f4 = st.columns(4)
    tipo_filtro = f1.selectbox("Tipo:", ["Todos", "Pagar", "Receber"])
    data_ini = f2.date_input("Emissão inicial:", value=date.today() - timedelta(days=30), key="lan_fin_ini")
    data_fim = f3.date_input("Emissão final:", value=date.today(), key="lan_fin_fim")
    busca = f4.text_input("Cliente/fornecedor/documento:")
    f5, f6, f7, f8 = st.columns(4)
    filtro_tipo_doc = f5.text_input("Tipo documento/receita:")
    filtro_centro = f6.text_input("Centro custo/receita:")
    filtro_categoria = f7.text_input("Categoria:")
    filtro_venc = f8.date_input("Vencimento até:", value=None, key="lan_fin_venc")

    conn = conectar_banco()
    c = conn.cursor()
    c.execute("SELECT *, 'Pagar' AS origem FROM contas_pagar")
    pagar = [dict(r) for r in c.fetchall()]
    c.execute("SELECT *, 'Receber' AS origem FROM contas_receber")
    receber = [dict(r) for r in c.fetchall()]
    conn.close()
    registros = pagar + receber
    if tipo_filtro != "Todos":
        registros = [r for r in registros if r.get("origem") == tipo_filtro]
    registros_filtrados = []
    for r in registros:
        emissao = parse_data_flex(r.get("data_emissao"))
        if emissao and (emissao < data_ini or emissao > data_fim):
            continue
        if filtro_venc and parse_data_flex(r.get("data_vencimento")) and parse_data_flex(r.get("data_vencimento")) > filtro_venc:
            continue
        texto = " ".join(str(r.get(campo) or "") for campo in [
            "fornecedor", "cliente", "numero_documento", "tipo_documento", "tipo_receita",
            "centro_custo", "centro_receita", "categoria", "plano_contas"
        ]).lower()
        if busca.strip() and busca.strip().lower() not in texto:
            continue
        if filtro_tipo_doc.strip() and filtro_tipo_doc.strip().lower() not in f"{r.get('tipo_documento','')} {r.get('tipo_receita','')}".lower():
            continue
        if filtro_centro.strip() and filtro_centro.strip().lower() not in f"{r.get('centro_custo','')} {r.get('centro_receita','')}".lower():
            continue
        if filtro_categoria.strip() and filtro_categoria.strip().lower() not in str(r.get("categoria") or "").lower():
            continue
        registros_filtrados.append(r)

    st.markdown("### Comparativo: contas a pagar × contas a receber")
    comparativo = montar_comparativo_pagar_receber(registros_filtrados, parse_data_flex)
    total_pagar = sum(float(item["A pagar"]) for item in comparativo)
    total_receber = sum(float(item["A receber"]) for item in comparativo)
    comp1, comp2, comp3 = st.columns(3)
    comp1.metric("Total a pagar", formatar_moeda_br(total_pagar))
    comp2.metric("Total a receber", formatar_moeda_br(total_receber))
    comp3.metric("Saldo previsto", formatar_moeda_br(total_receber - total_pagar))
    if comparativo:
        dados_grafico = pd.DataFrame(comparativo).set_index("Período")
        st.bar_chart(dados_grafico[["A pagar", "A receber"]], width="stretch")
        st.caption("Comparação mensal pelo vencimento, respeitando os filtros acima e desconsiderando lançamentos cancelados.")
    else:
        st.info("Não há lançamentos no período selecionado para montar o gráfico.")

    tabela = []
    for r in sorted(registros_filtrados, key=lambda x: (parse_data_flex(x.get("data_vencimento")) or date.max, int(x.get("id") or 0))):
        parte = r.get("fornecedor") if r.get("origem") == "Pagar" else r.get("cliente")
        tabela.append({
            "Origem": r.get("origem"), "ID": r.get("id"), "Cliente/Fornecedor": parte,
            "Documento": r.get("numero_documento"), "Tipo": r.get("tipo_documento") or r.get("tipo_receita"),
            "Centro": r.get("centro_custo") or r.get("centro_receita"), "Categoria": r.get("categoria"),
            "Emissão": data_para_br(r.get("data_emissao")), "Vencimento": data_para_br(r.get("data_vencimento")),
            "Valor": formatar_moeda_br(r.get("valor_total")), "Baixado": formatar_moeda_br(r.get("valor_baixado")),
            "Status": r.get("status"), "Conciliado": r.get("conciliado") or "Não",
        })
    if tabela:
        lancamento_clicado = tabela_clicavel_registro(st, tabela, "lancamentos_financeiros_grade")
        if lancamento_clicado:
            origem_clicada = lancamento_clicado.get("Origem")
            tabela_destino = "contas_pagar" if origem_clicada == "Pagar" else "contas_receber"
            st.session_state[f"financeiro_historico_selecionado_{tabela_destino}"] = int(
                lancamento_clicado.get("ID") or 0
            )
            st.session_state[f"{tabela_destino}_aba_destino"] = "Histórico e baixa"
            st.session_state["pagina_atual"] = "Contas a Pagar" if origem_clicada == "Pagar" else "Contas a Receber"
            st.rerun()
        st.caption(
            "Tela somente para consulta. Clique em uma linha para abrir o lançamento em Contas a Pagar ou Contas a Receber."
        )
        st.download_button("Exportar lançamentos", data=gerar_excel_tabela(tabela, "Lançamentos Financeiros"), file_name="lancamentos_financeiros.xls", mime="application/vnd.ms-excel", width="stretch")
    else:
        st.info("Nenhum lançamento encontrado.")
