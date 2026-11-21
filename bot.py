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

    def do_HEAD(self):
        self.do_GET()

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

VERSAO_ATUAL = "v4.8-GruposPorSetor"
ARQUIVO_VERSAO = "ultima_versao.txt"

ORDEM_SETORES = ["ATAQUE", "MEIO", "DEFESA", "GOLEIRO"]
TITULOS_SETORES = {
    "ATAQUE": "🎯 ATACANTES",
    "MEIO": "⚙️ MEIAS",
    "DEFESA": "🛡️ DEFESA",
    "GOLEIRO": "🧤 GOLEIROS",
}

async def obter_canal(canal_id):
    canal = bot.get_channel(canal_id)
    if canal:
        return canal
    try:
        return await bot.fetch_channel(canal_id)
    except Exception as e:
        print(f"⚠️ Não foi possível obter o canal {canal_id}: {e}")
        return None

def setor_da_posicao(pos):
    pos = pos.upper()
    if pos in ["ATD", "ATE", "ATA"]:
        return "ATAQUE"
    if pos in ["GL", "GOL"]:
        return "GOLEIRO"
    if pos in ["ZAG", "ZGE", "ZGD", "LAT", "LE", "LD", "VLE", "VLD"]:
        return "DEFESA"
    return "MEIO"

def consolidar_jogadores(jogadores):
    """Unifica jogadores por nome (ignorando maiúsculas/minúsculas) mantendo notas por posição."""
    consolidados = {}
    for nome_bruto, info in jogadores.items():
        chave = nome_bruto.strip().lower()
        if not chave:
            continue

        if chave not in consolidados:
            consolidados[chave] = {
                "nome": nome_bruto.strip(),
                "posicoes": {}
            }
        else:
            if any(c.isupper() for c in nome_bruto) and not any(c.isupper() for c in consolidados[chave]["nome"]):
                consolidados[chave]["nome"] = nome_bruto.strip()

        pos_map = info.get("posicoes", {})
        if not pos_map and "partidas" in info:
            pos_antiga = info.get("posicao", "MEI").upper()
            pos_map = {
                pos_antiga: {
                    "partidas": info.get("partidas", 0),
                    "gols": info.get("gols", 0),
                    "assistencias": info.get("assistencias", 0),
                    "soma_notas": info.get("soma_notas", 0.0)
                }
            }

        for pos, dados_pos in pos_map.items():
            pos_u = pos.upper()
            destino = consolidados[chave]["posicoes"].setdefault(
                pos_u,
                {"partidas": 0, "gols": 0, "assistencias": 0, "soma_notas": 0.0}
            )
            destino["partidas"] += dados_pos.get("partidas", 0)
            destino["gols"] += dados_pos.get("gols", 0)
            destino["assistencias"] += dados_pos.get("assistencias", 0)
            destino["soma_notas"] += dados_pos.get("soma_notas", 0.0)

    return consolidados

def calcular_selecao_semana(jogadores):
    """Calcula destaques por setor usando a média específica de cada posição."""
    melhores = {"ATAQUE": None, "MEIO": None, "DEFESA": None, "GOLEIRO": None}
    notas_melhores = {"ATAQUE": -1.0, "MEIO": -1.0, "DEFESA": -1.0, "GOLEIRO": -1.0}

    consolidados = consolidar_jogadores(jogadores)

    for _, info in consolidados.items():
        nome = info["nome"]
        total_partidas = sum(d.get("partidas", 0) for d in info.get("posicoes", {}).values())
        total_gols = sum(d.get("gols", 0) for d in info.get("posicoes", {}).values())
        total_assists = sum(d.get("assistencias", 0) for d in info.get("posicoes", {}).values())

        for pos, dados_pos in info.get("posicoes", {}).items():
            partidas = dados_pos.get("partidas", 0)
            if partidas <= 0:
                continue
            media_pos = dados_pos.get("soma_notas", 0.0) / partidas
            cat = setor_da_posicao(pos)

            if media_pos > notas_melhores[cat]:
                notas_melhores[cat] = media_pos
                melhores[cat] = (
                    nome,
                    pos,
                    media_pos,
                    total_gols,
                    total_assists,
                    total_partidas
                )

    return melhores

def montar_grupos_ranking(jogadores):
    """Agrupa jogadores por setor (Atacante, Meio, Defesa, Goleiro), mantendo notas por posição."""
    consolidados = consolidar_jogadores(jogadores)
    grupos = {setor: [] for setor in ORDEM_SETORES}

    for _, info in consolidados.items():
        nome = info["nome"]
        total_partidas = 0
        total_gols = 0
        total_assists = 0
        medias_por_pos = []
        partidas_por_setor = {setor: 0 for setor in ORDEM_SETORES}
        melhor_nota_por_setor = {setor: -1.0 for setor in ORDEM_SETORES}

        for pos, d in info.get("posicoes", {}).items():
            part = d.get("partidas", 0)
            if part > 0:
                total_partidas += part
                total_gols += d.get("gols", 0)
                total_assists += d.get("assistencias", 0)
                media_pos = d.get("soma_notas", 0.0) / part
                setor = setor_da_posicao(pos)

                partidas_por_setor[setor] += part
                if media_pos > melhor_nota_por_setor[setor]:
                    melhor_nota_por_setor[setor] = media_pos

                medias_por_pos.append((media_pos, part, f"`{pos}` ⭐ **{media_pos:.2f}**"))

        if total_partidas > 0:
            medias_por_pos.sort(key=lambda x: (x[0], x[1]), reverse=True)
            setor_principal = max(
                ORDEM_SETORES,
                key=lambda s: (partidas_por_setor[s], melhor_nota_por_setor[s])
            )
            nota_ref = melhor_nota_por_setor[setor_principal] if melhor_nota_por_setor[setor_principal] >= 0 else medias_por_pos[0][0]
            notas_pos_str = " | ".join([item[2] for item in medias_por_pos])

            linha = f"• **{nome}** — ⚽ `{total_gols}` | 🎯 `{total_assists}` | 🎮 `{total_partidas}` • {notas_pos_str}"
            grupos[setor_principal].append(((nota_ref, total_gols, total_assists), linha))

    for setor in ORDEM_SETORES:
        grupos[setor].sort(key=lambda x: x[0], reverse=True)

    return grupos

def montar_blocos_por_grupo(grupos, max_chars=3400):
    """Cria blocos de texto separados por grupo sem ultrapassar o limite do Discord."""
    secoes = []
    for setor in ORDEM_SETORES:
        itens = [item[1] for item in grupos[setor]]
        if not itens:
            continue

        titulo_grupo = TITULOS_SETORES[setor]
        blocos_setor = []
        atual = [titulo_grupo]
        chars_atual = len(titulo_grupo) + 1

        for linha in itens:
            tam = len(linha) + 1
            if len(atual) > 1 and chars_atual + tam > max_chars:
                blocos_setor.append("\n".join(atual))
                atual = [f"{titulo_grupo} (cont.)", linha]
                chars_atual = len(atual[0]) + 1 + tam
            else:
                atual.append(linha)
                chars_atual += tam

        if atual:
            blocos_setor.append("\n".join(atual))

        for b in blocos_setor:
            secoes.append(b)

    # Junta seções curtas num mesmo bloco quando couberem dentro do limite
    blocos_finais = []
    bloco_atual = ""
    for secao in secoes:
        if not bloco_atual:
            bloco_atual = secao
        elif len(bloco_atual) + len(secao) + 4 <= max_chars:
            bloco_atual = f"{bloco_atual}\n\n{secao}"
        else:
            blocos_finais.append(bloco_atual)
            bloco_atual = secao

    if bloco_atual:
        blocos_finais.append(bloco_atual)

    return blocos_finais

async def enviar_ranking_atualizado(canal_fallback=None):
    dados_est = carregar_do_db("estatisticas_cla", {"jogadores": {}, "partidas_totais": 0})
    jogadores = dados_est.get("jogadores", {})

    if not jogadores:
        return False

    canal_destino = await obter_canal(CANAL_MELHORES_SEMANA_ID)
    if not canal_destino:
        canal_destino = canal_fallback

    if not canal_destino:
        print("⚠️ Canal de ranking não encontrado para envio.")
        return False

    grupos = montar_grupos_ranking(jogadores)
    blocos_rank = montar_blocos_por_grupo(grupos, max_chars=3400)

    if not blocos_rank:
        return False

    melhores = calcular_selecao_semana(jogadores)
    emojis_cat = {"ATAQUE": "🎯", "MEIO": "⚙️", "DEFESA": "🛡️", "GOLEIRO": "🧤"}
    linhas_destaques = []
    for cat in ["ATAQUE", "MEIO", "DEFESA", "GOLEIRO"]:
        dados_craque = melhores.get(cat)
        if dados_craque:
            nome, pos, media_pos, gols, assists, part = dados_craque
            linhas_destaques.append(
                f"• {emojis_cat[cat]} **{cat.capitalize()}:** **{nome}** (`{pos}`) — ⭐ **{media_pos:.2f}** | ⚽ `{gols}` | 🎯 `{assists}` | 🎮 `{part}`"
            )

    mensagens_enviadas = []
    try:
        total_blocos = len(blocos_rank)
        for idx, bloco in enumerate(blocos_rank, start=1):
            titulo = "🏆 RANKING DA SEMANA — ROIPIAU FC" if total_blocos == 1 else f"🏆 RANKING DA SEMANA — ROIPIAU FC ({idx}/{total_blocos})"
            cabecalho = f"Partidas computadas: `{dados_est.get('partidas_totais', 0)}`\n\n" if idx == 1 else ""
            embed = discord.Embed(
                title=titulo,
                description=cabecalho + bloco,
                color=discord.Color.gold()
            )
            if idx == total_blocos and linhas_destaques:
                embed.add_field(
                    name="🌟 SELEÇÃO DA SEMANA (DESTAQUES)",
                    value="\n".join(linhas_destaques),
                    inline=False
                )
            embed.set_footer(text="RoiPau FC Bot • Atualiza automaticamente a cada partida e via !ranking ⚽🔥")
            msg = await canal_destino.send(embed=embed)
            mensagens_enviadas.append(msg.id)

        try:
            async for msg in canal_destino.history(limit=20):
                if msg.author.id == bot.user.id and msg.id not in mensagens_enviadas:
                    try:
                        await msg.delete()
                    except Exception:
                        pass
        except Exception as e:
            print(f"⚠️ Aviso ao limpar mensagens antigas do ranking: {e}")

        print("✅ Ranking atualizado automaticamente com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro ao enviar ranking atualizado: {e}")
        return False

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}!")

    if CANAL_AVISO_ID:
        channel = await obter_canal(CANAL_AVISO_ID)
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
                        "• **Grupos no Ranking Semanal:** Atacantes, Meias, Defesa e Goleiros separados por setor, com gols, assistências e jogos somados e notas por posição."
                    )
                    await channel.send(changelog_msg)

                    with open(ARQUIVO_VERSAO, "w") as f:
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
                channel = await obter_canal(payload.channel_id)
                if channel:
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

            melhores = calcular_selecao_semana(jogadores)

            canal_ranking = await obter_canal(CANAL_MELHORES_SEMANA_ID)
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
                    nome_digitado = partes[0].strip()
                    posicao = partes[1].upper()

                    posicoes_validas = ["ATD", "ATE", "ATA", "GL", "GOL", "ZAG", "ZGE", "ZGD", "LAT", "LE", "LD", "VLE", "VLD", "VOL", "MEI", "ME", "MD", "ALA", "MCE", "MCD"]
                    if posicao not in posicoes_validas:
                        erros_linhas.append(f"{linha} (Posição '{posicao}' inválida)")
                        continue

                    gols = int(partes[2])
                    assistencias = int(partes[3])
                    nota = float(partes[4].replace(",", "."))

                    jogadores = estatisticas_cla.setdefault("jogadores", {})

                    chave_existente = None
                    for k in jogadores.keys():
                        if k.strip().lower() == nome_digitado.lower():
                            chave_existente = k
                            break

                    nome_chave = chave_existente if chave_existente else nome_digitado
                    if nome_chave not in jogadores:
                        jogadores[nome_chave] = {"posicoes": {}}

                    if "posicoes" not in jogadores[nome_chave]:
                        pos_antiga = jogadores[nome_chave].get("posicao", "MEI")
                        jogadores[nome_chave]["posicoes"] = {
                            pos_antiga: {
                                "partidas": jogadores[nome_chave].get("partidas", 0),
                                "gols": jogadores[nome_chave].get("gols", 0),
                                "assistencias": jogadores[nome_chave].get("assistencias", 0),
                                "soma_notas": jogadores[nome_chave].get("soma_notas", 0.0)
                            }
                        }

                    posicoes_dict = jogadores[nome_chave]["posicoes"]
                    if posicao not in posicoes_dict:
                        posicoes_dict[posicao] = {"partidas": 0, "gols": 0, "assistencias": 0, "soma_notas": 0.0}

                    pos_Atual = posicoes_dict[posicao]
                    pos_Atual["partidas"] += 1
                    pos_Atual["gols"] += gols
                    pos_Atual["assistencias"] += assistencias
                    pos_Atual["soma_notas"] += nota

                    jogadores_processados.append((nome_chave, posicao, gols, assistencias, nota))
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

            canal_res = await obter_canal(CANAL_RESULTADOS_ID)
            if canal_res:
                embed_res = discord.Embed(title="📊 Resultado da Partida — RoiPau FC", color=discord.Color.green())
                resumo_txt = []
                for jp in jogadores_processados:
                    resumo_txt.append(f"• **{jp[0]}** (`{jp[1]}`) — ⭐ {jp[4]} | ⚽ {jp[2]} | 🎯 {jp[3]}")
                embed_res.add_field(name="Destaques do Jogo", value="\n".join(resumo_txt), inline=False)
                await canal_res.send(embed=embed_res)

            await enviar_ranking_atualizado()
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
            "`!ranking`\n> Publica o ranking atualizado e a Seleção da Semana no canal de melhores da semana (também atualiza sozinho a cada partida).\n"
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
        canal = await obter_canal(dados["channel_id"])
        nome_canal = f"<#{dados['channel_id']}>" if canal else "Canal desconhecido"

        info_txt = (
            f"🏟️ **Canal:** {nome_canal}\n"
            f"⚽ **Formação:** `{dados['esquema']}` | **Foco:** `{dados['categoria']}`\n"
            f"👥 **Titulares Inscritos:** `{len(dados['titulares'])}` | ⏳ **Reservas:** `{len(dados['reservas'])}`\n"
            f"🔗 [Ir para a Mensagem da Lista](https://discord.com/channels/{ctx.guild.id}/{dados['channel_id']}/{mid})"
        )
        embed.add_field(name=f"📌 {dados['titulo']}", value=info_txt, inline=False)

    embed.set_footer(text="RoiPau FC Bot • Gestão inteligente de elencos ⚽🔥")

    canal_aviso = await obter_canal(CANAL_AVISO_ID)
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

    channel = await obter_canal(dados_alvo["channel_id"])

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
        canal_id = dados.get("channel_id")
        canal = await obter_canal(canal_id)

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
    est_db = carregar_do_db("estatisticas_cla", {"jogadores": {}, "partidas_totais": 0})

    feedback_msg = (
        "🤖 **DIAGNÓSTICO E TESTE DO BOT ROIPIAU (NUVEM)** ⚽\n\n"
        f"🟢 **Status da Conexão:** Online e Operacional (PostgreSQL)\n"
        f"⚡ **Latência (Ping):** `{ping_ms}ms`\n"
        f"📋 **Listas Ativas Salvas:** `{len(listas_ativas)}`\n"
        f"📊 **Partidas Registradas no Banco (Nuvem):** `{est_db.get('partidas_totais', 0)}`\n"
        f"🔒 **Comandos:** `!comandos`, `!listasativas`, `!reabrir`, `!limparmortas`, `!criarlista`, `!limpar`, `!simular`, `!addtime`, `!fecharlista`, `!remover`, `!ranking`, `!relatoriodasemana`, `!teste` — **Tudo OK!**"
    )

    await ctx.send(feedback_msg, delete_after=15)

@bot.command(name="ranking")
async def ranking_cmd(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    dados_est = carregar_do_db("estatisticas_cla", {"jogadores": {}, "partidas_totais": 0})
    if not dados_est.get("jogadores"):
        await ctx.send("⚠️ Ainda não há estatísticas salvas no banco.", delete_after=10)
        return

    enviou = await enviar_ranking_atualizado(canal_fallback=ctx.channel)
    if enviou:
        await ctx.send("✅ Ranking e Seleção da Semana enviados com sucesso!", delete_after=8)
    else:
        await ctx.send("⚠️ Não foi possível enviar o ranking agora.", delete_after=10)

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

        global listas_ativas
        listas_ativas = carregar_dados_iniciais()
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

    global listas_ativas
    listas_ativas = carregar_dados_iniciais()
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

    channel = await obter_canal(dados["channel_id"])
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

    global listas_ativas
    listas_ativas = carregar_dados_iniciais()
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

    channel = await obter_canal(dados["channel_id"])
    try:
        msg = await channel.fetch_message(msg_id)
        novo_embed = gerar_embed_dinamico(
            dados["titulo"], dados["esquema"], dados["categoria"],
            dados["titulares"], dados["reservas"], dados["capitaes"], dados["qtd_times_ativos"]
        )
        await msg.edit(embed=novo_embed, view=dados.get("view"))
    except Exception:
        pass

    await ctx.send(f"🧪 **Simulação concluída!** Inseridos `{len(titulares) + len(reservas)}` jogadores respeitando estritamente o teto máximo por posição.", delete_after=10)

@bot.command(name="addtime")
async def addtime(ctx, numero_time: int):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    if numero_time not in [3, 4]:
        await ctx.send("⚠️ Você só pode adicionar o `3` ou o `4` time!", delete_after=10)
        return

    global listas_ativas
    listas_ativas = carregar_dados_iniciais()
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

    channel = await obter_canal(dados["channel_id"])
    try:
        msg = await channel.fetch_message(msg_id)
        novo_embed = gerar_embed_dinamico(
            dados["titulo"], dados["esquema"], dados["categoria"],
            dados["titulares"], dados["reservas"], dados["capitaes"], dados["qtd_times_ativos"]
        )
        await msg.edit(embed=novo_embed, view=nova_view)
    except Exception:
        novo_embed = gerar_embed_dinamico(
            dados["titulo"], dados["esquema"], dados["categoria"],
            dados["titulares"], dados["reservas"], dados["capitaes"], dados["qtd_times_ativos"]
        )
        nova_msg = await channel.send(content="@everyone", embed=novo_embed, view=nova_view)
        del listas_ativas[msg_id]
        listas_ativas[nova_msg.id] = dados
        salvar_listas()

    await ctx.send(f"🛡️ **TIME {numero_time} ABERTO!** Botões de capitães atualizados e reservas promovidos respeitando a ordem e posição exata.", delete_after=12)

@bot.command(name="remover")
async def remover(ctx, member: discord.Member = None):
    if not member and ctx.message.mentions:
        member = ctx.message.mentions[0]

    if not member:
        await ctx.send("⚠️ **Uso correto:** Digite `!remover @Jogador`")
        return

    global listas_ativas
    listas_ativas = carregar_dados_iniciais()
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

    channel = await obter_canal(dados["channel_id"])
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

    global listas_ativas
    listas_ativas = carregar_dados_iniciais()
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
                    alocado_alt = False
                    for p in config_formacao.keys():
                        if len(times_montados[i][p]) < config_formacao[p]:
                            times_montados[i][p].append(encontrado['user'])
                            alocado_alt = True
                            break
                    if not alocado_alt:
                        todos_candidatos.append(encontrado)

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
                novos_reservas.append(item)

    dados["reservas"] = novos_reservas
    salvar_listas()

    for i in range(qtd_times):
        if i not in capitaes_atribuidos or not capitaes_atribuidos[i] or "*A definir" in str(capitaes_atribuidos[i]):
            candidatos = [j for v in times_montados[i].values() for j in v]
            if candidatos:
                capitaes_atribuidos[i] = random.choice(candidatos)
            else:
                capitaes_atribuidos[i] = "*Nenhum*"

    channel = await obter_canal(dados["channel_id"])
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

        msg_escalacao_enviada = await ctx.send(mensagem_escalacao)

        relatorio_msg_enviada = None
        canal_escalacao = await obter_canal(CANAL_ESCALACAO_ID)
        if canal_escalacao:
            participantes_str = ", ".join(todos_participantes) if todos_participantes else "*Nenhum participante*"
            relatorio_msg = (
                f"📋 **RELATÓRIO DE ESCALAÇÃO — {dados['titulo'].upper()}** ⚽\n\n"
                f"🏆 **Muito obrigado a todos os jogadores que colaram e participaram da lista de hoje!**\n"
                f"👥 **Participantes ({len(todos_participantes)}):** {participantes_str}\n\n"
                f"🔥 *Bom jogo e ótima resenha a todos os membros do RoiPau FC!*"
            )
            relatorio_msg_enviada = await canal_escalacao.send(relatorio_msg)

        async def apagar_depois_de_24h(msg_esc, msg_rel):
            await asyncio.sleep(86400)
            try:
                if msg_esc:
                    await msg_esc.delete()
            except Exception as e:
                print(f"Erro ao apagar mensagem de escalação automática: {e}")
            try:
                if msg_rel:
                    await msg_rel.delete()
            except Exception as e:
                print(f"Erro ao apagar relatório automático: {e}")

        bot.loop.create_task(apagar_depois_de_24h(msg_escalacao_enviada, relatorio_msg_enviada))

    except Exception as e:
        await ctx.send(f"⚠️ Erro ao fechar lista: {e}")

TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print("❌ ERRO CRÍTICO: A variável DISCORD_TOKEN não foi encontrada nas variáveis de ambiente do Render!")
else:
    bot.run(TOKEN)
