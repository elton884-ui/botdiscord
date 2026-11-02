import os
import random
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord.ext import commands

# --- SERVIDOR WEB PARA MANTER NO PLANO GRATUITO DO RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Roipau esta rodando!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# Inicia o servidor web em segundo plano
Thread(target=run_web_server, daemon=True).start()

# --- CÓDIGO DO BOT DISCORD ---
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

def gerar_embed(titulo, esquema, categoria, qtd_times, times_data, reservas, fechada=False):
    cor = discord.Color.red() if fechada else discord.Color.green()
    
    embed = discord.Embed(
        title=f"📋 {titulo.upper()}" + (" [FECHADA]" if fechada else ""),
        description=f"⚽ **Formação:** `{esquema}` | **Foco:** `{categoria}`\n👥 **Times:** `{qtd_times}`\n\u200b",
        color=cor
    )

    for idx, time in enumerate(times_data, start=1):
        linhas = []
        for pos, vagas in time.items():
            emoji = POS_EMOJIS.get(pos, "🔹")
            if len(vagas) == 1:
                linhas.append(f"{emoji} `{pos}:` {vagas[0] or ''}")
            else:
                for i, p in enumerate(vagas, start=1):
                    linhas.append(f"{emoji} `{pos} {i}:` {p or ''}")

        embed.add_field(name=f"⚽ TIME {idx}", value="\n".join(linhas), inline=False)
        
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
        embed.set_footer(text="Ao sair um titular, o 1º reserva da posição assume automaticamente! | ❌ Sair")
        
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

def remover_jogador(times_data, reservas, mention):
    posicoes_liberadas = []
    for time in times_data:
        for pos in time:
            for i in range(len(time[pos])):
                if time[pos][i] == mention:
                    time[pos][i] = None
                    posicoes_liberadas.append(pos)

    reservas[:] = [r for r in reservas if r['user'] != mention]

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

        embed = gerar_embed(titulo, esquema, categoria, qtd_times, times_data, reservas)
        msg = await ctx.send(embed=embed)

        listas_ativas[msg.id] = {
            "titulo": titulo,
            "esquema": esquema,
            "categoria": categoria,
            "qtd_times": qtd_times,
            "times": times_data,
            "reservas": reservas,
            "channel_id": ctx.channel.id,
            "fechada": False
        }

        for pos in config_formacao.keys():
            if pos in POS_EMOJIS:
                await msg.add_reaction(POS_EMOJIS[pos])
        await msg.add_reaction("❌")

    except Exception:
        await ctx.send("⚠️ **Formato inválido!** Use: `!criarlista 352;mei;LIGA CLUBS das 17h;2;0;1`")

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
            fechada=True
        )
        await msg.edit(embed=novo_embed)
        await msg.clear_reactions()
        await ctx.send("🔒 **Lista fechada com sucesso!**")
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

    if emoji_str == "❌":
        remover_jogador(dados["times"], dados["reservas"], user.mention)
    elif emoji_str in EMOJIS_POSICAO:
        pos_key = EMOJIS_POSICAO[emoji_str]
        processar_posicao(dados["times"], dados["reservas"], pos_key, user.mention)

    novo_embed = gerar_embed(
        dados["titulo"], 
        dados["esquema"], 
        dados["categoria"], 
        dados["qtd_times"], 
        dados["times"], 
        dados["reservas"]
    )
    await msg.edit(embed=novo_embed)

# Substitui pela tua chave do Discord:
TOKEN = os.environ.get("DISCORD_TOKEN", "SEU_TOKEN_DO_DISCORD_AQUI")
bot.run(TOKEN)
