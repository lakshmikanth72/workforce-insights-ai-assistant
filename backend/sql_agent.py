"""Safe, predefined read-only SQL answers for common workforce questions."""

from typing import Any, Dict, List, Optional, Tuple

from .database import get_connection

SCHEMA = """workforce_ai_view(employee_id, age, gender, marital_status, education,
education_field, department, job_role, job_level, business_travel,
total_working_years, years_at_company, years_in_current_role,
years_since_last_promotion, years_with_curr_manager, num_companies_worked,
distance_from_home, overtime, daily_rate, hourly_rate, monthly_income,
monthly_rate, percent_salary_hike, stock_option_level, environment_satisfaction,
job_involvement, job_satisfaction, relationship_satisfaction,
work_life_balance, performance_rating, training_times_last_year, attrition,
attrition_flag)
employee_attrition_predictions(employee_id, predicted_attrition,
predicted_attrition_label, attrition_probability, risk_category)"""


def _query_for(question: str) -> Optional[Tuple[str, str]]:
    text = question.lower().strip()

    # 1. High-risk employees by department (Must join on employee_id)
    if ("high risk" in text or "high-risk" in text) and "department" in text:
        return (
            "SELECT w.department, COUNT(*) AS high_risk_count "
            "FROM employee_attrition_predictions p "
            "JOIN workforce_ai_view w ON p.employee_id = w.employee_id "
            "WHERE LOWER(p.risk_category) LIKE '%high%' "
            "GROUP BY w.department "
            "ORDER BY high_risk_count DESC;",
            "High-risk employees by department",
        )

    # 2. Department with highest attrition
    if ("highest attrition" in text or "highest turnover" in text) and "department" in text:
        return (
            "SELECT department, "
            "COUNT(*) FILTER (WHERE LOWER(attrition_flag::text) IN ('1', 'true', 'yes') OR LOWER(attrition::text) = 'yes') AS attrition_count, "
            "COUNT(*) AS total_employees, "
            "ROUND(100.0 * COUNT(*) FILTER (WHERE LOWER(attrition_flag::text) IN ('1', 'true', 'yes') OR LOWER(attrition::text) = 'yes') / NULLIF(COUNT(*), 0), 2) AS attrition_rate "
            "FROM workforce_ai_view "
            "GROUP BY department "
            "ORDER BY attrition_rate DESC NULLS LAST "
            "LIMIT 1;",
            "The department with the highest attrition",
        )

    # 3. Overall attrition rate
    if "attrition rate" in text or "turnover rate" in text:
        return (
            "SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE LOWER(attrition_flag::text) IN ('1', 'true', 'yes') OR LOWER(attrition::text) = 'yes') / NULLIF(COUNT(*), 0), 2) AS attrition_rate_percent "
            "FROM workforce_ai_view;",
            "The workforce attrition rate",
        )

    # 4. Employees who actually left (Must be checked before generic employee count)
    if "actually left" in text or "have left" in text or "who left" in text or "actual attrition" in text or "how many left" in text:
        return (
            "SELECT COUNT(*) FILTER (WHERE LOWER(attrition_flag::text) IN ('1', 'true', 'yes') OR LOWER(attrition::text) = 'yes') AS actual_attrition_count "
            "FROM workforce_ai_view;",
            "The number of employees who actually left",
        )

    # 5. Employees predicted to leave
    if "predicted to leave" in text or "predicted attrition" in text or "predicted to quit" in text:
        return (
            "SELECT COUNT(*) AS predicted_to_leave_count "
            "FROM employee_attrition_predictions "
            "WHERE LOWER(predicted_attrition::text) IN ('1', 'true', 'yes') "
            "OR LOWER(predicted_attrition_label::text) IN ('yes', 'leave', 'left');",
            "The number of employees predicted to leave",
        )

    # 6. High-risk employees count
    if "high risk" in text or "high-risk" in text:
        return (
            "SELECT COUNT(*) AS high_risk_count "
            "FROM employee_attrition_predictions "
            "WHERE LOWER(risk_category) LIKE '%high%';",
            "The number of high-risk employees",
        )

    # 7. Medium-risk employees count
    if "medium risk" in text or "medium-risk" in text or "moderate risk" in text:
        return (
            "SELECT COUNT(*) AS medium_risk_count "
            "FROM employee_attrition_predictions "
            "WHERE LOWER(risk_category) LIKE '%medium%';",
            "The number of medium-risk employees",
        )

    # 8. Low-risk employees count
    if "low risk" in text or "low-risk" in text:
        return (
            "SELECT COUNT(*) AS low_risk_count "
            "FROM employee_attrition_predictions "
            "WHERE LOWER(risk_category) LIKE '%low%';",
            "The number of low-risk employees",
        )

    # 9. Average job satisfaction
    if "average" in text and "satisfaction" in text:
        return (
            "SELECT ROUND(AVG(job_satisfaction)::numeric, 2) AS average_job_satisfaction "
            "FROM workforce_ai_view;",
            "The average job satisfaction",
        )

    # 10. Overtime count
    if "overtime" in text:
        return (
            "SELECT COUNT(*) FILTER (WHERE LOWER(overtime::text) = 'yes') AS overtime_employee_count "
            "FROM workforce_ai_view;",
            "The number of employees working overtime",
        )

    # 11. Specific department employee count
    for dept in ("sales", "research & development", "human resources"):
        if dept in text and ("employee" in text or "headcount" in text or "how many" in text or "people" in text):
            return (
                f"SELECT COUNT(*) AS employee_count FROM workforce_ai_view WHERE LOWER(department) = '{dept}';",
                f"The number of employees in {dept.title()}",
            )

    # 12. Total employee count / headcount
    if "how many employees" in text or "employee count" in text or "headcount" in text or "total employees" in text:
        return (
            "SELECT COUNT(*) AS employee_count FROM workforce_ai_view;",
            "The total employee count",
        )

    return None


def _format_explanation(label: str, rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return f"{label}: No data returned."
    if len(rows) == 1:
        row = rows[0]
        details = ", ".join(f"{k.replace('_', ' ').title()}: {v}" for k, v in row.items())
        return f"{label}: {details}."
    # Multiple rows (e.g. department breakdown)
    items = []
    for r in rows:
        vals = list(r.values())
        if len(vals) >= 2:
            items.append(f"{vals[0]} ({vals[1]})")
        else:
            items.append(str(vals[0]))
    return f"{label}: {', '.join(items)}."


def answer_sql_question(question: str) -> Optional[Dict[str, Any]]:
    selected = _query_for(question)
    if selected is None:
        return None
    sql, label = selected

    # Safety check: ensure query is read-only SELECT
    normalized_sql = sql.lstrip().upper()
    if not normalized_sql.startswith("SELECT") or any(
        word in normalized_sql for word in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE")
    ):
        return {"sql": sql, "rows": [], "explanation": "Only safe read-only queries are permitted."}

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql)
            columns = [description[0] for description in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return {"sql": sql, "rows": rows, "explanation": _format_explanation(label, rows)}
except Exception as error:
    print(f"POSTGRESQL ERROR: {type(error).__name__}: {error}", flush=True)
    return {
        "sql": sql,
        "rows": [],
        "explanation": f"Unable to query PostgreSQL ({label}): {error}. Please verify database connection and views.",
    }
finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
