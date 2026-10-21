"""Download compartilhado, com tamanho físico único para entrada e Kanban."""
from dsystem_erp.services.recepcao_kanban import gerar_etiqueta_equipamento, validar_url_etiqueta, configuracao_etiqueta_os


def renderizar_etiquetas_os(st, equipamentos, config_get, base_url, prefixo):
    try:
        url = validar_url_etiqueta(config_get("APP_BASE_URL", base_url))
        config = configuracao_etiqueta_os(config_get)
        largura, altura = config["largura_mm"], config["altura_mm"]
    except (ValueError, TypeError) as exc:
        st.warning(f"Antes de imprimir o QR dinâmico: {exc}")
        return
    if config["perfil"] == "elgin_i8":
        st.info("Elgin i8 — bobina térmica de 80 mm. PDF de 80 × 60 mm por aparelho, com margens laterais de 4 mm.")
        st.caption("No computador conectado à impressora, abra o PDF, selecione Elgin i8 e papel 80 × 60 mm, tamanho real / 100%, sem ajustar à página. O corte é configurado no driver, não pelo PDF.")
        st.warning("A i8 é uma impressora de cupons. Use bobina térmica padrão; não coloque etiquetas adesivas sem confirmação de compatibilidade pela Elgin.")
    else:
        st.caption(
            f"Etiqueta {largura:g} × {altura:g} mm, uma por página. Imprima na etiquetadora em tamanho real / 100%, "
            "sem ajustar à página, com papel do mesmo tamanho. Configure as medidas em Configurações do Sistema > Empresa."
        )
    st.caption("O QR abre a ficha atualizada e exige login com acesso à Recepção. O celular precisa acessar a URL do sistema. O texto já impresso não muda.")
    for item in equipamentos:
        st.download_button(
            f"Baixar {'cupom Elgin i8' if config['perfil'] == 'elgin_i8' else 'etiqueta'} {item.get('numero_item')} para impressão",
            data=gerar_etiqueta_equipamento(item, url, largura, altura, config["margem_mm"]),
            file_name=f"etiqueta_{item.get('numero_item')}.pdf", mime="application/pdf",
            key=f"{prefixo}_{item.get('id')}",
        )
