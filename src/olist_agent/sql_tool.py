"""Restrict agent SQL to bounded, read-only queries against modeled tables."""

from pathlib import Path

import duckdb
import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {"fact_orders", "fact_order_items", "fact_reviews", "dim_customers",
                  "dim_products", "dim_sellers"}
BLOCKED_NODES = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter,
                 exp.Command, exp.Copy, exp.Merge, exp.Attach, exp.Pragma)
BLOCKED_FUNCTIONS = {"read_csv", "read_csv_auto", "read_parquet", "sqlite_scan",
                     "postgres_scan", "httpfs", "query", "query_table"}


def validate_sql(query: str) -> str:
    try:
        statements = sqlglot.parse(query, read="duckdb")
    except sqlglot.errors.ParseError as error:
        raise ValueError("Invalid SQL") from error
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError("Only a single SELECT query is allowed")
    statement = statements[0]
    if any(isinstance(node, BLOCKED_NODES) for node in statement.walk()):
        raise ValueError("SQL contains a forbidden operation")
    cte_names = {cte.alias.lower() for cte in statement.find_all(exp.CTE)}
    for table in statement.find_all(exp.Table):
        if table.db or table.catalog or table.name.lower() not in ALLOWED_TABLES | cte_names:
            raise ValueError("SQL references a table outside the modeled schema")
    for function in statement.find_all(exp.Func):
        if function.sql_name().lower() in BLOCKED_FUNCTIONS:
            raise ValueError("External data access is forbidden")
    return statement.sql(dialect="duckdb")


def query_database(database: Path, query: str, limit: int = 100) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100")
    safe_sql = validate_sql(query)
    with duckdb.connect(str(database), read_only=True, config={"enable_external_access": "false"}) as con:
        result = con.execute(f"SELECT * FROM ({safe_sql}) AS answer LIMIT ?", [limit])
        columns = [item[0] for item in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]