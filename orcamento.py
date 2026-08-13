import streamlit as st
import streamlit.components.v1 as components
import mysql.connector
import base64
import io
import os
import json
import pandas as pd
import textwrap
import re
import html
import unicodedata
import xml.etree.ElementTree as ET
import uuid
import hashlib
import secrets as py_secrets
import hmac
import struct
import math
import wave
import time
import smtplib
from email.message import EmailMessage
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from openpyxl import load_workbook
from dsystem_erp.app_context import criar_app_context
from dsystem_erp.config import config_val
from dsystem_erp.db import mysql_connection_config
from dsystem_erp.migrations import aplicar_migrations_pendentes, garantir_tabela_migrations, registrar_migration
try:
    from dsystem_erp.migrations import garantir_coluna
except ImportError:
    def garantir_coluna(cursor, tabela, coluna, definicao):
        tabela_segura = "".join(ch for ch in tabela if ch.isalnum() or ch == "_")
        coluna_segura = "".join(ch for ch in coluna if ch.isalnum() or ch == "_")
        if not tabela_segura or not coluna_segura:
            raise ValueError("Nome de tabela ou coluna invalido.")
        cursor.execute(f"SHOW COLUMNS FROM `{tabela_segura}` LIKE %s", (coluna_segura,))
        if cursor.fetchone() is not None:
            return False
        try:
            cursor.execute(f"ALTER TABLE `{tabela_segura}` ADD COLUMN `{coluna_segura}` {definicao}")
            return True
        except Exception as ex:
            if getattr(ex, "errno", None) == 1060:
                return False
            raise
from dsystem_erp.services.whatsapp import criar_url_whatsapp, normalizar_telefone_whatsapp
from dsystem_erp.services.nfse import analisar_retorno_nfse, chamar_webservice_nfse, consultar_protocolo_nfse, executar_fluxo_emissao_nfse, validar_nfse, validar_xml_nfse_basico
from dsystem_erp.services.portal_cliente import normalizar_secao_portal, portal_card_html, portal_mini_grid_html
try:
    from dsystem_erp.services.settings import endpoint_nfse_nacional_rest, normalizar_whatsapp_config, validar_nfse_config
except ImportError:
    from dsystem_erp.services.settings import normalizar_whatsapp_config, validar_nfse_config

    def endpoint_nfse_nacional_rest(valor: str | None) -> bool:
        endpoint = str(valor or "").strip().lower().rstrip("/")
        return (
            ("adn." in endpoint and "nfse.gov.br" in endpoint)
            or ("sefin." in endpoint and "nfse.gov.br" in endpoint)
            or "/contribuintes" in endpoint
            or "/sefinnacional" in endpoint
        )
from dsystem_erp.services.audit import (
    cliente_do_log,
    extrair_colunas_insert,
    extrair_colunas_update,
    extrair_tabela_sql,
    extrair_where_id,
    limpar_registro_log,
    montar_registro_params,
)
from dsystem_erp.services.documentos import gerar_excel_tabela as service_gerar_excel_tabela
from dsystem_erp.services.documentos import gerar_pdf_tabela_simples as service_gerar_pdf_tabela_simples
from dsystem_erp.services.nfse_xml import formatar_decimal_xml as service_formatar_decimal_xml
from dsystem_erp.services.nfse_xml import gerar_xml_nfse_bh_rps as service_gerar_xml_nfse_bh_rps
from dsystem_erp.services.nfse_xml import xml_texto as service_xml_texto
from dsystem_erp.services.nfse_pdf import gerar_pdf_nota_autorizada_simples as service_gerar_pdf_nota_autorizada_simples
from dsystem_erp.services.nfse_signature import assinar_xml_nfse_bh as service_assinar_xml_nfse_bh
from dsystem_erp.services.security import mascarar_segredo as service_mascarar_segredo
from dsystem_erp.services.streamlit_static import configurar_limite_arquivos_estaticos
from dsystem_erp.services.alertas_atendimento import agendamentos_proximos, chamado_esta_aberto, ids_novos
from dsystem_erp.services.orcamentos import aplicar_encargos_renegociacao, data_validade_orcamento, numero_renegociacao, orcamento_esta_vencido, total_geral_orcamento, total_item_orcamento
from dsystem_erp.services.contas_receber import IMPOSTOS_PADRAO, calcular_impostos, calcular_margem_lucro, gerar_parcelas
from dsystem_erp.services.precificacao_estoque import decimal_valor
from dsystem_erp.services.cobrancas_recorrentes import sincronizar_lancamentos_recorrentes
from dsystem_erp.ui import injetar_css_base
from dsystem_erp.ui_consulta import tabela_selecionavel_id
try:
    from dsystem_erp.ui import configurar_campos_data_br
except ImportError:
    # Compatibilidade com processos Streamlit que mantiveram dsystem_erp.ui em cache.
    def configurar_campos_data_br(st_module):
        if getattr(st_module, "_dsystem_data_br_configurada", False):
            return
        date_input_original = st_module.date_input

        def date_input_br(*args, **kwargs):
            kwargs.setdefault("format", "DD/MM/YYYY")
            return date_input_original(*args, **kwargs)

        st_module.date_input = date_input_br
        try:
            from streamlit.delta_generator import DeltaGenerator
            delta_original = DeltaGenerator.date_input
            if not getattr(delta_original, "_dsystem_data_br", False):
                def delta_date_input_br(self, *args, **kwargs):
                    kwargs.setdefault("format", "DD/MM/YYYY")
                    return delta_original(self, *args, **kwargs)
                delta_date_input_br._dsystem_data_br = True
                DeltaGenerator.date_input = delta_date_input_br
        except Exception:
            pass
        st_module._dsystem_data_br_configurada = True
from dsystem_erp.services.clientes import dados_cliente_padrao, montar_endereco_cliente
from dsystem_erp.services.faturamento import itens_faturamento_lista, resumo_itens_faturamento
from dsystem_erp.pages.system_tools import renderizar_backups_sistema as page_renderizar_backups_sistema
from dsystem_erp.pages.system_tools import renderizar_diagnostico_sistema as page_renderizar_diagnostico_sistema
from dsystem_erp.pages.gerador_orcamentos import renderizar_gerador_orcamentos as page_renderizar_gerador_orcamentos
from dsystem_erp.pages.clientes import renderizar_cadastro_cliente_fornecedor as page_renderizar_cadastro_cliente_fornecedor
from dsystem_erp.pages.infraestrutura import renderizar_infraestrutura_ti as page_renderizar_infraestrutura_ti
from dsystem_erp.pages.faturamento import renderizar_a_faturar as page_renderizar_a_faturar
from dsystem_erp.pages.faturamento import renderizar_faturado as page_renderizar_faturado
from dsystem_erp.pages.atendimentos import renderizar_atendimentos_checklists as page_renderizar_atendimentos_checklists
from dsystem_erp.pages.cobrancas import renderizar_cobrancas as page_renderizar_cobrancas
from dsystem_erp.pages.ordens_servico import renderizar_ordem_servico as page_renderizar_ordem_servico
from dsystem_erp.pages.usuarios import renderizar_gerenciador_usuarios as page_renderizar_gerenciador_usuarios
from dsystem_erp.pages.portal_cliente import renderizar_portal_cliente_page as page_renderizar_portal_cliente
from dsystem_erp.pages.acesso_softwares import renderizar_acesso_softwares as page_renderizar_acesso_softwares
from dsystem_erp.pages.estoque import renderizar_estoque as page_renderizar_estoque
from dsystem_erp.pages.compras import renderizar_compras as page_renderizar_compras
from dsystem_erp.pages.contratos import renderizar_contratos as page_renderizar_contratos
from dsystem_erp.pages.recepcao_kanban import renderizar_recepcao_kanban as page_renderizar_recepcao_kanban
from dsystem_erp.services.contratos import salvar_contrato_gerado
from dsystem_erp.pages.emails import renderizar_gestao_emails as page_renderizar_gestao_emails
from dsystem_erp.technical_logs import registrar_log_tecnico
from dsystem_erp.utils.datas import data_extenso_br, data_input_valor, data_para_banco_br, data_para_br, data_para_iso, parse_data_flex
from dsystem_erp.utils.formatadores import formatar_moeda_br, tamanho_arquivo_legivel

NFSE_ENDPOINT_TESTE_NACIONAL = "https://bhisshomologaws.pbh.gov.br/bhiss-ws/nfse"
from dsystem_erp.repositories.clientes import buscar_cliente_por_nome as repo_buscar_cliente_por_nome
from dsystem_erp.repositories.clientes import listar_clientes as repo_listar_clientes
from dsystem_erp.repositories.faturamento import (
    listar_faturados_para_nf as repo_listar_faturados_para_nf,
    listar_faturamentos as repo_listar_faturamentos,
    listar_faturamentos_para_nf as repo_listar_faturamentos_para_nf,
)
from dsystem_erp.repositories.estoque import (
    listar_alertas_estoque_minimo as repo_listar_alertas_estoque_minimo,
    listar_estoque as repo_listar_estoque,
)
from dsystem_erp.repositories.financeiro import listar_recorrencias as repo_listar_recorrencias
from modules.registry import PAGINA_ESTOQUE, PAGINA_FATURAMENTO, PAGINA_INFRAESTRUTURA

st.set_page_config(page_title="Sistema Dsystem ERP", layout="wide", initial_sidebar_state="expanded")
configurar_campos_data_br(st)
injetar_css_base(st)

DB_BACKEND = "mysql"

FUSO_SAO_PAULO = ZoneInfo("America/Sao_Paulo")

def agora_sao_paulo():
    return datetime.now(FUSO_SAO_PAULO)

def agora_br(fmt="%d/%m/%Y %H:%M"):
    return agora_sao_paulo().strftime(fmt)

DB_NAME = config_val("MYSQL_DATABASE", "banco_dsystem")
APP_BASE_URL = (config_val("APP_BASE_URL", "") or "").rstrip("/")
WHATSAPP_OFICIAL = re.sub(r"\D", "", config_val("WHATSAPP_OFICIAL", "31935023241") or "")
WHATSAPP_API_NUMERO = re.sub(r"\D", "", config_val("WHATSAPP_API_NUMERO", WHATSAPP_OFICIAL) or WHATSAPP_OFICIAL)
SMTP_HOST = config_val("SMTP_HOST", "")
SMTP_PORT = int(config_val("SMTP_PORT", "587") or 587)
SMTP_USER = config_val("SMTP_USER", "")
SMTP_PASSWORD = config_val("SMTP_PASSWORD", "")
SMTP_FROM = config_val("SMTP_FROM", SMTP_USER)
HASH_PREFIX = "pbkdf2_sha256"
HASH_ITERATIONS = 260000
AREAS_CHAMADO = ["Gerente", "Suporte", "Compras"]
MAX_UPLOAD_BANCO_BYTES = int(config_val("MAX_UPLOAD_BANCO_BYTES", str(8 * 1024 * 1024)) or (8 * 1024 * 1024))
DSYSTEM_UPLOAD_MAX_BYTES = int(config_val("DSYSTEM_UPLOAD_MAX_BYTES", str(7 * 1024 * 1024 * 1024)) or (7 * 1024 * 1024 * 1024))
configurar_limite_arquivos_estaticos(DSYSTEM_UPLOAD_MAX_BYTES)
DSYSTEM_STATIC_DIR = Path(__file__).resolve().parent / "static" / "dsystem"
DSYSTEM_STATIC_DIR_LEGADA = Path(__file__).resolve().parent / ".streamlit" / "static" / "dsystem"
TIPOS_IMAGEM_UPLOAD = ["png", "jpg", "jpeg", "webp"]

def responsavel_area_chamado(area):
    return "Daniel.fabio" if area in {"Gerente", "Compras"} else ""

def criar_hash_senha(senha):
    salt = py_secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", str(senha).encode("utf-8"), salt.encode("utf-8"), HASH_ITERATIONS)
    return f"{HASH_PREFIX}${HASH_ITERATIONS}${salt}${digest.hex()}"

def senha_esta_com_hash(valor):
    return isinstance(valor, str) and valor.startswith(f"{HASH_PREFIX}$")

def verificar_senha(senha_digitada, senha_salva):
    senha_digitada = "" if senha_digitada is None else str(senha_digitada)
    senha_salva = "" if senha_salva is None else str(senha_salva)
    if senha_esta_com_hash(senha_salva):
        try:
            _, iteracoes, salt, digest_salvo = senha_salva.split("$", 3)
            digest = hashlib.pbkdf2_hmac("sha256", senha_digitada.encode("utf-8"), salt.encode("utf-8"), int(iteracoes)).hex()
            return py_secrets.compare_digest(digest, digest_salvo)
        except Exception:
            return False
    return py_secrets.compare_digest(senha_digitada, senha_salva)

def gerar_secret_2fa():
    return base64.b32encode(py_secrets.token_bytes(20)).decode("ascii").rstrip("=")

def codigo_totp(secret, intervalo=30, digitos=6, momento=None):
    if not secret:
        return ""
    momento = int(time.time() if momento is None else momento)
    contador = int(momento // intervalo)
    padding = "=" * ((8 - len(secret) % 8) % 8)
    chave = base64.b32decode((secret + padding).upper())
    msg = struct.pack(">Q", contador)
    digest = hmac.new(chave, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    codigo = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(codigo % (10 ** digitos)).zfill(digitos)

def verificar_totp(secret, codigo, janela=1):
    codigo = re.sub(r"\D", "", codigo or "")
    if len(codigo) != 6:
        return False
    agora = int(time.time())
    return any(py_secrets.compare_digest(codigo_totp(secret, momento=agora + (offset * 30)), codigo) for offset in range(-janela, janela + 1))

def uri_totp_cliente(usuario, secret):
    issuer = "Dsystem ERP"
    label = f"{issuer}:{usuario}"
    return (
        "otpauth://totp/"
        f"{quote(label)}?secret={secret}&issuer={quote(issuer)}&digits=6&period=30"
    )

def gerar_codigo_email_2fa():
    return f"{py_secrets.randbelow(1000000):06d}"

def enviar_email(destinatario, assunto, corpo):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD or not SMTP_FROM:
        raise RuntimeError("SMTP não configurado. Configure SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD e SMTP_FROM.")
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = destinatario
    msg["Subject"] = assunto
    msg.set_content(corpo)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)


def enviar_email_com_anexo(destinatario, assunto, corpo, nome_arquivo, arquivo, mime_type="application/pdf"):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD or not SMTP_FROM:
        raise RuntimeError("SMTP não configurado. Configure SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD e SMTP_FROM.")
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = destinatario
    msg["Subject"] = assunto
    msg.set_content(corpo)
    tipo, subtipo = (mime_type or "application/pdf").split("/", 1)
    msg.add_attachment(bytes(arquivo), maintype=tipo, subtype=subtipo, filename=nome_arquivo)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)

def enviar_codigo_email_cliente(cliente, contexto="login"):
    email_cliente = (cliente.get("email") or "").strip()
    if not email_cliente:
        raise RuntimeError("Cliente sem e-mail cadastrado.")
    codigo = gerar_codigo_email_2fa()
    st.session_state["cliente_email_2fa_hash"] = criar_hash_senha(codigo)
    st.session_state["cliente_email_2fa_expira"] = time.time() + 600
    st.session_state["cliente_email_2fa_destino"] = email_cliente
    assunto = "Código de acesso ao Portal Dsystem"
    corpo = (
        f"Olá, {cliente.get('nome') or 'cliente'}.\n\n"
        f"Seu código de acesso ao Portal Dsystem é: {codigo}\n\n"
        "Esse código vence em 10 minutos.\n"
        "Se você não tentou acessar o portal, ignore esta mensagem."
    )
    enviar_email(email_cliente, assunto, corpo)
    registrar_acesso_cliente(cliente, f"codigo_email_enviado_{contexto}")

def verificar_codigo_email_cliente(codigo):
    expira = st.session_state.get("cliente_email_2fa_expira", 0)
    codigo_hash = st.session_state.get("cliente_email_2fa_hash", "")
    if time.time() > expira:
        return False
    return verificar_senha(re.sub(r"\D", "", codigo or ""), codigo_hash)

from dsystem_erp.navigation import ARVORE_PERMISSOES, LEGACY_PERMISSOES, MODULOS_NAVEGACAO, PERMISSOES_INFRA_ABAS, TODAS_PERMISSOES
def carregar_submodulos(valor):
    if not valor:
        return set()
    if isinstance(valor, (list, tuple, set)):
        return {str(item) for item in valor}
    try:
        dados = json.loads(valor)
        if isinstance(dados, dict):
            return {str(k) for k, v in dados.items() if v}
        if isinstance(dados, list):
            return {str(item) for item in dados}
    except Exception:
        pass
    return set()

def valor_usuario(usuario, chave, padrao=0):
    try:
        return usuario.get(chave, padrao)
    except Exception:
        try:
            return usuario[chave]
        except Exception:
            return padrao

def permissoes_do_usuario(usuario):
    permissoes = carregar_submodulos(valor_usuario(usuario, "submodulos", "[]"))
    for acao, coluna in LEGACY_PERMISSOES.items():
        if valor_usuario(usuario, coluna, 0):
            permissoes.add(acao)
    return permissoes

def tem_permissao(acao, usuario=None):
    usuario = usuario or st.session_state
    if valor_usuario(usuario, "tipo_login", "") == "cliente":
        return acao in {"cliente.portal", "cliente.os", "cliente.autorizacao", "cliente.chamados", "cliente.propostas"}
    if valor_usuario(usuario, "is_admin", 0):
        return True
    permissoes = permissoes_do_usuario(usuario)
    return acao in permissoes

def tem_alguma_permissao(prefixo, usuario=None):
    usuario = usuario or st.session_state
    if valor_usuario(usuario, "is_admin", 0):
        return True
    permissoes = permissoes_do_usuario(usuario)
    return any(item == prefixo or item.startswith(f"{prefixo}.") for item in permissoes)

def flags_legadas(permissoes):
    return {coluna: int(acao in permissoes) for acao, coluna in LEGACY_PERMISSOES.items()}

def editor_permissoes(prefixo, usuario=None):
    permissoes_atuais = permissoes_do_usuario(usuario or {})
    selecionadas = set()
    for modulo in ARVORE_PERMISSOES:
        acoes_modulo = [acao for sub in modulo["submodulos"] for acao, _ in sub["acoes"]]
        modulo_completo = all(acao in permissoes_atuais for acao in acoes_modulo)
        liberar_modulo = st.checkbox(
            f"{modulo['titulo']}",
            value=modulo_completo,
            key=f"{prefixo}_{modulo['modulo']}_full",
            help="Marcado libera todo o módulo. Abra os submódulos abaixo para permissões específicas.",
        )
        if liberar_modulo:
            selecionadas.update(acoes_modulo)
        with st.expander(f"Submódulos de {modulo['titulo']}", expanded=False):
            for submodulo in modulo["submodulos"]:
                st.markdown(f"**{submodulo['titulo']}**")
                cols = st.columns(min(len(submodulo["acoes"]), 4) or 1)
                for idx, (acao, rotulo) in enumerate(submodulo["acoes"]):
                    valor = liberar_modulo or acao in permissoes_atuais
                    marcado = cols[idx % len(cols)].checkbox(
                        rotulo,
                        value=valor,
                        disabled=liberar_modulo,
                        key=f"{prefixo}_{acao}",
                    )
                    if liberar_modulo or marcado:
                        selecionadas.add(acao)
    return selecionadas

class CompatRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

TABELA_LOG_SISTEMA = "logs_sistema"
TABELAS_SEM_LOG_AUTOMATICO = {TABELA_LOG_SISTEMA, "clientes_portal_acessos"}
COLUNAS_ID_LOG = {
    "clientes": "id",
    "usuarios": "id",
    "orcamentos": "orc_id",
    "ordens_servico": "os_id",
}

def usuario_log_atual():
    try:
        return st.session_state.get("username") or "sistema"
    except Exception:
        return "sistema"

def pagina_log_atual():
    try:
        return st.session_state.get("pagina_atual") or ""
    except Exception:
        return ""

def acao_pt_log(acao):
    return {"insert": "Entrada", "update": "Editar", "delete": "Excluir"}.get(acao, acao)

def registrar_log_cursor(cursor, acao, tabela, registro_id="", cliente="", detalhes=None):
    if not tabela or tabela in TABELAS_SEM_LOG_AUTOMATICO:
        return
    agora = agora_sao_paulo().strftime("%Y-%m-%d %H:%M:%S")
    try:
        ip = st.context.ip_address or ""
    except Exception:
        ip = ""
    detalhes_json = json.dumps(detalhes or {}, ensure_ascii=False, default=str)
    cursor.execute(
        f"""INSERT INTO {TABELA_LOG_SISTEMA}
           (criado_em, usuario, acao, tabela, registro_id, cliente, pagina, detalhes, ip)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (agora, usuario_log_atual(), acao_pt_log(acao), tabela, str(registro_id or ""), cliente or "", pagina_log_atual(), detalhes_json, ip),
    )

def registrar_evento_sistema(acao, tabela="sistema", registro_id="", cliente="", detalhes=None):
    conn = conectar_banco()
    c = conn.cursor()
    registrar_log_cursor(c._cursor, acao, tabela, registro_id, cliente, detalhes)
    conn.commit()
    conn.close()

def resumir_detalhes_log(valor, limite=180):
    if not valor:
        return ""
    try:
        dados = json.loads(valor)
        if isinstance(dados, dict):
            partes = []
            for chave in ["novo", "alterado", "excluido"]:
                bloco = dados.get(chave)
                if isinstance(bloco, dict):
                    preenchidos = [f"{k}: {v}" for k, v in bloco.items() if v not in (None, "")]
                    if preenchidos:
                        partes.append(f"{chave}: " + "; ".join(preenchidos[:4]))
            texto = " | ".join(partes) or json.dumps(dados, ensure_ascii=False)
        else:
            texto = str(dados)
    except Exception:
        texto = str(valor)
    return texto[:limite] + ("..." if len(texto) > limite else "")

def gerar_pdf_tabela_simples(rows, titulo):
    try:
        return service_gerar_pdf_tabela_simples(rows, titulo)
    except Exception:
        return gerar_excel_tabela(rows, titulo)

def renderizar_log_sistema():
    if not eh_admin_master():
        st.error("Este log é exclusivo para Daniel.fabio.")
        return

    st.title("Log do Sistema")
    st.caption("Histórico exclusivo do Daniel.fabio com entradas, saídas, edições e exclusões registradas no site.")

    hoje = date.today()
    col1, col2, col3, col4 = st.columns([1.2, 1.2, 1, 1])
    with col1:
        data_inicio = st.date_input("Data inicial:", value=hoje - timedelta(days=30), key="log_data_inicio")
    with col2:
        data_fim = st.date_input("Data final:", value=hoje, key="log_data_fim")
    with col3:
        filtro_acao = st.selectbox("Ação:", ["Todas", "Entrada", "Saída", "Editar", "Excluir"], key="log_acao")
    with col4:
        limite = st.number_input("Limite:", min_value=50, max_value=5000, value=500, step=50, key="log_limite")

    col5, col6, col7 = st.columns([1.4, 1.2, 1.4])
    filtro_cliente = col5.text_input("Filtrar por cliente:", key="log_cliente")
    filtro_tabela = col6.text_input("Filtrar por módulo/tabela:", key="log_tabela")
    busca_livre = col7.text_input("Busca livre:", key="log_busca")

    inicio_sql = f"{data_inicio.strftime('%Y-%m-%d')} 00:00:00"
    fim_sql = f"{data_fim.strftime('%Y-%m-%d')} 23:59:59"
    where = ["criado_em BETWEEN %s AND %s"]
    params = [inicio_sql, fim_sql]
    if filtro_acao != "Todas":
        where.append("acao=%s")
        params.append(filtro_acao)
    if filtro_cliente.strip():
        where.append("cliente LIKE %s")
        params.append(f"%{filtro_cliente.strip()}%")
    if filtro_tabela.strip():
        where.append("tabela LIKE %s")
        params.append(f"%{filtro_tabela.strip()}%")
    if busca_livre.strip():
        where.append("(usuario LIKE %s OR tabela LIKE %s OR registro_id LIKE %s OR cliente LIKE %s OR detalhes LIKE %s)")
        busca = f"%{busca_livre.strip()}%"
        params.extend([busca, busca, busca, busca, busca])

    conn = conectar_banco()
    c = conn.cursor()
    c.execute(
        f"""SELECT * FROM {TABELA_LOG_SISTEMA}
            WHERE {' AND '.join(where)}
            ORDER BY criado_em DESC
            LIMIT %s""",
        params + [int(limite)],
    )
    logs = c.fetchall()
    conn.close()

    if not logs:
        st.info("Nenhum registro encontrado para os filtros selecionados.")
        return

    tabela_logs = []
    contagem_acoes = {}
    contagem_tabelas = {}
    for log in logs:
        item = dict(log)
        criado = item.get("criado_em")
        if isinstance(criado, datetime):
            criado_fmt = criado.strftime("%d/%m/%Y %H:%M:%S")
        else:
            criado_fmt = str(criado or "")
        tabela_logs.append({
            "Data/Hora": criado_fmt,
            "Usuário": item.get("usuario", ""),
            "Ação": item.get("acao", ""),
            "Módulo/Tabela": item.get("tabela", ""),
            "ID": item.get("registro_id", ""),
            "Cliente": item.get("cliente", ""),
            "Página": item.get("pagina", ""),
            "Resumo": resumir_detalhes_log(item.get("detalhes")),
        })
        acao_log = item.get("acao", "") or "Sem ação"
        tabela_log = item.get("tabela", "") or "Sem tabela"
        contagem_acoes[acao_log] = contagem_acoes.get(acao_log, 0) + 1
        contagem_tabelas[tabela_log] = contagem_tabelas.get(tabela_log, 0) + 1

    met1, met2, met3, met4 = st.columns(4)
    met1.metric("Registros filtrados", len(tabela_logs))
    met2.metric("Edições", contagem_acoes.get("Editar", 0))
    met3.metric("Exclusões", contagem_acoes.get("Excluir", 0))
    modulo_top = max(contagem_tabelas.items(), key=lambda item: item[1])[0] if contagem_tabelas else "-"
    met4.metric("Módulo mais ativo", modulo_top)
    st.dataframe(tabela_logs, width="stretch", hide_index=True)

    exp1, exp2, exp3 = st.columns([1, 1, 1.2])
    exp1.download_button(
        "Exportar log em Excel",
        data=gerar_excel_tabela(tabela_logs, "Log do Sistema"),
        file_name="log_sistema.xls",
        mime="application/vnd.ms-excel",
        width="stretch",
    )
    exp2.download_button(
        "Exportar log em PDF",
        data=gerar_pdf_tabela_simples(tabela_logs, "Log do Sistema"),
        file_name="log_sistema.pdf",
        mime="application/pdf",
        width="stretch",
    )
    with exp3:
        confirmar_limpeza = st.checkbox("Confirmar limpeza do log filtrado", key="log_confirma_limpeza")
        if st.button("Limpar log filtrado", disabled=not confirmar_limpeza, width="stretch", key="btn_limpar_log"):
            conn_limpa = conectar_banco()
            climpa = conn_limpa.cursor()
            climpa.execute(f"DELETE FROM {TABELA_LOG_SISTEMA} WHERE {' AND '.join(where)}", params)
            conn_limpa.commit()
            conn_limpa.close()
            st.success("Log filtrado limpo.")
            st.rerun()

    with st.expander("Ver detalhes técnicos do log", expanded=False):
        id_log = st.number_input("ID do log:", min_value=1, step=1, key="log_id_detalhe")
        log_sel = next((dict(x) for x in logs if int(x.get("id") or 0) == int(id_log)), None)
        if log_sel:
            log_sel = {k: (v.strftime("%Y-%m-%d %H:%M:%S") if isinstance(v, datetime) else v) for k, v in log_sel.items()}
            st.json(log_sel)
        else:
            st.caption("Informe um ID visível no resultado carregado.")

    renderizar_logs_tecnicos()

def renderizar_logs_tecnicos():
    st.write("---")
    st.subheader("Logs técnicos")
    st.caption("Erros e eventos internos: backup, banco, emissão fiscal, e-mail, integrações e rotinas automáticas.")

    t1, t2, t3 = st.columns([1, 1.3, 1])
    nivel = t1.selectbox("Nível técnico:", ["Todos", "ERROR", "WARNING", "INFO"], key="log_tecnico_nivel")
    origem = t2.text_input("Origem:", key="log_tecnico_origem")
    limite = t3.number_input("Limite técnico:", min_value=20, max_value=1000, value=200, step=20, key="log_tecnico_limite")

    where = ["1=1"]
    params = []
    if nivel != "Todos":
        where.append("nivel=%s")
        params.append(nivel)
    if origem.strip():
        where.append("origem LIKE %s")
        params.append(f"%{origem.strip()}%")

    conn = conectar_banco()
    c = conn.cursor()
    try:
        c.execute(
            f"""SELECT id, criado_em, nivel, origem, mensagem, detalhes
                FROM logs_tecnicos
                WHERE {' AND '.join(where)}
                ORDER BY criado_em DESC
                LIMIT %s""",
            params + [int(limite)],
        )
        tecnicos = c.fetchall()
    except Exception as ex:
        conn.close()
        st.info(f"Log técnico ainda não está disponível neste banco: {ex}")
        return
    conn.close()

    if not tecnicos:
        st.info("Nenhum log técnico encontrado.")
        return

    linhas = []
    por_nivel = {}
    for log in tecnicos:
        item = dict(log)
        criado = item.get("criado_em")
        criado_fmt = criado.strftime("%d/%m/%Y %H:%M:%S") if isinstance(criado, datetime) else str(criado or "")
        nivel_item = item.get("nivel") or "-"
        por_nivel[nivel_item] = por_nivel.get(nivel_item, 0) + 1
        linhas.append({
            "ID": item.get("id"),
            "Data/Hora": criado_fmt,
            "Nível": nivel_item,
            "Origem": item.get("origem") or "",
            "Mensagem": item.get("mensagem") or "",
            "Detalhes": resumir_detalhes_log(item.get("detalhes"), limite=240),
        })

    l1, l2, l3 = st.columns(3)
    l1.metric("Eventos técnicos", len(linhas))
    l2.metric("Erros", por_nivel.get("ERROR", 0))
    l3.metric("Avisos", por_nivel.get("WARNING", 0))
    st.dataframe(linhas, width="stretch", hide_index=True)
    st.download_button(
        "Exportar logs técnicos",
        data=gerar_excel_tabela(linhas, "Logs Técnicos"),
        file_name="logs_tecnicos.xls",
        mime="application/vnd.ms-excel",
        width="stretch",
        key="exportar_logs_tecnicos",
    )

class CompatCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self._lastrowid = None

    def _adaptar_sql(self, sql):
        return (sql
            .replace("INT PRIMARY KEY AUTO_INCREMENT", "INT PRIMARY KEY AUTO_INCREMENT")
            .replace("AUTO_INCREMENT", "AUTO_INCREMENT")
            .replace("?", "%s"))

    def execute(self, sql, params=None):
        sql_adaptado = self._adaptar_sql(sql)
        acao = None
        if re.match(r"^\s*INSERT\s+INTO\s+", sql_adaptado, flags=re.I):
            acao = "insert"
        elif re.match(r"^\s*UPDATE\s+", sql_adaptado, flags=re.I):
            acao = "update"
        elif re.match(r"^\s*DELETE\s+FROM\s+", sql_adaptado, flags=re.I):
            acao = "delete"

        tabela = extrair_tabela_sql(sql_adaptado, acao) if acao else ""
        deve_logar = bool(acao and tabela and tabela not in TABELAS_SEM_LOG_AUTOMATICO)
        antes = None
        registro_id = ""
        if deve_logar and acao in {"update", "delete"}:
            coluna_id, registro_id = extrair_where_id(sql_adaptado, params)
            if coluna_id and registro_id is not None:
                try:
                    self._cursor.execute(f"SELECT * FROM `{tabela}` WHERE `{coluna_id}`=%s LIMIT 1", (registro_id,))
                    antes = self._cursor.fetchone()
                except Exception:
                    antes = None

        resultado = self._cursor.execute(sql_adaptado, params)
        self._lastrowid = self._cursor.lastrowid

        if deve_logar:
            try:
                if acao == "insert":
                    registro_id = self._lastrowid or ""
                    dados = montar_registro_params(extrair_colunas_insert(sql_adaptado), params)
                    detalhes = {"novo": limpar_registro_log(dados)}
                    cliente = cliente_do_log(tabela, dados)
                elif acao == "update":
                    dados_update = montar_registro_params(extrair_colunas_update(sql_adaptado), params)
                    detalhes = {"antes": limpar_registro_log(antes), "alterado": limpar_registro_log(dados_update)}
                    cliente = cliente_do_log(tabela, dados_update) or cliente_do_log(tabela, antes)
                else:
                    detalhes = {"excluido": limpar_registro_log(antes)}
                    cliente = cliente_do_log(tabela, antes)
                registrar_log_cursor(self._cursor, acao, tabela, registro_id, cliente, detalhes)
            except Exception:
                pass
        return resultado

    def executemany(self, sql, params=None):
        return self._cursor.executemany(self._adaptar_sql(sql), params)

    def fetchone(self):
        row = self._cursor.fetchone()
        return CompatRow(row) if isinstance(row, dict) else row

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [CompatRow(row) if isinstance(row, dict) else row for row in rows]

    @property
    def lastrowid(self):
        return self._lastrowid if self._lastrowid is not None else self._cursor.lastrowid

    def close(self):
        return self._cursor.close()

class CompatConnection:
    row_factory = None

    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args, **kwargs):
        kwargs["dictionary"] = True
        return CompatCursor(self._conn.cursor(*args, **kwargs))

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

def conectar_banco(usar_database=True):
    config = mysql_connection_config(DB_NAME, usar_database=usar_database)
    try:
        return CompatConnection(mysql.connector.connect(**config))
    except mysql.connector.Error as erro:
        if usar_database and getattr(erro, "errno", None) == 1049:
            conn = conectar_banco(usar_database=False)
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            conn.commit()
            cursor.close()
            conn.close()
            return CompatConnection(mysql.connector.connect(**config))
        registrar_log_tecnico("ERROR", "conectar_banco", "Falha ao conectar no MySQL", {"erro": str(erro), "database": DB_NAME})
        raise

def imprimir_html(html, titulo="Impressao"):
    html_limpo = limpar_html_impressao(html).replace("`", "\\`")
    components.html(f"""
    <script>
        var iframe = window.parent.document.createElement('iframe');
        iframe.style.position = 'absolute';
        iframe.style.width = '0px';
        iframe.style.height = '0px';
        iframe.style.border = 'none';
        window.parent.document.body.appendChild(iframe);
        var doc = iframe.contentWindow.document;
        doc.open();
        doc.write(`
            <html>
            <head>
                <title>{titulo}</title>
                <style>
                    body {{ margin: 0; padding: 0; background: white; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                    @page {{ size: A4 portrait; margin: 8mm; }}
                    .quebra-pagina {{ page-break-before: always; }}
                </style>
            </head>
            <body>{html_limpo}</body>
            </html>
        `);
        doc.close();
        setTimeout(function() {{
            iframe.contentWindow.focus();
            iframe.contentWindow.print();
        }}, 500);
    </script>
    """, height=0)

st.markdown("""
<style>
  
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;}
    header {visibility: visible;}
    
   
    .stButton>button { 
        background-color: #004488 !important; 
        color: white !important; 
        border-radius: 8px; 
        border: 2px solid #004488; 
        font-weight: bold; 
        transition: all 0.3s ease; 
    }
    
    div[data-testid="metric-container"] { 
        background-color: #ffffff; 
        border: 1px solid #e0e0e0; 
        padding: 15px; 
        border-radius: 10px; 
        border-left: 6px solid #00a2e8; 
        box-shadow: 2px 4px 10px rgba(0,0,0,0.08); 
    }
    
    h1, h2, h3 { 
        color: #004488 !important; 
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
    }
    
  
    @media print {
        header, footer, [data-testid="stSidebar"], [data-testid="stHeader"],
        [data-baseweb="tab-list"], [role="tablist"], button { 
            display: none !important; 
        }
        
        * {
            background: transparent !important;
            background-color: transparent !important;
        }
        
        body * { 
            visibility: hidden; 
        }
        
        #doc-impressao, #doc-impressao * { 
            visibility: visible !important; 
            color: black !important;
        }
        #doc-impressao {
            background-color: white !important;
        }
        
        html, body, .stApp, .main, .block-container, [data-testid="stAppViewContainer"], 
        [data-testid="stVerticalBlock"], [data-baseweb="tab-panel"], [role="tabpanel"], .element-container {
            position: static !important;
            padding: 0 !important;
            margin: 0 !important;
            max-width: 100% !important; 
            width: 100% !important;
            transform: none !important;
            border: none !important;
            overflow: visible !important;
        }
        
        #doc-impressao { 
            position: absolute !important; 
            top: 0 !important; 
            left: 0 !important; 
            width: 100% !important; 
            max-width: 100% !important; 
            padding: 10mm 15mm !important; 
            margin: 0 !important; 
            box-sizing: border-box !important;
        }
        
        #doc-impressao > div {
            width: 100% !important;
            max-width: 100% !important;
        }
        table {
            width: 100% !important;
        }
        
        table, tr, td, th { 
            page-break-inside: avoid !important; 
            break-inside: avoid !important; 
        }
        
        @page { 
            margin: 0 !important; 
            size: A4 portrait; 
        }

        html, body {
            width: 210mm !important;
            min-height: 297mm !important;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }

        #doc-impressao {
            width: 210mm !important;
            min-height: 297mm !important;
            max-width: 210mm !important;
            padding: 8mm 10mm !important;
            box-sizing: border-box !important;
        }

        #doc-impressao .folha-a4 {
            width: 100% !important;
            min-height: 281mm !important;
            max-width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            box-sizing: border-box !important;
        }

        #doc-impressao .quebra-pagina {
            page-break-before: always !important;
            break-before: page !important;
        }
    }
</style>
""", unsafe_allow_html=True)

def garantir_tabela_nova(conn, cursor, nome_tabela, sql_criacao):
    cursor.execute(sql_criacao)
    try:
        cursor.execute(f"SELECT 1 FROM `{nome_tabela}` LIMIT 1")
        cursor.fetchone()
    except Exception as ex:
        codigo_erro = getattr(ex, "errno", None)
        if codigo_erro not in (1146, 1932):
            raise
        try:
            cursor.execute(f"DROP TABLE IF EXISTS `{nome_tabela}`")
        except Exception:
            pass
        cursor.execute(sql_criacao)
        conn.commit()

def iniciar_banco():
    conn = conectar_banco()
    c = conn.cursor()
    garantir_tabela_migrations(c)
    aplicar_migrations_pendentes(c)
    
    c.execute('''CREATE TABLE IF NOT EXISTS logs_sistema (
        id INT PRIMARY KEY AUTO_INCREMENT,
        criado_em DATETIME,
        usuario VARCHAR(120),
        acao VARCHAR(40),
        tabela VARCHAR(120),
        registro_id VARCHAR(80),
        cliente VARCHAR(255),
        pagina VARCHAR(255),
        detalhes LONGTEXT,
        ip TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS financeiro_cadastros_aux (
        id INT PRIMARY KEY AUTO_INCREMENT,
        tipo VARCHAR(80),
        nome TEXT,
        codigo TEXT,
        ativo VARCHAR(10) DEFAULT 'Sim',
        observacoes LONGTEXT,
        criado_por TEXT,
        criado_em TEXT,
        alterado_por TEXT,
        alterado_em TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ordens_servico (os_id INT PRIMARY KEY AUTO_INCREMENT, data_os TEXT, cliente TEXT, cpf_cnpj TEXT, endereco TEXT, equipamento TEXT, marca TEXT, avaria TEXT, servico TEXT, atendente TEXT, so TEXT, formatar TEXT, backup TEXT, aplicativos TEXT, fonte TEXT, hd_ssd TEXT, ram TEXT, cpu TEXT, gpu TEXT, placa_mae TEXT, gabinete TEXT, chave_so TEXT, app_especifico_check TEXT, app_especifico_nome TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clientes (id INT PRIMARY KEY AUTO_INCREMENT, codigo_cliente TEXT, documento_chave VARCHAR(20) UNIQUE, nome TEXT, telefone TEXT, telefone_secundario TEXT, email TEXT, emails_cobranca TEXT, cnpj TEXT, rg_mei TEXT, endereco TEXT, numero TEXT, complemento TEXT, bairro TEXT, cidade_estado TEXT, cep TEXT, pessoa TEXT, endereco_padrao TEXT, referencia TEXT, codigo_ibge TEXT, uf TEXT, contato_padrao TEXT, contato_cobranca TEXT, contato TEXT, estado_insc_estadual TEXT, data_nascimento TEXT, optante_simples_nacional TEXT, ramo_atividade TEXT, dias_antecedencia_faturamento TEXT, dia_faturamento TEXT, dia_vencimento TEXT, redes_sociais LONGTEXT, funcionarios LONGTEXT, logo_nome TEXT, logo_mime TEXT, logo LONGBLOB, portal_username TEXT, portal_password TEXT, portal_trocar_senha INTEGER DEFAULT 1, portal_2fa_secret TEXT, portal_2fa_ativo INTEGER DEFAULT 0, portal_ultimo_login TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orcamentos (orc_id INT PRIMARY KEY AUTO_INCREMENT, numero TEXT, data_orc TEXT, cliente TEXT, cpf_cnpj TEXT, valor_total TEXT, forma_pagamento TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orcamento_pdfs (
        id INT PRIMARY KEY AUTO_INCREMENT,
        orc_id INTEGER,
        empresa VARCHAR(80),
        nome_arquivo TEXT,
        mime_type TEXT,
        arquivo LONGBLOB,
        criado_por TEXT,
        criado_em TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INT PRIMARY KEY AUTO_INCREMENT, username TEXT UNIQUE, password TEXT, trocar_senha INTEGER DEFAULT 0, is_admin INTEGER, perm_orcamentos INTEGER, perm_del_orc INTEGER, perm_os INTEGER, perm_edit_os INTEGER, perm_del_os INTEGER, perm_emails INTEGER DEFAULT 1, perm_edit_em INTEGER DEFAULT 0, perm_del_em INTEGER DEFAULT 0, perm_infra INTEGER DEFAULT 1, perm_edit_infra INTEGER DEFAULT 0, perm_del_infra INTEGER DEFAULT 0, perm_clientes INTEGER DEFAULT 1, perm_estoque INTEGER DEFAULT 1, perm_faturamento INTEGER DEFAULT 0, submodulos LONGTEXT, empresas_permitidas LONGTEXT, funcionario_nome TEXT, funcionario_cpf TEXT, funcionario_rj TEXT, funcionario_dados_bancarios TEXT, funcionario_telefone TEXT, funcionario_email TEXT, funcionario_endereco TEXT, funcionario_tipo_contrato TEXT, funcionario_forma_pagamento TEXT, funcionario_emite_nf TEXT, funcionario_deslocamento TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS emails_clientes (id INT PRIMARY KEY AUTO_INCREMENT, cliente_vinculado TEXT, funcionario TEXT, email TEXT, senha TEXT, aliases TEXT, provedor TEXT, config_entrada TEXT, config_saida TEXT, capacidade TEXT, data_verificacao TEXT, backup_realizado TEXT, data_backup TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS infra_v4 (id INT PRIMARY KEY AUTO_INCREMENT, cliente_vinc TEXT, fantasia TEXT, razao TEXT, cnpj TEXT, endereco TEXT, contato TEXT, email_prin TEXT, tel_prin TEXT, tel_prov TEXT, contrato_data TEXT, pagto TEXT, venc TEXT, sys_dados TEXT, sys_serial TEXT, sys_cod TEXT, sys_adm TEXT, sys_senha TEXT, sys_sec TEXT, rede_prov TEXT, rede_ip TEXT, rede_log TEXT, rede_sen TEXT, rede_ddns TEXT, rede_dsen TEXT, rede_wire TEXT, rede_wsen TEXT, serv_nome TEXT, serv_ip TEXT, serv_link TEXT, serv_log TEXT, serv_sen TEXT, cert_log TEXT, cert_sen TEXT, fin_b1 TEXT, fin_b2 TEXT, fin_b3 TEXT, pcs_acessos TEXT, faixas_ip LONGTEXT, vpn_acessos LONGTEXT, hospedagem_acessos LONGTEXT, setores LONGTEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS estoque (id INT PRIMARY KEY AUTO_INCREMENT, codigo TEXT, codigo_entrada TEXT, produto TEXT, nome_generico TEXT, categoria TEXT, fileira TEXT, caixa TEXT, quantidade INTEGER, estoque_minimo INTEGER, valor_custo TEXT, valor_venda TEXT, fornecedor TEXT, observacoes TEXT, foto_nome TEXT, foto_mime TEXT, foto LONGBLOB)''')
    c.execute('''CREATE TABLE IF NOT EXISTS equipamentos_os (
        id INT PRIMARY KEY AUTO_INCREMENT,
        os_id INTEGER,
        numero_item TEXT,
        letra_equipamento TEXT,
        tipo_equipamento TEXT,
        equipamento TEXT,
        marca TEXT,
        numero_serie TEXT,
        avaria TEXT,
        defeito TEXT,
        servico TEXT,
        configuracao TEXT,
        foto_nome TEXT,
        foto_mime TEXT,
        foto LONGBLOB
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pedidos_compra (
        id INT PRIMARY KEY AUTO_INCREMENT,
        data_pedido TEXT, produto_id INTEGER, codigo TEXT, produto TEXT,
        quantidade_solicitada INTEGER, fornecedor TEXT, status TEXT, observacoes TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS atendimentos_checklist (
        id INT PRIMARY KEY AUTO_INCREMENT,
        tipo_atendimento TEXT, cliente TEXT, equipamento TEXT, 
        funcionario_atendido TEXT, maquinas_atendidas TEXT, tecnicos TEXT, 
        data_entrada TEXT, status TEXT, obs_entrada TEXT, 
        formatacao TEXT, bkp_convencionais TEXT, bkp_c TEXT, bkp_nav TEXT, bkp_email TEXT, data_backup TEXT,
        pasta_dsys TEXT, limpeza_int TEXT, limpeza_ext TEXT, verif_update TEXT, 
        soft_indesejado TEXT, confirma_soft TEXT, bkp_retornou TEXT, testado_hw TEXT, sacola TEXT, 
        verif_desempenho TEXT, obs_desempenho TEXT, detalhes_realizado TEXT, senhas_alteradas TEXT, historico TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS atendimentos_intervencoes (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        equipamento TEXT,
        identificacao TEXT,
        tipo_equipamento TEXT,
        quem_usa TEXT,
        tecnico TEXT,
        data_intervencao TEXT,
        descricao LONGTEXT,
        preventiva_prevista VARCHAR(20) DEFAULT 'Não',
        periodo_preventiva VARCHAR(60),
        preventiva_realizada VARCHAR(20) DEFAULT 'Não',
        data_preventiva TEXT,
        proxima_preventiva TEXT,
        observacoes LONGTEXT,
        criado_por TEXT,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS infra_equipamentos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        funcionario_usuario TEXT,
        funcionario_nome TEXT,
        origem VARCHAR(80),
        tipo_equipamento VARCHAR(80),
        nome_equipamento TEXT,
        ip_equipamento TEXT,
        quem_usa TEXT,
        informacoes LONGTEXT,
        criado_por TEXT,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS infra_equipamentos_fotos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        equipamento_id INTEGER,
        foto_nome TEXT,
        foto_mime TEXT,
        foto LONGBLOB,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS infra_item_fotos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        ficha_id INTEGER,
        tipo_item VARCHAR(40),
        item_indice INTEGER,
        item_nome TEXT,
        foto_nome TEXT,
        foto_mime TEXT,
        foto LONGBLOB,
        criado_em TEXT
    )''')

   
    c.execute('''CREATE TABLE IF NOT EXISTS agenda_visitas (
        id INT PRIMARY KEY AUTO_INCREMENT,
        tecnico TEXT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        data_visita TEXT,
        hora_inicio TEXT,
        hora_fim TEXT,
        tipo_visita TEXT,
        descricao TEXT,
        status VARCHAR(60) DEFAULT 'Agendado',
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS autorizacoes_cliente (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente TEXT,
        os_id INTEGER,
        servico TEXT,
        status TEXT,
        observacao TEXT,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS chamados_cliente (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        solicitante TEXT,
        area_destino VARCHAR(40) DEFAULT 'Suporte',
        tipo_atendimento TEXT,
        data_solicitada TEXT,
        hora_inicio TEXT,
        hora_fim TEXT,
        titulo TEXT,
        descricao TEXT,
        status VARCHAR(80) DEFAULT 'Novo',
        administrador VARCHAR(120) DEFAULT 'Daniel.fabio',
        funcionario_designado TEXT,
        ajuste_tipo_atendimento TEXT,
        ajuste_data TEXT,
        ajuste_hora_inicio TEXT,
        ajuste_hora_fim TEXT,
        ajuste_descricao TEXT,
        resposta_cliente TEXT,
        criado_por TEXT,
        criado_em TEXT,
        atualizado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS chamados_mensagens (
        id INT PRIMARY KEY AUTO_INCREMENT,
        chamado_id INTEGER,
        autor_tipo VARCHAR(40),
        autor_nome TEXT,
        mensagem LONGTEXT,
        anexo_nome TEXT,
        anexo_mime TEXT,
        anexo LONGBLOB,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS propostas_contratos_cliente (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        tipo TEXT,
        titulo TEXT,
        descricao TEXT,
        nome_arquivo TEXT,
        mime_type TEXT,
        arquivo LONGBLOB,
        status VARCHAR(80) DEFAULT 'Pendente',
        resposta_cliente TEXT,
        criado_por TEXT,
        criado_em TEXT,
        respondido_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS dsystem_arquivos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        pasta TEXT,
        nome_arquivo TEXT,
        mime_type TEXT,
        tamanho BIGINT,
        arquivo LONGBLOB,
        caminho_arquivo TEXT,
        url_arquivo TEXT,
        armazenamento VARCHAR(40) DEFAULT 'banco',
        criado_por TEXT,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS contrato_clausulas (
        id INT PRIMARY KEY AUTO_INCREMENT,
        tipo_contrato VARCHAR(80),
        titulo TEXT,
        texto LONGTEXT,
        ativo VARCHAR(10) DEFAULT 'Sim',
        criado_por TEXT,
        criado_em TEXT,
        alterado_por TEXT,
        alterado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS clientes_portal_acessos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        portal_username TEXT,
        evento VARCHAR(80),
        ip TEXT,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cobrancas_recorrentes (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        tipo_cobranca VARCHAR(120),
        valor_financeiro DECIMAL(12,2) DEFAULT 0,
        data_emprestimo_locacao TEXT,
        motivo LONGTEXT,
        tipo_backup VARCHAR(120),
        quantidade INTEGER DEFAULT 0,
        servidor_backup TEXT,
        maquina_backup TEXT,
        data_cobranca TEXT,
        valor_cobranca DECIMAL(12,2) DEFAULT 0,
        vigencia_inicio TEXT,
        vigencia_fim TEXT,
        licencas_servidor INTEGER DEFAULT 0,
        licencas_maquinas INTEGER DEFAULT 0,
        pagamento VARCHAR(120),
        periodicidade VARCHAR(40),
        informacoes LONGTEXT,
        status VARCHAR(40) DEFAULT 'Ativa',
        criado_por TEXT,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cobrancas_renovacoes (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cobranca_id INTEGER,
        data_renovacao TEXT,
        vigencia_inicio_anterior TEXT,
        vigencia_fim_anterior TEXT,
        vigencia_inicio_nova TEXT,
        vigencia_fim_nova TEXT,
        valor_cobranca DECIMAL(12,2) DEFAULT 0,
        observacao LONGTEXT,
        criado_por TEXT,
        criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS contas_pagar (
        id INT PRIMARY KEY AUTO_INCREMENT,
        fornecedor TEXT, cpf_cnpj TEXT, numero_documento TEXT, tipo_documento TEXT,
        categoria TEXT, centro_custo TEXT, plano_contas TEXT, conta_bancaria TEXT,
        data_emissao TEXT, data_competencia TEXT, data_vencimento TEXT,
        valor_original DECIMAL(14,2) DEFAULT 0, desconto DECIMAL(14,2) DEFAULT 0,
        juros DECIMAL(14,2) DEFAULT 0, multa DECIMAL(14,2) DEFAULT 0,
        valor_total DECIMAL(14,2) DEFAULT 0, forma_pagamento TEXT,
        codigo_barras LONGTEXT, chave_pix TEXT, status VARCHAR(60) DEFAULT 'Aberto',
        observacoes LONGTEXT, data_baixa TEXT, valor_baixado DECIMAL(14,2) DEFAULT 0,
        baixado_por TEXT, criado_por TEXT, criado_em TEXT, alterado_por TEXT, alterado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS contas_receber (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER, cliente TEXT, cpf_cnpj TEXT, numero_documento TEXT,
        tipo_receita TEXT, categoria TEXT, centro_receita TEXT, plano_contas TEXT,
        conta_bancaria TEXT, data_emissao TEXT, data_competencia TEXT, data_vencimento TEXT,
        valor_original DECIMAL(14,2) DEFAULT 0, desconto DECIMAL(14,2) DEFAULT 0,
        juros DECIMAL(14,2) DEFAULT 0, multa DECIMAL(14,2) DEFAULT 0,
        valor_total DECIMAL(14,2) DEFAULT 0, forma_recebimento TEXT,
        nota_fiscal TEXT, boleto TEXT, status VARCHAR(60) DEFAULT 'Aberto',
        observacoes LONGTEXT, data_baixa TEXT, valor_baixado DECIMAL(14,2) DEFAULT 0,
        baixado_por TEXT, criado_por TEXT, criado_em TEXT, alterado_por TEXT, alterado_em TEXT
    )''')
    for coluna_os_recepcao, tipo_os_recepcao in (
        ("chamado_id", "INTEGER"), ("recebido_por", "TEXT"), ("recebido_em", "TEXT"),
    ):
        try: garantir_coluna(c, "ordens_servico", coluna_os_recepcao, tipo_os_recepcao)
        except Exception: pass
    for coluna_eq_kanban, tipo_eq_kanban in (
        ("kanban_status", "VARCHAR(60) DEFAULT 'Recebido'"), ("etiqueta_codigo", "VARCHAR(80)"),
        ("kanban_alterado_por", "TEXT"), ("kanban_alterado_em", "TEXT"),
    ):
        try: garantir_coluna(c, "equipamentos_os", coluna_eq_kanban, tipo_eq_kanban)
        except Exception: pass
    c.execute('''CREATE TABLE IF NOT EXISTS contratos (
        id INT PRIMARY KEY AUTO_INCREMENT, tipo VARCHAR(100), parte_tipo VARCHAR(40), parte_id INTEGER,
        parte_nome TEXT, nome_arquivo TEXT, mime_type TEXT, arquivo LONGBLOB,
        status VARCHAR(40) DEFAULT 'Ativo', valor TEXT, data_inicio TEXT, data_vencimento TEXT,
        observacoes LONGTEXT, criado_por TEXT, criado_em TEXT, alterado_por TEXT, alterado_em TEXT,
        INDEX idx_contratos_parte (parte_tipo, parte_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS cotacoes_compra (
        id INT PRIMARY KEY AUTO_INCREMENT,
        pedido_compra_id INTEGER NOT NULL,
        fornecedor TEXT NOT NULL,
        telefone TEXT,
        meio_compra TEXT NOT NULL,
        valor_item DECIMAL(15,2) NOT NULL,
        observacoes TEXT,
        escolhida INTEGER DEFAULT 0,
        criado_por TEXT,
        criado_em TEXT,
        INDEX idx_cotacoes_pedido (pedido_compra_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS clientes_portal_usuarios (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INTEGER NOT NULL,
        username VARCHAR(255) NOT NULL UNIQUE,
        nome TEXT,
        cargo TEXT,
        tipo VARCHAR(30) DEFAULT 'Funcionário',
        password TEXT,
        trocar_senha INTEGER DEFAULT 1,
        twofa_secret TEXT,
        twofa_ativo INTEGER DEFAULT 0,
        ultimo_login TEXT,
        ativo INTEGER DEFAULT 1,
        criado_em TEXT,
        INDEX idx_portal_usuario_cliente (cliente_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS financeiro_impostos_taxas (
        id INT PRIMARY KEY AUTO_INCREMENT, nome VARCHAR(120) UNIQUE, tipo VARCHAR(30) DEFAULT 'Imposto',
        aliquota_padrao DECIMAL(10,4) DEFAULT 0, ativo VARCHAR(10) DEFAULT 'Sim', criado_por TEXT, criado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS faturamento (
        id INT PRIMARY KEY AUTO_INCREMENT,
        data_lanc TEXT, cliente TEXT, cnpj TEXT, tipo TEXT, emite_nf TEXT, tipo_nota TEXT,
        forma_pag TEXT, itens LONGTEXT, valor_total DECIMAL(14,2) DEFAULT 0, parcelas TEXT,
        vencimento TEXT, orc_ref TEXT, obs_interna LONGTEXT, obs_nota LONGTEXT,
        nota_fiscal TEXT, boleto TEXT, status VARCHAR(60) DEFAULT 'Aberto',
        alterado_por TEXT, alterado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS faturamento_anexos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        faturamento_id INTEGER,
        tipo VARCHAR(80),
        nome_arquivo TEXT,
        mime_type TEXT,
        arquivo LONGBLOB,
        criado_por TEXT,
        criado_em TEXT
    )''')

    for coluna_fat, tipo_fat in [
        ("alterado_por", "TEXT"), ("alterado_em", "TEXT"),
        ("nota_fiscal", "TEXT"), ("boleto", "TEXT"),
        ("status", "VARCHAR(60) DEFAULT 'Aberto'"),
    ]:
        try:
            garantir_coluna(c, "faturamento", coluna_fat, tipo_fat)
        except Exception:
            pass

    garantir_tabela_nova(conn, c, "financeiro_recorrencias_v2", '''CREATE TABLE IF NOT EXISTS financeiro_recorrencias_v2 (
        id INT PRIMARY KEY AUTO_INCREMENT, tipo VARCHAR(20), parte TEXT, cpf_cnpj TEXT, descricao TEXT,
        valor DECIMAL(14,2) DEFAULT 0, frequencia VARCHAR(40), dia_vencimento INTEGER,
        data_inicial TEXT, data_final TEXT, centro TEXT, categoria TEXT, gerar_automaticamente VARCHAR(10),
        ativo VARCHAR(10) DEFAULT 'Sim', ultima_geracao TEXT, criado_por TEXT, criado_em TEXT
    )''')
    garantir_tabela_nova(conn, c, "financeiro_cobrancas_v2", '''CREATE TABLE IF NOT EXISTS financeiro_cobrancas_v2 (
        id INT PRIMARY KEY AUTO_INCREMENT, conta_receber_id INTEGER, cliente TEXT, dias_atraso INTEGER,
        valor_atualizado DECIMAL(14,2) DEFAULT 0, historico LONGTEXT, status VARCHAR(60),
        proxima_acao TEXT, responsavel TEXT, observacoes LONGTEXT, criado_em TEXT, alterado_em TEXT
    )''')
    garantir_tabela_nova(conn, c, "financeiro_renegociacoes_v2", '''CREATE TABLE IF NOT EXISTS financeiro_renegociacoes_v2 (
        id INT PRIMARY KEY AUTO_INCREMENT, tipo VARCHAR(20), parte TEXT, titulos_originais TEXT,
        valor_original DECIMAL(14,2) DEFAULT 0, valor_renegociado DECIMAL(14,2) DEFAULT 0,
        entrada DECIMAL(14,2) DEFAULT 0, parcelas INTEGER DEFAULT 1, primeiro_vencimento TEXT,
        juros DECIMAL(14,2) DEFAULT 0, multa DECIMAL(14,2) DEFAULT 0, desconto DECIMAL(14,2) DEFAULT 0,
        status VARCHAR(40) DEFAULT 'Ativo', observacoes LONGTEXT, criado_por TEXT, criado_em TEXT
    )''')

    for tabela_fin in ["contas_pagar", "contas_receber"]:
        for coluna_fin, tipo_coluna in [
            ("anexo_nome", "TEXT"), ("anexo_mime", "TEXT"), ("anexo", "LONGBLOB"),
            ("comprovante_nome", "TEXT"), ("comprovante_mime", "TEXT"), ("comprovante", "LONGBLOB"),
            ("conta_baixa", "TEXT"), ("forma_baixa", "TEXT"), ("observacao_baixa", "LONGTEXT"),
            ("taxas_baixa", "DECIMAL(14,2) DEFAULT 0"), ("juros_baixa", "DECIMAL(14,2) DEFAULT 0"),
            ("multa_baixa", "DECIMAL(14,2) DEFAULT 0"), ("desconto_baixa", "DECIMAL(14,2) DEFAULT 0"),
            ("cancelado_por", "TEXT"), ("motivo_cancelamento", "LONGTEXT"),
        ]:
            try: c.execute(f"ALTER TABLE {tabela_fin} ADD COLUMN {coluna_fin} {tipo_coluna}")
            except Exception: pass
    for coluna_rec, tipo_rec in [
        ("regime_tributario", "VARCHAR(40) DEFAULT 'Normal'"), ("impostos", "LONGTEXT"),
        ("simples_aliquota", "DECIMAL(10,4) DEFAULT 0"), ("simples_valor", "DECIMAL(14,2) DEFAULT 0"),
        ("taxas_personalizadas", "LONGTEXT"), ("valor_impostos", "DECIMAL(14,2) DEFAULT 0"),
        ("valor_liquido", "DECIMAL(14,2) DEFAULT 0"), ("parcelado", "VARCHAR(10) DEFAULT 'Não'"),
        ("quantidade_parcelas", "INTEGER DEFAULT 1"), ("meio_parcelamento", "VARCHAR(60)"),
        ("parcelas_detalhes", "LONGTEXT"), ("bandeira_cartao", "VARCHAR(40)"),
        ("custo_tipo", "VARCHAR(20)"), ("pedido_compra_id", "INTEGER"),
        ("fornecedor_custo", "TEXT"), ("custo_unitario", "DECIMAL(14,2) DEFAULT 0"),
        ("quantidade_custo", "DECIMAL(14,3) DEFAULT 1"), ("custo_total", "DECIMAL(14,2) DEFAULT 0"),
        ("lucro_estimado", "DECIMAL(14,2) DEFAULT 0"), ("margem_lucro_percentual", "DECIMAL(10,4) DEFAULT 0"),
        ("cobranca_recorrente_id", "INTEGER"), ("cobranca_competencia", "VARCHAR(30)"),
    ]:
        try: garantir_coluna(c, "contas_receber", coluna_rec, tipo_rec)
        except Exception: pass
    try:
        c.execute(
            "CREATE UNIQUE INDEX uq_conta_receber_recorrencia ON contas_receber (cobranca_recorrente_id, cobranca_competencia)"
        )
    except Exception:
        pass
    for coluna_aprovacao, tipo_aprovacao in [
        ("solicitante", "TEXT"), ("aprovador", "TEXT"), ("status_aprovacao", "VARCHAR(60) DEFAULT 'Pendente'"),
        ("motivo_reprovacao", "LONGTEXT"), ("data_aprovacao", "TEXT"),
    ]:
        try: c.execute(f"ALTER TABLE contas_pagar ADD COLUMN {coluna_aprovacao} {tipo_aprovacao}")
        except Exception: pass

    c.execute('''CREATE TABLE IF NOT EXISTS notas_fiscais (
        id INT PRIMARY KEY AUTO_INCREMENT,
        faturamento_id INTEGER, cliente TEXT, cpf_cnpj TEXT, tipo_nota TEXT,
        data_competencia TEXT, descricao LONGTEXT,
        valor_servicos DECIMAL(14,2) DEFAULT 0, aliquota_iss DECIMAL(8,4) DEFAULT 0,
        valor_iss DECIMAL(14,2) DEFAULT 0, codigo_servico TEXT, municipio_prestacao TEXT,
        status VARCHAR(60) DEFAULT 'Pendente', numero_nota TEXT, chave_acesso TEXT,
        link_nota LONGTEXT, observacoes LONGTEXT, criado_por TEXT, criado_em TEXT, emitido_em TEXT,
        xml_envio LONGTEXT, xml_retorno LONGTEXT, xml_autorizado LONGTEXT, pdf_base64 LONGTEXT,
        protocolo TEXT, mensagem_retorno LONGTEXT, numero_lote TEXT, atualizado_em TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS nfse_bh_servicos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        nome TEXT,
        codigo_servico TEXT,
        item_lista_servico TEXT,
        aliquota_iss DECIMAL(8,4) DEFAULT 0,
        ativo VARCHAR(10) DEFAULT 'Sim',
        observacoes LONGTEXT
    )''')
    c.execute("SELECT COUNT(*) AS total FROM nfse_bh_servicos")
    total_nfse_servicos = c.fetchone()
    if (total_nfse_servicos.get("total") if isinstance(total_nfse_servicos, dict) else total_nfse_servicos[0]) == 0:
        c.execute(
            """INSERT INTO nfse_bh_servicos
               (nome, codigo_servico, item_lista_servico, aliquota_iss, ativo, observacoes)
               VALUES (?,?,?,?,?,?)""",
            ("Serviço Dsystem", "", "", 0, "Sim", "Cadastro inicial. Preencha o código e item da lista conforme a atividade."),
        )

    servicos_informatica_padrao = [
        ("Analise e desenvolvimento de sistemas", "01.01.01", "01.01", 0, "Sim", "Projeto, analise, desenho e desenvolvimento de sistemas sob demanda."),
        ("Desenvolvimento de sistemas sob encomenda", "01.01.02", "01.01", 0, "Sim", "Criacao de software, modulos, sistemas internos e automacoes."),
        ("Programacao", "01.02.01", "01.02", 0, "Sim", "Programacao, ajustes tecnicos e implementacao de codigo."),
        ("Consultoria em informatica", "01.06.01", "01.06", 0, "Sim", "Diagnostico, assessoria, planejamento tecnico e orientacao em TI."),
        ("Suporte tecnico em informatica", "01.07.01", "01.07", 0, "Sim", "Suporte, manutencao, instalacao, configuracao e bancos de dados."),
        ("Instalacao/configuracao de software", "01.07.02", "01.07", 0, "Sim", "Instalacao, configuracao e parametrizacao de programas."),
        ("Instalacao de Office e aplicativos", "01.07.02", "01.07", 0, "Sim", "Instalacao e configuracao de pacote Office, navegadores, antivirus e aplicativos de uso geral."),
        ("Instalacao de Windows e drivers", "01.07.02", "01.07", 0, "Sim", "Instalacao, configuracao de Windows, drivers e programas essenciais do computador."),
        ("Manutencao de software/banco de dados", "01.07.03", "01.07", 0, "Sim", "Manutencao corretiva, preventiva e atualizacao de sistemas ou banco de dados."),
        ("Formatacao e reinstalacao de sistema", "01.07.03", "01.07", 0, "Sim", "Formatacao, reinstalacao do sistema operacional, backup basico e configuracoes iniciais."),
        ("Paginas eletronicas / Web design", "01.08.01", "01.08", 0, "Sim", "Planejamento, criacao, manutencao e atualizacao de sites."),
        ("Manutencao de hardware/equipamentos", "14.01.01", "14.01", 0, "Sim", "Manutencao, reparo, limpeza, troca de pecas e revisao de computadores, notebooks e perifericos."),
    ]
    for servico_padrao in servicos_informatica_padrao:
        c.execute("SELECT COUNT(*) AS total FROM nfse_bh_servicos WHERE codigo_servico=? AND nome=?", (servico_padrao[1], servico_padrao[0]))
        total_servico_padrao = c.fetchone()
        total_servico_padrao = total_servico_padrao.get("total") if isinstance(total_servico_padrao, dict) else total_servico_padrao[0]
        if not total_servico_padrao:
            c.execute(
                """INSERT INTO nfse_bh_servicos
                   (nome, codigo_servico, item_lista_servico, aliquota_iss, ativo, observacoes)
                   VALUES (?,?,?,?,?,?)""",
                servico_padrao,
            )

    c.execute('''CREATE TABLE IF NOT EXISTS codigos_fiscais_produtos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        nome TEXT,
        ncm VARCHAR(20),
        categoria VARCHAR(120),
        ativo VARCHAR(10) DEFAULT 'Sim',
        observacoes LONGTEXT
    )''')
    produtos_informatica_padrao = [
        ("Notebook ate 3,5 kg", "8471.30.12", "Informatica", "Computador portatil/notebook. Confirme a classificacao conforme configuracao do produto."),
        ("Notebook/outro portatil", "8471.30.19", "Informatica", "Outras maquinas automaticas portateis de processamento de dados."),
        ("Computador desktop / conjunto", "8471.49.00", "Informatica", "Computador apresentado como sistema/conjunto. Conferir se acompanha monitor/perifericos."),
        ("Monitor de informatica", "8528.52.00", "Informatica", "Monitor capaz de conexao direta a maquina de processamento de dados."),
        ("Impressora ou multifuncional", "8443.31.00", "Informatica", "Maquinas com duas ou mais funcoes, como impressao/copia/digitalizacao."),
        ("Teclado para computador", "8471.60.52", "Informatica", "Unidade de entrada: teclado."),
        ("Mouse para computador", "8471.60.53", "Informatica", "Unidade de entrada: mouse."),
        ("HD/SSD/unidade de armazenamento", "8471.70.40", "Informatica", "Unidade de memoria/armazenamento. Conferir modelo e tecnologia antes da nota."),
    ]
    for produto_padrao in produtos_informatica_padrao:
        c.execute("SELECT COUNT(*) AS total FROM codigos_fiscais_produtos WHERE ncm=?", (produto_padrao[1],))
        total_produto_padrao = c.fetchone()
        total_produto_padrao = total_produto_padrao.get("total") if isinstance(total_produto_padrao, dict) else total_produto_padrao[0]
        if not total_produto_padrao:
            c.execute(
                """INSERT INTO codigos_fiscais_produtos
                   (nome, ncm, categoria, ativo, observacoes)
                   VALUES (?,?,?,?,?)""",
                (produto_padrao[0], produto_padrao[1], produto_padrao[2], "Sim", produto_padrao[3]),
            )

    try: c.execute('ALTER TABLE usuarios ADD COLUMN perm_atendimentos INTEGER DEFAULT 0')
    except Exception: pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN perm_edit_atendimentos INTEGER DEFAULT 0')
    except Exception: pass

    try: c.execute('ALTER TABLE usuarios ADD COLUMN perm_clientes INTEGER DEFAULT 1')
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN cep TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN emails_cobranca TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN codigo_cliente TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN documento_chave VARCHAR(20)")
    except Exception: pass
    try:
        c.execute("SHOW INDEX FROM clientes WHERE Key_name='nome'")
        if c.fetchone():
            c.execute("ALTER TABLE clientes DROP INDEX nome")
    except Exception:
        pass
    try:
        c.execute("SELECT cnpj FROM clientes WHERE COALESCE(cnpj,'')<>'' GROUP BY cnpj HAVING COUNT(*)=1")
        for doc_unico in [row[0] for row in c.fetchall()]:
            chave_doc = re.sub(r"\D", "", str(doc_unico or ""))
            if chave_doc:
                c.execute("UPDATE clientes SET documento_chave=? WHERE cnpj=? AND documento_chave IS NULL", (chave_doc, doc_unico))
        c.execute("CREATE UNIQUE INDEX uq_clientes_documento_chave ON clientes (documento_chave)")
    except Exception:
        pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN funcionarios LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN telefone_secundario TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN redes_sociais LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN logo_nome TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN logo_mime TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN logo LONGBLOB")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN portal_username TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN portal_password TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN portal_trocar_senha INTEGER DEFAULT 1")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN portal_2fa_secret TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN portal_2fa_ativo INTEGER DEFAULT 0")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN portal_ultimo_login TEXT")
    except Exception: pass
    for coluna_cliente_nova in [
        "pessoa", "endereco_padrao", "referencia", "codigo_ibge", "uf",
        "contato_padrao", "contato_cobranca", "contato", "estado_insc_estadual",
        "data_nascimento", "optante_simples_nacional", "ramo_atividade",
        "dias_antecedencia_faturamento", "dia_faturamento", "dia_vencimento",
    ]:
        try: c.execute(f"ALTER TABLE clientes ADD COLUMN {coluna_cliente_nova} TEXT")
        except Exception: pass
    try: c.execute("ALTER TABLE dsystem_arquivos ADD COLUMN caminho_arquivo TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE dsystem_arquivos ADD COLUMN url_arquivo TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE dsystem_arquivos ADD COLUMN armazenamento VARCHAR(40) DEFAULT 'banco'")
    except Exception: pass
    try: c.execute("ALTER TABLE dsystem_arquivos MODIFY COLUMN tamanho BIGINT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN area_destino VARCHAR(40) DEFAULT 'Suporte'")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN funcionario_designado TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN ajuste_tipo_atendimento TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN ajuste_data TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN ajuste_hora_inicio TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN ajuste_hora_fim TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN ajuste_descricao TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN resposta_cliente TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE chamados_cliente ADD COLUMN administrador VARCHAR(120) DEFAULT 'Daniel.fabio'")
    except Exception: pass
    try: c.execute("ALTER TABLE ordens_servico ADD COLUMN tecnico_extra VARCHAR(255) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN numero_item TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN tipo_equipamento TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN avaria TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN configuracao TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN foto_nome TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN foto_mime TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE equipamentos_os ADD COLUMN foto LONGBLOB")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN dvr_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN cameras_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN alarmes_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN aplicativos_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN pfsense_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN antivirus_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN setores LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN faixas_ip LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN vpn_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_v4 ADD COLUMN hospedagem_acessos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE atendimentos_intervencoes ADD COLUMN proxima_preventiva TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_equipamentos ADD COLUMN funcionario_usuario TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE infra_equipamentos ADD COLUMN funcionario_nome TEXT")
    except Exception: pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN perm_estoque INTEGER DEFAULT 1')
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN codigo_entrada VARCHAR(255) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN nome_generico VARCHAR(255) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN fileira VARCHAR(255) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN caixa VARCHAR(255) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN foto_nome TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN foto_mime TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE estoque ADD COLUMN foto LONGBLOB")
    except Exception: pass
    for coluna_estoque_preco, tipo_estoque_preco in (
        ("custo_deslocamento", "DECIMAL(15,2) DEFAULT 0"),
        ("imposto_percentual", "DECIMAL(9,4) DEFAULT 0"),
        ("lucro_percentual", "DECIMAL(9,4) DEFAULT 0"),
        ("preco_revenda_automatico", "VARCHAR(5) DEFAULT 'Não'"),
        ("permitir_ajuste_preco", "INTEGER DEFAULT 0"),
        ("situacao_nota", "VARCHAR(30) DEFAULT 'Comprado com nota'"),
    ):
        try: c.execute(f"ALTER TABLE estoque ADD COLUMN {coluna_estoque_preco} {tipo_estoque_preco}")
        except Exception: pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN perm_faturamento INTEGER DEFAULT 0')
    except Exception: pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN modulo_gerencial INTEGER DEFAULT 0')
    except Exception: pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN modulo_financeiro INTEGER DEFAULT 0')
    except Exception: pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN modulo_faturamento INTEGER DEFAULT 0')
    except Exception: pass
    try: c.execute('ALTER TABLE usuarios ADD COLUMN modulo_operacional INTEGER DEFAULT 0')
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN submodulos LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN empresas_permitidas LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_nome TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_cpf TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_rj TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_dados_bancarios TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_telefone TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_email TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_endereco TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_tipo_contrato TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_forma_pagamento TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_emite_nf TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN funcionario_deslocamento TEXT")
    except Exception: pass
    try: garantir_coluna(c, "usuarios", "trocar_senha", "INTEGER DEFAULT 0")
    except Exception: pass

 
    try: c.execute("ALTER TABLE clientes ADD COLUMN tipo VARCHAR(40) DEFAULT 'Cliente'")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN insc_estadual VARCHAR(80) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN insc_municipal VARCHAR(80) DEFAULT ''")
    except Exception: pass
    try: c.execute("ALTER TABLE clientes ADD COLUMN substituto_tributario VARCHAR(20) DEFAULT 'Não'")
    except Exception: pass

 
    try: c.execute("ALTER TABLE orcamentos ADD COLUMN itens LONGTEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE orcamentos ADD COLUMN obs_pag TEXT")
    except Exception: pass
    try: c.execute("ALTER TABLE orcamentos ADD COLUMN obs_geral TEXT")
    except Exception: pass
    for coluna_orc, tipo_orc in [
        ("status", "VARCHAR(60) DEFAULT 'Aberto'"),
        ("empresa_aprovada", "TEXT"),
        ("tipo_faturamento_aprovado", "TEXT"),
        ("faturamento_id", "INTEGER"),
        ("data_validade", "VARCHAR(30)"),
        ("orcamento_origem_id", "INTEGER"),
        ("versao", "INTEGER DEFAULT 1"),
        ("enviado_email_em", "TEXT"),
        ("enviado_whatsapp_em", "TEXT"),
        ("juros_percentual", "DECIMAL(10,4) DEFAULT 0"),
        ("taxa_renegociacao", "DECIMAL(15,2) DEFAULT 0"),
        ("alterado_em", "TEXT"),
        ("alterado_por", "TEXT"),
    ]:
        try: c.execute(f"ALTER TABLE orcamentos ADD COLUMN {coluna_orc} {tipo_orc}")
        except Exception: pass

    c.execute("SELECT id FROM clientes WHERE codigo_cliente IS NULL OR codigo_cliente=''")
    clientes_sem_codigo = [row[0] for row in c.fetchall()]
    for cli_id in clientes_sem_codigo:
        c.execute("UPDATE clientes SET codigo_cliente=? WHERE id=?", (f"CLI{cli_id:05d}", cli_id))

    c.execute("SELECT * FROM usuarios WHERE is_admin=1 LIMIT 1")
    if not c.fetchone():
        admin_usuario = config_val("ADMIN_USERNAME", "Daniel.fabio")
        senha_admin = config_val("ADMIN_PASSWORD") or config_val("ADMINPASS") or config_val("SENHA_ADMIN_MASTER")
        if senha_admin:
            c.execute('''INSERT INTO usuarios (username, password, is_admin, perm_orcamentos, perm_del_orc, perm_os, perm_edit_os, perm_del_os, perm_emails, perm_edit_em, perm_del_em, perm_infra, perm_edit_infra, perm_del_infra, perm_clientes, perm_estoque, perm_faturamento) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (admin_usuario, criar_hash_senha(senha_admin), 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1))

    usuario_recepcao = str(config_val("RECEPCAO_USERNAME", "recepcao") or "").strip()
    senha_recepcao = str(config_val("RECEPCAO_PASSWORD", "") or "")
    c.execute("SELECT id FROM usuarios WHERE LOWER(username)=LOWER(?) LIMIT 1", (usuario_recepcao,))
    if usuario_recepcao and senha_recepcao and not c.fetchone():
        c.execute('''INSERT INTO usuarios
            (username, password, trocar_senha, is_admin, perm_orcamentos, perm_del_orc,
             perm_os, perm_edit_os, perm_del_os, perm_emails, perm_edit_em, perm_del_em,
             perm_infra, perm_edit_infra, perm_del_infra, perm_clientes, perm_estoque,
             perm_faturamento, perm_atendimentos, perm_edit_atendimentos, submodulos,
             empresas_permitidas, funcionario_nome)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (usuario_recepcao, criar_hash_senha(senha_recepcao), 1, 0, 0, 0,
             1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0,
             0, 0, 0, json.dumps(["os.view", "os.edit", "recepcao.view", "recepcao.edit"]),
             "[]", "Recepção"))
    
    registrar_migration(c, "000_schema_legado_iniciar_banco", "Schema atual criado e atualizado pelo iniciar_banco legado.")
    conn.commit()
    conn.close()

iniciar_banco()

def empresas_permitidas_usuario(usuario=None):
    usuario = usuario or st.session_state
    if valor_usuario(usuario, "is_admin", 0) or valor_usuario(usuario, "tipo_login", "") == "cliente":
        return []
    return sorted(carregar_submodulos(valor_usuario(usuario, "empresas_permitidas", "[]")))

def pode_acessar_empresa(nome_empresa, usuario=None):
    permitidas = empresas_permitidas_usuario(usuario)
    if not permitidas:
        return True
    return (nome_empresa or "") in permitidas

def filtrar_registros_por_empresa(registros, *campos):
    permitidas = set(empresas_permitidas_usuario())
    if not permitidas:
        return registros
    filtrados = []
    for registro in registros:
        item = dict(registro)
        if any((item.get(campo) or "") in permitidas for campo in campos):
            filtrados.append(registro)
    return filtrados

def buscar_clientes(aplicar_permissao=True):
    dados = repo_listar_clientes(conectar_banco)
    if aplicar_permissao:
        dados = filtrar_registros_por_empresa(dados, "nome")
    return dados

def buscar_cliente_por_nome(nome, aplicar_permissao=True):
    nome = (nome or "").strip()
    if not nome:
        return None
    if aplicar_permissao:
        for cliente in buscar_clientes(aplicar_permissao=True):
            if (cliente.get("nome") or "").strip().lower() == nome.lower():
                return dict(cliente)
        return None
    return repo_buscar_cliente_por_nome(conectar_banco, nome)

def config_sistema_val(chave, padrao=""):
    try:
        conn = conectar_banco()
        c = conn.cursor()
        c.execute("SELECT valor FROM configuracoes_sistema WHERE chave=%s LIMIT 1", (chave,))
        row = c.fetchone()
        conn.close()
        if row and row.get("valor") not in (None, ""):
            return row.get("valor")
    except Exception:
        pass
    return config_val(chave, padrao)

def salvar_config_sistema(chave, valor, descricao=""):
    conn = conectar_banco()
    c = conn.cursor()
    c.execute(
        """INSERT INTO configuracoes_sistema (chave, valor, descricao, atualizado_por, atualizado_em)
           VALUES (%s,%s,%s,%s,NOW())
           ON DUPLICATE KEY UPDATE valor=VALUES(valor), descricao=VALUES(descricao),
           atualizado_por=VALUES(atualizado_por), atualizado_em=NOW()""",
        (chave, str(valor or ""), descricao, st.session_state.get("username", "")),
    )
    conn.commit()
    conn.close()

def registrar_tentativa_login(usuario, tipo, sucesso, mensagem=""):
    try:
        ip = ""
        try:
            ip = st.context.ip_address or ""
        except Exception:
            pass
        conn = conectar_banco()
        c = conn.cursor()
        c.execute(
            """INSERT INTO tentativas_login (usuario, tipo, sucesso, ip, mensagem)
               VALUES (%s,%s,%s,%s,%s)""",
            ((usuario or "").strip(), tipo, 1 if sucesso else 0, ip, mensagem),
        )
        conn.commit()
        conn.close()
    except Exception as ex:
        registrar_log_tecnico("ERROR", "login", "Falha ao registrar tentativa de login", {"erro": str(ex)})

def eh_chefe_chamados(usuario=None):
    usuario = usuario or st.session_state
    return (valor_usuario(usuario, "username", "") or "").strip().lower() == "daniel.fabio"

def eh_admin_master(usuario=None):
    usuario = usuario or st.session_state
    return bool(valor_usuario(usuario, "is_admin", 0)) and (valor_usuario(usuario, "username", "") or "").strip().lower() == "daniel.fabio"

def upload_dentro_limite(arquivo, limite=MAX_UPLOAD_BANCO_BYTES):
    if arquivo is None:
        return True
    try:
        tamanho = int(getattr(arquivo, "size", 0) or 0)
    except Exception:
        tamanho = 0
    if not tamanho:
        pos = arquivo.tell()
        arquivo.seek(0, 2)
        tamanho = arquivo.tell()
        arquivo.seek(pos)
    return tamanho <= limite

def erro_upload_grande(nome="arquivo"):
    st.error(
        f"O {nome} é maior que {tamanho_arquivo_legivel(MAX_UPLOAD_BANCO_BYTES)}. "
        "Envie um arquivo menor para salvar no banco de dados."
    )

def erro_pacote_mysql():
    st.error(
        "O MySQL recusou o arquivo porque o limite max_allowed_packet está baixo. "
        "Aumente esse limite no MySQL/XAMPP e reinicie o banco para salvar arquivos maiores."
    )

def dados_upload(arquivo):
    if not arquivo:
        return None, "", ""
    return arquivo.getvalue(), arquivo.name, arquivo.type or "application/octet-stream"

def nome_arquivo_seguro(nome):
    nome = os.path.basename(nome or "arquivo")
    nome = re.sub(r"[^A-Za-z0-9._ -]+", "_", nome).strip(" .")
    return nome or "arquivo"

def salvar_upload_dsystem(arquivo):
    DSYSTEM_STATIC_DIR.mkdir(parents=True, exist_ok=True)
    nome_original = arquivo.name or "arquivo"
    nome_salvo = f"{uuid.uuid4().hex}_{nome_arquivo_seguro(nome_original)}"
    caminho = DSYSTEM_STATIC_DIR / nome_salvo
    try:
        arquivo.seek(0)
    except Exception:
        pass
    with open(caminho, "wb") as destino:
        while True:
            bloco = arquivo.read(1024 * 1024)
            if not bloco:
                break
            destino.write(bloco)
    tamanho = caminho.stat().st_size
    url_relativa = f"app/static/dsystem/{quote(nome_salvo)}"
    return str(caminho), url_relativa, tamanho

def url_download_dsystem(arquivo):
    url_arquivo = arquivo.get("url_arquivo") or ""
    if not url_arquivo:
        return ""
    if APP_BASE_URL:
        return f"{APP_BASE_URL}/{url_arquivo.lstrip('/')}"
    return "/" + url_arquivo.lstrip("/")

def migrar_arquivos_dsystem_static():
    if not DSYSTEM_STATIC_DIR_LEGADA.exists():
        return
    DSYSTEM_STATIC_DIR.mkdir(parents=True, exist_ok=True)
    migrados = []
    for caminho_antigo in DSYSTEM_STATIC_DIR_LEGADA.iterdir():
        if not caminho_antigo.is_file():
            continue
        caminho_novo = DSYSTEM_STATIC_DIR / caminho_antigo.name
        if not caminho_novo.exists():
            caminho_antigo.replace(caminho_novo)
        else:
            caminho_antigo.unlink()
        migrados.append((str(caminho_novo), str(caminho_antigo)))
    if migrados:
        conn = conectar_banco()
        c = conn.cursor()
        for caminho_novo, caminho_antigo in migrados:
            c.execute(
                "UPDATE dsystem_arquivos SET caminho_arquivo=? WHERE caminho_arquivo=?",
                (caminho_novo, caminho_antigo),
            )
        conn.commit()
        conn.close()

def logo_dsystem_html(larg="150"):
    return carrega_logo("logo_dsystem.png", "D-System", "#004488", larg)

def exibir_logo_dsystem(larg="170"):
    st.markdown(
        f'<div style="text-align:center; margin:8px 0 18px;">{logo_dsystem_html(larg)}</div>',
        unsafe_allow_html=True,
    )

def listar_funcionarios_sistema():
    conn = conectar_banco()
    c = conn.cursor()
    c.execute("SELECT username, funcionario_nome FROM usuarios ORDER BY username")
    funcionarios = []
    for row in c.fetchall():
        username = row.get("username") or ""
        nome = row.get("funcionario_nome") or ""
        if username:
            funcionarios.append({"username": username, "nome": nome, "label": f"{nome} ({username})" if nome else username})
    conn.close()
    return funcionarios

def texto_data_br(data_iso):
    return data_para_br(data_iso)

def linhas_faturamento_export(rows, item_filtro="Todos"):
    linhas = []
    for row in rows:
        reg = dict(row)
        itens = itens_faturamento_lista(reg.get("itens"))
        if not itens:
            itens = [{"desc": "", "qtd": 0, "vunit": 0.0, "vtotal": float(reg.get("valor_total") or 0)}]
        for idx, item in enumerate(itens, start=1):
            if item_filtro != "Todos" and item.get("desc") != item_filtro:
                continue
            linhas.append({
                "ID Faturamento": reg.get("id"),
                "Data Lançamento": data_para_br(reg.get("data_lanc")),
                "Cliente": reg.get("cliente") or "",
                "CNPJ": reg.get("cnpj") or "",
                "Tipo": reg.get("tipo") or "",
                "Status": reg.get("status") or "Aberto",
                "Emite NF": reg.get("emite_nf") or "",
                "Tipo Nota": reg.get("tipo_nota") or "",
                "Forma Pagamento": reg.get("forma_pag") or "",
                "Parcelas": reg.get("parcelas") or "",
                "Vencimento": data_para_br(reg.get("vencimento")),
                "Orçamento Ref.": reg.get("orc_ref") or "",
                "Item": idx,
                "Tipo Item": item.get("tipo_item") or "Serviço",
                "Descrição Item": item.get("desc") or "",
                "Qtd": item.get("qtd") or 0,
                "Valor Unitário": float(item.get("vunit") or 0),
                "Valor Total Item": float(item.get("vtotal") or 0),
                "Valor Total Faturamento": float(reg.get("valor_total") or 0),
                "Observação Interna": reg.get("obs_interna") or "",
                "Informações Nota": reg.get("obs_nota") or "",
            })
    return linhas

def gerar_excel_faturamentos_registrados(rows, titulo="Faturamentos", item_filtro="Todos"):
    wb = Workbook()
    ws = wb.active
    ws.title = "Faturamentos"
    linhas = linhas_faturamento_export(rows, item_filtro=item_filtro)
    colunas = list(linhas[0].keys()) if linhas else [
        "ID Faturamento", "Data Lançamento", "Cliente", "CNPJ", "Tipo", "Status",
        "Emite NF", "Tipo Nota", "Forma Pagamento", "Parcelas", "Vencimento",
        "Orçamento Ref.", "Item", "Descrição Item", "Qtd", "Valor Unitário",
        "Valor Total Item", "Valor Total Faturamento", "Observação Interna", "Informações Nota"
    ]
    ws.append(colunas)
    for linha in linhas:
        ws.append([linha.get(col, "") for col in colunas])
    header_fill = PatternFill("solid", fgColor="004488")
    header_font = Font(bold=True, color="FFFFFF")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    moeda_cols = {"Valor Unitário", "Valor Total Item", "Valor Total Faturamento"}
    for col_idx, titulo_col in enumerate(colunas, start=1):
        largura = min(max(len(titulo_col) + 4, 12), 45)
        for cell in ws.iter_cols(min_col=col_idx, max_col=col_idx, min_row=2, values_only=False):
            for ccell in cell:
                largura = min(max(largura, len(str(ccell.value or "")) + 2), 55)
                if titulo_col in moeda_cols:
                    ccell.number_format = 'R$ #,##0.00'
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = largura
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    resumo = wb.create_sheet("Resumo")
    resumo.append([titulo])
    resumo.append(["Total de linhas", len(linhas)])
    resumo.append(["Total faturado nos itens", sum(float(l.get("Valor Total Item") or 0) for l in linhas)])
    resumo["A1"].font = Font(bold=True, size=14)
    resumo["B3"].number_format = 'R$ #,##0.00'
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()

def opcoes_clientes_para_puxar():
    clientes = buscar_clientes()
    return clientes, ["-- Manter cliente atual --"] + [c.get("nome") or "" for c in clientes]

def buscar_emails_para_empresa(cliente_nome, fantasia="", razao="", email_principal=""):
    nomes_busca = [n for n in {cliente_nome, fantasia, razao} if n and n != "-- Avulso --"]
    dominio_email = ""
    if email_principal and "@" in str(email_principal):
        dominio_email = str(email_principal).split("@", 1)[1].strip().lower()
    conn = conectar_banco()
    c = conn.cursor(dictionary=True)
    emails = []
    ids = set()
    for nome_busca in nomes_busca:
        c.execute(
            """SELECT id, cliente_vinculado, funcionario, email, aliases, provedor, config_entrada, config_saida, capacidade
               FROM emails_clientes
               WHERE cliente_vinculado=?
               ORDER BY id DESC""",
            (nome_busca,),
        )
        for row in c.fetchall():
            if row.get("id") not in ids:
                ids.add(row.get("id"))
                emails.append(row)
    if dominio_email:
        c.execute(
            """SELECT id, cliente_vinculado, funcionario, email, aliases, provedor, config_entrada, config_saida, capacidade
               FROM emails_clientes
               WHERE LOWER(email) LIKE ? OR LOWER(aliases) LIKE ?
               ORDER BY id DESC""",
            (f"%@{dominio_email}", f"%@{dominio_email}%"),
        )
        for row in c.fetchall():
            if row.get("id") not in ids:
                ids.add(row.get("id"))
                emails.append(row)
    conn.close()
    return emails

def texto_lista_infra(valor, separador="||"):
    return "\n".join([p.strip() for p in str(valor or "").split(separador) if p.strip()])

def lista_texto_infra(valor, separador="||"):
    return separador.join([p.strip() for p in str(valor or "").splitlines() if p.strip()])

def renderizar_conta_financeira(tipo):
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
    abas_fin = st.tabs(nomes_abas)
    aba_dash, aba1, aba2, aba_rec = abas_fin[:4]
    aba_cobranca = abas_fin[4] if not eh_pagar else None

    clientes = buscar_clientes()
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
        st.markdown("#### Fluxo por vencimento")
        fluxo = {}
        for registro_fluxo in abertos:
            venc_fluxo = data_para_br(registro_fluxo.get("data_vencimento")) or "Sem vencimento"
            fluxo[venc_fluxo] = fluxo.get(venc_fluxo, 0) + float(registro_fluxo.get("valor_total") or 0)
        if fluxo:
            st.dataframe([{"Vencimento": k, "Valor previsto": formatar_moeda_br(v)} for k, v in fluxo.items()], width="stretch", hide_index=True)
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
            conta_bancaria = r1.text_input("Conta bancária:")
            data_emissao = r2.date_input("Data de emissão:", value=date.today())
            data_competencia = r3.date_input("Data de competência:", value=date.today())
            data_vencimento = r4.date_input("Data de vencimento:", value=date.today())

            v1, v2, v3, v4, v5 = st.columns(5)
            valor_original = v1.number_input("Valor original R$:", min_value=0.0, step=0.01, format="%.2f")
            desconto = v2.number_input("Desconto R$:", min_value=0.0, step=0.01, format="%.2f")
            juros = v3.number_input("Juros R$:", min_value=0.0, step=0.01, format="%.2f")
            multa = v4.number_input("Multa R$:", min_value=0.0, step=0.01, format="%.2f")
            valor_total = max(0.0, valor_original - desconto + juros + multa)
            v5.metric("Valor total", formatar_moeda_br(valor_total))

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
                if not parte_valida or valor_total <= 0:
                    st.error(f"Informe {parte_label.lower()} e um valor maior que zero.")
                else:
                    if anexo_lancamento and not upload_dentro_limite(anexo_lancamento):
                        erro_upload_grande("anexo")
                        st.stop()
                    anexo_dados, anexo_nome, anexo_mime = dados_upload(anexo_lancamento)
                    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
                    usuario = st.session_state.get("username", "")
                    conn = conectar_banco()
                    c = conn.cursor()
                    if eh_pagar:
                        c.execute("""INSERT INTO contas_pagar
                            (fornecedor, cpf_cnpj, numero_documento, tipo_documento, categoria, centro_custo,
                             plano_contas, conta_bancaria, data_emissao, data_competencia, data_vencimento,
                             valor_original, desconto, juros, multa, valor_total, forma_pagamento,
                             codigo_barras, chave_pix, status, observacoes, criado_por, criado_em,
                             anexo_nome, anexo_mime, anexo, solicitante, status_aprovacao)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (parte, cpf_cnpj, numero_documento, tipo_doc, categoria, centro, plano, conta_bancaria,
                             data_para_banco_br(data_emissao), data_para_banco_br(data_competencia), data_para_banco_br(data_vencimento),
                             valor_original, desconto, juros, multa, valor_total, forma, extra1, extra2, status, observacoes,
                             usuario, agora, anexo_nome, anexo_mime, anexo_dados, usuario, "Pendente"))
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
                             lucro_estimado, margem_lucro_percentual)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (parte_id, parte, cpf_cnpj, numero_documento, tipo_doc, categoria, centro, plano, conta_bancaria,
                             data_para_banco_br(data_emissao), data_para_banco_br(data_competencia), data_para_banco_br(data_vencimento),
                             valor_original, desconto, juros, multa, valor_total, forma, extra1, extra2, status, observacoes,
                              usuario, agora, anexo_nome, anexo_mime, anexo_dados, regime_tributario,
                              impostos_json, simples_aliquota, simples_valor, taxas_personalizadas_json,
                              valor_impostos, valor_liquido, parcelado_txt, int(quantidade_parcelas),
                              meio_parcelamento, parcelas_json, bandeira_cartao, custo_tipo, pedido_compra_id,
                              fornecedor_custo, custo_unitario, quantidade_custo, custo_total,
                              lucro_estimado, margem_lucro_percentual))
                    conn.commit()
                    conn.close()
                    st.success("Lançamento salvo.")
                    st.rerun()

    with aba2:
        f1, f2, f3 = st.columns(3)
        filtro_status = f1.selectbox("Filtrar por status:", ["Todos"] + status_opcoes, key=f"{tabela}_status")
        busca = f2.text_input(f"Buscar {parte_label.lower()}/documento:", key=f"{tabela}_busca")
        filtro_vencimento = f3.date_input("Vencimento até:", value=None, key=f"{tabela}_venc")

        conn = conectar_banco()
        c = conn.cursor()
        c.execute(f"SELECT * FROM {tabela} ORDER BY id DESC")
        registros = [dict(r) for r in c.fetchall()]
        conn.close()
        campo_parte = "fornecedor" if eh_pagar else "cliente"
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
            } if not eh_pagar else {}),
            "Status": r.get("status"), "Baixado": formatar_moeda_br(r.get("valor_baixado")),
        } for r in registros]
        id_financeiro_selecionado = None
        if resumo:
            id_financeiro_selecionado = tabela_selecionavel_id(st, resumo, f"{tabela}_grade_consulta", "ID")
            st.caption("Clique no lançamento para abrir automaticamente a consulta/edição e baixa.")
        else:
            st.info("Nenhum lançamento encontrado.")

        if registros and tem_permissao(f"{permissao}.edit"):
            st.write("---")
            id_baixa = st.number_input("ID para baixar/alterar:", min_value=1, step=1, value=int(id_financeiro_selecionado or 1), key=f"{tabela}_id_baixa_{id_financeiro_selecionado or 'manual'}")
            registro = next((r for r in registros if int(r.get("id") or 0) == int(id_baixa)), None)
            if registro:
                if registro.get("anexo"):
                    st.download_button(
                        f"Baixar anexo: {registro.get('anexo_nome') or 'arquivo'}",
                        data=registro.get("anexo"),
                        file_name=registro.get("anexo_nome") or "anexo",
                        mime=registro.get("anexo_mime") or "application/octet-stream",
                        key=f"{tabela}_baixar_anexo_{id_baixa}",
                    )
                if eh_pagar:
                    st.markdown("**Aprovação do pagamento**")
                    ap1, ap2 = st.columns(2)
                    status_aprovacao = ap1.selectbox("Status da aprovação:", ["Pendente", "Aprovado", "Reprovado"], index=["Pendente", "Aprovado", "Reprovado"].index(registro.get("status_aprovacao") or "Pendente"), key=f"{tabela}_aprovacao")
                    motivo_reprovacao = ap2.text_input("Motivo da reprovação:", value=registro.get("motivo_reprovacao") or "", key=f"{tabela}_motivo_reprovacao")
                    if st.button("Registrar aprovação", key=f"{tabela}_registrar_aprovacao"):
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
                data_baixa = b1.date_input("Data da baixa:", value=date.today(), key=f"{tabela}_data_baixa")
                valor_baixa = b2.number_input("Valor baixado R$:", min_value=0.0, value=float(registro.get("valor_total") or 0), step=0.01, format="%.2f", key=f"{tabela}_valor_baixa")
                novo_status = b3.selectbox("Novo status:", status_opcoes, index=status_opcoes.index(status_baixa), key=f"{tabela}_novo_status")
                bb1, bb2, bb3, bb4 = st.columns(4)
                conta_baixa = bb1.text_input("Conta bancária da baixa:", value=registro.get("conta_baixa") or registro.get("conta_bancaria") or "", key=f"{tabela}_conta_baixa")
                forma_baixa = bb2.text_input("Forma da baixa:", value=registro.get("forma_baixa") or registro.get("forma_pagamento") or registro.get("forma_recebimento") or "", key=f"{tabela}_forma_baixa")
                taxas_baixa = bb3.number_input("Taxas R$:", min_value=0.0, value=float(registro.get("taxas_baixa") or 0), step=0.01, key=f"{tabela}_taxas_baixa")
                juros_baixa = bb4.number_input("Juros da baixa R$:", min_value=0.0, value=float(registro.get("juros_baixa") or 0), step=0.01, key=f"{tabela}_juros_baixa")
                bc1, bc2 = st.columns(2)
                desconto_baixa = bc1.number_input("Desconto da baixa R$:", min_value=0.0, value=float(registro.get("desconto_baixa") or 0), step=0.01, key=f"{tabela}_desconto_baixa")
                observacao_baixa = bc2.text_input("Observação da baixa:", value=registro.get("observacao_baixa") or "", key=f"{tabela}_obs_baixa")
                comprovante_baixa = st.file_uploader("Comprovante da baixa:", key=f"{tabela}_comprovante_baixa")
                if st.button("Registrar baixa/alteração", type="primary", key=f"{tabela}_baixar"):
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

        if registros and tem_permissao(f"{permissao}.delete"):
            with st.expander("Excluir lançamento"):
                id_excluir = st.number_input("ID para excluir:", min_value=1, step=1, key=f"{tabela}_id_excluir")
                if st.button("Excluir permanentemente", key=f"{tabela}_excluir"):
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
            vencidas_cob = [r for r in contas_cob if parse_data_flex(r.get("data_vencimento")) and parse_data_flex(r.get("data_vencimento")) < date.today() and r.get("status") not in ("Recebido", "Cancelado", "Baixado por perda")]
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
                ren_valor_original = float(ren_titulo.get("valor_total") or 0) if ren_titulo else 0.0
                ren_valor = ren2.number_input("Valor renegociado R$:", min_value=0.0, value=ren_valor_original, step=0.01, key="ren_valor")
                ren_entrada = ren3.number_input("Entrada R$:", min_value=0.0, step=0.01, key="ren_entrada")
                ren4, ren5, ren6 = st.columns(3)
                ren_parcelas = ren4.number_input("Parcelas:", min_value=1, value=1, step=1, key="ren_parcelas")
                ren_primeiro_venc = ren5.date_input("Primeiro vencimento:", value=date.today(), key="ren_primeiro_venc")
                ren_status = ren6.selectbox("Status:", ["Ativo", "Quitado", "Cancelado"], key="ren_status")
                ren_obs = st.text_area("Observações da negociação:", key="ren_obs")
                if st.button("Salvar renegociação", type="primary", key="salvar_renegociacao"):
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

def obter_query_param(nome, padrao=""):
    try:
        valor = st.query_params.get(nome, padrao)
    except Exception:
        try:
            valores = st.experimental_get_query_params().get(nome, [padrao])
            valor = valores[0] if valores else padrao
        except Exception:
            valor = padrao
    if isinstance(valor, list):
        return valor[0] if valor else padrao
    return valor or padrao

def telefone_whatsapp(numero):
    return normalizar_telefone_whatsapp(numero)

def url_whatsapp(numero, mensagem):
    return criar_url_whatsapp(numero, mensagem)

def whatsapp_oficial_url(mensagem):
    return url_whatsapp(WHATSAPP_API_NUMERO or WHATSAPP_OFICIAL, mensagem)

def url_base_app():
    base_url = APP_BASE_URL
    if not base_url:
        try:
            partes = urlsplit(st.context.url)
            base_url = urlunsplit((partes.scheme, partes.netloc, partes.path, "", ""))
        except Exception:
            base_url = "http://localhost:8501"
    return base_url.rstrip("/")

def url_portal_chamado(chamado_id=None):
    parametros = {"pagina": "portal"}
    if chamado_id:
        parametros["chamado"] = chamado_id
    query = urlencode(parametros)
    return f"{url_base_app()}?{query}"

def url_abrir_chamado():
    return f"{url_base_app()}?{urlencode({'pagina': 'portal', 'acao': 'abrir_chamado'})}"

def url_mailto(destinatario, assunto, corpo):
    email = quote((destinatario or "").strip(), safe="@._+-")
    return f"mailto:{email}?subject={quote(assunto)}&body={quote(corpo)}"

def url_gmail(destinatario, assunto, corpo):
    return (
        "https://mail.google.com/mail/?view=cm&fs=1"
        f"&to={quote((destinatario or '').strip(), safe='@._+-')}"
        f"&su={quote(assunto)}"
        f"&body={quote(corpo)}"
    )

def buscar_contato_cliente(cliente_id=None, cliente_nome=""):
    conn = conectar_banco()
    c = conn.cursor()
    if cliente_id:
        c.execute("SELECT nome, telefone, email, portal_username FROM clientes WHERE id=%s LIMIT 1", (cliente_id,))
    else:
        c.execute("SELECT nome, telefone, email, portal_username FROM clientes WHERE nome=%s LIMIT 1", (cliente_nome,))
    contato = c.fetchone()
    conn.close()
    return contato or {}

def texto_retorno_chamado(chamado, mensagem=""):
    data_ch, inicio_ch, fim_ch, tipo_ch, _ = periodo_chamado(chamado)
    link = url_portal_chamado(chamado.get("id"))
    corpo = mensagem.strip() or "Temos uma atualização sobre o seu chamado."
    return (
        f"Olá, {chamado.get('cliente_nome') or 'cliente'}.\n\n"
        f"{corpo}\n\n"
        f"Chamado #{chamado.get('id')} - {chamado.get('titulo') or 'Sem assunto'}\n"
        f"Área: {chamado.get('area_destino') or 'Suporte'}\n"
        f"Status: {chamado.get('status') or 'Novo'}\n"
        f"Atendimento: {tipo_ch} em {texto_data_br(data_ch)} das {inicio_ch} às {fim_ch}\n\n"
        f"Acesse o portal para acompanhar ou responder:\n{link}"
    )

def texto_cliente_abrir_chamado():
    return (
        "Olá! Para abrir um chamado, acesse o portal pelo link abaixo, faça login e preencha as informações do atendimento:\n\n"
        f"{url_abrir_chamado()}\n\n"
        f"Nosso WhatsApp oficial para atendimento é {WHATSAPP_OFICIAL}."
    )

def periodo_chamado(chamado):
    data = chamado.get("ajuste_data") or chamado.get("data_solicitada") or ""
    inicio = chamado.get("ajuste_hora_inicio") or chamado.get("hora_inicio") or ""
    fim = chamado.get("ajuste_hora_fim") or chamado.get("hora_fim") or ""
    tipo = chamado.get("ajuste_tipo_atendimento") or chamado.get("tipo_atendimento") or ""
    descricao = chamado.get("ajuste_descricao") or chamado.get("descricao") or ""
    return data, inicio, fim, tipo, descricao

def horarios_sobrepoem(inicio_a, fim_a, inicio_b, fim_b):
    if not all([inicio_a, fim_a, inicio_b, fim_b]):
        return False
    return inicio_a < fim_b and fim_a > inicio_b

def conflito_agenda_funcionario(funcionario, data_visita, hora_inicio, hora_fim, chamado_ignorar=None):
    if not funcionario or not data_visita or not hora_inicio or not hora_fim:
        return None
    conn = conectar_banco()
    c = conn.cursor()
    c.execute(
        """SELECT id, cliente_nome, hora_inicio, hora_fim, status
           FROM agenda_visitas
           WHERE tecnico=%s AND data_visita=%s AND status NOT IN ('Cancelado', 'Concluído', 'Realizado')""",
        (funcionario, data_visita),
    )
    for visita in c.fetchall():
        if horarios_sobrepoem(hora_inicio, hora_fim, visita.get("hora_inicio") or "", visita.get("hora_fim") or ""):
            conn.close()
            return f"Conflito com visita #{visita['id']} ({visita.get('cliente_nome') or 'cliente sem nome'}) das {visita.get('hora_inicio')} às {visita.get('hora_fim')}."

    c.execute(
        """SELECT * FROM chamados_cliente
           WHERE funcionario_designado=%s
             AND status NOT IN ('Concluído', 'Cancelado', 'Recusado pelo cliente')""",
        (funcionario,),
    )
    for chamado in c.fetchall():
        if chamado_ignorar and chamado.get("id") == chamado_ignorar:
            continue
        data_ch, inicio_ch, fim_ch, _, _ = periodo_chamado(chamado)
        if data_ch == data_visita and horarios_sobrepoem(hora_inicio, hora_fim, inicio_ch, fim_ch):
            conn.close()
            return f"Conflito com chamado #{chamado['id']} ({chamado.get('cliente_nome') or 'cliente sem nome'}) das {inicio_ch} às {fim_ch}."
    conn.close()
    return None

def salvar_mensagem_chamado(chamado_id, autor_tipo, autor_nome, mensagem, anexo_upload=None):
    anexo_dados, anexo_nome, anexo_mime = dados_upload(anexo_upload)
    conn = conectar_banco()
    c = conn.cursor()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute(
        """INSERT INTO chamados_mensagens
           (chamado_id, autor_tipo, autor_nome, mensagem, anexo_nome, anexo_mime, anexo, criado_em)
           VALUES (?,?,?,?,?,?,?,?)""",
        (chamado_id, autor_tipo, autor_nome, mensagem, anexo_nome, anexo_mime, anexo_dados, agora),
    )
    c.execute("UPDATE chamados_cliente SET atualizado_em=? WHERE id=?", (agora, chamado_id))
    conn.commit()
    conn.close()

def mensagens_chamado(chamado_id):
    conn = conectar_banco()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM chamados_mensagens WHERE chamado_id=%s ORDER BY id ASC", (chamado_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def renderizar_chat_chamado(chamado, cliente_portal):
    mensagens = mensagens_chamado(chamado.get("id"))
    if not mensagens:
        mensagens = [{
            "id": f"desc_{chamado.get('id')}",
            "autor_tipo": "cliente",
            "autor_nome": chamado.get("solicitante") or cliente_portal,
            "mensagem": chamado.get("descricao") or "",
            "criado_em": chamado.get("criado_em") or "",
        }]

    for msg in mensagens:
        autor_tipo = (msg.get("autor_tipo") or "").lower()
        classe = "chat-bubble cliente" if autor_tipo == "cliente" else "chat-bubble equipe"
        nome = h(msg.get("autor_nome") or ("Cliente" if autor_tipo == "cliente" else "Equipe Dsystem"))
        data_msg = h(msg.get("criado_em") or "")
        texto = h(msg.get("mensagem") or "").replace("\n", "<br>")
        st.markdown(
            f"""
<div class="{classe}">
  <div class="chat-meta">{nome} | {data_msg}</div>
  <div class="chat-text">{texto}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if msg.get("anexo"):
            st.download_button(
                f"Baixar anexo: {msg.get('anexo_nome') or 'arquivo'}",
                data=msg.get("anexo"),
                file_name=msg.get("anexo_nome") or "anexo",
                mime=msg.get("anexo_mime") or "application/octet-stream",
                key=f"baixar_anexo_chamado_msg_{msg.get('id')}",
            )

def renderizar_abertura_chamado(cliente_portal, cliente_id=None):
    st.subheader("Abrir chamado")
    if st.session_state.get("acao_portal") == "abrir_chamado":
        st.info("Preencha as informações abaixo para registrar seu chamado.")
    st.write("Solicite um atendimento remoto ou presencial informando a data, o horário e o que precisa ser feito.")
    msg_whats = f"Olá, sou {cliente_portal or 'cliente'} e quero abrir um chamado pelo portal."
    st.link_button("Falar pelo WhatsApp oficial", whatsapp_oficial_url(msg_whats), width="stretch")
    with st.form("form_novo_chamado_cliente"):
        c0, c1, c2 = st.columns(3)
        area_destino = c0.selectbox("Com quem deseja falar:", AREAS_CHAMADO)
        solicitante = c1.text_input("Solicitante:", value=st.session_state.get("username", ""))
        tipo = c2.selectbox("Tipo de atendimento:", ["Remoto", "Presencial", "Presencial ou remoto"])
        d1, d2, d3 = st.columns(3)
        data_solicitada = d1.date_input("Data desejada:", value=date.today(), min_value=date.today())
        hora_inicio = d2.time_input("Hora de início:", value=None, step=1800)
        hora_fim = d3.time_input("Hora de término:", value=None, step=1800)
        titulo = st.text_input("Assunto:")
        descricao = st.text_area("Informações do que precisa:", height=130)
        enviar = st.form_submit_button("Enviar chamado para Daniel.fabio", type="primary", width="stretch")

    if enviar:
        erros = []
        if not cliente_portal:
            erros.append("Cliente não identificado para abrir o chamado.")
        if not titulo.strip():
            erros.append("Informe o assunto do chamado.")
        if not descricao.strip():
            erros.append("Descreva o que precisa ser feito.")
        if not hora_inicio or not hora_fim:
            erros.append("Informe o horário de início e término.")
        elif hora_fim <= hora_inicio:
            erros.append("A hora de término precisa ser maior que a hora de início.")
        if erros:
            for erro in erros:
                st.error(erro)
            return

        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        conn = conectar_banco()
        c = conn.cursor()
        funcionario_inicial = responsavel_area_chamado(area_destino)
        c.execute(
            """INSERT INTO chamados_cliente
               (cliente_id, cliente_nome, solicitante, area_destino, tipo_atendimento, data_solicitada,
                hora_inicio, hora_fim, titulo, descricao, status, administrador,
                funcionario_designado, criado_por, criado_em, atualizado_em)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cliente_id,
                cliente_portal,
                solicitante,
                area_destino,
                tipo,
                data_solicitada.strftime("%Y-%m-%d"),
                hora_inicio.strftime("%H:%M"),
                hora_fim.strftime("%H:%M"),
                titulo,
                descricao,
                "Novo",
                "Daniel.fabio",
                funcionario_inicial,
                st.session_state.get("username", ""),
                agora,
                agora,
            ),
        )
        chamado_id_novo = c.lastrowid
        c.execute(
            """INSERT INTO chamados_mensagens
               (chamado_id, autor_tipo, autor_nome, mensagem, criado_em)
               VALUES (?,?,?,?,?)""",
            (chamado_id_novo, "cliente", solicitante or cliente_portal, descricao, agora),
        )
        conn.commit()
        conn.close()
        destino = "Daniel.fabio" if funcionario_inicial else "fila de suporte"
        st.success(f"Chamado enviado para {area_destino} ({destino}).")
        st.rerun()

def renderizar_chamados_cliente(cliente_portal):
    st.subheader("Meus chamados")
    conn = conectar_banco()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM chamados_cliente WHERE cliente_nome=%s ORDER BY id DESC", (cliente_portal,))
    chamados = c.fetchall()
    conn.close()

    if not chamados:
        st.info("Nenhum chamado aberto para este cliente.")
        return

    filtro_status = st.selectbox(
        "Filtrar chamados:",
        ["Todos", "Abertos", "Aguardando cliente", "Concluídos"],
        key="portal_chamados_filtro_status",
    )
    if filtro_status == "Abertos":
        chamados = [c for c in chamados if (c.get("status") or "Novo") not in ("Concluído", "Concluido", "Cancelado")]
    elif filtro_status == "Aguardando cliente":
        chamados = [c for c in chamados if "aguardando" in (c.get("status") or "").lower()]
    elif filtro_status == "Concluídos":
        chamados = [c for c in chamados if (c.get("status") or "") in ("Concluído", "Concluido")]

    if not chamados:
        st.info("Nenhum chamado encontrado neste filtro.")
        return

    opcoes = [f"#{c.get('id')} - {c.get('titulo') or 'Sem assunto'}" for c in chamados]
    destaque = str(st.session_state.get("chamado_destacado") or "")
    idx_padrao = next((i for i, c in enumerate(chamados) if str(c.get("id")) == destaque), 0)
    escolha = st.selectbox("Selecione um chamado para conversar:", opcoes, index=idx_padrao, key="portal_chamado_chat_sel")
    chamado = chamados[opcoes.index(escolha)]

    data_ch, inicio_ch, fim_ch, tipo_ch, descricao_ch = periodo_chamado(chamado)
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Chamado", f"#{chamado.get('id')}")
    r2.metric("Status", chamado.get("status") or "Novo")
    r3.metric("Área", chamado.get("area_destino") or "Suporte")
    r4.metric("Responsável", chamado.get("funcionario_designado") or "Fila")

    st.markdown(f"#### {chamado.get('titulo') or 'Sem assunto'}")
    st.caption(f"{tipo_ch or 'Atendimento'} em {texto_data_br(data_ch)} das {inicio_ch or '--:--'} às {fim_ch or '--:--'}")

    if chamado.get("ajuste_descricao") or chamado.get("ajuste_data"):
        st.info("Daniel.fabio sugeriu alterações para este pedido. Confira e aprove ou recuse abaixo.")

    renderizar_chat_chamado(chamado, cliente_portal)

    st.markdown("#### Responder chamado")
    with st.form(f"form_responder_chamado_{chamado.get('id')}", clear_on_submit=True):
        resposta = st.text_area("Mensagem:", height=110, key=f"chat_resp_{chamado.get('id')}")
        anexo = st.file_uploader("Anexo opcional:", key=f"chat_anexo_{chamado.get('id')}")
        enviar = st.form_submit_button("Enviar mensagem", type="primary", width="stretch")
    if enviar:
        if not resposta.strip() and not anexo:
            st.error("Digite uma mensagem ou anexe um arquivo.")
        elif anexo and not upload_dentro_limite(anexo):
            erro_upload_grande("anexo")
        else:
            salvar_mensagem_chamado(
                chamado.get("id"),
                "cliente" if st.session_state.get("tipo_login") == "cliente" else "equipe",
                st.session_state.get("username") or cliente_portal,
                resposta.strip(),
                anexo,
            )
            st.success("Mensagem enviada.")
            st.rerun()

    if chamado.get("status") == "Modificado - aguardando aprovação":
        st.markdown("#### Aprovação de alterações")
        resposta_decisao = st.text_area("Observação sobre a decisão:", key=f"resp_cli_ch_{chamado['id']}")
        b1, b2 = st.columns(2)
        if b1.button("Aprovar alterações", key=f"aprov_ch_{chamado['id']}", width="stretch"):
            conn_ap = conectar_banco()
            cap = conn_ap.cursor()
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            cap.execute(
                "UPDATE chamados_cliente SET status=?, resposta_cliente=?, atualizado_em=? WHERE id=?",
                ("Aprovado pelo cliente", resposta_decisao, agora, chamado["id"]),
            )
            cap.execute(
                "INSERT INTO chamados_mensagens (chamado_id, autor_tipo, autor_nome, mensagem, criado_em) VALUES (?,?,?,?,?)",
                (chamado["id"], "cliente", st.session_state.get("username") or cliente_portal, f"Alterações aprovadas. {resposta_decisao}".strip(), agora),
            )
            conn_ap.commit()
            conn_ap.close()
            st.success("Alterações aprovadas.")
            st.rerun()
        if b2.button("Recusar alterações", key=f"rec_ch_{chamado['id']}", width="stretch"):
            conn_rec = conectar_banco()
            crec = conn_rec.cursor()
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            crec.execute(
                "UPDATE chamados_cliente SET status=?, resposta_cliente=?, atualizado_em=? WHERE id=?",
                ("Recusado pelo cliente", resposta_decisao, agora, chamado["id"]),
            )
            crec.execute(
                "INSERT INTO chamados_mensagens (chamado_id, autor_tipo, autor_nome, mensagem, criado_em) VALUES (?,?,?,?,?)",
                (chamado["id"], "cliente", st.session_state.get("username") or cliente_portal, f"Alterações recusadas. {resposta_decisao}".strip(), agora),
            )
            conn_rec.commit()
            conn_rec.close()
            st.warning("Alterações recusadas.")
            st.rerun()

def renderizar_propostas_contratos(cliente_portal, cliente_id=None):
    st.subheader("Propostas/Contratos")

    if st.session_state.get("tipo_login") != "cliente":
        st.write("Envie propostas ou contratos para o cliente selecionado no portal.")
        with st.form(f"form_envio_proposta_{cliente_id or cliente_portal}"):
            p1, p2 = st.columns(2)
            tipo = p1.selectbox("Tipo:", ["Proposta", "Contrato"])
            titulo = p2.text_input("Título:")
            descricao = st.text_area("Observação para o cliente:", height=90)
            arquivo = st.file_uploader("Arquivo da proposta/contrato:", type=None)
            enviar = st.form_submit_button("Enviar para o cliente", type="primary", width="stretch")

        if enviar:
            if not cliente_portal:
                st.error("Selecione um cliente antes de enviar.")
            elif not titulo.strip():
                st.error("Informe o título.")
            elif arquivo is None:
                st.error("Selecione um arquivo.")
            elif not upload_dentro_limite(arquivo):
                erro_upload_grande("arquivo")
            else:
                conn_env = conectar_banco()
                cenv = conn_env.cursor()
                cenv.execute(
                    """INSERT INTO propostas_contratos_cliente
                       (cliente_id, cliente_nome, tipo, titulo, descricao, nome_arquivo, mime_type,
                        arquivo, status, criado_por, criado_em)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        cliente_id,
                        cliente_portal,
                        tipo,
                        titulo,
                        descricao,
                        arquivo.name,
                        arquivo.type or "application/octet-stream",
                        arquivo.getvalue(),
                        "Pendente",
                        st.session_state.get("username", ""),
                        datetime.now().strftime("%d/%m/%Y %H:%M"),
                    ),
                )
                if tipo == "Contrato":
                    salvar_contrato_gerado(
                        conn_env, tipo=titulo.strip() or "Contrato", parte_tipo="Cliente",
                        parte_id=cliente_id, parte_nome=cliente_portal, nome_arquivo=arquivo.name,
                        arquivo=arquivo.getvalue(), criado_por=st.session_state.get("username", ""),
                        criado_em=datetime.now().strftime("%d/%m/%Y %H:%M"),
                    )
                conn_env.commit()
                conn_env.close()
                st.success("Arquivo enviado para o cliente.")
                st.rerun()

    conn = conectar_banco()
    c = conn.cursor()
    c.execute(
        """SELECT id, tipo, titulo, descricao, nome_arquivo, mime_type, arquivo, status,
                  resposta_cliente, criado_por, criado_em, respondido_em
           FROM propostas_contratos_cliente
           WHERE cliente_nome=%s
           ORDER BY id DESC""",
        (cliente_portal,),
    )
    propostas = c.fetchall()
    conn.close()

    if not propostas:
        st.info("Nenhuma proposta ou contrato enviado para este cliente.")
        return

    if st.session_state.get("tipo_login") != "cliente":
        retornos = [
            p for p in propostas
            if (p.get("resposta_cliente") or "").strip() or p.get("status") == "Contraproposta"
        ]
        if retornos:
            st.write("---")
            st.subheader("Retornos do cliente")
            for proposta in retornos:
                with st.expander(f"#{proposta['id']} - {proposta.get('titulo')} - {proposta.get('status')}", expanded=proposta.get("status") == "Contraproposta"):
                    st.write(f"**Cliente:** {cliente_portal}")
                    st.write(f"**Respondido em:** {proposta.get('respondido_em') or 'Ainda não respondido'}")
                    st.write(f"**Resposta/observação:** {proposta.get('resposta_cliente') or 'Sem observação'}")

        st.write("---")
        st.subheader("Histórico enviado")

    for proposta in propostas:
        titulo_exp = f"#{proposta['id']} - {proposta.get('tipo') or 'Arquivo'} - {proposta.get('titulo') or 'Sem título'}"
        with st.expander(titulo_exp, expanded=st.session_state.get("tipo_login") == "cliente" and proposta.get("status") == "Pendente"):
            st.write(f"**Status:** {proposta.get('status') or 'Pendente'}")
            st.write(f"**Enviado em:** {proposta.get('criado_em') or ''}")
            if proposta.get("descricao"):
                st.write(f"**Observação:** {proposta.get('descricao')}")
            st.download_button(
                "Baixar arquivo",
                data=proposta.get("arquivo") or b"",
                file_name=proposta.get("nome_arquivo") or "arquivo",
                mime=proposta.get("mime_type") or "application/octet-stream",
                width="stretch",
                key=f"down_prop_{proposta['id']}",
            )

            if st.session_state.get("tipo_login") == "cliente":
                if proposta.get("status") == "Pendente":
                    resposta = st.text_area("Observação ou contraproposta:", key=f"resp_prop_{proposta['id']}")
                    b1, b2, b3 = st.columns(3)
                    if b1.button("Aceitar", type="primary", width="stretch", key=f"aceitar_prop_{proposta['id']}"):
                        conn_acc = conectar_banco()
                        cacc = conn_acc.cursor()
                        cacc.execute(
                            "UPDATE propostas_contratos_cliente SET status=?, resposta_cliente=?, respondido_em=? WHERE id=?",
                            ("Aceita", resposta, datetime.now().strftime("%d/%m/%Y %H:%M"), proposta["id"]),
                        )
                        conn_acc.commit()
                        conn_acc.close()
                        st.success("Proposta aceita.")
                        st.rerun()
                    if b2.button("Recusar", width="stretch", key=f"recusar_prop_{proposta['id']}"):
                        conn_rec = conectar_banco()
                        crec = conn_rec.cursor()
                        crec.execute(
                            "UPDATE propostas_contratos_cliente SET status=?, resposta_cliente=?, respondido_em=? WHERE id=?",
                            ("Recusada", resposta, datetime.now().strftime("%d/%m/%Y %H:%M"), proposta["id"]),
                        )
                        conn_rec.commit()
                        conn_rec.close()
                        st.warning("Proposta recusada.")
                        st.rerun()
                    if b3.button("Enviar contraproposta", width="stretch", key=f"contra_prop_{proposta['id']}"):
                        if not resposta.strip():
                            st.error("Escreva a contraproposta antes de enviar.")
                        else:
                            conn_ctr = conectar_banco()
                            cctr = conn_ctr.cursor()
                            cctr.execute(
                                "UPDATE propostas_contratos_cliente SET status=?, resposta_cliente=?, respondido_em=? WHERE id=?",
                                ("Contraproposta", resposta, datetime.now().strftime("%d/%m/%Y %H:%M"), proposta["id"]),
                            )
                            conn_ctr.commit()
                            conn_ctr.close()
                            st.info("Contraproposta enviada.")
                            st.rerun()
                elif proposta.get("resposta_cliente"):
                    st.write(f"**Sua resposta:** {proposta.get('resposta_cliente')}")
            elif proposta.get("resposta_cliente"):
                st.write(f"**Resposta do cliente:** {proposta.get('resposta_cliente')}")

def renderizar_pasta_dsystem():
    if st.session_state.get("tipo_login") == "cliente":
        st.error("Esta pasta é de uso exclusivo da equipe interna da Dsystem.")
        return
    st.subheader("Pasta Dsystem")
    st.write("Arquivos padrão disponíveis para download.")
    st.caption(f"Limite para esta pasta: {tamanho_arquivo_legivel(DSYSTEM_UPLOAD_MAX_BYTES)} por arquivo. Arquivos grandes ficam salvos no disco do servidor.")
    try:
        migrar_arquivos_dsystem_static()
    except Exception as ex:
        st.warning(f"Não foi possível preparar os arquivos antigos para download: {ex}")

    if eh_admin_master():
        with st.expander("Gerenciar arquivos da Pasta Dsystem", expanded=True):
            pasta = st.text_input("Pasta/categoria:", value="Geral")
            arquivos = st.file_uploader("Adicionar arquivos:", accept_multiple_files=True, key="upload_dsystem")
            if st.button("Salvar arquivos", type="primary", width="stretch"):
                if not arquivos:
                    st.error("Selecione pelo menos um arquivo.")
                elif any(not upload_dentro_limite(arquivo, DSYSTEM_UPLOAD_MAX_BYTES) for arquivo in arquivos):
                    st.error(f"Algum arquivo é maior que {tamanho_arquivo_legivel(DSYSTEM_UPLOAD_MAX_BYTES)}.")
                else:
                    conn_up = None
                    try:
                        conn_up = conectar_banco()
                        cup = conn_up.cursor()
                        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
                        for arquivo in arquivos:
                            caminho_arquivo, url_arquivo, tamanho_arquivo = salvar_upload_dsystem(arquivo)
                            cup.execute(
                                """INSERT INTO dsystem_arquivos
                                   (pasta, nome_arquivo, mime_type, tamanho, arquivo, caminho_arquivo, url_arquivo, armazenamento, criado_por, criado_em)
                                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                (
                                    pasta.strip() or "Geral",
                                    arquivo.name,
                                    arquivo.type or "application/octet-stream",
                                    tamanho_arquivo,
                                    None,
                                    caminho_arquivo,
                                    url_arquivo,
                                    "disco",
                                    st.session_state.get("username", ""),
                                    agora,
                                ),
                            )
                        conn_up.commit()
                        st.success("Arquivos salvos na Pasta Dsystem.")
                        st.rerun()
                    except mysql.connector.Error as ex:
                        if getattr(ex, "errno", None) == 1153 or "max_allowed_packet" in str(ex):
                            erro_pacote_mysql()
                        else:
                            st.error(f"Erro ao salvar arquivo: {ex}")
                    finally:
                        if conn_up:
                            conn_up.close()

    conn = conectar_banco()
    c = conn.cursor()
    c.execute("SELECT * FROM dsystem_arquivos ORDER BY pasta ASC, nome_arquivo ASC, id DESC")
    arquivos_salvos = c.fetchall()
    conn.close()

    if not arquivos_salvos:
        st.info("Nenhum arquivo cadastrado na Pasta Dsystem.")
        return

    pastas = sorted({arquivo.get("pasta") or "Geral" for arquivo in arquivos_salvos})
    for pasta in pastas:
        st.markdown(f"**{pasta}**")
        for arquivo in [a for a in arquivos_salvos if (a.get("pasta") or "Geral") == pasta]:
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"{arquivo.get('nome_arquivo') or 'Arquivo'}")
            c2.write(tamanho_arquivo_legivel(arquivo.get("tamanho")))
            if arquivo.get("armazenamento") == "disco" and arquivo.get("url_arquivo"):
                c3.link_button("Baixar", url_download_dsystem(arquivo), width="stretch")
            else:
                c3.download_button(
                    "Baixar",
                    data=arquivo.get("arquivo") or b"",
                    file_name=arquivo.get("nome_arquivo") or "arquivo",
                    mime=arquivo.get("mime_type") or "application/octet-stream",
                    width="stretch",
                    key=f"down_dsystem_{arquivo['id']}",
                )
            if eh_admin_master():
                if st.button("Excluir", key=f"del_dsystem_{arquivo['id']}"):
                    caminho = arquivo.get("caminho_arquivo") or ""
                    if caminho:
                        try:
                            caminho_resolvido = Path(caminho).resolve()
                            base_resolvida = DSYSTEM_STATIC_DIR.resolve()
                            if str(caminho_resolvido).startswith(str(base_resolvida)) and caminho_resolvido.exists():
                                caminho_resolvido.unlink()
                        except Exception:
                            pass
                    conn_del = conectar_banco()
                    cdel = conn_del.cursor()
                    cdel.execute("DELETE FROM dsystem_arquivos WHERE id=?", (arquivo["id"],))
                    conn_del.commit()
                    conn_del.close()
                    st.success("Arquivo removido.")
                    st.rerun()

def renderizar_gestao_chamados_chefe():
    st.subheader("Banco de chamados")
    funcionarios = listar_funcionarios_sistema()
    labels_func = ["-- Sem funcionário --"] + [f["label"] for f in funcionarios]
    mapa_func = {f["label"]: f["username"] for f in funcionarios}

    with st.expander("Enviar link para cliente abrir chamado", expanded=False):
        texto_abertura = texto_cliente_abrir_chamado()
        st.caption(f"Canal oficial de WhatsApp: {WHATSAPP_OFICIAL}")
        e1, e2 = st.columns(2)
        email_abertura = e1.text_input("E-mail do cliente:", key="link_abrir_ch_email")
        whats_abertura = e2.text_input("Celular/WhatsApp do cliente:", placeholder="(31) 99999-9999", key="link_abrir_ch_whats")
        st.text_area("Mensagem para enviar:", value=texto_abertura, height=120, key="link_abrir_ch_msg", disabled=True)
        b1, b2, b3 = st.columns(3)
        telefone_abertura = telefone_whatsapp(whats_abertura)
        if telefone_abertura:
            b1.link_button(
                "Abrir WhatsApp",
                url_whatsapp(telefone_abertura, texto_abertura),
                width="stretch",
            )
        else:
            b1.warning("Informe o celular.")
        if email_abertura.strip():
            b2.link_button(
                "Abrir Gmail",
                url_gmail(email_abertura, "Abrir chamado no portal", texto_abertura),
                width="stretch",
            )
        else:
            b2.warning("Informe o e-mail.")
        b3.text_input("Link direto:", value=url_abrir_chamado(), key="link_abrir_ch_direto")

    conn = conectar_banco()
    c = conn.cursor()
    c.execute("SELECT * FROM chamados_cliente ORDER BY id DESC")
    chamados = c.fetchall()
    conn.close()

    if not chamados:
        st.info("Nenhum chamado registrado.")
        return

    tabela = []
    for chamado in chamados:
        data_ch, inicio_ch, fim_ch, tipo_ch, _ = periodo_chamado(chamado)
        tabela.append({
            "ID": chamado.get("id"),
            "Cliente": chamado.get("cliente_nome"),
            "Área": chamado.get("area_destino") or "Suporte",
            "Assunto": chamado.get("titulo"),
            "Status": chamado.get("status"),
            "Funcionário": chamado.get("funcionario_designado") or "",
            "Data": texto_data_br(data_ch),
            "Horário": f"{inicio_ch} às {fim_ch}",
            "Tipo": tipo_ch,
            "Criado em": chamado.get("criado_em"),
        })
    st.dataframe(pd.DataFrame(tabela), width="stretch", hide_index=True)

    id_ed = st.number_input("ID do chamado para gerenciar:", min_value=1, step=1, key="gest_ch_id")
    chamado = next((item for item in chamados if item.get("id") == id_ed), None)
    if not chamado:
        return

    data_ch, inicio_ch, fim_ch, tipo_ch, descricao_ch = periodo_chamado(chamado)
    with st.expander(f"Gerenciando chamado #{id_ed} - {chamado.get('cliente_nome')}", expanded=True):
        st.write(f"**Pedido original:** {chamado.get('descricao') or ''}")
        st.write(f"**Solicitado para:** {texto_data_br(chamado.get('data_solicitada'))} das {chamado.get('hora_inicio')} às {chamado.get('hora_fim')}")
        contato_cliente = buscar_contato_cliente(chamado.get("cliente_id"), chamado.get("cliente_nome") or "")
        st.markdown("#### Conversa do chamado")
        renderizar_chat_chamado(chamado, chamado.get("cliente_nome") or "")
        with st.form(f"form_resposta_equipe_chamado_{id_ed}", clear_on_submit=True):
            msg_equipe = st.text_area("Responder no chat do chamado:", height=90, key=f"msg_equipe_ch_{id_ed}")
            anexo_equipe = st.file_uploader("Anexo opcional:", key=f"anexo_equipe_ch_{id_ed}")
            enviar_msg_equipe = st.form_submit_button("Enviar resposta para o cliente", type="primary", width="stretch")
        if enviar_msg_equipe:
            if not msg_equipe.strip() and not anexo_equipe:
                st.error("Digite uma resposta ou anexe um arquivo.")
            elif anexo_equipe and not upload_dentro_limite(anexo_equipe):
                erro_upload_grande("anexo")
            else:
                salvar_mensagem_chamado(id_ed, "equipe", st.session_state.get("username") or "Equipe Dsystem", msg_equipe.strip(), anexo_equipe)
                st.success("Resposta enviada no chamado.")
                st.rerun()

        with st.expander("Responder cliente por WhatsApp ou e-mail", expanded=False):
            r1, r2 = st.columns(2)
            email_cliente = r1.text_input(
                "E-mail do cliente:",
                value=(contato_cliente.get("email") or "").strip(),
                key=f"ch_email_cliente_{id_ed}",
            )
            telefone_digitado = r2.text_input(
                "Celular/WhatsApp do cliente:",
                value=contato_cliente.get("telefone") or "",
                placeholder="(31) 99999-9999",
                key=f"ch_whats_cliente_{id_ed}",
            )
            mensagem_retorno = st.text_area(
                "Mensagem para o cliente:",
                value="Temos uma atualização sobre o seu chamado. Acesse o portal pelo link abaixo para acompanhar ou responder.",
                height=100,
                key=f"ch_msg_cliente_{id_ed}",
            )
            texto_envio = texto_retorno_chamado(chamado, mensagem_retorno)
            st.text_area("Prévia da mensagem:", value=texto_envio, height=170, key=f"ch_preview_envio_{id_ed}", disabled=True)
            cwa, cgmail, cem = st.columns(3)
            telefone_cliente = telefone_whatsapp(telefone_digitado)
            if telefone_cliente:
                cwa.link_button(
                    "Abrir WhatsApp",
                    url_whatsapp(telefone_cliente, texto_envio),
                    width="stretch",
                )
            else:
                cwa.warning("Informe o celular para abrir o WhatsApp.")
            if email_cliente.strip():
                cgmail.link_button(
                    "Abrir Gmail",
                    url_gmail(email_cliente, f"Retorno do chamado #{id_ed}", texto_envio),
                    width="stretch",
                )
                cem.link_button(
                    "App de e-mail",
                    url_mailto(email_cliente, f"Retorno do chamado #{id_ed}", texto_envio),
                    width="stretch",
                )
            else:
                cgmail.warning("Informe o e-mail.")
                cem.warning("Informe o e-mail.")

        s1, s2, s3, s4 = st.columns(4)
        status_opcoes = ["Novo", "Em análise", "Modificado - aguardando aprovação", "Aprovado pelo cliente", "Designado", "Em atendimento", "Concluído", "Cancelado", "Recusado pelo cliente"]
        status_atual = chamado.get("status") if chamado.get("status") in status_opcoes else "Novo"
        novo_status = s1.selectbox("Status:", status_opcoes, index=status_opcoes.index(status_atual), key=f"ch_status_{id_ed}")
        label_atual = next((f["label"] for f in funcionarios if f["username"] == chamado.get("funcionario_designado")), "-- Sem funcionário --")
        funcionario_label = s2.selectbox("Funcionário designado:", labels_func, index=labels_func.index(label_atual) if label_atual in labels_func else 0, key=f"ch_func_{id_ed}")
        novo_tipo = s3.selectbox("Tipo ajustado:", ["Remoto", "Presencial", "Presencial ou remoto"], index=["Remoto", "Presencial", "Presencial ou remoto"].index(tipo_ch) if tipo_ch in ["Remoto", "Presencial", "Presencial ou remoto"] else 0, key=f"ch_tipo_{id_ed}")
        area_atual = chamado.get("area_destino") if chamado.get("area_destino") in AREAS_CHAMADO else "Suporte"
        nova_area = s4.selectbox("Área:", AREAS_CHAMADO, index=AREAS_CHAMADO.index(area_atual), key=f"ch_area_{id_ed}")

        d1, d2, d3 = st.columns(3)
        try:
            data_default = datetime.strptime(data_ch, "%Y-%m-%d").date()
        except Exception:
            data_default = date.today()
        nova_data = d1.date_input("Data ajustada:", value=data_default, key=f"ch_data_{id_ed}")
        try:
            inicio_default = datetime.strptime(inicio_ch, "%H:%M").time() if inicio_ch else None
        except Exception:
            inicio_default = None
        try:
            fim_default = datetime.strptime(fim_ch, "%H:%M").time() if fim_ch else None
        except Exception:
            fim_default = None
        nova_hora_inicio = d2.time_input("Hora início ajustada:", value=inicio_default, key=f"ch_ini_{id_ed}", step=1800)
        nova_hora_fim = d3.time_input("Hora fim ajustada:", value=fim_default, key=f"ch_fim_{id_ed}", step=1800)
        novo_titulo = st.text_input("Assunto:", value=chamado.get("titulo") or "", key=f"ch_titulo_{id_ed}")
        nova_descricao = st.text_area("Descrição/ajuste para o cliente:", value=descricao_ch, height=120, key=f"ch_desc_{id_ed}")

        if st.button("Salvar gestão do chamado", type="primary", width="stretch", key=f"ch_salvar_{id_ed}"):
            funcionario = mapa_func.get(funcionario_label, "")
            if not funcionario and nova_area in {"Gerente", "Compras"}:
                funcionario = responsavel_area_chamado(nova_area)
            h_ini = nova_hora_inicio.strftime("%H:%M") if nova_hora_inicio else ""
            h_fim = nova_hora_fim.strftime("%H:%M") if nova_hora_fim else ""
            erros = []
            if not novo_titulo.strip():
                erros.append("Informe o assunto do chamado.")
            if not h_ini or not h_fim:
                erros.append("Informe o horário de início e término.")
            elif h_fim <= h_ini:
                erros.append("A hora de término precisa ser maior que a hora de início.")
            if funcionario:
                conflito = conflito_agenda_funcionario(funcionario, nova_data.strftime("%Y-%m-%d"), h_ini, h_fim, chamado_ignorar=id_ed)
                if conflito:
                    erros.append(conflito)
            if erros:
                for erro in erros:
                    st.error(erro)
                return

            conn_up = conectar_banco()
            cup = conn_up.cursor()
            cup.execute(
                """UPDATE chamados_cliente SET titulo=?, status=?, funcionario_designado=?, area_destino=?,
                   ajuste_tipo_atendimento=?, ajuste_data=?, ajuste_hora_inicio=?, ajuste_hora_fim=?,
                   ajuste_descricao=?, atualizado_em=? WHERE id=?""",
                (
                    novo_titulo,
                    novo_status,
                    funcionario,
                    nova_area,
                    novo_tipo,
                    nova_data.strftime("%Y-%m-%d"),
                    h_ini,
                    h_fim,
                    nova_descricao,
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    id_ed,
                ),
            )
            conn_up.commit()
            conn_up.close()
            st.success("Chamado atualizado.")
            st.rerun()

def renderizar_chamados_funcionario():
    funcionario = st.session_state.get("username", "")
    if not funcionario:
        return
    conn = conectar_banco()
    c = conn.cursor()
    eh_daniel = funcionario.strip().lower() == "daniel.fabio"
    c.execute(
        """SELECT * FROM chamados_cliente
           WHERE (funcionario_designado=%s
                  OR (%s=0 AND COALESCE(funcionario_designado, '')='' AND COALESCE(area_destino, 'Suporte')='Suporte'))
             AND status NOT IN ('Concluído', 'Cancelado', 'Recusado pelo cliente')
           ORDER BY ajuste_data ASC, data_solicitada ASC, hora_inicio ASC""",
        (funcionario, int(eh_daniel)),
    )
    chamados = c.fetchall()
    conn.close()
    if not chamados:
        st.info("Nenhum chamado atribuído a você.")
        return
    st.subheader("Chamados atribuídos a mim")
    for chamado in chamados:
        data_ch, inicio_ch, fim_ch, tipo_ch, descricao_ch = periodo_chamado(chamado)
        with st.expander(f"#{chamado['id']} - {chamado.get('cliente_nome')} - {texto_data_br(data_ch)} {inicio_ch}", expanded=False):
            st.write(f"**Área:** {chamado.get('area_destino') or 'Suporte'}")
            st.write(f"**Status:** {chamado.get('status')}")
            st.write(f"**Tipo:** {tipo_ch}")
            st.write(f"**Horário:** {texto_data_br(data_ch)} das {inicio_ch} às {fim_ch}")
            st.write(f"**Descrição:** {descricao_ch}")

def possui_chamados_atribuidos(username):
    if not username:
        return False
    conn = conectar_banco()
    c = conn.cursor()
    eh_daniel = username.strip().lower() == "daniel.fabio"
    c.execute(
        """SELECT id FROM chamados_cliente
           WHERE (funcionario_designado=%s
                  OR (%s=0 AND COALESCE(funcionario_designado, '')='' AND COALESCE(area_destino, 'Suporte')='Suporte'))
             AND status NOT IN ('Concluído', 'Cancelado', 'Recusado pelo cliente')
           LIMIT 1""",
        (username, int(eh_daniel)),
    )
    existe = c.fetchone() is not None
    conn.close()
    return existe

def proximo_codigo_cliente(cursor):
    cursor.execute("SELECT MAX(id) FROM clientes")
    ultimo_id = cursor.fetchone()[0] or 0
    return f"CLI{ultimo_id + 1:05d}"


def normalizar_documento_cliente(valor):
    return re.sub(r"\D", "", str(valor or ""))


def buscar_ids_cliente_por_documento(cursor, documento, ignorar_id=None):
    chave = normalizar_documento_cliente(documento)
    if not chave:
        return []
    sql = "SELECT id FROM clientes WHERE (documento_chave=? OR REGEXP_REPLACE(COALESCE(cnpj,''), '[^0-9]', '')=?)"
    params = [chave, chave]
    if ignorar_id is not None:
        sql += " AND id<>?"
        params.append(int(ignorar_id))
    cursor.execute(sql, tuple(params))
    return [int(row[0]) for row in cursor.fetchall()]

def preparar_funcionarios(funcionarios):
    preparados = []
    for idx, funcionario in enumerate(funcionarios, start=1):
        item = dict(funcionario)
        if not item.get("codigo"):
            item["codigo"] = f"FUN{idx:03d}"
        preparados.append(item)
    return json.dumps(preparados, ensure_ascii=False)

def carregar_lista_json(valor):
    try:
        dados = json.loads(valor or "[]")
        return dados if isinstance(dados, list) else []
    except Exception:
        return []

def preparar_redes_sociais(redes):
    return json.dumps([r for r in redes if r.get("rede") or r.get("url")], ensure_ascii=False)

def preparar_setores(setores):
    return json.dumps([s for s in setores if s.get("nome") or s.get("softwares") or s.get("informacoes")], ensure_ascii=False)

def calcular_proxima_preventiva(data_realizacao, periodo):
    if not data_realizacao or periodo in ("Sem recorrência", "", None):
        return ""
    dias_por_periodo = {
        "30 dias": 30,
        "6 meses": 180,
        "1 ano": 365,
    }
    dias = dias_por_periodo.get(periodo)
    if not dias:
        return ""
    try:
        if isinstance(data_realizacao, str):
            data_base = datetime.strptime(data_realizacao, "%d/%m/%Y").date()
        else:
            data_base = data_realizacao
        return (data_base + timedelta(days=dias)).strftime("%d/%m/%Y")
    except Exception:
        return ""

def letra_equipamento(indice):
    letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return letras[indice] if indice < len(letras) else str(indice + 1)

def numero_item_os(os_id, indice):
    return f"{int(os_id):05d}-{letra_equipamento(indice)}"

def resumo_config_os(item):
    config = item.get("config", {})
    partes = []
    for chave in ["tipo", "so", "cpu", "ram", "hd", "gpu", "placa", "gabinete", "chave_so"]:
        valor = config.get(chave, "")
        if valor:
            partes.append(f"{chave}: {valor}")
    return " | ".join(partes)

def salvar_equipamentos_os(cursor, os_id, itens):
    cursor.execute("SELECT numero_item, kanban_status, etiqueta_codigo, kanban_alterado_por, kanban_alterado_em FROM equipamentos_os WHERE os_id=?", (os_id,))
    estados_anteriores = {row.get("numero_item"): dict(row) for row in cursor.fetchall()}
    cursor.execute("DELETE FROM equipamentos_os WHERE os_id=?", (os_id,))
    for idx, item in enumerate(itens):
        numero = numero_item_os(os_id, idx)
        config_json = json.dumps(item.get("config", {}), ensure_ascii=False)
        foto = item.get("foto") or {}
        estado = estados_anteriores.get(numero, {})
        cursor.execute('''INSERT INTO equipamentos_os
            (os_id, numero_item, letra_equipamento, tipo_equipamento, equipamento, marca, numero_serie, avaria, defeito, servico, configuracao, foto_nome, foto_mime, foto, kanban_status, etiqueta_codigo, kanban_alterado_por, kanban_alterado_em)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (os_id, numero, letra_equipamento(idx), item.get("tipo", ""), item.get("equipamento", ""),
             item.get("marca", ""), item.get("serie", ""), item.get("avaria", ""), item.get("defeito", ""),
             item.get("servico", ""), config_json, foto.get("nome") or "", foto.get("mime") or "", foto.get("dados"),
             estado.get("kanban_status") or "Recebido", estado.get("etiqueta_codigo") or numero,
             estado.get("kanban_alterado_por") or "", estado.get("kanban_alterado_em") or ""))

def salvar_cliente_simples(nome, cpf, end, tel, cep):
    if not nome.strip() or not normalizar_documento_cliente(cpf):
        return
    conn = conectar_banco()
    c = conn.cursor()
    ids_documento = buscar_ids_cliente_por_documento(c, cpf)
    if not ids_documento:
        codigo_cliente = proximo_codigo_cliente(c)
        c.execute('''INSERT INTO clientes (codigo_cliente, documento_chave, nome, cnpj, endereco, telefone, cep, email, rg_mei, numero, complemento, bairro, cidade_estado, tipo, insc_estadual, insc_municipal, substituto_tributario, funcionarios) VALUES (?, ?, ?, ?, ?, ?, ?, "", "", "", "", "", "", "Cliente", "", "", "Não", "[]")''', (codigo_cliente, normalizar_documento_cliente(cpf), nome, cpf, end, tel, cep))
    conn.commit()
    conn.close()


def sincronizar_logins_portal_cliente(cursor, cliente_id, cliente_nome, documento, funcionarios):
    """Mantém o login da empresa e as contas dos funcionários vinculados ao portal."""
    usuario_empresa = normalizar_documento_cliente(documento)
    if usuario_empresa:
        cursor.execute(
            """UPDATE clientes SET portal_username=?,
               portal_password=CASE WHEN COALESCE(portal_password, '')='' THEN ? ELSE portal_password END,
               portal_trocar_senha=CASE WHEN COALESCE(portal_password, '')='' THEN 1 ELSE portal_trocar_senha END
               WHERE id=?""",
            (usuario_empresa, criar_hash_senha("1234"), cliente_id),
        )

    try:
        lista = json.loads(funcionarios or "[]") if isinstance(funcionarios, str) else list(funcionarios or [])
    except Exception:
        lista = []
    emails_ativos = []
    for funcionario in lista:
        email = str(funcionario.get("email") or "").strip().lower()
        if not email:
            continue
        emails_ativos.append(email)
        cursor.execute("SELECT id, cliente_id FROM clientes_portal_usuarios WHERE username=?", (email,))
        conta_existente = cursor.fetchone()
        if conta_existente and int(conta_existente.get("cliente_id") or 0) != int(cliente_id):
            raise ValueError(f"O e-mail {email} já está vinculado a outra empresa.")
        if conta_existente:
            cursor.execute(
                """UPDATE clientes_portal_usuarios SET nome=?, cargo=?, tipo='Funcionário', ativo=1
                   WHERE id=?""",
                (funcionario.get("nome") or "", funcionario.get("cargo") or "", conta_existente.get("id")),
            )
        else:
            cursor.execute(
                """INSERT INTO clientes_portal_usuarios
                   (cliente_id, username, nome, cargo, tipo, password, trocar_senha, twofa_ativo, ativo, criado_em)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (cliente_id, email, funcionario.get("nome") or "", funcionario.get("cargo") or "",
                 "Funcionário", criar_hash_senha("1234"), 1, 0, 1, agora_br()),
            )
    if emails_ativos:
        marcadores = ",".join(["?"] * len(emails_ativos))
        cursor.execute(
            f"UPDATE clientes_portal_usuarios SET ativo=0 WHERE cliente_id=? AND username NOT IN ({marcadores})",
            (cliente_id, *emails_ativos),
        )
    else:
        cursor.execute("UPDATE clientes_portal_usuarios SET ativo=0 WHERE cliente_id=?", (cliente_id,))

def salvar_cliente(nome, tel, tel_sec, email, emails_cobranca, cnpj, rg, end, num, comp, bairro, cid, cep, tipo, ie, im, sub, redes_sociais="[]", funcionarios="[]", portal_username="", portal_senha="", logo_dados=None, logo_nome="", logo_mime="", dados_complementares=None):
    if not nome.strip():
        raise ValueError("Informe o Nome/Empresa.")
    documento_chave = normalizar_documento_cliente(cnpj)
    if len(documento_chave) not in (11, 14):
        raise ValueError("Informe um CPF com 11 dígitos ou CNPJ com 14 dígitos.")
    conn = conectar_banco()
    c = conn.cursor()
    ids_documento = buscar_ids_cliente_por_documento(c, cnpj)
    if len(ids_documento) > 1:
        conn.close()
        raise ValueError("Existem cadastros antigos duplicados com este CPF/CNPJ. Revise-os antes de atualizar.")
    row_id = ids_documento[0] if ids_documento else None
    portal_hash = criar_hash_senha(portal_senha) if portal_senha else None
    if row_id:
        campos_logo = ", logo_nome=?, logo_mime=?, logo=?" if logo_dados is not None else ""
        if portal_senha:
            sql = f'''UPDATE clientes SET nome=?, documento_chave=?, telefone=?, telefone_secundario=?, email=?, emails_cobranca=?, cnpj=?, rg_mei=?, endereco=?, numero=?, complemento=?, bairro=?, cidade_estado=?, cep=?, tipo=?, insc_estadual=?, insc_municipal=?, substituto_tributario=?, redes_sociais=?, funcionarios=?, portal_username=?, portal_password=?, portal_trocar_senha=1, portal_2fa_secret=NULL, portal_2fa_ativo=0{campos_logo} WHERE id=?'''
            params = [nome, documento_chave, tel, tel_sec, email, emails_cobranca, cnpj, rg, end, num, comp, bairro, cid, cep, tipo, ie, im, sub, redes_sociais, funcionarios, portal_username, portal_hash]
        else:
            sql = f'''UPDATE clientes SET nome=?, documento_chave=?, telefone=?, telefone_secundario=?, email=?, emails_cobranca=?, cnpj=?, rg_mei=?, endereco=?, numero=?, complemento=?, bairro=?, cidade_estado=?, cep=?, tipo=?, insc_estadual=?, insc_municipal=?, substituto_tributario=?, redes_sociais=?, funcionarios=?, portal_username=?{campos_logo} WHERE id=?'''
            params = [nome, documento_chave, tel, tel_sec, email, emails_cobranca, cnpj, rg, end, num, comp, bairro, cid, cep, tipo, ie, im, sub, redes_sociais, funcionarios, portal_username]
        if logo_dados is not None:
            params.extend([logo_nome, logo_mime, logo_dados])
        params.append(row_id)
        c.execute(sql, tuple(params))
        cliente_id_salvo = row_id
    else:
        codigo_cliente = proximo_codigo_cliente(c)
        c.execute('''INSERT INTO clientes (codigo_cliente, documento_chave, nome, telefone, telefone_secundario, email, emails_cobranca, cnpj, rg_mei, endereco, numero, complemento, bairro, cidade_estado, cep, tipo, insc_estadual, insc_municipal, substituto_tributario, redes_sociais, funcionarios, logo_nome, logo_mime, logo, portal_username, portal_password, portal_trocar_senha, portal_2fa_ativo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (codigo_cliente, documento_chave, nome, tel, tel_sec, email, emails_cobranca, cnpj, rg, end, num, comp, bairro, cid, cep, tipo, ie, im, sub, redes_sociais, funcionarios, logo_nome, logo_mime, logo_dados, portal_username, portal_hash or "", 1 if portal_hash else 0, 0))
        cliente_id_salvo = c.lastrowid
    if dados_complementares:
        campos_complementares = list(dados_complementares.keys())
        atribuicoes = ", ".join(f"{campo}=?" for campo in campos_complementares)
        c.execute(
            f"UPDATE clientes SET {atribuicoes} WHERE id=?",
            tuple(dados_complementares[campo] for campo in campos_complementares) + (cliente_id_salvo,),
        )
    sincronizar_logins_portal_cliente(c, cliente_id_salvo, nome, cnpj, funcionarios)
    conn.commit()
    conn.close()


def garantir_logins_clientes_existentes():
    """Cria uma única vez os acessos automáticos para cadastros já existentes."""
    conn = conectar_banco()
    c = conn.cursor()
    try:
        c.execute("SELECT id, nome, cnpj, funcionarios FROM clientes ORDER BY id")
        for cliente in c.fetchall():
            try:
                sincronizar_logins_portal_cliente(
                    c,
                    cliente.get("id"),
                    cliente.get("nome") or "",
                    cliente.get("cnpj") or "",
                    cliente.get("funcionarios") or "[]",
                )
            except ValueError:
                # E-mails antigos duplicados ficam preservados para correção manual no cadastro.
                continue
        conn.commit()
    finally:
        conn.close()


garantir_logins_clientes_existentes()


def deletar_registro(tabela, coluna_id, id_val):
    conn = conectar_banco()
    c = conn.cursor()
    c.execute(f'DELETE FROM {tabela} WHERE {coluna_id} = ?', (id_val,))
    conn.commit()
    conn.close()

def formata_moeda(valor): 
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def moeda_para_float(valor):
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor or "").replace("R$", "").strip()
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except Exception:
        return 0.0

def multiplicador_orcamento_empresa(empresa):
    if "LC Printer" in str(empresa or ""):
        return 1.30
    if "GT" in str(empresa or ""):
        return 1.45
    return 1.0

def itens_orcamento_normalizados(valor):
    if isinstance(valor, list):
        itens = valor
    else:
        try:
            itens = json.loads(valor or "[]")
        except Exception:
            itens = []
    normalizados = []
    for item in itens if isinstance(itens, list) else []:
        if not isinstance(item, dict):
            continue
        desc = str(item.get("d") or item.get("desc") or item.get("descricao") or "").strip()
        try:
            qtd = int(float(item.get("q") or item.get("qtd") or 0))
        except Exception:
            qtd = 0
        vunit = moeda_para_float(item.get("v") if item.get("v") is not None else item.get("vunit"))
        vtotal = moeda_para_float(item.get("t") if item.get("t") is not None else item.get("vtotal"))
        if not vtotal:
            vtotal = vunit * qtd
        tipo_item = item.get("tipo_item") or item.get("tipo") or item.get("tipo_nota") or "Serviço"
        if tipo_item not in ["Produto", "Serviço"]:
            tipo_item = "Serviço"
        if desc or vtotal:
            normalizados.append({
                "d": desc, "q": qtd, "v": vunit, "t": vtotal, "tipo_item": tipo_item,
                "estoque_id": item.get("estoque_id"), "situacao_nota": item.get("situacao_nota") or "",
                "origem_item": item.get("origem_item") or "",
                "ajuste_preco_percentual": item.get("ajuste_preco_percentual") or 0,
            })
    return normalizados

def nome_arquivo_orcamento(numero, empresa):
    empresa_limpa = re.sub(r"[^A-Za-z0-9_-]+", "_", empresa or "orcamento").strip("_")
    numero_limpo = re.sub(r"[^A-Za-z0-9_-]+", "_", str(numero or "sem_numero")).strip("_")
    return f"orcamento_{numero_limpo}_{empresa_limpa}.pdf"

def gerar_pdf_orcamento_empresa(dados, empresa):
    buffer = io.BytesIO()
    try:
        import reportlab
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image as RLImage, SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    except Exception as ex:
        raise RuntimeError(f"Biblioteca de PDF não instalada: {ex}")

    mult = multiplicador_orcamento_empresa(empresa)
    cor = colors.HexColor("#004488") if "Dsystem" in empresa else colors.HexColor("#1c1762") if "LC Printer" in empresa else colors.HexColor("#4ba3d5")
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    pasta_fontes_orc = Path(reportlab.__file__).resolve().parent / "fonts"
    if "OrcamentoSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("OrcamentoSans", str(pasta_fontes_orc / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("OrcamentoSans-Bold", str(pasta_fontes_orc / "VeraBd.ttf")))
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "OrcamentoSans"
    styles["Title"].fontName = "OrcamentoSans-Bold"
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="Cell", parent=styles["Normal"], fontSize=8, leading=9))
    elementos = []
    titulo_empresa = {
        "Dsystem Tecnologia": "Dsystem Tecnologia",
        "LC Printer": "LC Printer - Luiz Cláudio da Silveira-ME",
        "GT Solutions": "GT Solutions",
    }.get(empresa, empresa)
    endereco_empresa = {
        "Dsystem Tecnologia": "Rua Glória, 25 - Sabará/MG - CEP 34.700-150",
        "LC Printer": "CNPJ 11.024.413/0001-22 - R. Geralda Martins de Miranda, 244 - Maria Goretti - Belo Horizonte/MG - CEP 31.930-450 - (31) 3432-3593 / 9 8500-2691 - lc_printer@hotmail.com",
    }.get(empresa, "")
    estilo_titulo_orc = ParagraphStyle(
        name="TituloOrc", parent=styles["Title"], textColor=cor, fontSize=20, leading=24
    )
    caminho_logo_lc = Path(__file__).resolve().parent / "logo_lc_printer.jpg"
    if empresa == "LC Printer" and caminho_logo_lc.exists():
        cabecalho_empresa = Table(
            [[
                RLImage(str(caminho_logo_lc), width=42 * mm, height=28.3 * mm),
                Paragraph(f"<b>{titulo_empresa}</b><br/><font size='8'>{endereco_empresa}</font>", estilo_titulo_orc),
            ]],
            colWidths=[48 * mm, 132 * mm],
        )
        cabecalho_empresa.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elementos.append(cabecalho_empresa)
    else:
        elementos.append(Paragraph(f"<b>{titulo_empresa}</b>", estilo_titulo_orc))
        if endereco_empresa:
            elementos.append(Paragraph(endereco_empresa, styles["Small"]))
    cabecalho_orcamento = f"Orçamento Nº {h(dados.get('numero'))} - emissão {h(dados.get('data_orc') or data_para_br(date.today()))}"
    if dados.get("data_validade"):
        cabecalho_orcamento += f" - válido até {h(dados.get('data_validade'))}"
    elementos.append(Paragraph(cabecalho_orcamento, styles["Small"]))
    elementos.append(Spacer(1, 8))
    cliente = [
        ["Cliente", dados.get("cliente") or ""],
        ["CPF/CNPJ", dados.get("cpf_cnpj") or ""],
        ["Telefone", dados.get("telefone") or ""],
        ["E-mail", dados.get("email") or ""],
        ["Endereço", dados.get("endereco") or ""],
    ]
    tabela_cliente = Table(cliente, colWidths=[28 * mm, 150 * mm])
    tabela_cliente.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f4f7")),
        ("FONTNAME", (0, 0), (-1, -1), "OrcamentoSans"),
        ("FONTNAME", (0, 0), (0, -1), "OrcamentoSans-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elementos.append(tabela_cliente)
    elementos.append(Spacer(1, 10))
    linhas = [["Item", "Descrição", "Qtd", "Unitário", "Total"]]
    total = 0.0
    for idx, item in enumerate(itens_orcamento_normalizados(dados.get("itens")), start=1):
        qtd = int(item.get("q") or 0)
        unit = float(item.get("v") or 0) * mult
        subtotal = float(item.get("t") or 0) * mult
        total += subtotal
        linhas.append([idx, Paragraph(h(item.get("d") or ""), styles["Cell"]), qtd, formata_moeda(unit), formata_moeda(subtotal)])
    if len(linhas) == 1:
        linhas.append(["", "Sem itens", "", "", formata_moeda(0)])
    tabela_itens = Table(linhas, colWidths=[12 * mm, 92 * mm, 16 * mm, 30 * mm, 30 * mm], repeatRows=1)
    tabela_itens.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), cor),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "OrcamentoSans"),
        ("FONTNAME", (0, 0), (-1, 0), "OrcamentoSans-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elementos.append(tabela_itens)
    elementos.append(Spacer(1, 8))
    elementos.append(Paragraph(f"<b>Total: {formata_moeda(total)}</b>", ParagraphStyle(name="TotalOrc", parent=styles["Normal"], fontSize=13, leading=16, alignment=2, textColor=cor)))
    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(f"<b>Forma de pagamento:</b> {h(dados.get('forma_pagamento') or '')}", styles["Small"]))
    if dados.get("obs_pag"):
        elementos.append(Paragraph(f"<b>Obs. pagamento:</b> {h(dados.get('obs_pag'))}", styles["Small"]))
    if dados.get("obs_geral"):
        elementos.append(Paragraph(f"<b>Observações:</b> {h(dados.get('obs_geral'))}", styles["Small"]))
    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

def dados_orcamento_base(numero, cliente, cpf_cnpj, itens, forma_pagamento, obs_pag="", obs_geral="", data_orc=None, telefone="", email="", endereco="", data_validade=""):
    return {
        "numero": numero,
        "cliente": cliente,
        "cpf_cnpj": cpf_cnpj,
        "itens": itens,
        "forma_pagamento": forma_pagamento,
        "obs_pag": obs_pag,
        "obs_geral": obs_geral,
        "data_orc": data_orc or date.today().strftime("%d/%m/%Y"),
        "telefone": telefone,
        "email": email,
        "endereco": endereco,
        "data_validade": data_validade,
    }

def tipo_nota_por_itens(itens):
    tipos = sorted({item.get("tipo_item") or "Serviço" for item in itens})
    return "Produto e Serviço" if len(tipos) > 1 else (tipos[0] if tipos else "Serviço")

def lancar_orcamento_dsystem_no_faturamento(orcamento):
    itens_aprov = itens_orcamento_normalizados(orcamento.get("itens"))
    valor_aprov = sum(float(item.get("t") or 0) for item in itens_aprov)
    tipo_nota_aprov = tipo_nota_por_itens(itens_aprov)
    itens_fat_orc = [
        {
            "desc": item.get("d") or "",
            "tipo_item": item.get("tipo_item") or "Serviço",
            "qtd": int(item.get("q") or 0),
            "vunit": float(item.get("v") or 0),
            "vtotal": float(item.get("t") or 0),
            "estoque_id": item.get("estoque_id"),
            "origem_item": item.get("origem_item") or "",
            "situacao_nota": item.get("situacao_nota") or "",
            "ajuste_preco_percentual": item.get("ajuste_preco_percentual") or 0,
        }
        for item in itens_aprov
    ]
    conn_lf = conectar_banco()
    clf = conn_lf.cursor()
    clf.execute("""INSERT INTO faturamento
                (data_lanc, cliente, cnpj, tipo, emite_nf, tipo_nota, forma_pag,
                 itens, valor_total, parcelas, vencimento, orc_ref, obs_interna, obs_nota, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (data_para_banco_br(date.today()), orcamento.get("cliente"), orcamento.get("cpf_cnpj"),
                 "Eventual", "Sim", tipo_nota_aprov, orcamento.get("forma_pagamento") or "",
                 json.dumps(itens_fat_orc, ensure_ascii=False), valor_aprov, "Não",
                 data_para_banco_br(date.today() + timedelta(days=5)), orcamento.get("numero"),
                 f"Gerado pelo orçamento #{orcamento.get('numero')} aprovado (Dsystem Tecnologia).",
                 orcamento.get("obs_geral") or "", "Aberto"))
    fat_id = clf.lastrowid
    clf.execute("""UPDATE orcamentos SET status=?, empresa_aprovada=?, tipo_faturamento_aprovado=?,
                faturamento_id=?, alterado_por=?, alterado_em=? WHERE orc_id=?""",
                ("Aprovado e lançado", "Dsystem Tecnologia", tipo_nota_aprov, fat_id,
                 st.session_state.get("username", ""), agora_br(), orcamento.get("orc_id")))
    conn_lf.commit()
    conn_lf.close()
    return fat_id, valor_aprov, tipo_nota_aprov

def preparar_nota_fiscal_por_tipo(faturamento, tipo_item, competencia=None):
    itens_tipo = [
        item for item in itens_faturamento_lista(faturamento.get("itens"))
        if (item.get("tipo_item") or "Serviço") == tipo_item
    ]
    if not itens_tipo:
        return None, 0.0
    valor_tipo = sum(float(item.get("vtotal") or 0) for item in itens_tipo)
    descricao = "\n".join(
        f"{item.get('desc') or ''} - Qtd: {item.get('qtd') or 0} - Total: {formatar_moeda_br(item.get('vtotal'))}"
        for item in itens_tipo
    )
    observacoes = faturamento.get("obs_nota") or faturamento.get("obs_interna") or ""
    data_competencia = data_para_banco_br(competencia or date.today())
    conn_nf_tipo = conectar_banco()
    cnf_tipo = conn_nf_tipo.cursor()
    valores_nf = (
        faturamento.get("cliente") or "",
        faturamento.get("cnpj") or "",
        tipo_item,
        data_competencia,
        descricao,
        valor_tipo,
        0,
        0,
        "",
        "Belo Horizonte / MG",
        observacoes,
    )
    cnf_tipo.execute(
        "SELECT id FROM notas_fiscais WHERE faturamento_id=? AND tipo_nota=? LIMIT 1",
        (faturamento.get("id"), tipo_item),
    )
    existente_nf = cnf_tipo.fetchone()
    if existente_nf:
        cnf_tipo.execute("""UPDATE notas_fiscais SET cliente=?, cpf_cnpj=?, tipo_nota=?, data_competencia=?,
                            descricao=?, valor_servicos=?, aliquota_iss=?, valor_iss=?, codigo_servico=?,
                            municipio_prestacao=?, observacoes=? WHERE id=?""",
                         valores_nf + (existente_nf["id"],))
        nota_id = existente_nf["id"]
    else:
        cnf_tipo.execute("""INSERT INTO notas_fiscais
                            (cliente, cpf_cnpj, tipo_nota, data_competencia, descricao, valor_servicos,
                             aliquota_iss, valor_iss, codigo_servico, municipio_prestacao, observacoes,
                             faturamento_id, status, criado_por, criado_em)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         valores_nf + (
                             faturamento.get("id"), "Pendente",
                             st.session_state.get("username", ""), agora_br()
                         ))
        nota_id = cnf_tipo.lastrowid
    conn_nf_tipo.commit()
    conn_nf_tipo.close()
    return nota_id, valor_tipo

def somente_digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))

def xml_texto(parent, tag, valor):
    return service_xml_texto(parent, tag, valor)

def formatar_decimal_xml(valor):
    return service_formatar_decimal_xml(valor)

def gerar_xml_nfse_bh_rps(faturamento, tipo_item, dados_nota):
    return service_gerar_xml_nfse_bh_rps(faturamento, tipo_item, dados_nota)

def gerar_pdf_nota_autorizada_simples(nota, retorno_info):
    return service_gerar_pdf_nota_autorizada_simples(nota, retorno_info, formatar_moeda_br)

def salvar_retorno_nota_fiscal(nota_id, xml_envio, xml_retorno, retorno_info, gerar_pdf=True):
    conn = conectar_banco()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM notas_fiscais WHERE id=%s", (nota_id,))
    nota = cur.fetchone() or {}
    status = retorno_info.get("status") or "Recebida"
    numero = retorno_info.get("numero_nfse") or nota.get("numero_nota") or ""
    chave = retorno_info.get("chave_acesso") or nota.get("chave_acesso") or ""
    protocolo = retorno_info.get("protocolo") or nota.get("protocolo") or ""
    lote = retorno_info.get("numero_lote") or nota.get("numero_lote") or ""
    mensagem = retorno_info.get("mensagem") or ""
    xml_retorno_txt = xml_retorno.decode("utf-8", errors="ignore") if isinstance(xml_retorno, bytes) else str(xml_retorno or "")
    xml_envio_txt = xml_envio.decode("utf-8", errors="ignore") if isinstance(xml_envio, bytes) else str(xml_envio or "")
    pdf_base64 = nota.get("pdf_base64") or ""
    emitido_em = nota.get("emitido_em")
    if status == "Autorizada":
        emitido_em = emitido_em or agora_br()
        if gerar_pdf:
            nota_pdf = {**nota, "numero_nota": numero, "chave_acesso": chave, "protocolo": protocolo, "mensagem_retorno": mensagem}
            pdf_base64 = base64.b64encode(gerar_pdf_nota_autorizada_simples(nota_pdf, retorno_info)).decode("ascii")
    cur.execute(
        """UPDATE notas_fiscais SET status=%s, numero_nota=%s, chave_acesso=%s, protocolo=%s,
           numero_lote=%s, mensagem_retorno=%s, xml_envio=%s, xml_retorno=%s, xml_autorizado=%s,
           pdf_base64=%s, emitido_em=%s, atualizado_em=%s WHERE id=%s""",
        (
            status, numero, chave, protocolo, lote, mensagem, xml_envio_txt, xml_retorno_txt,
            xml_retorno_txt if status == "Autorizada" else nota.get("xml_autorizado"),
            pdf_base64, emitido_em, agora_br(), nota_id,
        ),
    )
    conn.commit()
    conn.close()
    return status

def mensagem_retorno_nfse_legivel(retorno_info):
    codigo = retorno_info.get("codigo_erro") or ""
    mensagem = retorno_info.get("mensagem") or "Retorno recebido sem mensagem detalhada."
    protocolo = retorno_info.get("protocolo") or ""
    numero = retorno_info.get("numero_nfse") or ""
    partes = []
    if codigo:
        partes.append(f"Código: {codigo}")
    partes.append(mensagem)
    if protocolo:
        partes.append(f"Protocolo: {protocolo}")
    if numero:
        partes.append(f"NFS-e: {numero}")
    return " | ".join(partes)

def renderizar_notas_emitidas_tab():
    st.subheader("Notas fiscais")
    st.caption("Acompanhe notas preparadas, recebidas, autorizadas e rejeitadas, com XML, PDF e retorno do governo separados.")
    conn_notas = conectar_banco()
    cnotas = conn_notas.cursor(dictionary=True)
    cnotas.execute("SELECT * FROM notas_fiscais ORDER BY id DESC")
    notas = filtrar_registros_por_empresa(cnotas.fetchall(), "cliente")
    conn_notas.close()

    f1, f2, f3, f4 = st.columns(4)
    filtro_cliente = f1.text_input("Cliente, nota ou protocolo:", key="notas_emitidas_filtro")
    tipos = ["Todos"] + sorted({n.get("tipo_nota") for n in notas if n.get("tipo_nota")})
    statuses = ["Todos"] + sorted({n.get("status") for n in notas if n.get("status")})
    filtro_tipo = f2.selectbox("Tipo:", tipos, key="notas_emitidas_tipo")
    filtro_status = f3.selectbox("Status:", statuses, key="notas_emitidas_status")
    filtro_data = f4.date_input("Competência:", value=None, key="notas_emitidas_competencia")

    filtradas = list(notas)
    termo = (filtro_cliente or "").strip().lower()
    if termo:
        filtradas = [
            n for n in filtradas
            if termo in str(n.get("cliente") or "").lower()
            or termo in str(n.get("id") or "").lower()
            or termo in str(n.get("numero_nota") or "").lower()
            or termo in str(n.get("protocolo") or "").lower()
            or termo in str(n.get("chave_acesso") or "").lower()
        ]
    if filtro_tipo != "Todos":
        filtradas = [n for n in filtradas if (n.get("tipo_nota") or "") == filtro_tipo]
    if filtro_status != "Todos":
        filtradas = [n for n in filtradas if (n.get("status") or "") == filtro_status]
    if filtro_data:
        mes = filtro_data.strftime("%m/%Y")
        filtradas = [n for n in filtradas if mes in str(n.get("data_competencia") or "")]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Notas filtradas", len(filtradas))
    m2.metric("Autorizadas", sum(1 for n in filtradas if (n.get("status") or "") == "Autorizada"))
    m3.metric("Rejeitadas/erro", sum(1 for n in filtradas if (n.get("status") or "") in ("Rejeitada", "Erro")))
    m4.metric("Valor filtrado", formatar_moeda_br(sum(float(n.get("valor_servicos") or 0) for n in filtradas)))

    if not filtradas:
        st.info("Nenhuma nota encontrada para os filtros.")
        return

    st.markdown("#### Lista de notas")
    st.dataframe([{
        "ID": n.get("id"),
        "Faturamento": n.get("faturamento_id"),
        "Cliente": n.get("cliente") or "",
        "Tipo": n.get("tipo_nota") or "",
        "Valor": formatar_moeda_br(n.get("valor_servicos")),
        "Status": n.get("status") or "",
        "Número": n.get("numero_nota") or "",
        "Protocolo": n.get("protocolo") or "",
        "Mensagem": n.get("mensagem_retorno") or "",
    } for n in filtradas], width="stretch", hide_index=True)

    ids_notas = [int(n.get("id") or 0) for n in filtradas]
    id_sel = st.selectbox("Ver detalhes da nota:", ids_notas, key="notas_emitidas_id_sel")
    nota = next((n for n in filtradas if int(n.get("id") or 0) == int(id_sel)), None)
    if not nota:
        return

    st.markdown("#### Detalhes separados da nota")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Status", nota.get("status") or "-")
    d2.metric("Tipo", nota.get("tipo_nota") or "-")
    d3.metric("Valor", formatar_moeda_br(nota.get("valor_servicos")))
    d4.metric("Número", nota.get("numero_nota") or "-")

    with st.expander("1. Dados principais", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.text_input("Cliente:", value=nota.get("cliente") or "", disabled=True, key=f"nota_cliente_{id_sel}")
        c2.text_input("CPF/CNPJ:", value=nota.get("cpf_cnpj") or "", disabled=True, key=f"nota_doc_{id_sel}")
        c3.text_input("Competência:", value=nota.get("data_competencia") or "", disabled=True, key=f"nota_comp_{id_sel}")
        st.text_area("Descrição:", value=nota.get("descricao") or "", height=120, disabled=True, key=f"nota_desc_{id_sel}")

    with st.expander("2. Retorno do governo", expanded=True):
        r1, r2, r3 = st.columns(3)
        r1.text_input("Protocolo:", value=nota.get("protocolo") or "", disabled=True, key=f"nota_prot_{id_sel}")
        r2.text_input("Chave/Código:", value=nota.get("chave_acesso") or "", disabled=True, key=f"nota_chave_{id_sel}")
        r3.text_input("Lote:", value=nota.get("numero_lote") or "", disabled=True, key=f"nota_lote_{id_sel}")
        st.info(nota.get("mensagem_retorno") or "Sem mensagem de retorno salva.")
        endpoint = config_sistema_val("NFSE_ENDPOINT_SOAP", NFSE_ENDPOINT_TESTE_NACIONAL)
        if st.button("Consultar protocolo na prefeitura", width="stretch", key=f"consultar_protocolo_{id_sel}"):
            if not endpoint:
                st.error("Configure o endpoint/API em Configurações do Sistema > NFS-e.")
            elif not nota.get("protocolo"):
                st.error("Esta nota ainda não possui protocolo para consulta.")
            else:
                try:
                    retorno_consulta = consultar_protocolo_nfse(
                        endpoint,
                        nota.get("protocolo"),
                        config_sistema_val("NFSE_CNPJ", "23524449000154"),
                        config_sistema_val("NFSE_INSCRICAO_MUNICIPAL", "07395930011"),
                        cert_path=config_sistema_val("NFSE_CERT_PFX_PATH", ""),
                        cert_password=config_sistema_val("NFSE_CERT_PASSWORD", config_val("NFSE_CERT_PASSWORD", "")),
                    )
                    info_consulta = analisar_retorno_nfse(retorno_consulta)
                    salvar_retorno_nota_fiscal(nota.get("id"), nota.get("xml_envio") or "", retorno_consulta, info_consulta)
                    st.success("Consulta realizada e nota atualizada.")
                    st.info(mensagem_retorno_nfse_legivel(info_consulta))
                    st.rerun()
                except Exception as ex:
                    st.error(f"Falha ao consultar protocolo: {ex}")

    with st.expander("3. XML e PDF", expanded=False):
        if nota.get("xml_envio"):
            st.download_button("Baixar XML enviado", data=nota.get("xml_envio"), file_name=f"nota_{id_sel}_envio.xml", mime="application/xml", width="stretch", key=f"nota_xml_envio_{id_sel}")
        if nota.get("xml_retorno"):
            st.download_button("Baixar XML retorno", data=nota.get("xml_retorno"), file_name=f"nota_{id_sel}_retorno.xml", mime="application/xml", width="stretch", key=f"nota_xml_retorno_{id_sel}")
        if nota.get("xml_autorizado"):
            st.download_button("Baixar XML autorizado", data=nota.get("xml_autorizado"), file_name=f"nota_{id_sel}_autorizada.xml", mime="application/xml", width="stretch", key=f"nota_xml_autorizado_{id_sel}")
        if nota.get("pdf_base64"):
            st.download_button("Baixar PDF da nota", data=base64.b64decode(nota.get("pdf_base64")), file_name=f"nota_{id_sel}.pdf", mime="application/pdf", width="stretch", key=f"nota_pdf_{id_sel}")
        if not any([nota.get("xml_envio"), nota.get("xml_retorno"), nota.get("xml_autorizado"), nota.get("pdf_base64")]):
            st.info("Ainda não há XML/PDF salvo para esta nota.")

def injetar_css_portal_cliente():
    st.markdown("""
<style>
body, .stApp {
    background: #070a0f;
}
.portal-shell {
    margin: -2rem -1rem 1.5rem -1rem;
    padding: 28px 34px 34px;
    min-height: 420px;
    color: #fff;
    background:
        linear-gradient(110deg, rgba(7,10,15,.94) 0%, rgba(13,19,31,.88) 45%, rgba(18,26,35,.78) 100%),
        radial-gradient(circle at 80% 20%, rgba(223,255,0,.22), transparent 26%),
        linear-gradient(135deg, #101722, #06080d);
    border-bottom: 8px solid #eaff00;
    position: relative;
    overflow: hidden;
}
.portal-shell:after {
    content: "";
    position: absolute;
    inset: 0;
    background-image: repeating-linear-gradient(135deg, rgba(255,255,255,.04) 0 1px, transparent 1px 8px);
    pointer-events: none;
}
.portal-top, .portal-hero, .portal-actions, .portal-grid {
    position: relative;
    z-index: 1;
}
.portal-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 18px;
    margin-bottom: 58px;
}
.portal-brand {
    display: flex;
    align-items: center;
    gap: 16px;
    font-size: 18px;
    font-weight: 800;
    letter-spacing: .3px;
}
.portal-brand img {
    height: 70px;
    max-width: 210px;
    object-fit: contain;
}
.portal-nav {
    display: flex;
    gap: 24px;
    font-size: 13px;
    font-weight: 800;
    text-transform: uppercase;
}
.portal-nav a {
    color: #eaff00;
    text-decoration: none;
}
.portal-nav span {
    color: #eaff00;
    text-decoration: none;
}
.portal-nav a:hover {
    color: #fff;
    text-decoration: underline;
    text-decoration-color: #eaff00;
    text-underline-offset: 8px;
}
.portal-nav span:hover {
    color: #fff;
}
.portal-hero {
    max-width: 980px;
    margin: 0 auto;
    text-align: center;
}
.portal-kicker {
    color: #eaff00;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: .16em;
    font-size: 12px;
    margin-bottom: 18px;
}
.portal-title {
    font-size: clamp(34px, 5vw, 68px);
    line-height: 1.03;
    font-weight: 900;
    margin: 0;
}
.portal-title span {
    color: #eaff00;
}
.portal-subtitle {
    margin: 20px auto 0;
    max-width: 780px;
    color: rgba(255,255,255,.78);
    font-size: 18px;
    line-height: 1.55;
}
.portal-actions {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 18px 20px;
    margin: 28px auto 28px;
    max-width: 1400px;
    padding: 0 20px;
}
.portal-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: 56px;
    border: 1px solid rgba(234,255,0,.65);
    color: #fff !important;
    padding: 14px 18px;
    border-radius: 999px;
    background: #005293;
    font-weight: 800;
    text-decoration: none !important;
    transition: .16s ease;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,.04);
}
.portal-pill:hover {
    border-color: #eaff00;
    background: #0768b5;
    color: #fff;
    transform: translateY(-1px);
}
.portal-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin-top: 28px;
}
.portal-card {
    background: linear-gradient(180deg, rgba(25,31,42,.96), rgba(13,17,24,.96));
    border: 1px solid rgba(255,255,255,.1);
    border-radius: 8px;
    padding: 18px;
    min-height: 128px;
    box-shadow: 0 14px 34px rgba(0,0,0,.35);
    transition: .16s ease;
}
.portal-card-link {
    display: block;
    color: inherit !important;
    text-decoration: none !important;
}
.portal-card-link:hover {
    border-color: rgba(234,255,0,.65);
    transform: translateY(-2px);
    box-shadow: 0 18px 42px rgba(0,0,0,.42);
}
.portal-card strong {
    display: block;
    color: #fff;
    font-size: 15px;
    margin-bottom: 10px;
}
.portal-number {
    font-size: 34px;
    font-weight: 900;
    color: #eaff00;
}
.portal-muted {
    color: rgba(255,255,255,.62);
    font-size: 13px;
}
.portal-section-title {
    margin: 28px 0 12px;
    color: #fff;
    font-size: 26px;
    font-weight: 900;
}
.portal-mini-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    margin-bottom: 18px;
}
.portal-mini {
    border: 1px solid rgba(234,255,0,.22);
    background: rgba(16,22,31,.8);
    border-radius: 8px;
    padding: 16px;
}
.portal-mini b {
    color: #eaff00;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[kind="secondary"],
div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[kind="primary"] {
    border: 1px solid rgba(234,255,0,.55);
    color: #eaff00;
    background: rgba(234,255,0,.08);
    border-radius: 999px;
    font-weight: 900;
    min-height: 46px;
    transition: .16s ease;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button:hover {
    border-color: #eaff00;
    background: rgba(234,255,0,.18);
    color: #fff;
    transform: translateY(-1px);
}
.portal-whatsapp {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 56px;
    border-radius: 999px;
    background: #0877b8;
    border: 1px solid #2fb7ff;
    color: #fff !important;
    font-weight: 900;
    text-decoration: none !important;
    box-shadow: 0 10px 24px rgba(0, 99, 180, .24);
}
.portal-whatsapp:hover {
    background: #0a75c9;
    border-color: #79d7ff;
    color: #fff !important;
}
.portal-doc-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    margin: 16px 0 20px;
}
.portal-doc-box {
    border: 1px solid rgba(234,255,0,.18);
    border-radius: 8px;
    padding: 16px;
    background: rgba(16,22,31,.82);
}
.portal-doc-box b {
    color: #eaff00;
}
.chat-bubble {
    max-width: 78%;
    margin: 10px 0;
    padding: 13px 15px;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,.12);
    box-shadow: 0 10px 26px rgba(0,0,0,.22);
}
.chat-bubble.cliente {
    margin-left: auto;
    background: linear-gradient(180deg, rgba(0,75,141,.95), rgba(0,56,105,.95));
}
.chat-bubble.equipe {
    margin-right: auto;
    background: linear-gradient(180deg, rgba(25,31,42,.98), rgba(14,18,26,.98));
    border-color: rgba(234,255,0,.22);
}
.chat-meta {
    color: #eaff00;
    font-size: 12px;
    font-weight: 800;
    margin-bottom: 6px;
}
.chat-text {
    color: #fff;
    line-height: 1.45;
}
@media (max-width: 900px) {
    .portal-top { align-items: flex-start; flex-direction: column; margin-bottom: 34px; }
    .portal-nav { flex-wrap: wrap; gap: 12px; }
    .portal-actions, .portal-grid, .portal-mini-grid, .portal-doc-grid { grid-template-columns: 1fr; }
}
</style>
""", unsafe_allow_html=True)


def portal_logo_src():
    try:
        with open("logo_dsystem.png", "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""

def contar_portal_cliente(cliente_portal, cliente_portal_id=None):
    dados = {"chamados_abertos": 0, "os": 0, "propostas": 0, "notas": 0, "financeiro": 0.0}
    conn = conectar_banco()
    c = conn.cursor(dictionary=True)
    try:
        c.execute("SELECT COUNT(*) AS total FROM chamados_cliente WHERE cliente_nome=%s AND COALESCE(status,'') NOT IN ('Concluído','Concluido','Fechado','Cancelado')", (cliente_portal,))
        dados["chamados_abertos"] = (c.fetchone() or {}).get("total") or 0
    except Exception:
        pass
    try:
        c.execute("SELECT COUNT(*) AS total FROM ordens_servico WHERE cliente=%s", (cliente_portal,))
        dados["os"] = (c.fetchone() or {}).get("total") or 0
    except Exception:
        pass
    try:
        if cliente_portal_id:
            c.execute("SELECT COUNT(*) AS total FROM propostas_contratos_cliente WHERE cliente_id=%s OR cliente_nome=%s", (cliente_portal_id, cliente_portal))
        else:
            c.execute("SELECT COUNT(*) AS total FROM propostas_contratos_cliente WHERE cliente_nome=%s", (cliente_portal,))
        dados["propostas"] = (c.fetchone() or {}).get("total") or 0
    except Exception:
        pass
    try:
        c.execute("SELECT COUNT(*) AS total FROM notas_fiscais WHERE cliente=%s", (cliente_portal,))
        dados["notas"] = (c.fetchone() or {}).get("total") or 0
    except Exception:
        pass
    try:
        c.execute("SELECT COALESCE(SUM(valor_total),0) AS total FROM faturamento WHERE cliente=%s AND COALESCE(status,'Aberto') IN ('Aberto','Faturado')", (cliente_portal,))
        dados["financeiro"] = float((c.fetchone() or {}).get("total") or 0)
    except Exception:
        pass
    conn.close()
    return dados

def selecionar_secao_portal(secao):
    secao = normalizar_secao_portal(secao)
    st.session_state["portal_cliente_secao"] = secao
    try:
        st.query_params["pagina"] = "portal"
        st.query_params["secao"] = secao
        if st.session_state.get("portal_nav_sid"):
            st.query_params["portal_sid"] = st.session_state["portal_nav_sid"]
    except Exception:
        pass
    st.rerun()


PORTAL_NAV_SESSIONS = {}


def obter_portal_sid_atual():
    sid = st.session_state.get("portal_nav_sid")
    if not sid:
        sid = uuid.uuid4().hex
        st.session_state["portal_nav_sid"] = sid
    if len(PORTAL_NAV_SESSIONS) > 200:
        for chave in list(PORTAL_NAV_SESSIONS)[:50]:
            PORTAL_NAV_SESSIONS.pop(chave, None)
    PORTAL_NAV_SESSIONS[sid] = {key: st.session_state[key] for key in st.session_state.keys()}
    return sid


def restaurar_portal_por_sid():
    sid = obter_query_param("portal_sid")
    if not sid or st.session_state.get("autenticado"):
        return
    dados = PORTAL_NAV_SESSIONS.get(sid)
    if not dados:
        return
    for key, value in dados.items():
        st.session_state[key] = value
    st.session_state["portal_nav_sid"] = sid
    secao = obter_query_param("secao")
    if secao:
        st.session_state["portal_cliente_secao"] = normalizar_secao_portal(secao)


def portal_href(secao):
    return "?" + urlencode({
        "pagina": "portal",
        "secao": normalizar_secao_portal(secao),
        "portal_sid": obter_portal_sid_atual(),
    })


def renderizar_portal_cliente_home(cliente_portal, cliente_portal_id=None):
    injetar_css_portal_cliente()
    dados = contar_portal_cliente(cliente_portal, cliente_portal_id)
    logo_src = portal_logo_src()
    logo_html = f'<img src="{logo_src}" alt="Dsystem">' if logo_src else "<strong>Dsystem Tecnologia</strong>"
    whatsapp_href = whatsapp_oficial_url(
        f"Ola, sou {cliente_portal} e preciso de atendimento pelo portal do cliente."
    )
    st.markdown(f"""
<section class="portal-shell">
  <div class="portal-top">
    <div class="portal-brand">{logo_html}</div>
  </div>
  <div class="portal-hero">
    <div class="portal-kicker">Portal exclusivo do cliente</div>
    <h1 class="portal-title"><span>Suporte t&eacute;cnico</span> e gest&atilde;o digital em um s&oacute; lugar</h1>
    <p class="portal-subtitle">Ol&aacute;, {h(cliente_portal)}. Acompanhe atendimentos, documentos, notas, propostas e solicita&ccedil;&otilde;es com mais clareza.</p>
  </div>
</section>
""", unsafe_allow_html=True)

    botoes_portal = (
        ("Abrir chamado", "abrir_chamado"), ("Meus chamados", "meus_chamados"),
        ("Ver notas fiscais", "notas"), ("Financeiro", "financeiro"),
        ("Ordens de serviço", "os"), ("Documentos", "documentos"),
        ("Falar no WhatsApp", "contato"), ("Início", "inicio"),
    )
    for linha in range(0, len(botoes_portal), 4):
        colunas = st.columns(4)
        for coluna, (rotulo, secao) in zip(colunas, botoes_portal[linha:linha + 4]):
            if coluna.button(rotulo, key=f"portal_nav_{secao}", width="stretch"):
                selecionar_secao_portal(secao)

    st.markdown(f"""
<div class="portal-grid">
  {portal_card_html("meus_chamados", "Chamados em aberto", dados["chamados_abertos"], "Solicitações em acompanhamento")}
  {portal_card_html("os", "Ordens de serviço", dados["os"], "Histórico técnico registrado")}
  {portal_card_html("notas", "Notas fiscais", dados["notas"], "XML e PDF quando emitidas")}
  {portal_card_html("financeiro", "Financeiro", formatar_moeda_br(dados["financeiro"]), "Total em acompanhamento")}
</div>
""", unsafe_allow_html=True)

    if st.session_state.get("portal_cliente_secao", "inicio") == "inicio":
        st.markdown(portal_mini_grid_html(), unsafe_allow_html=True)

    if st.session_state.get("tipo_login") == "cliente":
        sair_col, _ = st.columns([1, 3])
        if sair_col.button("Sair do portal", width="stretch", key="portal_logout"):
            logout()

def renderizar_portal_ordens_servico(cliente_portal, cursor, conn):
    cursor.execute(
        "SELECT os_id, data_os, cliente, equipamento, servico FROM ordens_servico WHERE cliente=%s ORDER BY os_id DESC",
        (cliente_portal,),
    )
    ordens_cliente = cursor.fetchall()
    st.markdown("### Ordens de serviço")
    if ordens_cliente:
        for os_cli in ordens_cliente:
            with st.expander(f"OS #{os_cli['os_id']} - {os_cli.get('data_os') or 'Sem data'}", expanded=False):
                st.write(f"**Cliente:** {os_cli.get('cliente') or ''}")
                st.write(f"**Equipamento:** {os_cli.get('equipamento') or ''}")
                st.write(f"**Serviço:** {os_cli.get('servico') or ''}")
                st.write("**Status:** Em acompanhamento")
                cursor.execute(
                    "SELECT numero_item, equipamento, foto_nome, foto FROM equipamentos_os WHERE os_id=%s AND foto IS NOT NULL",
                    (os_cli["os_id"],),
                )
                fotos_cli_os = cursor.fetchall()
                for foto_cli in fotos_cli_os:
                    st.image(
                        foto_cli.get("foto"),
                        caption=f"{foto_cli.get('numero_item') or ''} - {foto_cli.get('equipamento') or ''}",
                        width=240,
                    )
                obs_aut = st.text_area("Observação da autorização:", key=f"aut_obs_{os_cli['os_id']}")
                if tem_permissao("cliente.autorizacao") and st.button("Autorizar serviço", key=f"aut_btn_{os_cli['os_id']}"):
                    cursor.execute(
                        "INSERT INTO autorizacoes_cliente (cliente, os_id, servico, status, observacao, criado_em) VALUES (?,?,?,?,?,?)",
                        (cliente_portal, os_cli["os_id"], os_cli.get("servico") or "", "Autorizado", obs_aut, data_para_banco_br(date.today())),
                    )
                    conn.commit()
                    st.success("Autorização registrada.")
                    st.rerun()
    else:
        st.info("Nenhuma OS encontrada para este cliente.")

def renderizar_portal_notas_cliente(cliente_portal):
    st.markdown("### Notas fiscais")
    conn = conectar_banco()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM notas_fiscais WHERE cliente=%s ORDER BY id DESC", (cliente_portal,))
    notas = c.fetchall()
    conn.close()
    if not notas:
        st.info("Nenhuma nota fiscal encontrada para este cliente.")
        return
    st.dataframe([{
        "ID": n.get("id"),
        "Tipo": n.get("tipo_nota") or "",
        "Status": n.get("status") or "",
        "Número": n.get("numero_nota") or "",
        "Valor": formatar_moeda_br(n.get("valor_servicos")),
        "Competência": n.get("data_competencia") or "",
        "Mensagem": n.get("mensagem_retorno") or "",
    } for n in notas], width="stretch", hide_index=True)
    ids = [int(n.get("id") or 0) for n in notas]
    id_nota = st.selectbox("Baixar documentos da nota:", ids, key="portal_nota_id")
    nota = next((n for n in notas if int(n.get("id") or 0) == int(id_nota)), None)
    if nota:
        c1, c2, c3 = st.columns(3)
        if nota.get("pdf_base64"):
            c1.download_button("Baixar PDF", data=base64.b64decode(nota.get("pdf_base64")), file_name=f"nota_{id_nota}.pdf", mime="application/pdf", width="stretch")
        if nota.get("xml_autorizado") or nota.get("xml_retorno"):
            c2.download_button("Baixar XML", data=nota.get("xml_autorizado") or nota.get("xml_retorno"), file_name=f"nota_{id_nota}.xml", mime="application/xml", width="stretch")
        if nota.get("link_nota"):
            c3.link_button("Abrir link da nota", nota.get("link_nota"), width="stretch")

def renderizar_portal_documentos_cliente(cliente_portal, cliente_portal_id=None):
    st.markdown("### Documentos")
    st.markdown("""
<div class="portal-doc-grid">
  <div class="portal-doc-box"><b>Propostas e contratos</b><br><span class="portal-muted">Arquivos enviados pela equipe para aprovação ou consulta.</span></div>
  <div class="portal-doc-box"><b>Notas fiscais</b><br><span class="portal-muted">XML, PDF e links ficam na área de notas.</span></div>
</div>
""", unsafe_allow_html=True)

    aba_docs, aba_notas = st.tabs(["Propostas/Contratos", "Notas"])
    with aba_docs:
        renderizar_propostas_contratos(cliente_portal, cliente_portal_id)

    with aba_notas:
        st.info("As notas fiscais ficam separadas para facilitar o download de XML e PDF.")
        if st.button("Abrir notas fiscais", width="stretch", key="portal_docs_abrir_notas"):
            selecionar_secao_portal("notas")

def renderizar_portal_financeiro_cliente(cliente_portal):
    st.markdown("### Financeiro")
    conn = conectar_banco()
    c = conn.cursor(dictionary=True)
    try:
        c.execute("""SELECT id, data_lanc, vencimento, tipo, forma_pag, valor_total, status, itens, boleto, nota_fiscal
                     FROM faturamento WHERE cliente=%s ORDER BY id DESC""", (cliente_portal,))
    except mysql.connector.Error as ex:
        if getattr(ex, "errno", None) != 1054:
            raise
        c.execute("""SELECT id, data_lanc, vencimento, tipo, forma_pag, valor_total, status, itens
                     FROM faturamento WHERE cliente=%s ORDER BY id DESC""", (cliente_portal,))
    rows = c.fetchall()
    for r in rows:
        r.setdefault("boleto", "")
        r.setdefault("nota_fiscal", "")
    conn.close()
    if not rows:
        st.info("Nenhum lançamento financeiro encontrado para este cliente.")
        return
    hoje = date.today()
    total_aberto = sum(float(r.get("valor_total") or 0) for r in rows if (r.get("status") or "Aberto") in ("Aberto", "Faturado", "A faturar"))
    vencidos = []
    for r in rows:
        venc = parse_data_flex(r.get("vencimento"))
        status = r.get("status") or "Aberto"
        if venc and venc < hoje and status not in ("Pago", "Recebido", "Cancelado", "Faturado"):
            vencidos.append(r)

    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Lançamentos", len(rows))
    f2.metric("Em aberto", formatar_moeda_br(total_aberto))
    f3.metric("Vencidos", len(vencidos))
    f4.metric("Último status", rows[0].get("status") or "-")

    col_f1, col_f2 = st.columns(2)
    status_opcoes = ["Todos"] + sorted({r.get("status") or "Aberto" for r in rows})
    filtro_status = col_f1.selectbox("Filtrar status:", status_opcoes, key="portal_fin_status")
    busca_item = col_f2.text_input("Buscar por item/observação:", key="portal_fin_busca")
    rows_filtrados = rows
    if filtro_status != "Todos":
        rows_filtrados = [r for r in rows_filtrados if (r.get("status") or "Aberto") == filtro_status]
    if busca_item.strip():
        termo = busca_item.strip().lower()
        rows_filtrados = [r for r in rows_filtrados if termo in str(r.get("itens") or "").lower()]

    st.dataframe([{
        "ID": r.get("id"),
        "Data": data_para_br(r.get("data_lanc")),
        "Vencimento": data_para_br(r.get("vencimento")),
        "Tipo": r.get("tipo") or "",
        "Forma": r.get("forma_pag") or "",
        "Itens": r.get("itens") or "",
        "Valor": formatar_moeda_br(r.get("valor_total")),
        "Status": r.get("status") or "",
        "Boleto": "Sim" if r.get("boleto") else "",
        "Nota": r.get("nota_fiscal") or "",
    } for r in rows_filtrados], width="stretch", hide_index=True)

    st.write("---")
    st.markdown("#### Segunda via e atendimento financeiro")
    ids = [int(r.get("id") or 0) for r in rows_filtrados]
    if ids:
        id_segunda_via = st.selectbox("Lançamento:", ids, key="portal_fin_segunda_via")
        lancamento = next((r for r in rows_filtrados if int(r.get("id") or 0) == int(id_segunda_via)), None)
        if lancamento:
            msg = (
                f"Olá, sou {cliente_portal}. Preciso da segunda via do lançamento "
                f"#{id_segunda_via}, vencimento {data_para_br(lancamento.get('vencimento'))}, "
                f"valor {formatar_moeda_br(lancamento.get('valor_total'))}."
            )
            c1, c2 = st.columns(2)
            c1.link_button("Pedir segunda via no WhatsApp", criar_url_whatsapp(WHATSAPP_OFICIAL, msg), width="stretch")
            if lancamento.get("boleto") and str(lancamento.get("boleto")).startswith(("http://", "https://")):
                c2.link_button("Abrir boleto", lancamento.get("boleto"), width="stretch")
            elif lancamento.get("boleto"):
                c2.info("Boleto registrado. Solicite a segunda via pelo WhatsApp.")

def renderizar_portal_contato_cliente(cliente_portal):
    st.markdown("### Contato")
    msg = f"Olá, sou {cliente_portal} e preciso de atendimento pelo portal da Dsystem."
    whatsapp_url = criar_url_whatsapp(WHATSAPP_OFICIAL, msg)
    c1, c2 = st.columns(2)
    c1.markdown(
        f"""
<a class="portal-whatsapp" href="{whatsapp_url}" target="_blank">Falar no WhatsApp</a>
""",
        unsafe_allow_html=True,
    )
    c2.link_button("Enviar e-mail", f"mailto:{SMTP_FROM}?subject=Atendimento%20Portal%20Dsystem", width="stretch")
    st.info(f"WhatsApp principal: {WHATSAPP_OFICIAL}")
    st.info(f"E-mail: {SMTP_FROM}")


def assinar_xml_nfse_bh(xml_bytes, cert_path=None, cert_password=None):
    cert_path = cert_path or config_sistema_val("NFSE_CERT_PFX_PATH", config_val("NFSE_CERT_PFX_PATH", str(Path(__file__).resolve().parent / "certificado_dsystem.pfx")))
    cert_password = cert_password if cert_password is not None else config_sistema_val("NFSE_CERT_PASSWORD", config_val("NFSE_CERT_PASSWORD", ""))
    return service_assinar_xml_nfse_bh(xml_bytes, cert_path, cert_password)

def localizar_produto_estoque(cursor, item):
    estoque_id = item.get("estoque_id")
    if estoque_id:
        cursor.execute("SELECT * FROM estoque WHERE id=? LIMIT 1", (estoque_id,))
        encontrado_id = cursor.fetchone()
        if encontrado_id:
            return dict(encontrado_id)
    termo = str(item.get("desc") or "").strip()
    if not termo:
        return None
    candidatos = [termo]
    if "|" in termo:
        candidatos.extend([p.strip() for p in termo.split("|") if p.strip()])
    for candidato in candidatos:
        cursor.execute(
            """SELECT * FROM estoque
               WHERE produto=? OR codigo_entrada=? OR codigo=?
               ORDER BY id DESC LIMIT 1""",
            (candidato, candidato, candidato),
        )
        encontrado = cursor.fetchone()
        if encontrado:
            return dict(encontrado)
    for candidato in candidatos:
        if len(candidato) < 3:
            continue
        cursor.execute(
            """SELECT * FROM estoque
               WHERE produto LIKE ? OR codigo_entrada LIKE ?
               ORDER BY id DESC LIMIT 1""",
            (f"%{candidato}%", f"%{candidato}%"),
        )
        encontrado = cursor.fetchone()
        if encontrado:
            return dict(encontrado)
    return None

def faturar_lancamento_com_integracoes(faturamento):
    fat_id = int(faturamento.get("id") or 0)
    if not fat_id:
        return {"ok": False, "mensagem": "Faturamento inválido."}
    if (faturamento.get("status") or "Aberto") == "Faturado":
        return {"ok": False, "mensagem": "Este lançamento já está marcado como faturado."}

    itens = itens_faturamento_lista(faturamento.get("itens"))
    total = float(faturamento.get("valor_total") or sum(float(i.get("vtotal") or 0) for i in itens))
    usuario = st.session_state.get("username", "")
    agora = agora_br()
    documento = f"FAT-{fat_id}"
    baixas_estoque = []
    alertas = []

    conn_fat = conectar_banco()
    cfat = conn_fat.cursor()
    try:
        cfat.execute("SELECT id FROM contas_receber WHERE numero_documento=? LIMIT 1", (documento,))
        conta_existente = cfat.fetchone()
        if not conta_existente:
            cfat.execute("""INSERT INTO contas_receber
                         (cliente, cpf_cnpj, numero_documento, tipo_receita, categoria, centro_receita,
                          data_emissao, data_competencia, data_vencimento, valor_original, valor_total,
                          forma_recebimento, nota_fiscal, boleto, status, observacoes, criado_por, criado_em)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (
                             faturamento.get("cliente") or "", faturamento.get("cnpj") or "", documento,
                             faturamento.get("tipo") or "Eventual", "Faturamento", "Faturamento",
                             data_para_banco_br(date.today()), faturamento.get("data_lanc") or data_para_banco_br(date.today()),
                             faturamento.get("vencimento") or data_para_banco_br(date.today()), total, total,
                             faturamento.get("forma_pag") or "", "Sim" if faturamento.get("emite_nf") == "Sim" else "Não",
                             "Não", "Aberto", f"Gerado automaticamente pelo faturamento #{fat_id}.",
                             usuario, agora,
                         ))

        for item in itens:
            if not item.get("estoque_id") and (item.get("tipo_item") or "Serviço") != "Produto":
                continue
            produto = localizar_produto_estoque(cfat, item)
            if not produto:
                alertas.append(f"Produto não encontrado no estoque: {item.get('desc') or ''}")
                continue
            qtd_saida = int(item.get("qtd") or 0)
            qtd_atual = int(produto.get("quantidade") or 0)
            nova_qtd = max(0, qtd_atual - qtd_saida)
            cfat.execute("UPDATE estoque SET quantidade=? WHERE id=?", (nova_qtd, produto.get("id")))
            baixas_estoque.append({
                "produto": produto.get("produto") or produto.get("codigo_entrada"),
                "quantidade": qtd_saida,
                "estoque_anterior": qtd_atual,
                "estoque_atual": nova_qtd,
            })

        cfat.execute("UPDATE faturamento SET status=?, alterado_por=?, alterado_em=? WHERE id=?", ("Faturado", usuario, agora, fat_id))
        conn_fat.commit()
    except Exception as ex:
        conn_fat.rollback()
        conn_fat.close()
        return {"ok": False, "mensagem": f"Erro ao faturar: {ex}"}
    conn_fat.close()

    registrar_evento_sistema(
        "faturamento_marcado_como_faturado",
        "faturamento",
        fat_id,
        faturamento.get("cliente") or "",
        {"conta_receber": documento, "baixas_estoque": baixas_estoque, "alertas": alertas},
    )
    mensagem = f"Faturamento #{fat_id} marcado como faturado e enviado para Contas a Receber."
    if baixas_estoque:
        mensagem += f" Estoque baixado em {len(baixas_estoque)} item(ns)."
    if alertas:
        mensagem += " Atenção: " + " | ".join(alertas)
    return {"ok": True, "mensagem": mensagem}

def gerar_pdfs_tres_orcamentos(dados):
    return {
        empresa: {
            "nome": nome_arquivo_orcamento(dados.get("numero"), empresa),
            "dados": gerar_pdf_orcamento_empresa(dados, empresa),
        }
        for empresa in ["Dsystem Tecnologia", "LC Printer", "GT Solutions"]
    }

def salvar_pdfs_orcamento(cursor, orc_id, dados):
    cursor.execute("DELETE FROM orcamento_pdfs WHERE orc_id=?", (orc_id,))
    for empresa, pdf in gerar_pdfs_tres_orcamentos(dados).items():
        cursor.execute("""INSERT INTO orcamento_pdfs
                       (orc_id, empresa, nome_arquivo, mime_type, arquivo, criado_por, criado_em)
                       VALUES (?,?,?,?,?,?,?)""",
                       (orc_id, empresa, pdf["nome"], "application/pdf", pdf["dados"],
                        st.session_state.get("username", ""), agora_br()))

def carrega_logo(img, nome, cor, larg="150"):
    caminho_logo = img if os.path.isabs(img) else os.path.join(os.path.dirname(os.path.abspath(__file__)), img)
    if os.path.exists(caminho_logo):
        with open(caminho_logo, "rb") as f: 
            codigo = base64.b64encode(f.read()).decode()
            return f'<img src="data:image/png;base64,{codigo}" width="{larg}">'
    return f'<h2 style="color: {cor}; margin: 0;">{nome}</h2>'

def limpar_html_impressao(html):
    return "\n".join(linha.lstrip() for linha in textwrap.dedent(html).strip().splitlines())

def preparar_tabela_emails(rows, incluir_senhas=False):
    colunas = [("id", "ID"),("cliente_vinculado", "Empresa/Cliente"),("funcionario", "Usuário/Funcionário"),("email", "E-mail"),("senha", "Senha"),("aliases", "Aliases"),("provedor", "Provedor"),("config_entrada", "Entrada"),("config_saida", "Saída"),("capacidade", "Capacidade"),("data_verificacao", "Data Verificação"),("backup_realizado", "Backup"),("data_backup", "Data Backup")]
    dados = []
    for row in rows:
        item = dict(row)
        if not incluir_senhas:
            item["senha"] = mascarar_segredo(item.get("senha"))
        dados.append({titulo: item.get(campo, "") for campo, titulo in colunas})
    return dados

def confirmar_senha_usuario_atual(senha_digitada):
    usuario = st.session_state.get("username", "")
    if not usuario or not senha_digitada:
        return False
    conn = conectar_banco()
    c = conn.cursor()
    c.execute("SELECT password FROM usuarios WHERE username=?", (usuario,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    senha_hash = row.get("password") if hasattr(row, "get") else row[0]
    return verificar_senha(senha_digitada, senha_hash)

def gerar_excel_emails(rows, titulo, incluir_senhas=False):
    dados = preparar_tabela_emails(rows, incluir_senhas=incluir_senhas)
    df = pd.DataFrame(dados)
    html = f"<html><head><meta charset='utf-8'></head><body><h2>{titulo}</h2>{df.to_html(index=False, escape=True)}</body></html>"
    return html.encode("utf-8")

def _pdf_escape(texto):
    return str(texto).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def gerar_pdf_emails(rows, titulo, incluir_senhas=False):
    dados = preparar_tabela_emails(rows, incluir_senhas=incluir_senhas)
    linhas = [titulo, ""]
    for item in dados:
        linhas.extend([
            f"Empresa/Cliente: {item['Empresa/Cliente']}",
            f"Usuário/Funcionário: {item['Usuário/Funcionário']}",
            f"E-mail: {item['E-mail']}",
            f"Senha: {item['Senha']}",
            f"Aliases: {item['Aliases']}",
            f"Provedor: {item['Provedor']}",
            f"Entrada: {item['Entrada']} | Saída: {item['Saída']}",
            f"Capacidade: {item['Capacidade']} | Backup: {item['Backup']} | Data Backup: {item['Data Backup']}",
            "-" * 95,
        ])
    if not dados:
        linhas.append("Nenhum e-mail encontrado.")

    paginas, linha_atual = [], []
    for linha in linhas:
        partes = textwrap.wrap(str(linha), width=95) or [""]
        for parte in partes:
            linha_atual.append(parte)
            if len(linha_atual) >= 45:
                paginas.append(linha_atual)
                linha_atual = []
    if linha_atual: paginas.append(linha_atual)

    objetos = ["<< /Type /Catalog /Pages 2 0 R >>", "", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    page_ids = []
    for pagina in paginas:
        page_id = len(objetos) + 1
        content_id = page_id + 1
        page_ids.append(page_id)
        comandos = ["BT", "/F1 9 Tf", "50 800 Td"]
        for idx, linha in enumerate(pagina):
            if idx: comandos.append("0 -15 Td")
            comandos.append(f"({_pdf_escape(linha)}) Tj")
        comandos.append("ET")
        stream = "\n".join(comandos).encode("cp1252", errors="replace")
        objetos.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>")
        objetos.append(f"<< /Length {len(stream)} >>\nstream\n{stream.decode('cp1252')}\nendstream")

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objetos[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>"

    saida = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida.extend(f"{idx} 0 obj\n{obj}\nendobj\n".encode("cp1252", errors="replace"))
    xref = len(saida)
    saida.extend(f"xref\n0 {len(objetos)+1}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets[1:]: saida.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    saida.extend(f"trailer\n<< /Size {len(objetos)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii"))
    return bytes(saida)

MODELOS_CONTRATO = {
    "Suporte Tecnológico": "Contrato_Suporte_Tecnologico_DSystem.pdf",
    "Corporativo CLT": "Contrato_Corporativo_CLT_DSystem.pdf",
    "Estágio": "Contrato_Estagio_DSystem_Auditoria_Premium.pdf",
}

def caminho_modelo_contrato(tipo_contrato):
    nome_arquivo = MODELOS_CONTRATO.get(tipo_contrato)
    if not nome_arquivo:
        raise ValueError("Tipo de contrato inválido.")
    return Path(__file__).resolve().parent / "modelos_contratos" / "CONTRATOS" / nome_arquivo

def _texto_pdf(canvas_pdf, texto, x, y, largura, tamanho=9, entrelinha=None, negrito=False, max_linhas=5):
    entrelinha = entrelinha or (tamanho + 2)
    try:
        from reportlab.pdfbase import pdfmetrics
        fonte_personalizada = "ContratoSans-Bold" if negrito else "ContratoSans"
        fonte = fonte_personalizada if fonte_personalizada in pdfmetrics.getRegisteredFontNames() else ("Helvetica-Bold" if negrito else "Helvetica")
    except Exception:
        fonte = "Helvetica-Bold" if negrito else "Helvetica"
    palavras = str(texto or "").split()
    linhas, atual = [], ""
    for palavra in palavras:
        tentativa = f"{atual} {palavra}".strip()
        if canvas_pdf.stringWidth(tentativa, fonte, tamanho) <= largura:
            atual = tentativa
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    canvas_pdf.setFont(fonte, tamanho)
    for indice, linha in enumerate(linhas[:max_linhas]):
        canvas_pdf.drawString(x, y - (indice * entrelinha), linha)

def _caixa_pdf(canvas_pdf, x, y, largura, altura):
    canvas_pdf.setFillColorRGB(1, 1, 1)
    canvas_pdf.setStrokeColorRGB(1, 1, 1)
    canvas_pdf.rect(x, y, largura, altura, fill=1, stroke=0)
    canvas_pdf.setFillColorRGB(0, 0, 0)

def anexar_clausulas_pdf(pdf_original, clausulas, tipo_contrato=""):
    clausulas_validas = [
        {"titulo": str(item.get("titulo") or "").strip(), "texto": str(item.get("texto") or "").strip()}
        for item in (clausulas or [])
        if str(item.get("titulo") or "").strip() and str(item.get("texto") or "").strip()
    ]
    if not clausulas_validas:
        return pdf_original
    try:
        import reportlab
        from pypdf import PdfReader, PdfWriter
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except ImportError as ex:
        raise RuntimeError("Instale as dependências pypdf e reportlab para adicionar cláusulas.") from ex

    fonte_normal, fonte_negrito = "Helvetica", "Helvetica-Bold"
    try:
        pasta_fontes = Path(reportlab.__file__).resolve().parent / "fonts"
        if "ClausulaSans" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("ClausulaSans", str(pasta_fontes / "Vera.ttf")))
        if "ClausulaSans-Bold" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("ClausulaSans-Bold", str(pasta_fontes / "VeraBd.ttf")))
        fonte_normal, fonte_negrito = "ClausulaSans", "ClausulaSans-Bold"
    except Exception:
        pass

    def quebrar_linhas(pdf, texto, largura, fonte=fonte_normal, tamanho=9):
        linhas = []
        for paragrafo in str(texto).splitlines() or [""]:
            palavras = paragrafo.split()
            atual = ""
            for palavra in palavras:
                tentativa = f"{atual} {palavra}".strip()
                if pdf.stringWidth(tentativa, fonte, tamanho) <= largura:
                    atual = tentativa
                else:
                    if atual:
                        linhas.append(atual)
                    atual = palavra
            linhas.append(atual)
        return linhas or [""]

    camada = io.BytesIO()
    pdf = canvas.Canvas(camada, pagesize=A4)
    largura, altura = A4
    margem = 52
    y = altura - 72
    numero_pagina = 1

    def cabecalho():
        nonlocal y
        pdf.setFillColorRGB(0.09, 0.20, 0.30)
        pdf.rect(0, altura - 48, largura, 48, fill=1, stroke=0)
        pdf.setFillColorRGB(1, 1, 1)
        pdf.setFont(fonte_negrito, 11)
        pdf.drawString(margem, altura - 30, "CLÁUSULAS ADICIONAIS")
        pdf.setFont(fonte_normal, 8)
        pdf.drawRightString(largura - margem, altura - 30, tipo_contrato)
        pdf.setFillColorRGB(0.35, 0.42, 0.46)
        pdf.drawRightString(largura - margem, 28, f"Página adicional {numero_pagina}")
        pdf.setFillColorRGB(0, 0, 0)
        y = altura - 76

    cabecalho()
    for indice, item in enumerate(clausulas_validas, start=1):
        linhas = quebrar_linhas(pdf, item["texto"], largura - (2 * margem), tamanho=9)
        altura_bloco = 30 + (len(linhas) * 13)
        if y - altura_bloco < 55:
            pdf.showPage()
            numero_pagina += 1
            cabecalho()
        pdf.setFont(fonte_negrito, 10)
        pdf.setFillColorRGB(0.10, 0.46, 0.66)
        pdf.drawString(margem, y, f"Cláusula adicional {indice}ª - {item['titulo']}")
        y -= 18
        pdf.setFont(fonte_normal, 9)
        pdf.setFillColorRGB(0.12, 0.15, 0.17)
        for linha in linhas:
            pdf.drawString(margem, y, linha)
            y -= 13
        y -= 14
    pdf.save()
    camada.seek(0)

    leitor_original = PdfReader(io.BytesIO(pdf_original))
    leitor_clausulas = PdfReader(camada)
    escritor = PdfWriter()
    escritor.clone_document_from_reader(leitor_original)
    for pagina in leitor_clausulas.pages:
        escritor.add_page(pagina)
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()

def gerar_contrato_pdf(tipo_contrato, dados):
    try:
        import reportlab
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except ImportError as ex:
        raise RuntimeError("Instale as dependências pypdf e reportlab para gerar contratos.") from ex

    pasta_fontes = Path(reportlab.__file__).resolve().parent / "fonts"
    try:
        if "ContratoSans" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("ContratoSans", str(pasta_fontes / "Vera.ttf")))
        if "ContratoSans-Bold" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("ContratoSans-Bold", str(pasta_fontes / "VeraBd.ttf")))
    except Exception:
        pass

    caminho_modelo = caminho_modelo_contrato(tipo_contrato)
    if not caminho_modelo.exists():
        raise FileNotFoundError(f"Modelo não encontrado: {caminho_modelo.name}")

    leitor = PdfReader(str(caminho_modelo))
    escritor = PdfWriter()
    if tipo_contrato in {"Estágio", "Corporativo CLT", "Suporte Tecnológico"} and leitor.get_fields():
        escritor.clone_document_from_reader(leitor)
        endereco_formulario = ", ".join(
            parte for parte in [dados.get("endereco"), dados.get("numero"), dados.get("complemento"),
                                dados.get("bairro"), dados.get("cidade_estado"), dados.get("cep")]
            if str(parte or "").strip()
        )
        if tipo_contrato == "Estágio":
            campos_formulario = {
                "nome_estagiario": dados.get("nome") or "", "cpf_estagiario": dados.get("cnpj") or "",
                "endereco_estagiario": endereco_formulario, "telefone_estagiario": dados.get("telefone") or "",
                "email_estagiario": dados.get("email") or "", "instituicao_ensino": dados.get("instituicao_ensino") or "",
                "curso": dados.get("curso") or "", "jornada_20": "/Yes" if str(dados.get("jornada") or "").startswith("20") else "/Off",
                "jornada_30": "/Yes" if str(dados.get("jornada") or "").startswith("30") else "/Off",
                "data_emissao": dados.get("data_contrato") or "",
            }
        elif tipo_contrato == "Corporativo CLT":
            campos_formulario = {
                "nome_colaborador": dados.get("nome") or "", "cpf_colaborador": dados.get("cnpj") or "",
                "rg_colaborador": dados.get("rg_mei") or "", "cargo_colaborador": dados.get("cargo") or "",
                "endereco_colaborador": endereco_formulario, "telefone_colaborador": dados.get("telefone") or "",
                "email_colaborador": dados.get("email") or "", "salario_colaborador": dados.get("valor_contrato") or "",
                "data_emissao": dados.get("data_contrato") or "",
            }
        else:
            campos_formulario = {
                "nome_contratante": dados.get("nome") or "", "cnpj_contratante": dados.get("cnpj") or "",
                "endereco_contratante": endereco_formulario, "responsavel_contratante": dados.get("responsavel_legal") or "",
                "cpf_responsavel": dados.get("cpf_responsavel") or "", "telefone_contratante": dados.get("telefone") or "",
                "email_contratante": dados.get("email") or "", "data_inicio": dados.get("data_contrato") or "",
                "dia_vencimento": dados.get("dia_vencimento") or "", "valor_mensal": dados.get("valor_contrato") or "",
                "forma_pagamento": dados.get("forma_pagamento") or "", "data_emissao": dados.get("data_contrato") or "",
            }
        for pagina in escritor.pages:
            escritor.update_page_form_field_values(pagina, campos_formulario, auto_regenerate=False)
        saida = io.BytesIO()
        escritor.write(saida)
        return anexar_clausulas_pdf(saida.getvalue(), dados.get("clausulas"), tipo_contrato)

    endereco_completo = ", ".join(
        parte for parte in [
            dados.get("endereco"), dados.get("numero"), dados.get("complemento"),
            dados.get("bairro"), dados.get("cidade_estado"), f"CEP {dados.get('cep')}" if dados.get("cep") else "",
        ] if str(parte or "").strip()
    )

    for indice_pagina, pagina in enumerate(leitor.pages):
        largura = float(pagina.mediabox.width)
        altura = float(pagina.mediabox.height)
        camada = io.BytesIO()
        pdf = canvas.Canvas(camada, pagesize=(largura, altura))

        if tipo_contrato == "Suporte Tecnológico":
            if indice_pagina == 0:
                _caixa_pdf(pdf, 35, altura - 165, largura - 70, 120)
                _texto_pdf(pdf, f"Contrato de Manutenção das estações de trabalho entre {dados.get('nome')} e D-System Tecnologia - ME", 42, altura - 75, largura - 84, 12, 15, True, 3)
                _caixa_pdf(pdf, 35, 350, largura - 70, 340)
                _texto_pdf(pdf, "CONTRATANTE:", 42, altura - 188, largura - 84, 10, negrito=True)
                qualificacao = f"{dados.get('nome')}, com sede em {endereco_completo}, inscrita no CPF/CNPJ sob o nº {dados.get('cnpj')}."
                _texto_pdf(pdf, qualificacao, 42, altura - 210, largura - 84, 10, 13, False, 5)
                _texto_pdf(pdf, "CONTRATADA:", 42, altura - 285, largura - 84, 10, negrito=True)
                _texto_pdf(pdf, "D F PEREIRA INFORMÁTICA - ME (D-System Tecnologia), com sede em Sabará, na Rua Glória, nº 25, CEP 34.700-150, no Estado MG, inscrita no CNPJ sob o nº 23.524.449/0001-54.", 42, altura - 307, largura - 84, 10, 13, False, 6)
                _texto_pdf(pdf, "As partes acima identificadas têm, entre si, justo e acertado o presente Contrato de manutenção de computadores, redes periféricas adjuntas e softwares próprios necessários ao funcionamento dos computadores, que se regerá pelas cláusulas seguintes e pelas condições descritas no presente contrato e proposta comercial anexa.", 42, 445, largura - 84, 10, 13, False, 6)
                _texto_pdf(pdf, "DO OBJETO DO CONTRATO", 42, 370, largura - 84, 11, negrito=True)
            elif indice_pagina == 2:
                _caixa_pdf(pdf, 35, 440, largura - 70, 260)
                _texto_pdf(pdf, "DO PAGAMENTO", 42, altura - 165, largura - 84, 11, negrito=True)
                pagamento = (
                    f"Cláusula 8ª. Pelo serviço prestado, a CONTRATANTE pagará à CONTRATADA "
                    f"a quantia mensal de {dados.get('valor_contrato')}, com vencimento todo dia "
                    f"{dados.get('dia_vencimento')} de cada mês, por meio de {dados.get('forma_pagamento')}."
                )
                _texto_pdf(pdf, pagamento, 42, altura - 195, largura - 84, 10, 14, False, 6)
            elif indice_pagina == 3:
                _caixa_pdf(pdf, 90, 685, 260, 30)
                _caixa_pdf(pdf, 35, 525, largura - 70, 175)
                _texto_pdf(pdf, f"Belo Horizonte, {dados.get('data_contrato')}.", 42, altura - 165, largura - 84, 10)
                _texto_pdf(pdf, dados.get("nome"), 42, altura - 225, largura - 84, 10, negrito=True)
                _texto_pdf(pdf, "(Assinatura certificado gov.br)", 42, altura - 244, largura - 84, 9)
                _texto_pdf(pdf, f"{dados.get('responsavel_legal')} - CPF {dados.get('cpf_responsavel')}", 42, altura - 263, largura - 84, 9)
        elif tipo_contrato == "Corporativo CLT" and indice_pagina == 0:
            _caixa_pdf(pdf, 35, 380, largura - 70, 310)
            _texto_pdf(pdf, "CONTRATO CORPORATIVO DE TRABALHO (CLT)", 42, altura - 175, largura - 84, 13, negrito=True)
            _texto_pdf(pdf, "DADOS DO COLABORADOR", 42, altura - 215, largura - 84, 11, negrito=True)
            linhas = [
                ("Nome Completo", dados.get("nome")), ("CPF", dados.get("cnpj")),
                ("RG", dados.get("rg_mei")), ("Endereço", endereco_completo),
                ("Telefone", dados.get("telefone")), ("E-mail", dados.get("email")),
                ("Cargo", dados.get("cargo")), ("Salário", dados.get("valor_contrato")),
            ]
            y = altura - 242
            for rotulo, valor in linhas:
                _texto_pdf(pdf, f"{rotulo}: {valor or ''}", 42, y, largura - 84, 9, max_linhas=2)
                y -= 25
        elif tipo_contrato == "Estágio" and indice_pagina == 1:
            _caixa_pdf(pdf, 35, 320, largura - 70, 280)
            _texto_pdf(pdf, "DADOS DO ESTAGIÁRIO", 42, altura - 275, largura - 84, 11, negrito=True)
            linhas = [
                ("Nome", dados.get("nome")), ("CPF", dados.get("cnpj")),
                ("Instituição de Ensino", dados.get("instituicao_ensino")),
                ("Curso", dados.get("curso")), ("Jornada", dados.get("jornada")),
                ("Endereço", endereco_completo), ("Telefone", dados.get("telefone")),
                ("E-mail", dados.get("email")),
            ]
            y = altura - 305
            for rotulo, valor in linhas:
                _texto_pdf(pdf, f"{rotulo}: {valor or ''}", 42, y, largura - 84, 9, max_linhas=2)
                y -= 23

        pdf.save()
        camada.seek(0)
        sobreposicao = PdfReader(camada)
        if sobreposicao.pages:
            pagina.merge_page(sobreposicao.pages[0])
        escritor.add_page(pagina)

    saida = io.BytesIO()
    escritor.write(saida)
    return anexar_clausulas_pdf(saida.getvalue(), dados.get("clausulas"), tipo_contrato)

def h(texto):
    return html.escape("" if texto is None else str(texto))

def mascarar_segredo(valor):
    return service_mascarar_segredo(valor)

def montar_codigo_entrada(fileira1, fileira2, identificacao):
    partes = [str(x or "").strip() for x in [fileira1, fileira2, identificacao]]
    return " | ".join([p for p in partes if p])

def preparar_tabela_estoque(rows):
    colunas = [
        ("id", "ID"), ("codigo", "Fileira 1"), ("categoria", "Fileira 2"),
        ("produto", "Fileira 3 / Identificação"), ("nome_generico", "Nome genérico"),
        ("codigo_entrada", "Código Interno"),
        ("caixa", "Caixa"), ("quantidade", "Qtd"), ("estoque_minimo", "Mínimo"),
        ("valor_custo", "Compra"), ("custo_deslocamento", "Deslocamento"),
        ("imposto_percentual", "Imposto %"), ("lucro_percentual", "Lucro %"),
        ("valor_venda", "Revenda"), ("preco_revenda_automatico", "Preço automático"),
        ("permitir_ajuste_preco", "Permite ajuste"), ("situacao_nota", "Documento da compra"),
        ("fornecedor", "Fornecedor"),
        ("observacoes", "Observações"),
    ]
    return [{titulo: dict(row).get(campo, "") for campo, titulo in colunas} for row in rows]

COLUNAS_ESTOQUE_IMPORTACAO = {
    "codigo": "Fileira 1",
    "categoria": "Fileira 2",
    "produto": "Produto / Identificação",
    "nome_generico": "Nome genérico",
    "codigo_entrada": "Código interno",
    "caixa": "Caixa / Gaveta",
    "quantidade": "Quantidade",
    "estoque_minimo": "Estoque mínimo",
    "valor_custo": "Valor de custo",
    "valor_venda": "Valor de venda",
    "fornecedor": "Fornecedor",
    "observacoes": "Observações",
}

COLUNAS_CLIENTES_IMPORTACAO = {
    "codigo_cliente": "Código do cliente",
    "tipo": "Classificação",
    "nome": "Nome / Empresa",
    "cnpj": "CPF / CNPJ",
    "rg_mei": "RG / Fantasia",
    "insc_estadual": "Inscrição Estadual",
    "insc_municipal": "Inscrição Municipal",
    "substituto_tributario": "Substituto tributário",
    "telefone": "Telefone principal",
    "telefone_secundario": "Telefone secundário",
    "email": "E-mail",
    "emails_cobranca": "E-mails de cobrança",
    "endereco": "Endereço",
    "numero": "Número",
    "complemento": "Complemento",
    "bairro": "Bairro",
    "cidade_estado": "Cidade / UF",
    "cep": "CEP",
    "pessoa": "Pessoa física / jurídica",
    "endereco_padrao": "Endereço padrão",
    "referencia": "Referência",
    "codigo_ibge": "Código IBGE / Cidade",
    "uf": "UF",
    "contato_padrao": "Contato padrão",
    "contato_cobranca": "Contato cobrança",
    "contato": "Contato",
    "estado_insc_estadual": "Estado da Inscrição Estadual",
    "data_nascimento": "Data de nascimento",
    "optante_simples_nacional": "Optante Simples Nacional",
    "ramo_atividade": "Ramo de atividade",
    "dias_antecedencia_faturamento": "Dias antecedência faturamento",
    "dia_faturamento": "Dia de faturamento",
    "dia_vencimento": "Dia de vencimento",
}

SINONIMOS_CLIENTES_IMPORTACAO = {
    "codigo_cliente": ["codigo cliente", "código cliente", "cod cliente", "id cliente"],
    "tipo": ["tipo", "classificacao", "classificação", "cliente fornecedor"],
    "nome": ["nome", "nome empresa", "empresa", "razao social", "razão social", "cliente"],
    "cnpj": ["cpf cnpj", "cpf", "cnpj", "documento"],
    "rg_mei": ["rg fantasia", "rg", "fantasia", "nome fantasia"],
    "insc_estadual": ["inscricao estadual", "inscrição estadual", "ie"],
    "insc_municipal": ["inscricao municipal", "inscrição municipal", "im"],
    "substituto_tributario": ["substituto tributario", "substituto tributário"],
    "telefone": ["telefone principal", "telefone", "celular", "fone"],
    "telefone_secundario": ["telefone secundario", "telefone secundário", "telefone 2", "celular 2"],
    "email": ["email", "e-mail"],
    "emails_cobranca": ["emails cobranca", "e-mails de cobrança", "email cobranca", "e-mail cobrança"],
    "endereco": ["endereco", "endereço", "logradouro", "rua"],
    "numero": ["numero", "número", "numero endereco", "nº"],
    "complemento": ["complemento"],
    "bairro": ["bairro"],
    "cidade_estado": ["cidade estado", "cidade uf", "cidade", "municipio", "município"],
    "cep": ["cep"],
    "pessoa": ["pessoa"],
    "endereco_padrao": ["endereco padrao", "endereço padrão"],
    "referencia": ["referencia", "referência"],
    "codigo_ibge": ["codigo ibge cidade", "código ibge cidade", "codigo ibge"],
    "uf": ["uf", "estado"],
    "contato_padrao": ["contato padrao", "contato padrão"],
    "contato_cobranca": ["contato cobranca", "contato cobrança"],
    "contato": ["contato"],
    "estado_insc_estadual": ["estado inscricao estadual", "estado inscrição estadual"],
    "data_nascimento": ["data de nascimento", "data nascimento", "nascimento"],
    "optante_simples_nacional": ["optante simples nacional", "simples nacional"],
    "ramo_atividade": ["ramo atividade", "ramo de atividade"],
    "dias_antecedencia_faturamento": ["dias antecedencia faturamento", "dias antecedência faturamento"],
    "dia_faturamento": ["dia faturamento", "dia de faturamento"],
    "dia_vencimento": ["dia vencimento", "dia de vencimento"],
}

SINONIMOS_ESTOQUE_IMPORTACAO = {
    "codigo": ["fileira 1", "localizacao", "localização"],
    "categoria": ["fileira 2", "categoria", "grupo"],
    "produto": ["fileira 3", "produto", "modelo", "item", "nome"],
    "nome_generico": ["nome generico", "nome genérico", "descricao", "descrição", "discriminacao", "discriminação"],
    "codigo_entrada": ["codigo", "código", "codigo interno", "código interno", "codigo entrada", "sku", "referencia", "referência"],
    "caixa": ["caixa", "gaveta", "local"],
    "quantidade": ["quantidade", "qtd", "qte", "estoque", "saldo"],
    "estoque_minimo": ["estoque minimo", "estoque mínimo", "minimo", "mínimo", "qtd minima", "qtd mínima"],
    "valor_custo": ["valor custo", "valor de custo", "custo", "preco custo", "preço custo"],
    "valor_venda": ["valor venda", "valor de venda", "venda", "preco venda", "preço venda"],
    "fornecedor": ["fornecedor", "fabricante", "marca"],
    "observacoes": ["observacoes", "observações", "obs", "observacao", "observação", "tem fonte"],
}

def normalizar_cabecalho_importacao(valor):
    texto = str(valor or "").strip().lower()
    texto = "".join(
        caractere for caractere in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caractere)
    )
    return re.sub(r"\s+", " ", texto)

def montar_registros_planilha(cabecalhos_brutos, linhas):
    cabecalhos = []
    usados = set()
    for idx, valor in enumerate(cabecalhos_brutos, start=1):
        nome = str(valor or f"Coluna {idx}").strip()
        nome_original = nome
        contador = 2
        while nome in usados:
            nome = f"{nome_original} ({contador})"
            contador += 1
        usados.add(nome)
        cabecalhos.append(nome)
    dados = []
    for linha in linhas:
        registro = {cabecalhos[i]: linha[i] for i in range(min(len(cabecalhos), len(linha)))}
        if any(valor not in (None, "") for valor in registro.values()):
            dados.append(registro)
    return cabecalhos, dados

def ler_planilha_importacao(arquivo):
    conteudo = arquivo.getvalue()
    inicio = conteudo.lstrip(b"\xef\xbb\xbf \r\n\t")
    if inicio.startswith(b"<?xml") or b"<Workbook" in inicio[:1000]:
        raiz = ET.fromstring(conteudo.decode("utf-8-sig"))
        ns = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
        tabela = raiz.find(".//ss:Worksheet/ss:Table", ns)
        linhas_xml = tabela.findall("ss:Row", ns) if tabela is not None else []
        linhas = []
        indice_xml = "{urn:schemas-microsoft-com:office:spreadsheet}Index"
        for linha_xml in linhas_xml:
            valores, posicao = [], 1
            for celula in linha_xml.findall("ss:Cell", ns):
                indice = celula.attrib.get(indice_xml)
                if indice:
                    while posicao < int(indice):
                        valores.append("")
                        posicao += 1
                dado = celula.find("ss:Data", ns)
                valores.append(dado.text if dado is not None and dado.text is not None else "")
                posicao += 1
            linhas.append(valores)
        return montar_registros_planilha(linhas[0] if linhas else [], linhas[1:])

    workbook = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    planilha = workbook[workbook.sheetnames[0]]
    linhas = planilha.iter_rows(values_only=True)
    cabecalhos_brutos = next(linhas, [])
    cabecalhos, dados = montar_registros_planilha(cabecalhos_brutos, linhas)
    workbook.close()
    return cabecalhos, dados

def ler_excel_estoque(arquivo):
    return ler_planilha_importacao(arquivo)

def sugerir_coluna_estoque(campo, cabecalhos):
    sinonimos = [normalizar_cabecalho_importacao(x) for x in SINONIMOS_ESTOQUE_IMPORTACAO.get(campo, [])]
    for cabecalho in cabecalhos:
        normalizado = normalizar_cabecalho_importacao(cabecalho)
        if normalizado in sinonimos or any(s in normalizado for s in sinonimos):
            return cabecalho
    return "-- Não importar --"

def sugerir_coluna_cliente(campo, cabecalhos):
    sinonimos = [normalizar_cabecalho_importacao(x) for x in SINONIMOS_CLIENTES_IMPORTACAO.get(campo, [])]
    for cabecalho in cabecalhos:
        normalizado = normalizar_cabecalho_importacao(cabecalho)
        if normalizado in sinonimos:
            return cabecalho
    for cabecalho in cabecalhos:
        normalizado = normalizar_cabecalho_importacao(cabecalho)
        if any(s in normalizado for s in sinonimos):
            return cabecalho
    return "-- Não relacionar --"

def inteiro_importacao(valor, padrao=0):
    try:
        if valor in (None, ""):
            return padrao
        return max(0, int(float(str(valor).replace(",", "."))))
    except Exception:
        return padrao

def texto_importacao(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()

def gerar_excel_tabela(rows, titulo):
    return service_gerar_excel_tabela(rows, titulo)

def preparar_tabela_compras(rows):
    colunas = [
        ("id", "ID"), ("data_pedido", "Data"), ("codigo", "Fileira 1"),
        ("categoria", "Fileira 2"), ("produto", "Fileira 3 / Identificação"),
        ("codigo_entrada", "Código Interno"), ("caixa", "Caixa"), ("quantidade_solicitada", "Qtd Solicitada"),
        ("fornecedor", "Fornecedor"), ("status", "Status"), ("observacoes", "Observações"),
    ]
    return [{titulo: dict(row).get(campo, "") for campo, titulo in colunas} for row in rows]

def injetar_mascaras():
    components.html("""
    <script>
    (function aplicarMascaras() {
        var doc = window.parent.document;

        function mask(el, fn) {
            if (!el || el.dataset.maskReady === '1') return;
            el.dataset.maskReady = '1';

            function aplicarMascara() {
                var val = el.value.replace(/\\D/g, '');
                if (!val) return;
                var formatted = fn(val);
                var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeSetter.call(el, formatted);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }

            el.addEventListener('input', function() {
                var pos = el.selectionStart || el.value.length;
                aplicarMascara();
                try { el.setSelectionRange(el.value.length, el.value.length); } catch (e) {}
            });
            el.addEventListener('blur', aplicarMascara);
        }

        function fmtCpfCnpj(v) {
            if (v.length <= 11) {
                v = v.slice(0,11);
                if (v.length > 9) return v.replace(/(\\d{3})(\\d{3})(\\d{3})(\\d{1,2})/, '$1.$2.$3-$4');
                if (v.length > 6) return v.replace(/(\\d{3})(\\d{3})(\\d{1,3})/, '$1.$2.$3');
                if (v.length > 3) return v.replace(/(\\d{3})(\\d{1,3})/, '$1.$2');
                return v;
            } else {
                v = v.slice(0,14);
                if (v.length > 12) return v.replace(/(\\d{2})(\\d{3})(\\d{3})(\\d{4})(\\d{1,2})/, '$1.$2.$3/$4-$5');
                if (v.length > 8)  return v.replace(/(\\d{2})(\\d{3})(\\d{3})(\\d{1,4})/, '$1.$2.$3/$4');
                if (v.length > 5)  return v.replace(/(\\d{2})(\\d{3})(\\d{1,3})/, '$1.$2.$3');
                if (v.length > 2)  return v.replace(/(\\d{2})(\\d{1,3})/, '$1.$2');
                return v;
            }
        }

        function fmtTel(v) {
            v = v.slice(0,11);
            if (v.length > 10) return v.replace(/(\\d{2})(\\d{5})(\\d{4})/, '($1) $2-$3');
            if (v.length > 6)  return v.replace(/(\\d{2})(\\d{4,5})(\\d{0,4})/, '($1) $2-$3');
            if (v.length > 2)  return v.replace(/(\\d{2})(\\d{0,5})/, '($1) $2');
            return v;
        }

        function fmtCep(v) {
            v = v.slice(0,8);
            if (v.length > 5) return v.replace(/(\\d{5})(\\d{1,3})/, '$1-$2');
            return v;
        }

        function encontrarInputPorLabel(labelsArray) {
            for (var a = 0; a < labelsArray.length; a++) {
                var byAria = doc.querySelector('input[aria-label="' + labelsArray[a].replace(/"/g, '\\"') + '"]');
                if (byAria) return byAria;
            }

            var els = doc.querySelectorAll('label p, label');
            for (var i = 0; i < els.length; i++) {
                var txt = els[i].textContent.trim();
                if (labelsArray.indexOf(txt) !== -1) {
                    var container = els[i].closest('[data-testid="stTextInput"]');
                    if (container) {
                        var inp = container.querySelector('input');
                        if (inp) return inp;
                    }
                }
            }
            return null;
        }

        function aplicar() {
            var cpfCnpj = encontrarInputPorLabel(['CPF/CNPJ:', 'CNPJ/CPF:', 'CPF/CNPJ']);
            var tel     = encontrarInputPorLabel(['Telefone Principal:', 'Telefone:', 'Telefone Principal']);
            var cep     = encontrarInputPorLabel(['CEP:']);

            if (cpfCnpj) mask(cpfCnpj, fmtCpfCnpj);
            if (tel)     mask(tel, fmtTel);
            if (cep)     mask(cep, fmtCep);

            setTimeout(aplicar, 1200);
        }
        setTimeout(aplicar, 600);
    })();
    </script>
    """, height=0)

def mudar_pagina(n): 
    st.session_state['pagina_atual'] = n
    st.session_state['pagina_atual_radio'] = n

def pode_acessar_item_navegacao(item):
    if item.get("somente_daniel"):
        return eh_admin_master()
    if item.get("prefixo") and tem_alguma_permissao(item["prefixo"]):
        return True
    if item.get("permite_chamados_atribuidos") and possui_chamados_atribuidos(st.session_state.get("username", "")):
        return True
    return any(tem_permissao(acao) for acao in item.get("acoes", []))

def modulos_navegacao_visiveis():
    modulos = []
    for modulo in MODULOS_NAVEGACAO:
        submodulos = [
            submodulo
            for submodulo in modulo.get("submodulos", [])
            if pode_acessar_item_navegacao(submodulo)
        ]
        if submodulos:
            modulos.append({**modulo, "submodulos": submodulos})
    return modulos

def paginas_disponiveis_usuario():
    if st.session_state.get("tipo_login") == "cliente":
        return ["Portal do Cliente"]

    paginas = ["Página Inicial"]
    for modulo in modulos_navegacao_visiveis():
        for submodulo in modulo["submodulos"]:
            pagina = submodulo["pagina"]
            if pagina not in paginas:
                paginas.append(pagina)
    return paginas

def renderizar_sidebar_navegacao():
    st.sidebar.markdown("**Navegação do Sistema:**")

    if "Página Inicial" in opcoes:
        tipo_botao = "primary" if st.session_state["pagina_atual"] == "Página Inicial" else "secondary"
        if st.sidebar.button("Página Inicial", key="nav_pagina_inicial", width="stretch", type=tipo_botao):
            mudar_pagina("Página Inicial")
            st.rerun()

    for modulo in modulos_navegacao_visiveis():
        modulo_ativo = any(sub["pagina"] == st.session_state["pagina_atual"] for sub in modulo["submodulos"])
        with st.sidebar.expander(f"{modulo['titulo']}", expanded=modulo_ativo):
            for submodulo in modulo["submodulos"]:
                pagina = submodulo["pagina"]
                tipo_botao = "primary" if pagina == st.session_state["pagina_atual"] else "secondary"
                if st.button(submodulo["titulo"], key=f"nav_{modulo['titulo']}_{pagina}", width="stretch", type=tipo_botao):
                    mudar_pagina(pagina)
                    st.rerun()

def renderizar_modulos_home():
    modulos = modulos_navegacao_visiveis()
    if not modulos:
        st.info("Nenhum módulo liberado para este usuário.")
        return

    estilos_modulo = {
        "Cadastros": "info",
        "Financeiro": "info",
        "Estoque": "success",
        "Serviços": "success",
        "Faturamento": "info",
        "ServiceDesk": "success",
        "Relatórios": "warning",
        "Acesso Softwares": "warning",
        "Cliente": "info",
    }

    for modulo in modulos:
        st.subheader(modulo["titulo"])
        cols = st.columns(3)
        for idx, submodulo in enumerate(modulo["submodulos"]):
            with cols[idx % 3]:
                estilo = estilos_modulo.get(modulo["titulo"], "info")
                getattr(st, estilo)(submodulo["titulo"])
                st.button(
                    submodulo.get("botao", f"Acessar {submodulo['titulo']}"),
                    width="stretch",
                    on_click=mudar_pagina,
                    args=(submodulo["pagina"],),
                    key=f"home_{modulo['titulo']}_{submodulo['pagina']}",
                )

def renderizar_agenda_usuario_home():
    usuario_logado = st.session_state.get("username", "")
    nome_funcionario = st.session_state.get("funcionario_nome", "")
    tecnicos_filtro = [usuario_logado]
    if nome_funcionario and nome_funcionario not in tecnicos_filtro:
        tecnicos_filtro.append(nome_funcionario)

    conn = conectar_banco()
    c = conn.cursor()
    placeholders = ",".join(["?"] * len(tecnicos_filtro))
    hoje = date.today().strftime("%Y-%m-%d")
    c.execute(
        f"""SELECT * FROM agenda_visitas
            WHERE tecnico IN ({placeholders})
              AND data_visita >= ?
              AND status NOT IN ('Concluído', 'Realizado', 'Cancelado')
            ORDER BY data_visita ASC, hora_inicio ASC
            LIMIT 8""",
        tecnicos_filtro + [hoje],
    )
    visitas = [dict(row) for row in c.fetchall()]
    conn.close()

    st.write("---")
    st.subheader("Minha Agenda")
    if not visitas:
        st.info("Você não tem visitas agendadas a partir de hoje.")
        return

    status_cores = {
        "Agendado": "#1a73e8",
        "Realizado": "#34a853",
        "Reagendado": "#fbbc05",
        "Adiado": "#fbbc05",
        "Atrasado": "#f29900",
        "Transferido": "#7b61ff",
        "Concluído": "#34a853",
        "Cancelado": "#ea4335",
    }

    for visita in visitas:
        cor = status_cores.get(visita.get("status"), "#777")
        data_br = visita.get("data_visita") or ""
        try:
            data_br = datetime.strptime(data_br, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            pass
        horario = visita.get("hora_inicio") or "Horário não definido"
        if visita.get("hora_fim"):
            horario = f"{horario} - {visita['hora_fim']}"
        st.markdown(
            f"""
<div style="border-left:5px solid {cor}; background:#f8f9fa; border-radius:6px; padding:12px 16px; margin-bottom:8px;">
  <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px;">
    <b>{visita.get('cliente_nome') or 'Cliente não informado'}</b>
    <span style="color:#555;">{data_br} | {horario}</span>
  </div>
  <div style="font-size:13px; color:#333; margin-top:4px;">
    <b>Status:</b> {visita.get('status') or ''} &nbsp;|&nbsp; <b>Tipo:</b> {visita.get('tipo_visita') or ''}
  </div>
  <div style="font-size:13px; color:#555; margin-top:4px;">{visita.get('descricao') or ''}</div>
</div>
""",
            unsafe_allow_html=True,
        )

def renderizar_chamados_usuario_home():
    username = (st.session_state.get("username") or "").strip()
    if not username or st.session_state.get("tipo_login") == "cliente":
        return

    conn = conectar_banco()
    c = conn.cursor()
    eh_daniel = username.lower() == "daniel.fabio"
    c.execute(
        """SELECT * FROM chamados_cliente
           WHERE (funcionario_designado=%s
                  OR (%s=0 AND COALESCE(funcionario_designado, '')='' AND COALESCE(area_destino, 'Suporte')='Suporte'))
             AND status NOT IN ('Concluído', 'Cancelado', 'Recusado pelo cliente')
           ORDER BY ajuste_data ASC, data_solicitada ASC, hora_inicio ASC
           LIMIT 10""",
        (username, int(eh_daniel)),
    )
    chamados = [dict(row) for row in c.fetchall()]
    conn.close()

    st.write("---")
    st.subheader("Meus chamados designados")
    if not chamados:
        st.info("Você não tem chamados designados no momento.")
        return

    for chamado in chamados:
        data_ch, inicio_ch, fim_ch, tipo_ch, descricao_ch = periodo_chamado(chamado)
        horario = f"{texto_data_br(data_ch)}"
        if inicio_ch or fim_ch:
            horario += f" das {inicio_ch or '--:--'} às {fim_ch or '--:--'}"
        cor_status = {
            "Novo": "#1a73e8",
            "Em análise": "#f29900",
            "Designado": "#7b61ff",
            "Em atendimento": "#34a853",
            "Modificado - aguardando aprovação": "#fbbc05",
        }.get(chamado.get("status"), "#777")
        st.markdown(
            f"""
<div style="border-left:5px solid {cor_status}; background:#f8f9fa; border-radius:6px; padding:12px 16px; margin-bottom:8px;">
  <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px;">
    <b>#{chamado.get('id')} - {chamado.get('cliente_nome') or 'Cliente não informado'}</b>
    <span style="color:#555;">{horario}</span>
  </div>
  <div style="font-size:13px; color:#333; margin-top:4px;">
    <b>Status:</b> {chamado.get('status') or 'Novo'} &nbsp;|&nbsp; <b>Área:</b> {chamado.get('area_destino') or 'Suporte'} &nbsp;|&nbsp; <b>Tipo:</b> {tipo_ch or ''}
  </div>
  <div style="font-size:13px; color:#555; margin-top:4px;"><b>Assunto:</b> {chamado.get('titulo') or 'Sem assunto'}</div>
  <div style="font-size:13px; color:#555; margin-top:4px;">{descricao_ch or ''}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        chamado_id = int(chamado.get("id"))
        selecionado = st.session_state.get("chamado_home_detalhes_id") == chamado_id
        if st.button(
            "Fechar informações" if selecionado else "Ver todas as informações",
            key=f"chamado_home_detalhes_{chamado_id}",
            width="stretch",
        ):
            st.session_state["chamado_home_detalhes_id"] = None if selecionado else chamado_id
            st.rerun()

        if selecionado:
            contato = buscar_contato_cliente(chamado.get("cliente_id"), chamado.get("cliente_nome") or "")
            with st.container(border=True):
                st.markdown(f"### Chamado #{chamado_id} — {chamado.get('titulo') or 'Sem assunto'}")
                d1, d2, d3 = st.columns(3)
                d1.write(f"**Cliente:** {chamado.get('cliente_nome') or 'Não informado'}")
                d1.write(f"**Solicitante:** {chamado.get('solicitante') or 'Não informado'}")
                d2.write(f"**Status:** {chamado.get('status') or 'Novo'}")
                d2.write(f"**Área:** {chamado.get('area_destino') or 'Suporte'}")
                d3.write(f"**Funcionário:** {chamado.get('funcionario_designado') or 'Não designado'}")
                d3.write(f"**Administrador:** {chamado.get('administrador') or 'Não informado'}")

                st.markdown("#### Atendimento atual")
                st.write(f"**Tipo:** {tipo_ch or 'Não informado'}")
                st.write(f"**Data e horário:** {texto_data_br(data_ch)} das {inicio_ch or '--:--'} às {fim_ch or '--:--'}")
                st.write(f"**Descrição:** {descricao_ch or 'Não informada'}")

                houve_ajuste = any(chamado.get(campo) for campo in (
                    "ajuste_tipo_atendimento", "ajuste_data", "ajuste_hora_inicio",
                    "ajuste_hora_fim", "ajuste_descricao",
                ))
                if houve_ajuste:
                    with st.expander("Ver solicitação original", expanded=False):
                        st.write(f"**Tipo solicitado:** {chamado.get('tipo_atendimento') or 'Não informado'}")
                        st.write(
                            f"**Data e horário solicitados:** {texto_data_br(chamado.get('data_solicitada'))} "
                            f"das {chamado.get('hora_inicio') or '--:--'} às {chamado.get('hora_fim') or '--:--'}"
                        )
                        st.write(f"**Descrição original:** {chamado.get('descricao') or 'Não informada'}")

                st.markdown("#### Contato e registro")
                c1, c2 = st.columns(2)
                c1.write(f"**Telefone:** {contato.get('telefone') or 'Não informado'}")
                c1.write(f"**E-mail:** {contato.get('email') or 'Não informado'}")
                c2.write(f"**Criado por:** {chamado.get('criado_por') or 'Não informado'}")
                c2.write(f"**Criado em:** {chamado.get('criado_em') or 'Não informado'}")
                c2.write(f"**Última atualização:** {chamado.get('atualizado_em') or 'Não informada'}")
                if chamado.get("resposta_cliente"):
                    st.write(f"**Resposta do cliente:** {chamado.get('resposta_cliente')}")

                st.markdown("#### Histórico da conversa")
                renderizar_chat_chamado(chamado, chamado.get("cliente_nome") or "Cliente")

def renderizar_alertas_home():
    hoje = date.today()
    limite_preventiva = hoje + timedelta(days=30)

    if tem_permissao("atendimentos.view"):
        conn = conectar_banco()
        c = conn.cursor()
        c.execute(
            """SELECT id, cliente_nome, equipamento, identificacao, quem_usa, periodo_preventiva, proxima_preventiva
               FROM atendimentos_intervencoes
               WHERE preventiva_prevista='Sim'
                 AND (preventiva_realizada IS NULL OR preventiva_realizada <> 'Sim' OR proxima_preventiva IS NOT NULL)
               ORDER BY id DESC"""
        )
        preventivas = filtrar_registros_por_empresa(c.fetchall(), "cliente_nome")
        conn.close()

        alertas_preventiva = []
        for item in preventivas:
            data_txt = item.get("proxima_preventiva") or ""
            try:
                data_prev = datetime.strptime(data_txt, "%d/%m/%Y").date()
            except Exception:
                continue
            if data_prev <= limite_preventiva:
                dias = (data_prev - hoje).days
                alertas_preventiva.append({
                    "ID": item.get("id"),
                    "Cliente": item.get("cliente_nome"),
                    "Equipamento": item.get("equipamento") or item.get("identificacao"),
                    "Quem usa": item.get("quem_usa"),
                    "Período": item.get("periodo_preventiva"),
                    "Próxima preventiva": data_txt,
                    "Status": "Vencida" if dias < 0 else f"Faltam {dias} dias",
                })

        if alertas_preventiva:
            st.warning("Preventivas vencidas ou faltando até 30 dias.")
            st.dataframe(alertas_preventiva, width="stretch", hide_index=True)

    if tem_permissao("estoque.view") or tem_permissao("estoque"):
        estoque_alerta = repo_listar_alertas_estoque_minimo(conectar_banco)

        if estoque_alerta:
            st.warning("Itens no estoque mínimo ou abaixo do mínimo.")
            st.dataframe(
                [{
                    "ID": item.get("id"),
                    "Código": item.get("codigo_entrada"),
                    "Produto": item.get("produto"),
                    "Categoria": item.get("categoria"),
                    "Qtd": item.get("quantidade"),
                    "Mínimo": item.get("estoque_minimo"),
                    "Fornecedor": item.get("fornecedor"),
                } for item in estoque_alerta],
                width="stretch",
                hide_index=True,
            )

    if tem_permissao("faturamento.view"):
        conn_sinc_rec = conectar_banco()
        try:
            sincronizar_lancamentos_recorrentes(
                conn_sinc_rec, hoje, st.session_state.get("username", ""), horizonte_dias=35
            )
        except Exception as ex:
            registrar_log_tecnico("ERROR", "cobrancas_recorrentes", "Falha ao gerar Contas a Receber", {"erro": str(ex)})
        finally:
            conn_sinc_rec.close()
        limite_cobranca = hoje + timedelta(days=30)
        conn = conectar_banco()
        c = conn.cursor()
        try:
            c.execute(
                """SELECT id, cliente_nome, tipo_cobranca, valor_cobranca, vigencia_fim, periodicidade, pagamento
                   FROM cobrancas_recorrentes
                   WHERE status='Ativa'
                   ORDER BY vigencia_fim ASC"""
            )
            cobrancas = filtrar_registros_por_empresa(c.fetchall(), "cliente_nome")
        except Exception:
            cobrancas = []
        conn.close()

        alertas_cobrancas = []
        for item in cobrancas:
            data_txt = item.get("vigencia_fim") or ""
            data_fim = parse_data_flex(data_txt)
            if not data_fim:
                continue
            if data_fim <= limite_cobranca:
                dias = (data_fim - hoje).days
                alertas_cobrancas.append({
                    "ID": item.get("id"),
                    "Cliente": item.get("cliente_nome"),
                    "Cobrança": item.get("tipo_cobranca"),
                    "Valor": formatar_moeda_br(item.get("valor_cobranca")),
                    "Periodicidade": item.get("periodicidade"),
                    "Pagamento": item.get("pagamento"),
                    "Fim da vigência": data_para_br(data_fim),
                    "Status": "Vencida" if dias < 0 else f"Faltam {dias} dias",
                })

        if alertas_cobrancas:
            st.warning("Cobranças recorrentes vencidas ou faltando até 30 dias.")
            st.dataframe(alertas_cobrancas, width="stretch", hide_index=True)

def registrar_acesso_cliente(cliente, evento):
    conn = conectar_banco()
    c = conn.cursor()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    try:
        ip = st.context.ip_address or ""
    except Exception:
        ip = ""
    c.execute(
        """INSERT INTO clientes_portal_acessos
           (cliente_id, cliente_nome, portal_username, evento, ip, criado_em)
           VALUES (?,?,?,?,?,?)""",
        (cliente.get("id"), cliente.get("nome"), cliente.get("portal_username"), evento, ip, agora),
    )
    if evento in {"login_ok", "primeiro_acesso_ok"}:
        c.execute("UPDATE clientes SET portal_ultimo_login=%s WHERE id=%s", (agora, cliente.get("id")))
        if cliente.get("portal_conta_id"):
            c.execute(
                "UPDATE clientes_portal_usuarios SET ultimo_login=%s WHERE id=%s",
                (agora, cliente.get("portal_conta_id")),
            )
    conn.commit()
    conn.close()

def concluir_login_cliente(cliente, evento="login_ok"):
    registrar_acesso_cliente(cliente, evento)
    registrar_evento_sistema("insert", "sistema", cliente.get("id"), cliente.get("nome"), {"evento": "Entrada no portal do cliente"})
    st.session_state["autenticado"] = True
    st.session_state["tipo_login"] = "cliente"
    st.session_state["username"] = cliente.get("portal_username") or ""
    st.session_state["cliente_id"] = cliente.get("id")
    st.session_state["cliente_nome"] = cliente.get("nome")
    st.session_state["portal_tipo_usuario"] = cliente.get("portal_tipo_usuario") or "Empresa"
    st.session_state["portal_usuario_nome"] = cliente.get("portal_usuario_nome") or cliente.get("nome")
    st.session_state["pagina_atual"] = "Portal do Cliente"
    st.session_state["pagina_atual_radio"] = "Portal do Cliente"
    for key in ["cliente_login_pendente", "cliente_2fa_secret_temp", "cliente_email_2fa_hash", "cliente_email_2fa_expira", "cliente_email_2fa_destino", "cliente_primeiro_acesso_senha_hash"]:
        st.session_state.pop(key, None)
    st.rerun()

def qr_totp_url(usuario, secret):
    return "https://quickchart.io/qr?size=220&text=" + quote(uri_totp_cliente(usuario, secret), safe="")

def renderizar_primeiro_acesso_cliente(cliente):
    st.title("Primeiro acesso do cliente")
    st.info("Por segurança, crie uma nova senha e configure o Google Authenticator.")

    nova_senha = st.text_input("Nova senha:", type="password")
    confirmar_senha = st.text_input("Confirmar nova senha:", type="password")
    secret_temp = st.session_state.get("cliente_2fa_secret_temp") or gerar_secret_2fa()
    st.session_state["cliente_2fa_secret_temp"] = secret_temp
    usuario_portal = cliente.get("portal_username") or st.session_state.get("cliente_login_pendente", {}).get("portal_username", "") or "cliente"
    st.write("Escaneie o QR Code no Google Authenticator e digite o código gerado.")
    st.image(qr_totp_url(usuario_portal, secret_temp), width=220)
    with st.expander("Não conseguiu escanear?"):
        st.code(secret_temp)

    if st.button("Validar senha e autenticador", width="stretch"):
        erros = []
        if len(nova_senha) < 8:
            erros.append("A nova senha precisa ter pelo menos 8 caracteres.")
        if nova_senha != confirmar_senha:
            erros.append("A confirmação da senha não confere.")
        if erros:
            for erro in erros:
                st.error(erro)
            return
        st.session_state["cliente_primeiro_acesso_senha_hash"] = criar_hash_senha(nova_senha)
        st.success("Senha validada. Digite abaixo o código do Google Authenticator.")

    codigo_2fa = st.text_input("Código do Google Authenticator:", max_chars=6)

    if st.button("Confirmar código e acessar", type="primary", width="stretch"):
        erros = []
        senha_hash = st.session_state.get("cliente_primeiro_acesso_senha_hash")
        if not senha_hash:
            erros.append("Clique em Validar senha e autenticador antes de confirmar.")
        if not verificar_totp(secret_temp, codigo_2fa):
            erros.append("Código inválido ou vencido.")
        if erros:
            for erro in erros:
                st.error(erro)
            return
        conn = conectar_banco()
        c = conn.cursor()
        if cliente.get("portal_conta_id"):
            c.execute(
                """UPDATE clientes_portal_usuarios
                   SET password=%s, trocar_senha=0, twofa_secret=%s, twofa_ativo=1
                   WHERE id=%s""",
                (senha_hash, secret_temp, cliente.get("portal_conta_id")),
            )
        else:
            c.execute(
                "UPDATE clientes SET portal_password=%s, portal_trocar_senha=0, portal_2fa_secret=%s, portal_2fa_ativo=1 WHERE id=%s",
                (senha_hash, secret_temp, cliente.get("id")),
            )
        conn.commit()
        conn.close()
        cliente["portal_username"] = cliente.get("portal_username") or st.session_state.get("cliente_login_pendente", {}).get("portal_username", "")
        concluir_login_cliente(cliente, "primeiro_acesso_ok")

def renderizar_2fa_cliente(cliente):
    st.title("Autenticação em duas etapas")
    st.write("Digite o código de 6 dígitos do Google Authenticator.")
    codigo = st.text_input("Código do Google Authenticator:", max_chars=6)
    if st.button("Confirmar acesso", type="primary", width="stretch"):
        if verificar_totp(cliente.get("portal_2fa_secret"), codigo):
            concluir_login_cliente(cliente)
        else:
            registrar_acesso_cliente(cliente, "totp_invalido")
            st.error("Código inválido ou vencido.")

def renderizar_cadastros_financeiros():
    if not tem_permissao("financeiro.cadastros"):
        st.error("Você não tem permissão para acessar estes cadastros.")
        return
    st.title("Cadastros Financeiros")
    tipos = ["Centro de custo", "Categoria financeira", "Plano de contas", "Imposto"]
    with st.form("form_cadastro_financeiro", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        tipo = c1.selectbox("Tipo:", tipos)
        nome = c2.text_input("Nome:")
        codigo = c3.text_input("Código:")
        observacoes = st.text_area("Observações:", height=80)
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
                conn.commit()
                conn.close()
                st.success("Cadastro financeiro salvo.")
                st.rerun()

    conn = conectar_banco()
    c = conn.cursor()
    c.execute("SELECT * FROM financeiro_cadastros_aux ORDER BY tipo, nome")
    registros = [dict(r) for r in c.fetchall()]
    conn.close()
    if registros:
        st.dataframe(registros, width="stretch", hide_index=True)
        if st.session_state.get("is_admin", 0):
            with st.expander("Editar / excluir cadastro"):
                id_aux = st.number_input("ID:", min_value=1, step=1, key="fin_aux_id")
                registro = next((r for r in registros if int(r.get("id") or 0) == int(id_aux)), None)
                if registro:
                    e1, e2, e3 = st.columns(3)
                    tipo_e = e1.selectbox("Tipo:", tipos, index=tipos.index(registro.get("tipo")) if registro.get("tipo") in tipos else 0, key="fin_aux_tipo_e")
                    nome_e = e2.text_input("Nome:", value=registro.get("nome") or "", key="fin_aux_nome_e")
                    codigo_e = e3.text_input("Código:", value=registro.get("codigo") or "", key="fin_aux_codigo_e")
                    ativo_e = st.selectbox("Ativo:", ["Sim", "Não"], index=0 if registro.get("ativo") != "Não" else 1, key="fin_aux_ativo_e")
                    obs_e = st.text_area("Observações:", value=registro.get("observacoes") or "", key="fin_aux_obs_e")
                    a1, a2 = st.columns(2)
                    if a1.button("Salvar alteração", type="primary", width="stretch", key="fin_aux_salvar_e"):
                        conn_e = conectar_banco()
                        ce = conn_e.cursor()
                        ce.execute("""UPDATE financeiro_cadastros_aux SET tipo=?, nome=?, codigo=?, ativo=?,
                                    observacoes=?, alterado_por=?, alterado_em=? WHERE id=?""",
                                   (tipo_e, nome_e, codigo_e, ativo_e, obs_e,
                                    st.session_state.get("username", ""), agora_br(), id_aux))
                        conn_e.commit()
                        conn_e.close()
                        st.success("Cadastro alterado.")
                        st.rerun()
                    if a2.button("Excluir cadastro", width="stretch", key="fin_aux_excluir_e"):
                        deletar_registro("financeiro_cadastros_aux", "id", id_aux)
                        st.success("Cadastro excluído.")
                        st.rerun()
    else:
        st.info("Nenhum cadastro financeiro registrado ainda.")

def renderizar_lancamentos_financeiros():
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

    tabela = []
    for r in sorted(registros_filtrados, key=lambda x: (parse_data_flex(x.get("data_vencimento")) or date.max, int(x.get("id") or 0))):
        parte = r.get("fornecedor") if r.get("origem") == "Pagar" else r.get("cliente")
        tabela.append({
            "Origem": r.get("origem"), "ID": r.get("id"), "Cliente/Fornecedor": parte,
            "Documento": r.get("numero_documento"), "Tipo": r.get("tipo_documento") or r.get("tipo_receita"),
            "Centro": r.get("centro_custo") or r.get("centro_receita"), "Categoria": r.get("categoria"),
            "Emissão": data_para_br(r.get("data_emissao")), "Vencimento": data_para_br(r.get("data_vencimento")),
            "Valor": formatar_moeda_br(r.get("valor_total")), "Baixado": formatar_moeda_br(r.get("valor_baixado")),
            "Status": r.get("status"),
        })
    if tabela:
        st.dataframe(tabela, width="stretch", hide_index=True)
        st.download_button("Exportar lançamentos", data=gerar_excel_tabela(tabela, "Lançamentos Financeiros"), file_name="lancamentos_financeiros.xls", mime="application/vnd.ms-excel", width="stretch")
    else:
        st.info("Nenhum lançamento encontrado.")

    if registros_filtrados:
        with st.expander("Baixa, baixa parcial ou cancelamento"):
            b1, b2, b3 = st.columns(3)
            origem_baixa = b1.selectbox("Origem:", ["Pagar", "Receber"], key="lan_fin_origem_baixa")
            id_baixa = b2.number_input("ID:", min_value=1, step=1, key="lan_fin_id_baixa")
            acao_baixa = b3.selectbox("Ação:", ["Baixa total", "Baixa parcial", "Cancelar"])
            tabela_baixa = "contas_pagar" if origem_baixa == "Pagar" else "contas_receber"
            registro = next((r for r in registros if r.get("origem") == origem_baixa and int(r.get("id") or 0) == int(id_baixa)), None)
            valor_padrao = float(registro.get("valor_total") or 0) if registro else 0.0
            valor_baixa = st.number_input("Valor da baixa R$:", min_value=0.0, value=valor_padrao, step=0.01, format="%.2f", disabled=acao_baixa == "Cancelar")
            motivo = st.text_area("Motivo/observação:")
            if st.button("Aplicar ação no lançamento", type="primary", key="lan_fin_aplicar_baixa"):
                if not registro:
                    st.error("Lançamento não encontrado.")
                elif acao_baixa == "Cancelar" and not motivo.strip():
                    st.error("Informe o motivo do cancelamento.")
                else:
                    novo_status = "Cancelado" if acao_baixa == "Cancelar" else ("Pago" if origem_baixa == "Pagar" else "Recebido")
                    if acao_baixa == "Baixa parcial":
                        novo_status = "Pago parcial" if origem_baixa == "Pagar" else "Recebido parcial"
                    conn_b = conectar_banco()
                    cb = conn_b.cursor()
                    if acao_baixa == "Cancelar":
                        cb.execute(f"""UPDATE {tabela_baixa} SET status=?, cancelado_por=?, motivo_cancelamento=?,
                                   alterado_por=?, alterado_em=? WHERE id=?""",
                                   (novo_status, st.session_state.get("username", ""), motivo,
                                    st.session_state.get("username", ""), agora_br(), id_baixa))
                    else:
                        cb.execute(f"""UPDATE {tabela_baixa} SET status=?, data_baixa=?, valor_baixado=?,
                                   observacao_baixa=?, baixado_por=?, alterado_por=?, alterado_em=? WHERE id=?""",
                                   (novo_status, data_para_banco_br(date.today()), valor_baixa, motivo,
                                    st.session_state.get("username", ""), st.session_state.get("username", ""), agora_br(), id_baixa))
                    conn_b.commit()
                    conn_b.close()
                    registrar_evento_sistema("update", tabela_baixa, id_baixa, registro.get("fornecedor") or registro.get("cliente") or "", {"acao": acao_baixa, "status": novo_status, "motivo": motivo})
                    st.success("Lançamento atualizado.")
                    st.rerun()

def renderizar_configuracoes_sistema():
    if not eh_admin_master():
        st.error("Acesso restrito ao Administrador Master.")
        return
    st.title("Configurações do Sistema")
    st.caption("Configurações salvas no banco, sem precisar alterar o código.")

    abas_cfg = st.tabs(["Empresa", "WhatsApp/E-mail", "NFS-e", "Serviços NFS-e", "Segurança"])
    with abas_cfg[0]:
        st.subheader("Dados da Dsystem")
        c1, c2, c3 = st.columns(3)
        cfg_nome = c1.text_input("Nome da empresa:", value=config_sistema_val("DSYSTEM_NOME", "Dsystem Tecnologia"))
        cfg_cnpj = c2.text_input("CNPJ:", value=config_sistema_val("NFSE_CNPJ", "23524449000154"))
        cfg_im = c3.text_input("Inscrição Municipal:", value=config_sistema_val("NFSE_INSCRICAO_MUNICIPAL", "07395930011"))
        e1, e2, e3 = st.columns(3)
        cfg_end = e1.text_input("Endereço:", value=config_sistema_val("DSYSTEM_ENDERECO", "Rua Glória, 25"))
        cfg_cidade = e2.text_input("Cidade/UF:", value=config_sistema_val("DSYSTEM_CIDADE_UF", "Sabará / MG"))
        cfg_base = e3.text_input("URL do sistema:", value=config_sistema_val("APP_BASE_URL", APP_BASE_URL))
        if st.button("Salvar dados da empresa", type="primary", width="stretch", key="cfg_salvar_empresa"):
            for chave, valor, desc in [
                ("DSYSTEM_NOME", cfg_nome, "Nome usado em documentos"),
                ("NFSE_CNPJ", cfg_cnpj, "CNPJ da Dsystem"),
                ("NFSE_INSCRICAO_MUNICIPAL", cfg_im, "Inscrição municipal"),
                ("DSYSTEM_ENDERECO", cfg_end, "Endereço da Dsystem"),
                ("DSYSTEM_CIDADE_UF", cfg_cidade, "Cidade/UF da Dsystem"),
                ("APP_BASE_URL", cfg_base, "URL pública do ERP"),
            ]:
                salvar_config_sistema(chave, valor, desc)
            st.success("Configurações da empresa salvas.")
            st.rerun()

    with abas_cfg[1]:
        st.subheader("Canais")
        w1, w2 = st.columns(2)
        cfg_whats = w1.text_input("WhatsApp oficial:", value=config_sistema_val("WHATSAPP_OFICIAL", WHATSAPP_OFICIAL))
        cfg_whats_api = w2.text_input("WhatsApp API:", value=config_sistema_val("WHATSAPP_API_NUMERO", WHATSAPP_API_NUMERO))
        s1, s2, s3 = st.columns(3)
        cfg_smtp_host = s1.text_input("SMTP host:", value=config_sistema_val("SMTP_HOST", SMTP_HOST))
        cfg_smtp_port = s2.text_input("SMTP porta:", value=config_sistema_val("SMTP_PORT", str(SMTP_PORT)))
        cfg_smtp_from = s3.text_input("SMTP remetente:", value=config_sistema_val("SMTP_FROM", SMTP_FROM))
        whats_preview = normalizar_whatsapp_config(cfg_whats)
        whats_api_preview = normalizar_whatsapp_config(cfg_whats_api)
        st.caption(f"WhatsApp oficial normalizado: {whats_preview or 'nao informado'} / API: {whats_api_preview or 'nao informado'}")
        if st.button("Salvar canais", type="primary", width="stretch", key="cfg_salvar_canais"):
            for chave, valor in [
                ("WHATSAPP_OFICIAL", whats_preview),
                ("WHATSAPP_API_NUMERO", whats_api_preview),
                ("SMTP_HOST", cfg_smtp_host),
                ("SMTP_PORT", cfg_smtp_port),
                ("SMTP_FROM", cfg_smtp_from),
            ]:
                salvar_config_sistema(chave, valor)
            st.success("Canais salvos.")

    with abas_cfg[2]:
        st.subheader("NFS-e")
        n1, n2, n3 = st.columns(3)
        cfg_amb = n1.selectbox("Ambiente:", ["homologacao", "producao"], index=0 if config_sistema_val("NFSE_AMBIENTE", "homologacao") != "producao" else 1)
        cfg_endpoint = n2.text_input("Endpoint/API:", value=config_sistema_val("NFSE_ENDPOINT_SOAP", NFSE_ENDPOINT_TESTE_NACIONAL))
        cfg_cert = n3.text_input("Caminho certificado PFX:", value=config_sistema_val("NFSE_CERT_PFX_PATH", config_val("NFSE_CERT_PFX_PATH", "")))
        n4, n5, n6 = st.columns(3)
        cfg_serie = n4.text_input("Serie padrao RPS:", value=config_sistema_val("NFSE_SERIE_RPS", "DS"))
        cfg_item = n5.text_input("Item lista servico padrao:", value=config_sistema_val("NFSE_ITEM_LISTA_SERVICO_PADRAO", ""))
        cfg_timeout = n6.number_input("Timeout SOAP (segundos):", min_value=5, max_value=180, value=int(float(config_sistema_val("NFSE_TIMEOUT", "30") or 30)), step=5)
        n7, n8 = st.columns(2)
        cfg_xsd = n7.text_input("Caminho XSD principal (opcional):", value=config_sistema_val("NFSE_XSD_PATH", ""))
        cfg_cert_password = n8.text_input("Senha certificado PFX:", value=config_sistema_val("NFSE_CERT_PASSWORD", config_val("NFSE_CERT_PASSWORD", "")), type="password")
        st.markdown("**Emissor Nacional (DPS)**")
        nn1, nn2, nn3 = st.columns(3)
        cfg_nfse_modo = nn1.selectbox(
            "Modo de emissao:",
            ["nacional", "municipal_soap"],
            index=0 if config_sistema_val("NFSE_MODO_EMISSAO", "nacional") != "municipal_soap" else 1,
        )
        cfg_codigo_municipio = nn2.text_input(
            "Codigo IBGE municipio emissor:",
            value=config_sistema_val("NFSE_CODIGO_MUNICIPIO", "3106200"),
        )
        cfg_serie_dps = nn3.number_input(
            "Serie DPS (aplicativo proprio):",
            min_value=1,
            max_value=49999,
            value=int(config_sistema_val("NFSE_DPS_SERIE", "1") or 1),
        )
        nn4, nn5, nn6 = st.columns(3)
        opcoes_simples = {
            "": "-- Selecione --",
            "1": "1 - Nao optante",
            "2": "2 - MEI",
            "3": "3 - ME/EPP",
        }
        simples_atual = str(config_sistema_val("NFSE_OP_SIMPLES_NACIONAL", "") or "")
        cfg_op_simples = nn4.selectbox(
            "Situacao no Simples Nacional:",
            list(opcoes_simples),
            format_func=lambda valor: opcoes_simples[valor],
            index=list(opcoes_simples).index(simples_atual) if simples_atual in opcoes_simples else 0,
        )
        cfg_reg_ap_simples = nn5.selectbox(
            "Regime de apuracao SN (ME/EPP):",
            ["", "1", "2", "3"],
            index=int(config_sistema_val("NFSE_REG_APURACAO_SIMPLES", "") or 0),
        )
        cfg_reg_esp = nn6.selectbox(
            "Regime especial municipal:",
            ["0", "1", "2", "3", "4", "5", "6", "9"],
            index=["0", "1", "2", "3", "4", "5", "6", "9"].index(str(config_sistema_val("NFSE_REGIME_ESPECIAL_NACIONAL", "0") or "0")),
        )
        cfg_endpoint_nacional = st.text_input(
            "Endpoint Nacional personalizado (deixe vazio para usar o oficial do ambiente):",
            value=config_sistema_val("NFSE_NACIONAL_ENDPOINT", ""),
        )
        if endpoint_nfse_nacional_rest(cfg_endpoint):
            st.warning(
                "A URL informada e da API Nacional REST da NFS-e. Ela usa DPS/JSON com certificado na conexao, "
                "nao SOAP/XML ABRASF. O botao atual de emissao SOAP precisa de um WebService municipal compativel."
            )
        st.caption("Para NFS-e Nacional, use o fluxo DPS/JSON. Para SOAP/XML ABRASF, informe o endpoint municipal correto.")
        if st.button("Salvar configuração NFS-e", type="primary", width="stretch", key="cfg_salvar_nfse"):
            validacao_nfse = validar_nfse_config({
                "NFSE_CNPJ": cfg_cnpj,
                "NFSE_INSCRICAO_MUNICIPAL": cfg_im,
                "NFSE_ENDPOINT_SOAP": cfg_endpoint,
            })
            if not validacao_nfse.ok:
                for mensagem in validacao_nfse.mensagens:
                    st.error(mensagem)
                st.stop()
            for chave, valor in [
                ("NFSE_AMBIENTE", cfg_amb),
                ("NFSE_ENDPOINT_SOAP", cfg_endpoint),
                ("NFSE_CERT_PFX_PATH", cfg_cert),
                ("NFSE_CERT_PASSWORD", cfg_cert_password),
                ("NFSE_SERIE_RPS", cfg_serie),
                ("NFSE_ITEM_LISTA_SERVICO_PADRAO", cfg_item),
                ("NFSE_XSD_PATH", cfg_xsd),
                ("NFSE_TIMEOUT", str(cfg_timeout)),
                ("NFSE_MODO_EMISSAO", cfg_nfse_modo),
                ("NFSE_CODIGO_MUNICIPIO", somente_digitos(cfg_codigo_municipio)),
                ("NFSE_DPS_SERIE", str(cfg_serie_dps)),
                ("NFSE_OP_SIMPLES_NACIONAL", cfg_op_simples),
                ("NFSE_REG_APURACAO_SIMPLES", cfg_reg_ap_simples),
                ("NFSE_REGIME_ESPECIAL_NACIONAL", cfg_reg_esp),
                ("NFSE_NACIONAL_ENDPOINT", cfg_endpoint_nacional),
            ]:
                salvar_config_sistema(chave, valor)
            st.success("Configuração de NFS-e salva.")

    with abas_cfg[3]:
        st.subheader("Lista de códigos de serviço")
        conn_serv = conectar_banco()
        cserv = conn_serv.cursor(dictionary=True)
        cserv.execute("SELECT * FROM nfse_bh_servicos ORDER BY ativo DESC, nome, id")
        servicos = cserv.fetchall()
        conn_serv.close()
        st.dataframe(servicos, width="stretch", hide_index=True)
        with st.form("cfg_form_servico_nfse", clear_on_submit=True):
            fs1, fs2, fs3, fs4 = st.columns(4)
            nome_serv = fs1.text_input("Nome:")
            codigo_serv = fs2.text_input("Código serviço:")
            item_serv = fs3.text_input("Item lista:")
            aliquota_serv = fs4.number_input("ISS %:", min_value=0.0, value=0.0, step=0.01, format="%.4f")
            obs_serv = st.text_input("Observação:")
            if st.form_submit_button("Adicionar serviço", type="primary", width="stretch"):
                conn_add = conectar_banco()
                cadd = conn_add.cursor()
                cadd.execute(
                    """INSERT INTO nfse_bh_servicos
                       (nome, codigo_servico, item_lista_servico, aliquota_iss, ativo, observacoes)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (nome_serv, codigo_serv, item_serv, aliquota_serv, "Sim", obs_serv),
                )
                conn_add.commit()
                conn_add.close()
                st.success("Serviço cadastrado.")
                st.rerun()

        if servicos:
            st.markdown("---")
            st.subheader("Editar ou excluir servico")
            opcoes_servicos = {
                f"#{serv.get('id')} - {serv.get('nome') or serv.get('codigo_servico') or 'Sem nome'}": serv
                for serv in servicos
            }
            serv_label = st.selectbox("Servico cadastrado:", list(opcoes_servicos.keys()), key="cfg_servico_editar_sel")
            serv_sel = opcoes_servicos[serv_label]
            ed1, ed2, ed3, ed4 = st.columns(4)
            ed_nome = ed1.text_input("Nome:", value=serv_sel.get("nome") or "", key="cfg_servico_ed_nome")
            ed_codigo = ed2.text_input("Codigo servico:", value=serv_sel.get("codigo_servico") or "", key="cfg_servico_ed_codigo")
            ed_item = ed3.text_input("Item lista:", value=serv_sel.get("item_lista_servico") or "", key="cfg_servico_ed_item")
            try:
                aliquota_atual = float(serv_sel.get("aliquota_iss") or 0)
            except Exception:
                aliquota_atual = 0.0
            ed_aliquota = ed4.number_input("ISS %:", min_value=0.0, value=aliquota_atual, step=0.01, format="%.4f", key="cfg_servico_ed_aliquota")
            ed_obs = st.text_input("Observacao:", value=serv_sel.get("observacoes") or "", key="cfg_servico_ed_obs")
            ed_ativo = st.selectbox("Ativo:", ["Sim", "Nao"], index=0 if (serv_sel.get("ativo") or "Sim") == "Sim" else 1, key="cfg_servico_ed_ativo")
            ac1, ac2 = st.columns(2)
            if ac1.button("Salvar alteracoes do servico", type="primary", width="stretch", key="cfg_servico_salvar_edicao"):
                conn_ed = conectar_banco()
                ced = conn_ed.cursor()
                ced.execute(
                    """UPDATE nfse_bh_servicos
                       SET nome=%s, codigo_servico=%s, item_lista_servico=%s,
                           aliquota_iss=%s, ativo=%s, observacoes=%s
                       WHERE id=%s""",
                    (ed_nome, ed_codigo, ed_item, ed_aliquota, ed_ativo, ed_obs, serv_sel.get("id")),
                )
                conn_ed.commit()
                conn_ed.close()
                st.success("Servico atualizado.")
                st.rerun()
            if ac2.button("Excluir servico", width="stretch", key="cfg_servico_excluir"):
                conn_del = conectar_banco()
                cdel = conn_del.cursor()
                cdel.execute("DELETE FROM nfse_bh_servicos WHERE id=%s", (serv_sel.get("id"),))
                conn_del.commit()
                conn_del.close()
                st.success("Servico excluido.")
                st.rerun()

        st.markdown("---")
        st.subheader("Codigos fiscais de produtos de informatica")
        st.caption("Referencias de NCM para produtos. Confirme com a contabilidade antes de emitir nota fiscal de produto.")
        conn_prod_cod = conectar_banco()
        cprod_cod = conn_prod_cod.cursor(dictionary=True)
        cprod_cod.execute("SELECT nome, ncm, categoria, ativo, observacoes FROM codigos_fiscais_produtos ORDER BY nome")
        codigos_produtos = cprod_cod.fetchall()
        conn_prod_cod.close()
        st.dataframe(codigos_produtos, width="stretch", hide_index=True)

    with abas_cfg[4]:
        st.subheader("Tentativas de login")
        conn_login = conectar_banco()
        clog = conn_login.cursor(dictionary=True)
        clog.execute("SELECT * FROM tentativas_login ORDER BY id DESC LIMIT 300")
        tentativas = clog.fetchall()
        conn_login.close()
        st.dataframe(tentativas, width="stretch", hide_index=True)

def renderizar_backups_sistema():
    return page_renderizar_backups_sistema(eh_admin_master, registrar_log_tecnico, tamanho_arquivo_legivel, DB_NAME)


def renderizar_diagnostico_sistema():
    return page_renderizar_diagnostico_sistema(
        eh_admin_master=eh_admin_master,
        conectar_banco=conectar_banco,
        db_name=DB_NAME,
        dsystem_static_dir=DSYSTEM_STATIC_DIR,
        whatsapp_oficial=WHATSAPP_OFICIAL,
        smtp_host=SMTP_HOST,
        smtp_from=SMTP_FROM,
        gerar_excel_tabela=gerar_excel_tabela,
        tamanho_arquivo_legivel=tamanho_arquivo_legivel,
        app_dir=Path(__file__).resolve().parent,
    )

if 'autenticado' not in st.session_state: 
    st.session_state['autenticado'] = False

if 'pagina_atual' not in st.session_state: 
    st.session_state['pagina_atual'] = "Página Inicial"

def login():
    usuario_troca = st.session_state.get("usuario_troca_senha_pendente")
    if usuario_troca:
        exibir_logo_dsystem("190")
        st.title("Definir nova senha")
        st.info(f"Primeiro acesso do usuário {usuario_troca.get('username')}. Troque a senha temporária para continuar.")
        nova_senha = st.text_input("Nova senha:", type="password", key="usuario_nova_senha")
        confirmar_nova = st.text_input("Confirmar nova senha:", type="password", key="usuario_confirmar_nova_senha")
        if st.button("Salvar nova senha e entrar", type="primary", width="stretch"):
            if len(nova_senha) < 6:
                st.error("A nova senha precisa ter pelo menos 6 caracteres.")
            elif nova_senha != confirmar_nova:
                st.error("As senhas não conferem.")
            elif nova_senha == "1234":
                st.error("Escolha uma senha diferente da senha temporária.")
            else:
                conn_troca = conectar_banco(); ct = conn_troca.cursor()
                ct.execute("UPDATE usuarios SET password=?, trocar_senha=0 WHERE id=?", (criar_hash_senha(nova_senha), usuario_troca.get("id")))
                conn_troca.commit(); conn_troca.close()
                for key, value in usuario_troca.items():
                    if key != "password":
                        st.session_state[key] = value
                st.session_state["trocar_senha"] = 0
                st.session_state["autenticado"] = True
                st.session_state.pop("usuario_troca_senha_pendente", None)
                registrar_evento_sistema("update", "usuarios", usuario_troca.get("id"), "", {"evento": "Senha temporária alterada"})
                st.rerun()
        return

    cliente_pendente = st.session_state.get("cliente_login_pendente")
    if cliente_pendente:
        exibir_logo_dsystem("190")
        if int(cliente_pendente.get("portal_trocar_senha") or 0) or not int(cliente_pendente.get("portal_2fa_ativo") or 0):
            renderizar_primeiro_acesso_cliente(cliente_pendente)
        else:
            renderizar_2fa_cliente(cliente_pendente)
        return

    exibir_logo_dsystem("210")
    st.title("Acesso ao Sistema Dsystem ERP")
    with st.container():
        user = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        
        if st.button("Entrar no Sistema", type="primary"):
            conn = conectar_banco()
            c = conn.cursor(dictionary=True)
            c.execute("SELECT * FROM usuarios WHERE username=%s", (user,))
            row = c.fetchone()
            
            if row is not None and verificar_senha(password, row.get("password", "")):
                if not senha_esta_com_hash(row.get("password", "")):
                    c.execute("UPDATE usuarios SET password=%s WHERE id=%s", (criar_hash_senha(password), row["id"]))
                    conn.commit()
                    row["password"] = ""
                if int(row.get("trocar_senha") or 0):
                    conn.close()
                    st.session_state["usuario_troca_senha_pendente"] = dict(row)
                    st.rerun()
                conn.close()
                row_dict = row
                for key, value in row_dict.items():
                    if key == "password":
                        continue
                    st.session_state[key] = value
                st.session_state['autenticado'] = True
                registrar_tentativa_login(user, "usuario", True, "Login do sistema autorizado")
                registrar_evento_sistema("insert", "sistema", row.get("id"), "", {"evento": "Entrada no sistema"})
                st.rerun()
            else:
                usuario_portal_busca = user.strip().lower()
                documento_login = normalizar_documento_cliente(user)
                if len(documento_login) in (11, 14):
                    usuario_portal_busca = documento_login
                c.execute("SELECT * FROM clientes WHERE LOWER(portal_username)=%s", (usuario_portal_busca,))
                cliente = c.fetchone()
                if cliente is None:
                    c.execute(
                        """SELECT p.id AS portal_conta_id, p.username, p.nome AS portal_usuario_nome,
                                  p.tipo AS portal_tipo_usuario, p.password AS conta_password,
                                  p.trocar_senha, p.twofa_secret, p.twofa_ativo, c.*
                           FROM clientes_portal_usuarios p
                           INNER JOIN clientes c ON c.id=p.cliente_id
                           WHERE LOWER(p.username)=%s AND p.ativo=1 LIMIT 1""",
                        (usuario_portal_busca,),
                    )
                    conta_funcionario = c.fetchone()
                    if conta_funcionario is not None:
                        cliente = dict(conta_funcionario)
                        cliente["portal_username"] = conta_funcionario.get("username")
                        cliente["portal_password"] = conta_funcionario.get("conta_password")
                        cliente["portal_trocar_senha"] = conta_funcionario.get("trocar_senha")
                        cliente["portal_2fa_secret"] = conta_funcionario.get("twofa_secret")
                        cliente["portal_2fa_ativo"] = conta_funcionario.get("twofa_ativo")
                if cliente is not None and verificar_senha(password, cliente.get("portal_password", "")):
                    if not senha_esta_com_hash(cliente.get("portal_password", "")):
                        if cliente.get("portal_conta_id"):
                            c.execute(
                                "UPDATE clientes_portal_usuarios SET password=%s WHERE id=%s",
                                (criar_hash_senha(password), cliente["portal_conta_id"]),
                            )
                        else:
                            c.execute("UPDATE clientes SET portal_password=%s WHERE id=%s", (criar_hash_senha(password), cliente["id"]))
                        conn.commit()
                        cliente["portal_trocar_senha"] = 1
                    conn.close()
                    registrar_tentativa_login(user, "cliente", True, "Login do portal autorizado")
                    st.session_state["cliente_login_pendente"] = dict(cliente)
                    st.rerun()
                else:
                    if cliente is not None:
                        registrar_acesso_cliente(cliente, "senha_invalida")
                    registrar_tentativa_login(user, "usuario" if row is not None else "cliente", False, "Usuário ou senha incorretos")
                    conn.close()
                    st.error("Usuário ou senha incorretos.")


def tocar_campainha_alerta():
    """Toca um alarme WAV nativo, com melhor compatibilidade entre navegadores."""
    st.audio(gerar_audio_alarme(), format="audio/wav", autoplay=True)


@st.cache_data
def gerar_audio_alarme():
    taxa = 22050
    amostras = []
    sequencia = ((880, 0.20), (0, 0.08), (1320, 0.24), (0, 0.12)) * 3
    for frequencia, duracao in sequencia:
        quantidade = int(taxa * duracao)
        for indice in range(quantidade):
            if not frequencia:
                valor = 0
            else:
                envelope = min(1.0, indice / 250, (quantidade - indice) / 250)
                valor = int(15000 * envelope * math.sin(2 * math.pi * frequencia * indice / taxa))
            amostras.append(valor)
    arquivo = io.BytesIO()
    with wave.open(arquivo, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(taxa)
        wav.writeframes(struct.pack(f"<{len(amostras)}h", *amostras))
    return arquivo.getvalue()


@st.fragment(run_every="15s")
def renderizar_central_atendimentos_global():
    """Mantém chamados e agenda visíveis em todas as telas internas."""
    if not st.session_state.get("autenticado") or st.session_state.get("tipo_login") == "cliente":
        return
    try:
        conn_alerta = conectar_banco()
        cur_alerta = conn_alerta.cursor()
        cur_alerta.execute("SELECT id, cliente_nome, titulo, status, criado_em FROM chamados_cliente ORDER BY id DESC LIMIT 100")
        chamados = [dict(item) for item in cur_alerta.fetchall()]
        hoje_iso = agora_sao_paulo().strftime("%Y-%m-%d")
        cur_alerta.execute(
            "SELECT id, tecnico, cliente_nome, data_visita, hora_inicio, status FROM agenda_visitas WHERE data_visita >= ? ORDER BY data_visita, hora_inicio LIMIT 200",
            (hoje_iso,),
        )
        agenda = [dict(item) for item in cur_alerta.fetchall()]
        conn_alerta.close()
    except Exception as ex:
        registrar_log_tecnico("WARNING", "alertas_atendimento", "Não foi possível atualizar os alertas", {"erro": str(ex)})
        return

    abertos = [item for item in chamados if chamado_esta_aberto(item)]
    novos_chamados, maior_chamado = ids_novos(chamados, st.session_state.get("alerta_ultimo_chamado_id"))
    novos_agendamentos, maior_agenda = ids_novos(agenda, st.session_state.get("alerta_ultimo_agenda_id"))
    st.session_state["alerta_ultimo_chamado_id"] = maior_chamado
    st.session_state["alerta_ultimo_agenda_id"] = maior_agenda

    proximos = agendamentos_proximos(agenda, agora_sao_paulo(), minutos=30)
    lembrados = set(st.session_state.get("alerta_agenda_lembrados", []))
    novos_lembretes = [item for item in proximos if int(item.get("id") or 0) not in lembrados]
    lembrados.update(int(item.get("id") or 0) for item in novos_lembretes)
    st.session_state["alerta_agenda_lembrados"] = sorted(lembrados)

    disparar_som = bool(novos_chamados or novos_agendamentos or novos_lembretes)
    alerta_ativo = bool(abertos or proximos)
    st.markdown(
        """
        <style>
        @keyframes dsystem-alarme-pulso {
          0%, 100% { transform: scale(1); box-shadow: 0 0 0 rgba(255, 59, 48, 0); }
          50% { transform: scale(1.008); box-shadow: 0 0 22px rgba(255, 59, 48, .55); }
        }
        .dsystem-alarme {
          padding: 14px 18px; border-radius: 10px; margin-bottom: 8px;
          font-size: 1.08rem; font-weight: 800; border: 2px solid #ff3b30;
          background: linear-gradient(90deg, #5b1717, #2f1518); color: #fff;
          animation: dsystem-alarme-pulso 1.15s ease-in-out infinite;
        }
        .dsystem-alarme-inativo {
          padding: 12px 16px; border-radius: 10px; margin-bottom: 8px;
          font-weight: 700; border: 1px solid #315b7d; background:#132333; color:#d8ecff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        titulo = f"🔔 Atendimento — {len(abertos)} solicitação(ões) em aberto"
        classe_alerta = "dsystem-alarme" if alerta_ativo else "dsystem-alarme-inativo"
        st.markdown(f'<div class="{classe_alerta}">{titulo}</div>', unsafe_allow_html=True)
        if novos_chamados:
            st.warning(f"Chegou {len(novos_chamados)} nova(s) solicitação(ões) de atendimento.")
        if novos_agendamentos:
            st.info(f"Foi realizado {len(novos_agendamentos)} novo(s) agendamento(s) na agenda.")
        for item in novos_lembretes:
            st.warning(
                f"Agendamento próximo: {item.get('cliente_nome') or 'Cliente'} às "
                f"{item.get('hora_inicio') or '--:--'} com {item.get('tecnico') or 'técnico não definido'}."
            )
        if abertos:
            resumo = " • ".join(
                f"#{item.get('id')} {item.get('cliente_nome') or 'Cliente'} — {item.get('titulo') or 'Sem assunto'}"
                for item in abertos[:3]
            )
            st.caption(resumo)
        elif not proximos:
            st.caption("Nenhuma solicitação aberta ou compromisso próximo neste momento.")
        testar_som = st.button("🔊 Testar som do alarme", key="testar_som_alerta_global")
        st.caption("Som automático ativado para novos chamados, novos agendamentos e lembretes próximos do horário.")
    if disparar_som or testar_som:
        tocar_campainha_alerta()

restaurar_portal_por_sid()

if not st.session_state['autenticado']: 
    login()
    st.stop()

if st.session_state.get("tipo_login") == "cliente" and (obter_query_param("pagina").lower() == "portal" or obter_query_param("chamado")):
    st.session_state["pagina_atual"] = "Portal do Cliente"
    st.session_state["pagina_atual_radio"] = "Portal do Cliente"
    st.session_state["chamado_destacado"] = obter_query_param("chamado")
    st.session_state["acao_portal"] = obter_query_param("acao")

renderizar_central_atendimentos_global()

def logout():
    registrar_evento_sistema("Saída", "sistema", st.session_state.get("id", ""), st.session_state.get("cliente_nome", ""), {"evento": "Saída do sistema"})
    for key in list(st.session_state.keys()): 
        del st.session_state[key]
    st.rerun()

if st.session_state.get("tipo_login") == "cliente":
    st.markdown("""
<style>
[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
.block-container { padding-top: 1rem; max-width: 100% !important; }
</style>
""", unsafe_allow_html=True)
    st.session_state["pagina_atual"] = "Portal do Cliente"
    st.session_state["pagina_atual_radio"] = "Portal do Cliente"
    opcoes = ["Portal do Cliente"]
    menu = "Portal do Cliente"
else:
    st.sidebar.markdown(
        f'<div style="text-align:center; margin:4px 0 12px;">{logo_dsystem_html("150")}</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.title(f"Usuário: {st.session_state.get('username', 'Usuário')}")
    st.sidebar.write("---")

    opcoes = paginas_disponiveis_usuario()

    if st.session_state['pagina_atual'] not in opcoes:
        st.session_state['pagina_atual'] = opcoes[0]
        st.session_state['pagina_atual_radio'] = opcoes[0]

    renderizar_sidebar_navegacao()
    st.sidebar.write("<br><br>", unsafe_allow_html=True)

    if st.sidebar.button("Sair do Sistema"):
        logout()

    menu = st.session_state['pagina_atual']

if menu == "Log do Sistema":
    renderizar_log_sistema()

elif menu == "Backups do Sistema":
    renderizar_backups_sistema()

elif menu == "Diagnóstico do Sistema":
    renderizar_diagnostico_sistema()

elif menu == "Configurações do Sistema":
    renderizar_configuracoes_sistema()

elif menu == "Página Inicial":
    st.title("Visão Geral do Sistema")
    renderizar_agenda_usuario_home()
    renderizar_chamados_usuario_home()
    renderizar_alertas_home()
    renderizar_modulos_home()

elif menu == "Contas a Pagar":
    renderizar_conta_financeira("pagar")

elif menu == "Contas a Receber":
    renderizar_conta_financeira("receber")

elif menu == "Lançamentos Financeiros":
    renderizar_lancamentos_financeiros()

elif menu == "Cadastros Financeiros":
    renderizar_cadastros_financeiros()

elif menu == "Cadastro de Cliente/Fornecedor":
    page_renderizar_cadastro_cliente_fornecedor(criar_app_context(globals()))

elif menu == PAGINA_INFRAESTRUTURA:
    page_renderizar_infraestrutura_ti(criar_app_context(globals()))

elif menu == "Gestão de E-mails":
    page_renderizar_gestao_emails(criar_app_context(globals()))

elif menu == PAGINA_ESTOQUE:
    page_renderizar_estoque(criar_app_context(globals()))

elif menu == "Compras e Cotações":
    page_renderizar_compras(criar_app_context(globals()))

elif menu == "Contratos":
    page_renderizar_contratos(criar_app_context(globals()))

elif menu == "Recepção e Kanban":
    page_renderizar_recepcao_kanban(criar_app_context(globals()))

elif menu == "Acesso Softwares":
    page_renderizar_acesso_softwares(criar_app_context(globals()))

elif menu == "Portal do Cliente":
    page_renderizar_portal_cliente(criar_app_context(globals()))

elif menu == "Gerenciador de Usuários":
    page_renderizar_gerenciador_usuarios(criar_app_context(globals()))

elif menu == "Gerador de Orçamentos":
    page_renderizar_gerador_orcamentos(criar_app_context(globals()))

elif menu == "Ordem de Serviço (OS)":
    page_renderizar_ordem_servico(criar_app_context(globals()))

elif menu == PAGINA_FATURAMENTO:
    page_renderizar_a_faturar(criar_app_context(globals()))

elif menu == "Faturado":
    page_renderizar_faturado(criar_app_context(globals()))

elif menu == "Cobranças":
    page_renderizar_cobrancas(criar_app_context(globals()))

elif menu == "Atendimentos e Checklists":
    page_renderizar_atendimentos_checklists(criar_app_context(globals()))
