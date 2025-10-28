import streamlit as st
import pandas as pd
import requests
import os
from orcamentobr import despesa_detalhada
import locale

# --- Configuração da Página e Título ---
st.set_page_config(page_title="Dashboard FDEPM", layout="wide")
st.title("Dashboard de Execução - FDEPM")
st.markdown("Fundo de Desenvolvimento do Ensino Profissional Marítimo")

# --- Constante principal do dashboard ---
UO_FDEPM_COD = "52133"  # Unidade Orçamentária do FDEPM

# --- Funções de Formatação e Busca ---
def formatar_moeda(valor):
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
        return locale.currency(valor, grouping=True)
    except:
        return f"R$ {valor:,.2f}"

# --- FUNÇÃO 1: BUSCAR DESPESAS (via orcamentobr) ---
@st.cache_data
def buscar_despesas(ano, uo_cod):
    st.write(f"Buscando despesas para UO {uo_cod} no ano {ano}...")
    try:
        df = despesa_detalhada(
            exercicio=ano,
            uo=uo_cod,
            gnd=True,
            acao=True,
            fonte=True,
            inclui_descricoes=True,
            ignore_secure_certificate=True
        )
        return df
    except Exception as e:
        # Se o SIOP falhar, também mostra o erro real
        st.exception(e)
        return pd.DataFrame()

# --- FUNÇÃO 2: BUSCAR RECEITAS (via Portal da Transparência) ---
@st.cache_data
def buscar_receitas(ano, orgao_cod, api_key):
    st.write(f"Buscando receitas para Órgão {orgao_cod} no ano {ano}...") 
    URL_BASE = "https://api.portaldatransparencia.gov.br/api-de-dados/receitas/por-orgao"
    HEADERS = {"chave-api-dados": api_key}
    
    pagina = 1
    dados_receita_total = []
    
    while True:
        params = {
            "anoExercicio": ano,
            "codigoOrgao": orgao_cod, 
            "pagina": pagina
        }
        
        try:
            response = requests.get(URL_BASE, headers=HEADERS, params=params)
            
            # --- MUDANÇA PRINCIPAL AQUI ---
            # Vamos deixar o .raise_for_status() apanhar TODOS os erros
            # (incluindo 401, 403, 500, etc.)
            response.raise_for_status() 
            
            dados_pagina = response.json()
            
            if not dados_pagina:
                break  
                
            dados_receita_total.extend(dados_pagina)
            pagina += 1
            
        except requests.exceptions.RequestException as e:
            # --- E AQUI ---
            # Em vez de st.error(), usamos st.exception()
            # Isto vai imprimir o erro completo no dashboard
            st.error("Ocorreu um erro técnico ao consultar a API:")
            st.exception(e)
            return pd.DataFrame()
            
    return pd.DataFrame(dados_receita_total)

# --- Interface do Usuário (Barra Lateral) ---
st.sidebar.header("Filtros")
ano_selecionado = st.sidebar.number_input("Selecione o Ano", min_value=2010, max_value=2025, value=2024)

st.sidebar.subheader("Autenticação")
api_key_input = st.sidebar.text_input(
    "Cole sua 'chave-api-dados' aqui:",
    type="password",  
    help="Necessário para consultar a aba 'Receitas'"
)

# --- Cria as Abas ---
tab_desp, tab_rec = st.tabs(["📊 Despesas", "💰 Receitas"])

# --- Lógica do Botão ---
if st.sidebar.button("Consultar"):

    # --- ABA 1: PAINEL DE DESPESAS ---
    with tab_desp:
        # (Código da aba de despesas mantido)
        with st.spinner(f"Buscando dados de DESPESA para {ano_selecionado}..."):
            df_desp = buscar_despesas(ano_selecionado, UO_FDEPM_COD)
            if not df_desp.empty:
                st.subheader("Visão Geral das Despesas (Execução)")
                dotacao = df_desp['loa_mais_credito'].sum()
                empenhado = df_desp['empenhado'].sum()
                pago = df_desp['pago'].sum()
                col1, col2, col3 = st.columns(3)
                col1.metric("Dotação Atualizada", formatar_moeda(dotacao))
                col2.metric("Empenhado", formatar_moeda(empenhado))
                col3.metric("Pago", formatar_moeda(pago))
                st.divider()
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.markdown("#### Despesas por Ação Orçamentária")
                    acao_data = df_desp.groupby('Acao_desc')['empenhado'].sum().reset_index()
                    acao_data = acao_data.sort_values('empenhado', ascending=False)
                    st.bar_chart(acao_data, x='Acao_desc', y='empenhado')
                with col_g2:
                    st.markdown("#### Despesas por Natureza (GND)")
                    gnd_data = df_desp.groupby('GND_desc')['empenhado'].sum().reset_index()
                    gnd_data = gnd_data.sort_values('empenhado', ascending=False)
                    st.bar_chart(gnd_data, x='GND_desc', y='empenhado')
                st.dataframe(df_desp)
            else:
                st.warning("Nenhum dado de DESPESA encontrado para este ano.")

    # --- ABA 2: PAINEL DE RECEITAS ---
    with tab_rec:
        if not api_key_input:
            st.warning("Por favor, insira sua 'chave-api-dados' na barra lateral para consultar as receitas.")
        else:
            api_key_tratada = api_key_input.strip() # Mantemos a limpeza de espaços
            
            if not api_key_tratada:
                 st.warning("A chave inserida estava vazia ou continha apenas espaços.")
            else:
                st.info(f"Testando com a chave que começa com: '{api_key_tratada[:4]}...'")
                with st.spinner(f"Buscando dados de RECEITA para {ano_selecionado}..."):
                    df_rec = buscar_receitas(ano_selecionado, UO_FDEPM_COD, api_key_tratada)
                    
                    if not df_rec.empty:
                        # (Código da aba de receitas mantido)
                        st.subheader("Visão Geral das Receitas (Arrecadação)")
                        prevista = df_rec['valorPrevisto'].sum()
                        realizada = df_rec['valorRealizado'].sum()
                        col_r1, col_r2 = st.columns(2)
                        col_r1.metric("Receita Prevista", formatar_moeda(prevista))
                        col_r2.metric("Receita Realizada (Arrecadado)", formatar_moeda(realizada))
                        st.divider()
                        st.markdown("#### Receitas por Origem (Categoria Primária)")
                        rec_data = df_rec.groupby('descricaoPrimaria')['valorRealizado'].sum().reset_index()
                        rec_data = rec_data.sort_values('valorRealizado', ascending=False)
                        st.bar_chart(rec_data, x='descricaoPrimaria', y='valorRealizado')
                        st.dataframe(df_rec)
                    
                    else:
                        st.warning("Nenhum dado de RECEITA encontrado. Verifique o ano ou a chave da API.")
else:
    st.info("Por favor, selecione o ano, insira sua chave da API e clique em 'Consultar'.")
              
