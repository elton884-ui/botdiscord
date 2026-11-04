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

def gerar_embed(titulo, esquema, categoria, qtd_times, times_data, reservas, capitaes, fechada=False):
    cor = discord.Color.red() if fechada else discord.Color.green()
    
    embed = discord.Embed(
        title=f"📋 {titulo.upper()}" + (" [FECHADA]" if fechada else ""),
        description=f"⚽ **Formação:** `{esquema}` | **Foco:** `{categoria}`\n👥 **Times:** `{qtd_times}`\n\u200b",
        color=cor
    )

    val_capitaes_list = []
    for i in range(qtd_times):
        nome_t = NOMES_TIMES[i] if i < len(NOMES_TIMES) else f"Time {i+1}"
        cap = capitaes.get(i) or "*A definir (clique no botão)*"
        emoji_cap = EMOJIS_CAP[i % len(EMOJIS_CAP)]
        val_capitaes_list.append(f"{emoji_cap} **{nome_t}:** {cap}")

    val_capitaes = "\n".join(val_capitaes_list)
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
        embed.set_footer(text="Clique nos botões abaixo para se inscrever ou assumir capitão!")
        
    return embed

def jogador_no_time_principal(times_data, target_id):
    for time in times_data:
        for pos in time:
            for j in time[pos]:
                if j and extrair_id(j) == target_id:
                    return True
    return False

def jogador_no_time_especifico(time_data, target_id):
    for pos in time_data:
        for j in time_data[pos]:
            if j and extrair_id(j) == target_id:
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

def remover_jogador(times_data, reservas, capitaes, target_id):
    posicoes_liberadas = []
    for time in times_data:
        for pos in time:
            for i in range(len(time[pos])):
                if time[pos][i] and extrair_id(time[pos][i]) == target_id:
                    time[pos][i] = None
                    posicoes_liberadas.append(pos)

    reservas[:] = [r for r in reservas if extrair_id(r['user']) != target_id]

    for k, v in list(capitaes.items()):
        if v and extrair_id(v) == target_id:
            capitaes[k] = None

    for pos_liberada in posicoes_liberadas:
        promover_reserva(times_data, reservas, pos_liberada)

def processar_posicao(times_data, reservas, posicao, mention):
    user_id = extrair_id(mention)
    if jogador_no_time_principal(times_data, user_id):
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
        reservas[:] = [r for r in reservas if extrair_id(r['user']) != user_id]
    else:
        res_entry = None
        for r in reservas:
            if extrair_id(r['user']) == user_id:
                res_entry = r
                break

        if res_entry:
            if posicao not in res_entry['posicoes']:
                res_entry['posicoes'].append(posicao)
        else:
            reservas.append({"user": mention, "posicoes": [posicao]})

def checar_e_expandir_auto(dados):
    max_times = len(NOMES_TIMES)
    while dados["qtd_times"] < max_times:
        todos_cheios = True
        for time in dados["times"]:
            for pos, vagas in time.items():
                if None in vagas:
                    todos_cheios = False
                    break
            if not todos_cheios:
                break

        if todos_cheios:
            dados["qtd_times"] += 1
            idx_novo = dados["qtd_times"] - 1
            dados["capitaes"][idx_novo] = None

            config_formacao = FORMAGOES.get(dados["esquema"], FORMAGOES["352"])
            novo_time = {pos: [None] * qtd for pos, qtd in config_formacao.items()}
            dados["times"].append(novo_time)

            reservas_copia = list(dados["reservas"])
            for res in reservas_copia:
                user_mention = res["user"]
                user_id = extrair_id(user_mention)
                colocado = False
                for pos in res["posicoes"]:
                    time_idx = dados["qtd_times"] - 1
                    t = dados["times"][time_idx]
                    if pos in t and None in t[pos]:
                        for i in range(len(t[pos])):
                            if t[pos][i] is None:
                                t[pos][i] = user_mention
                                colocado = True
                                break
                    if colocado:
                        dados["reservas"] = [r for r in dados["reservas"] if extrair_id(r["user"]) != user_id]
                        break
        else:
            break

class ListaButtons(discord.ui.View):
    def __init__(self, esquema, qtd_times=2):
        super().__init__(timeout=None)
        
        for i in range(min(qtd_times, len(NOMES_TIMES))):
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
            await interaction.response.send_message("⚠️ Esta lista expirou na memória do bot (após o restart). Crie uma nova com !criarlista.", ephemeral=True)
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
            nome_t = NOMES_TIMES[time_idx] if time_idx < len(NOMES_TIMES) else f"Time {time_idx+1}"

            if len(dados["times"]) <= time_idx or not jogador_no_time_especifico(dados["times"][time_idx], user_id):
                await interaction.response.send_message(f"⚠️ Você precisa estar escalado no **{nome_t}** para ser o capitão dele!", ephemeral=True)
                return False

            cap_atual_id = extrair_id(dados["capitaes"].get(time_idx))

            if cap_atual_id == user_id:
                dados["capitaes"][time_idx] = None
            elif cap_atual_id is not None:
                await interaction.response.send_message(f"⚠️ O **{nome_t}** já tem um capitão definido! Ele precisa clicar no botão para sair antes que outro assuma.", ephemeral=True)
                return False
            else:
                for k in list(dados["capitaes"].keys()):
                    if extrair_id(dados["capitaes"].get(k)) == user_id:
                        dados["capitaes"][k] = None
                dados["capitaes"][time_idx] = user_mention

        elif custom_id == "btn_sair":
            remover_jogador(dados["times"], dados["reservas"], dados["capitaes"], user_id)

        elif custom_id.startswith("btn_pos_"):
            pos_key = custom_id.replace("btn_pos_", "")
            qtd_antiga = dados["qtd_times"]
            processar_posicao(dados["times"], dados["reservas"], pos_key, user_mention)
            checar_e_expandir_auto(dados)

            if dados["qtd_times"] != qtd_antiga:
                dados["view"] = ListaButtons(dados["esquema"], dados["qtd_times"])

        novo_embed = gerar_embed(
            dados["titulo"], 
            dados["esquema"], 
            dados["categoria"], 
            dados["qtd_times"], 
            dados["times"], 
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
        capitaes = {i: None for i in range(qtd_times)}

        view = ListaButtons(esquema, qtd_times)
        embed = gerar_embed(titulo, esquema, categoria, qtd_times, times_data, reservas, capitaes)
        msg = await ctx.send(embed=embed, view=view)

        listas_ativas[msg.id] = {
            "titulo": titulo,
            "esquema": esquema,
            "categoria": categoria,
            "qtd_times": qtd_times,
            "times": times_data,
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
        await ctx.send("⚠️ **Uso correto:** Digite `!remover @Jogador` (marcando o membro com @).")
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
        await ctx.send("⚠️ **Nenhuma lista ativa encontrada na memória!** Crie uma nova lista com `!criarlista`.")
        return

    dados = listas_ativas[msg_id]
    user_id = member.id

    capitaes_ids = [extrair_id(c) for c in dados["capitaes"].values() if c]

    esta_no_time = jogador_no_time_principal(dados["times"], user_id)
    esta_nos_reservas = any(extrair_id(r['user']) == user_id for r in dados["reservas"])
    esta_de_capitao = user_id in capitaes_ids

    if not esta_no_time and not esta_nos_reservas and not esta_de_capitao:
        await ctx.send(f"⚠️ O jogador {member.mention} não está escalado nesta lista.")
        return

    remover_jogador(dados["times"], dados["reservas"], dados["capitaes"], user_id)

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
    await msg.edit(embed=novo_embed, view=dados.get("view"))

    try:
        await ctx.message.delete()
    except Exception:
        pass

    msg_confirm = await ctx.send(f"🗑️ O jogador {member.mention} foi removido da escalação e do cargo de capitão!")
    try:
        await msg_confirm.delete(delay=4)
    except Exception:
        pass

@bot.command(name="atualizarlista")
async def atualizar_lista(ctx, nova_qtd: int):
    try:
        await ctx.message.delete()
    except Exception:
        pass

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
    for i in range(qtd_antiga, nova_qtd):
        dados["capitaes"][i] = None

    config_formacao = FORMAGOES.get(dados["esquema"], FORMAGOES["352"])

    for _ in range(nova_qtd - qtd_antiga):
        t_dict = {}
        for pos, qtd in config_formacao.items():
            t_dict[pos] = [None] * qtd
        dados["times"].append(t_dict)

    reservas_copia = list(dados["reservas"])
    for res in reservas_copia:
        user_mention = res["user"]
        user_id = extrair_id(user_mention)
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
                dados["reservas"] = [r for r in dados["reservas"] if extrair_id(r["user"]) != user_id]
                break

    dados["view"] = ListaButtons(dados["esquema"], nova_qtd)

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
    await msg.edit(embed=novo_embed, view=dados["view"])

    msg_confirm = await ctx.send(f"⚡ **Lista atualizada para {nova_qtd} times!** Reservas realocados.")
    try:
        await msg_confirm.delete(delay=4)
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

    all_cap_ids = [extrair_id(c) for c in dados["capitaes"].values() if c]

    for i in range(dados["qtd_times"]):
        if not dados["capitaes"].get(i):
            jogadores_do_time = [j for vagas in dados["times"][i].values() for j in vagas if j]
            candidatos = [j for j in jogadores_do_time if extrair_id(j) not in all_cap_ids]
            
            if candidatos:
                escolhido = random.choice(candidatos)
                dados["capitaes"][i] = escolhido
                all_cap_ids.append(extrair_id(escolhido))
            elif jogadores_do_time:
                escolhido = random.choice(jogadores_do_time)
                dados["capitaes"][i] = escolhido
                all_cap_ids.append(extrair_id(escolhido))

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
        await msg.edit(embed=novo_embed, view=None)

        mensagem_escalacao = "🔒 **ESCALAÇÃO FINALIZADA E CONVOCADA!**\n\n"

        for idx, time in enumerate(dados["times"]):
            nome_time = NOMES_TIMES[idx] if idx < len(NOMES_TIMES) else f"Time {idx+1}"
            capitao = dados["capitaes"].get(idx) or "*Nenhum capitão definido*"

            jogadores = []
            for pos, vagas in time.items():
                for j in vagas:
                    if j:
                        jogadores.append(j)

            mencoes = " ".join(jogadores) if jogadores else "*Nenhum jogador escalado*"

            mensagem_escalacao += f"🛡️ **{nome_time.upper()}** (👑 Cap: {capitao})\n"
            mensagem_escalacao += f"👥 **Jogadores:** {mencoes}\n"
            mensagem_escalacao += f"🔊 **Call:** Entrar na call do {nome_time}\n"
            mensagem_escalacao += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"

        await ctx.send(mensagem_escalacao)

    except Exception as e:
        await ctx.send(f"⚠️ Erro ao atualizar lista: {e}")

# --- INICIALIZAÇÃO DO BOT ---
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print("❌ ERRO CRÍTICO: A variável DISCORD_TOKEN não foi encontrada nas Environment Variables do Render!")
else:
    bot.run(TOKEN)
