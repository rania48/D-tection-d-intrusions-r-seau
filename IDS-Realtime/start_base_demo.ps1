Write-Host "=== Démarrage Docker ===" -ForegroundColor Cyan

docker start zookeeper
docker start kafka
docker start mongodb

Write-Host "Attente Kafka..." -ForegroundColor Yellow
Start-Sleep -Seconds 45

Write-Host "Test Kafka topic..." -ForegroundColor Cyan
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --list

Write-Host "Vidage MongoDB pour une démo propre..." -ForegroundColor Yellow
python -c "from pymongo import MongoClient; c=MongoClient('mongodb://localhost:27017/'); c['ids_db']['predictions'].delete_many({}); print('MongoDB vidé')"

Write-Host "Lancement Spark Streaming..." -ForegroundColor Green
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', 'C:\Users\Rania\OneDrive\Bureau\IDS-Realtime\scripts\01_start_spark.ps1'

Write-Host "Attente du démarrage Spark..." -ForegroundColor Yellow
Start-Sleep -Seconds 35

Write-Host "Lancement Dashboard Streamlit..." -ForegroundColor Green
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', 'C:\Users\Rania\OneDrive\Bureau\IDS-Realtime\scripts\02_start_dashboard.ps1'

Write-Host ""
Write-Host "Base du projet lancée." -ForegroundColor Cyan
Write-Host "Maintenant lance le producer manuellement avec le nombre de flux souhaité." -ForegroundColor Yellow
Write-Host ""
Write-Host "Exemple démo lente : python producer\kafka_producer.py --limit 50 --sleep 1" -ForegroundColor White
Write-Host "Exemple moyen : python producer\kafka_producer.py --limit 500 --sleep 0.1" -ForegroundColor White
Write-Host "Exemple rapide : python producer\kafka_producer.py --limit 1000 --sleep 0.01" -ForegroundColor White
Write-Host ""
Write-Host "Dashboard : http://localhost:8501/" -ForegroundColor Green
