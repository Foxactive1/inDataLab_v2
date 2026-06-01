import pandas as pd

class SQLExecutor:

    @staticmethod
    def execute(conn, query):

        return pd.read_sql(query, conn)