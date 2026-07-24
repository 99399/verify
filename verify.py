from flask import Flask, redirect, request, render_template_string
import requests
import json
import os

app = Flask(__name__)

# --- 設定項目 ---
CLIENT_ID = "1529736883826065508"
CLIENT_SECRET = "Lv8lPIzeR3EDekpq3FYZzfZpNofi_mzI"
REDIRECT_URI = "https://verify-jeps.onrender.com/callback"

# ★Botのトークン（Botを操作するための権限）
BOT_TOKEN = "MTUyOTczNjg4MzgyNjA2NTUwOA.GRST66.tV-byEOtwGZNwNdufUU4PiHwJcLuV9VER7Ak08"

# Botが保存する設定ファイルのパス
SETTINGS_FILE = "settings.json"

verified_ips = set()

def load_role_id(guild_id):
    """settings.jsonからサーバーごとのロールIDを取得する"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                guild_data = settings.get(str(guild_id))
                if guild_data:
                    return guild_data.get("role_id")
        except Exception as e:
            print(f"Settings load error: {e}")
    return None

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
    # ログイン時にどのギルドから来たかの情報をstateなどで渡す仕組みも可能ですが、
    # ユーザーの所属ギルド一覧を取得して一致するサーバーのロールを付与します。
    discord_auth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )
    return redirect(discord_auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "<h3 style='color: red;'>エラー</h3><p>トップページの「Discordでログイン」ボタンから進んでください。</p>", 400

    # IPアドレスの取得
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        user_ip = request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
    else:
        user_ip = request.remote_addr

    # 重複IPチェック
    if user_ip in verified_ips:
        return "<h3 style='color: red;'>認証失敗</h3><p>同一ipを検知</p>", 403

    # VPN / Proxy チェック
    ip_api_url = f"http://ip-api.com/json/{user_ip}?fields=status,message,proxy,hosting"
    try:
        api_res = requests.get(ip_api_url, timeout=5).json()
        if api_res.get("status") == "fail" or api_res.get("proxy", False) or api_res.get("hosting", False):
            return "<h3 style='color: red;'>認証失敗</h3><p>vpn,proxyを検知</p>", 403
    except Exception:
        return "<h3 style='color: red;'>ERROR</h3><p>検証中にエラーが発生しました</p>", 500

    # OAuth2 アクセストークンの取得
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
    user_headers = {"Authorization": f"Bearer {access_token}"}
    
    # ユーザー情報の取得
    user_res = requests.get("https://discord.com/api/users/@me", headers=user_headers).json()
    discord_id = user_res.get("id")

    # ユーザーが所属しているギルド一覧の取得
    user_guilds = requests.get("https://discord.com/api/users/@me/guilds", headers=user_headers).json()

    # settings.json を読み込み
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            pass

    # ロール付与処理
    bot_headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    given_roles = 0
    if isinstance(user_guilds, list):
        for guild in user_guilds:
            g_id = str(guild.get("id"))
            if g_id in settings:
                role_id = settings[g_id].get("role_id")
                if role_id:
                    role_url = f"https://discord.com/api/v10/guilds/{g_id}/members/{discord_id}/roles/{role_id}"
                    res = requests.put(role_url, headers=bot_headers)
                    if res.status_code == 204:
                        given_roles += 1

    verified_ips.add(user_ip)

    if given_roles > 0:
        return f"""
        <h3 style='color: green;'>認証成功＆ロール付与完了！</h3>
        <p>Discordアカウント（ID: {discord_id}）の検証とロールの付与が完了しました。ブラウザは閉じて大丈夫です。</p>
        """
    else:
        return f"""
        <h3 style='color: orange;'>⚠️ 認証成功（ロール付与対象なし）</h3>
        <p>IPチェックは通過しましたが、Botの設定があるサーバーへの参加が確認できないか、ロールが付与されませんでした。</p>
        """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
