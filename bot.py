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

NOMES_TIMES = ["Time 1", "Time 2", "Time 3", "Time 4"]
EMOJIS_CAP = ["👑", "🎗️", "⭐", "🌟"]

def extrair_id(texto):
    if not texto:
        return None
    match = re.search(r'\d+', str(texto))
    return int(match.group()) if match else None

def gerar_embed_aberto(titulo, esquema, categoria, inscritos, capitaes, max_capitaes=4):
    embed = discord.Embed(
        title=f"📋 {titulo.upper()}",
        description=f"⚽ **Formação por Time:** `{esquema}` | **Foco:** `{categoria}`\n👥 **Inscritos até agora:** `{len(inscritos)}`\n\u200b",
        color=discord.Color.green()
    )

    val_capitaes_list = []
    for i in range(max_capitaes):
        nome_t = NOMES_TIMES[i]
        cap = capitaes.get(i) or "*A definir (clique no botão)*"
        emoji_cap = EMOJIS_CAP[i % len(EMOJIS_CAP)]
        val_capitaes_list.append(f"{emoji_cap} **{nome_t}:** {cap}")

    embed.add_field(name="⭐ CAPITÃES", value="\n".join(val_capitaes_list), inline=False)
    embed.add_field(name="\u200b", value="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", inline=False)

    if inscritos:
        linhas_insc = []
        for idx, ins in enumerate(inscritos, start=1):
            emoji = POS_EMOJIS.get(ins['pos'], "⚽")
            linhas_insc.append(f"`{idx}.` {emoji} `{ins['pos']}` — {ins['user']}")
        val_inscritos = "\n".join(linhas_insc)
    else:
        val_inscritos = "*Nenhum jogador inscrito no momento.*"

    embed.add_field(name="👥 LISTA DE INSCRITOS", value=val_inscritos, inline=False)
    embed.set_footer(text="Clique nos botões abaixo para se inscrever na posição ou assumir capitão!")
    return embed

def jogador_ja_inscrito(inscritos, target_id):
    for ins in inscritos:
        if extrair_id(ins['user']) == target_id:
            return True
    return False

class ListaButtonsGeral(discord.ui.View):
    def __init__(self, esquema):
        super().__init__(timeout=None)
        
        for i in range(len(NOMES_TIMES)):
            nome_t = NOMES_TIMES[i]
            emoji_cap = EMOJIS_CAP[i % len(EMOJIS_CAP)]
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

        if custom_id.startswith("btn_cap_time"):
            time_idx = int(custom_id.replace("btn_cap_time", "")) - 1
            nome_t = NOMES_TIMES[time_idx]

            if not jogador_ja_inscrito(dados["inscritos"], user_id):
                await interaction.response.send_message(f"⚠️ Você precisa estar inscrito em alguma posição para ser capitão do **{nome_t}**!", ephemeral=True)
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
            dados["inscritos"] = [ins for ins in dados["inscritos"] if extrair_id(ins['user']) != user_id]
            for k, v in list(dados["capitaes"].items()):
                if extrair_id(v) == user_id:
                    dados["capitaes"][k] = None

        elif custom_id.startswith("btn_pos_"):
            pos_key = custom_id.replace("btn_pos_", "")
            if not jogador_ja_inscrito(dados["inscritos"], user_id):
                dados["inscritos"].append({"user": user_mention, "pos": pos_key})

        novo_embed = gerar_embed_aberto(
            dados["titulo"], 
            dados["esquema"], 
            dados["categoria"], 
            dados["inscritos"], 
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

        inscritos = []
        capitaes = {i: None for i in range(len(NOMES_TIMES))}

        view = ListaButtonsGeral(esquema)
        embed = gerar_embed_aberto(titulo, esquema, categoria, inscritos, capitaes)
        msg = await ctx.send(embed=embed, view=view)

        listas_ativas[msg.id] = {
            "titulo": titulo,
            "esquema": esquema,
            "categoria": categoria,
            "inscritos": inscritos,
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

    dados["inscritos"] = [ins for ins in dados["inscritos"] if extrair_id(ins['user']) != user_id]
    for k, v in list(dados["capitaes"].items()):
        if extrair_id(v) == user_id:
            dados["capitaes"][k] = None

    channel = bot.get_channel(dados["channel_id"])
    msg = await channel.fetch_message(msg_id)
    novo_embed = gerar_embed_aberto(dados["titulo"], dados["esquema"], dados["categoria"], dados["inscritos"], dados["capitaes"])
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
    vagas_por_time = sum(config_formacao.values())

    total_inscritos = len(dados["inscritos"])
    
    # Define automaticamente quantos times serão formados (2, 3 ou 4) com base no total de inscritos
    if total_inscritos > (vags_3 := vagas_por_time * 3):
        qtd_times = 4
    elif total_inscritos > (vags_2 := vagas_por_time * 2):
        qtd_times = 3
    else:
        qtd_times = 2

    # Separa capitães ativos
    capitaes_atribuidos = {}
    capitaes_ids = []
    for i in range(qtd_times):
        cap = dados["capitaes"].get(i)
        if cap:
            capitaes_atribuidos[i] = cap
            capitaes_ids.append(extrair_id(cap))

    # Jogadores restantes para sortear (excluindo capitães)
    pool_jogadores = [ins for ins in dados["inscritos"] if extrair_id(ins['user']) not in capitaes_ids]
    random.shuffle(pool_jogadores)

    # Preenche capitães automáticos se faltar algum
    for i in range(qtd_times):
        if i not in capitaes_atribuidos:
            if pool_jogadores:
                sorteado = pool_jogadores.pop(0)
                capitaes_atribuidos[i] = sorteado['user']
            else:
                capitaes_atribuidos[i] = "*Nenhum*"

    # Cria a estrutura dos times montados
    times_montados = []
    for i in range(qtd_times):
        t_dict = {pos: [] for pos in config_formacao.keys()}
        times_montados.append(t_dict)

    # Distribui os jogadores pelo pool de forma equilibrada nas formações
    for ins in pool_jogadores:
        pos = ins['pos']
        # Procura um time que ainda tenha vaga nessa posição
        alocado = False
        for time in times_montados:
            if pos in time and len(time[pos]) < config_formacao[pos]:
                time[pos].append(ins['user'])
                alocado = True
                break
        if not alocado:
            # Se a posição estiver cheia em todos, joga na primeira vaga livre que encontrar
            for time in times_montados:
                for p, vagas in time.items():
                    if len(vagas) < config_formacao[p]:
                        vagas.append(ins['user'])
                        alocado = True
                        break
                if alocado:
                    break

    channel = bot.get_channel(dados["channel_id"])
    try:
        msg = await channel.fetch_message(msg_id)
        await msg.edit(view=None)

        mensagem_escalacao = f"🔒 **ESCALAÇÃO FINALIZADA ({qtd_times} TIMES MONTADOS AUTOMATICAMENTE)!**\n\n"

        for idx in range(qtd_times):
            nome_time = NOMES_TIMES[idx]
            capitao = capitaes_atribuidos.get(idx, "*Nenhum*")

            membros_time = []
            for pos, lista_jogadores in times_montados[idx].items():
                emoji = POS_EMOJIS.get(pos, "⚽")
                for j in lista_jogadores:
                    membros_time.append(f"{emoji}{pos}: {j}")

            mencoes_str = " | ".join(membros_time) if membros_time else "*Apenas o capitão*"

            mensagem_escalacao += f"🛡️ **{nome_time.upper()}** (👑 Cap: {capitao})\n"
            mensagem_escalacao += f"👥 **Elenco:** {mencoes_str}\n"
            mensagem_escalacao += f"🔊 **Call:** Entrar na call do {nome_time}\n"
            mensagem_escalacao += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"

        await ctx.send(mensagem_escalacao)

    except Exception as e:
        await ctx.send(f"⚠️ Erro ao fechar lista: {e}")

TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print("❌ ERRO CRÍTICO: A variável DISCORD_TOKEN não foi encontrada!")
else:
    bot.run(TOKEN)
