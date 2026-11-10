import pandas as pd
import numpy as np
import re
import unicodedata
import argparse
import os
from thefuzz import process

parser = argparse.ArgumentParser(description="Motor ETL - Integração Espacial de Crimes e IBGE")
parser.add_argument('-c', '--crimes', type=str, help="Caminho do ficheiro de ocorrências criminais (.xlsx ou .csv)")
parser.add_argument('-p', '--populacao', type=str, help="Caminho do ficheiro de população (.xlsx ou .csv)")
parser.add_argument('-s', '--saida', type=str, default='banco_importacao.sql', help="Nome do ficheiro SQL gerado")
parser.add_argument('--skip-pop', type=int, default=4, help="Linhas a ignorar no cabeçalho da população (padrão: 4)")

args, unknown = parser.parse_known_args()

# Se o utilizador rodar o script sem parâmetros no terminal, o motor pergunta interativamente:
print("=== MOTOR ETL: GERADOR DE BANCO DE DADOS ESPACIAL ===")
ARQUIVO_CRIMES = args.crimes or input("📁 Digite o nome/caminho da planilha de CRIMES (ex: crimes_2027.xlsx): ").strip()
ARQUIVO_POP = args.populacao or input("📁 Digite o nome/caminho da planilha de POPULAÇÃO (ex: ibge.xlsx): ").strip()
ARQUIVO_SQL = args.saida
SKIP_POP = args.skip_pop

if not os.path.exists(ARQUIVO_CRIMES) or not os.path.exists(ARQUIVO_POP):
    print("\n❌ Erro: Um dos ficheiros não foi encontrado. Verifique os nomes e tente novamente.")
    exit(1)

print("\n⚙️ 1/5 - A extrair dados das planilhas...")

# Extração dinâmica: Se for Excel, lê TODAS as abas e junta tudo automaticamente
if ARQUIVO_CRIMES.endswith('.csv'):
    df_crimes = pd.read_csv(ARQUIVO_CRIMES)
else:
    dict_abas = pd.read_excel(ARQUIVO_CRIMES, sheet_name=None)
    df_crimes = pd.concat(dict_abas.values(), ignore_index=True)

if ARQUIVO_POP.endswith('.csv'):
    df_ibge_bruto = pd.read_csv(ARQUIVO_POP, skiprows=SKIP_POP)
else:
    df_ibge_bruto = pd.read_excel(ARQUIVO_POP, skiprows=SKIP_POP)

# ---------------------------------------------------------
# 2. PROCESSAMENTO E NORMALIZAÇÃO DA POPULAÇÃO
# ---------------------------------------------------------
df_ibge_bruto.columns = ['localidade', 'populacao']
df_ibge_bruto = df_ibge_bruto.dropna(subset=['localidade']).copy()

def normalizar_texto(texto):
    if pd.isna(texto): return ""
    texto = str(texto).strip().lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto

df_crimes.columns = [str(c).strip().lower().replace(" ", "_") for c in df_crimes.columns]
if 'bairro' in df_crimes.columns: df_crimes['bairro'] = df_crimes['bairro'].apply(normalizar_texto)
if 'nome_municipio' in df_crimes.columns:
    df_crimes['nome_municipio'] = df_crimes['nome_municipio'].apply(normalizar_texto).replace({
        's. andre': 'santo andre', 's.andre': 'santo andre',
        's. bernardo do campo': 'sao bernardo do campo', 's.bernardo do campo': 'sao bernardo do campo',
        's. caetano do sul': 'sao caetano do sul', 's.caetano do sul': 'sao caetano do sul'
    })

dados_ibge_processados = []
municipio_atual = None
populacao_municipio_atual = None
municipios_validos = ['santo andre', 'sao bernardo do campo', 'sao caetano do sul']

for idx, row in df_ibge_bruto.iterrows():
    pop_valor = pd.to_numeric(row['populacao'], errors='coerce')
    if pd.isna(pop_valor): continue
    local_limpo = normalizar_texto(row['localidade'])
    
    if "bairro" in local_limpo and "total" in str(row['populacao']).lower(): continue
    if local_limpo in municipios_validos:
        municipio_atual = local_limpo
        populacao_municipio_atual = int(pop_valor)
        continue
    if " - " in local_limpo:
        partes = local_limpo.split(" - ")
        bairro, cidade_parte = partes[0].strip(), partes[1].replace("(sp)", "").strip()
        dados_ibge_processados.append({
            'nome_municipio': cidade_parte, 'bairro': bairro,
            'populacao_bairro': int(pop_valor),
            'populacao_municipio': populacao_municipio_atual if cidade_parte == municipio_atual else None
        })

df_pop = pd.DataFrame(dados_ibge_processados)

if 'latitude' in df_crimes.columns and 'longitude' in df_crimes.columns:
    df_crimes['latitude'] = pd.to_numeric(df_crimes['latitude'].astype(str).str.replace(',', '.'), errors='coerce')
    df_crimes['longitude'] = pd.to_numeric(df_crimes['longitude'].astype(str).str.replace(',', '.'), errors='coerce')

# ---------------------------------------------------------
# 3. FILTROS ESPACIAIS E FUZZY MATCHING
# ---------------------------------------------------------
print("⚙️ 2/5 - A padronizar municípios e aplicar Fuzzy Matching...")
if 'nome_municipio' in df_crimes.columns:
    df_crimes = df_crimes[df_crimes['nome_municipio'].isin(municipios_validos)].copy()

def limpar_prefixos(texto):
    if not isinstance(texto, str): return texto
    t = texto.strip()
    return t.replace('bairro ', '', 1).strip() if t.startswith('bairro ') else t

df_crimes['bairro_limpo'] = df_crimes['bairro'].apply(limpar_prefixos)
df_pop['bairro_limpo'] = df_pop['bairro'].apply(limpar_prefixos)

correcoes_manuais = {
    'dos alvarengas': 'alvarenga', 'dos casa': 'casa',
    'parque novo oratorio i': 'parque novo oratorio', 'parque novo oratorio ii': 'parque novo oratorio',
    'vila santa paula': 'santa paula', 'jardim teles de menezes': 'teles de menezes'
}
df_crimes['bairro_limpo'] = df_crimes['bairro_limpo'].replace(correcoes_manuais)

bairros_ibge_por_municipio = df_pop.groupby('nome_municipio')['bairro_limpo'].unique().to_dict()

def encontrar_melhor_bairro(row):
    bairro_crime, municipio = row['bairro_limpo'], row['nome_municipio']
    if municipio in bairros_ibge_por_municipio:
        if bairro_crime in bairros_ibge_por_municipio[municipio]: return bairro_crime
        if isinstance(bairro_crime, str):
            melhor_opcao, score = process.extractOne(bairro_crime, bairros_ibge_por_municipio[municipio])
            if score >= 85: return melhor_opcao
    return bairro_crime

df_crimes['bairro_match'] = df_crimes.apply(encontrar_melhor_bairro, axis=1)
df_crimes['bairro'] = df_crimes['bairro_match']
df_pop['bairro'] = df_pop['bairro_limpo']

print("⚙️ 3/5 - A cruzar dados espaciais com densidade demográfica...")
df_final = pd.merge(df_crimes, df_pop, on=['nome_municipio', 'bairro'], how='left')

# Todas as linhas processadas neste ficheiro pertencerão ao Lote 1 de importação
df_final['id_importacao'] = 1 

colunas_desejadas = [
    'nome_departamento', 'nome_municipio', 'data_ocorrencia_bo', 'data_registro',
    'hora_ocorrencia_bo', 'num_bo', 'bairro', 'latitude', 'longitude', 
    'rubrica', 'descr_conduta', 'natureza_apurada', 'cod_ibge', 
    'populacao_bairro', 'populacao_municipio', 'id_importacao'
]
df_final = df_final[[col for col in colunas_desejadas if col in df_final.columns]]

# ---------------------------------------------------------
# 4. GERAÇÃO DO FICHEIRO SQL COM CONTROLE DE IMPORTAÇÃO
# ---------------------------------------------------------
print(f"⚙️ 4/5 - A gerar o motor SQL de saída ({ARQUIVO_SQL})...")
with open(ARQUIVO_SQL, "w", encoding="utf-8") as f:
    
    f.write("SET FOREIGN_KEY_CHECKS = 0;\n")
    f.write("DROP TABLE IF EXISTS ocorrencias_criminais;\n")
    f.write("DROP TABLE IF EXISTS controle_importacoes;\n")
    f.write("SET FOREIGN_KEY_CHECKS = 1;\n\n")

    sql_controle = """
CREATE TABLE controle_importacoes (
    id_importacao INT PRIMARY KEY AUTO_INCREMENT,
    fonte_terceiro VARCHAR(100),
    nome_arquivo_origem VARCHAR(255) NOT NULL,
    tabela_destino VARCHAR(100),
    data_importacao DATETIME DEFAULT CURRENT_TIMESTAMP,
    usuario_adm VARCHAR(100)
) ENGINE=InnoDB;
"""
    f.write(sql_controle)

    sql_estrutura = """
CREATE TABLE ocorrencias_criminais (
    id_ocorrencia INT AUTO_INCREMENT PRIMARY KEY,
    nome_departamento VARCHAR(150),
    nome_municipio VARCHAR(150),
    data_registro DATE,
    num_bo VARCHAR(150),
    data_ocorrencia_bo DATE,
    hora_ocorrencia_bo TIME,
    bairro VARCHAR(150),
    latitude DECIMAL(11, 8),
    longitude DECIMAL(11, 8),
    geom POINT,
    rubrica VARCHAR(255),
    descr_conduta TEXT,
    natureza_apurada VARCHAR(255),
    cod_ibge INT,
    populacao_bairro INT,
    populacao_municipio INT,
    id_importacao INT,
    INDEX idx_ocorrencias_data (data_ocorrencia_bo),
    INDEX idx_ocorrencias_cod_ibge (cod_ibge),
    INDEX idx_ocorrencias_bairro (bairro),
    FOREIGN KEY (id_importacao) REFERENCES controle_importacoes(id_importacao) ON DELETE CASCADE
) ENGINE=InnoDB;
"""
    f.write(sql_estrutura)

    # Regista automaticamente o nome dos ficheiros que o utilizador escolheu
    nomes_arquivos = f"{os.path.basename(ARQUIVO_CRIMES)} + {os.path.basename(ARQUIVO_POP)}"
    f.write(f"INSERT INTO controle_importacoes (id_importacao, fonte_terceiro, nome_arquivo_origem, tabela_destino, usuario_adm) VALUES (1, 'Motor ETL Dinâmico', '{nomes_arquivos}', 'ocorrencias_criminais', 'admin_motor');\n\n")

    colunas_df = list(df_final.columns)
    colunas_sql_str = ", ".join([f"`{c}`" for c in colunas_df])

    for _, row in df_final.iterrows():
        valores = []
        for col in colunas_df:
            val = row[col]
            if pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == "null":
                valores.append("NULL")
            elif isinstance(val, (int, float)):
                if col in ['populacao_bairro', 'populacao_municipio', 'cod_ibge', 'id_importacao']:
                    valores.append(str(int(val)) if not pd.isna(val) else "NULL")
                else:
                    valores.append(str(val))
            else:
                texto = str(val).replace("'", "''").replace("\\", "\\\\")
                valores.append(f"'{texto}'")

        f.write(f"INSERT INTO ocorrencias_criminais ({colunas_sql_str}) VALUES ({', '.join(valores)});\n")

    sql_final = """
UPDATE ocorrencias_criminais 
SET geom = ST_GeomFromText(CONCAT('POINT(', longitude, ' ', latitude, ')')) 
WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
"""
    f.write(sql_final)

print("✅ 5/5 - Motor executado com sucesso! Os ficheiros foram unidos e convertidos para SQL.")

