import os
import re
import random
import json
import asyncio
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord.ext import commands

# --- SERVIDOR WEB PARA O RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Roipau esta rodando!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

Thread(target=run_web_server, daemon=True).start()

# --- CONFIGURAÇÃO DO BOT DISCORD ---
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- PERSISTÊNCIA DE DADOS EM ARQUIVO JSON ---
ARQUIVO_DADOS = "listas_ativas.json"

def carregar_listas():
    if os.path.exists(ARQUIVO_DADOS):
        try:
            with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
                dados_brutos = json.load(f)
                return {int(k): v for k, v in dados_brutos.items()}
        except Exception as e:
            print(f"⚠️ Erro ao carregar listas salvas: {e}")
    return {}

def salvar_listas():
    try:
        with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
            dados_str_keys = {str(k): v for k, v in listas_ativas.items()}
            json.dump(dados_str_keys, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"⚠️ Erro ao salvar listas: {e}")

listas_ativas = carregar_listas()

CANAL_AVISO_ID = 1570420721312866436
CANAL_ESCALACAO_ID = 1570429628588499086

VERSAO_ATUAL = "v3.13"
ARQUIVO_VERSAO = "ultima_versao.txt"

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}!")
    
    if CANAL_AVISO_ID:
        channel = bot.get_channel(CANAL_AVISO_ID)
        if channel:
            try:
                ultima_versao = ""
                if os.path.exists(ARQUIVO_VERSAO):
                    with open(ARQUIVO_VERSAO, "r", encoding="utf-8") as f:
                        ultima_versao = f.read().strip()
                
                if ultima_versao != VERSAO_ATUAL:
                    changelog_msg = (
                        f"🚀 **RoiPau FC Bot atualizado com sucesso!** (Versão {VERSAO_ATUAL})\n\n"
                        "📋 **O que há de novo:**\n"
                        "• **Alinhamento Perfeito dos 4 Capitães:** Todos os botões de capitães (1 a 4) agora cabem perfeitamente na primeira linha do painel, garantindo a exibição do Time 4."
                    )
                    await channel.send(changelog_msg)
                    
                    with open(ARQUIVO_VERSAO, "w" as f):
                        f.write(VERSAO_ATUAL)
                else:
                    await channel.send("🤖 **RoiPau FC Bot** reiniciado e operando normalmente! ⚽🔥")
                    
            except Exception as e:
                print(f"Erro ao enviar mensagem de aviso no canal: {e}")

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    if payload.channel_id == CANAL_AVISO_ID:
        if str(payload.emoji) == "✅":
            try:
                channel = bot.get_channel(payload.channel_id)
                message = await channel.fetch_message(payload.message_id)
                if message.author.id == bot.user.id:
                    await message.delete()
            except Exception as e:
                print(f"Erro ao tentar apagar mensagem via reação: {e}")

FORMAGOES = {
    "352":  {"GOL": 1, "ZAG": 3, "VOL": 2, "ALA": 2, "MEI": 1, "ATA": 2},
    "433":  {"GOL": 1, "LAT": 2, "ZAG": 2, "VOL": 1, "MEI": 2, "ATA": 3},
    "442":  {"GOL": 1, "LAT": 2, "ZAG": 2, "VOL": 2, "ALA": 2, "ATA": 2},
    "4231": {"GOL": 1, "LAT": 2, "ZAG": 2, "VOL": 2, "MEI": 3, "ATA": 1},
    "532":  {"GOL": 1, "LAT": 2, "ZAG": 3, "VOL": 1, "MEI": 2, "ATA": 2},
}

POS_EMOJIS = {
    "GOL": "🧤",
    "LAT": "👟",
    "ZAG": "🛡️",
    "VOL": "🧱",
    "ALA": "⚡",
    "MEI": "⚙️",
    "ATA": "🎯"
}

NOMES_TIMES = ["Time 1", "Time 2", "Time 3", "Time 4"]
EMOJIS_CAP = ["👑", "🎗️", "⭐", "🌟"]

def extrair_id(texto):
    if not texto:
        return None
    match = re.search(r'\d+', str(texto))
    return int(match.group()) if match else None

def jogador_ja_esta_na_lista(titulares, reservas, target_id):
    return any(extrair_id(item['user']) == target_id for item in titulares) or any(extrair_id(item['user']) == target_id for item in reservas)

def gerar_embed_dinamico(titulo, esquema, categoria, titulares, reservas, capitaes, qtd_times_ativos=2):
    embed = discord.Embed(
        title=f"📋 {titulo.upper()}",
        description=f"⚽ **Formação:** `{esquema}` (11 por time) | **Foco:** `{categoria}` | 🛡️ **Times Ativos:** `{qtd_times_ativos}` (Máx: 4)\n👥 **Titulares:** `{len(titulares)}` | ⏳ **Reservas:** `{len(reservas)}`\n\u200b",
        color=discord.Color.green()
    )

    val_capitaes_list = []
    capitaes_int = {int(k): v for k, v in capitaes.items()}
    for i in range(qtd_times_ativos):
        nome_t = NOMES_TIMES[i]
        cap = capitaes_int.get(i) or "*A definir (clique no botão)*"
        emoji_cap = EMOJIS_CAP[i]
        val_capitaes_list.append(f"{emoji_cap} **{nome_t}:** {cap}")

    embed.add_field(name="⭐ CAPITÃES", value="\n".join(val_capitaes_list), inline=False)
    embed.add_field(name="\u200b", value="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", inline=False)

    config_formacao = FORMAGOES.get(esquema, FORMAGOES["352"])
    linhas_vagas = []

    for pos, qtd_por_time in config_formacao.items():
        emoji = POS_EMOJIS.get(pos, "⚽")
        limite_vagas = qtd_por_time * qtd_times_ativos
        
        ocupantes_pos = [item for item in titulares if item['pos'] == pos]

        for i in range(limite_vagas):
            num_str = f" {i+1}" if limite_vagas > qtd_times_ativos else ""
            jogador_nome = ocupantes_pos[i]['user'] if i < len(ocupantes_pos) else "*Vago*"
            linhas_vagas.append(f"{emoji} `{pos}{num_str}:` {jogador_nome}")

    embed.add_field(name="👥 QUADRO DE INSCRITOS", value="\n".join(linhas_vagas), inline=False)
    embed.add_field(name="\u200b", value="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", inline=False)

    if reservas:
        linhas_res = []
        for idx, res in enumerate(reservas, start=1):
            emoji = POS_EMOJIS.get(res['pos'], "⚽")
            linhas_res.append(f"`{idx}.` {emoji} `{res['pos']}` — {res['user']}")
        val_reservas = "\n".join(linhas_res)
    else:
        val_reservas = "*Nenhum reserva no momento.*"

    embed.add_field(name="⏳ LISTA DE SUPLENTES / RESERVAS", value=val_reservas, inline=False)
    embed.set_footer(text="Clique nos botões abaixo para preencher a vaga ou escolher os capitães!")
    return embed

class ListaButtonsDinamica(discord.ui.View):
    def __init__(self, esquema, qtd_times=2):
        super().__init__(timeout=None)
        
        # Adiciona TODOS os 4 botões de capitães na linha 0 (o Discord aceita até 5 botões por linha)
        for i in range(4):
            nome_t = NOMES_TIMES[i]
            emoji_cap = EMOJIS_CAP[i]
            # Desativa visualmente ou restringe pelo código se o time ainda não estiver ativo
            style = discord.ButtonStyle.primary if i < qtd_times else discord.ButtonStyle.secondary
            self.add_item(discord.ui.Button(
                label=f"Cap. {nome_t}", 
                emoji=emoji_cap, 
                style=style, 
                custom_id=f"btn_cap_time{i+1}", 
                row=0
            ))

        # Botão de sair fica na linha 1
        self.add_item(discord.ui.Button(
            label="Sair da Lista", 
            emoji="❌", 
            style=discord.ButtonStyle.danger, 
            custom_id="btn_sair", 
            row=1
        ))

# O resto do código permanece o vivo e funcional
