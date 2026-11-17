import os
import re
import random
import json
import asyncio
import io
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord.ext import commands
from google import genai
from PIL import Image as PILImage

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

# --- INICIALIZAÇÃO DA GEMINI API ---
gemini_client = genai.Client()

# --- PERSISTÊNCIA DE DADOS E ESTATÍSTICAS ---
ARQUIVO_DADOS = "listas_ativas.json"
ARQUIVO_ESTATS = "estatisticas_cla.json"

def carregar_json(arquivo, padrao):
    if os.path.exists(arquivo):
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Erro ao carregar {arquivo}: {e}")
    return padrao

def salvar_json(arquivo, dados):
    try:
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"⚠️ Erro ao salvar {arquivo}: {e}")

listas_ativas = {int(k): v for k, v in carregar_json(ARQUIVO_DADOS, {}).items()}
estatisticas_cla = carregar_json(ARQUIVO_ESTATS, {"jogadores": {}, "partidas_totais": 0})

def salvar_listas():
    salvar_json(ARQUIVO_DADOS, {str(k): v for k, v in listas_ativas.items()})

def salvar_estats():
    salvar_json(ARQUIVO_ESTATS, estatisticas_cla)

CANAL_AVISO_ID = 1570420721312866436
CANAL_ESCALACAO_ID = 1570429628588499086
CANAL_PRINTS_ID = 1572265046002638878
CANAL_ESTATISTICAS_ID = 1572265122066604212

VERSAO_ATUAL = "v3.47"
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
                        "• **Correção Definitiva de Rota:** Ajustado o mapeamento de modelos no botão de reanálise para evitar erros 404 e garantir processamento liso!"
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

# --- VIEW COM BOTÃO DE RETRY BLINDADO ---
class RetryPrintView(discord.ui.View):
    def __init__(self, ctx, anexo_url):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.anexo_url = anexo_url

    @discord.ui.button(label="🔄 Tentar Análise Novamente", style=discord.ButtonStyle.primary)
    async def retry_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔄 Reiniciando a análise do print, aguarde...", ephemeral=True)
        await processar_print_ia(self.ctx, self.anexo_url, interaction.message)

async def processar_print_ia(ctx, image_url, status_msg):
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    await status_msg.edit(content="❌ Erro ao baixar a imagem do print para reanálise.")
                    return
                image_bytes = await resp.read()

        pil_image = PILImage.open(io.BytesIO(image_bytes))

        prompt = (
            "Analise este print de estatísticas de uma partida de EA Sports FC Pro Clubs. "
            "1. Identifique o Craque do Jogo (MVP) e o Segundo Melhor em Campo (com nome e nota). "
            "2. Retorne também em formato JSON puro (dentro de um bloco de código json) uma lista com todos os jogadores visíveis contendo: "
            "nome, nota, gols, assistencias para que possamos atualizar o banco de dados do clã."
        )

        # Utilizando apenas o modelo oficial ativo `gemini-3.8-flash`
        sucesso = False
        response = None
        ultimo_erro = ""

        for tentativa in range(1, 4):
            try:
                response = gemini_client.models.generate_content(
                    model='gemini-3.8-flash',
                    contents=[prompt, pil_image]
                )
                if response and response.text:
                    sucesso = True
                    break
            except Exception as e:
                ultimo_erro = str(e)
                if "429" in ultimo_erro or "503" in ultimo_erro or "exhausted" in ultimo_erro.lower() or "unavailable" in ultimo_erro.lower():
                    await asyncio.sleep(3 * tentativa)
                    continue
                else:
                    break

        if not sucesso:
            view_retry = RetryPrintView(ctx, image_url)
            await status_msg.edit(
                content=f"❌ O Google está com muita demanda no momento. Clique no botão abaixo para tentar de novo! (Erro: `{ultimo_erro}`)",
                view=view_retry
            )
            return

        texto_resposta = response.text if response and response.text else "Não foi possível extrair os dados da imagem."

        try:
            match_json = re.search(r'```json\s*([\s\S]*?)\s*```', texto_resposta)
            if match_json:
                dados_partida = json.loads(match_json.group(1))
                estatisticas_cla["partidas_totais"] += 1
                
                for p in dados_partida:
                    nome = p.get("nome", "Desconhecido").strip()
                    nota = float(p.get("nota", 0.0))
                    gols = int(p.get("gols", 0))
                    asts = int(p.get("assistencias", 0))
                    
                    if nome not in estatisticas_cla["jogadores"]:
                        estatisticas_cla["jogadores"][nome] = {"partidas": 0, "gols": 0, "assistencias": 0, "soma_notas": 0.0, "mvps": 0}
                    
                    j = estatisticas_cla["jogadores"][nome]
                    j["partidas"] += 1
                    j["gols"] += gols
                    j["assistencias"] += asts
                    j["soma_notas"] += nota
                
                salvar_estats()
        except Exception as e:
            print(f"⚠️ Erro ao processar banco de dados estatístico: {e}")

        canal_estatisticas = bot.get_channel(CANAL_ESTATISTICAS_ID)

        embed = discord.Embed(
            title="📊 Destaques da Partida — RoiPau FC",
            description="Estatísticas processadas e banco de dados atualizado com sucesso:",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="⭐ Craque e 2º Melhor", 
            value=f"{texto_resposta[:1000]}", 
            inline=False
        )
        
        embed.set_image(url=image_url)
        embed.set_footer(text=f"Enviado por {ctx.author.display_name} • Banco de Dados RoiPau FC")

        if canal_estatisticas:
            await canal_estatisticas.send(embed=embed)
        else:
            await ctx.send(embed=embed)

        await status_msg.edit(content="✅ **Análise concluída, banco de dados atualizado e relatório publicado!**", view=None)
        
        await asyncio.sleep(8)
        try:
            await status_msg.delete()
        except Exception:
            pass

    except Exception as e:
        await status_msg.edit(content=f"❌ Erro crítico ao processar o print: `{e}`")

@bot.command(name="print")
async def cmd_print(ctx):
    if ctx.channel.id != CANAL_PRINTS_ID:
        await ctx.send("⚠️ Este comando deve ser usado apenas no canal de envios de prints!", delete_after=10)
        return

    anexo = None
    if ctx.message.attachments:
        for att in ctx.message.attachments:
            if att.content_type and "image" in att.content_type:
                anexo = att
                break
    elif ctx.message.reference:
        try:
            msg_ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if msg_ref.attachments:
                for att in msg_ref.attachments:
                    if att.content_type and "image" in att.content_type:
                        anexo = att
                        break
        except Exception:
            pass

    if not anexo:
        await ctx.send("⚠️ **Faltou a imagem, Lobinho!** Envie o print junto com o comando `!print` ou marque a mensagem da foto respondendo com o comando.", delete_after=12)
        return

    processing_msg = await ctx.send("🔄 **Print capturado, Lobinho!** A Inteligência Artificial da Gemini está analisando as estatísticas da partida e atualizando o banco de dados...")
    await processar_print_ia(ctx, anexo.url, processing_msg)

# --- COMANDO DE TESTE (COM PING E LATÊNCIA) ---
@bot.command(name="teste")
async def teste(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass
    
    ping_ms = round(bot.latency * 1000)
    
    embed = discord.Embed(
        title="🏓 TESTE DE SISTEMA — ROIPIAU FC",
        description=(
            f"🤖 **Status do Bot:** `Operacional e Conectado`\n"
            f"⚡ **Latência (Ping):** `{ping_ms}ms`\n"
            f"🌐 **Servidor Web (Render):** `Online`\n"
            f"🧠 **IA & Banco de Dados:** `Prontos para uso`"
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="RoiPau FC Bot • Diagnóstico de rede ⚽🔥")
    
    await ctx.send(embed=embed, delete_after=15)

# --- COMANDOS DE GESTÃO DE LISTAS, SIMULAÇÃO E TIMES ---
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
    
    qtd_times_atuais = dados["qtd_times_ativos"]
    vagas_titulares_atuais = sum(config_formacao.values()) * qtd_times_atuais
    
    limites_absolutos = {pos: qtd * 4 for pos, qtd in config_formacao.items()}
    contagem_atual = {pos: 0 for pos in config_formacao.keys()}

    titulares = []
    reservas = []

    for i in range(1, quantidade + 1):
        nome_simulado = f"🤖 Jogador {i}"
        
        pos_escolhida = None
        for pos, limite in limites_absolutos.items():
            if contagem_atual[pos] < limite:
                pos_escolhida = pos
                break
                
        if not pos_escolhida:
            break
            
        contagem_atual[pos_escolhida] += 1
        
        if len(titulares) < vagas_titulares_atuais and sum(1 for item in titulares if item['pos'] == pos_escolhida) < config_formacao[pos_escolhida] * qtd_times_atuais:
            titulares.append({"user": nome_simulado, "pos": pos_escolhida})
        else:
            reservas.append({"user": nome_simulado, "pos": pos_escolhida})

    dados["titulares"] = titulares
    dados["reservas"] = reservas
    salvar_listas()

    channel = bot.get_channel(dados["channel_id"])
    try:
        msg = await channel.fetch_message(msg_id)
        novo_embed = gerar_embed_dinamico(
            dados["titulo"], dados["esquema"], dados["categoria"], 
            dados["titulares"], dados["reservas"], dados["capitaes"], dados["qtd_times_ativos"]
        )
        await msg.edit(embed=novo_embed, view=dados.get("view"))
    except Exception:
        pass

    await ctx.send(f"🧪 **Simulação concluída!** Inseridos `{len(titulares) + len(reservas)}` jogadores.", delete_after=10)

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

    dados["qtd_times_ativos"] = numero_time
    esquema = dados["esquema"]
    config_formacao = FORMAGOES.get(esquema, FORMAGOES["352"])
    
    novos_reservas = []
    for res in dados["reservas"]:
        pos_key = res['pos']
        qtd_por_time = config_formacao.get(pos_key, 1)
        limite_titulares_pos = qtd_por_time * dados["qtd_times_ativos"]
        ocupantes_pos_atual = sum(1 for item in dados["titulares"] if item['pos'] == pos_key)
        
        if ocupantes_pos_atual < limite_titulares_pos:
            dados["titulares"].append(res)
        else:
            novos_reservas.append(res)
            
    dados["reservas"] = novos_reservas
    nova_view = ListaButtonsDinamica(dados["esquema"], qtd_times=dados["qtd_times_ativos"])
    dados["view"] = nova_view
    salvar_listas()

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

    await ctx.send(f"🛡️ **TIME {numero_time} ABERTO!**", delete_after=12)

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
    salvar_listas()

    channel = bot.get_channel(dados["channel_id"])
    try:
        msg = await channel.fetch_message(msg_id)
        novo_embed = gerar_embed_dinamico(dados["titulo"], dados["esquema"], dados["categoria"], dados["titulares"], dados["reservas"], dados["capitaes"], dados["qtd_times_ativos"])
        await msg.edit(embed=novo_embed, view=dados.get("view"))
    except Exception:
        pass

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

    todos_candidatos = list(dados["titulares"]) + list(dados["reservas"])
    todos_participantes = [item['user'] for item in todos_candidatos]

    for i in range(qtd_times):
        cap_str = capitaes_atribuidos.get(i)
        if cap_str and "*A definir" not in str(cap_str) and "*Nenhum" not in str(cap_str):
            cap_id = extrair_id(cap_str)
            encontrado = None
            for item in todos_candidatos:
                if extrair_id(item['user']) == cap_id:
                    encontrado = item
                    break
            if encontrado:
                todos_candidatos.remove(encontrado)
                pos = encontrado['pos']
                if len(times_montados[i][pos]) < config_formacao[pos]:
                    times_montados[i][pos].append(encontrado['user'])
                else:
                    for p in config_formacao.keys():
                        if len(times_montados[i][p]) < config_formacao[p]:
                            times_montados[i][p].append(encontrado['user'])
                            break

    random.shuffle(todos_candidatos)
    novos_reservas = []

    for item in todos_candidatos:
        pos = item['pos']
        times_com_vaga_pos = [i for i in range(qtd_times) if len(times_montados[i][pos]) < config_formacao[pos]]
        
        if times_com_vaga_pos:
            times_com_vaga_pos.sort(key=lambda t: sum(len(lst) for lst in times_montados[t].values()))
            t_escolhido = times_com_vaga_pos[0]
            times_montados[t_escolhido][pos].append(item['user'])
        else:
            novos_reservas.append(item)

    dados["reservas"] = novos_reservas
    salvar_listas()

    channel = bot.get_channel(dados["channel_id"])
    try:
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.edit(view=None)
        except Exception:
            pass

        mensagem_escalacao = f"🔒 **ESCALAÇÃO FINALIZADA ({qtd_times} TIMES DE 11 JOGADORES)!**\n\n"

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
            mensagem_escalacao += f"👥 **Elenco (11/11):**\n{elenco_str}\n"
            mensagem_escalacao += f"🔊 **Call:** Entrar na call do **{nome_time}**\n"
            mensagem_escalacao += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"

        if dados["reservas"]:
            res_str = ", ".join([f"{item['user']} ({item['pos']})" for item in dados["reservas"]])
            mensagem_escalacao += f"⏳ **Suplentes / Reservas:** {res_str}\n"

        await ctx.send(mensagem_escalacao)
    except Exception as e:
        await ctx.send(f"⚠️ Erro ao fechar lista: {e}")

# --- COMANDOS DE RANKING E RELATÓRIO ---
@bot.command(name="ranking")
async def ranking(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    jogadores = estatisticas_cla.get("jogadores", {})
    if not jogadores:
        await ctx.send("⚠️ O banco de dados ainda não possui registros de partidas. Envie prints com `!print`!", delete_after=10)
        return

    top_gols = sorted(jogadores.items(), key=lambda x: x[1]['gols'], reverse=True)[:5]
    top_asts = sorted(jogadores.items(), key=lambda x: x[1]['assistencias'], reverse=True)[:5]
    
    embed = discord.Embed(
        title="🏆 RANKING OFICIAL — ROIPIAU FC",
        description=f"Partidas Registradas no Banco de Dados: `{estatisticas_cla['partidas_totais']}`\n\u200b",
        color=discord.Color.gold()
    )

    gols_txt = "\n".join([f"`{idx+1}.` **{nome}** — ⚽ `{dados['gols']}` gols (`{dados['partidas']}` jogos)" for idx, (nome, dados) in enumerate(top_gols)])
    asts_txt = "\n".join([f"`{idx+1}.` **{nome}** — 🎯 `{dados['assistencias']}` assistências" for idx, (nome, dados) in enumerate(top_asts)])

    embed.add_field(name="⚽ Top Artilheiros", value=gols_txt or "*Nenhum dado*", inline=False)
    embed.add_field(name="🎯 Top Assistências", value=asts_txt or "*Nenhum dado*", inline=False)
    embed.set_footer(text="RoiPau FC Bot • Estatísticas gerais da temporada ⚽🔥")

    await ctx.send(embed=embed)

@bot.command(name="relatoriosemanal")
async def relatorio_semanal(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    jogadores = estatisticas_cla.get("jogadores", {})
    if not jogadores:
        await ctx.send("⚠️ Não há dados suficientes no banco de dados para gerar o relatório semanal!", delete_after=10)
        return

    artilheiro = max(jogadores.items(), key=lambda x: x[1]['gols'])
    garcom = max(jogadores.items(), key=lambda x: x[1]['assistencias'])
    
    melhor_media = max(
        jogadores.items(), 
        key=lambda x: (x[1]['soma_notas'] / x[1]['partidas']) if x[1]['partidas'] > 0 else 0
    )
    media_nota_val = (melhor_media[1]['soma_notas'] / melhor_media[1]['partidas']) if melhor_media[1]['partidas'] > 0 else 0

    embed = discord.Embed(
        title="📰 BALANÇO & RELATÓRIO SEMANAL — ROIPIAU FC",
        description=f"Resumo oficial do desempenho do clã com base em `{estatisticas_cla['partidas_totais']}` partidas cadastradas.\n\u200b",
        color=discord.Color.blue()
    )

    embed.add_field(name="⚽ Artilheiro da Semana", value=f"👑 **{artilheiro[0]}** com **{artilheiro[1]['gols']}** gols.", inline=False)
    embed.add_field(name="🎯 Rei das Assistências", value=f"🎯 **{garcom[0]}** com **{garcom[1]['assistencias']}** passes para gol.", inline=False)
    embed.add_field(name="⭐ Maior Média de Notas", value=f"⭐ **{melhor_media[0]}** com média de **{media_nota_val:.2f}** por partida!", inline=False)

    embed.set_footer(text="RoiPau FC Bot • Relatório gerado automaticamente ⚽🔥")

    canal_estatisticas = bot.get_channel(CANAL_ESTATISTICAS_ID)
    if canal_estatisticas:
        await canal_estatisticas.send(embed=embed)
    else:
        await ctx.send(embed=embed)

@bot.command(name="resetartemporada")
async def resetar_temporada(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    global estatisticas_cla
    estatisticas_cla = {"jogadores": {}, "partidas_totais": 0}
    salvar_estats()
    await ctx.send("🔄 **Banco de dados resetado com sucesso!** Uma nova temporada do RoiPau FC foi iniciada.", delete_after=12)

# --- PAINEL DE COMANDOS COMPLETO ---
@bot.command(name="comandos")
async def comandos(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = discord.Embed(
        title="⚽ PAINEL DE COMANDOS — ROIPIAU FC",
        description="Lista completa de comandos oficiais do bot:\n\u200b",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="📋 Gestão de Listas & Elencos",
        value=(
            "`!criarlista <esquema>;<foco>;<titulo>;...`\n> Cria a convocação oficial.\n"
            "`!listasativas` ou `!ativas`\n> Mostra convocações abertas.\n"
            "`!simular <qtd>`\n> Simula inscrições de jogadores.\n"
            "`!addtime <3 ou 4>`\n> Abre o 3º ou 4º time na lista.\n"
            "`!remover @Jogador`\n> Remove um participante da lista.\n"
            "`!fecharlista`\n> Sorteia e encerra a convocação."
        ),
        inline=False
    )

    embed.add_field(
        name="📊 Estatísticas, Prints & Relatórios",
        value=(
            "`!print` (com imagem)\n> Envia print para análise de MVP e banco de dados.\n"
            "`!ranking`\n> Mostra o top artilheiros e assistências.\n"
            "`!relatoriosemanal`\n> Gera o balanço completo do clã.\n"
            "`!resetartemporada`\n> Zera as estatísticas para nova temporada.\n"
            "`!teste`\n> Mede o ping, latência e testa o sistema."
        ),
        inline=False
    )

    embed.set_footer(text="RoiPau FC Bot • Gestão inteligente de elencos ⚽🔥")
    await ctx.send(embed=embed)

TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print("❌ ERRO CRÍTICO: A variável DISCORD_TOKEN não foi encontrada nas variáveis de ambiente do Render!")
else:
    bot.run(TOKEN)
