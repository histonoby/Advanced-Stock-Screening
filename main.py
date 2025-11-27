import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import io

# --- ページ設定 ---
st.set_page_config(page_title="株価スクリーニングアプリ (マルチ戦略版)", layout="wide")

st.title("🚀 株価スクリーニングアプリ (マルチ戦略版)")

# --- サイドバー設定 ---
st.sidebar.header("1. 戦略・市場選択")

# キャッシュクリアボタン
if st.sidebar.button("データを再取得（キャッシュクリア）"):
    st.cache_data.clear()
    st.rerun()

# 市場選択
market_type = st.sidebar.radio("対象市場", ["日本株 (プライム)", "米国株 (S&P500)"], index=0)

# 戦略選択（ここを追加）
strategy = st.sidebar.selectbox(
    "探索戦略 (Strategy)", 
    ["1. 底値反転 (Reversal)", "2. 上昇トレンド (Trend Follow)"]
)

st.sidebar.divider()

# 戦略に応じたパラメータ表示
if "Reversal" in strategy:
    st.sidebar.subheader("📉 底値反転の設定")
    st.markdown("**条件:** 5年高値から大幅下落 + 直近底打ち")
    drop_threshold = st.sidebar.slider("高値からの下落率 (%)", 30, 90, 50) / 100
    recover_threshold = st.sidebar.slider("底値からの戻り率 (%)", 5, 50, 10) / 100
else:
    st.sidebar.subheader("📈 上昇トレンドの設定")
    st.markdown("**条件:** パーフェクトオーダー (SMA13 > 26 > 52) + 長期線サポート")
    # トレンドフォロー用の設定（必要に応じて調整）
    ma_margin = st.sidebar.slider("長期線(SMA52)との乖離許容 (%)", 0, 20, 5, help="株価が長期線から離れすぎていないか（押し目狙いなら小さく）") / 100

st.sidebar.divider()

st.sidebar.header("2. 探索設定")
max_stocks = st.sidebar.number_input("探索銘柄数の上限", 10, 4000, 100, step=50)
batch_size = 20
grid_cols = st.sidebar.radio("表示列数", [2, 3], index=1, horizontal=True)

# --- プリセットデータ（取得失敗時のバックアップ） ---
def get_fallback_prime():
    return {
        "7203.T": "トヨタ自動車", "6758.T": "ソニーG", "9984.T": "ソフトバンクG",
        "8035.T": "東京エレクトロン", "6861.T": "キーエンス", "6098.T": "リクルートHD", 
        "4063.T": "信越化学", "9432.T": "NTT", "8306.T": "三菱UFJ", "7974.T": "任天堂", 
        "6981.T": "村田製作所", "7741.T": "HOYA", "6367.T": "ダイキン", "2413.T": "エムスリー", 
        "4661.T": "オリエンタルランド", "6501.T": "日立製作所", "8058.T": "三菱商事"
    }

def get_fallback_sp500():
    return {
        "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon",
        "NVDA": "NVIDIA", "META": "Meta", "TSLA": "Tesla", "BRK-B": "Berkshire",
        "V": "Visa", "JNJ": "Johnson&Johnson", "WMT": "Walmart", "JPM": "JPMorgan",
        "PG": "Procter&Gamble", "MA": "Mastercard", "HD": "Home Depot", "XOM": "Exxon",
        "LLY": "Eli Lilly", "AVGO": "Broadcom", "COST": "Costco", "PEP": "PepsiCo"
    }

# --- データ取得関数 (堅牢版) ---

@st.cache_data
def get_prime_tickers():
    url = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
    try:
        df = pd.read_excel(url)
        code_col = next((c for c in df.columns if 'コード' in str(c)), None)
        name_col = next((c for c in df.columns if '銘柄名' in str(c)), None)
        market_col = next((c for c in df.columns if '市場' in str(c) or '区分' in str(c)), None)

        if not code_col or not market_col or not name_col:
            raise ValueError("Columns not found")

        prime_df = df[df[market_col].astype(str).str.contains('プライム')]
        ticker_map = {}
        for index, row in prime_df.iterrows():
            raw_code = str(row[code_col])
            name = str(row[name_col])
            if len(raw_code) >= 4 and raw_code[:4].isdigit():
                ticker_map[f"{raw_code[:4]}.T"] = name
        return ticker_map, None
    except Exception as e:
        return get_fallback_prime(), f"JPX Error: {e}"

@st.cache_data
def get_sp500_tickers():
    # 1. Wikipedia Try
    url_wiki = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url_wiki, headers=headers, timeout=10)
        response.raise_for_status()
        all_tables = pd.read_html(io.StringIO(response.text))
        
        found_df = None
        s_col, n_col = None, None
        for df in all_tables:
            cols = [str(c) for c in df.columns]
            s = next((c for c in cols if 'Symbol' in c or 'Ticker' in c), None)
            n = next((c for c in cols if 'Security' in c or 'Name' in c), None)
            if s and n:
                found_df = df; s_col = s; n_col = n; break
        
        if found_df is not None:
            t_map = {}
            for _, row in found_df.iterrows():
                sym = str(row[s_col]).replace('.', '-')
                t_map[sym] = str(row[n_col])
            return t_map, None
    except Exception: pass

    # 2. CSV Backup
    try:
        url_csv = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(url_csv)
        t_map = {}
        for _, row in df.iterrows():
            t_map[str(row['Symbol']).replace('.', '-')] = str(row['Security'])
        return t_map, None
    except Exception as e:
        return get_fallback_sp500(), f"All Sources Failed: {e}"

# --- 判定ロジック ---

def check_conditions(df, ticker, strategy_type, params):
    try:
        if len(df) < 52: return None
        close = df['Close']
        high = df['High']
        low = df['Low']
        curr = float(close.iloc[-1])
        
        # 移動平均線の計算 (週足)
        # SMA13 (約3ヶ月), SMA26 (約半年), SMA52 (約1年)
        sma13 = close.rolling(window=13).mean()
        sma26 = close.rolling(window=26).mean()
        sma52 = close.rolling(window=52).mean()

        if strategy_type == "Reversal":
            # --- 戦略1: 底値反転 ---
            high_5y = float(high.max())
            if high_5y == 0: return None
            
            # 下落率
            drop_ratio = (high_5y - curr) / high_5y
            is_big_drop = drop_ratio >= params['drop_th']

            # 底打ち
            low_1y = float(low.iloc[-52:].min())
            if low_1y == 0: return None
            recover_ratio = (curr / low_1y) - 1
            is_bottom_out = recover_ratio >= params['recover_th']

            # 短期トレンド転換 (SMA13)
            sma13_curr = sma13.iloc[-1]
            sma13_prev = sma13.iloc[-2]
            is_recovering = (sma13_curr > sma13_prev) and (curr > sma13_curr)

            if is_big_drop and is_bottom_out and is_recovering:
                return {
                    "type": "Reversal",
                    "ticker": ticker,
                    "current_price": curr,
                    "val_1": f"▼{drop_ratio:.0%}", # 下落率
                    "val_2": f"△{recover_ratio:.0%}", # 戻り率
                    "data": df,
                    "lines": {"SMA13": sma13}
                }

        else:
            # --- 戦略2: 上昇トレンド (Trend Follow) ---
            # 条件:
            # 1. パーフェクトオーダー (Price > SMA13 > SMA26 > SMA52)
            # 2. 長期線(SMA52)が上向き
            # 3. 現在値が長期線より上にある (サポートされている)
            
            s13 = sma13.iloc[-1]
            s26 = sma26.iloc[-1]
            s52 = sma52.iloc[-1]
            s52_prev_4w = sma52.iloc[-5] # 1ヶ月前
            
            # トレンド判定
            is_perfect_order = (curr > s13) and (s13 > s26) and (s26 > s52)
            is_sma52_rising = s52 > s52_prev_4w
            is_above_support = curr > s52
            
            # サポート確認（乖離率チェック）
            # 株価がSMA52から離れすぎていないか？（オプション）
            # params['ma_margin'] は使わなくても良いが、押し目買いなら「SMA52に近い」方が良い
            # ここではシンプルに「強いトレンド」を重視してパーフェクトオーダーを採用
            
            if is_perfect_order and is_sma52_rising and is_above_support:
                return {
                    "type": "Trend",
                    "ticker": ticker,
                    "current_price": curr,
                    "val_1": "Trend: UP",
                    "val_2": "Supp: Strong",
                    "data": df,
                    "lines": {"SMA13": sma13, "SMA26": sma26, "SMA52": sma52}
                }

        return None
    except Exception:
        return None

def plot_interactive_chart(res):
    df = res['data']
    lines = res['lines']
    
    fig = go.Figure()
    
    # ローソク足
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name='株価', increasing_line_color='#00CC96', decreasing_line_color='#FF4136'
    ))
    
    # 移動平均線の描画（戦略によって本数が変わる）
    colors = {"SMA13": "orange", "SMA26": "cyan", "SMA52": "purple"}
    for name, series in lines.items():
        fig.add_trace(go.Scatter(
            x=df.index, y=series, 
            line=dict(color=colors.get(name, "blue"), width=1.5), 
            name=name
        ))

    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=300, xaxis_rangeslider_visible=False, showlegend=False)
    return fig

# --- メイン処理 ---

if market_type == "日本株 (プライム)":
    if 'prime_data_final' not in st.session_state:
        st.session_state['prime_data_final'] = get_prime_tickers()
    ticker_map, error_msg = st.session_state['prime_data_final']
    currency_symbol = "¥"
else:
    if 'us_data_final' not in st.session_state:
        st.session_state['us_data_final'] = get_sp500_tickers()
    ticker_map, error_msg = st.session_state['us_data_final']
    currency_symbol = "$"

if error_msg:
    st.warning(f"⚠️ {error_msg}")
    st.info("💡 プリセットデータを使用します。")

all_tickers = list(ticker_map.keys())

st.info(f"市場: {market_type} | 戦略: {strategy} | 対象: {len(all_tickers)} 件")

if st.sidebar.button("探索開始"):
    results = []
    target_tickers = all_tickers[:max_stocks]
    
    bar = st.progress(0)
    status = st.empty()
    
    total_batches = (len(target_tickers) + batch_size - 1) // batch_size
    
    # パラメータの準備
    if "Reversal" in strategy:
        strat_type = "Reversal"
        params = {'drop_th': drop_threshold, 'recover_th': recover_threshold}
    else:
        strat_type = "Trend"
        params = {'ma_margin': 0.0} # 必要ならスライダーの値を入れる

    for i in range(total_batches):
        start = i * batch_size
        end = min((i + 1) * batch_size, len(target_tickers))
        batch = target_tickers[start:end]
        
        status.text(f"Scanning {start}-{end} / {len(target_tickers)}...")
        bar.progress((i + 1) / total_batches)
        
        try:
            data = yf.download(batch, period="5y", interval="1wk", group_by='ticker', progress=False, threads=True)
            if data.empty: continue

            for ticker in batch:
                try:
                    if len(batch) == 1: stock_df = data
                    else: stock_df = data[ticker].copy()
                    
                    if stock_df.empty or stock_df['Close'].isnull().all(): continue
                    stock_df.dropna(inplace=True)
                    
                    res = check_conditions(stock_df, ticker, strat_type, params)
                    if res:
                        res['name'] = ticker_map.get(ticker, ticker)
                        results.append(res)
                except KeyError: continue
        except Exception: continue

    bar.empty()
    status.empty()

    st.divider()
    if results:
        st.success(f"🎉 {len(results)} 銘柄が見つかりました！")
        cols = st.columns(grid_cols)
        for i, res in enumerate(results):
            with cols[i % grid_cols]:
                with st.container(border=True):
                    st.subheader(f"{res['name']}")
                    st.caption(f"Code: {res['ticker']} | Val: {currency_symbol}{res['current_price']:,.2f}")
                    
                    # 戦略によって表示する指標を変える
                    c1, c2 = st.columns(2)
                    if res['type'] == "Reversal":
                        c1.metric("下落率", res['val_1'])
                        c2.metric("戻り率", res['val_2'])
                    else:
                        c1.metric("状態", "上昇中")
                        c2.metric("長期線", "サポート有")
                    
                    st.plotly_chart(plot_interactive_chart(res), use_container_width=True)
    else:
        st.warning("条件に合う銘柄は見つかりませんでした。")