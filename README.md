# 🚀 TSE Prime Market Stock Scanner (Grid View)

東証プライム市場の全銘柄を対象に、**「長期下落からの底打ち・トレンド転換」**の兆候がある銘柄を自動探索するスクリーニングツールです。

Python と Streamlit を使用して構築されており、インタラクティブなグリッド表示でチャートを一括確認できます。

## 📷 スクリーンショット
<img src="https://via.placeholder.com/800x400?text=App+Screenshot+Placeholder" alt="App Screenshot" width="800">

## ✨ 主な機能

JPX公式サイトからプライム市場の銘柄リストを自動取得し、Yahoo! Financeのデータを用いて以下の条件でフィルタリングを行います。

1.  **長期下落 (Long-term Drop)**
    * 過去5年間の最高値から、指定した比率（デフォルト50%）以上下落している銘柄。
2.  **底打ち (Bottom Out)**
    * 直近1年間の最安値から、指定した比率（デフォルト10%）以上リバウンドしている銘柄。
3.  **トレンド初動 (Trend Reversal)**
    * 週足移動平均線（13週線）が上向き、かつ現在の株価がその上にある銘柄。

## 🛠 技術スタック

* **Python 3.8+**
* **Streamlit**: Webアプリフレームワーク
* **yfinance**: 株価データ取得
* **Pandas**: データ操作・分析
* **Plotly**: インタラクティブなチャート描画

## 📦 インストール手順

1.  **リポジトリをクローン**
    ```bash
    git clone [https://github.com/あなたのユーザー名/tse-prime-scanner.git](https://github.com/あなたのユーザー名/tse-prime-scanner.git)
    cd tse-prime-scanner
    ```

2.  **依存ライブラリのインストール**
    ```bash
    pip install -r requirements.txt
    ```

## 🚀 使い方

以下のコマンドを実行してアプリを起動します。

```bash
streamlit run app.py