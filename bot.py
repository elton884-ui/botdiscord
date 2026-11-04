import os
import re
import random
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

bot = commands.Bot(command_prefix="!", intents=intents)

listas_ativas = {}

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

NOMES_TIMES = ["Time 1", "Time 2"]
EMOJIS_CAP = ["👑", "🎗️"]

def extrair_id(texto):
    if not texto:
        return None
    match = re.search(r'\d+', str(texto))
    return int(match.group()) if match else None

def gerar_embed_fixo_2_times(titulo, esquema, categoria, titulares, reservas, capitaes):
    embed = discord.Embed(
        title=f"📋 {titulo.upper()}",
        description=f"⚽ **Formação:** `{esquema}` | **Foco:** `{categoria}`\n👥 **Titulares:** `{len(titulares)}` | ⏳ **Reservas:** `{len(reservas)}`\n\u200b",
        color=discord.Color.green()
    )

    # Capitães
    val_capitaes_list = []
    for i in range(2):
        nome_t = NOMES_TIMES[i]
        cap = capitaes.get(i) or "*A definir (clique no botão)*"
        emoji_cap = EMOJIS_CAP[i]
        val_capitaes_list.append(f"{emoji_cap} **{nome_t}:** {cap}")

    embed.add_field(name="⭐ CAPITÃES", value="\n".join(val_capitaes_list), inline=False)
    embed.add_field(name="\u200b", value="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", inline=False)

    config_formacao = FORMAGOES.get(esquema, FORMAGOES["352"])
    linhas_vagas = []

    # Para cada posição, o limite total para 2 times é (qtd_por_time * 2)
    for pos, qtd_por_time in config_formacao.items():
        emoji = POS_EMOJIS.get(pos, "⚽")
        limite_vagas = qtd_por_time * 2
        
        ocupantes_pos = [item['user'] for item in titulares if item['pos'] == pos]

        for i in range(limite_vagas):
            num_str = f" {i+1}" if limite_vagas > 2 else ""
            if i < len(ocupantes_pos):
                linhas_vagas.append(f"{emoji} `{pos}{num_str}:` {ocupantes_pos[i]}")
            else:
                linhas_vagas.append(f"{emoji} `{pos}{num_str}:` *Vago*")

    embed.add_field(name="👥 TITULARES (2 TIMES)", value="\n".join(linhas_vagas), inline=False)
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
    embed.set_footer(text="Clique nos botões abaixo para preencher a vaga ou entrar na reserva!")
    return embed

def jogador_ja_esta_na_lista(titulares, reservas, target_id):
    for item in titulares:
        if extrair_id(item['user']) == target_id:
            return True
    for item in reservas:
        if extrair_id(item['user']) == target_id:
            return True
    return False

class ListaButtonsFixo(discord.ui.View):
    def __init__(self, esquema):
        super().__init__(timeout=None)
        
        for i in range(len(NOMES_TIMES)):
            nome_t = NOMES_TIMES[i]
            emoji_cap = EMOJIS_CAP[i]
            self.add_item(discord.ui.Button(
                label=f"Cap. {nome_t}", 
                emoji=emoji_cap, 
                style=discord.ButtonStyle.primary, 
                custom_id=f"btn_cap_time{i+1}", 
                row=0
            ))

        self.add_item(discord.ui.Button(
            label="Sair da Lista", 
            emoji="❌", 
            style=discord.ButtonStyle.danger, 
            custom_id="btn_sair", 
            row=0
        ))

        config_formacao = FORMAGOES.get(esquema, FORMAGOES["352"])
        row_curr = 1
        count_in_row = 0
        
        for pos in config_formacao.keys():
            emoji = POS_EMOJIS.get(pos, "⚽")
            btn = discord.ui.Button(label=pos, emoji=emoji, style=discord.ButtonStyle.secondary, custom_id=f"btn_pos_{pos}", row=row_curr)
            self.add_item(btn)
            count_in_row += 1
            if count_in_row >= 4:
                row_curr += 1
                count_in_row = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        msg_id = interaction.message.id
        if msg_id not in listas_ativas:
            await interaction.response.send_message("⚠️ Esta lista expirou na memória do bot. Crie uma nova com !criarlista.", ephemeral=True)
            return False

        dados = listas_ativas[msg_id]
        if dados["fechada"]:
            await interaction.response.send_message("🔒 Esta lista já está fechada!", ephemeral=True)
            return False

        custom_id = interaction.data["custom_id"]
        user_mention = interaction.user.mention
        user_id = interaction.user.id

        config_formacao = FORMAGOES.get(dados["esquema"], FORMAGOES["352"])

        if custom_id.startswith("btn_cap_time"):
            time_idx = int(custom_id.replace("btn_cap_time", "")) - 1
            nome_t = NOMES_TIMES[time_idx]

            if not jogador_ja_esta_na_lista(dados["titulares"], dados["reservas"], user_id):
                await interaction.response.send_message(f"⚠️ Você precisa estar na lista para ser capitão do **{nome_t}**!", ephemeral=True)
                return False

            cap_atual_id = extrair_id(dados["capitaes"].get(time_idx))

            if cap_atual_id == user_id:
                dados["capitaes"][time_idx] = None
            elif cap_atual_id is not None:
                await interaction.response.send_message(f"⚠️ O **{nome_t}** já tem um capitão definido!", ephemeral=True)
                return False
            else:
                for k in list(dados["capitaes"].keys()):
                    if extrair_id(dados["capitaes"].get(k)) == user_id:
                        dados["capitaes"][k] = None
                dados["capitaes"][time_idx] = user_mention

        elif custom_id == "btn_sair":
            dados["titulares"] = [item for item in dados["titulares"] if extrair_id(item['user']) != user_id]
            dados["reservas"] = [item for item in dados["reservas"] if extrair_id(item['user']) != user_id]
            for k, v in list(dados["capitaes"].items()):
                if extrair_id(v) == user_id:
                    dados["capitaes"][k] = None

        elif custom_id.startswith("btn_pos_"):
            pos_key = custom_id.replace("btn_pos_", "")
            
            if jogador_ja_esta_na_lista(dados["titulares"], dados["reservas"], user_id):
                await interaction.response.send_message("⚠️ Você já está inscrito nesta lista!", ephemeral=True)
                return False

            limite_pos = config_formacao.get(pos_key, 1) * 2
            ocupantes_pos = [item for item in dados["titulares"] if item['pos'] == pos_key]

            # Se ainda houver vaga nos titulares para essa posição, entra como titular. Senão, vai para suplentes/reservas.
            if len(ocupantes_pos) < limite_pos:
                dados["titulares"].append({"user": user_mention, "pos": pos_key})
            else:
                dados["reservas"].append({"user": user_mention, "pos": pos_key})

        novo_embed = gerar_embed_fixo_2_times(
            dados["titulo"], 
            dados["esquema"], 
            dados["categoria"], 
            dados["titulares"], 
            dados["reservas"],
            dados["capitaes"]
        )

        await interaction.response.edit_message(embed=novo_embed, view=dados["view"])
        return True

@bot.command(name="criarlista")
async def criar_lista(ctx, *, args):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    try:
        params = [p.strip() for p in args.split(";")]
        esquema, categoria, titulo, _, _, _ = params

        titulares = []
        reservas = []
        capitaes = {0: None, 1: None}

        view = ListaButtonsFixo(esquema)
        embed = gerar_embed_fixo_2_times(titulo, esquema, categoria, titulares, reservas, capitaes)
        msg = await ctx.send(embed=embed, view=view)

        listas_ativas[msg.id] = {
            "titulo": titulo,
            "esquema": esquema,
            "categoria": categoria,
            "titulares": titulares,
            "reservas": reservas,
            "capitaes": capitaes,
            "channel_id": ctx.channel.id,
            "fechada": False,
            "view": view
        }
    except Exception:
        await ctx.send("⚠️ **Formato inválido!** Use: `!criarlista 352;mei;LIGA CLUBS das 17h;2;0;1`")

@bot.command(name="remover")
async def remover(ctx, member: discord.Member = None):
    if not member and ctx.message.mentions:
        member = ctx.message.mentions[0]

    if not member:
        await ctx.send("⚠️ **Uso correto:** Digite `!remover @Jogador`")
        return

    msg_id = None
    if ctx.message.reference:
        msg_id = ctx.message.reference.message_id
    else:
        for mid, dados in reversed(list(listas_ativas.items())):
            if dados["channel_id"] == ctx.channel.id and not dados["fechada"]:
                msg_id = mid
                break

    if not msg_id or msg_id not in listas_ativas:
        await ctx.send("⚠️ Nenhuma lista ativa encontrada!")
        return

    dados = listas_ativas[msg_id]
    user_id = member.id

    dados["titulares"] = [item for item in dados["titulares"] if extrair_id(item['user']) != user_id]
    dados["reservas"] = [item for item in dados["reservas"] if extrair_id(item['user']) != user_id]
    for k, v in list(dados["capitaes"].items()):
        if extrair_id(v) == user_id:
            dados["capitaes"][k] = None

    channel = bot.get_channel(dados["channel_id"])
    msg = await channel.fetch_message(msg_id)
    novo_embed = gerar_embed_fixo_2_times(dados["titulo"], dados["esquema"], dados["categoria"], dados["titulares"], dados["reservas"], dados["capitaes"])
    await msg.edit(embed=novo_embed, view=dados.get("view"))

    try:
        await ctx.message.delete()
    except Exception:
        pass

@bot.command(name="fecharlista")
async def fechar_lista(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    msg_id = None
    if ctx.message.reference:
        msg_id = ctx.message.reference.message_id
    else:
        for mid, dados in reversed(list(listas_ativas.items())):
            if dados["channel_id"] == ctx.channel.id and not dados["fechada"]:
                msg_id = mid
                break

    if not msg_id or msg_id not in listas_ativas:
        await ctx.send("⚠️ Nenhuma lista aberta foi encontrada para fechar!")
        return

    dados = listas_ativas[msg_id]
    dados["fechada"] = True

    esquema = dados["esquema"]
    config_formacao = FORMAGOES.get(esquema, FORMAGOES["352"])

    # Separa capitães
    capitaes_atribuidos = {}
    capitaes_ids = []
    for i in range(2):
        cap = dados["capitaes"].get(i)
        if cap:
            capitaes_atribuidos[i] = cap
            capitaes_ids.append(extrair_id(cap))

    # Divide os titulares entre Time 1 e Time 2 de forma equilibrada por posição
    time_1 = {pos: [] for pos in config_formacao.keys()}
    time_2 = {pos: [] for pos in config_formacao.keys()}

    # Agrupa os titulares por posição
    for item in dados["titulares"]:
        pos = item['pos']
        # Alterna entre time 1 e time 2 para garantir equilíbrio
        if pos in time_1 and len(time_1[pos]) < config_formacao[pos]:
            time_1[pos].append(item['user'])
        elif pos in time_2 and len(time_2[pos]) < config_formacao[pos]:
            time_2[pos].append(item['user'])
        else:
            # Caso caia algum excedente por ajuste, joga no time 1 ou 2 que tiver espaço
            if sum(len(v) for v in time_1.values()) <= sum(len(v) for v in time_2.values()):
                time_1[pos].append(item['user'])
            else:
                time_2[pos].append(item['user'])

    # Se faltar capitão escolhido, sorteia entre os titulares de cada time
    todos_titulares_flat = [j for v in time_1.values() for j in v] + [j for v in time_2.values() for j in v]
    
    for i in range(2):
        if i not in capitaes_atribuidos:
            candidatos_time = list(time_1.values())[0] if i == 0 and time_1 else list(time_2.values())[0] if i == 1 and time_2 else todos_titulares_flat
            if candidatos_time:
                sorteado = random.choice(candidatos_time)
                capitaes_atribuidos[i] = sorteado
            else:
                capitaes_atribuidos[i] = "*Nenhum*"

    channel = bot.get_channel(dados["channel_id"])
    try:
        msg = await channel.fetch_message(msg_id)
        await msg.edit(view=None)

        mensagem_escalacao = "🔒 **ESCALAÇÃO FINALIZADA (2 TIMES CONVOCADOS)!**\n\n"

        times_lista = [("Time 1", time_1), ("Time 2", time_2)]
        for idx, (nome_time, t_dict) in enumerate(times_lista):
            capitao = capitaes_atribuidos.get(idx, "*Nenhum*")

            membros_time = []
            for pos, lista_jogadores in t_dict.items():
                emoji = POS_EMOJIS.get(pos, "⚽")
                for j in lista_jogadores:
                    membros_time.append(f"{emoji}{pos}: {j}")

            mencoes_str = " | ".join(membros_time) if membros_time else "*Nenhum jogador*"

            mensagem_escalacao += f"🛡️ **{nome_time.upper()}** (👑 Cap: {capitao})\n"
            mensagem_escalacao += f"👥 **Elenco:** {mencoes_str}\n"
            mensagem_escalacao += f"🔊 **Call:** Entrar na call do {nome_time}\n"
            mensagem_escalacao += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"

        # Se houver reservas
        if dados["reservas"]:
            res_str = ", ".join([f"{item['user']} ({item['pos']})" for item in dados["reservas"]])
            mensagem_escalacao += f"⏳ **Suplentes / Reservas:** {res_str}\n"

        await ctx.send(mensagem_escalacao)

    except Exception as e:
        await ctx.send(f"⚠️ Erro ao fechar lista: {e}")

TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print("❌ ERRO CRÍTICO: A variável DISCORD_TOKEN não foi encontrada!")
else:
    bot.run(TOKEN)
