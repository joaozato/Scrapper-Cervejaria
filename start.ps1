# Script to start CARGO Disponibilidade locally
Write-Host "Starting PostgreSQL database..."
docker compose up -d

Write-Host "Starting Backend API on http://localhost:8000 ..."
Start-Process -NoNewWindow -FilePath "powershell" -ArgumentList "-Command `"cd backend; .\venv\Scripts\uvicorn app.main:app --reload --port 8000`""

Write-Host "Starting Frontend App on http://localhost:5173 ..."
Start-Process -NoNewWindow -FilePath "powershell" -ArgumentList "-Command `"cd frontend; npm run dev`""

Write-Host "All services started!"
Write-Host "Admin Login: admin / change_me"
