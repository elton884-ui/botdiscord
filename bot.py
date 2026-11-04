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
