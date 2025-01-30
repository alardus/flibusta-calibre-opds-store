#!/bin/bash

# Удаляем старый zip-файл, если он существует
rm -f calibre-flibusta-plugin.zip

# Переходим в папку src и архивируем её содержимое
cd src && zip -r ../calibre-flibusta-plugin.zip ./*

echo "Плагин успешно упакован в calibre-flibusta-plugin.zip" 