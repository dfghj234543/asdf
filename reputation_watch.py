import requests
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
from datetime import datetime
import os
from openai import OpenAI

# --- 初期設定 ---
KEYWORDS = ["横山直和", "瀧本　ゆとり", "なかむら矯正歯科", "横須賀輝尚", "和佐大輔", "右京雅生", "行政書士法改正"]
CALOO_URL_TEMPLATE = "https://caloo.jp/search?keyword={keyword}"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GMAIL_USER = "1yokogyou@gmail.com"
GMAIL_APP_PASS = os.getenv("GMAIL_APP_PASS")
RECIPIENT = GMAIL_USER

# --- データ取得関数 ---
def fetch_google_snippets(keyword):
    url = f"https://www.google.com/search?q={keyword}"
    res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    soup = BeautifulSoup(res.text, 'html.parser')
    return [s.get_text() for s in soup.select(".BNeawe.s3v9rd.AP7Wnd")]

def fetch_cahoo(keyword):
    res = requests.get(CALOO_URL_TEMPLATE.format(keyword=keyword))
    soup = BeautifulSoup(res.text, 'html.parser')
    return [el.get_text().strip() for el in soup.select(".review-comment")]

# --- 感情分析 ---
def analyze_sentiment(texts):
    client = OpenAI(api_key=OPENAI_API_KEY)
    scores = []
    for text in texts:
        try:
            resp = client.chat.completions.create(
                messages=[
                    {"role":"system","content":"You are sentiment analyzer. Score from -1 to 1."},
                    {"role":"user","content":text}
                ],
                model="gpt-3.5-turbo"
            )
            content = resp.choices[0].message.content.strip()
            scores.append(float(content))
        except:
            scores.append(0.0)
    return scores

# --- レポート生成 ---
def generate_report(df):
    if df.empty or 'date' not in df.columns:
        print("データがないためレポート生成スキップ")
        return
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"週次風評レポート {df['date'].min()}〜{df['date'].max()}", ln=True)
    for idx, row in df.iterrows():
        pdf.multi_cell(0, 6, f"{row['keyword']} | {row['source']} | {row['text'][:50]}… | 感情:{row['sentiment']:.2f}")
    png = "trend.png"
    df.groupby("keyword")["sentiment"].mean().plot(kind="bar")
    plt.title("週次平均感情スコア")
    plt.savefig(png)
    pdf.image(png, w=180)
    pdf.output("weekly_report.pdf")

# --- メール送信 ---
def send_email():
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.application import MIMEApplication

    msg = MIMEMultipart()
    msg["Subject"] = "風評レポート"
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT

    try:
        with open("weekly_report.pdf", "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
            part.add_header('Content-Disposition', 'attachment', filename="weekly_report.pdf")
            msg.attach(part)
        with open("weekly_data.csv", "rb") as f:
            part2 = MIMEApplication(f.read(), _subtype="csv")
            part2.add_header('Content-Disposition', 'attachment', filename="weekly_data.csv")
            msg.attach(part2)
    except FileNotFoundError:
        print("添付ファイルが見つかりません")
        return

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(GMAIL_USER, GMAIL_APP_PASS)
    server.send_message(msg)
    server.quit()

# --- メイン処理 ---
def main():
    records = []
    today = datetime.now()
    for kw in KEYWORDS:
        for source, fn in [("Google", fetch_google_snippets), ("Caloo", fetch_cahoo)]:
            texts = fn(kw)
            if not texts:
                continue
            scores = analyze_sentiment(texts)
            for t, s in zip(texts, scores):
                records.append({
                    "date": today.date(),
                    "keyword": kw,
                    "source": source,
                    "text": t,
                    "sentiment": s
                })
    df = pd.DataFrame(records)
    df.to_csv("weekly_data.csv", index=False)
    generate_report(df)
    send_email()

if __name__ == "__main__":
    main()
