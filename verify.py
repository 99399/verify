import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import os

# Intentsの設定
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class VerifyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.settings_file = "settings.json"
        self.settings = self.load_settings()

    def load_settings(self):
        """JSONファイルから設定（付与ロールIDなど）を読み込む"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_settings(self):
        """設定をJSONファイルに保存する"""
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)

    async def setup_hook(self):
        # 起動時にスラッシュコマンドを同期
        await self.tree.sync()
        # 再起動後もボタンが機能するように永続ビューを登録
        self.add_view(VerifyView(self))
        print("スラッシュコマンドの同期と永続ビューの登録が完了しました")

bot = VerifyBot()

# 過去に認証されたIPを記録するセット (本番環境ではDB推奨)
verified_ips = set()

class VerifyView(discord.ui.View):
    """永続的に動作する認証ボタンのView"""
    def __init__(self, bot_instance):
        super().__init__(timeout=None)
        self.bot_instance = bot_instance

    @discord.ui.button(label="認証する (Verify)", style=discord.ButtonStyle.green, custom_id="persistent_verify_button:v1")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # サーバー設定からロールIDを取得
        guild_id_str = str(interaction.guild.id)
        guild_settings = self.bot_instance.settings.get(guild_id_str)

        if not guild_settings or "role_id" not in guild_settings:
            await interaction.response.send_message("このサーバーではまだ認証ロールが設定されていません", ephemeral=True)
            return

        role_id = guild_settings["role_id"]
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("設定されたロールが見つからないか、削除されています。", ephemeral=True)
            return

        # 案内メッセージ
        await interaction.response.send_message(
            "認証プロセスへ進みます。\n"
            "下のボタン（または案内）からWeb認証ページにアクセスしてIP検証を行ってください。\n"
            "※ VPN、プロキシ、同一IP（マルチアカウント）からのアクセスはブロックされます。\n"
            "*(※実際の運用ではここに外部Web認証サービスのURLボタン等を配置します)*",
            ephemeral=True
        )

# --- 外部Webサーバー等から呼び出されるIPチェッカーの関数サンプル ---
async def check_user_connection(ip_address: str, user_id: int) -> dict:
    """
    IP-APIを使用してVPN、プロキシ、および同一IPの重複をチェックする関数
    """
    # 1. 同一IPのチェック
    if ip_address in verified_ips:
        return {"success": False, "reason": "認証に失敗しました(同一ip)"}

    # 2. IP-APIによるVPN/プロキシ判定
    url = f"http://ip-api.com/json/{ip_address}?fields=status,message,proxy,hosting,query"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                return {"success": False, "reason": "エラーが発生しました"}
            
            data = await response.json()
            if data.get("status") == "fail":
                return {"success": False, "reason": f"無効なIPアドレスです: {data.get('message')}"}

            # proxy または hosting (データセンター/VPN等) の判定
            if data.get("proxy", False) or data.get("hosting", False):
                return {"success": False, "reason": "vpn,proxyを検知しました"}

            # チェック通過 -> IPを記録
            verified_ips.add(ip_address)
            return {"success": True, "ip": ip_address}


# --- スラッシュコマンド群 ---

@bot.tree.command(name="setup_verify", description="認証パネルのパネルを設置します")
@app_commands.describe(role="認証成功時に付与するロール")
@app_commands.checks.has_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction, role: discord.Role):
    guild_id_str = str(interaction.guild.id)

    # 設定をJSON用に保持して保存
    if guild_id_str not in bot.settings:
        bot.settings[guild_id_str] = {}
    bot.settings[guild_id_str]["role_id"] = role.id
    bot.save_settings()

    embed = discord.Embed(
        title="VERIFY",
        description="下の **「verify」** ボタンを押して、画面の指示に従い認証を完了させてください\n\n"
                    "**注意:**\n"
                    "・VPNやproxy\n"
                    "・同一ip\n"
                    "これらはブロックされます",
        color=discord.Color.blue()
    )

    await interaction.channel.send(embed=embed, view=VerifyView(bot))
    await interaction.response.send_message(f"認証パネルを設置しました！（ロール: {role.name}）", ephemeral=True)

@setup_verify.error
async def setup_verify_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("このコマンドを実行する権限（管理者）がありません。", ephemeral=True)
    else:
        await interaction.response.send_message(f"エラーが発生しました: {error}", ephemeral=True)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")

# Botの起動
bot.run("MTUyOTczNjg4MzgyNjA2NTUwOA.GdujAY.CW_fo98vMxsO6vqsCUWIfTsiVTuP75IBIRuOeg")
