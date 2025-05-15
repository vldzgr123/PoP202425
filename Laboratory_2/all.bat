@echo off
start cmd /k "python -m transaction_service.server"
start cmd /k "python -m report_service.server"
start cmd /k "python -m user_service.server"
start cmd /k "python -m graphql_api.server"
timeout 5
echo Все сервисы запущены