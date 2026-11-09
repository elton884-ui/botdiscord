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

def gerar_embed_dinamico(titulo, esquema, categoria, titulares, reservas, capitaes, times_draft=None):
    if times_draft:
        embed = discord.Embed(
            title=f"📋 {titulo.upper()} (DRAFT EM ANDAMENTO)",
            description=f"⚽ **Formação:** `{esquema}` | **Foco:** `{categoria}`\n👥 **Inscritos Totais:** `{len(titulares) + len(reservas)}`\n\u200b",
            color=discord.Color.blue()
        )
        
        for idx in range(len(NOMES_TIMES)):
            nome_t = NOMES_TIMES[idx]
            emoji_cap = EMOJIS_CAP[idx]
            cap = capitaes.get(idx) or "*Nenhum*"
            
            membros = []
            for pos, lista_j in times_draft[idx].items():
                emoji_pos = POS_EMOJIS.get(pos, "⚽")
                for j in lista_j:
                    membros.append(f"{emoji_pos}{pos}: {j}")
            
            elenco_str = " | ".join(membros) if membros else "*Vazio*"
            embed.add_field(name=f"{emoji_cap} {nome_t.upper()} (Cap: {cap})", value=f"👥 {elenco_str}", inline=False)
            
        if titulares:
            restantes_str = ", ".join([item['user'] for item in titulares])
            embed.add_field(name="⏳ DISPONÍVEIS PARA ESCOLHA", value=restantes_str, inline=False)
    else:
        embed = discord.Embed(
            title=f"📋 {titulo.upper()}",
            description=f"⚽ **Formação:** `{esquema}` | **Foco:** `{categoria}`\n👥 **Titulares:** `{len(titulares)}` | ⏳ **Reservas:** `{len(reservas)}`\n\u200b",
            color=discord.Color.green()
        )

        val_capitaes_list = []
        for i in range(len(NOMES_TIMES)):
            nome_t = NOMES_TIMES[i]
            cap = capitaes.get(i) or "*A definir (clique no botão)*"
            emoji_cap = EMOJIS_CAP[i]
            val_capitaes_list.append(f"{emoji_cap} **{nome_t}:** {cap}")

        embed.add_field(name="⭐ CAPITÃES", value="\n".join(val_capitaes_list), inline=False)
        embed.add_field(name="\u200b", value="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", inline=False)

        config_formacao = FORMAGOES.get(esquema, FORMAGOES["352"])
        linhas_vagas = []

        for pos, qtd_por_time in config_formacao.items():
            emoji = POS_EMOJIS.get(pos, "⚽")
            limite_vagas = qtd_por_time * len(NOMES_TIMES)
            
            ocupantes_pos = [item for item in titulares if item['pos'] == pos]

            for i in range(limite_vagas):
                num_str = f" {i+1}" if limite_vagas > len(NOMES_TIMES) else ""
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
    
    embed.set_footer(text="Use os comandos do bot para gerenciar o sorteio e o draft!")
    return embed

def jogador_ja_esta_na_lista(titulares, reservas, target_id):
    for item in titulares:
        if extrair_id(item['user']) == target_id:
            return True
    for item in reservas:
        if extrair_id(item['user']) == target_id:
            return True
    return False

class ListaButtonsDinamica(discord.ui.View):
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

            limite_pos = config_formacao.get(pos_key, 1) * len(NOMES_TIMES)
            ocupantes_pos = [item for item in dados["titulares"] if item['pos'] == pos_key]

            if len(ocupantes_pos) < limite_pos:
                dados["titulares"].append({"user": user_mention, "pos": pos_key})
            else:
                dados["reservas"].append({"user": user_mention, "pos": pos_key})

        novo_embed = gerar_embed_dinamico(
            dados["titulo"], 
            dados["esquema"], 
            dados["categoria"], 
            dados["titulares"], 
            dados["reservas"],
            dados["capitaes"],
            dados.get("times_draft")
        )

        await interaction.response.edit_message(embed=novo_embed, view=dados["view"])
        return True

@bot.command(name="teste")
async def teste(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    ping_ms = round(bot.latency * 1000)
    
    feedback_msg = (
        "🤖 **DIAGNÓSTICO E TESTE DO BOT ROIPIAU** ⚽\n\n"
        f"🟢 **Status da Conexão:** Online e Operacional\n"
        f"⚡ **Latência (Ping):** `{ping_ms}ms`\n"
        f"📋 **Listas Ativas na Memória:** `{len(listas_ativas)}`\n"
        f"🔒 **Comandos:** `!criarlista`, `!fecharlista`, `!sorteiocapitao`, `!escolher`, `!remover`, `!teste` — **Tudo OK!**"
    )
    
    await ctx.send(feedback_msg, delete_after=15)

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
        capitaes = {i: None for i in range(len(NOMES_TIMES))}

        view = ListaButtonsDinamica(esquema)
        embed = gerar_embed_dinamico(titulo, esquema, categoria, titulares, reservas, capitaes)
        
        msg = await ctx.send(content="@everyone", embed=embed, view=view)

        listas_ativas[msg.id] = {
            "titulo": titulo,
            "esquema": esquema,
            "categoria": categoria,
            "titulares": titulares,
            "reservas": reservas,
            "capitaes": capitaes,
            "channel_id": ctx.channel.id,
            "fechada": False,
            "view": view,
            "times_draft": None
        }
    except Exception:
        await ctx.send("⚠️ **Formato inválido!** Use: `!criarlista 352;mei;LIGA CLUBS das 17h;2;0;1`")

@bot.command(name="sorteiocapitao")
async def sorteiocapitao(ctx, qtd_times: int = 2):
    msg_id = None
    if ctx.message.reference:
        msg_id = ctx.message.reference.message_id
    else:
        for mid, dados in reversed(list(listas_ativas.items())):
            if dados["channel_id"] == ctx.channel.id and not dados["fechada"]:
                msg_id = mid
                break

    if not msg_id or msg_id not in listas_ativas:
        await ctx.send("⚠️ Nenhuma lista ativa encontrada neste canal!")
        return

    dados = listas_ativas[msg_id]
    
    # Junta titulares e reservas para garantir que todos os inscritos participam do sorteio
    todos_inscritos = list(dados["titulares"]) + list(dados["reservas"])

    if len(todos_inscritos) < qtd_times:
        await ctx.send(f"⚠️ Jogadores insuficientes! Há {len(todos_inscritos)} inscrito(s) na lista e você pediu para sortear {qtd_times} capitães.")
        return

    capitaes_sorteados = random.sample(todos_inscritos, qtd_times)
    
    for i in range(qtd_times):
        dados["capitaes"][i] = capitaes_sorteados[i]['user']

    config_formacao = FORMAGOES.get(dados["esquema"], FORMAGOES["352"])
    dados["times_draft"] = [{pos: [] for pos in config_formacao.keys()} for _ in range(qtd_times)]

    uids_capitaes = [extrair_id(c['user']) for c in capitaes_sorteados]
    dados["titulares"] = [item for item in dados["titulares"] if extrair_id(item['user']) not in uids_capitaes]
    dados["reservas"] = [item for item in dados["reservas"] if extrair_id(item['user']) not in uids_capitaes]

    channel = bot.get_channel(dados["channel_id"])
    msg = await channel.fetch_message(msg_id)
    novo_embed = gerar_embed_dinamico(dados["titulo"], dados["esquema"], dados["categoria"], dados["titulares"], dados["reservas"], dados["capitaes"], dados["times_draft"])
    await msg.edit(embed=novo_embed, view=dados.get("view"))

    try:
        await ctx.message.delete()
    except Exception:
        pass
    await ctx.send(f"👑 **{qtd_times} Capitães sorteados com sucesso!** Já podem começar a escolher os jogadores com o comando `!escolher`.", delete_after=10)

@bot.command(name="escolher", aliases=["add"])
async def escolher(ctx, member: discord.Member, *, time_alvo_str):
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
    if not dados.get("times_draft"):
        await ctx.send("⚠️ O sorteio de capitães ainda não foi realizado! Use `!sorteiocapitao` primeiro.")
        return

    time_idx = -1
    for idx, nome_t in enumerate(NOMES_TIMES):
        if nome_t.lower() in time_alvo_str.lower():
            time_idx = idx
            break

    if time_idx == -1 or time_idx >= len(dados["times_draft"]):
        await ctx.send("⚠️ Time inválido! Use por exemplo: `!escolher @Jogador Time 2`")
        return

    user_id = member.id
    alvo_encontrado = None

    for item in dados["titulares"]:
        if extrair_id(item['user']) == user_id:
            alvo_encontrado = item
            dados["titulares"].remove(item)
            break

    if not alvo_encontrado:
        for item in dados["reservas"]:
            if extrair_id(item['user']) == user_id:
                alvo_encontrado = item
                dados["reservas"].remove(item)
                break

    if not alvo_encontrado:
        await ctx.send(f"⚠️ O jogador {member.mention} não foi encontrado na lista de disponíveis!")
        return

    pos = alvo_encontrado['pos']
    dados["times_draft"][time_idx][pos].append(alvo_encontrado['user'])

    channel = bot.get_channel(dados["channel_id"])
    msg = await channel.fetch_message(msg_id)
    novo_embed = gerar_embed_dinamico(dados["titulo"], dados["esquema"], dados["categoria"], dados["titulares"], dados["reservas"], dados["capitaes"], dados["times_draft"])
    await msg.edit(embed=novo_embed, view=dados.get("view"))

    try:
        await ctx.message.delete()
    except Exception:
        pass

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
    novo_embed = gerar_embed_dinamico(dados["titulo"], dados["esquema"], dados["categoria"], dados["titulares"], dados["reservas"], dados["capitaes"], dados.get("times_draft"))
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

    channel = bot.get_channel(dados["channel_id"])
    try:
        msg = await channel.fetch_message(msg_id)
        await msg.edit(view=None)

        if dados.get("times_draft"):
            times_montados = dados["times_draft"]
            qtd_times = len(times_montados)
            capitaes_atribuidos = dados["capitaes"]
            tipo_msg = "TIMES MONTADOS VIA DRAFT"
        else:
            esquema = dados["esquema"]
            config_formacao = FORMAGOES.get(esquema, FORMAGOES["352"])
            vagas_por_time = sum(config_formacao.values())
            total_titulares = len(dados["titulares"])
            
            if total_titulares > (vagas_por_time * 3):
                qtd_times = 4
            elif total_titulares > (vagas_por_time * 2):
                qtd_times = 3
            else:
                qtd_times = 2

            times_montados = [{pos: [] for pos in config_formacao.keys()} for _ in range(qtd_times)]
            capitaes_atribuidos = dados["capitaes"]

            restantes = list(dados["titulares"])
            for i in range(qtd_times):
                cap_str = capitaes_atribuidos.get(i)
                if cap_str:
                    cap_id = extrair_id(cap_str)
                    encontrado = None
                    for item in restantes:
                        if extrair_id(item['user']) == cap_id:
                            encontrado = item
                            break
                    if encontrado:
                        restantes.remove(encontrado)
                        pos = encontrado['pos']
                        if len(times_montados[i][pos]) < config_formacao[pos]:
                            times_montados[i][pos].append(encontrado['user'])
                        else:
                            for p in config_formacao.keys():
                                if len(times_montados[i][p]) < config_formacao[p]:
                                    times_montados[i][p].append(encontrado['user'])
                                    break

            random.shuffle(restantes)
            for item in restantes:
                pos = item['pos']
                times_com_vaga = [i for i in range(qtd_times) if len(times_montados[i][pos]) < config_formacao[pos]]
                if times_com_vaga:
                    t_escolhido = random.choice(times_com_vaga)
                    times_montados[t_escolhido][pos].append(item['user'])
                else:
                    dados["reservas"].append(item)

            tipo_msg = "TIMES CONVOCADOS COM SORTEIO ALEATÓRIO"

        mensagem_escalacao = f"🔒 **ESCALAÇÃO FINALIZADA ({qtd_times} TIMES - {tipo_msg})!**\n\n"

        for idx in range(qtd_times):
            nome_time = NOMES_TIMES[idx]
            capitao = capitaes_atribuidos.get(idx, "*Nenhum*")

            membros_time = []
            for pos, lista_jogadores in times_montados[idx].items():
                emoji = POS_EMOJIS.get(pos, "⚽")
                for j in lista_jogadores:
                    membros_time.append(f"{emoji}{pos}: {j}")

            mencoes_str = " | ".join(membros_time) if membros_time else "*Nenhum jogador*"

            mensagem_escalacao += f"🛡️ **{nome_time.upper()}** (👑 Cap: {capitao})\n"
            mensagem_escalacao += f"👥 **Elenco:** {mencoes_str}\n"
            mensagem_escalacao += f"🔊 **Call:** Entrar na call do **{nome_time}**\n"
            mensagem_escalacao += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"

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
