import sys
try:
    import alembic.config
    alembic.config.main(argv=['init', 'alembic'])
    print("Alembic initialization successful.")
except Exception as e:
    print(f"Error initializing alembic: {e}")
