# ADR 0001: Decisões Arquiteturais Iniciais e Padrões do Sistema

**Data:** 17 de Julho de 2026
**Status:** Aceito
**Contexto:** CARGO Disponibilidade - Painel Inteligente

## Contexto e Problema

A a transportadora necessita de um sistema corporativo interno para cruzar a disponibilidade de motoristas (dados vindos de planilhas) com as cargas disponíveis no sistema parceiro (Portal). O sistema parceiro não fornece uma API oficial, sendo necessária uma solução de captura de dados. Além disso, a segurança da informação é crítica (LGPD) e há necessidade de processamento em tempo real para tomada de decisões operacionais (match automático de cargas e motoristas).

## Decisões

### 1. Stack Tecnológico Base
- **Backend:** Python com **FastAPI**. Escolhido pela alta performance com rotinas assíncronas (essencial para scraping e websockets) e tipagem de dados segura (Pydantic).
- **Frontend:** **React 19 com Vite**. Escolhido pelo ecossistema rico, rapidez de build e facilidade na construção de interfaces dinâmicas (como o Dashboard e Live Monitor).
- **Banco de Dados:** **PostgreSQL** (com `asyncpg` e `SQLAlchemy`). Robusto, open-source e lida perfeitamente com a concorrência assíncrona da aplicação.

### 2. Estratégia de Integração e Captura de Dados
- **Decisão:** Utilizar o **Playwright** operando em modo *stealth* (`playwright_stealth`) como um robô em *background* acoplado ao backend.
- **Justificativa:** Devido à ausência de uma API oficial do Portal, precisamos simular um usuário real navegando.
- **Regras Críticas:** O bot deve agir com permissão **estrita de LEITURA**. Lógicas de aceite ou confirmação automática de carga foram banidas arquiteturalmente. O uso de delays randômicos (`asyncio.sleep`) é mandatório para preservar a furtividade e evitar bloqueios operacionais da conta CARGO.

### 3. Topologia de Deploy e Hospedagem
- **Decisão:** Utilizar a plataforma **Railway** com um `Dockerfile` *multi-stage* monolítico.
- **Justificativa:** O processo de CI/CD compila o projeto React (Frontend) e embuti os arquivos estáticos dentro da estrutura do FastAPI (Backend). Dessa forma, a aplicação inteira (API + Interface + Robô) roda em um único serviço (container) na porta 8000, barateando custos de infraestrutura e simplificando o gerenciamento do *deploy*.

### 4. Segurança, LGPD e Evolução do Banco de Dados
- **Decisão:** Proibir a criação de rotas ou endpoints públicos (mesmo que ocultos) para aplicar migrações ou manutenções de banco de dados. Qualquer alteração estrutural deve ser feita no bloco `lifespan` de inicialização no `main.py` ou via conexão direta segura.
- **Justificativa:** Evita brechas de segurança e rotas expostas que poderiam vazar dados corporativos e de faturamento, respeitando a LGPD.

### 5. Monitoramento Operacional
- **Decisão:** Criação de um **Live Monitor** trafegando dados via WebSockets.
- **Justificativa:** A equipe operacional não tem acesso a logs de servidor. O WebSocket permite transmitir as telas capturadas (screenshots) e logs do robô diretamente para a tela do sistema em tempo real, alertando caso a integração com o Portal precise de intervenção humana (ex: recadastro de login).

## Consequências

- **Positivas:** Temos um sistema unificado, escalável, de baixa latência e seguro. A operação consegue interagir visualmente com a saúde da automação (Live Monitor). O deploy único reduz a sobrecarga de devops da equipe.
- **Riscos (Mitigados):** A evolução do schema do banco de dados (sem o uso de um migrador dedicado como o Alembic) exige atenção manual e cuidadosa nas instruções SQL adicionadas ao `main.py`. A dependência de Web Scraping é sensível a mudanças na interface da plataforma terceira; mitigamos isso garantindo acesso rápido a evidências visuais no painel.
