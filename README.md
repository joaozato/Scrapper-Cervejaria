# Captador de Cargas (Smart Cargas) — Projeto de Portfólio

> **Aviso:** versão de portfólio. Nomes de empresa, credenciais, usuários, URLs e dados reais foram removidos ou substituídos por valores fictícios (`CARGO`, `Portal`, `example.com`). O código é mostrado apenas para demonstrar arquitetura e habilidades técnicas; não está afiliado a nenhuma empresa e não contém dados operacionais. Use variáveis de ambiente para qualquer configuração.

**Stack:** FastAPI · SQLAlchemy async · PostgreSQL · Playwright · APScheduler · WebSockets · React 19 · Vite · Zustand · Docker


O **CARGO Disponibilidade** é um sistema corporativo interno desenvolvido para mensurar a disponibilidade de motoristas (integrado com planilhas do Google Sheets) e cruzar esses dados em tempo real com as cargas disponíveis no sistema Portal. O objetivo principal é fornecer uma visão clara para a equipe operacional, otimizando o cruzamento de motoristas prontos com as melhores cargas, expandindo as operações e aumentando o faturamento da CARGO.

## 🚀 Arquitetura e Funcionalidades

O projeto é dividido em duas partes principais que entregam os seguintes recursos:

- **Frontend (`/frontend`)**: Desenvolvido em React + Vite. 
  - **Dashboard Inteligente**: Gráficos de análise, KPI's de peso e valor total.
  - **Listagem de Cargas e Motoristas**: Filtros avançados, visualização de *tags* e histórico de *rounds* (Smart Cargas e Pool de Cargas).
  - **Exportação CSV**: Exportação otimizada de relatórios (compatível nativamente com Excel em PT-BR).
  - **Live Monitor**: Acompanhamento visual em tempo real (screenshots/logs) da atividade do robô *headless* no Portal.
- **Backend (`/backend`)**: Desenvolvido em Python com FastAPI. 
  - Orquestra a API e gerencia o banco de dados PostgreSQL.
  - **Scraper Inteligente**: Executa rotinas avançadas e furtivas de captura de cargas via Playwright.
  - **Match Automático**: Algoritmos para cruzar a "Rota Frequente" e localização dos motoristas com as melhores cargas disponíveis no momento.
  - **Sincronização**: Integração contínua e em segundo plano com planilhas do Google Sheets.

### Principais Tecnologias
- **Backend**: FastAPI, SQLAlchemy, Asyncpg, Playwright (Scraper), APScheduler, Pydantic.
- **Frontend**: React 19, Vite, Recharts, Axios, Zustand.
- **Banco de Dados**: PostgreSQL.
- **Hospedagem**: [Railway](https://railway.app/).

## 🤖 Scraper do Portal (Regras Críticas)

O sistema conta com um robô invisível (*headless*) feito com **Playwright** que acessa o Portal para raspar os cards de cargas (`scraper_portal.py`). 

> [!CAUTION]
> **REGRAS INVIOLÁVEIS DO SCRAPER:**
> 1. O script é de **extrema importância** e serve **APENAS PARA LER** cargas.
> 2. **NUNCA** adicione lógicas que confirmem, editem ou aceitem cargas automaticamente, fora da exceção explícita abaixo. A visão do bot é e sempre deve ser restrita aos ícones de informação.
> 3. O script possui mecanismos rigorosos (*playwright_stealth*) e **delays estratégicos** (uso de `asyncio.sleep` com valores randômicos) entre navegação, digitação e cliques. Qualquer alteração no scraper deve **obrigatoriamente** respeitar esses atrasos para evitar detecção de bots e bloqueio da conta CARGO.
>
> **Exceção controlada "Assistente" (somente branch `dev`):** existe um modo opcional de aceite e confirmação automática, restrito a uma lista fechada de rotas, só no Smart Cargas, só quando ativado manualmente pelo operador. Nunca se aplica em produção/`main` sem uma nova decisão explícita. Ver `docs/adr/` antes de mexer em qualquer código de aceite/confirmação.

## 🔒 Segurança e LGPD

Por ser um sistema corporativo contendo dados sensíveis de viagens e faturamento, a segurança é prioridade máxima:
- O acesso a rotas de manipulação do banco de dados (mesmo rotas de correção/hotfix temporárias) deve ser evitado. Manutenções estruturais devem ser feitas através da inicialização da aplicação (ex: `main.py` injetando comandos SQL no *lifespan*) ou conexões protegidas via painel da Railway.
- Todos os dados trafegados estão sujeitos às normativas da LGPD.

## ⚙️ Como Rodar o Projeto Localmente

### Pré-requisitos
- Node.js (v20+)
- Python (3.11+)
- PostgreSQL (rodando localmente ou via Docker na porta 5433)

### Passo a Passo

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/<seu-usuario>/captador-cargas.git
   cd cargo-disponibilidade
   ```

2. **Configuração do Backend:**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # No Windows: venv\Scripts\activate
   pip install -r requirements.txt
   
   # Instalar navegadores do Playwright
   playwright install chromium
   
   # Criar arquivo .env e preencher as variáveis (DATABASE_URL, PORTAL_USER, etc)
   cp .env.example .env 
   
   # Rodar a API
   uvicorn app.main:app --reload
   ```

3. **Configuração do Frontend:**
   ```bash
   cd ../frontend
   npm install
   npm run dev
   ```

4. **Acesso:**
   Abra `http://localhost:5173` no seu navegador. A API estará rodando em `http://localhost:8000`.

## 📦 Deploy (Railway)

O projeto está configurado com um `Dockerfile` multi-stage na raiz que compila o frontend e serve-o de forma embutida com o backend FastAPI.

Ao realizar um push para a *branch* principal, a Railway automaticamente:
1. Constrói o *bundle* do React.
2. Instala as dependências Python e os drivers do Playwright.
3. Executa as validações e correções de banco de dados (`main.py`).
4. Inicia os serviços (API na porta 8000, Scraper no background).

---
*Desenvolvido e mantido pela equipe a transportadora.*
