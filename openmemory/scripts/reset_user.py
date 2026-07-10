import sys
import os

# Adiciona o diretório da API ao path para poder importar os módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../api')))

from sqlalchemy.orm import sessionmaker
from app.database import engine
from app.models import User, Machine, MachineStatus

def reset_user(name: str):
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        # Encontra o usuário
        user = db.query(User).filter(User.name == name).first()
        
        if not user:
            print(f"Usuário '{name}' não encontrado.")
            return

        print(f"Usuário encontrado: {user.name} (Google Sub: {user.google_sub})")

        # Encontra a máquina vinculada a este usuário
        machines = db.query(Machine).filter(Machine.linked_user_id == user.id).all()
        
        if not machines:
            print("O usuário não possui nenhuma máquina vinculada.")
        
        for machine in machines:
            print(f"Desvinculando máquina: {machine.hostname}")
            machine.linked_user_id = None
            machine.status = MachineStatus.unlinked
            machine.linked_at = None
            machine.linked_by = None
            db.add(machine)
            
        db.commit()
        print("Reset concluído com sucesso!")
        
    except Exception as e:
        db.rollback()
        print(f"Erro ao resetar: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        reset_user(sys.argv[1])
    else:
        print("Uso: python reset_user.py 'Nome do Usuário'")
