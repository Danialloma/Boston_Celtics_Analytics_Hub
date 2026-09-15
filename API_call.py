"""
Descarga estadísticas de jugadores y de equipo (tradicionales y avanzadas)
de los Boston Celtics para la temporada regular 2024-25, y las guarda
en archivos CSV locales para no tener que volver a llamar a la API.

Requisitos:
    pip install nba_api pandas
"""

import os
import time
import pandas as pd

from nba_api.stats.static import teams
from nba_api.stats.endpoints import leaguedashplayerstats, leaguedashteamstats

# ----------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------
SEASON = "2025-26"          # última temporada regular COMPLETA
SEASON_TYPE = "Regular Season"
OUTPUT_DIR = "celtics_data"
TIMEOUT = 60                 # stats.nba.com puede tardar; el default (30s) a veces no alcanza
MAX_RETRIES = 5
RETRY_BACKOFF = 5            # segundos, se va multiplicando (5, 10, 20, 40, 80)

os.makedirs(OUTPUT_DIR, exist_ok=True)


def call_with_retries(endpoint_class, **kwargs):
    """
    Llama a un endpoint de nba_api reintentando si hay ConnectionError
    (muy común con stats.nba.com por corte de conexión del servidor).
    No se pasan headers personalizados: nba_api ya trae internamente
    los headers correctos, y sobreescribirlos suele causar el corte 10054.
    """
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return endpoint_class(timeout=TIMEOUT, **kwargs)
        except Exception as e:
            last_error = e
            wait = RETRY_BACKOFF * attempt
            print(f"  [WARN] Intento {attempt}/{MAX_RETRIES} falló ({type(e).__name__}). "
                  f"Reintentando en {wait}s...")
            time.sleep(wait)
    raise last_error


def get_celtics_id():
    """Obtiene el team_id de los Celtics sin llamar a la API (datos estáticos)."""
    nba_teams = teams.get_teams()
    celtics = [t for t in nba_teams if t["full_name"] == "Boston Celtics"][0]
    return celtics["id"]


def fetch_and_save(measure_type, filename, team_id):
    """
    Descarga leaguedashplayerstats para un measure_type dado
    ('Base' = tradicionales, 'Advanced' = avanzadas),
    filtra solo jugadores de los Celtics y guarda en CSV.
    """
    path = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(path):
        print(f"[SKIP] {filename} ya existe, no se vuelve a pedir a la API.")
        return pd.read_csv(path)

    print(f"[FETCH] Descargando jugadores - {measure_type} ...")
    stats = call_with_retries(
        leaguedashplayerstats.LeagueDashPlayerStats,
        season=SEASON,
        season_type_all_star=SEASON_TYPE,
        measure_type_detailed_defense=measure_type,
        per_mode_detailed="PerGame",
    )
    df = stats.get_data_frames()[0]
    df_team = df[df["TEAM_ID"] == team_id].copy()
    df_team.to_csv(path, index=False)
    print(f"[OK] Guardado en {path} ({len(df_team)} jugadores)")
    time.sleep(2)  # pausa para no saturar la API
    return df_team


def fetch_and_save_team(measure_type, filename, team_id):
    """
    Descarga leaguedashteamstats para un measure_type dado,
    filtra solo la fila de los Celtics y guarda en CSV.
    """
    path = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(path):
        print(f"[SKIP] {filename} ya existe, no se vuelve a pedir a la API.")
        return pd.read_csv(path)

    print(f"[FETCH] Descargando equipo - {measure_type} ...")
    stats = call_with_retries(
        leaguedashteamstats.LeagueDashTeamStats,
        season=SEASON,
        season_type_all_star=SEASON_TYPE,
        measure_type_detailed_defense=measure_type,
        per_mode_detailed="PerGame",
    )
    df = stats.get_data_frames()[0]
    df_team = df[df["TEAM_ID"] == team_id].copy()
    df_team.to_csv(path, index=False)
    print(f"[OK] Guardado en {path}")
    time.sleep(2)
    return df_team


def main():
    team_id = get_celtics_id()
    print(f"Celtics team_id: {team_id}\n")

    # --- Jugadores ---
    df_players_base = fetch_and_save(
        "Base", "players_traditional.csv", team_id
    )
    df_players_adv = fetch_and_save(
        "Advanced", "players_advanced.csv", team_id
    )

    # --- Equipo ---
    df_team_base = fetch_and_save_team(
        "Base", "team_traditional.csv", team_id
    )
    df_team_adv = fetch_and_save_team(
        "Advanced", "team_advanced.csv", team_id
    )

    # --- Vista rápida en consola ---
    print("\n=== Jugadores - Tradicionales (PTS, REB, AST, etc.) ===")
    cols_base = ["PLAYER_NAME", "GP", "MIN", "PTS", "REB", "AST", "STL", "BLK", "FG_PCT", "FG3_PCT"]
    cols_base = [c for c in cols_base if c in df_players_base.columns]
    print(df_players_base[cols_base].sort_values("PTS", ascending=False).to_string(index=False))

    print("\n=== Jugadores - Avanzadas (PER-like, +/-, USG%, etc.) ===")
    cols_adv = ["PLAYER_NAME", "OFF_RATING", "DEF_RATING", "NET_RATING", "USG_PCT", "TS_PCT", "PIE"]
    cols_adv = [c for c in cols_adv if c in df_players_adv.columns]
    print(df_players_adv[cols_adv].sort_values("NET_RATING", ascending=False).to_string(index=False))

    print("\n=== Equipo - Tradicionales ===")
    print(df_team_base.to_string(index=False))

    print("\n=== Equipo - Avanzadas ===")
    print(df_team_adv.to_string(index=False))

    print(f"\nTodos los CSV están en la carpeta '{OUTPUT_DIR}/'.")
    print("Para volver a leerlos sin llamar a la API, usa:")
    print("  pd.read_csv('celtics_data/players_traditional.csv')")


if __name__ == "__main__":
    main()