import os
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
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

listas_ativas = {}

FORMAGOES = {
    "352":  {"GOL": 1, "ZAG": 3, "VOL": 2, "ALA": 2, "MEI": 1, "ATA": 2},
    "433":  {"GOL": 1, "LAT": 2, "ZAG": 2, "VOL": 1, "MEI": 2, "ATA": 3},
    "442":  {"GOL": 1, "LAT": 2, "ZAG": 2, "VOL": 2, "ALA": 2, "ATA": 2},
    "4231": {"GOL": 1, "LAT": 2, "ZAG": 2, "VOL": 2, "MEI": 3, "ATA": 1},
    "532":  {"GOL": 1, "LAT": 2, "ZAG": 3, "VOL": 1, "MEI": 2, "ATA": 2},
}

EMOJIS_POSICAO = {
    "🧤": "GOL",
    "👟": "LAT",
    "🛡️": "ZAG",
    "🧱": "VOL",
    "⚡": "ALA",
    "⚙️": "MEI",
    "🎯": "ATA"
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

NOMES_TIMES = ["RoiPau", "RoiPau FC", "RoiPau 3", "RoiPau 4"]
LINKS_CALL = [
    "https://discord.com/channels/1468243764412809462/1524800890094223490",  # RoiPau
    "https://discord.com/channels/1468243764412809462/1553042214517735515",  # RoiPau FC
    "",
    ""
]

def gerar_embed(titulo, esquema, categoria, qtd_times, times_data, reservas, capitaes, fechada=False):
    cor = discord.Color.red() if fechada else discord.Color.green()
    
    embed = discord.Embed(
        title=f"📋 {titulo.upper()}" + (" [FECHADA]" if fechada else ""),
        description=f"⚽ **Formação:** `{esquema}` | **Foco:** `{categoria}`\n👥 **Times:** `{qtd_times}`\n\u200b",
        color=cor
    )

    cap1 = capitaes.get(0) or "*A definir (reaja com 👑)*"
    cap2 = capitaes.get(1) or "*A definir (reaja com 🎗️)*"
    val_capitaes = f"👑 **RoiPau:** {cap1}\n🎗️ **RoiPau FC:** {cap2}"
    embed.add_field(name="⭐ CAPITÃES DOS TIMES", value=val_capitaes, inline=False)
    embed.add_field(name="\u200b", value="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", inline=False)

    for idx, time in enumerate(times_data, start=1):
        nome_exibicao = NOMES_TIMES[idx-1] if idx-1 < len(NOMES_TIMES) else f"TIME {idx}"
        linhas = []
        for pos, vagas in time.items():
            emoji = POS_EMOJIS.get(pos, "🔹")
            if len(vagas) == 1:
                linhas.append(f"{emoji} `{pos}:` {vagas[0] or ''}")
            else:
                for i, p in enumerate(vagas, start=1):
                    linhas.append(f"{emoji} `{pos} {i}:` {p or ''}")

        embed.add_field(name=f"⚽ {nome_exibicao.upper()}", value="\n".join(linhas), inline=False)
        
        if idx < qtd_times:
            embed.add_field(name="\u200b", value="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", inline=False)

    embed.add_field(name="\u200b", value="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", inline=False)

    if reservas:
        linhas_res = []
        for idx, res in enumerate(reservas, start=1):
            pos_formatadas = " / ".join([f"{POS_EMOJIS.get(p, '')} {p}" for p in res['posicoes']])
            linhas_res.append(f"`{idx}.` {res['user']} ({pos_formatadas})")
        val_reservas = "\n".join(linhas_res)
    else:
        val_reservas = "*Nenhum reserva no momento.*"

    embed.add_field(name="⏳ RESERVAS / LISTA B", value=val_reservas, inline=False)
    
    if fechada:
        embed.set_footer(text="🔒 LISTA FECHADA • As inscrições e alterações foram encerradas.")
    else:
        embed.set_footer(text="Reaja com 👑/🎗️ para Capitão | Emojis de Posição para Jogar | ❌ Sair")
        
    return embed

def jogador_no_time_principal(times_data, mention):
    for time in times_data:
        for pos in time:
            if mention in time[pos]:
                return True
    return False

def promover_reserva(times_data, reservas, posicao):
    for idx, res in enumerate(reservas):
        if posicao in res['posicoes']:
            candidate_mention = res['user']
            for time in times_data:
                if posicao in time and None in time[posicao]:
                    for i in range(len(time[posicao])):
                        if time[posicao][i] is None:
                            time[posicao][i] = candidate_mention
                            reservas.pop(idx)
                            return True
    return False

def remover_jogador(times_data, reservas, capitaes, mention):
    posicoes_liberadas = []
    for time in times_data:
        for pos in time:
            for i in range(len(time[pos])):
                if time[pos][i] == mention:
                    time[pos][i] = None
                    posicoes_liberadas.append(pos)

    reservas[:] = [r for r in reservas if r['user'] != mention]

    for k, v in list(capitaes.items()):
        if v == mention:
            capitaes[k] = None

    for pos_liberada in posicoes_liberadas:
        promover_reserva(times_data, reservas, pos_liberada)

def processar_posicao(times_data, reservas, posicao, mention):
    if jogador_no_time_principal(times_data, mention):
        return

    times_disponiveis = []
    for idx, time in enumerate(times_data):
        if posicao in time and None in time[posicao]:
            times_disponiveis.append(idx)

    if times_disponiveis:
        time_escolhido = random.choice(times_disponiveis)
        for i in range(len(times_data[time_escolhido][posicao])):
            if times_data[time_escolhido][posicao][i] is None:
                times_data[time_escolhido][posicao][i] = mention
                break
        reservas[:] = [r for r in reservas if r['user'] != mention]
    else:
        res_entry = None
        for r in reservas:
            if r['user'] == mention:
                res_entry = r
                break

        if res_entry:
            if posicao not in res_entry['posicoes']:
                res_entry['posicoes'].append(posicao)
        else:
            reservas.append({"user": mention, "posicoes": [posicao]})

@bot.command(name="criarlista")
async def criar_lista(ctx, *, args):
    try:
        params = [p.strip() for p in args.split(";")]
        esquema, categoria, titulo, qtd_times, reservas_param, status = params
        qtd_times = int(qtd_times)

        config_formacao = FORMAGOES.get(esquema, FORMAGOES["352"])

        times_data = []
        for _ in range(qtd_times):
            t_dict = {}
            for pos, qtd in config_formacao.items():
                t_dict[pos] = [None] * qtd
            times_data.append(t_dict)

        reservas = []
        capitaes = {0: None, 1: None}

        embed = gerar_embed(titulo, esquema, categoria, qtd_times, times_data, reservas, capitaes)
        msg = await ctx.send(embed=embed)

        listas_ativas[msg.id] = {
            "titulo": titulo,
            "esquema": esquema,
            "categoria": categoria,
            "qtd_times": qtd_times,
            "times": times_data,
            "reservas": reservas,
            "capitaes": capitaes,
            "channel_id": ctx.channel.id,
            "fechada": False
        }

        await msg.add_reaction("👑")
        await msg.add_reaction("🎗️")

        for pos in config_formacao.keys():
            if pos in POS_EMOJIS:
                await msg.add_reaction(POS_EMOJIS[pos])
        await msg.add_reaction("❌")

    except Exception:
        await ctx.send("⚠️ **Formato inválido!** Use: `!criarlista 352;mei;LIGA CLUBS das 17h;2;0;1`")

@bot.command(name="remover")
async def remover(ctx, member: discord.Member):
    msg_id = None
    
    if ctx.message.reference:
        msg_id = ctx.message.reference.message_id
    else:
        for mid, dados in reversed(list(listas_ativas.items())):
            if dados["channel_id"] == ctx.channel.id and not dados["fechada"]:
                msg_id = mid
                break

    if not msg_id or msg_id not in listas_ativas:
        await ctx.send("⚠️ Nenhuma lista aberta foi encontrada neste canal!")
        return

    dados = listas_ativas[msg_id]
    mention = member.mention

    esta_no_time = jogador_no_time_principal(dados["times"], mention)
    esta_nos_reservas = any(r['user'] == mention for r in dados["reservas"])

    if not esta_no_time and not esta_nos_reservas:
        await ctx.send(f"⚠️ O jogador {mention} não está nesta lista.")
        return

    remover_jogador(dados["times"], dados["reservas"], dados["capitaes"], mention)

    channel = bot.get_channel(dados["channel_id"])
    msg = await channel.fetch_message(msg_id)

    novo_embed = gerar_embed(
        dados["titulo"], 
        dados["esquema"], 
        dados["categoria"], 
        dados["qtd_times"], 
        dados["times"], 
        dados["reservas"],
        dados["capitaes"]
    )
    await msg.edit(embed=novo_embed)
    await ctx.send(f"🗑️ O jogador {mention} foi removido da lista!")

@bot.command(name="atualizarlista")
async def atualizar_lista(ctx, nova_qtd: int):
    msg_id = None
    for mid, dados in reversed(list(listas_ativas.items())):
        if dados["channel_id"] == ctx.channel.id and not dados["fechada"]:
            msg_id = mid
            break

    if not msg_id:
        await ctx.send("⚠️ Nenhuma lista aberta encontrada para atualizar!")
        return

    dados = listas_ativas[msg_id]
    qtd_antiga = dados["qtd_times"]

    if nova_qtd <= qtd_antiga:
        await ctx.send(f"⚠️ A nova quantidade de times ({nova_qtd}) deve ser maior que a atual ({qtd_antiga})!")
        return

    dados["qtd_times"] = nova_qtd
    config_formacao = FORMAGOES.get(dados["esquema"], FORMAGOES["352"])

    for _ in range(nova_qtd - qtd_antiga):
        t_dict = {}
        for pos, qtd in config_formacao.items():
            t_dict[pos] = [None] * qtd
        dados["times"].append(t_dict)

    reservas_copia = list(dados["reservas"])
    for res in reservas_copia:
        user_mention = res["user"]
        colocado = False
        for pos in res["posicoes"]:
            for idx_t in range(qtd_antiga, nova_qtd):
                time = dados["times"][idx_t]
                if pos in time and None in time[pos]:
                    for i in range(len(time[pos])):
                        if time[pos][i] is None:
                            time[pos][i] = user_mention
                            colocado = True
                            break
                if colocado:
                    break
            if colocado:
                dados["reservas"] = [r for r in dados["reservas"] if r["user"] != user_mention]
                break

    channel = bot.get_channel(dados["channel_id"])
    msg = await channel.fetch_message(msg_id)

    novo_embed = gerar_embed(
        dados["titulo"], 
        dados["esquema"], 
        dados["categoria"], 
        dados["qtd_times"], 
        dados["times"], 
        dados["reservas"],
        dados["capitaes"]
    )
    await msg.edit(embed=novo_embed)
    await ctx.send(f"⚡ **Lista atualizada de {qtd_antiga} para {nova_qtd} times!** Os reservas foram escalados nos novos times.")

@bot.command(name="fecharlista")
async def fechar_lista(ctx):
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

    for i in range(min(2, dados["qtd_times"])):
        if not dados["capitaes"].get(i):
            for pos, vagas in dados["times"][i].items():
                for jogador in vagas:
                    if jogador:
                        dados["capitaes"][i] = jogador
                        break
                if dados["capitaes"].get(i):
                    break

    channel = bot.get_channel(dados["channel_id"])
    try:
        msg = await channel.fetch_message(msg_id)
        novo_embed = gerar_embed(
            dados["titulo"], 
            dados["esquema"], 
            dados["categoria"], 
            dados["qtd_times"], 
            dados["times"], 
            dados["reservas"],
            dados["capitaes"],
            fechada=True
        )
        await msg.edit(embed=novo_embed)
        await msg.clear_reactions()

        mensagem_escalacao = "🔒 **ESCALAÇÃO FINALIZADA E CONVOCADA!**\n\n"

        for idx, time in enumerate(dados["times"]):
            nome_time = NOMES_TIMES[idx] if idx < len(NOMES_TIMES) else f"Time {idx+1}"
            link_call = LINKS_CALL[idx] if idx < len(LINKS_CALL) else ""
            capitao = dados["capitaes"].get(idx) or "*Nenhum capitão definido*"

            jogadores = []
            for pos, vagas in time.items():
                for j in vagas:
                    if j:
                        jogadores.append(j)

            mencoes = " ".join(jogadores) if jogadores else "*Nenhum jogador escalado*"

            mensagem_escalacao += f"🛡️ **{nome_time.upper()}** (👑 Cap: {capitao})\n"
            mensagem_escalacao += f"👥 **Jogadores:** {mencoes}\n"
            if link_call:
                mensagem_escalacao += f"🔊 **Entrar na Call:** {link_call}\n"
            mensagem_escalacao += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"

        await ctx.send(mensagem_escalacao)

    except Exception as e:
        await ctx.send(f"⚠️ Erro ao atualizar lista: {e}")

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    msg_id = payload.message_id
    if msg_id not in listas_ativas:
        return

    dados = listas_ativas[msg_id]
    channel = bot.get_channel(payload.channel_id)
    msg = await channel.fetch_message(msg_id)
    user = await bot.fetch_user(payload.user_id)

    try:
        await msg.remove_reaction(payload.emoji, user)
    except Exception:
        pass

    if dados["fechada"]:
        return

    emoji_str = str(payload.emoji)

    if emoji_str == "👑":
        dados["capitaes"][0] = user.mention
    elif emoji_str == "🎗️":
        dados["capitaes"][1] = user.mention
    elif emoji_str == "❌":
        remover_jogador(dados["times"], dados["reservas"], dados["capitaes"], user.mention)
    elif emoji_str in EMOJIS_POSICAO:
        pos_key = EMOJIS_POSICAO[emoji_str]
        processar_posicao(dados["times"], dados["reservas"], pos_key, user.mention)

    novo_embed = gerar_embed(
        dados["titulo"], 
        dados["esquema"], 
        dados["categoria"], 
        dados["qtd_times"], 
        dados["times"], 
        dados["reservas"],
        dados["capitaes"]
    )
    await msg.edit(embed=novo_embed)

TOKEN = os.environ.get("DISCORD_TOKEN")
bot.run(TOKEN)
