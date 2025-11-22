import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- ページ設定 ---
st.set_page_config(page_title="プライム全銘柄スキャナー（グリッド版）", layout="wide")

st.title("🚀 プライム市場 全銘柄スキャナー (グリッド表示版)")
st.markdown("""
**探索条件:**
1. **長期下落:** 5年高値から大幅に調整
2. **底打ち:** 1年安値からリバウンド中
3. **トレンド初動:** 週足(13週線)が上向き & 株価がその上
""")

# --- サイドバー設定 ---
st.sidebar.header("1. 検索条件")
drop_threshold = st.sidebar.slider("高値からの下落率 (%)", 30, 90, 50) / 100
recover_threshold = st.sidebar.slider("底値からの戻り率 (%)", 5, 50, 10) / 100

st.sidebar.header("2. 探索設定")
max_stocks = st.sidebar.number_input("探索銘柄数の上限", 10, 4000, 1607, step=50)
batch_size = 20

# 表示列数の設定
grid_cols = st.sidebar.radio("表示列数", [2, 3], index=1, horizontal=True)

debug_mode = st.sidebar.checkbox("デバッグモード", value=False)

# --- 関数定義 ---

@st.cache_data
def get_prime_tickers():
    """JPX公式サイトからプライム銘柄一覧と社名を取得して辞書で返す"""
    url = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
    try:
        df = pd.read_excel(url)
        # カラム名を柔軟に検索
        code_col = next((c for c in df.columns if 'コード' in str(c)), None)
        name_col = next((c for c in df.columns if '銘柄名' in str(c)), None)
        market_col = next((c for c in df.columns if '市場' in str(c) or '区分' in str(c)), None)

        if not code_col or not market_col or not name_col:
            return {}

        # プライム市場でフィルタリング
        prime_df = df[df[market_col].astype(str).str.contains('プライム')]
        
        # 辞書を作成 { 'xxxx.T': '銘柄名' }
        ticker_map = {}
        for index, row in prime_df.iterrows():
            raw_code = str(row[code_col])
            name = str(row[name_col])
            
            # コードのクリーニング（4桁の数字のみ抽出）
            if len(raw_code) >= 4 and raw_code[:4].isdigit():
                clean_code = f"{raw_code[:4]}.T"
                ticker_map[clean_code] = name
                
        return ticker_map

    except ImportError:
        st.error("エラー: `pip install xlrd` を実行してください。")
        return {}
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return {}

def check_conditions(df, ticker, drop_th, recover_th):
    try:
        if len(df) < 52: return None
        close = df['Close']
        high = df['High']
        low = df['Low']

        current_price = float(close.iloc[-1])
        five_year_high = float(high.max())
        if five_year_high == 0: return None
        
        # 1. 長期下落
        drop_ratio = (five_year_high - current_price) / five_year_high
        is_big_drop = drop_ratio >= drop_th

        # 2. 底打ち
        recent_one_year_low = float(low.iloc[-52:].min())
        if recent_one_year_low == 0: return None
        recover_ratio = (current_price / recent_one_year_low) - 1
        is_bottom_out = recover_ratio >= recover_th

        # 3. 復調 (SMA13)
        sma13 = close.rolling(window=13).mean()
        sma13_curr = sma13.iloc[-1]
        sma13_prev = sma13.iloc[-2]
        is_recovering = (sma13_curr > sma13_prev) and (current_price > sma13_curr)

        if is_big_drop and is_bottom_out and is_recovering:
            return {
                "ticker": ticker,
                "current_price": current_price,
                "high_price": five_year_high,
                "drop_ratio": drop_ratio,
                "low_price": recent_one_year_low,
                "recover_ratio": recover_ratio,
                "data": df
            }
        return None
    except Exception:
        return None

def plot_interactive_chart(df, ticker, res):
    """ミニチャート描画（グリッド表示用に少し高さを抑える）"""
    fig = go.Figure()
    
    # ローソク足
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name='株価', increasing_line_color='#00CC96', decreasing_line_color='#FF4136'
    ))
    
    # 移動平均線
    sma13 = df['Close'].rolling(window=13).mean()
    fig.add_trace(go.Scatter(x=df.index, y=sma13, line=dict(color='orange', width=1.5), name='13週'))

    # マーカー（シンプル化）
    fig.add_annotation(x=df['High'].idxmax(), y=res['high_price'], text="高値", showarrow=True, arrowhead=1, ay=-20, bgcolor="red", font=dict(size=10, color="white"))
    fig.add_annotation(x=df['Low'].iloc[-52:].idxmin(), y=res['low_price'], text="底値", showarrow=True, arrowhead=1, ay=20, bgcolor="green", font=dict(size=10, color="white"))

    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10), # 余白を詰める
        height=300, # 高さを抑える
        xaxis_rangeslider_visible=False, # グリッド表示ではスライダーは邪魔なので消す
        showlegend=False # 凡例も消してスッキリさせる
    )
    return fig

# --- メイン処理 ---

if 'prime_ticker_map' not in st.session_state:
    with st.spinner("JPXから銘柄リストをダウンロード中..."):
        st.session_state['prime_ticker_map'] = get_prime_tickers()

# 辞書 {code: name} を取得
ticker_map = st.session_state['prime_ticker_map']
# 辞書のキー（コード）をリスト化して探索対象にする
all_tickers = list(ticker_map.keys())

if len(all_tickers) == 0:
    st.error("銘柄リスト取得失敗。`pip install xlrd` を確認してください。")
    # フォールバック用のダミーデータ（名前付き辞書にする）
    ticker_map = {
        "2413.T": "エムスリー", "9984.T": "ソフトバンクG", "6758.T": "ソニーG",
        "6981.T": "村田製作所", "4385.T": "メルカリ", "7974.T": "任天堂"
    }
    all_tickers = list(ticker_map.keys())

st.info(f"ターゲット銘柄数: {len(all_tickers)} 件 (上限: {max_stocks}件)")

if st.sidebar.button("探索開始"):
    results = []
    target_tickers = all_tickers[:max_stocks]
    
    bar = st.progress(0)
    status = st.empty()
    
    total_batches = (len(target_tickers) + batch_size - 1) // batch_size
    
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
                    
                    if stock_df['Close'].isnull().all(): continue
                    stock_df.dropna(inplace=True)
                    
                    res = check_conditions(stock_df, ticker, drop_threshold, recover_threshold)
                    if res:
                        # ここで辞書から名前を取得して結果に追加
                        res['name'] = ticker_map.get(ticker, "名称不明")
                        results.append(res)
                except KeyError: continue
        except Exception: continue

    bar.empty()
    status.empty()

    # --- 結果表示（グリッドレイアウト） ---
    st.divider()
    if results:
        st.success(f"🎉 {len(results)} 銘柄が見つかりました！")
        
        # カラムを作成
        cols = st.columns(grid_cols)
        
        for i, res in enumerate(results):
            # インデックスに応じてカラムを振り分け
            with cols[i % grid_cols]:
                with st.container(border=True):
                    # 【変更点】社名を表示に追加
                    st.subheader(f"{res['name']}")
                    st.caption(f"Code: {res['ticker']} | 現在値: ¥{res['current_price']:,.0f}")
                    
                    # 重要な指標を横並びで
                    c1, c2 = st.columns(2)
                    c1.metric("下落率", f"▼{res['drop_ratio']:.0%}", help="5年高値からの下落")
                    c2.metric("戻り率", f"△{res['recover_ratio']:.0%}", help="1年安値からの上昇")
                    
                    # チャート
                    st.plotly_chart(plot_interactive_chart(res['data'], res['ticker'], res), use_container_width=True)
    else:
        st.warning("条件に合う銘柄は見つかりませんでした。")