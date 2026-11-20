import os
import re
import random
import json
import asyncio
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord.ext import commands
import psycopg2
from urllib.parse import urlparse

# --- SERVIDOR WEB PARA O RENDER (MANTÉM O APP VIVO) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Roipau esta rodando com Banco na Nuvem!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"🌐 Servidor web rodando na porta {port}")
    server.serve_forever()

Thread(target=run_web_server, daemon=False).start()

# --- CONFIGURAÇÃO DO BANCO DE DADOS POSTGRESQL (NUVEM) ---
DATABASE_URL = os.environ.get("DATABASE_URL")

def conectar_db():
    if not DATABASE_URL:
        return None
    try:
        url = urlparse(DATABASE_URL)
        return psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port,
            connect_timeout=5
        )
    except Exception as e:
        print(f"⚠️ Erro ao conectar no PostgreSQL: {e}")
        return None

def inicializar_tabelas():
    conn = conectar_db()
    if not conn:
        print("⚠️ Aviso: DATABASE_URL não configurada ou sem conexão!")
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dados_bot (
                chave VARCHAR(50) PRIMARY KEY,
                conteudo TEXT
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Tabelas do banco de dados na nuvem inicializadas com sucesso!")
    except Exception as e:
        print(f"⚠️ Erro ao inicializar tabelas no banco: {e}")

inicializar_tabelas()

def carregar_do_db(chave, padrao):
    conn = conectar_db()
    if not conn:
        return padrao
    try:
        cur = conn.cursor()
        cur.execute("SELECT conteudo FROM dados_bot WHERE chave = %s;", (chave,))
        res = cur.fetchone()
        cur.close()
        conn.close()
        if res:
            return json.loads(res[0])
    except Exception as e:
        print(f"⚠️ Erro ao carregar {chave} do banco: {e}")
    return padrao

def salvar_no_db(chave, dados):
    conn = conectar_db()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO dados_bot (chave, conteudo) VALUES (%s, %s)
            ON CONFLICT (chave) DO UPDATE SET conteudo = EXCLUDED.conteudo;
        """, (chave, json.dumps(dados, ensure_ascii=False)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Erro ao salvar {chave} no banco: {e}")

def carregar_dados_iniciais():
    try:
        raw_listas = carregar_do_db("listas_ativas", {})
        return {int(k) if str(k).isdigit() else k: v for k, v in raw_listas.items()}
    except Exception:
        return {}

listas_ativas = carregar_dados_iniciais()
estatisticas_cla = carregar_do_db("estatisticas_cla", {"jogadores": {}, "partidas_totais": 0})

def salvar_listas():
    salvar_no_db("listas_ativas", {str(k): v for k, v in listas_ativas.items()})

def salvar_estats():
    salvar_no_db("estatisticas_cla", estatisticas_cla)

# --- CONFIGURAÇÃO DO BOT DISCORD ---
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- IDs DOS CANAIS OFICIAIS ---
CANAL_AVISO_ID = 1570420721312866436
CANAL_ESCALACAO_ID = 1570429628588499086
CANAL_DADOS_FECHADO_ID = 1572265046002638878
CANAL_RESULTADOS_ID = 1572265122066604212
CANAL_MELHORES_SEMANA_ID = 1572363417606430861

VERSAO_ATUAL = "v4.4-RankingFetchFix"
ARQUIVO_VERSAO = "ultima_versao.txt"

# --- FUNÇÃO DE ATUALIZAÇÃO AUTOMÁTICA DO RANKING ---
async def atualizar_canal_ranking():
    global estatisticas_cla
    estatisticas_cla = carregar_do_db("estatisticas_cla", {"jogadores": {}, "partidas_totais": 0})

    try:
        canal_ranking = bot.get_channel(CANAL_MELHORES_SEMANA_ID)
        if not canal_ranking:
            canal_ranking = await bot.fetch_channel(CANAL_MELHORES_SEMANA_ID)

        if not canal_ranking:
            print("⚠️ Canal de melhores da semana não encontrado!")
            return False

        jogadores = estatisticas_cla.get("jogadores", {})
        if not jogadores:
            print("⚠️ Sem jogadores no banco para montar o ranking.")
            return False

        ranking_expandido = []
        for nome, info in jogadores.items():
            posicoes_dict = info.get("posicoes", {})
            for pos, dados_pos in posicoes_dict.items():
                partidas = dados_pos.get("partidas", 0)
                if partidas > 0:
                    media = dados_pos.get("soma_notas", 0.0) / partidas
                    ranking_expandido.append((nome, pos, media, dados_pos))

        melhores_semana = {"ATAQUE": None, "MEIO": None, "DEFESA": None, "GOLEIRO": None}
        notas_melhores_semana = {"ATAQUE": -1, "MEIO": -1, "DEFESA": -1, "GOLEIRO": -1}
        posicoes_dict_ranking = {"ATAQUE": [], "MEIO": [], "DEFESA": [], "GOLEIRO": []}

        for nome, pos, media, dados_pos in ranking_expandido:
            linha_txt = (
                f"• **{nome}** (`{pos}`) — ⭐ **{media:.2f}** | "
                f"⚽ `{dados_pos.get('gols', 0)}` | 🎯 `{dados_pos.get('assistencias', 0)}` | "
                f"🎮 `{dados_pos.get('partidas', 0)}`"
            )

            if pos in ["ATD", "ATE", "ATA"]:
                cat = "ATAQUE"
            elif pos in ["GL", "GOL"]:
                cat = "GOLEIRO"
            elif pos in ["ZAG", "ZGE", "ZGD", "LAT", "LE", "LD", "VLE", "VLD"]:
                cat = "DEFESA"
            else:
                cat = "MEIO"

            posicoes_dict_ranking[cat].append((media, linha_txt))

            if media > notas_melhores_semana[cat]:
                notas_melhores_semana[cat] = media
                melhores_semana[cat] = (nome, pos, media)

        for cat in posicoes_dict_ranking:
            posicoes_dict_ranking[cat].sort(key=lambda x: x[0], reverse=True)
            posicoes_dict_ranking[cat] = [item[1] for item in posicoes_dict_ranking[cat]]

        embed_rank = discord.Embed(
            title="🏆 RANKING E SELEÇÃO DA SEMANA — ROIPIAU FC",
            description=(
                f"Partidas computadas no total: `{estatisticas_cla.get('partidas_totais', 0)}`\n\n"
                "📖 **LEGENDA DE ESTATÍSTICAS:**\n"
                "> ⭐ **Média:** Média de notas obtidas nas partidas\n"
                "> ⚽ **Gols:** Total de gols marcados\n"
                "> 🎯 **Assistências:** Total de passes para gol\n"
                "> 🎮 **Partidas:** Total de jogos disputados na posição\n"
                "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
            ),
            color=discord.Color.gold()
        )

        selecao_txt = []
        emojis_sel = {"ATAQUE": "🎯 Ataque", "MEIO": "⚙️ Meio", "DEFESA": "🛡️ Defesa", "GOLEIRO": "🧤 Goleiro"}
        for cat, dados_craque in melhores_semana.items():
            if dados_craque:
                nome_c, pos_c, med_c = dados_craque
                selecao_txt.append(f"• **{emojis_sel[cat]}:** {nome_c} (`{pos_c}`) — ⭐ **{med_c:.2f}**")

        if selecao_txt:
            embed_rank.add_field(name="🌟 SELEÇÃO DA SEMANA (DESTAQUES)", value="\n".join(selecao_txt), inline=False)
            embed_rank.add_field(name="\u200b", value="▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", inline=False)

        for cat, lista_jog in posicoes_dict_ranking.items():
            if lista_jog:
                embed_rank.add_field(name=f"📋 Categoria: {cat}", value="\n".join(lista_jog), inline=False)

        embed_rank.set_footer(text="RoiPau FC Bot • O ranking atualiza automaticamente a cada partida! ⚽🔥")

        nova_msg = await canal_ranking.send(embed=embed_rank)

        try:
            async for msg in canal_ranking.history(limit=15):
                if msg.author.id == bot.user.id and msg.id != nova_msg.id:
                    try:
                        await msg.delete()
                    except Exception:
                        pass
        except Exception as e:
            print(f"⚠️ Aviso ao limpar histórico antigo do ranking: {e}")

        print("✅ Ranking de melhores da semana atualizado com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro crítico ao atualizar canal de ranking: {e}")
        return False

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}!")

    await atualizar_canal_ranking()

    if CANAL_AVISO_ID:
        channel = bot.get_channel(CANAL_AVISO_ID)
        if not channel:
            try:
                channel = await bot.fetch_channel(CANAL_AVISO_ID)
            except Exception:
                channel = None
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
                        "• **Ranking Resiliente:** Busca direta do canal de melhores da semana e log detalhado após reinicializações."
                    )
                    await channel.send(changelog_msg)

                    with open(ARQUIVO_VERSAO, "w", encoding="utf-8") as f:
                        f.write(VERSAO_ATUAL)
                else:
                    await channel.send("🤖 **RoiPau FC Bot** reiniciado e operando perfeitamente! ⚽🔥")

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
                if not channel:
                    channel = await bot.fetch_channel(payload.channel_id)
                message = await channel.fetch_message(payload.message_id)
                if message.author.id == bot.user.id:
                    await message.delete()
            except Exception as e:
                print(f"Erro ao tentar apagar mensagem via reação: {e}")

# --- LISTENER AUTOMÁTICO DO CANAL FECHADO DE DADOS ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == CANAL_DADOS_FECHADO_ID:
        conteudo = message.content.strip()

        if conteudo.lower() == "!relatoriodasemana":
            global estatisticas_cla
            estatisticas_cla = carregar_do_db("estatisticas_cla", {"jogadores": {}, "partidas_totais": 0})
            jogadores = estatisticas_cla.get("jogadores", {})
            if not jogadores:
                await message.channel.send("⚠️ Não há dados estatísticos registrados para gerar o relatório!", delete_after=10)
                return

            melhores = {"ATAQUE": None, "MEIO": None, "DEFESA": None, "GOLEIRO": None}
            notas_melhores = {"ATAQUE": -1, "MEIO": -1, "DEFESA": -1, "GOLEIRO": -1}

            for nome, info in jogadores.items():
                posicoes_jogador = info.get("posicoes", {})
                for pos, dados_pos in posicoes_jogador.items():
                    media = dados_pos["soma_notas"] / dados_pos["partidas"] if dados_pos["partidas"] > 0 else 0

                    if pos in ["ATD", "ATE", "ATA"]:
                        cat = "ATAQUE"
                    elif pos in ["GL", "GOL"]:
                        cat = "GOLEIRO"
                    elif pos in ["ZAG", "ZGE", "ZGD", "LAT", "LE", "LD", "VLE", "VLD"]:
                        cat = "DEFESA"
                    else:
                        cat = "MEIO"

                    if media > notas_melhores[cat]:
                        notas_melhores[cat] = media
                        melhores[cat] = (nome, pos, media, dados_pos['gols'], dados_pos['assistencias'], dados_pos['partidas'])

            canal_ranking = bot.get_channel(CANAL_MELHORES_SEMANA_ID)
            if not canal_ranking:
                try:
                    canal_ranking = await bot.fetch_channel(CANAL_MELHORES_SEMANA_ID)
                except Exception:
                    canal_ranking = None

            if canal_ranking:
                embed_rel = discord.Embed(
                    title="🎉 PREMIAÇÃO — SELEÇÃO DA SEMANA ROIPIAU FC 🏆",
                    description="Parabéns aos craques que dominaram as partidas e foram elogiados em suas posições! 🌟\n\u200b",
                    color=discord.Color.brand_green()
                )

                emojis_cat = {"ATAQUE": "🎯", "MEIO": "⚙️", "DEFESA": "🛡️", "GOLEIRO": "🧤"}
                for cat, dados_craque in melhores.items():
                    if dados_craque:
                        nome, pos, media, gols, assists, part = dados_craque
                        txt_craque = (
                            f"👑 **{nome}** (`{pos}`)\n"
                            f"⭐ Média: **{media:.2f}** | ⚽ Gols: `{gols}` | 🎯 Assists: `{assists}` | 🎮 Jogos: `{part}`"
                        )
                        embed_rel.add_field(name=f"{emojis_cat[cat]} Craque do {cat}", value=txt_craque, inline=False)

                embed_rel.set_footer(text="RoiPau FC • O ciclo semanal foi encerrado e zerado para a próxima temporada! ⚽🔥")
                await canal_ranking.send(embed=embed_rel)

            estatisticas_cla["jogadores"] = {}
            estatisticas_cla["partidas_totais"] = 0
            salvar_estats()

            await message.add_reaction("✅")
            await message.channel.send("🏆 **Relatório final gerado com sucesso!** O banco de dados estatístico foi zerado e está pronto para um novo ciclo.", delete_after=15)
            return

        linhas = conteudo.split("\n")
        jogadores_processados = []
        erros_linhas = []

        estatisticas_cla = carregar_do_db("estatisticas_cla", {"jogadores": {}, "partidas_totais": 0})

        for linha in linhas:
            if not linha.strip():
                continue
            partes = [p.strip() for p in linha.split("|")]
            if len(partes) >= 5:
                try:
                    nome = partes[0]
                    posicao = partes[1].upper()

                    posicoes_validas = [
                        "ATD", "ATE", "ATA", "GL", "GOL",
                        "ZAG", "ZGE", "ZGD", "LAT", "LE", "LD", "VLE", "VLD",
                        "VOL", "MEI", "ME", "MD", "ALA", "MCE", "MCD"
                    ]
                    if posicao not in posicoes_validas:
                        erros_linhas.append(f"{linha} (Posição '{posicao}' inválida)")
                        continue

                    gols = int(partes[2])
                    assistencias = int(partes[3])
                    nota = float(partes[4].replace(",", "."))

                    jogadores = estatisticas_cla.setdefault("jogadores", {})
                    if nome not in jogadores:
                        jogadores[nome] = {"posicoes": {}}

                    if "posicoes" not in jogadores[nome]:
                        pos_antiga = jogadores[nome].get("posicao", "MEI")
                        jogadores[nome]["posicoes"] = {
                            pos_antiga: {
                                "partidas": jogadores[nome].get("partidas", 0),
                                "gols": 0,
                                "assistencias": 0,
                                "soma_notas": 0.0
                            }
                        }

                    posicoes_dict = jogadores[nome]["posicoes"]
                    if posicao not in posicoes_dict:
                        posicoes_dict[posicao] = {"partidas": 0, "gols": 0, "assistencias": 0, "soma_notas": 0.0}

                    pos_atual = posicoes_dict[posicao]
                    pos_atual["partidas"] += 1
                    pos_atual["gols"] += gols
                    pos_atual["assistencias"] += assistencias
                    pos_atual["soma_notas"] += nota

                    jogadores_processados.append((nome, posicao, gols, assistencias, nota))
                except Exception:
                    erros_linhas.append(linha)
            else:
                if not linha.startswith("!"):
                    erros_linhas.append(linha)

        if erros_linhas:
            erro_txt = "\n".join([f"• `{l}`" for l in erros_linhas])
            await message.channel.send(
                f"❌ **Erro de formação ou posição detectado!** Verifique as linhas abaixo:\n{erro_txt}\n\n"
                "⚠️ *Nenhuma partida foi computada para proteger o ranking.* Corrija e envie novamente!",
                delete_after=20
            )
            return

        if jogadores_processados:
            estatisticas_cla["partidas_totais"] += 1
            salvar_estats()

            canal_res = bot.get_channel(CANAL_RESULTADOS_ID)
            if not canal_res:
                try:
                    canal_res = await bot.fetch_channel(CANAL_RESULTADOS_ID)
                except Exception:
                    canal_res = None

            if canal_res:
                embed_res = discord.Embed(title="📊 Resultado da Partida — RoiPau FC", color=discord.Color.green())
                resumo_txt = []
                for jp in jogadores_processados:
                    resumo_txt.append(f"• **{jp[0]}** (`{jp[1]}`) — ⭐ {jp[4]} | ⚽ {jp[2]} | 🎯 {jp[3]}")
                embed_res.add_field(name="Destaques do Jogo", value="\n".join(resumo_txt), inline=False)
                await canal_res.send(embed=embed_res)

            await atualizar_canal_ranking()
            await message.add_reaction("✅")
            return
        else:
            await message.channel.send("⚠️ Nenhuma linha válida encontrada no formato `Nome | Posição | Gols | Assistências | Nota`!", delete_after=10)

    await bot.process_commands(message)

# --- FORMAÇÕES E CONFIGURAÇÕES DE LISTAS ---
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
        global listas_ativas
        listas_ativas = carregar_dados_iniciais()
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
        name="📊 Estatísticas & Relatório Semanal",
        value=(
            "`!relatoriodasemana` (No canal fechado de dados)\n> Gera o relatório final premiando os melhores de cada posição, publica no canal de melhores da semana e **zera o banco** para um novo ciclo!"
        ),
        inline=False
    )

    embed.add_field(
        name="⚙️ Comandos Avançados & Simulação",
        value=(
            "`!simular <quantidade>`\n> Cria jogadores virtuais respeitando estritamente o teto máximo por posição.\n"
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

    global listas_ativas
    listas_ativas = carregar_dados_iniciais()
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

    global listas_ativas
    listas_ativas = carregar_dados_iniciais()
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
        await ctx.send("🔄 **Lista reaberta e restaurada com sucesso!**", delete_after=12)
    except (discord.NotFound, discord.HTTPException):
        novo_embed = gerar_embed_dinamico(
            dados_alvo["titulo"], dados_alvo["esquema"], dados_alvo["categoria"],
            dados_alvo["titulares"], dados_alvo["reservas"], dados_alvo["capitaes"], dados_alvo["qtd_times_ativos"]
        )
        nova_msg = await channel.send(content="@everyone", embed=novo_embed, view=nova_view)

        del listas_ativas[msg_id_alvo]
        listas_ativas[nova_msg.id] = dados_alvo
        salvar_listas()

        await ctx.send("🔄 **A mensagem anterior tinha sido apagada!** Recriei a lista atualizada com sucesso.", delete_after=12)

    salvar_listas()

@bot.command(name="limparmortas")
async def limpar_mortas(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    global listas_ativas
    listas_ativas = carregar_dados_iniciais()
    removidas = 0
    ids_para_remover = []

    for mid, dados in list(listas_ativas.items()):
        canal
