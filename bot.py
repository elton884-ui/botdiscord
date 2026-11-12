# Versão atual do bot (mude este número sempre que fizer uma alteração importante no código)
VERSAO_ATUAL = "v1.2"
ARQUIVO_VERSAO = "ultima_versao.txt"

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}!")
    
    if CANAL_AVISO_ID:
        channel = bot.get_channel(CANAL_AVISO_ID)
        if channel:
            try:
                # Lê a última versão salva no arquivo temporário do servidor
                ultima_versao = ""
                if os.path.exists(ARQUIVO_VERSAO):
                    with open(ARQUIVO_VERSAO, "r") as f:
                        ultima_versao = f.read().strip()
                
                # Se a versão mudou, significa que o código foi atualizado!
                if ultima_versao != VERSAO_ATUAL:
                    changelog_msg = (
                        "🚀 **RoiPau FC Bot atualizado com sucesso!** (Versão " + VERSAO_ATUAL + ")\n\n"
                        "📋 **O que há de novo nesta atualização:**\n"
                        "• **Comando `!simular [qtd]`:** Cria jogadores virtuais para testar lotação e fila de reservas.\n"
                        "• **Times Progressivos (`!addtime 3` / `!addtime 4`):** Começa com 2 times e sorteia novos capitães direto dos reservas ao abrir novos times[cite: 1].\n"
                        "• **Layout Vertical:** Listas de escalação final otimizadas para leitura limpa no chat[cite: 1].\n"
                        "• **Equilíbrio Automático:** Distribuição justa de jogadores entre os times ativos[cite: 1]."
                    )
                    await channel.send(changelog_msg)
                    
                    # Salva a nova versão atualizada
                    with open(ARQUIVO_VERSAO, "w") as f:
                        f.write(VERSAO_ATUAL)
                else:
                    # Se a versão for a mesma, foi apenas um reinício simples/simples reconexão
                    await channel.send("🤖 **RoiPau FC Bot** reiniciado e operando normalmente! ⚽🔥")
                    
            except Exception as e:
                print(f"Erro ao enviar mensagem de aviso no canal: {e}")
