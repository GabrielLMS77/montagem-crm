# Clinicaflow

## Executar com Docker

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e em execução.

1. Crie o arquivo de configuração local:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Edite `.env` e preencha os dados da NFS-e quando for utilizá-la. O `DATABASE_URL` desse arquivo pode permanecer como está: o Docker o configura automaticamente para o banco interno.

3. Inicie a aplicação:

   ```powershell
   docker compose up --build -d
   ```

4. Abra http://localhost:8000. A documentação da API fica em http://localhost:8000/docs.

Na primeira inicialização, as migrações do banco são aplicadas automaticamente. Os dados do PostgreSQL e os XMLs da NFS-e ficam em volumes Docker, portanto permanecem após `docker compose down`.

### Comandos úteis

```powershell
# Acompanhar os logs
docker compose logs -f

# Parar os serviços, preservando dados
docker compose down

# Parar e remover também todos os dados locais (ação irreversível)
docker compose down -v
```

Não compartilhe o arquivo `.env` nem certificados `.pfx`/`.p12`: eles podem conter credenciais e dados fiscais. Para um ambiente que ficará exposto à internet, defina uma senha forte em `POSTGRES_PASSWORD` antes de iniciar os serviços.
