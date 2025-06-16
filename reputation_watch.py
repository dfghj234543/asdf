import requests
from bs4 import BeautifulSoup
import tweepy
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
from datetime import datetime, timedelta
import os
from openai import OpenAI

# --- 初期設定 ---
KEYWORDS = ["横山直和", "瀧本　ゆとり", "なかむら矯正歯科", "横須賀輝尚", "和佐大輔", "右京雅生", "なかむら矯正歯科", "行政書士法改正"]
CALOO_URL_TEMPLATE = "https://caloo.jp/search?keyword={keyword}"
TWITTER_BEARER = os.getenv("TWITTER_BEARER")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GMAIL_USER = "1yokogyou@gmail.com"
GMAIL_APP_PASS = os.getenv("GMAIL_APP_PASS")  # アプリパスワード
RECIPIENT = GMAIL_USER

# --- ユーティリティ関数 ---
def fetch_google_snippets(keyword):
    url = f"https://www.google.com/search?q={keyword}"
    res = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    soup = BeautifulSoup(res.text, 'html.parser')
    return [s.get_text() for s in soup.select(".BNeawe.s3v9rd.AP7Wnd")]

def fetch_cahoo(keyword):
    res = requests.get(CALOO_URL_TEMPLATE.format(keyword=keyword))
    soup = BeautifulSoup(res.text, 'html.parser')
    return [el.get_text().strip() for el in soup.select(".review-comment")]

def fetch_twitter(keyword):
    client = tweepy.Client(bearer_token=TWITTER_BEARER)
    tweets = client.search_recent_tweets(query=keyword, max_results=10)
    return [t.text for t in tweets.data] if tweets.data else []

def analyze_sentiment(texts):
    client = OpenAI(api_key=OPENAI_API_KEY)
    scores = []
    for text in texts:
        resp = client.chat.completions.create(
            messages=[
                {"role":"system","content":"You are sentiment analyzer. Score from -1 to 1."},
                {"role":"user","content":text}
            ],
            model="gpt-3.5-turbo"
        )
        content = resp.choices[0].message.content.strip()
        try:
            scores.append(float(content))
        except:
            scores.append(0.0)
    return scores

def generate_report(df):
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

def send_email():
    import smtplib
    from email.mime.base import MIMEBase
    from email.mime.multipart import MIMEMultipart
    from email.mime.application import MIMEApplication

    msg = MIMEMultipart()
    msg["Subject"] = "風評レポート"
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT

    with open("weekly_report.pdf","rb") as f:
        part = MIMEApplication(f.read(), _subtype="pdf")
        part.add_header('Content-Disposition','attachment',filename="weekly_report.pdf")
        msg.attach(part)
    with open("weekly_data.csv","rb") as f:
        part2 = MIMEApplication(f.read(), _subtype="csv")
        part2.add_header('Content-Disposition','attachment',filename="weekly_data.csv")
        msg.attach(part2)

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(GMAIL_USER, GMAIL_APP_PASS)
    server.send_message(msg)
    server.quit()

# --- メイン処理 ---
def main():
