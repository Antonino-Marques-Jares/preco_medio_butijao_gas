"""
Mudança de preço do gás GLP de 13kg ao longo do tempo (2004 a 2026)

Autor: Antonino Marques Jares
Fonte: https://dados.gov.br/dados/conjuntos-dados/serie-historica-de-precos-de-combustiveis-e-de-glp
Atualizado em: 04/06/2025

Pipeline: bronze -> prata -> SQLite -> JSON -> limpeza
"""

import json
import sqlite3
import warnings
from datetime import date
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

# Pastas de entrada/saída (ajuste se necessário)
DIR_BRONZE = Path(r"D:\ETL\nivel_01_bronze\glp")
DIR_PRATA  = Path(r"D:\ETL\nivel_02_prata\glp")

# Banco e JSON ficam ao lado do script
DB_PATH  = BASE_DIR / "glp.db"
DIR_ETL  = BASE_DIR / "etl"
JSON_GLP = DIR_ETL / "botijao_gas_glp.json"

# Processa de 2004 até 2026 (inclusive)
ANOS = list(range(2004, 2027))
SEMESTRES = ["01", "02"]

ANO_ATUAL = date.today().year


# ---------------------------------------------------------------------------
# ETAPA 1 — bronze -> prata
# ---------------------------------------------------------------------------
def processar_bronze_para_prata() -> None:
    """Lê os CSVs brutos (bronze) e gera os CSVs tratados (prata)."""
    DIR_PRATA.mkdir(parents=True, exist_ok=True)

    colunas_necessarias = [
        "Regiao - Sigla", "Estado - Sigla", "Municipio",
        "CNPJ da Revenda", "Produto", "Data da Coleta", "Valor de Venda",
    ]

    for ano in ANOS:
        if ano > ANO_ATUAL:
            continue

        for semestre in SEMESTRES:
            planilha_origem  = DIR_BRONZE / f"glp-{ano}-{semestre}.csv"
            planilha_destino = DIR_PRATA  / f"glp-{ano}-{semestre}.csv"

            if not planilha_origem.exists():
                print(f"⚠ Arquivo não encontrado: {planilha_origem}")
                continue

            try:
                df = None
                for enc in ("utf-8", "latin1", "cp1252"):
                    try:
                        df = pd.read_csv(
                            planilha_origem, sep=";",
                            encoding=enc, low_memory=False,
                        )
                        break
                    except UnicodeDecodeError:
                        continue

                if df is None:
                    print(f"❌ Não foi possível decodificar {planilha_origem}")
                    continue

                faltantes = [c for c in colunas_necessarias if c not in df.columns]
                if faltantes:
                    print(f"⚠ Colunas faltantes em {planilha_origem}: {faltantes}")
                    continue

                df = df[colunas_necessarias].rename(columns={
                    "Estado - Sigla":  "ESTADO",
                    "Municipio":       "MUNICIPIO",
                    "CNPJ da Revenda": "CNPJ",
                    "Produto":         "PRODUTO",
                    "Data da Coleta":  "DATA",
                    "Valor de Venda":  "VL_VENDA",
                })

                df["DATA"]    = pd.to_datetime(df["DATA"], errors="coerce")
                df["ANO"]     = df["DATA"].dt.year.astype("Int64")
                df["MES"]     = df["DATA"].dt.month.astype("Int64")
                df["MES_ANO"] = (
                    df["MES"].astype(str).str.zfill(2)
                    + "/"
                    + df["ANO"].astype(str)
                )

                df.to_csv(planilha_destino, index=False, encoding="utf-8")
                print(f"✅ {planilha_destino} salvo com sucesso!")

            except Exception as e:
                print(f"❌ Erro grave em {planilha_origem}: {e}")

    print("✅ Todos os arquivos processados!")


# ---------------------------------------------------------------------------
# ETAPA 2 — prata -> SQLite
# ---------------------------------------------------------------------------
def _drop_tabela(cursor: sqlite3.Cursor) -> None:
    try:
        cursor.execute("DROP TABLE IF EXISTS glp")
    except Exception as e:
        print(f"Erro ao apagar tabela glp: {e}")


def _criar_tabela(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS glp (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ESTADO     TEXT,
            PRODUTO    TEXT,
            MES_ANO    TEXT,
            VL_VENDA   REAL
        )
    """)


def carregar_prata_no_sqlite() -> None:
    """Lê os CSVs prata e popula a tabela `glp` no SQLite."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        _drop_tabela(cursor)
        _criar_tabela(cursor)
        conn.commit()

        for ano in ANOS:
            if ano > ANO_ATUAL:
                continue

            for semestre in SEMESTRES:
                print(f"\nProcessando ano ({ano}) / semestre ({semestre}) ...")
                arquivo = DIR_PRATA / f"glp-{ano}-{semestre}.csv"

                try:
                    df = pd.read_csv(
                        arquivo, sep=",", encoding="utf-8", low_memory=False,
                    )
                    df_filtrado = df[
                        ["ESTADO", "PRODUTO", "MES_ANO", "VL_VENDA"]
                    ].copy()

                    df_filtrado.to_sql(
                        name="glp", con=conn,
                        if_exists="append", index=False,
                    )
                    print(f"Dados de {ano} salvos.\nRegistros salvos: {len(df_filtrado)}")

                except FileNotFoundError:
                    print(
                        f"Arquivo do ano {ano} semestre {semestre} "
                        f"não encontrado. Pulando..."
                    )
                except Exception as e:
                    print(f"Erro ao processar {ano}/{semestre}: {e}")

        print("\nProcesso concluído com sucesso!")

    finally:
        conn.close()


# ---------------------------------------------------------------------------
# ETAPA 3 — SQLite -> JSON
# ---------------------------------------------------------------------------
def gerar_json_glp() -> None:
    """Executa a query no SQLite e gera `etl/botijao_gas_glp.json`."""
    query = """
        SELECT
            ESTADO,
            PRODUTO,
            MES_ANO,
            AVG(VL_VENDA) AS VL_VENDA
        FROM glp
        WHERE MES_ANO IS NOT NULL
          AND VL_VENDA IS NOT NULL
          AND VL_VENDA > 0
        GROUP BY ESTADO, PRODUTO, MES_ANO
        ORDER BY ESTADO, PRODUTO, MES_ANO;
    """

    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    # Garante tipos serializáveis em JSON
    df["ESTADO"]   = df["ESTADO"].astype(str)
    df["PRODUTO"]  = df["PRODUTO"].astype(str)
    df["MES_ANO"]  = df["MES_ANO"].astype(str)
    df["VL_VENDA"] = df["VL_VENDA"].astype(float).round(2)

    estrutura = {
        "metadados": {
            "data_de_atualizacao": date.today().strftime("%d-%m-%Y"),
            "responsavel":         "Antonino Marques Jares",
            "nome_programa":       "etl_botijao_gas_glp.py",
        },
        "dados": df.to_dict(orient="records"),
    }

    DIR_ETL.mkdir(parents=True, exist_ok=True)
    print(f"Salvando ... {JSON_GLP}")
    with open(JSON_GLP, "w", encoding="utf-8") as f:
        json.dump(estrutura, f, ensure_ascii=False, indent=2)

    print(f"✅ JSON gerado com {len(df)} registros.")


# ---------------------------------------------------------------------------
# ETAPA 4 — limpeza de artefatos intermediários
# ---------------------------------------------------------------------------
def limpar_artefatos_intermediarios() -> None:
    """Apaga CSVs da pasta prata e o glp.db após o JSON ser gerado."""
    if not JSON_GLP.exists():
        print(f"⚠ JSON não encontrado ({JSON_GLP}). Limpeza cancelada por segurança.")
        return

    # 1. Apaga CSVs em DIR_PRATA
    if DIR_PRATA.exists():
        for csv in DIR_PRATA.glob("*.csv"):
            try:
                csv.unlink()
                print(f"🗑  Removido: {csv}")
            except Exception as e:
                print(f"⚠ Falha ao remover {csv}: {e}")
    else:
        print(f"⚠ Pasta não encontrada: {DIR_PRATA}")

    # 2. Apaga glp.db
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
            print(f"🗑  Removido: {DB_PATH}")
        except Exception as e:
            print(f"⚠ Falha ao remover {DB_PATH}: {e}")
    else:
        print(f"⚠ Banco não encontrado: {DB_PATH}")

    print("✅ Limpeza concluída.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 60)
    print("ETAPA 1 — bronze -> prata")
    print("=" * 60)
    processar_bronze_para_prata()

    print("\n" + "=" * 60)
    print("ETAPA 2 — prata -> SQLite")
    print("=" * 60)
    carregar_prata_no_sqlite()

    print("\n" + "=" * 60)
    print("ETAPA 3 — SQLite -> JSON")
    print("=" * 60)
    gerar_json_glp()

    print("\n" + "=" * 60)
    print("ETAPA 4 — limpeza de artefatos intermediários")
    print("=" * 60)
    limpar_artefatos_intermediarios()


if __name__ == "__main__":
    main()