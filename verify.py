from flask import Flask, redirect, request, render_template_string
import requests
import os

app = Flask(__name__)

# --- 設定項目 ---
CLIENT_ID = "1529736883826065508"
CLIENT_SECRET = "Lv8lPIzeR3EDekpq3FYZzfZpNofi_mzI"
REDIRECT_URI = "https://verify-jeps.onrender.com/callback"

verified_ips = set()

@app.route("/")
def index():
    html = """
    <html>
        <head><title>サーバー認証</title></head>
        <body style="font-family: sans-serif; text-align: center; margin-top: 50px;">
            <h2>Discord Verify</h2>
            <p>ボタンを押してDiscordアカウントでログインし、認証をしてください</p>
            <a href="/login" style="background: #5865F2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">Discordでログインして認証</a>
        </body>
    </html>
    """
    return render_template_string(html)

@app.route("/login")
def login():
    discord_auth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify"
    )
    return redirect(discord_auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        # 直接アクセスされたときのエラーメッセージを分かりやすくしました
        return "<h3 style='color: red;'>エラー</h3><p>トップページの「Discordでログイン」ボタンから進んでください。</p>", 400

    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        user_ip = request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
    else:
        user_ip = request.remote_addr

    if user_ip in verified_ips:
        return "<h3 style='color: red;'>認証失敗</h3><p>同一ipを検知</p>", 403

    ip_api_url = f"http://ip-api.com/json/{user_ip}?fields=status,message,proxy,hosting"
    try:
        api_res = requests.get(ip_api_url, timeout=5).json()
        if api_res.get("status") == "fail" or api_res.get("proxy", False) or api_res.get("hosting", False):
            return "<h3 style='color: red;'>認証失敗</h3><p>vpn,proxyを検知</p>", 403
    except Exception:
        return "<h3 style='color: red;'>ERROR</h3><p>検証中にエラーが発生しました</p>", 500

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_res = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers).json()
    
    if "access_token" not in token_res:
        return "Discord側で認証に失敗しました", 400

    access_token = token_res["access_token"]
    user_res = requests.get("https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {access_token}"}).json()
    discord_id = user_res.get("id")

    verified_ips.add(user_ip)

    return f"""
    <h3 style='color: green;'>認証成功！</h3>
    <p>Discordアカウント（ID: {discord_id}）の検証が完了しました、ブラウザは閉じて大丈夫です</p>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
