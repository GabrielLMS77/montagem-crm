
from clinicaflow.core.database import test_connection

resultado = test_connection()

print("Conexão com o PostgreSQL funcionando!")
print("Resultado do teste:", resultado)
