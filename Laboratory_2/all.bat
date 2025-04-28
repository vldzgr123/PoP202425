python -m user_service.server
python -m transaction_service.server
python -m report_service.server

# Регистрация пользователя
python -m client.cli register --username testuser --email test@example.com --password pass123

# Вход
python -m client.cli login --email test@example.com --password pass123

# Добавление транзакций
python -m client.cli add-transaction --amount 1000 --category salary --type income --description "Monthly salary"
python -m client.cli add-transaction --amount 200 --category groceries --type expense --description "Weekly shopping"

# Получение транзакций
python -m client.cli get-transactions

# Генерация отчёта
python -m client.cli generate-report --month 2023-10

# Экспорт отчёта
python -m client.cli export-report --month 2023-10 --format json