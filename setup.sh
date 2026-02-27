#!/bin/bash
# AURA-VIP Setup Script for Unix/Linux/macOS

echo "🚀 Setting up AURA-VIP Orchestration System..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.template .env
    echo "✅ .env file created. Please update with your configuration."
else
    echo "✅ .env file already exists."
fi

# Backend setup
echo ""
echo "🐍 Setting up Python backend..."
cd backend

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing Python dependencies..."
pip install -r requirements.txt

cd ..

# Frontend setup
echo ""
echo "⚛️  Setting up React frontend..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "Installing Node dependencies..."
    npm install
else
    echo "✅ Node modules already installed."
fi

cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the backend:"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "To start the frontend:"
echo "  cd frontend"
echo "  npm run dev"
