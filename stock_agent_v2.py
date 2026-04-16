import os, json, smtplib, requests
from datetime import datetime
from email.mime.text import MIMEText
from twilio.rest import Client as TwilioClient
import anthropic
from indicators import check_all

ANTHROPIC_KEY  = os.environ["ANTHROPIC_API_KEY"]
TWILIO_SID     = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_TOKEN   = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM    = os.environ["TWILIO_PHONE"]
YOUR_PHONE     = os.environ["YOUR_PHONE"]
YOUR_EMAIL     = os.environ["YOUR_EMAIL"]
EMAIL_PASS     = os.environ["EMAIL_APP_PASSWORD"]
SLACK_WEBHOOK  = os.environ.get("SLACK_WEBHOOK_URL", "")

# YOUR WATCHLIST — change these tickers to whatever stocks you want!
WATCHLIST = ["TSLA", "AVGO"]

def research_ticker(ticker, tech):
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    context = (
        f"Price: ${tech['price']}, RSI: {tech['rsi']}, "
        f"200 SMA: ${tech['sma200']} ({tech['pct_from_sma']:+.1f}% from SMA), "
        f"BB lower: ${tech['bb_lower']}, BB upper: ${tech['bb_upper']}"
    )
    prompt = (
        f"Research {ticker} stock today ({datetime.now().strftime('%B %d, %Y')}).\n"
        f"Technical context: {context}\n"
        f"Search for: recent news, insider buying/selling (SEC Form 4), "
        f"big-name investors (Buffett, Ackman, Burry, Cathie Wood, Icahn), "
        f"analyst upgrades/downgrades, unusual options volume.\n"
        f"Flag any unusual cluster insider buying over $500K.\n"
        f"Respond in JSON: {{\"summary\":\"...\","
        f"\"insider_signal\":\"BUY|SELL|NEUTRAL\","
        f"\"insider_detail\":\"...\",\"big_name\":\"...\","
        f"\"news\":[\"...\"],\"overall\":\"BULLISH|BEARISH|NEUTRAL\"}}"
    )
    res = client.messages.create(
        model="claude-sonnet-4-5", max_tokens=400,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )
    text = "".join(b.text for b in res.content if b.type == "text")
    try:
        s = text.find("{")
        return json.loads(text[s:text.rfind("}")+1])
    except:
        return {"summary": text, "insider_signal": "NEUTRAL", "overall": "NEUTRAL"}

def send_sms(msg):
    TwilioClient(TWILIO_SID, TWILIO_TOKEN).messages.create(
        body=msg, from_=TWILIO_FROM, to=YOUR_PHONE)
    print("  SMS sent!")

def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = msg["To"] = YOUR_EMAIL
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(YOUR_EMAIL, EMAIL_PASS)
        s.send_message(msg)
    print(f"  Email sent: {subject}")

def send_slack(text):
    if SLACK_WEBHOOK:
        requests.post(SLACK_WEBHOOK, json={"text": text})
        print("  Slack sent!")

def fire_alert(tech, research):
    t   = tech["ticker"]
    ts  = datetime.now().strftime("%b %d %I:%M %p")
    alts = "\n".join(tech["alerts"])
    pri  = "HIGH ALERT" if tech["priority"] == "HIGH" else "ALERT"
    sma_line = f"200 SMA: ${tech['sma200']} ({tech['pct_from_sma']:+.1f}%)"
    sms = (
        f"{pri}: {t} — {ts}\n"
        f"{alts}\n"
        f"Price: ${tech['price']} | RSI: {tech['rsi']}\n"
        f"{sma_line}\n"
        f"Insider: {research.get('insider_signal','?')}"
    )
    email_body = (
        f"{t} Alert — {ts}\n{'='*45}\n\n"
        f"TRIGGERS:\n{alts}\n\n"
        f"Price:    ${tech['price']}\n"
        f"RSI:      {tech['rsi']}\n"
        f"200 SMA:  ${tech['sma200']} ({tech['pct_from_sma']:+.1f}% away)\n"
        f"BB Upper: ${tech['bb_upper']}\n"
        f"BB Lower: ${tech['bb_lower']}\n"
        f"SMA Cross: {tech['sma_cross']}\n\n"
        f"AI Summary:\n{research.get('summary','')}\n\n"
        f"Insider Signal: {research.get('insider_signal','')}\n"
        f"Insider Detail: {research.get('insider_detail','')}\n"
        f"Big Names: {research.get('big_name','')}\n\n"
        f"News:\n" + "\n".join(f"  - {h}" for h in research.get("news",[]))
    )
    slack_msg = (
        f"*{pri}: {t}* — {ts}\n"
        + "\n".join(f"> {a}" for a in tech["alerts"])
        + f"\nPrice: ${tech['price']} | RSI: {tech['rsi']} | {sma_line}"
    )
    send_sms(sms)
    send_email(f"{pri}: {t} — {tech['alerts'][0]}", email_body)
    send_slack(slack_msg)

def run():
    print(f"\nStock Agent — {datetime.now().strftime('%B %d, %Y %I:%M %p')}")
    print("="*55)
    briefing = []
    for ticker in WATCHLIST:
        print(f"\nChecking {ticker}...")
        tech = check_all(ticker)
        print(f"  Price: ${tech['price']} | RSI: {tech['rsi']} | 200 SMA: ${tech['sma200']} ({tech['pct_from_sma']:+.1f}%) | {'ALERT' if tech['triggered'] else 'OK'}")
        research = research_ticker(ticker, tech)
        if tech["triggered"]:
            fire_alert(tech, research)
        briefing.append(
            f"{ticker}: ${tech['price']} | RSI {tech['rsi']} | "
            f"SMA200 {tech['pct_from_sma']:+.1f}% | {research.get('overall','?')}\n"
            f"{research.get('summary','')[:180]}"
        )
    daily = "\n\n".join(briefing)
    send_email(f"Daily Stock Briefing — {datetime.now().strftime('%b %d')}", daily)
    send_slack(f"*Daily Briefing — {datetime.now().strftime('%b %d')}*\n" + daily[:900])
    print("\nAll done!")

if __name__ == "__main__":
    run()
