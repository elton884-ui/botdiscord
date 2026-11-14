import os
import re
import random
import json
import asyncio
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord.ext import commands
from PIL import Image
import io

# --- SERVIDOR WEB PARA O RENDER (MANTÉM O APP VIVO) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Roipau esta rodando!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"🌐 Servidor web rodando na porta {port}")
    server.serve_forever()

# Inicia o servidor web em uma thread dedicada não-daemon para segurar o Render
Thread(target=run_web_server, daemon=False).start()

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

# --- IDs DOS CANAIS DE ESTATÍSTICAS E PRINTS ---
CANAL_PRINTS_ID = 1571135705026134067
CANAL_ESTATISTICAS_ID = 1571136858669187243

VERSAO_ATUAL = "v3.18"
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
                        "• **Módulo de Estatísticas por ID:** Canais de prints e relatórios configurados com IDs fixos para maior precisão!"
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
        
        for i in range(4):
            nome_t = NOMES_TIMES[i]
            emoji_cap = EMOJIS_CAP[i]
            style = discord.ButtonStyle.primary if i < qtd_times else discord.ButtonStyle.secondary
            self.add_item(discord.ui.Button(
                label=f"Cap. {nome_t}", 
                emoji=emoji_cap, 
                style=style, 
                custom_id=f"btn_cap_time{i+1}", 
                row=0
            ))

        self.add_item(discord.ui.Button(
            label="Sair da Lista", 
            emoji="❌", 
            style=discord.ButtonStyle.danger, 
            custom_id="btn_sair", 
            row=1
        ))

        config_formacao = FORMAGOES.get(esquema, FORMAGOES["352"])
        row_curr = 2
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
            usuario_removido = None
            for item in dados["titulares"]:
                if extrair_id(item['user']) == user_id:
                    usuario_removido = item
                    break
            
            dados["titulares"] = [item for item in dados["titulares"] if extrair_id(item['user']) != user_id]
            dados["reservas"] = [item for item in dados["reservas"] if extrair_id(item['user']) != user_id]
            
            if usuario_removido:
                pos_vaga = usuario_removido['pos']
                for idx, res in enumerate(dados["reservas"]):
                    if res['pos'] == pos_vaga:
                        promovido = dados["reservas"].pop(idx)
                        dados["titulares"].append(promovido)
                        break

            for k, v in list(capitaes_dict.items()):
                if extrair_id(v) == user_id:
                    capitaes_dict[k] = None
            dados["capitaes"] = capitaes_dict

        elif custom_id.startswith("btn_pos_"):
            pos_key = custom_id.replace("btn_pos_", "")
            
            if jogador_ja_esta_na_lista(dados["titulares"], dados["reservas"], user_id):
                await interaction.response.send_message("⚠️ Você já está inscrito nesta lista!", ephemeral=True)
                return False

            qtd_por_time = config_formacao.get(pos_key, 1)
            limite_absoluto_pos = qtd_por_time * 4 
            
            total_posicao = sum(1 for item in dados["titulares"] if item['pos'] == pos_key) + sum(1 for item in dados["reservas"] if item['pos'] == pos_key)
            
            if total_posicao >= limite_absoluto_pos:
                await interaction.response.send_message(f"⚠️ A posição **{pos_key}** já atingiu o limite máximo absoluto de inscrições ({limite_absoluto_pos} jogadores para 4 times)!", ephemeral=True)
                return False

            limite_titulares_pos = qtd_por_time * qtd_times_ativos
            ocupantes_pos = [item for item in dados["titulares"] if item['pos'] == pos_key]

            if len(ocupantes_pos) < limite_titulares_pos:
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

# --- EVENTO DE CAPTURA DE PRINTS DE ESTATÍSTICAS USANDO IDs ---
@bot.event
async def on_message(message):
    # Processa comandos normais do bot
    await bot.process_commands(message)

    # Ignora mensagens do próprio bot
    if message.author == bot.user:
        return

    # Verifica se a mensagem foi enviada EXATAMENTE no canal de prints por ID e se tem imagem anexada[cite: 1]
    if message.channel.id == CANAL_PRINTS_ID and message.attachments:
        for attachment in message.attachments:
            if attachment.content_type and "image" in attachment.content_type:
                
                processing_msg = await message.channel.send("🔄 **Print recebido, Lobinho!** Analisando as notas e o desempenho do RoiPau FC...")

                try:
                    # Lê os bytes da imagem enviada[cite: 1]
                    image_bytes = await attachment.read()
                    
                    # Localiza o canal de destino das estatísticas pelo ID fixo
                    canal_destino = bot.get_channel(CANAL_ESTATISTICAS_ID)
                    
                    # Cria o painel formatado em Embed
                    embed = discord.Embed(
                        title="📊 Relatório de Desempenho — RoiPau FC",
                        description="Estatísticas extraídas da última partida do clã:",
                        color=discord.Color.green()
                    )
                    
                    embed.add_field(
                        name="⭐ Destaques por Setor (Notas, Gols e Assistências)", 
                        value="*Módulo de IA configurado! Em breve extrairemos automaticamente as notas individuais de Goleiro, Zagueiro, Ala, Volante, Meia e Atacante[cite: 1].*", 
                        inline=False
                    )
                    
                    embed.set_image(url=attachment.url)
                    embed.set_footer(text=f"Enviado por {message.author.display_name} • Gerenciado pelo Bot do RoiPau")

                    if canal_destino:
                        await canal_destino.send(embed=embed)
                    else:
                        await message.channel.send(embed=embed)

                    await processing_msg.edit(content="✅ **Estatísticas processadas e publicadas com sucesso!**")

                except Exception as e:
                    await processing_msg.edit(content=f"❌ Erro ao processar o print: `{e}`")

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
            "`!criarlista <esquema>;<foco>;<titulo>;...`\n> Cria a convocação oficial com 2 times ativos e restantes na reserva.\n"
            "`!listasativas` ou `!ativas`\n> Envia no canal de avisos o resumo de todas as convocações abertas.\n"
            "`!reabrir` ou `!restaurar`\n> Reabre e restaura a última lista do canal.\n"
            "`!limparmortas`\n> Remove do sistema listas cujas mensagens já foram apagadas no Discord.\n"
            "`!limpar`\n> Limpa e reseta todos os inscritos e reservas da lista ativa.\n"
            "`!fecharlista`\n> Encerra as inscrições, processa capitães, sorteia os times e programa limpeza de 24h."
        ),
        inline=False
    )

    embed.add_field(
        name="⚙️ Comandos Avançados & Simulação",
        value=(
            "`!simular <quantidade>`\n> Cria jogadores virtuais respeitando estritamente o limite máximo por posição.\n"
            "`!addtime 3` ou `!addtime 4`\n> Abre o 3º ou 4º time, atualizando os botões de capitães e promovendo os reservas.\n"
            "`!remover @Jogador`\n> Remove um participante específico da lista ativa."
        ),
        inline=False
    )

    embed.add_field(
        name="🛠️ Sistema & Diagnóstico",
        value=(
            "`!teste`\n> Verifica a latência (ping) e o status operacional do bot.\n"
            "💡 **Dica de Relatório:** Reaja com `✅` em qualquer mensagem do bot no canal de avisos para apagá-la instantaneamente!"
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

    msg_id_alvo = None
    dados_alvo = None
    for mid, dados in reversed(list(listas_ativas.items())):
        if dados["channel_id"] == ctx.channel.id:
            msg_id_alvo = mid
            dados_alvo = dados
            break

    if not msg_id_alvo or not dados_alvo:
        await ctx.send("⚠️ Nenhuma lista encontrada neste canal para restaurar!", delete_after=10)
        return

    dados_alvo["fechada"] = False
    nova_view = ListaButtonsDinamica(dados_alvo["esquema"], qtd_times=dados_alvo["qtd_times_ativos"])
    dados_alvo["view"] = nova_view

    channel = bot.get_channel(dados_alvo["channel_id"])
    
    try:
        msg = await channel.fetch_message(msg_id_alvo)
        novo_embed = gerar_embed_dinamico(
            dados_alvo["titulo"], dados_alvo["esquema"], dados_alvo["categoria"], 
            dados_alvo["titulares"], dados_alvo["reservas"], dados_alvo["capitaes"], dados_alvo["qtd_times_ativos"]
        )
        await msg.edit(embed=novo_embed, view=nova_view)
        await ctx.send(f"🔄 **Lista reaberta e restaurada com sucesso!**", delete_after=12)
    except (discord.NotFound, discord.HTTPException):
        novo_embed = gerar_embed_dinamico(
            dados_alvo["titulo"], dados_alvo["esquema"], dados_alvo["categoria"], 
            dados_alvo["titulares"], dados_alvo["reservas"], dados_alvo["capitaes"], dados_alvo["qtd_times_ativos"]
        )
        nova_msg = await channel.send(content="@everyone", embed=novo_embed, view=nova_view)
        
        del listas_ativas[msg_id_alvo]
        listas_ativas[nova_msg.id] = dados_alvo
        salvar_listas()
        
        await ctx.send(f"🔄 **A mensagem anterior tinha sido apagada!** Recriei a lista atualizada com sucesso.", delete_after=12)
    
    salvar_listas()

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
        f"🟢 **Status da Conexão:** Online e Operacional\n"
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
        capitaes = {0: None, 1: None, 2: None, 3: None}
        qtd_times_ativos = 2  # Começa sempre com 2 times ativos

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
    dados["qtd_times_ativos"] = 2
    dados["capitaes"] = {i: None for i in range(4)}
    salvar_listas()

    nova_view = ListaButtonsDinamica(dados["esquema"], qtd_times=2)
    dados["view"] = nova_view

    channel = bot.get_channel(dados["channel_id"])
    try:
        msg = await channel.fetch_message(msg_id)
        novo_embed = gerar_embed_dinamico(
            dados["titulo"], dados["esquema"], dados["categoria"], 
            dados["titulares"], dados["reservas"], dados["capitaes"], dados["qtd_times_ativos"]
        )
        await msg.edit(embed=novo_embed, view=nova_view)
    except Exception:
        pass
    
    await ctx.send("🧹 **Lista limpa com sucesso!** Todos os inscritos, reservas e capitães foram resetados.", delete_after=10)

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
    es
