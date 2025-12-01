from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests
import streamlit as st

import secure_api_key
from gmgn_client import GMGNSolanaClient, GMGNError
from telegram_signal_pipeline import (
    DEFAULT_EXPORT_ROOT,
    OpenAISentimentClient,
    ReliabilityLearner,
    TelegramScraperAdapter,
    TelegramSignalPipeline,
    build_feedback_from_pnl,
)


ROOT = Path(__file__).resolve().parent
SYSPATHS = [
    ROOT / "rough_bergomi",
    ROOT / "rough_bergomi" / "rbergomi",
    ROOT / "jumpdiff",
    ROOT / "pykalman",
    ROOT / "hmmlearn" / "src",
    ROOT / "limit-order-book" / "python",
    ROOT / "RLTrader",
    ROOT / "TradeMaster",
]
for p in SYSPATHS:
    sys.path.insert(0, str(p))
sys.path.insert(0, str(ROOT / "src"))

from polyo.config import PolyoConfig
from polyo.lstm_forecaster import get_or_init_lstm_forecaster
from polyo.rl import build_obs_with_lstm


DEFAULT_BASE_URL = "https://gmgn.ai/api/v1/solana"


def init_config() -> PolyoConfig:
    cfg = st.session_state.get("polyo_config")
    if not isinstance(cfg, PolyoConfig):
        cfg = PolyoConfig()
    st.session_state["polyo_config"] = cfg
    return cfg


def configure_lstm_settings(config: PolyoConfig) -> PolyoConfig:
    st.sidebar.subheader("LSTM Forecasting")
    use_lstm = st.sidebar.checkbox("Activer LSTM", value=config.use_lstm, key="use_lstm_toggle")
    horizon = st.sidebar.slider("Horizon LSTM (pas)", min_value=1, max_value=64, value=int(config.lstm_horizon), step=1)
    feature_options = ["returns", "price", "volatility"]
    features = st.sidebar.multiselect(
        "LSTM features",
        options=feature_options,
        default=config.lstm_features or ["returns"],
    )
    available_models = [str(p) for p in (ROOT / "models" / "lstm").glob("*.pt")]
    selected_model = None
    if available_models:
        selected_model = st.sidebar.selectbox("Modèles LSTM disponibles", options=available_models)
    model_path = st.sidebar.text_input(
        "Chemin du modèle LSTM",
        value=selected_model or config.lstm_model_path,
    )
    config.use_lstm = use_lstm
    config.lstm_horizon = int(horizon)
    config.lstm_features = features or ["returns"]
    config.lstm_model_path = model_path
    return config


def gmgn_request(
    path: str,
    params: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
) -> Optional[Dict[str, Any]]:
    """Thin wrapper around requests.get with friendly Streamlit errors."""
    params = params or {}
    url = path if path.startswith("http") else f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    headers: Dict[str, str] = {"accept": "application/json"}
    if api_key:
        headers["x-route-key"] = api_key  # per GMGN docs
        headers["gmgn-api-key"] = api_key  # compatibility with older key name
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
    except requests.RequestException as exc:
        st.error(f"GMGN request error: {exc}")
        return None
    if not resp.ok:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def gmgn_or_dummy(endpoint: str, params: dict | None = None, api_key: str = "") -> dict:
    params = params or {}
    token = params.get("token")
    base_url = params.get("base_url", DEFAULT_BASE_URL)
    limit = params.get("limit", 200)
    mode = "test"
    data: Any = None

    if api_key:
        live_data: Any = None
        if endpoint == "new_pairs":
            live_data = gmgn_request("/pairs/new", api_key=api_key, base_url=base_url)
        elif endpoint == "token_info":
            live_data = gmgn_request(f"/token/{token}", api_key=api_key, base_url=base_url) if token else None
        elif endpoint == "trades":
            live_data = gmgn_request(
                f"/token/{token}/trades", params={"limit": limit}, api_key=api_key, base_url=base_url
            ) if token else None
        elif endpoint == "price_series":
            trades_resp = gmgn_request(
                f"/token/{token}/trades", params={"limit": limit}, api_key=api_key, base_url=base_url
            ) if token else None
            trades = (trades_resp or {}).get("data") or trades_resp
            if trades:
                df = pd.DataFrame(trades)
                price_col = next((c for c in ["price", "price_usd", "p", "amount_out_usd"] if c in df.columns), None)
                time_col = next(
                    (c for c in ["ts", "timestamp", "block_timestamp", "block_time", "time"] if c in df.columns),
                    None,
                )
                if price_col:
                    df = df.dropna(subset=[price_col])
                    if time_col:
                        try:
                            df[time_col] = pd.to_datetime(df[time_col], unit="s", errors="coerce")
                        except (ValueError, TypeError):
                            df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
                        df = df.sort_values(time_col)
                        ts_list = [str(ts) for ts in df[time_col]]
                    else:
                        ts_list = [str(i) for i in range(len(df))]
                    prices = df[price_col].astype(float).tolist()
                    returns = [0.0] + np.diff(np.log(np.array(prices) + 1e-9)).tolist()
                    live_data = {"timestamps": ts_list[:limit], "prices": prices[:limit], "returns": returns[:limit]}
        if live_data:
            mode = "live"
            data = live_data
        else:
            mode = "test"
            data = {}
    else:
        mode = "test"
        data = {}

    st.session_state["gmgn_mode"] = mode
    return {"mode": mode, "data": data}


def generate_rough_series(steps: int, h: float, eta: float) -> tuple[np.ndarray, np.ndarray, List[str]]:
    notes: List[str] = []
    try:
        from rbergomi import rBergomi

        a_param = float(h - 0.5)
        a_param = min(-0.01, a_param)  # ensure negative alpha as used in model
        rb = rBergomi(n=steps, N=1, T=1.0, a=a_param)
        dW1 = rb.dW1()
        Y = rb.Y(dW1)
        V = rb.V(Y, xi=0.04, eta=eta)
        dW2 = rb.dW2()
        dB = rb.dB(dW1, dW2, rho=-0.7)
        S = rb.S(V, dB, S0=1.0)
        price_path = S[0]
        vol_path = V[0]
    except Exception as exc:  # noqa: BLE001
        notes.append(f"rough_bergomi unavailable, fallback random path ({exc})")
        rng = np.random.default_rng(42)
        price_path = np.cumprod(1 + rng.normal(0, 0.01, steps + 1))
        vol_path = np.maximum(0.01, rng.normal(0.2, 0.02, steps + 1))
    return price_path, vol_path, notes


def compute_jump_stats(returns: np.ndarray) -> Optional[Dict[str, float]]:
    if returns.size == 0:
        return None
    try:
        from jumpdiff import jump_amplitude, jump_rate, moments

        bins = np.array([max(10, min(120, returns.size * 2))])
        _, mom = moments(
            returns.reshape(-1, 1),
            bw=0.1,
            bins=bins,
            power=4,
            lag=[1],
            correction=False,
            norm=False,
            verbose=False,
        )
        xi = jump_amplitude(moments=mom, verbose=False)
        lam = jump_rate(moments=mom, xi_est=xi, verbose=False)
        return {"jump_amplitude": float(np.nanmean(xi)), "jump_rate": float(np.nanmean(lam))}
    except Exception as exc:  # noqa: BLE001
        st.warning(f"jumpdiff unavailable: {exc}")
        return None


def apply_kalman_filter(returns: np.ndarray) -> Optional[np.ndarray]:
    if returns.size == 0:
        return None
    try:
        from pykalman import KalmanFilter

        kf = KalmanFilter(
            transition_matrices=[[1]],
            observation_matrices=[[1]],
            transition_covariance=[[0.001]],
            observation_covariance=[[0.05]],
            initial_state_mean=[0.0],
            initial_state_covariance=[[1.0]],
        )
        state_means, _ = kf.filter(returns.reshape(-1, 1))
        return state_means[:, 0]
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Kalman filter unavailable: {exc}")
        return None


def detect_regimes(returns: np.ndarray, kalman_state: Optional[np.ndarray]) -> Optional[np.ndarray]:
    if returns.size < 5:
        return np.zeros(returns.size, dtype=int)
    try:
        from hmmlearn.hmm import GaussianHMM
    except Exception as exc:  # noqa: BLE001
        st.warning(f"hmmlearn unavailable: {exc}")
        return None

    features = returns.reshape(-1, 1)
    if kalman_state is not None and kalman_state.shape[0] == returns.shape[0]:
        features = np.column_stack([returns, kalman_state])
    n_states = max(1, min(3, max(1, features.shape[0] // 5)))
    try:
        model = GaussianHMM(n_components=n_states, covariance_type="diag", n_iter=50, random_state=42)
        model.fit(features)
        return model.predict(features)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Regime detection skipped: {exc}")
        return None


def run_synthetic_pipeline(h: float, eta: float, steps: int) -> Dict[str, Any]:
    price_path, vol_path, notes = generate_rough_series(steps, h, eta)
    returns = np.diff(np.log(price_path + 1e-9))
    jump_stats = compute_jump_stats(returns)
    kalman_state = apply_kalman_filter(returns)
    regimes = detect_regimes(returns, kalman_state)
    return {
        "price": price_path,
        "vol": vol_path,
        "returns": returns,
        "jump_stats": jump_stats,
        "kalman": kalman_state,
        "regimes": regimes,
        "notes": notes,
    }


def run_gmgn_analysis(token_addr: str, api_key: Optional[str], base_url: str) -> Dict[str, Any]:
    resp = gmgn_or_dummy("price_series", {"token": token_addr, "limit": 200, "base_url": base_url}, api_key or "")
    mode = resp.get("mode", "test")
    series = resp.get("data") or {}
    notes: List[str] = []
    if mode == "test":
        notes.append("Using dummy price series (mode=test).")
    timestamps = series.get("timestamps") or list(range(len(series.get("prices", []))))
    prices_list = series.get("prices") or []
    if not prices_list:
        notes.append("No price data available; generating synthetic rough path.")
        price_path, vol_path, rb_notes = generate_rough_series(90, h=0.12, eta=0.8)
        prices_list = price_path.tolist()
        timestamps = list(range(len(prices_list)))
        notes.extend(rb_notes)
    prices = np.asarray(prices_list, dtype=float)
    returns = np.diff(np.log(prices + 1e-9))
    jump_stats = compute_jump_stats(returns)
    kalman_state = apply_kalman_filter(returns)
    regimes = detect_regimes(returns, kalman_state)
    rough_overlay, _, overlay_notes = generate_rough_series(max(5, len(prices) - 1), h=0.1, eta=0.7)
    notes.extend(overlay_notes)
    return {
        "prices": prices,
        "timestamps": timestamps,
        "returns": returns,
        "jump_stats": jump_stats,
        "kalman": kalman_state,
        "regimes": regimes,
        "rough_overlay": rough_overlay,
        "notes": notes,
        "mode": mode,
    }


def run_rl_simulation(
    prices: np.ndarray,
    regimes: Optional[np.ndarray],
    steps: int = 20,
    config: Optional[PolyoConfig] = None,
    forecaster=None,
) -> Dict[str, Any]:
    config = config or PolyoConfig()
    rng = np.random.default_rng()
    if prices.size < steps + 1:
        extra_steps = steps + 1 - prices.size
        increments = rng.normal(0, 0.01, extra_steps)
        synthetic_tail = prices[-1] * np.cumprod(1 + increments)
        prices = np.concatenate([prices, synthetic_tail])
    actions_map = {0: "hold", 1: "long", 2: "short"}
    history: List[Dict[str, Any]] = []
    cum_pnl = 0.0
    base_order = ("price", "norm_price", "regime")
    for t in range(steps):
        p0 = float(prices[t])
        p1 = float(prices[t + 1])
        action = int(rng.integers(0, 3))
        delta = p1 - p0
        reward = delta if action == 1 else (-delta if action == 2 else 0.0)
        cum_pnl += reward
        reg = int(regimes[t]) if regimes is not None and len(regimes) > t else 0
        obs, obs_names = build_obs_with_lstm(
            base_features={
                "price": p1,
                "norm_price": p1 / prices[0],
                "regime": reg,
            },
            base_order=base_order,
            prices=prices[: t + 2],
            config=config,
            forecaster=forecaster,
        )
        history.append(
            {
                "t": t,
                "price": p1,
                "norm_price": p1 / prices[0],
                "regime": reg,
                "action": actions_map[action],
                "reward": reward,
                "cum_pnl": cum_pnl,
                "obs": obs.tolist(),
                "obs_fields": obs_names,
            }
        )
    df = pd.DataFrame(history)
    running_max = df["cum_pnl"].cummax()
    drawdown = float((df["cum_pnl"] - running_max).min()) if not df.empty else 0.0
    return {"df": df, "final_pnl": cum_pnl, "drawdown": drawdown}


def render_gmgn_live_market(api_key: Optional[str], base_url: str) -> None:
    st.header("GMGN Live Market")
    st.caption("Explore live Solana pairs from GMGN. All calls gracefully degrade on errors.")
    with st.expander("ℹ️ Comment fonctionne cet onglet ?"):
        st.markdown(
            """
            - Toutes les requêtes passent par `gmgn_or_dummy` : `mode: live` si la clé GMGN répond, sinon `mode: test` avec `dummy_gmgn`.
            - **New Pairs** : appelle `/pairs/new` (ou dummy). Affiche token/pair/liquidité/volume/horodatage.
            - **Token Snapshot** : appelle `/token/{mint}` (ou dummy). Affiche metrics clés (prix, change, liquidity, volume, holders) + JSON brut.
            - **Recent Trades** : appelle `/token/{mint}/trades` (ou dummy) avec limite, table des trades et histogramme du montant.
            - Les badges LIVE/TEST s’affichent à chaque section. Les erreurs API sont capturées via `st.error`.
            """
        )

    st.subheader("New Pairs Scanner")
    if st.button("Fetch New Pairs"):
        result = gmgn_or_dummy("new_pairs", {"base_url": base_url}, api_key or "")
        mode = result.get("mode", "test")
        data = result.get("data")
        pairs = (data or {}).get("data") if isinstance(data, dict) and "data" in data else data
        if pairs:
            df_pairs = pd.DataFrame(pairs)
            if not df_pairs.empty:
                st.dataframe(df_pairs.head(200))
                st.success(f"Loaded {len(df_pairs)} pairs.")
            else:
                st.warning("GMGN returned an empty list.")
        else:
            st.error("Unable to fetch new pairs.")
        if mode == "live":
            st.success("Mode: LIVE (GMGN API)")
        else:
            st.info("Mode: TEST (Dummy data)")
    else:
        st.info('Click "Fetch New Pairs" to query GMGN.')

    st.divider()
    st.subheader("Token Snapshot")
    token_addr = st.text_input("Token address", key="token_snapshot_input")
    if st.button("Fetch Token Info"):
        if not token_addr:
            st.warning("Enter a token address first.")
        else:
            result = gmgn_or_dummy("token_info", {"token": token_addr, "base_url": base_url}, api_key or "")
            mode = result.get("mode", "test")
            info = (result.get("data") or {}).get("data") if isinstance(result.get("data"), dict) else result.get("data")
            if info:
                price = info.get("price") or info.get("price_usd")
                change = info.get("price_change_24h") or info.get("change_24h")
                liquidity = info.get("liquidity") or info.get("liq")
                volume = info.get("volume_24h") or info.get("volume")
                holders = info.get("holders")
                cols = st.columns(4)
                cols[0].metric("Price", f"{price:.6f}" if price else "N/A", f"{change:+.2%}" if change else None)
                cols[1].metric("Liquidity", f"{liquidity:,.0f}" if liquidity else "N/A")
                cols[2].metric("24h Volume", f"{volume:,.0f}" if volume else "N/A")
                cols[3].metric("Holders", f"{holders:,}" if holders else "N/A")
                with st.expander("Raw response"):
                    st.json(info)
                if mode == "live":
                    st.success("Mode: LIVE (GMGN API)")
                else:
                    st.info("Mode: TEST (Dummy data)")
            else:
                st.error("No data returned for that token.")

    st.divider()
    st.subheader("Recent Trades")
    trade_token = st.text_input("Token or pool address", key="trades_input")
    trades_btn = st.button("Fetch Recent Trades")
    if trades_btn and not trade_token:
        st.warning("Enter a token or pool address for trades.")
    if trades_btn and trade_token:
        result = gmgn_or_dummy("trades", {"token": trade_token, "limit": 120, "base_url": base_url}, api_key or "")
        mode = result.get("mode", "test")
        trades = (result.get("data") or {}).get("data") if isinstance(result.get("data"), dict) else result.get("data")
        if trades:
            df_trades = pd.DataFrame(trades)
            if not df_trades.empty:
                candidates = [c for c in ["side", "price", "amount", "amount_usd", "usd_amount", "ts", "timestamp"] if c in df_trades.columns]
                if candidates:
                    st.dataframe(df_trades[candidates].head(200))
                else:
                    st.dataframe(df_trades.head(200))
                amount_col = next((c for c in ["amount_usd", "usd_amount", "amount"] if c in df_trades.columns), None)
                if amount_col:
                    st.bar_chart(df_trades[amount_col].head(60))
            else:
                st.warning("GMGN returned no trades.")
        else:
            st.error("Trade fetch failed.")
        if mode == "live":
            st.success("Mode: LIVE (GMGN API)")
        else:
            st.info("Mode: TEST (Dummy data)")


def render_quant_pipeline() -> None:
    st.header("Quant Pipeline (Synthetic)")
    st.write("Simulate a rough volatility path, add jump diffusion stats, smooth with a Kalman filter, and detect regimes with HMM.")
    with st.expander("ℹ️ Comment fonctionne cet onglet ?"):
        st.markdown(
            """
            - Génère un chemin rough volatility via `rbergomi` (ou fallback bruité) sur un horizon court.
            - Calcule les retours log, estime des statistiques de sauts avec `jumpdiff` (amplitude, intensité).
            - Lissage de la série par `pykalman.KalmanFilter` pour obtenir un état latent.
            - Détection de régimes (1–3) avec `hmmlearn.GaussianHMM` sur les features (retours, état Kalman).
            - Affiche : trajectoires prix/vol, régimes, état Kalman, stats de sauts. Toute exception est capturée et signalée.
            """
        )
    col_h, col_eta, col_steps = st.columns(3)
    h = col_h.slider("H (roughness)", 0.01, 0.5, 0.12, 0.01)
    eta = col_eta.slider("eta (vol-of-vol)", 0.1, 3.0, 0.8, 0.05)
    steps = col_steps.slider("Steps", 32, 256, 96, 8)
    if st.button("Run Synthetic Pipeline"):
        result = run_synthetic_pipeline(h, eta, steps)
        price_path = result["price"]
        vol_path = result["vol"]
        returns = result["returns"]
        regimes = result["regimes"]
        kalman = result["kalman"]
        jump_stats = result["jump_stats"]

        df_price = pd.DataFrame({"Price": price_path, "Vol": vol_path})
        st.line_chart(df_price)

        if regimes is not None:
            st.bar_chart(pd.DataFrame({"Regime": regimes}))
        if kalman is not None:
            st.line_chart(pd.DataFrame({"Kalman state": kalman}))
        if jump_stats:
            st.write("Jump estimates", jump_stats)
        if result["notes"]:
            for note in result["notes"]:
                st.warning(note)
        st.success("Synthetic pipeline finished.")


def render_gmgn_overlay(api_key: Optional[str], base_url: str) -> None:
    st.header("GMGN + Quant Overlay")
    with st.expander("ℹ️ Comment fonctionne cet onglet ?"):
        st.markdown(
            """
            - Récupère une série de prix pour un token via `gmgn_or_dummy("price_series")` (live si clé valide, sinon dummy).
            - Calcule retours log, stats de sauts (`jumpdiff`), lissage Kalman (`pykalman`), régimes HMM (`hmmlearn`).
            - Génère en parallèle une trajectoire rough synthétique pour comparaison et l’overlay sur le graphe de prix.
            - Si l’historique GMGN est insuffisant, fallback dummy + avertissement. Les graphiques montrent prix + overlay rough, régimes, état Kalman, stats de sauts.
            """
        )
    token_addr = st.text_input("Token address for overlay", key="overlay_input")
    if st.button("Fetch + Analyze"):
        if not token_addr:
            st.warning("Please enter a token address.")
            return
        result = run_gmgn_analysis(token_addr, api_key, base_url)
        prices = result["prices"]
        timestamps = result.get("timestamps") or list(range(len(prices)))
        regimes = result["regimes"]
        kalman = result["kalman"]
        jump_stats = result["jump_stats"]
        overlay = result["rough_overlay"]
        notes = result["notes"]
        mode = result.get("mode", "test")

        df_price = pd.DataFrame({"price": prices}, index=timestamps if len(timestamps) == len(prices) else None)
        df_price["rough_overlay"] = overlay[: len(df_price)]
        st.line_chart(df_price)

        if kalman is not None:
            st.line_chart(pd.DataFrame({"Raw returns": result["returns"], "Kalman": kalman}))
        if regimes is not None:
            st.bar_chart(pd.DataFrame({"Regime": regimes}))
        if jump_stats:
            st.write("Jump estimates", jump_stats)
        if notes:
            for note in notes:
                st.warning(note)
        if mode == "live":
            st.success("Mode: LIVE (GMGN API)")
        else:
            st.info("Mode: TEST (Dummy price series)")
        st.success("GMGN overlay analysis done.")


def render_rl_demo(api_key: Optional[str], base_url: str, config: PolyoConfig) -> None:
    st.header("RL Shitcoin Demo")
    with st.expander("ℹ️ Comment fonctionne cet onglet ?"):
        st.markdown(
            """
            - Source de données : pipeline synthétique ou série de prix GMGN (`gmgn_or_dummy("price_series")` si clé, sinon dummy).
            - Environnement jouet : état = prix normalisé (et régime si présent), actions {0: hold, 1: long, 2: short}, reward = Δprix * position.
            - Politique aléatoire sans entraînement, nombre d’étapes court (5–30). PnL cumulé et drawdown calculés à chaque pas.
            - Sorties : DataFrame (t, prix, régime, action, reward, cum_PnL) + courbe de PnL. Exceptions capturées pour ne pas bloquer l’UI.
            """
        )
    source = st.radio("Data source", ["Synthetic", "GMGN token"])
    steps = st.slider("Simulation steps", 5, 30, 12, 1)
    st.caption(
        f"LSTM {'activé' if config.use_lstm else 'désactivé'} | horizon={config.lstm_horizon} | features={', '.join(config.lstm_features)}"
    )
    forecaster = get_or_init_lstm_forecaster(config) if config.use_lstm else None
    token_addr = None
    if source == "GMGN token":
        token_addr = st.text_input("GMGN token address", key="rl_token_input")
    if st.button("Run RL Demo"):
        if source == "Synthetic":
            price_path, _, notes = generate_rough_series(steps + 4, h=0.15, eta=0.9)
            if notes:
                for note in notes:
                    st.warning(note)
            regimes = detect_regimes(np.diff(np.log(price_path + 1e-9)), None)
            sim = run_rl_simulation(price_path, regimes, steps=steps, config=config, forecaster=forecaster)
        else:
            if not token_addr:
                st.warning("Enter a token address to fetch GMGN data.")
                return
            gmgn_data = run_gmgn_analysis(token_addr, api_key, base_url)
            prices = gmgn_data["prices"]
            if prices.size < 2:
                st.error("Not enough GMGN prices to run the demo.")
                return
            sim = run_rl_simulation(prices, gmgn_data["regimes"], steps=steps, config=config, forecaster=forecaster)
            if gmgn_data.get("mode") == "live":
                st.success("Mode: LIVE (GMGN API)")
            else:
                st.info("Mode: TEST (Dummy price series)")
        df = sim["df"]
        st.dataframe(df)
        st.line_chart(df.set_index("t")[["cum_pnl"]])
        st.success(f"Final PnL: {sim['final_pnl']:.4f} | Drawdown: {sim['drawdown']:.4f}")


def render_telegram_signal_tab(openai_key: Optional[str]) -> None:
    st.header("Telegram Scraper → OpenAI Sentiment → RL Weighting")
    st.caption(
        "Ingest Telegram channels (via unnohwn/telegram-scraper exports or Telethon), "
        "score messages with OpenAI, and learn per-source reliability to emit trading signals."
    )
    with st.expander("ℹ️ How this works"):
        st.markdown(
            """
            - **Scraper**: Reads exports from `telegram-scraper` (`channel/channel.json|csv|db`). If Telethon + API credentials
              are present (`TELEGRAM_API_ID/TELEGRAM_API_HASH` or session), it can fetch live messages.
            - **Sentiment**: Uses OpenAI (if `OPENAI_API_KEY` is set or provided) to extract token calls; otherwise falls back to
              simple heuristics.
            - **RL**: Maintains per-source weights (channel/message type). Feedback from realised PnL updates the weights and
              feeds back into scoring so noisy sources get down-weighted.
            - **Outputs**: A table of proposed tokens/actions ranked by weighted score; stored in `st.session_state['telegram_trading_signals']`
              so the rest of the pipeline can size trades.
            """
        )

    default_channels = st.session_state.get("telegram_channels_text", "alpha_calls,signals,alerts")
    channels_text = st.text_input("Channels (comma separated)", value=default_channels)
    st.session_state["telegram_channels_text"] = channels_text
    export_root = st.text_input("Export folder (telegram-scraper output)", value=str(DEFAULT_EXPORT_ROOT))
    msg_limit = st.slider("Messages per channel", 10, 400, 120, 10)
    pnl_feedback = st.number_input("Realised PnL for last batch (optional feedback)", value=0.0, step=10.0)
    feedback_notional = st.number_input("Notional used for PnL", value=100.0, min_value=1.0, step=10.0)
    apply_feedback_now = st.checkbox("Apply PnL feedback to RL weights during this run", value=False)
    offer_download = st.checkbox("Offer download of aggregated signals as JSON", value=True)

    st.markdown("#### Tester un canal (aperçu brut)")
    preview_channel = st.text_input("Canal unique à prévisualiser", value="", key="preview_channel")
    preview_limit = st.slider("Messages à charger pour l'aperçu", 5, 200, 40, 5, key="preview_limit")
    if st.button("Fetch / afficher le canal"):
        if not preview_channel.strip():
            st.warning("Renseigne un canal pour l'aperçu.")
        else:
            normalized = preview_channel.strip()
            if normalized.startswith("@"):
                normalized = normalized[1:]
            fetcher_preview = TelegramScraperAdapter(export_root=Path(export_root))
            preview_msgs = fetcher_preview.fetch_messages([normalized], limit=preview_limit)
            if preview_msgs:
                df_prev = pd.DataFrame(
                    [
                        {
                            "channel": m.channel,
                            "message_id": m.message_id,
                            "timestamp": m.timestamp,
                            "text": m.text,
                        }
                        for m in preview_msgs
                    ]
                )
                st.dataframe(df_prev)
            else:
                st.info("Aucun message trouvé (export manquant ou canal vide).")

    run_btn = st.button("Run Telegram Signal Pipeline")
    if run_btn:
        channels = []
        for c in channels_text.split(","):
            norm = c.strip()
            if norm.startswith("@"):
                norm = norm[1:]
            if norm:
                channels.append(norm)
        if not channels:
            st.warning("Enter at least one channel.")
            return

        fetcher = TelegramScraperAdapter(export_root=Path(export_root))
        learner = ReliabilityLearner(initial_weights=st.session_state.get("telegram_rl_weights", {}))
        sentiment_client = OpenAISentimentClient(api_key=openai_key)
        pipeline = TelegramSignalPipeline(fetcher=fetcher, sentiment_client=sentiment_client, learner=learner)
        result = pipeline.run(channels, limit=msg_limit)

        if apply_feedback_now and abs(pnl_feedback) > 1e-9:
            sources_for_feedback = list({sig.source_type for sig in result["signals"]}) or ["channel"]
            feedback_objs = [
                build_feedback_from_pnl(src, pnl_feedback, notional=feedback_notional) for src in sources_for_feedback
            ]
            pipeline.learner.apply_feedback(feedback_objs, openai_client=sentiment_client)
            result["aggregated"] = pipeline.learner.aggregate(result["signals"])

        st.session_state["telegram_rl_weights"] = pipeline.learner.weights
        st.session_state["telegram_trading_signals"] = result["aggregated"]
        st.session_state["telegram_last_sources"] = list({sig.source_type for sig in result["signals"]})

        st.subheader("Latest messages (first 15)")
        messages = result["messages"][:15]
        if messages:
            df_msgs = pd.DataFrame(
                [
                    {
                        "channel": m.channel,
                        "message_id": m.message_id,
                        "text": m.text[:140] + ("…" if len(m.text) > 140 else ""),
                        "timestamp": m.timestamp,
                    }
                    for m in messages
                ]
            )
            st.dataframe(df_msgs)
        else:
            st.info("No messages available from exports or live fetch.")

        st.subheader("Raw sentiment")
        df_raw = pd.DataFrame(
            [
                {
                    "token": sig.token,
                    "stance": sig.stance,
                    "confidence": sig.confidence,
                    "score": sig.sentiment_score,
                    "source": sig.source,
                    "source_type": sig.source_type,
                    "weight_used": sig.weight,
                    "reason": sig.reason,
                }
                for sig in result["signals"]
            ]
        )
        if not df_raw.empty:
            st.dataframe(df_raw)
        else:
            st.info("No sentiments extracted.")

        st.subheader("Aggregated trading signals")
        df_signals = pd.DataFrame(result["aggregated"])
        if not df_signals.empty:
            st.dataframe(df_signals)
            st.success("Signals stored in session_state['telegram_trading_signals'] for downstream sizing.")
            if offer_download:
                st.download_button(
                    "Download aggregated signals (JSON)",
                    data=json.dumps(result["aggregated"], indent=2),
                    file_name="telegram_signals.json",
                    mime="application/json",
                )
            token_list = [row["token"] for row in result["aggregated"] if row.get("token")]
            if token_list:
                default_tok = st.session_state.get("telegram_selected_token") or token_list[0]
                if default_tok not in token_list:
                    default_tok = token_list[0]
                selected_tok = st.selectbox(
                    "Choisir un token pour l'injecter dans les autres modules GMGN/RL",
                    token_list,
                    index=token_list.index(default_tok),
                )
                st.session_state["telegram_selected_token"] = selected_tok
                if st.button("Envoyer ce token vers les modules GMGN/RL"):
                    st.session_state["token_snapshot_input"] = selected_tok
                    st.session_state["overlay_input"] = selected_tok
                    st.session_state["rl_token_input"] = selected_tok
                    st.success("Token injecté dans les champs GMGN/RL (snapshots, overlay, RL demo).")
        else:
            st.warning("No trading signals generated.")

        st.subheader("RL source weights")
        df_weights = pd.DataFrame(
            [{"source_type": k, "weight": v} for k, v in pipeline.learner.weights.items()]
        )
        if not df_weights.empty:
            st.dataframe(df_weights)

    if st.button("Apply PnL feedback to RL weights"):
        sources = st.session_state.get("telegram_last_sources") or []
        if not sources:
            st.warning("Run the pipeline first so we know which sources to update.")
            return
        if abs(pnl_feedback) < 1e-9:
            st.info("Enter a non-zero PnL to update weights.")
            return
        learner = ReliabilityLearner(initial_weights=st.session_state.get("telegram_rl_weights", {}))
        sentiment_client = OpenAISentimentClient(api_key=openai_key)
        feedback = [build_feedback_from_pnl(src, pnl_feedback, notional=feedback_notional) for src in sources]
        learner.apply_feedback(feedback, openai_client=sentiment_client)
        st.session_state["telegram_rl_weights"] = learner.weights
        st.success("Weights updated with feedback; rerun the pipeline to see the impact.")


def render_pipeline_tests(api_key: str) -> None:
    st.header("Pipeline Demo Tests")
    st.caption("Run each test module manually. If a step fails or its log is empty, downstream steps will use the constant fallback files.")

    pipeline_dir = ROOT / "tests" / "pipeline_demo"
    log_dir = pipeline_dir / "pipeline_logs"
    tg_input_default = "https://t.me/gmgnsignals/3993253"
    tg_input = st.text_input("Telegram channel/link for step 01", value=tg_input_default, key="pipeline_demo_channel")
    st.info("Les logs sont éditables ici. Si un log est non vide, il sera utilisé par le test suivant. Les champs sont vides par défaut à l'affichage.")

    def read_text(path: Path) -> str:
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    steps = [
        {
            "label": "Step 01 - Fetch Telegram",
            "script": "step01_fetch_telegram.py",
            "log": "step01_telegram_messages.log",
            "fallback": "step01_telegram_messages_fallback.jsonl",
            "args_fn": lambda: ["--channel", tg_input or tg_input_default, "--limit", "1"],
        },
        {
            "label": "Step 02 - Sentiment OpenAI",
            "script": "step02_sentiment_openai.py",
            "log": "step02_sentiment.log",
            "fallback": "step02_sentiment_fallback.jsonl",
            "args_fn": lambda: [],
        },
        {
            "label": "Step 03 - Fetch GMGN",
            "script": "step03_fetch_gmgn.py",
            "log": "step03_gmgn_data.log",
            "fallback": "step03_gmgn_data_fallback.jsonl",
            "args_fn": lambda: [],
        },
        {
            "label": "Step 04 - Preprocess Prices",
            "script": "step04_preprocess_prices.py",
            "log": "step04_preprocessed.log",
            "fallback": "step04_preprocessed_fallback.jsonl",
            "args_fn": lambda: [],
        },
        {
            "label": "Step 05 - Kalman",
            "script": "step05_kalman_analysis.py",
            "log": "step05_kalman.log",
            "fallback": "step05_kalman_fallback.jsonl",
            "args_fn": lambda: [],
        },
        {
            "label": "Step 06 - JumpDiff",
            "script": "step06_jumpdiff_analysis.py",
            "log": "step06_jumpdiff.log",
            "fallback": "step06_jumpdiff_fallback.jsonl",
            "args_fn": lambda: [],
        },
        {
            "label": "Step 07 - rBergomi",
            "script": "step07_rbergomi_analysis.py",
            "log": "step07_rbergomi.log",
            "fallback": "step07_rbergomi_fallback.jsonl",
            "args_fn": lambda: [],
        },
        {
            "label": "Step 08 - Combine Features",
            "script": "step08_combine_features.py",
            "log": "step08_combined_features.log",
            "fallback": "step08_combined_features_fallback.jsonl",
            "args_fn": lambda: [],
        },
        {
            "label": "Step 09 - Run RL",
            "script": "step09_run_rl.py",
            "log": "step09_orders.log",
            "fallback": "step09_orders_fallback.jsonl",
            "args_fn": lambda: [],
        },
        {
            "label": "Step 10 - Simulate GMGN Order",
            "script": "step10_simulate_gmgn_order.py",
            "log": "step10_simulated_calls.log",
            "fallback": "step10_simulated_calls.log",  # uses same name for log; no fallback file specified
            "args_fn": lambda: [],
        },
    ]

    for step in steps:
        log_state_key = f"log_edit_{step['log']}"
        st.subheader(step["label"])
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**Fallback (placeholder input)**")
            fb_path = pipeline_dir / step["fallback"]
            st.text_area(
                "Fallback content",
                value=read_text(fb_path),
                height=200,
                key=f"{step['label']}_fb",
                disabled=True,
            )
        with cols[1]:
            st.markdown("**Current log output**")
            log_path = log_dir / step["log"]
            if log_state_key not in st.session_state:
                st.session_state[log_state_key] = ""
            st.text_area(
                "Log content (éditable, utilisé si non vide)",
                value=st.session_state[log_state_key],
                height=200,
                key=log_state_key,
            )

            run_btn = st.button(f"Run {step['label']}", key=f"{step['label']}_run")
            if run_btn:
                script_path = pipeline_dir / step["script"]
                args = step.get("args_fn", lambda: [])()
                cmd = [sys.executable, str(script_path)] + args
                try:
                    # Persist previous step log content so current step can read it
                    idx = steps.index(step)
                    if idx > 0:
                        prev = steps[idx - 1]
                        prev_log_state_key = f"log_edit_{prev['log']}"
                        prev_log_path = log_dir / prev["log"]
                        prev_log_path.parent.mkdir(parents=True, exist_ok=True)
                        prev_content = st.session_state.get(prev_log_state_key, "")
                        prev_log_path.write_text(prev_content, encoding="utf-8")

                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    # Save current edited content before run
                    current_content = st.session_state.get(log_state_key, "")
                    log_path.write_text(current_content, encoding="utf-8")

                    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                    has_content = log_path.exists() and log_path.stat().st_size > 0
                    if result.returncode == 0 and has_content:
                        st.success("SUCCESS (log updated).")
                    elif result.returncode != 0 and has_content:
                        st.warning(f"WARNING: return code {result.returncode} (log has content; fallback logic may be used).")
                    else:
                        st.error(f"ERROR: return code {result.returncode} and log empty; downstream will use fallback.")
                    # Reload displayed content from file after run
                    st.session_state[log_state_key] = read_text(log_path)
                    if result.stdout:
                        st.code(result.stdout, language="text")
                    if result.stderr:
                        st.code(result.stderr, language="text")
                except Exception as exc:
                    st.error(f"Failed to run step: {exc}")

    st.divider()
    st.subheader("GMGN Swap Route Test (read-only)")
    st.caption("Query the GMGN Solana router to fetch a swap route (no signing/submission here).")
    if not api_key:
        st.warning("Provide a GMGN API key in the sidebar to test the swap route.")
        return

    col_a, col_b = st.columns(2)
    with col_a:
        swap_token_in = st.text_input("Input token mint", value="So11111111111111111111111111111111111111112", key="swap_token_in")
        swap_amount = st.number_input("Input amount (lamports)", value=1000000, min_value=1, step=1000, key="swap_amount")
        swap_slip = st.slider("Slippage (%)", 0.1, 50.0, 10.0, 0.1, key="swap_slip")
    with col_b:
        swap_token_out = st.text_input("Output token mint", value="Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", key="swap_token_out")
        swap_from = st.text_input("From address (payer)", value="", key="swap_from_addr")
        swap_mode = st.selectbox("Swap mode", ["ExactIn", "ExactOut"], index=0, key="swap_mode")
        swap_anti_mev = st.checkbox("Use Anti-MEV routing", value=True, key="swap_anti_mev")
        swap_fee = st.number_input("Priority fee (SOL, optional)", value=0.0, min_value=0.0, step=0.0001, format="%.6f", key="swap_fee")
        swap_partner = st.text_input("Partner (optional)", value="", key="swap_partner")

    if st.button("Query GMGN Route", key="query_gmgn_route"):
        client = GMGNSolanaClient(api_key=api_key)
        try:
            resp = client.get_swap_route(
                token_in_address=swap_token_in.strip(),
                token_out_address=swap_token_out.strip(),
                in_amount_lamports=int(swap_amount),
                from_address=swap_from.strip(),
                slippage_pct=swap_slip,
                swap_mode=swap_mode,
                fee=swap_fee if swap_fee > 0 else None,
                is_anti_mev=swap_anti_mev,
                partner=swap_partner or None,
            )
            st.success("Route retrieved.")
            st.json(resp.get("quote") or {}, expanded=False)
            raw_tx = resp.get("raw_tx") or {}
            st.markdown("**Raw transaction (unsigned, base64 preview)**")
            st.code((raw_tx.get("swapTransaction", "") or "")[:300] + "...", language="text")
            st.write(
                {
                    "lastValidBlockHeight": raw_tx.get("lastValidBlockHeight"),
                    "recentBlockhash": raw_tx.get("recentBlockhash"),
                    "prioritizationFeeLamports": raw_tx.get("prioritizationFeeLamports"),
                }
            )
        except GMGNError as exc:
            st.error(f"GMGN API error: {exc}")
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")


def render_gmgn_swap_client(api_key: str) -> None:
    st.header("GMGN Solana Swap Client (Query Router Only)")
    st.caption("Build and query swap routes via GMGN Solana Trading API. No signing or submission is performed here.")
    if not api_key:
        st.warning("Provide a GMGN API key in the sidebar to query routes.")
        return

    token_in = st.text_input("Input token mint (token_in_address)", value="So11111111111111111111111111111111111111112")
    token_out = st.text_input("Output token mint (token_out_address)", value="Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB")  # USDT
    from_addr = st.text_input("From address (payer)", value="")
    in_amount = st.number_input("Input amount (lamports)", value=1000000, min_value=1, step=1000)
    slippage = st.slider("Slippage (%)", 0.1, 50.0, 10.0, 0.1)
    swap_mode = st.selectbox("Swap mode", options=["ExactIn", "ExactOut"], index=0)
    is_anti_mev = st.checkbox("Use Anti-MEV routing (JITO)", value=True)
    fee = st.number_input("Priority fee (SOL, optional)", value=0.0, min_value=0.0, step=0.0001, format="%.6f")
    partner = st.text_input("Partner (optional)", value="")

    if st.button("Query swap route"):
        client = GMGNSolanaClient(api_key=api_key)
        try:
            resp = client.get_swap_route(
                token_in_address=token_in.strip(),
                token_out_address=token_out.strip(),
                in_amount_lamports=int(in_amount),
                from_address=from_addr.strip(),
                slippage_pct=slippage,
                swap_mode=swap_mode,
                fee=fee if fee > 0 else None,
                is_anti_mev=is_anti_mev,
                partner=partner or None,
            )
            st.success("Route retrieved.")
            st.json(resp.get("quote") or {}, expanded=False)
            st.markdown("**Raw transaction (unsigned, base64)**")
            raw_tx = resp.get("raw_tx") or {}
            st.code(raw_tx.get("swapTransaction", "")[:300] + "...", language="text")
            st.write(
                {
                    "lastValidBlockHeight": raw_tx.get("lastValidBlockHeight"),
                    "recentBlockhash": raw_tx.get("recentBlockhash"),
                    "prioritizationFeeLamports": raw_tx.get("prioritizationFeeLamports"),
                }
            )
        except GMGNError as exc:
            st.error(f"GMGN API error: {exc}")
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")


def main() -> None:
    st.set_page_config(page_title="GMGN + POLYO Playground", layout="wide")
    st.markdown(
        """
        <style>
        /* Boost tab label font size/weight for clearer subtitles */
        div[data-baseweb="tab"] button {font-size: 1.05rem !important; font-weight: 600 !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("GMGN + POLYO Quant Playground")
    st.write("Live GMGN market hooks combined with rough volatility, jump diffusion, Kalman smoothing, HMM regimes, and a tiny RL loop.")

    config = configure_lstm_settings(init_config())

    with st.expander("📘 Guide rapide de l'application (GMGN live ou dummy)"):
        st.markdown(
            """
            - **Modes de données** : clé GMGN dans la barre latérale -> `mode: live` (appels GMGN) ; sans clé ou en cas d’échec -> `mode: test` (fallback `dummy_gmgn`). Le mode actif est affiché dans le bandeau latéral.
            - **GMGN Live Market** : scanner de nouveaux pairs, snapshot d’un token (metrics + JSON brut), trades récents (table + bar chart). Toutes les requêtes passent par `gmgn_or_dummy`, donc utilisables même sans clé.
            - **Quant Pipeline (Synthetic)** : génère un chemin rough-vol/jump, calcule les retours, stats de sauts (jumpdiff), lissage Kalman (pykalman), régimes HMM (hmmlearn). Léger et purement synthétique.
            - **GMGN + Quant Overlay** : récupère ou simule une série de prix GMGN pour un token, calcule retours, sauts, Kalman, régimes, et ajoute une trajectoire rough synthétique en overlay. Bascule en dummy si l’historique GMGN est insuffisant.
            - **RL Shitcoin Demo** : mini environnement RL jouet (actions hold/long/short, PnL cumulé) sur données synthétiques ou prix GMGN (live/dummy). Exécution courte, pas d’entraînement.
            - **Barre latérale** : saisie clé GMGN + URL de base. Badge de mode (LIVE/TEST). Les caches sont activés côté dummy pour répondre vite.
            """
        )

    stored_key = secure_api_key.load_api_key()
    stored_hash = secure_api_key.load_api_key_hash()
    api_key_input = st.sidebar.text_input("GMGN API key (x-route-key)", type="password")
    base_url = st.sidebar.text_input("GMGN base URL", value=DEFAULT_BASE_URL)
    openai_default = os.getenv("OPENAI_API_KEY", "")
    openai_key_input = st.sidebar.text_input("OpenAI API key (sentiment/RL)", value=openai_default, type="password")
    save_btn = st.sidebar.button("Save API Key Securely")
    clear_btn = st.sidebar.button("Clear API Key")

    if save_btn:
        if api_key_input:
            secure_api_key.encrypt_and_store_api_key(api_key_input)
            stored_key = secure_api_key.load_api_key()
            stored_hash = secure_api_key.load_api_key_hash()
            st.sidebar.success("API key encrypted and stored locally.")
        else:
            st.sidebar.warning("Enter a key before saving.")
    if clear_btn:
        secure_api_key.clear_api_key()
        stored_key = None
        stored_hash = None
        st.sidebar.info("Stored API key cleared.")

    if stored_hash:
        st.sidebar.markdown("Encrypted key loaded.")
        st.sidebar.markdown(f"SHA-256 prefix: `{stored_hash[:12]}…`")
    else:
        st.sidebar.warning("No API key stored.")

    effective_key = api_key_input or stored_key or ""
    mode_status = "test"
    if effective_key:
        probe = gmgn_or_dummy("new_pairs", {"limit": 5, "base_url": base_url}, effective_key)
        mode_status = probe.get("mode", "test")
    else:
        st.session_state["gmgn_mode"] = "test"

    if mode_status == "live":
        st.sidebar.markdown("### MODE: LIVE (GMGN API)")
        st.sidebar.success("Using real-time GMGN data.")
    else:
        if effective_key:
            st.sidebar.markdown("### MODE: TEST (Dummy Data)")
            st.sidebar.warning("API key provided but live check failed; using dummy data.")
        else:
            st.sidebar.markdown("### MODE: TEST (Dummy Data)")
            st.sidebar.info("No API key; using dummy data.")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "GMGN Live Market",
            "Quant Pipeline (Synthetic)",
            "GMGN + Quant Overlay",
            "RL Shitcoin Demo",
            "Telegram Signals (RL)",
            "Pipeline Demo Tests",
            "GMGN Swap Client",
        ]
    )

    with tab1:
        render_gmgn_live_market(effective_key, base_url)
    with tab2:
        render_quant_pipeline()
    with tab3:
        render_gmgn_overlay(effective_key, base_url)
    with tab4:
        render_rl_demo(effective_key, base_url, config)
    with tab5:
        render_telegram_signal_tab(openai_key_input or None)
    with tab6:
        render_pipeline_tests(effective_key)
    with tab7:
        render_gmgn_swap_client(effective_key)


if __name__ == "__main__":
    main()
