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

CANAL_AVISO_ID = 1570420721312866436     # Canal de avisos/relatórios do bot[cite: 1]
CANAL_ESCALACAO_ID = 1570429628588499086 # Canal dedicado ao histórico de escalações e agradecimentos[cite: 1]

VERSAO_ATUAL = "v2.2"
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
                    with open(ARQUIVO_VERSAO, "r") as f:
                        ultima_versao = f.read().strip()
                
                if ultima_versao != VERSAO_ATUAL:
                    changelog_msg = (
                        f"🚀 **RoiPau FC Bot atualizado com sucesso!** (Versão {VERSAO_ATUAL})\n\n"
                        "📋 **O que há de novo:**\n"
                        "• **Comando `!reabrir` (Restaurar):** Permite restaurar e reabrir rapidamente a última lista fechada no canal, trazendo os botões de volta[cite: 1]."
                    )
                    await channel.send(changelog_msg)
                    
                    with open(ARQUIVO_VERSAO, "w") as f:
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

def jogador_esta_nos_titulares(titulares, target_id):
    for item in titulares:
        if extrair_id(item['user']) == target_id:
            return True
    return False

def jogador_ja_esta_na_lista(titulares, reservas, target_id):
    return jogador_esta_nos_titulares(titulares, target_id) or any(extrair_id(item['user']) == target_id for item in reservas)

def gerar_embed_dinamico(titulo, esquema, categoria, titulares, reservas, capitaes, qtd_times_ativos=2):
    embed = discord.Embed(
        title=f"📋 {titulo.upper()}",
        description=f"⚽ **Formação:** `{esquema}` | **Foco:** `{categoria}` | 🛡️ **Times Ativos:** `{qtd_times_ativos}`\n👥 **Titulares:** `{len(titulares)}` | ⏳ **Reservas:** `{len(reservas)}`\n\u200b",
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
    embed.set_footer(text="Clique nos botões abaixo para preencher a vaga ou use os comandos progressivos!")
    return embed

class ListaButtonsDinamica(discord.ui.View):
    def __init__(self, esquema, qtd_times=2):
        super().__init__(timeout=None)
        
        for i in range(qtd_times):
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
        qtd_times_ativos = dados["qtd_times_ativos"]
        capitaes_dict = {int(k): v for k, v in dados["capitaes"].items()}

        if custom_id.startswith("btn_cap_time"):
            time_idx = int(custom_id.replace("btn_cap_time", "")) - 1
            if time_idx >= qtd_times_ativos:
                await interaction.response.send_message(f"⚠️ O Time {time_idx+1} ainda não está aberto!", ephemeral=True)
                return False

            nome_t = NOMES_TIMES[time_idx]

            if not jogador_ja_esta_na_lista(dados["titulares"], dados["reservas"], user_id):
                await interaction.response.send_message(f"⚠️ Você precisa estar na lista para ser capitão do **{nome_t}**!", ephemeral=True)
                return False

            if qtd_times_ativos <= 2 and not jogador_esta_nos_titulares(dados["titulares"], user_id):
                await interaction.response.send_message(f"⚠️ Com apenas 2 times ativos, apenas jogadores **titulares** podem ser capitães!", ephemeral=True)
                return False

            cap_atual_id = extrair_id(capitaes_dict.get(time_idx))

            if cap_atual_id == user_id:
                capitaes_dict[time_idx] = None
            elif cap_atual_id is not None:
                await interaction.response.send_message(f"⚠️ O **{nome_t}** já tem um capitão definido!", ephemeral=True)
                return False
            else:
                for k in list(capitaes_dict.keys()):
                    if extrair_id(capitaes_dict.get(k)) == user_id:
                        capitaes_dict[k] = None
                capitaes_dict[time_idx] = user_mention

            dados["capitaes"] = capitaes_dict

        elif custom_id == "btn_sair":
            dados["titulares"] = [item for item in dados["titulares"] if extrair_id(item['user']) != user_id]
            dados["reservas"] = [item for item in dados["reservas"] if extrair_id(item['user']) != user_id]
            for k, v in list(capitaes_dict.items()):
                if extrair_id(v) == user_id:
                    capitaes_dict[k] = None
            dados["capitaes"] = capitaes_dict

        elif custom_id.startswith("btn_pos_"):
            pos_key = custom_id.replace("btn_pos_", "")
            
            if jogador_ja_esta_na_lista(dados["titulares"], dados["reservas"], user_id):
                await interaction.response.send_message("⚠️ Você já está inscrito nesta lista!", ephemeral=True)
                return False

            limite_pos = config_formacao.get(pos_key, 1) * qtd_times_ativos
            ocupantes_pos = [item for item in dados["titulares"] if item['pos'] == pos_key]

            if len(ocupantes_pos) < limite_pos:
                dados["titulares"].append({"user": user_mention, "pos": pos_key})
            else:
                dados["reservas"].append({"user": user_mention, "pos": pos_key})

        salvar_listas()

        novo_embed = gerar_embed_dinamico(
            dados["titulo"], 
            dados["esquema"], 
            dados["categoria"], 
            dados["titulares"], 
            dados["reservas"],
            dados["capitaes"],
            dados["qtd_times_ativos"]
        )

        await interaction.response.edit_message(embed=novo_embed, view=dados["view"])
        return True

@bot.command(name="comandos")
async def comandos(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = discord.Embed(
        title="⚽ PAINEL DE COMANDOS — ROIPIAU FC",
        description="Lista completa de comandos e funcionalidades oficiais para gerenciar os treinos e campeonatos:\n\u200b",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="📋 Gestão de Listas",
        value=(
            "`!criarlista <esquema>;<foco>;<titulo>;...`\n> Cria a convocação oficial com botões interativos.\n"
            "`!listasativas` ou `!ativas`\n> Envia no canal de avisos o resumo de todas as convocações abertas[cite: 1].\n"
            "`!reabrir` ou `!restaurar`\n> Reabre e restaura a última lista fechada no canal com os botões ativos[cite: 1].\n"
            "`!limparmortas`\n> Remove do sistema listas cujas mensagens já foram apagadas no Discord[cite: 1].\n"
            "`!limpar`\n> Limpa e reseta todos os inscritos e reservas da lista ativa.\n"
            "`!fecharlista`\n> Encerra as inscrições, aloca capitães, sorteia os times e programa limpeza de 24h[cite: 1]."
        ),
        inline=False
    )

    embed.add_field(
        name="⚙️ Comandos Avançados & Simulação",
        value=(
            "`!simular <quantidade>`\n> Cria jogadores virtuais para testar lotação e fila de suplentes[cite: 1].\n"
            "`!addtime 3` ou `!addtime 4`\n> Abre o 3º ou 4º time (permitindo capitães dos reservas) e sorteia automaticamente[cite: 1].\n"
            "`!remover @Jogador`\n> Remove um participante específico da lista ativa."
        ),
        inline=False
    )

    embed.add_field(
        name="🛠️ Sistema & Diagnóstico",
        value=(
            "`!teste`\n> Verifica a latência (ping) e o status operacional do bot.\n"
            "💡 **Dica de Relatório:** Reaja com `✅` em qualquer mensagem do bot no canal de avisos para apagá-la instantaneamente[cite: 1]!"
        ),
        inline=False
    )

    embed.set_footer(text="RoiPau FC Bot • Gestão inteligente de elencos ⚽🔥")
    await ctx.send(embed=embed)

@bot.command(name="listasativas", aliases=["ativas"])
async def listas_ativas_cmd(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    abertas = {mid: dados for mid, dados in listas_ativas.items() if not dados["fechada"]}

    if not abertas:
        await ctx.send("⚠️ Não há nenhuma lista de convocação aberta no momento!", delete_after=10)
        return

    embed = discord.Embed(
        title="📋 CONVOCAÇÕES ABERTAS — ROIPIAU FC",
        description=f"Total de listas ativas salvas: `{len(abertas)}`\n\u200b",
        color=discord.Color.gold()
    )

    for mid, dados in abertas.items():
        canal = bot.get_channel(dados["channel_id"])
        nome_canal = f"<#{dados['channel_id']}>" if canal else "Canal desconhecido"
        
        info_txt = (
            f"🏟️ **Canal:** {nome_canal}\n"
            f"⚽ **Formação:** `{dados['esquema']}` | **Foco:** `{dados['categoria']}`\n"
            f"👥 **Titulares Inscritos:** `{len(dados['titulares'])}` | ⏳ **Reservas:** `{len(dados['reservas'])}`\n"
            f"🔗 [Ir para a Mensagem da Lista](https://discord.com/channels/{ctx.guild.id}/{dados['channel_id']}/{mid})"
        )
        embed.add_field(name=f"📌 {dados['titulo']}", value=info_txt, inline=False)

    embed.set_footer(text="RoiPau FC Bot • Gestão inteligente de elencos ⚽🔥")

    canal_aviso = bot.get_channel(CANAL_AVISO_ID)
    if canal_aviso:
        await canal_aviso.send(embed=embed)
    else:
        await ctx.send(embed=embed)

@bot.command(name="reabrir", aliases=["restaurar"])
async def reabrir_lista(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    # Encontra a última lista fechada neste canal
    msg_id_alvo = None
    for mid, dados in reversed(list(listas_ativas.items())):
        if dados["channel_id"] == ctx.channel.id and dados["fechada"]:
            msg_id_alvo = mid
            break

    if not msg_id_alvo or msg_id_alvo not in listas_ativas:
        await ctx.send("⚠️ Nenhuma lista fechada encontrada neste canal para restaurar!", delete_after=10)
        return

    dados = listas_ativas[msg_id_alvo]
    dados["fechada"] = False
    
    # Recria a view com os botões interativos
    nova_view = ListaButtonsDinamica(dados["esquema"], qtd_times=dados["qtd_times_ativos"])
    dados["view"] = nova_view
    salvar_listas()

    channel = bot.get_channel(dados["channel_id"])
    try:
        msg = await channel.fetch_message(msg_id_alvo)
        novo_embed = gerar_embed_dinamico(
            dados["titulo"], dados["esquema"], dados["categoria"], 
            dados["titulares"], dados["reservas"], dados["capitaes"], dados["qtd_times_ativos"]
        )
        await msg.edit(embed=novo_embed, view=nova_view)
        await ctx.send(f"🔄 **Lista reaberta e restaurada com sucesso!** Os botões estão ativos novamente.", delete_after=12)
    except Exception as e:
        await ctx.send(f"⚠️ Erro ao tentar restaurar a mensagem da lista: {e}", delete_after=10)

@bot.command(name="limparmortas")
async def limpar_mortas(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    removidas = 0
    ids_para_remover = []

    for mid, dados in list(listas_ativas.items()):
        canal_id = dados.get("channel_id")
        canal = bot.get_channel(canal_id)
        
        if not canal:
            ids_para_remover.append(mid)
            removidas += 1
            continue
            
        try:
            await canal.fetch_message(mid)
        except discord.NotFound:
            ids_para_remover.append(mid)
            removidas += 1
        except discord.Forbidden:
            pass
        except Exception:
            pass

    for mid in ids_para_remover:
        del listas_ativas[mid]

    if removidas > 0:
        salvar_listas()
        await ctx.send(f"🧹 **Limpeza concluída!** `{removidas}` listas órfãs/apagadas foram removidas do sistema.", delete_after=12)
    else:
        await ctx.send("✨ **Tudo limpo!** Nenhuma lista órfã encontrada no sistema.", delete_after=10)

@bot.command(name="teste")
async def teste(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    ping_ms = round(bot.latency * 1000)
    
    feedback_msg = (
        "🤖 **DIAGNÓSTICO E TESTE DO BOT ROIPIAU** ⚽\n\n"
        f"🟢 **Status da Conexão:** Online e Operacional (com persistência JSON e reabertura)\n"
        f"⚡ **Latência (Ping):** `{ping_ms}ms`\n"
        f"📋 **Listas Ativas Salvas:** `{len(listas_ativas)}`\n"
        f"🔒 **Comandos:** `!comandos`, `!listasativas`, `!reabrir`, `!limparmortas`, `!criarlista`, `!limpar`, `!simular`, `!addtime`, `!fecharlista`, `!remover`, `!teste` — **Tudo OK!**"
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
        capitaes = {0: None, 1: None}
        qtd_times_ativos = 2

        view = ListaButtonsDinamica(esquema, qtd_times=qtd_times_ativos)
        embed = gerar_embed_dinamico(titulo, esquema, categoria, titulares, reservas, capitaes, qtd_times_ativos)
        
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
            "qtd_times_ativos": qtd_times_ativos
        }
        salvar_listas()
    except Exception:
        await ctx.send("⚠️ **Formato inválido!** Use: `!criarlista 352;mei;LIGA CLUBS das 17h;2;0;1`")

@bot.command(name="limpar")
async def limpar(ctx):
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
        await ctx.send("⚠️ Nenhuma lista ativa encontrada para limpar!", delete_after=10)
        return

    dados = listas_ativas[msg_id]
    dados["titulares"] = []
    dados["reservas"] = []
    dados["capitaes"] = {i: None for i in range(dados["qtd_times_ativos"])}
    salvar_listas()

    channel = bot.get_channel(dados["channel_id"])
    msg = await channel.fetch_message(msg_id)
    novo_embed = gerar_embed_dinamico(
        dados["titulo"], dados["esquema"], dados["categoria"], 
        dados["titulares"], dados["reservas"], dados["capitaes"], dados["qtd_times_ativos"]
    )
    await msg.edit(embed=novo_embed, view=dados.get("view"))
    await ctx.send("🧹 **Lista limpa com sucesso!** Todos os inscritos e capitães foram resetados.", delete_after=10)

@bot.command(name="simular")
async def simular(ctx, quantidade: int):
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
        await ctx.send("⚠️ Crie uma lista primeiro com `!criarlista` antes de simular!", delete_after=10)
        return

    dados = listas_ativas[msg_id]
    esquema = dados["esquema"]
    config_formacao = FORMAGOES.get(esquema, FORMAGOES["352"])
    qtd_times = dados["qtd_times_ativos"]
    
    posicoes_disponiveis = []
    for pos, qtd in config_formacao.items():
        for _ in range(qtd * qtd_times):
            posicoes_disponiveis.append(pos)

    titulares = []
    reservas = []

    for i in range(1, quantidade + 1):
        nome_simulado = f"🤖 Jogador {i}"
        if posicoes_disponiveis:
            pos = posicoes_disponiveis.pop(0)
            titulares.append({"user": nome_simulado, "pos": pos})
        else:
            pos_res = list(config_formacao.keys())[i % len(config_formacao)]
            reservas.append({"user": nome_simulado, "pos": pos_res})

    dados["titulares"] = titulares
    dados["reservas"] = reservas
    salvar_listas()

    channel = bot.get_channel(dados["channel_id"])
    msg = await channel.fetch_message(msg_id)
    novo_embed = gerar_embed_dinamico(
        dados["titulo"], dados["esquema"], dados["categoria"], 
        dados["titulares"], dados["reservas"], dados["capitaes"], dados["qtd_times_ativos"]
    )
    await msg.edit(embed=novo_embed, view=dados.get("view"))
    await ctx.send(f"🧪 **Simulação concluída!** Inseridos `{quantidade}` jogadores virtuais.", delete_after=10)

@bot.command(name="addtime")
async def addtime(ctx, numero_time: int):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    if numero_time not in [3, 4]:
        await ctx.send("⚠️ Você só pode adicionar o `3` ou o `4` time!", delete_after=10)
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
        await ctx.send("⚠️ Nenhuma lista ativa encontrada!", delete_after=10)
        return

    dados = listas_ativas[msg_id]
    
    if dados["qtd_times_ativos"] >= numero_time:
        await ctx.send(f"⚠️ O **Time {numero_time}** já está aberto!", delete_after=10)
        return

    if dados["qtd_times_ativos"] != numero_time - 1:
        await ctx.send(f"⚠️ Você deve abrir os times em ordem! Abra o Time 3 antes do Time 4.", delete_after=10)
        return

    dados["qtd_times_ativos"] = numero_time
    time_idx = numero_time - 1
    capitaes_dict = {int(k): v for k, v in dados["capitaes"].items()}

    candidatos_cap = dados["reservas"] if dados["reservas"] else dados["titulares"]
    
    if candidatos_cap:
        sorteado = random.choice(candidatos_cap)
        capitaes_dict[time_idx] = sorteado['user']
        
        if sorteado in dados["reservas"]:
            dados["reservas"].remove(sorteado)
        elif sorteado in dados["titulares"]:
            dados["titulares"].remove(sorteado)
    else:
        capitaes_dict[time_idx] = "*Nenhum (Sem jogadores disponíveis)*"

    dados["capitaes"] = capitaes_dict
    salvar_listas()

    nova_view = ListaButtonsDinamica(dados["esquema"], qtd_times=dados["qtd_times_ativos"])
    dados["view"] = nova_view

    channel = bot.get_channel(dados["channel_id"])
    msg = await channel.fetch_message(msg_id)
    
    novo_embed = gerar_embed_dinamico(
        dados["titulo"], dados["esquema"], dados["categoria"], 
        dados["titulares"], dados["reservas"], dados["capitaes"], dados["qtd_times_ativos"]
    )
    await msg.edit(embed=novo_embed, view=nova_view)
    await ctx.send(f"🛡️ **TIME {numero_time} ABERTO COM SUCESSO!** Capitão sorteado automaticamente.", delete_after=12)

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
    capitaes_dict = {int(k): v for k, v in dados["capitaes"].items()}

    dados["titulares"] = [item for item in dados["titulares"] if extrair_id(item['user']) != user_id]
    dados["reservas"] = [item for item in dados["reservas"] if extrair_id(item['user']) != user_id]
    for k, v in list(capitaes_dict.items()):
        if extrair_id(v) == user_id:
            capitaes_dict[k] = None
    dados["capitaes"] = capitaes_dict
    salvar_listas()

    channel = bot.get_channel(dados["channel_id"])
    msg = await channel.fetch_message(msg_id)
    novo_embed = gerar_embed_dinamico(dados["titulo"], dados["esquema"], dados["categoria"], dados["titulares"], dados["reservas"], dados["capitaes"], dados["qtd_times_ativos"])
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
    salvar_listas()

    esquema = dados["esquema"]
    config_formacao = FORMAGOES.get(esquema, FORMAGOES["352"])
    qtd_times = dados["qtd_times_ativos"]

    times_montados = [{pos: [] for pos in config_formacao.keys()} for _ in range(qtd_times)]
    capitaes_atribuidos = {int(k): v for k, v in dados["capitaes"].items()}

    todos_participantes = [item['user'] for item in dados["titulares"]] + [item['user'] for item in dados["reservas"]]

    restantes = list(dados["titulares"])
    reservas_disponiveis = list(dados["reservas"])

    for i in range(qtd_times):
        cap_str = capitaes_atribuidos.get(i)
        if cap_str:
            cap_id = extrair_id(cap_str)
            encontrado = None
            origem = None

            for item in restantes:
                if extrair_id(item['user']) == cap_id:
                    encontrado = item
                    origem = "titular"
                    break
            
            if not encontrado:
                for item in reservas_disponiveis:
                    if extrair_id(item['user']) == cap_id:
                        encontrado = item
                        origem = "reserva"
                        break

            if encontrado:
                if origem == "titular":
                    restantes.remove(encontrado)
                else:
                    reservas_disponiveis.remove(encontrado)

                pos = encontrado['pos']
                if len(times_montados[i][pos]) < config_formacao[pos]:
                    times_montados[i][pos].append(encontrado['user'])
                else:
                    alocado = False
                    for p in config_formacao.keys():
                        if len(times_montados[i][p]) < config_formacao[p]:
                            times_montados[i][p].append(encontrado['user'])
                            alocado = True
                            break
                    if not alocado:
                        reservas_disponiveis.append(encontrado)

    dados["reservas"] = reservas_disponiveis
    salvar_listas()

    random.shuffle(restantes)

    for item in restantes:
        pos = item['pos']
        times_com_vaga_pos = [i for i in range(qtd_times) if len(times_montados[i][pos]) < config_formacao[pos]]
        
        if times_com_vaga_pos:
            times_com_vaga_pos.sort(key=lambda t: sum(len(lst) for lst in times_montados[t].values()))
            t_escolhido = times_com_vaga_pos[0]
            times_montados[t_escolhido][pos].append(item['user'])
        else:
            vagas_livres = []
            for i in range(qtd_times):
                for p in config_formacao.keys():
                    if len(times_montados[i][p]) < config_formacao[p]:
                        vagas_livres.append((i, p))
            
            if vagas_livres:
                vagas_livres.sort(key=lambda item_vaga: sum(len(lst) for lst in times_montados[item_vaga[0]].values()))
                t_escolhido, p_escolhida = vagas_livres[0]
                times_montados[t_escolhido][p_escolhida].append(item['user'])
            else:
                dados["reservas"].append(item)

    for i in range(qtd_times):
        membros = [j for v in times_montados[i].values() for j in v]
        if not membros:
            if dados["reservas"]:
                puxado = dados["reservas"].pop(0)
                p = puxado['pos']
                times_montados[i][p].append(puxado['user'])
            else:
                for outro_i in range(qtd_times):
                    for p, lista_j in times_montados[outro_i].items():
                        if len(lista_j) > 1:
                            movido = lista_j.pop()
                            times_montados[i][p].append(movido)
                            break
                    break

    for i in range(qtd_times):
        if i not in capitaes_atribuidos or not capitaes_atribuidos[i]:
            candidatos = [j for v in times_montados[i].values() for j in v]
            if candidatos:
                sorteado = random.choice(candidatos)
                capitaes_atribuidos[i] = sorteado
            else:
                capitaes_atribuidos[i] = "*Nenhum*"

    channel = bot.get_channel(dados["channel_id"])
    try:
        msg = await channel.fetch_message(msg_id)
        await msg.edit(view=None)

        mensagem_escalacao = f"🔒 **ESCALAÇÃO FINALIZADA ({qtd_times} TIMES - EQUILIBRADOS E SORTEADOS)!**\n\n"

        for idx in range(qtd_times):
            nome_time = NOMES_TIMES[idx]
            capitao = capitaes_atribuidos.get(idx, "*Nenhum*")

            membros_linhas = []
            for pos, lista_jogadores in times_montados[idx].items():
                emoji = POS_EMOJIS.get(pos, "⚽")
                for j in lista_jogadores:
                    membros_linhas.append(f"> {emoji} **{pos}:** {j}")

            elenco_str = "\n".join(membros_linhas) if membros_linhas else "> *Nenhum jogador*"

            mensagem_escalacao += f"🛡️ **{nome_time.upper()}** (👑 Cap: {capitao})\n"
            mensagem_escalacao += f"👥 **Elenco:**\n{elenco_str}\n"
            mensagem_escalacao += f"🔊 **Call:** Entrar na call do **{nome_time}**\n"
            mensagem_escalacao += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"

        if dados["reservas"]:
            res_str = ", ".join([f"{item['user']} ({item['pos']})" for item in dados["reservas"]])
            mensagem_escalacao += f"⏳ **Suplentes / Reservas:** {res_str}\n"

        msg_escalacao_enviada = await ctx.send(mensagem_escalacao)

        relatorio_msg_enviada = None
        canal_escalacao = bot.get_channel(CANAL_ESCALACAO_ID)
        if canal_escalacao:
            participantes_str = ", ".join(todos_participantes
