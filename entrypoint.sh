#!/bin/sh
# Inicia Gunicorn en segundo plano
cd /app
gunicorn --bind 0.0.0.0:5001 backend:app --daemon
# Inicia NGINX en primer plano
nginx -g "daemon off;"