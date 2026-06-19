$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "=== Démarrage infrastructure Docker ===" -ForegroundColor Cyan

if (-not (Test-Path ".\compose.yaml")) {
    Write-Host "ERREUR : compose.yaml introuvable à la racine du projet." -ForegroundColor Red
    Write-Host "Vérifie que le fichier compose.yaml est bien dans : $ProjectRoot" -ForegroundColor Yellow
    exit 1
}

Write-Host "Lancement avec Docker Compose..." -ForegroundColor Cyan
docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Docker Compose n'a pas pu démarrer les conteneurs." -ForegroundColor Yellow
    Write-Host "Cela peut arriver si les conteneurs kafka/zookeeper/mongodb existent déjà sur ce PC." -ForegroundColor Yellow
    Write-Host "On essaie donc de démarrer les conteneurs existants sans rien supprimer..." -ForegroundColor Yellow

    docker start zookeeper
    docker start kafka
    docker start mongodb
}

Write-Host ""
Write-Host "Attente du démarrage Kafka / MongoDB..." -ForegroundColor Yellow
Start-Sleep -Seconds 45

Write-Host ""
Write-Host "Vérification des conteneurs..." -ForegroundColor Cyan
docker ps --filter "name=zookeeper" --filter "name=kafka" --filter "name=mongodb"

Write-Host ""
Write-Host "Vérification du topic Kafka network-flows..." -ForegroundColor Cyan
docker exec -it kafka kafka-topics --bootstrap-server kafka:29092 --list

Write-Host ""
Write-Host "Vidage MongoDB pour une démo propre..." -ForegroundColor Yellow
python -c "from pymongo import MongoClient; c=MongoClient('mongodb://localhost:27017/'); c['ids_db']['predictions'].delete_many({}); print('MongoDB vidé')"

Write-Host ""
Write-Host "Lancement Spark Streaming..." -ForegroundColor Green
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', "$ProjectRoot\scripts\01_start_spark.ps1"

Write-Host "Attente du démarrage Spark..." -ForegroundColor Yellow
Start-Sleep -Seconds 35

Write-Host ""
Write-Host "Lancement Dashboard Streamlit..." -ForegroundColor Green
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', "$ProjectRoot\scripts\02_start_dashboard.ps1"

Write-Host ""
Write-Host "Base du projet lancée." -ForegroundColor Cyan
Write-Host "Maintenant lance le producer manuellement avec le nombre de flux souhaité." -ForegroundColor Yellow
Write-Host ""
Write-Host "Exemple démo lente : python producer\kafka_producer.py --limit 50 --sleep 1" -ForegroundColor White
Write-Host "Exemple moyen      : python producer\kafka_producer.py --limit 500 --sleep 0.1" -ForegroundColor White
Write-Host "Exemple rapide     : python producer\kafka_producer.py --limit 1000 --sleep 0.01" -ForegroundColor White
Write-Host ""
Write-Host "Dashboard : http://localhost:8501/" -ForegroundColor Green

