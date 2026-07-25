import logging
from db.client import get_session
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)

def main():
    with get_session() as session:
        if session is None:
            print("DB not available")
            return
        
        session.execute(
            text("UPDATE projects SET repo_path = 'D:/AUTOMATA' WHERE id = '0f90c2f9-0d9a-4787-ab07-8d4699fb4b13'")
        )
        print("Updated project repo_path to D:/AUTOMATA")

if __name__ == "__main__":
    main()
