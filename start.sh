#!/usr/bin/env bash
# Sincroniza, abre o navegador e serve o projeto (a pasta que contém agLocalSite) em http://localhost:8000/
# Ctrl+C para parar. Outra porta: ./start.sh 8001
cd "$(dirname "$0")"
python3 serve.py "$@"
