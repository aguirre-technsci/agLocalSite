#!/usr/bin/env bash
# Rode ./sync.sh (ou dê duplo-clique, se seu Finder/Explorer estiver configurado
# para executar .sh) para atualizar o site com o conteúdo mais recente dos .md
cd "$(dirname "$0")"
python3 sync.py
echo
read -p "Pressione Enter para fechar..."
