#!/bin/sh
# Выгрузка файла на хостинг по plain FTP (passive). Доступы из env:
# FTP_HOST, FTP_USER, FTP_PASS, FTP_REMOTE_DIR. Пароль не логируется.
set -eu

file="$1"
remote_name="$2"

curl -sS --ftp-pasv --ftp-create-dirs \
  -T "$file" \
  "ftp://$FTP_HOST:$FTP_PORT$FTP_REMOTE_DIR$remote_name" \
  -u "$FTP_USER:$FTP_PASS"